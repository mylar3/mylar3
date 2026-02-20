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

import requests

import mylar
from mylar import logger, db, helpers


# ── Health Check System ──
# Provides periodic health monitoring for Mylar3 components.
# Checks infrastructure (folders, disk, DB), providers (ComicVine, indexers),
# download clients (SABnzbd, NZBGet), and scheduler tasks.
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

    def run_all_checks(self):
        """Run all health checks and update DB, memory, and browser."""
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
            if not self._should_run(check_name):
                continue
            checks_that_ran.add(check_name)
            try:
                check_results = check_method()
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
        summary_msg = '[HealthCheck] Completed in %.2fs — %d errors, %d warnings, %d notices' % (
            elapsed, error_count, warning_count, notice_count)

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

    # ── Stubbed Checks (Phase 3) ──

    def check_disk_space(self):
        """[Phase 3] Check free disk space on storage paths."""
        return []

    def check_indexers(self):
        """[Phase 3] Test connectivity to each configured indexer."""
        return []

    def check_no_indexers(self):
        """[Phase 3] Warn if no search indexers/providers are enabled."""
        return []

    def check_download_client(self):
        """[Phase 3] Test download client connectivity."""
        return []

    def check_download_category(self):
        """[Phase 3] Verify the configured download category exists in the client."""
        return []

    def check_stalled_downloads(self):
        """[Phase 3] Check for downloads that appear stuck."""
        return []

    def check_failed_postprocessing(self):
        """[Phase 3] Check for repeated post-processing failures."""
        return []

    def check_update_available(self):
        """[Phase 3] Check if a newer version of Mylar3 is available."""
        return []

    def check_permissions(self):
        """[Phase 3] Verify write access to key directories."""
        return []

    def check_no_download_client(self):
        """[Phase 3] Warn if no download client is configured."""
        return []

    def check_api_key_missing(self):
        """[Phase 3] Warn if ComicVine API key is not set."""
        return []

    def check_database_integrity(self):
        """[Phase 3] Run SQLite integrity check."""
        return []

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
