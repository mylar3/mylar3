#  This file is part of Mylar.
# -*- coding: utf-8 -*-
#
#  Mylar is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Mylar is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with Mylar.  If not, see <http://www.gnu.org/licenses/>.

import os
import time
import datetime
import threading
import json
import logging
import re
import shutil
import socket

import requests

import mylar
from mylar import logger, db, helpers


# ── Health Check System ──
# Provides periodic health monitoring for Mylar3 components.
# Checks infrastructure (folders, disk, DB), providers (ComicVine, indexers),
# download clients (SABnzbd, NZBGet, qBittorrent, Transmission, rTorrent,
# Deluge, uTorrent), and scheduler tasks.
#
# Results are stored in the health_checks SQLite table and pushed to
# the browser via SSE for real-time banner and badge updates.
#
# See docs/health-dashboard/ for full architecture documentation.


# ── HealthCheckResult ──

class HealthCheckResult:
    """Single health check finding — one problem or informational item."""

    VALID_SEVERITIES = ('error', 'warning', 'notice')
    VALID_TYPES = ('infrastructure', 'provider', 'download', 'task', 'config', 'detected')

    def __init__(self, check_type, check_name, severity, message,
                 wiki_url=None, source='health_check', metadata=None):
        if severity not in self.VALID_SEVERITIES:
            raise ValueError('Invalid severity: %s' % severity)

        self.check_type = check_type
        self.check_name = check_name
        self.severity = severity
        self.message = message
        self.wiki_url = wiki_url or self._default_wiki_url(check_name)
        self.source = source
        self.metadata = metadata or {}
        self.first_seen = datetime.datetime.utcnow().isoformat()
        self.last_seen = self.first_seen
        self.resolved_at = None
        self.check_count = 1
        self.db_id = None  # set when loaded from / saved to DB

    def to_dict(self):
        """Convert to JSON-serializable dictionary."""
        return {
            'id': self.db_id,
            'check_type': self.check_type,
            'check_name': self.check_name,
            'severity': self.severity,
            'message': self.message,
            'wiki_url': self.wiki_url,
            'source': self.source,
            'metadata': self.metadata,
            'first_seen': self.first_seen,
            'last_seen': self.last_seen,
            'check_count': self.check_count,
            'resolved_at': self.resolved_at,
        }

    @staticmethod
    def from_db_row(row):
        """Create a HealthCheckResult from a database row dict."""
        result = HealthCheckResult(
            check_type=row['check_type'],
            check_name=row['check_name'],
            severity=row['severity'],
            message=row['message'],
            wiki_url=row['wiki_url'],
            source=row['source'] if row['source'] else 'health_check',
            metadata=json.loads(row['metadata']) if row['metadata'] else {},
        )
        result.first_seen = row['first_seen']
        result.last_seen = row['last_seen']
        result.resolved_at = row['resolved_at'] if 'resolved_at' in row.keys() else None
        result.check_count = row['check_count'] if row['check_count'] else 1
        result.db_id = row['id']
        return result

    @staticmethod
    def _default_wiki_url(check_name):
        base = 'https://github.com/mylar3/mylar3/wiki/Health-Checks'
        return '%s#%s' % (base, check_name.replace('_', '-'))


# ── HealthCheckRunner ──

class HealthCheckRunner:
    """Runs health checks on Mylar3 components and manages results."""

    # per-check intervals in minutes — expensive checks run less often
    CHECK_INTERVALS = {
        'root_folder':          5,
        'disk_space':           15,
        'database_integrity':   360,  # 6 hours
        'comicvine_api':        10,
        'indexers':             10,
        'no_indexers':          10,
        'download_client':      5,
        'download_category':    30,
        'stalled_downloads':    30,
        'stuck_tasks':          5,
        'failed_postprocessing': 10,
        'update_available':     360,  # 6 hours
        'permissions':          15,
        'no_download_client':   10,
        'api_key_missing':      10,
    }

    def __init__(self):
        self._lock = threading.Lock()
        self._results = []
        self._last_run = None
        self._check_timestamps = {}  # {check_name: datetime} — when each check last ran

    def run_all_checks(self, force=False):
        """Run all health checks and update DB, memory, and browser.

        Args:
            force: If True, bypass per-check interval gating (used for manual rechecks).
        """
        if not mylar.CONFIG.HEALTH_CHECK_ENABLED:
            return

        start_time = time.time()
        logger.info('[HealthCheck] Starting health check run')

        results = []
        checks_that_ran = set()  # track which check_names actually executed

        # each check is wrapped in try/except so one failure doesn't kill others
        check_methods = [
            ('root_folder',           self.check_root_folders),
            ('comicvine_api',         self.check_comicvine_api),
            ('indexers',              self.check_indexers),
            ('no_indexers',           self.check_no_indexers),
            ('download_client',       self.check_download_client),
            ('download_category',     self.check_download_category),
            ('disk_space',            self.check_disk_space),
            ('stuck_tasks',           self.check_stuck_tasks),
            ('failed_postprocessing', self.check_failed_postprocessing),
            ('stalled_downloads',     self.check_stalled_downloads),
            ('update_available',      self.check_update_available),
            ('permissions',           self.check_permissions),
            ('no_download_client',    self.check_no_download_client),
            ('api_key_missing',       self.check_api_key_missing),
            ('database_integrity',    self.check_database_integrity),
        ]

        for check_name, check_method in check_methods:
            if not force and not self._should_run(check_name):
                continue
            checks_that_ran.add(check_name)
            try:
                check_results = check_method()
                if not check_results:
                    logger.fdebug('[HealthCheck] %s: passed' % check_name)
                for cr in check_results:
                    if cr.severity == 'error':
                        logger.error('[HealthCheck] %s: %s' % (cr.check_name, cr.message))
                    elif cr.severity == 'warning':
                        logger.warn('[HealthCheck] %s: %s' % (cr.check_name, cr.message))
                    else:
                        logger.info('[HealthCheck] %s: %s' % (cr.check_name, cr.message))
                results.extend(check_results)
                self._check_timestamps[check_name] = datetime.datetime.utcnow()
            except Exception as e:
                # don't let one broken check kill all checks
                logger.error('[HealthCheck] Check "%s" threw exception: %s' % (check_name, str(e)[:200]))

        # merge: keep previous results for checks that were SKIPPED this cycle
        ran_check_names = {r.check_name for r in results}
        fresh_results = list(results)  # snapshot before merging carried-forward items
        with self._lock:
            for prev in self._results:
                if prev.check_name not in checks_that_ran and prev.check_name not in ran_check_names:
                    results.append(prev)
            _sev_order = {'error': 0, 'warning': 1, 'notice': 2}
            results.sort(key=lambda r: (_sev_order.get(r.severity, 3), r.check_name))
            self._results = results
            self._last_run = datetime.datetime.utcnow()

        # persist only FRESH results (from checks that ran) — carried-forward
        # items already have correct DB state, no need to bump their count/last_seen
        self._save_to_db(fresh_results)
        self._resolve_cleared(results, checks_that_ran)
        self._cleanup_old()

        # push to browsers
        self._push_sse(results)

        # update global for fast reads
        mylar.HEALTH_RESULTS = [r.to_dict() for r in results]

        elapsed = time.time() - start_time
        error_count = sum(1 for r in results if r.severity == 'error')
        warning_count = sum(1 for r in results if r.severity == 'warning')
        notice_count = sum(1 for r in results if r.severity == 'notice')
        summary_msg = '[HealthCheck] Completed in %.2fs — %d errors, %d warnings, %d notices (%d/%d checks ran)' % (
            elapsed, error_count, warning_count, notice_count,
            len(checks_that_ran), len(check_methods))

        if error_count > 0:
            logger.error(summary_msg)
        elif warning_count > 0:
            logger.warn(summary_msg)
        else:
            logger.info(summary_msg)

    def get_results(self):
        """Thread-safe read of current active health check results."""
        with self._lock:
            return list(self._results)

    def get_summary(self):
        """Get issue counts by severity."""
        with self._lock:
            results = list(self._results)
        return {
            'errors': sum(1 for r in results if r.severity == 'error'),
            'warnings': sum(1 for r in results if r.severity == 'warning'),
            'notices': sum(1 for r in results if r.severity == 'notice'),
            'total': len(results),
        }

    def last_run_iso(self):
        """Return last run time as ISO string, or None."""
        with self._lock:
            if self._last_run:
                return self._last_run.isoformat()
            return None

    def dismiss(self, check_id):
        """Mark a health check as resolved/dismissed by the user."""
        myconn = db.DBConnection()
        myconn.action(
            "UPDATE health_checks SET is_resolved=1, resolved_at=? WHERE id=?",
            [datetime.datetime.utcnow().isoformat(), check_id]
        )
        # remove from in-memory results
        with self._lock:
            self._results = [r for r in self._results if r.db_id != check_id]
        mylar.HEALTH_RESULTS = [r.to_dict() for r in self.get_results()]
        self._push_sse(self.get_results())

    def ingest_log_finding(self, result):
        """Accept a finding from the log handler and add to results."""
        with self._lock:
            # check if we already have an active result for this check_name
            existing = next((r for r in self._results if r.check_name == result.check_name), None)
            if existing:
                existing.last_seen = datetime.datetime.utcnow().isoformat()
                existing.check_count += 1
            else:
                self._results.append(result)

        # persist to DB
        self._save_single_to_db(result)
        # update browser
        mylar.HEALTH_RESULTS = [r.to_dict() for r in self.get_results()]
        self._push_sse(self.get_results())

    def load_from_db(self):
        """Load active health check records from database on startup."""
        try:
            myconn = db.DBConnection()
            rows = myconn.select(
                "SELECT * FROM health_checks WHERE is_resolved=0 "
                "ORDER BY CASE severity WHEN 'error' THEN 0 WHEN 'warning' THEN 1 WHEN 'notice' THEN 2 ELSE 3 END, last_seen DESC"
            )
            with self._lock:
                self._results = [HealthCheckResult.from_db_row(r) for r in rows]
            logger.info('[HealthCheck] Loaded %d active issues from database' % len(rows))
        except Exception as e:
            logger.error('[HealthCheck] Failed to load from database: %s' % e)

    def clear_resolved_history(self):
        """Delete all resolved health check records from the database."""
        try:
            myconn = db.DBConnection()
            myconn.action("DELETE FROM health_checks WHERE is_resolved=1")
            logger.info('[HealthCheck] Cleared all resolved history')
        except Exception as e:
            logger.error('[HealthCheck] Failed to clear resolved history: %s' % e)

    def get_resolved_history(self, days=None):
        """Query resolved health check records for the UI."""
        if days is None:
            days = int(mylar.CONFIG.HEALTH_HISTORY_DAYS or 30)
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
        myconn = db.DBConnection()
        rows = myconn.select(
            "SELECT * FROM health_checks WHERE is_resolved=1 AND resolved_at>=? ORDER BY resolved_at DESC",
            [cutoff]
        )
        return [HealthCheckResult.from_db_row(r).to_dict() for r in rows]

    # ── Check Methods ──

    def check_root_folders(self):
        """Check that configured comic root folders exist and are accessible."""
        results = []
        paths_to_check = []

        if mylar.CONFIG.DESTINATION_DIR:
            paths_to_check.append(mylar.CONFIG.DESTINATION_DIR)
        if mylar.CONFIG.MULTIPLE_DEST_DIRS:
            for d in mylar.CONFIG.MULTIPLE_DEST_DIRS.split(','):
                d = d.strip()
                if d:
                    paths_to_check.append(d)

        for path in paths_to_check:
            if not os.path.exists(path):
                results.append(HealthCheckResult(
                    check_type='infrastructure',
                    check_name='root_folder',
                    severity='error',
                    message='Root folder not accessible: %s — path does not exist or is not mounted.' % path,
                    metadata={'path': path, 'reason': 'not_found'}
                ))
            elif not os.access(path, os.R_OK):
                results.append(HealthCheckResult(
                    check_type='infrastructure',
                    check_name='root_folder',
                    severity='error',
                    message='Root folder not readable: %s — check permissions.' % path,
                    metadata={'path': path, 'reason': 'not_readable'}
                ))
        return results

    def check_comicvine_api(self):
        """Check ComicVine API connectivity and key validity."""
        results = []
        api_key = mylar.CONFIG.COMICVINE_API

        if not api_key or api_key in ('None', ''):
            return []  # check_api_key_missing handles this case

        test_url = '%sissue/1/?api_key=%s&format=json' % (mylar.CVURL or 'https://comicvine.gamespot.com/api/', api_key)
        try:
            resp = requests.get(test_url, timeout=5, headers=mylar.CV_HEADERS, verify=mylar.CONFIG.CV_VERIFY)
            if resp.status_code == 200:
                return []  # healthy
            elif resp.status_code == 401:
                results.append(HealthCheckResult(
                    check_type='provider',
                    check_name='comicvine_api',
                    severity='error',
                    message='ComicVine API key is invalid — returned 401 Unauthorized.',
                    metadata={'status_code': 401}
                ))
            elif resp.status_code == 429:
                results.append(HealthCheckResult(
                    check_type='provider',
                    check_name='comicvine_api',
                    severity='warning',
                    message='ComicVine API rate limit exceeded — returned 429. Requests will be delayed.',
                    metadata={'status_code': 429}
                ))
            else:
                results.append(HealthCheckResult(
                    check_type='provider',
                    check_name='comicvine_api',
                    severity='error',
                    message='ComicVine API returned unexpected status %d.' % resp.status_code,
                    metadata={'status_code': resp.status_code}
                ))
        except requests.exceptions.Timeout:
            results.append(HealthCheckResult(
                check_type='provider',
                check_name='comicvine_api',
                severity='error',
                message='ComicVine API unreachable — connection timed out after 5s. All metadata lookups will fail.',
                metadata={'error': 'timeout'}
            ))
        except requests.exceptions.ConnectionError as e:
            results.append(HealthCheckResult(
                check_type='provider',
                check_name='comicvine_api',
                severity='error',
                message='ComicVine API connection failed: %s' % str(e)[:200],
                metadata={'error': 'connection_error'}
            ))
        except Exception as e:
            results.append(HealthCheckResult(
                check_type='provider',
                check_name='comicvine_api',
                severity='error',
                message='ComicVine API check failed: %s' % str(e)[:200],
                metadata={'error': str(type(e).__name__)}
            ))
        return results

    def check_stuck_tasks(self):
        """Check for scheduler tasks that have been running too long."""
        results = []
        stale_minutes = int(mylar.CONFIG.HEALTH_STALE_TASK_MIN or 60)

        task_statuses = {
            'Monitor': mylar.MONITOR_STATUS,
            'Search': mylar.SEARCH_STATUS,
            'RSS': mylar.RSS_STATUS,
            'Weekly Pull': mylar.WEEKLY_STATUS,
            'Version Check': mylar.VERSION_STATUS,
        }

        for task_name, status in task_statuses.items():
            if status == 'Running':
                try:
                    myconn = db.DBConnection()
                    job = myconn.select(
                        "SELECT current_run FROM jobhistory WHERE JobName=?",
                        [task_name]
                    )
                    if job and job[0]['current_run']:
                        started = job[0]['current_run']
                        try:
                            start_dt = datetime.datetime.fromisoformat(started)
                            elapsed = (datetime.datetime.utcnow() - start_dt).total_seconds() / 60
                            if elapsed >= stale_minutes:
                                results.append(HealthCheckResult(
                                    check_type='task',
                                    check_name='stuck_tasks',
                                    severity='warning',
                                    message='%s scheduler has been running for %.0f minutes — may be stuck.' % (task_name, elapsed),
                                    metadata={'task': task_name, 'elapsed_min': round(elapsed)}
                                ))
                        except (ValueError, TypeError):
                            pass
                except Exception:
                    pass

        return results

    def check_disk_space(self):
        """Check free disk space on configured storage paths."""
        results = []

        # Cast thresholds from config — stored as str in config.ini
        warn_gb = float(mylar.CONFIG.HEALTH_DISK_WARN_GB or 5.0)
        error_gb = float(mylar.CONFIG.HEALTH_DISK_ERROR_GB or 1.0)

        paths_to_check = set()
        if mylar.CONFIG.DESTINATION_DIR and os.path.exists(mylar.CONFIG.DESTINATION_DIR):
            paths_to_check.add(mylar.CONFIG.DESTINATION_DIR)
        if mylar.CONFIG.CACHE_DIR and os.path.exists(mylar.CONFIG.CACHE_DIR):
            paths_to_check.add(mylar.CONFIG.CACHE_DIR)

        # Dedup by mount point — use (total, used) as a proxy for the same
        # filesystem since two paths on the same disk will report identical
        # total capacity.  This avoids duplicate alerts for /comics and /cache
        # when both live on the same volume.
        checked_mounts = set()

        for path in paths_to_check:
            try:
                usage = shutil.disk_usage(path)
                mount_key = usage.total  # same total == same filesystem
                if mount_key in checked_mounts:
                    continue
                checked_mounts.add(mount_key)

                free_gb = usage.free / (1024 ** 3)

                if free_gb < error_gb:
                    results.append(HealthCheckResult(
                        check_type='infrastructure',
                        check_name='disk_space',
                        severity='error',
                        message='Critically low disk space on %s — only %.1f GB free (threshold: %.1f GB). Downloads will fail.' % (path, free_gb, error_gb),
                        metadata={'path': path, 'free_gb': round(free_gb, 2), 'total_gb': round(usage.total / (1024 ** 3), 2)}
                    ))
                elif free_gb < warn_gb:
                    results.append(HealthCheckResult(
                        check_type='infrastructure',
                        check_name='disk_space',
                        severity='warning',
                        message='Low disk space on %s — %.1f GB free (warning threshold: %.1f GB).' % (path, free_gb, warn_gb),
                        metadata={'path': path, 'free_gb': round(free_gb, 2), 'total_gb': round(usage.total / (1024 ** 3), 2)}
                    ))
            except OSError as e:
                logger.debug('[HealthCheck] Could not check disk space for %s: %s' % (path, e))

        return results

    def check_indexers(self):
        """Check configured indexers for connectivity issues."""
        results = []

        # PROVIDER_STATUS is a dict of {provider_name: 'success'|'fail'}
        # populated by base.html from PROVIDER_ORDER and PROVIDER_BLOCKLIST
        provider_status = getattr(mylar, 'PROVIDER_STATUS', None)
        if not provider_status:
            return []  # not populated yet — skip until first page load

        for provider, status in provider_status.items():
            if status == 'fail':
                # check PROVIDER_BLOCKLIST for the reason this provider was blocked
                reason = 'unavailable'
                blocklist = getattr(mylar, 'PROVIDER_BLOCKLIST', [])
                for entry in blocklist:
                    if entry.get('site') == provider:
                        reason = entry.get('reason', 'unavailable')
                        break
                results.append(HealthCheckResult(
                    check_type='provider',
                    check_name='indexers',
                    severity='warning',
                    message='Indexer "%s" is currently unavailable — %s. Searches using this provider will fail.' % (provider, reason),
                    metadata={'provider': provider, 'reason': reason}
                ))

        return results

    def check_no_indexers(self):
        """Warn if no search indexers or providers are enabled."""
        results = []

        has_any = False

        # check newznab providers — EXTRA_NEWZNABS is a list of tuples
        # tuple format: (name, host, verify, apikey, uid/categories, enabled, id)
        # index 5 is the enabled flag ('0' or '1')
        try:
            newznabs = getattr(mylar.CONFIG, 'EXTRA_NEWZNABS', []) or []
            for nz in newznabs:
                if len(nz) > 5 and str(nz[5]) == '1':
                    has_any = True
                    break
        except Exception:
            pass

        # check torznab providers — same tuple format as newznabs
        if not has_any:
            try:
                torznabs = getattr(mylar.CONFIG, 'EXTRA_TORZNABS', []) or []
                for tz in torznabs:
                    if len(tz) > 5 and str(tz[5]) == '1':
                        has_any = True
                        break
            except Exception:
                pass

        # check other search toggles
        if not has_any:
            if getattr(mylar.CONFIG, 'ENABLE_TORRENT_SEARCH', False):
                has_any = True
            elif getattr(mylar.CONFIG, 'EXPERIMENTAL', False):
                has_any = True

        if not has_any:
            results.append(HealthCheckResult(
                check_type='config',
                check_name='no_indexers',
                severity='error',
                message='No search providers are enabled — Mylar cannot search for or download any comics. Configure at least one provider in Settings.',
            ))

        return results

    def check_download_client(self):
        """Test download client connectivity.

        NZB clients (SABnzbd, NZBGet): HTTP API version endpoint.
        Torrent clients (qBittorrent, Transmission, uTorrent): HTTP API probe.
        rTorrent: HTTP GET to SCGI pass-through URL (skipped for non-HTTP hosts).
        Deluge: TCP socket connect to daemon RPC port.
        """
        results = []

        if getattr(mylar, 'USE_SABNZBD', False):
            try:
                sab_host = mylar.CONFIG.SAB_HOST or ''
                sab_apikey = mylar.CONFIG.SAB_APIKEY or ''
                # SABnzbd API URL: host/api?mode=version&apikey=KEY&output=json
                if sab_host and not sab_host.endswith('/'):
                    sab_host = sab_host + '/'
                sab_url = '%sapi?mode=version&apikey=%s&output=json' % (sab_host, sab_apikey)
                verify = sab_host.startswith('https')
                resp = requests.get(sab_url, timeout=5, verify=verify)
                if resp.status_code != 200:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='SABnzbd returned HTTP %d — check host and API key.' % resp.status_code,
                        metadata={'client': 'sabnzbd', 'status_code': resp.status_code}
                    ))
            except requests.exceptions.ConnectionError:
                results.append(HealthCheckResult(
                    check_type='download',
                    check_name='download_client',
                    severity='error',
                    message='SABnzbd unreachable at %s — connection refused.' % mylar.CONFIG.SAB_HOST,
                    metadata={'client': 'sabnzbd', 'error': 'connection_refused'}
                ))
            except requests.exceptions.Timeout:
                results.append(HealthCheckResult(
                    check_type='download',
                    check_name='download_client',
                    severity='error',
                    message='SABnzbd connection timed out at %s.' % mylar.CONFIG.SAB_HOST,
                    metadata={'client': 'sabnzbd', 'error': 'timeout'}
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    check_type='download',
                    check_name='download_client',
                    severity='error',
                    message='SABnzbd check failed: %s' % str(e)[:200],
                    metadata={'client': 'sabnzbd', 'error': str(type(e).__name__)}
                ))

        if getattr(mylar, 'USE_NZBGET', False):
            try:
                nzbget_host = mylar.CONFIG.NZBGET_HOST or ''
                nzbget_port = mylar.CONFIG.NZBGET_PORT or ''
                # NZBGet uses XML-RPC; test with a simple HTTP GET to the base URL
                # Build URL: protocol://host:port[/subpath]/xmlrpc
                if nzbget_host.startswith('https'):
                    protocol = 'https'
                    host_part = nzbget_host[8:]
                elif nzbget_host.startswith('http'):
                    protocol = 'http'
                    host_part = nzbget_host[7:]
                else:
                    protocol = 'http'
                    host_part = nzbget_host

                nzbget_url = '%s://%s:%s/jsonrpc/version' % (protocol, host_part, nzbget_port)
                resp = requests.get(nzbget_url, timeout=5, verify=False)
                if resp.status_code != 200:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='NZBGet returned HTTP %d — check host and port.' % resp.status_code,
                        metadata={'client': 'nzbget', 'status_code': resp.status_code}
                    ))
            except requests.exceptions.ConnectionError:
                results.append(HealthCheckResult(
                    check_type='download',
                    check_name='download_client',
                    severity='error',
                    message='NZBGet unreachable at %s:%s — connection refused.' % (mylar.CONFIG.NZBGET_HOST, mylar.CONFIG.NZBGET_PORT),
                    metadata={'client': 'nzbget', 'error': 'connection_refused'}
                ))
            except requests.exceptions.Timeout:
                results.append(HealthCheckResult(
                    check_type='download',
                    check_name='download_client',
                    severity='error',
                    message='NZBGet connection timed out at %s:%s.' % (mylar.CONFIG.NZBGET_HOST, mylar.CONFIG.NZBGET_PORT),
                    metadata={'client': 'nzbget', 'error': 'timeout'}
                ))
            except Exception as e:
                results.append(HealthCheckResult(
                    check_type='download',
                    check_name='download_client',
                    severity='error',
                    message='NZBGet check failed: %s' % str(e)[:200],
                    metadata={'client': 'nzbget', 'error': str(type(e).__name__)}
                ))

        # ── Torrent client connectivity checks ──

        if getattr(mylar, 'USE_QBITTORRENT', False):
            qbt_host = getattr(mylar.CONFIG, 'QBITTORRENT_HOST', None) or ''
            if qbt_host:
                try:
                    # qBittorrent WebUI: /api/v2/app/version is unauthenticated
                    test_url = qbt_host.rstrip('/') + '/api/v2/app/version'
                    resp = requests.get(test_url, timeout=5, verify=False)
                    if resp.status_code == 403:
                        pass  # 403 = reachable, auth required — healthy
                    elif resp.status_code not in (200, 403):
                        results.append(HealthCheckResult(
                            check_type='download',
                            check_name='download_client',
                            severity='error',
                            message='qBittorrent returned HTTP %d — check host and port.' % resp.status_code,
                            metadata={'client': 'qbittorrent', 'status_code': resp.status_code}
                        ))
                except requests.exceptions.ConnectionError:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='qBittorrent unreachable at %s — connection refused.' % qbt_host,
                        metadata={'client': 'qbittorrent', 'error': 'connection_refused'}
                    ))
                except requests.exceptions.Timeout:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='qBittorrent connection timed out at %s.' % qbt_host,
                        metadata={'client': 'qbittorrent', 'error': 'timeout'}
                    ))
                except Exception as e:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='qBittorrent check failed: %s' % str(e)[:200],
                        metadata={'client': 'qbittorrent', 'error': str(type(e).__name__)}
                    ))

        if getattr(mylar, 'USE_TRANSMISSION', False):
            trans_host = getattr(mylar.CONFIG, 'TRANSMISSION_HOST', None) or ''
            if trans_host:
                try:
                    # Transmission RPC responds with 409 + X-Transmission-Session-Id
                    # header on first contact — that counts as reachable.
                    test_url = trans_host.rstrip('/') + '/transmission/rpc'
                    resp = requests.get(test_url, timeout=5, verify=False)
                    if resp.status_code not in (200, 401, 409):
                        results.append(HealthCheckResult(
                            check_type='download',
                            check_name='download_client',
                            severity='error',
                            message='Transmission returned HTTP %d — check host and port.' % resp.status_code,
                            metadata={'client': 'transmission', 'status_code': resp.status_code}
                        ))
                except requests.exceptions.ConnectionError:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='Transmission unreachable at %s — connection refused.' % trans_host,
                        metadata={'client': 'transmission', 'error': 'connection_refused'}
                    ))
                except requests.exceptions.Timeout:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='Transmission connection timed out at %s.' % trans_host,
                        metadata={'client': 'transmission', 'error': 'timeout'}
                    ))
                except Exception as e:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='Transmission check failed: %s' % str(e)[:200],
                        metadata={'client': 'transmission', 'error': str(type(e).__name__)}
                    ))

        if getattr(mylar, 'USE_RTORRENT', False):
            rt_host = getattr(mylar.CONFIG, 'RTORRENT_HOST', None) or ''
            if rt_host and rt_host.startswith('http'):
                try:
                    # rTorrent with HTTP(S) SCGI pass-through — a GET to the
                    # base URL should at least return *something* if reachable.
                    rpc_url = getattr(mylar.CONFIG, 'RTORRENT_RPC_URL', '') or ''
                    test_url = rt_host.rstrip('/') + '/' + rpc_url.lstrip('/')
                    rt_verify = getattr(mylar.CONFIG, 'RTORRENT_VERIFY', False)
                    resp = requests.get(test_url.rstrip('/'), timeout=5, verify=rt_verify)
                    # Any HTTP response means the server is reachable; only
                    # connection-level failures indicate a problem.
                except requests.exceptions.ConnectionError:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='rTorrent unreachable at %s — connection refused.' % rt_host,
                        metadata={'client': 'rtorrent', 'error': 'connection_refused'}
                    ))
                except requests.exceptions.Timeout:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='rTorrent connection timed out at %s.' % rt_host,
                        metadata={'client': 'rtorrent', 'error': 'timeout'}
                    ))
                except Exception as e:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='rTorrent check failed: %s' % str(e)[:200],
                        metadata={'client': 'rtorrent', 'error': str(type(e).__name__)}
                    ))

        if getattr(mylar, 'USE_DELUGE', False):
            deluge_host = getattr(mylar.CONFIG, 'DELUGE_HOST', None) or ''
            if deluge_host:
                try:
                    # Deluge uses daemon RPC (TCP, not HTTP).  A basic socket
                    # connect confirms the daemon port is accepting connections.
                    if ':' in deluge_host:
                        host_part, port_part = deluge_host.rsplit(':', 1)
                        port_num = int(port_part)
                    else:
                        host_part = deluge_host
                        port_num = 58846  # Deluge daemon default
                    sock = socket.create_connection((host_part, port_num), timeout=5)
                    sock.close()
                except (socket.timeout, socket.error, OSError) as e:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='Deluge daemon unreachable at %s — %s.' % (deluge_host, str(e)[:150]),
                        metadata={'client': 'deluge', 'error': 'connection_failed'}
                    ))
                except Exception as e:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='Deluge check failed: %s' % str(e)[:200],
                        metadata={'client': 'deluge', 'error': str(type(e).__name__)}
                    ))

        if getattr(mylar, 'USE_UTORRENT', False):
            ut_host = getattr(mylar.CONFIG, 'UTORRENT_HOST', None) or ''
            if ut_host:
                try:
                    # uTorrent WebUI — /gui/token.html returns auth token page
                    test_url = ut_host.rstrip('/') + '/gui/token.html'
                    resp = requests.get(test_url, timeout=5, verify=False)
                    if resp.status_code not in (200, 401):
                        results.append(HealthCheckResult(
                            check_type='download',
                            check_name='download_client',
                            severity='error',
                            message='uTorrent returned HTTP %d — check host and port.' % resp.status_code,
                            metadata={'client': 'utorrent', 'status_code': resp.status_code}
                        ))
                except requests.exceptions.ConnectionError:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='uTorrent unreachable at %s — connection refused.' % ut_host,
                        metadata={'client': 'utorrent', 'error': 'connection_refused'}
                    ))
                except requests.exceptions.Timeout:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='uTorrent connection timed out at %s.' % ut_host,
                        metadata={'client': 'utorrent', 'error': 'timeout'}
                    ))
                except Exception as e:
                    results.append(HealthCheckResult(
                        check_type='download',
                        check_name='download_client',
                        severity='error',
                        message='uTorrent check failed: %s' % str(e)[:200],
                        metadata={'client': 'utorrent', 'error': str(type(e).__name__)}
                    ))

        return results

    def check_download_category(self):
        """Verify the configured download category exists in the client."""
        # Deferred — requires querying SABnzbd/NZBGet categories API which
        # involves client-specific XML-RPC or REST calls and authentication.
        # Category validation will be added once download client wrappers
        # expose a list_categories() interface.
        return []

    def check_stalled_downloads(self):
        """Check for downloads that appear stuck in the client queue."""
        # Deferred — requires querying each download client's active queue
        # and comparing item ages against a threshold.  Each client (SABnzbd,
        # NZBGet, qBittorrent, etc.) has a different API for queue inspection.
        return []

    def check_failed_postprocessing(self):
        """Check for repeated post-processing failures in the last 24 hours."""
        results = []
        try:
            myconn = db.DBConnection()
            cutoff = (datetime.datetime.utcnow() - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            recent_failures = myconn.select(
                "SELECT COUNT(*) as cnt FROM Failed WHERE DateFailed >= ?",
                [cutoff]
            )
            if recent_failures and recent_failures[0]['cnt'] > 5:
                count = recent_failures[0]['cnt']
                results.append(HealthCheckResult(
                    check_type='task',
                    check_name='failed_postprocessing',
                    severity='warning',
                    message='%d post-processing failures in the last 24 hours. Check the Failed Downloads list for details.' % count,
                    metadata={'count': count, 'period': '24h'}
                ))
        except Exception as e:
            logger.debug('[HealthCheck] Could not query Failed table: %s' % str(e)[:200])
        return results

    def check_update_available(self):
        """Check if a newer version of Mylar3 is available."""
        results = []
        commits_behind = getattr(mylar, 'COMMITS_BEHIND', None)
        if commits_behind and int(commits_behind) > 0:
            branch = getattr(mylar.CONFIG, 'GIT_BRANCH', 'master') or 'master'
            results.append(HealthCheckResult(
                check_type='config',
                check_name='update_available',
                severity='notice',
                message='A newer version of Mylar3 is available — you are %d commit%s behind %s.' % (
                    int(commits_behind), 's' if int(commits_behind) != 1 else '', branch),
                metadata={'commits_behind': int(commits_behind), 'branch': branch}
            ))
        return results

    def check_permissions(self):
        """Verify write access to key Mylar directories."""
        results = []
        dirs_to_check = {
            'Data directory': getattr(mylar, 'DATA_DIR', None),
            'Log directory': getattr(mylar, 'LOG_DIR', None),
            'Cache directory': getattr(mylar.CONFIG, 'CACHE_DIR', None),
        }
        for label, path in dirs_to_check.items():
            if path and os.path.exists(path) and not os.access(path, os.W_OK):
                results.append(HealthCheckResult(
                    check_type='infrastructure',
                    check_name='permissions',
                    severity='error',
                    message='%s is not writable: %s — check file permissions.' % (label, path),
                    metadata={'path': path, 'label': label}
                ))
        return results

    def check_no_download_client(self):
        """Warn if no download client is configured."""
        results = []

        # NZB side — NZB_DOWNLOADER: 0=SABnzbd, 1=NZBGet, 2=Blackhole, 3=None
        has_nzb_client = any([
            getattr(mylar, 'USE_SABNZBD', False),
            getattr(mylar, 'USE_NZBGET', False),
            getattr(mylar, 'USE_BLACKHOLE', False),
        ])

        # Torrent side — only counts if torrents are enabled.  TORRENT_DOWNLOADER
        # defaults to 0 (watchfolder) which sets USE_WATCHDIR=True even when no
        # torrent client is intentionally configured.  Gating on ENABLE_TORRENTS
        # prevents that default from masking a missing download client.
        torrents_enabled = getattr(mylar.CONFIG, 'ENABLE_TORRENTS', False)
        has_torrent_client = torrents_enabled and any([
            getattr(mylar, 'USE_RTORRENT', False),
            getattr(mylar, 'USE_DELUGE', False),
            getattr(mylar, 'USE_TRANSMISSION', False),
            getattr(mylar, 'USE_QBITTORRENT', False),
            getattr(mylar, 'USE_UTORRENT', False),
            getattr(mylar, 'USE_WATCHDIR', False),
        ])

        has_client = has_nzb_client or has_torrent_client

        if not has_client:
            results.append(HealthCheckResult(
                check_type='download',
                check_name='no_download_client',
                severity='warning',
                message='No download client is configured. Mylar can find comics but cannot download them.',
            ))
        return results

    def check_api_key_missing(self):
        """Warn if ComicVine API key is not configured."""
        results = []
        api_key = getattr(mylar.CONFIG, 'COMICVINE_API', None)
        if not api_key or api_key in ('None', '') or not str(api_key).strip():
            results.append(HealthCheckResult(
                check_type='config',
                check_name='api_key_missing',
                severity='error',
                message='ComicVine API key is not set — Mylar cannot look up comic metadata. Add your API key in Settings > Web Interface.',
            ))
        return results

    def check_database_integrity(self):
        """Run SQLite PRAGMA integrity_check (runs every 6 hours)."""
        results = []
        try:
            myconn = db.DBConnection()
            integrity = myconn.select("PRAGMA integrity_check")
            if integrity and integrity[0]:
                # PRAGMA integrity_check returns [{'integrity_check': 'ok'}] when healthy
                status = str(integrity[0][0]) if integrity[0] else 'unknown'
                if status.lower() != 'ok':
                    results.append(HealthCheckResult(
                        check_type='infrastructure',
                        check_name='database_integrity',
                        severity='error',
                        message='Database integrity check failed: %s. Consider restoring from backup.' % status[:200],
                        metadata={'result': status[:500]}
                    ))
        except Exception as e:
            results.append(HealthCheckResult(
                check_type='infrastructure',
                check_name='database_integrity',
                severity='error',
                message='Database integrity check could not run: %s' % str(e)[:200],
                metadata={'error': str(type(e).__name__)}
            ))
        return results

    # ── Private Helpers ──

    def _should_run(self, check_name):
        # per-check interval gating — returns True if enough time has passed
        interval = self.CHECK_INTERVALS.get(check_name, 5)
        last = self._check_timestamps.get(check_name)
        if last is None:
            return True
        elapsed_min = (datetime.datetime.utcnow() - last).total_seconds() / 60
        return elapsed_min >= interval

    def _save_to_db(self, results):
        # persist current results to SQLite — upserts active, skips unchanged
        myconn = db.DBConnection()
        now = datetime.datetime.utcnow().isoformat()
        for result in results:
            try:
                # check if this check_name already has an active row
                existing = myconn.select(
                    "SELECT id, check_count, first_seen FROM health_checks WHERE check_name=? AND is_resolved=0",
                    [result.check_name]
                )
                if existing:
                    row = existing[0]
                    myconn.action(
                        "UPDATE health_checks SET last_seen=?, check_count=?, message=?, severity=?, metadata=? WHERE id=?",
                        [now, row['check_count'] + 1, result.message, result.severity,
                         json.dumps(result.metadata), row['id']]
                    )
                    result.db_id = row['id']
                    result.check_count = row['check_count'] + 1
                    result.first_seen = row['first_seen']  # preserve original first_seen from DB
                    result.last_seen = now  # sync in-memory last_seen with what we wrote to DB
                else:
                    myconn.action(
                        "INSERT INTO health_checks (check_type, check_name, severity, message, wiki_url, source, first_seen, last_seen, is_resolved, check_count, metadata) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1, ?)",
                        [result.check_type, result.check_name, result.severity, result.message,
                         result.wiki_url, result.source, now, now, json.dumps(result.metadata)]
                    )
                    # get the ID of the newly inserted row
                    new_row = myconn.select(
                        "SELECT id FROM health_checks WHERE check_name=? AND is_resolved=0 ORDER BY id DESC LIMIT 1",
                        [result.check_name]
                    )
                    if new_row:
                        result.db_id = new_row[0]['id']
            except Exception as e:
                logger.error('[HealthCheck] DB save failed for %s: %s' % (result.check_name, str(e)[:200]))

    def _save_single_to_db(self, result):
        # persist one result (used by log handler for immediate findings)
        self._save_to_db([result])

    def _resolve_cleared(self, current_results, checks_that_ran):
        # Only resolve DB records for checks that ACTUALLY RAN this cycle
        # and returned clean (no results).  If a check was skipped by
        # _should_run(), its DB records must be left untouched.
        active_names = {r.check_name for r in current_results}
        myconn = db.DBConnection()
        now = datetime.datetime.utcnow().isoformat()

        try:
            active_rows = myconn.select(
                "SELECT id, check_name FROM health_checks WHERE is_resolved=0"
            )
            for row in active_rows:
                # only resolve if: (a) the check ran this cycle, AND (b) it returned no findings
                if row['check_name'] in checks_that_ran and row['check_name'] not in active_names:
                    myconn.action(
                        "UPDATE health_checks SET is_resolved=1, resolved_at=? WHERE id=?",
                        [now, row['id']]
                    )
                    logger.info('[HealthCheck] Resolved: %s' % row['check_name'])
        except Exception as e:
            logger.error('[HealthCheck] Failed to resolve cleared checks: %s' % str(e)[:200])

    def _cleanup_old(self):
        # purge resolved records older than HEALTH_HISTORY_DAYS
        days = int(mylar.CONFIG.HEALTH_HISTORY_DAYS or 30)
        cutoff = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
        try:
            myconn = db.DBConnection()
            myconn.action(
                "DELETE FROM health_checks WHERE is_resolved=1 AND resolved_at<?",
                [cutoff]
            )
        except Exception as e:
            logger.error('[HealthCheck] Failed to cleanup old records: %s' % str(e)[:200])

    def _push_sse(self, results):
        # push health_update event to all connected browsers via GLOBAL_MESSAGES
        try:
            summary = self.get_summary()
            errors = [r.to_dict() for r in results if r.severity == 'error']
            warnings = [r.to_dict() for r in results if r.severity == 'warning']

            mylar.GLOBAL_MESSAGES = {
                'status': 'success',
                'event': 'health_update',
                'data': json.dumps({
                    'errors': errors,
                    'warnings': warnings,
                    'error_count': summary.get('errors', 0),
                    'warning_count': summary.get('warnings', 0),
                    'notice_count': summary.get('notices', 0),
                })
            }
        except Exception as e:
            logger.debug('[HealthCheck] SSE push failed: %s' % e)


# ── Log Interceptor (stub for Phase 3) ──

class HealthLogHandler(logging.Handler):
    """Watches log messages for error patterns between scheduled health checks."""
    pass
