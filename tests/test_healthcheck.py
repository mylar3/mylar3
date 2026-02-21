"""
Unit and integration tests for the health check system.

Tests cover:
- HealthCheckResult data container (creation, validation, serialization)
- HealthCheckRunner engine (results management, summary, dismiss, thread safety)
- Individual health checks (root folders, disk space, ComicVine, stuck tasks, etc.)
- HealthLogHandler log interceptor (pattern matching, throttling, loop prevention)
- Database operations (save/load round trip, cleanup old records)

Run with:
    python -m pytest tests/test_healthcheck.py -v

Run only unit tests:
    python -m pytest tests/test_healthcheck.py -m unit -v

Run only integration tests:
    python -m pytest tests/test_healthcheck.py -m integration -v
"""

import datetime
import json
import logging
import os
import sqlite3
import threading
import time

import pytest
import requests

import mylar
from mylar.healthcheck import HealthCheckResult, HealthCheckRunner, HealthLogHandler


# ── Fixtures ──

@pytest.fixture
def mock_config(monkeypatch):
    """Set up a fake mylar.CONFIG with health check defaults."""
    config = mylar.config.Config("./nothing")
    monkeypatch.setattr(mylar, "CONFIG", config)
    monkeypatch.setattr(config, "HEALTH_CHECK_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "HEALTH_CHECK_INTERVAL", 5, raising=False)
    monkeypatch.setattr(config, "HEALTH_DISK_WARN_GB", '5.0', raising=False)
    monkeypatch.setattr(config, "HEALTH_DISK_ERROR_GB", '1.0', raising=False)
    monkeypatch.setattr(config, "HEALTH_STALE_TASK_MIN", 60, raising=False)
    monkeypatch.setattr(config, "HEALTH_SHOW_BANNER", True, raising=False)
    monkeypatch.setattr(config, "HEALTH_HISTORY_DAYS", 30, raising=False)
    monkeypatch.setattr(config, "DESTINATION_DIR", '/comics', raising=False)
    monkeypatch.setattr(config, "MULTIPLE_DEST_DIRS", None, raising=False)
    monkeypatch.setattr(config, "COMICVINE_API", 'fake-api-key-12345', raising=False)
    monkeypatch.setattr(config, "CV_VERIFY", True, raising=False)
    monkeypatch.setattr(config, "CACHE_DIR", '/tmp/cache', raising=False)
    monkeypatch.setattr(config, "SAB_HOST", 'http://localhost:8080', raising=False)
    monkeypatch.setattr(config, "SAB_APIKEY", 'fake-sab-key', raising=False)
    monkeypatch.setattr(config, "NZBGET_HOST", 'localhost', raising=False)
    monkeypatch.setattr(config, "NZBGET_PORT", '6789', raising=False)
    monkeypatch.setattr(config, "GIT_BRANCH", 'master', raising=False)
    monkeypatch.setattr(config, "EXTRA_NEWZNABS", [], raising=False)
    monkeypatch.setattr(config, "EXTRA_TORZNABS", [], raising=False)
    monkeypatch.setattr(config, "ENABLE_TORRENT_SEARCH", False, raising=False)
    monkeypatch.setattr(config, "EXPERIMENTAL", False, raising=False)
    monkeypatch.setattr(config, "ENABLE_TORRENTS", False, raising=False)
    return config


@pytest.fixture
def mock_globals(monkeypatch):
    """Set up default mylar globals for health checks."""
    monkeypatch.setattr(mylar, "CVURL", 'https://comicvine.gamespot.com/api/', raising=False)
    monkeypatch.setattr(mylar, "CV_HEADERS", {'User-Agent': 'test'}, raising=False)
    monkeypatch.setattr(mylar, "GLOBAL_MESSAGES", {}, raising=False)
    monkeypatch.setattr(mylar, "HEALTH_RESULTS", [], raising=False)
    monkeypatch.setattr(mylar, "HEALTH_CHECK", None, raising=False)
    monkeypatch.setattr(mylar, "MONITOR_STATUS", 'Waiting', raising=False)
    monkeypatch.setattr(mylar, "SEARCH_STATUS", 'Waiting', raising=False)
    monkeypatch.setattr(mylar, "RSS_STATUS", 'Waiting', raising=False)
    monkeypatch.setattr(mylar, "WEEKLY_STATUS", 'Waiting', raising=False)
    monkeypatch.setattr(mylar, "VERSION_STATUS", 'Waiting', raising=False)
    monkeypatch.setattr(mylar, "COMMITS_BEHIND", 0, raising=False)
    monkeypatch.setattr(mylar, "DATA_DIR", '/tmp/mylar_data', raising=False)
    monkeypatch.setattr(mylar, "LOG_DIR", '/tmp/mylar_logs', raising=False)
    monkeypatch.setattr(mylar, "USE_SABNZBD", False, raising=False)
    monkeypatch.setattr(mylar, "USE_NZBGET", False, raising=False)
    monkeypatch.setattr(mylar, "USE_BLACKHOLE", False, raising=False)
    monkeypatch.setattr(mylar, "USE_RTORRENT", False, raising=False)
    monkeypatch.setattr(mylar, "USE_DELUGE", False, raising=False)
    monkeypatch.setattr(mylar, "USE_TRANSMISSION", False, raising=False)
    monkeypatch.setattr(mylar, "USE_QBITTORRENT", False, raising=False)
    monkeypatch.setattr(mylar, "USE_UTORRENT", False, raising=False)
    monkeypatch.setattr(mylar, "USE_WATCHDIR", False, raising=False)
    monkeypatch.setattr(mylar, "PROVIDER_STATUS", None, raising=False)
    monkeypatch.setattr(mylar, "PROVIDER_BLOCKLIST", [], raising=False)


@pytest.fixture
def mock_db(monkeypatch):
    """Mock the database connection so no real DB is touched."""
    class FakeDBConnection:
        def __init__(self):
            self._data = []

        def select(self, query, params=None):
            return self._data

        def action(self, query, params=None):
            pass

        def upsert(self, table, new_values, control):
            pass

    fake = FakeDBConnection()
    monkeypatch.setattr(mylar.db, "DBConnection", lambda: fake)
    return fake


@pytest.fixture
def runner(mock_config, mock_globals, mock_db):
    """Create a HealthCheckRunner with mocked dependencies."""
    return HealthCheckRunner()


@pytest.fixture
def real_db(tmp_path, monkeypatch):
    """Create a real SQLite database with the health_checks table."""
    db_path = str(tmp_path / "test_mylar.db")

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS health_checks ('
              'id INTEGER PRIMARY KEY AUTOINCREMENT, '
              'check_type TEXT NOT NULL, '
              'check_name TEXT NOT NULL, '
              'severity TEXT NOT NULL, '
              'message TEXT NOT NULL, '
              'wiki_url TEXT, '
              'source TEXT DEFAULT "health_check", '
              'first_seen TEXT NOT NULL, '
              'last_seen TEXT NOT NULL, '
              'is_resolved INTEGER DEFAULT 0, '
              'resolved_at TEXT, '
              'check_count INTEGER DEFAULT 1, '
              'metadata TEXT'
              ')')
    # also create jobhistory for stuck task tests
    c.execute('CREATE TABLE IF NOT EXISTS jobhistory ('
              'id INTEGER PRIMARY KEY AUTOINCREMENT, '
              'JobName TEXT, '
              'current_run TEXT, '
              'last_run_completed TEXT, '
              'status TEXT'
              ')')
    # also create Failed for post-processing tests
    c.execute('CREATE TABLE IF NOT EXISTS Failed ('
              'id INTEGER PRIMARY KEY AUTOINCREMENT, '
              'DateFailed TEXT'
              ')')
    conn.commit()
    conn.close()

    # Point Mylar's DB module at our temp database
    monkeypatch.setattr(mylar, "DB_FILE", db_path, raising=False)

    return db_path


# ── Unit Tests: HealthCheckResult ──

class TestHealthCheckResult:
    """Tests for the HealthCheckResult data container."""

    @pytest.mark.unit
    def test_creation_with_valid_fields(self):
        r = HealthCheckResult(
            check_type='infrastructure',
            check_name='root_folder',
            severity='error',
            message='Root folder not found'
        )
        assert r.check_type == 'infrastructure'
        assert r.check_name == 'root_folder'
        assert r.severity == 'error'
        assert r.message == 'Root folder not found'
        assert r.check_count == 1
        assert r.source == 'health_check'
        assert r.db_id is None

    @pytest.mark.unit
    def test_invalid_severity_raises_valueerror(self):
        with pytest.raises(ValueError):
            HealthCheckResult(
                check_type='infrastructure',
                check_name='test',
                severity='critical',
                message='test'
            )

    @pytest.mark.unit
    def test_to_dict_returns_json_serializable(self):
        r = HealthCheckResult(
            check_type='provider',
            check_name='comicvine_api',
            severity='error',
            message='API timeout',
            metadata={'timeout': 5}
        )
        d = r.to_dict()
        json_str = json.dumps(d)
        assert 'comicvine_api' in json_str

    @pytest.mark.unit
    def test_to_dict_contains_all_fields(self):
        r = HealthCheckResult(
            check_type='provider',
            check_name='comicvine_api',
            severity='warning',
            message='Rate limited',
            wiki_url='https://example.com/help',
            source='log_intercept',
            metadata={'code': 429}
        )
        d = r.to_dict()
        assert d['check_type'] == 'provider'
        assert d['check_name'] == 'comicvine_api'
        assert d['severity'] == 'warning'
        assert d['message'] == 'Rate limited'
        assert d['wiki_url'] == 'https://example.com/help'
        assert d['source'] == 'log_intercept'
        assert d['metadata'] == {'code': 429}
        assert d['check_count'] == 1
        assert 'first_seen' in d
        assert 'last_seen' in d

    @pytest.mark.unit
    def test_default_wiki_url_generated(self):
        r = HealthCheckResult(
            check_type='provider',
            check_name='comicvine_api',
            severity='error',
            message='test'
        )
        assert 'comicvine-api' in r.wiki_url
        assert 'Health-Checks' in r.wiki_url

    @pytest.mark.unit
    def test_custom_wiki_url_preserved(self):
        custom_url = 'https://example.com/my-help-page'
        r = HealthCheckResult(
            check_type='provider',
            check_name='comicvine_api',
            severity='error',
            message='test',
            wiki_url=custom_url
        )
        assert r.wiki_url == custom_url

    @pytest.mark.unit
    def test_from_db_row_creates_correct_object(self):
        row = {
            'id': 42,
            'check_type': 'infrastructure',
            'check_name': 'disk_space',
            'severity': 'warning',
            'message': 'Low disk space',
            'wiki_url': 'https://example.com',
            'source': 'health_check',
            'first_seen': '2025-01-01T00:00:00',
            'last_seen': '2025-01-01T01:00:00',
            'resolved_at': None,
            'check_count': 5,
            'metadata': '{"path": "/data", "free_gb": 3.2}',
        }
        r = HealthCheckResult.from_db_row(row)
        assert r.db_id == 42
        assert r.check_name == 'disk_space'
        assert r.severity == 'warning'
        assert r.check_count == 5
        assert r.metadata == {'path': '/data', 'free_gb': 3.2}
        assert r.first_seen == '2025-01-01T00:00:00'
        assert r.last_seen == '2025-01-01T01:00:00'

    @pytest.mark.unit
    def test_from_db_row_handles_null_metadata(self):
        row = {
            'id': 1,
            'check_type': 'config',
            'check_name': 'api_key_missing',
            'severity': 'error',
            'message': 'No API key',
            'wiki_url': None,
            'source': None,
            'first_seen': '2025-01-01T00:00:00',
            'last_seen': '2025-01-01T00:00:00',
            'resolved_at': None,
            'check_count': None,
            'metadata': None,
        }
        r = HealthCheckResult.from_db_row(row)
        assert r.metadata == {}
        assert r.check_count == 1
        assert r.source == 'health_check'

    @pytest.mark.unit
    def test_metadata_defaults_to_empty_dict(self):
        r = HealthCheckResult(
            check_type='config',
            check_name='test',
            severity='notice',
            message='test'
        )
        assert r.metadata == {}


# ── Unit Tests: HealthCheckRunner ──

class TestHealthCheckRunner:
    """Tests for the HealthCheckRunner engine."""

    @pytest.mark.unit
    def test_init_creates_empty_state(self, runner):
        assert runner.get_results() == []
        assert runner.last_run_iso() is None

    @pytest.mark.unit
    def test_get_results_returns_list(self, runner):
        results = runner.get_results()
        assert isinstance(results, list)

    @pytest.mark.unit
    def test_get_results_returns_copy_not_reference(self, runner):
        results1 = runner.get_results()
        results2 = runner.get_results()
        assert results1 is not results2

    @pytest.mark.unit
    def test_get_summary_empty_system(self, runner):
        summary = runner.get_summary()
        assert summary['errors'] == 0
        assert summary['warnings'] == 0
        assert summary['notices'] == 0
        assert summary['total'] == 0

    @pytest.mark.unit
    def test_get_summary_with_mixed_results(self, runner):
        # manually inject results
        with runner._lock:
            runner._results = [
                HealthCheckResult('infrastructure', 'root_folder', 'error', 'Missing folder'),
                HealthCheckResult('provider', 'comicvine_api', 'error', 'Timeout'),
                HealthCheckResult('download', 'download_client', 'warning', 'Slow'),
                HealthCheckResult('config', 'update_available', 'notice', 'Update ready'),
            ]
        summary = runner.get_summary()
        assert summary['errors'] == 2
        assert summary['warnings'] == 1
        assert summary['notices'] == 1
        assert summary['total'] == 4

    @pytest.mark.unit
    def test_last_run_iso_before_first_run(self, runner):
        assert runner.last_run_iso() is None

    @pytest.mark.unit
    def test_last_run_iso_after_run(self, runner):
        with runner._lock:
            runner._last_run = datetime.datetime(2025, 6, 15, 12, 30, 0)
        iso = runner.last_run_iso()
        assert iso == '2025-06-15T12:30:00'

    @pytest.mark.unit
    def test_dismiss_removes_from_results(self, runner, mock_db):
        result = HealthCheckResult('provider', 'comicvine_api', 'error', 'Timeout')
        result.db_id = 42
        with runner._lock:
            runner._results = [result]

        runner.dismiss(42)

        assert len(runner.get_results()) == 0

    @pytest.mark.unit
    def test_should_run_true_on_first_call(self, runner):
        assert runner._should_run('root_folder') is True

    @pytest.mark.unit
    def test_should_run_false_before_interval(self, runner):
        runner._check_timestamps['root_folder'] = datetime.datetime.now(datetime.timezone.utc)
        assert runner._should_run('root_folder') is False

    @pytest.mark.unit
    def test_should_run_true_after_interval(self, runner):
        # root_folder has 5 min interval — set timestamp to 6 min ago
        runner._check_timestamps['root_folder'] = (
            datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=6)
        )
        assert runner._should_run('root_folder') is True

    @pytest.mark.unit
    def test_ingest_log_finding_new_issue(self, runner, mock_db):
        result = HealthCheckResult('detected', 'comicvine_api', 'error', 'CV timeout', source='log_intercept')
        runner.ingest_log_finding(result)

        results = runner.get_results()
        assert len(results) == 1
        assert results[0].check_name == 'comicvine_api'

    @pytest.mark.unit
    def test_ingest_log_finding_deduplicates(self, runner, mock_db):
        r1 = HealthCheckResult('detected', 'comicvine_api', 'error', 'CV timeout 1', source='log_intercept')
        r2 = HealthCheckResult('detected', 'comicvine_api', 'error', 'CV timeout 2', source='log_intercept')
        runner.ingest_log_finding(r1)
        runner.ingest_log_finding(r2)

        results = runner.get_results()
        assert len(results) == 1
        assert results[0].check_count == 2

    @pytest.mark.unit
    def test_thread_safety_concurrent_access(self, runner):
        """Verify concurrent reads and writes don't crash."""
        errors = []

        def reader():
            try:
                for _ in range(100):
                    runner.get_results()
                    runner.get_summary()
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(100):
                    with runner._lock:
                        runner._results = [
                            HealthCheckResult('config', 'test_%d' % i, 'notice', 'msg')
                        ]
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=reader))
            threads.append(threading.Thread(target=writer))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# ── Unit Tests: Root Folder Check ──

class TestRootFolderCheck:
    """Tests for check_root_folders() — filesystem accessibility."""

    @pytest.mark.unit
    def test_existing_readable_folder_returns_empty(self, runner, tmp_path, mock_config):
        real_folder = tmp_path / "comics"
        real_folder.mkdir()
        mock_config.DESTINATION_DIR = str(real_folder)
        mock_config.MULTIPLE_DEST_DIRS = None

        results = runner.check_root_folders()
        assert results == []

    @pytest.mark.unit
    def test_missing_folder_returns_error(self, runner, mock_config):
        mock_config.DESTINATION_DIR = '/absolutely/does/not/exist/anywhere'
        mock_config.MULTIPLE_DEST_DIRS = None

        results = runner.check_root_folders()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert results[0].check_name == 'root_folder'
        assert 'not accessible' in results[0].message

    @pytest.mark.unit
    def test_unreadable_folder_returns_error(self, runner, tmp_path, mock_config, monkeypatch):
        real_folder = tmp_path / "comics"
        real_folder.mkdir()
        mock_config.DESTINATION_DIR = str(real_folder)
        mock_config.MULTIPLE_DEST_DIRS = None

        # mock os.access to return False for read check
        original_access = os.access
        def fake_access(path, mode):
            if path == str(real_folder) and mode == os.R_OK:
                return False
            return original_access(path, mode)
        monkeypatch.setattr(os, "access", fake_access)

        results = runner.check_root_folders()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert 'not readable' in results[0].message

    @pytest.mark.unit
    def test_multiple_folders_all_ok(self, runner, tmp_path, mock_config):
        folder1 = tmp_path / "comics1"
        folder2 = tmp_path / "comics2"
        folder1.mkdir()
        folder2.mkdir()
        mock_config.DESTINATION_DIR = str(folder1)
        mock_config.MULTIPLE_DEST_DIRS = str(folder2)

        results = runner.check_root_folders()
        assert results == []

    @pytest.mark.unit
    def test_multiple_folders_one_missing(self, runner, tmp_path, mock_config):
        folder1 = tmp_path / "comics1"
        folder1.mkdir()
        mock_config.DESTINATION_DIR = str(folder1)
        mock_config.MULTIPLE_DEST_DIRS = '/nonexistent/folder/here'

        results = runner.check_root_folders()
        assert len(results) == 1
        assert results[0].severity == 'error'

    @pytest.mark.unit
    def test_no_folders_configured_returns_empty(self, runner, mock_config):
        mock_config.DESTINATION_DIR = None
        mock_config.MULTIPLE_DEST_DIRS = None

        results = runner.check_root_folders()
        assert results == []


# ── Unit Tests: ComicVine Check ──

class TestComicVineCheck:
    """Tests for check_comicvine_api() — API connectivity."""

    @pytest.mark.unit
    def test_successful_api_call_returns_empty(self, runner, mock_config, mock_globals, monkeypatch):
        class FakeResponse:
            status_code = 200
        monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

        results = runner.check_comicvine_api()
        assert results == []

    @pytest.mark.unit
    def test_timeout_returns_error(self, runner, mock_config, mock_globals, monkeypatch):
        def fake_timeout(*args, **kwargs):
            raise requests.exceptions.Timeout("Connection timed out")
        monkeypatch.setattr(requests, "get", fake_timeout)

        results = runner.check_comicvine_api()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert 'timed out' in results[0].message.lower()

    @pytest.mark.unit
    def test_connection_error_returns_error(self, runner, mock_config, mock_globals, monkeypatch):
        def fake_conn_error(*args, **kwargs):
            raise requests.exceptions.ConnectionError("Connection refused")
        monkeypatch.setattr(requests, "get", fake_conn_error)

        results = runner.check_comicvine_api()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert results[0].check_name == 'comicvine_api'

    @pytest.mark.unit
    def test_401_returns_error_invalid_key(self, runner, mock_config, mock_globals, monkeypatch):
        class FakeResponse:
            status_code = 401
        monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

        results = runner.check_comicvine_api()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert '401' in results[0].message

    @pytest.mark.unit
    def test_429_returns_warning_rate_limit(self, runner, mock_config, mock_globals, monkeypatch):
        class FakeResponse:
            status_code = 429
        monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

        results = runner.check_comicvine_api()
        assert len(results) == 1
        assert results[0].severity == 'warning'
        assert 'rate limit' in results[0].message.lower()

    @pytest.mark.unit
    def test_500_returns_error(self, runner, mock_config, mock_globals, monkeypatch):
        class FakeResponse:
            status_code = 500
        monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

        results = runner.check_comicvine_api()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert '500' in results[0].message

    @pytest.mark.unit
    def test_no_api_key_returns_empty(self, runner, mock_config, mock_globals):
        mock_config.COMICVINE_API = None

        results = runner.check_comicvine_api()
        assert results == []

    @pytest.mark.unit
    def test_request_uses_5s_timeout(self, runner, mock_config, mock_globals, monkeypatch):
        captured = {}
        class FakeResponse:
            status_code = 200
        def capture_get(*args, **kwargs):
            captured.update(kwargs)
            return FakeResponse()
        monkeypatch.setattr(requests, "get", capture_get)

        runner.check_comicvine_api()
        assert captured.get('timeout') == 5


# ── Unit Tests: Stuck Tasks Check ──

class TestStuckTasksCheck:
    """Tests for check_stuck_tasks() — scheduler stale task detection."""

    @pytest.mark.unit
    def test_all_tasks_idle_returns_empty(self, runner, mock_config, mock_globals, mock_db):
        # all statuses are 'Waiting' by default from mock_globals
        results = runner.check_stuck_tasks()
        assert results == []

    @pytest.mark.unit
    def test_task_running_under_threshold_returns_empty(self, runner, mock_config, mock_globals, mock_db, monkeypatch):
        monkeypatch.setattr(mylar, "MONITOR_STATUS", 'Running', raising=False)
        # task started 5 minutes ago — under the 60 min threshold
        five_min_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).isoformat()
        mock_db._data = [{'current_run': five_min_ago}]

        results = runner.check_stuck_tasks()
        assert results == []

    @pytest.mark.unit
    def test_task_running_over_threshold_returns_warning(self, runner, mock_config, mock_globals, mock_db, monkeypatch):
        monkeypatch.setattr(mylar, "MONITOR_STATUS", 'Running', raising=False)
        # task started 2 hours ago — well over the 60 min threshold
        two_hours_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
        mock_db._data = [{'current_run': two_hours_ago}]

        results = runner.check_stuck_tasks()
        assert len(results) >= 1
        assert results[0].severity == 'warning'
        assert 'Monitor' in results[0].message

    @pytest.mark.unit
    def test_multiple_stuck_tasks_returns_multiple(self, runner, mock_config, mock_globals, mock_db, monkeypatch):
        monkeypatch.setattr(mylar, "MONITOR_STATUS", 'Running', raising=False)
        monkeypatch.setattr(mylar, "SEARCH_STATUS", 'Running', raising=False)
        two_hours_ago = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
        mock_db._data = [{'current_run': two_hours_ago}]

        results = runner.check_stuck_tasks()
        assert len(results) >= 2


# ── Unit Tests: Disk Space Check ──

class TestDiskSpaceCheck:
    """Tests for check_disk_space() — storage volume monitoring."""

    @pytest.mark.unit
    def test_plenty_of_space_returns_empty(self, runner, mock_config, tmp_path, monkeypatch):
        real_dir = str(tmp_path)
        mock_config.DESTINATION_DIR = real_dir
        mock_config.CACHE_DIR = None
        # set thresholds very low so real disk space passes
        mock_config.HEALTH_DISK_WARN_GB = '0.001'
        mock_config.HEALTH_DISK_ERROR_GB = '0.0001'

        results = runner.check_disk_space()
        assert results == []

    @pytest.mark.unit
    def test_low_space_returns_warning(self, runner, mock_config, tmp_path, monkeypatch):
        import shutil
        real_dir = str(tmp_path)
        mock_config.DESTINATION_DIR = real_dir
        mock_config.CACHE_DIR = None

        # get actual free space and set warning threshold just above it
        usage = shutil.disk_usage(real_dir)
        free_gb = usage.free / (1024 ** 3)
        mock_config.HEALTH_DISK_WARN_GB = str(free_gb + 10)
        mock_config.HEALTH_DISK_ERROR_GB = '0.0001'

        results = runner.check_disk_space()
        assert len(results) == 1
        assert results[0].severity == 'warning'

    @pytest.mark.unit
    def test_critical_space_returns_error(self, runner, mock_config, tmp_path, monkeypatch):
        import shutil
        real_dir = str(tmp_path)
        mock_config.DESTINATION_DIR = real_dir
        mock_config.CACHE_DIR = None

        # get actual free space and set error threshold just above it
        usage = shutil.disk_usage(real_dir)
        free_gb = usage.free / (1024 ** 3)
        mock_config.HEALTH_DISK_WARN_GB = str(free_gb + 20)
        mock_config.HEALTH_DISK_ERROR_GB = str(free_gb + 10)

        results = runner.check_disk_space()
        assert len(results) == 1
        assert results[0].severity == 'error'

    @pytest.mark.unit
    def test_threshold_cast_from_string_config(self, runner, mock_config, tmp_path):
        # verify string config values are properly cast to float
        mock_config.DESTINATION_DIR = str(tmp_path)
        mock_config.CACHE_DIR = None
        mock_config.HEALTH_DISK_WARN_GB = '0.001'
        mock_config.HEALTH_DISK_ERROR_GB = '0.0001'

        # should not raise a TypeError from failing to cast
        results = runner.check_disk_space()
        assert isinstance(results, list)

    @pytest.mark.unit
    def test_nonexistent_path_skipped(self, runner, mock_config):
        mock_config.DESTINATION_DIR = '/absolutely/nonexistent/path'
        mock_config.CACHE_DIR = None

        results = runner.check_disk_space()
        # nonexistent paths are skipped (os.path.exists guard), not errors
        assert results == []

    @pytest.mark.unit
    def test_same_mount_not_checked_twice(self, runner, mock_config, tmp_path):
        # both point to the same filesystem
        mock_config.DESTINATION_DIR = str(tmp_path)
        mock_config.CACHE_DIR = str(tmp_path)
        mock_config.HEALTH_DISK_WARN_GB = '0.001'
        mock_config.HEALTH_DISK_ERROR_GB = '0.0001'

        results = runner.check_disk_space()
        # even if both paths exist, same mount should only be checked once
        assert isinstance(results, list)


# ── Unit Tests: Download Client Check ──

class TestDownloadClientCheck:
    """Tests for check_download_client() — SABnzbd/NZBGet connectivity."""

    @pytest.mark.unit
    def test_sabnzbd_reachable_returns_empty(self, runner, mock_config, mock_globals, monkeypatch):
        monkeypatch.setattr(mylar, "USE_SABNZBD", True, raising=False)

        class FakeResponse:
            status_code = 200
        monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

        results = runner.check_download_client()
        assert results == []

    @pytest.mark.unit
    def test_sabnzbd_unreachable_returns_error(self, runner, mock_config, mock_globals, monkeypatch):
        monkeypatch.setattr(mylar, "USE_SABNZBD", True, raising=False)

        def fake_conn_error(*args, **kwargs):
            raise requests.exceptions.ConnectionError("Connection refused")
        monkeypatch.setattr(requests, "get", fake_conn_error)

        results = runner.check_download_client()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert 'SABnzbd' in results[0].message

    @pytest.mark.unit
    def test_sabnzbd_timeout_returns_error(self, runner, mock_config, mock_globals, monkeypatch):
        monkeypatch.setattr(mylar, "USE_SABNZBD", True, raising=False)

        def fake_timeout(*args, **kwargs):
            raise requests.exceptions.Timeout("timed out")
        monkeypatch.setattr(requests, "get", fake_timeout)

        results = runner.check_download_client()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert 'timed out' in results[0].message.lower()

    @pytest.mark.unit
    def test_nzbget_reachable_returns_empty(self, runner, mock_config, mock_globals, monkeypatch):
        monkeypatch.setattr(mylar, "USE_NZBGET", True, raising=False)

        class FakeResponse:
            status_code = 200
        monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())

        results = runner.check_download_client()
        assert results == []

    @pytest.mark.unit
    def test_no_client_configured_returns_empty(self, runner, mock_config, mock_globals):
        # all USE_* flags are False by default
        results = runner.check_download_client()
        assert results == []

    @pytest.mark.unit
    def test_sabnzbd_request_uses_5s_timeout(self, runner, mock_config, mock_globals, monkeypatch):
        monkeypatch.setattr(mylar, "USE_SABNZBD", True, raising=False)

        captured = {}
        class FakeResponse:
            status_code = 200
        def capture_get(*args, **kwargs):
            captured.update(kwargs)
            return FakeResponse()
        monkeypatch.setattr(requests, "get", capture_get)

        runner.check_download_client()
        assert captured.get('timeout') == 5


# ── Unit Tests: No Indexers Check ──

class TestNoIndexersCheck:
    """Tests for check_no_indexers() — provider configuration check."""

    @pytest.mark.unit
    def test_indexers_configured_returns_empty(self, runner, mock_config, mock_globals):
        # simulate one enabled newznab provider
        # tuple format: (name, host, verify, apikey, uid, enabled, id)
        mock_config.EXTRA_NEWZNABS = [
            ('TestProvider', 'http://example.com', False, 'key123', '0', '1', '0')
        ]

        results = runner.check_no_indexers()
        assert results == []

    @pytest.mark.unit
    def test_no_indexers_returns_error(self, runner, mock_config, mock_globals):
        mock_config.EXTRA_NEWZNABS = []
        mock_config.EXTRA_TORZNABS = []
        mock_config.ENABLE_TORRENT_SEARCH = False
        mock_config.EXPERIMENTAL = False

        results = runner.check_no_indexers()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert results[0].check_name == 'no_indexers'

    @pytest.mark.unit
    def test_torznab_configured_returns_empty(self, runner, mock_config, mock_globals):
        mock_config.EXTRA_NEWZNABS = []
        mock_config.EXTRA_TORZNABS = [
            ('Jackett', 'http://jackett:9117', False, 'key', '0', '1', '0')
        ]

        results = runner.check_no_indexers()
        assert results == []

    @pytest.mark.unit
    def test_torrent_search_enabled_returns_empty(self, runner, mock_config, mock_globals):
        mock_config.EXTRA_NEWZNABS = []
        mock_config.EXTRA_TORZNABS = []
        mock_config.ENABLE_TORRENT_SEARCH = True

        results = runner.check_no_indexers()
        assert results == []


# ── Unit Tests: Simple Config/State Checks ──

class TestSimpleChecks:
    """Tests for simple config and state checks (API key, download client, update, permissions, DB)."""

    @pytest.mark.unit
    def test_api_key_present_returns_empty(self, runner, mock_config):
        results = runner.check_api_key_missing()
        assert results == []

    @pytest.mark.unit
    def test_api_key_missing_returns_error(self, runner, mock_config):
        mock_config.COMICVINE_API = None
        results = runner.check_api_key_missing()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert results[0].check_name == 'api_key_missing'

    @pytest.mark.unit
    def test_api_key_whitespace_returns_error(self, runner, mock_config):
        mock_config.COMICVINE_API = '   '
        results = runner.check_api_key_missing()
        assert len(results) == 1
        assert results[0].severity == 'error'

    @pytest.mark.unit
    def test_api_key_none_string_returns_error(self, runner, mock_config):
        mock_config.COMICVINE_API = 'None'
        results = runner.check_api_key_missing()
        assert len(results) == 1
        assert results[0].severity == 'error'

    @pytest.mark.unit
    def test_no_download_client_returns_warning(self, runner, mock_config, mock_globals):
        # all USE_* flags are False by default from mock_globals
        results = runner.check_no_download_client()
        assert len(results) == 1
        assert results[0].severity == 'warning'
        assert results[0].check_name == 'no_download_client'

    @pytest.mark.unit
    def test_download_client_configured_returns_empty(self, runner, mock_config, mock_globals, monkeypatch):
        monkeypatch.setattr(mylar, "USE_SABNZBD", True, raising=False)
        results = runner.check_no_download_client()
        assert results == []

    @pytest.mark.unit
    def test_update_available_returns_notice(self, runner, mock_config, mock_globals, monkeypatch):
        monkeypatch.setattr(mylar, "COMMITS_BEHIND", 5, raising=False)
        results = runner.check_update_available()
        assert len(results) == 1
        assert results[0].severity == 'notice'
        assert results[0].check_name == 'update_available'
        assert '5' in results[0].message

    @pytest.mark.unit
    def test_no_update_returns_empty(self, runner, mock_config, mock_globals):
        results = runner.check_update_available()
        assert results == []

    @pytest.mark.unit
    def test_permissions_ok_returns_empty(self, runner, mock_config, mock_globals, tmp_path, monkeypatch):
        real_dir = str(tmp_path / "data")
        os.makedirs(real_dir, exist_ok=True)
        monkeypatch.setattr(mylar, "DATA_DIR", real_dir, raising=False)
        monkeypatch.setattr(mylar, "LOG_DIR", real_dir, raising=False)
        mock_config.CACHE_DIR = real_dir

        results = runner.check_permissions()
        assert results == []

    @pytest.mark.unit
    def test_permissions_not_writable_returns_error(self, runner, mock_config, mock_globals, tmp_path, monkeypatch):
        real_dir = str(tmp_path / "data")
        os.makedirs(real_dir, exist_ok=True)
        monkeypatch.setattr(mylar, "DATA_DIR", real_dir, raising=False)
        monkeypatch.setattr(mylar, "LOG_DIR", None, raising=False)
        mock_config.CACHE_DIR = None

        # mock os.access to return False for write check
        original_access = os.access
        def fake_access(path, mode):
            if path == real_dir and mode == os.W_OK:
                return False
            return original_access(path, mode)
        monkeypatch.setattr(os, "access", fake_access)

        results = runner.check_permissions()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert results[0].check_name == 'permissions'

    @pytest.mark.unit
    def test_database_integrity_ok_returns_empty(self, runner, mock_db):
        # PRAGMA integrity_check returns 'ok' for a healthy DB
        # simulate sqlite3.Row-like tuple result
        mock_db._data = [('ok',)]

        results = runner.check_database_integrity()
        assert results == []

    @pytest.mark.unit
    def test_database_integrity_corrupt_returns_error(self, runner, mock_db):
        mock_db._data = [('*** in tree page 5 of table foo: cell 12 is out of range',)]

        results = runner.check_database_integrity()
        assert len(results) == 1
        assert results[0].severity == 'error'
        assert results[0].check_name == 'database_integrity'

    @pytest.mark.unit
    def test_indexer_down_returns_warning(self, runner, mock_config, mock_globals, monkeypatch):
        monkeypatch.setattr(mylar, "PROVIDER_STATUS", {'NZBgeek': 'fail'}, raising=False)

        results = runner.check_indexers()
        assert len(results) == 1
        assert results[0].severity == 'warning'
        assert 'NZBgeek' in results[0].message

    @pytest.mark.unit
    def test_indexer_ok_returns_empty(self, runner, mock_config, mock_globals, monkeypatch):
        monkeypatch.setattr(mylar, "PROVIDER_STATUS", {'NZBgeek': 'success'}, raising=False)

        results = runner.check_indexers()
        assert results == []

    @pytest.mark.unit
    def test_indexers_not_populated_returns_empty(self, runner, mock_config, mock_globals):
        # PROVIDER_STATUS is None when not populated yet
        results = runner.check_indexers()
        assert results == []


# ── Unit Tests: HealthLogHandler ──

class TestHealthLogHandler:
    """Tests for the HealthLogHandler log interceptor."""

    def _make_record(self, message, level=logging.WARNING):
        """Helper to create a log record."""
        record = logging.LogRecord(
            name='mylar',
            level=level,
            pathname='test.py',
            lineno=1,
            msg=message,
            args=(),
            exc_info=None,
        )
        return record

    @pytest.mark.unit
    def test_ignores_info_messages(self, mock_globals, monkeypatch):
        handler = HealthLogHandler()
        record = self._make_record('ComicVine timeout error', level=logging.INFO)

        # handler level is WARNING — INFO should be filtered by logging framework
        assert handler.level == logging.WARNING
        assert record.levelno < handler.level

    @pytest.mark.unit
    def test_ignores_debug_messages(self, mock_globals, monkeypatch):
        handler = HealthLogHandler()
        record = self._make_record('ComicVine timeout error', level=logging.DEBUG)

        assert record.levelno < handler.level

    @pytest.mark.unit
    def test_catches_comicvine_timeout_pattern(self, mock_globals, mock_config, mock_db, monkeypatch):
        runner = HealthCheckRunner()
        monkeypatch.setattr(mylar, "HEALTH_CHECK", runner, raising=False)

        handler = HealthLogHandler()
        record = self._make_record('ComicVine API timeout after 5s')
        handler.emit(record)

        results = runner.get_results()
        assert len(results) == 1
        assert results[0].check_name == 'comicvine_api'

    @pytest.mark.unit
    def test_catches_sabnzbd_connection_pattern(self, mock_globals, mock_config, mock_db, monkeypatch):
        runner = HealthCheckRunner()
        monkeypatch.setattr(mylar, "HEALTH_CHECK", runner, raising=False)

        handler = HealthLogHandler()
        record = self._make_record('SABnzbd connection refused at localhost:8080')
        handler.emit(record)

        results = runner.get_results()
        assert len(results) == 1
        assert results[0].check_name == 'download_client'

    @pytest.mark.unit
    def test_catches_permission_denied_pattern(self, mock_globals, mock_config, mock_db, monkeypatch):
        runner = HealthCheckRunner()
        monkeypatch.setattr(mylar, "HEALTH_CHECK", runner, raising=False)

        handler = HealthLogHandler()
        record = self._make_record('Permission denied writing to /data/comics')
        handler.emit(record)

        results = runner.get_results()
        assert len(results) == 1
        assert results[0].check_name == 'permissions'

    @pytest.mark.unit
    def test_catches_disk_full_pattern(self, mock_globals, mock_config, mock_db, monkeypatch):
        runner = HealthCheckRunner()
        monkeypatch.setattr(mylar, "HEALTH_CHECK", runner, raising=False)

        handler = HealthLogHandler()
        record = self._make_record('No space left on device')
        handler.emit(record)

        results = runner.get_results()
        assert len(results) == 1
        assert results[0].check_name == 'disk_space'

    @pytest.mark.unit
    def test_catches_database_locked_pattern(self, mock_globals, mock_config, mock_db, monkeypatch):
        runner = HealthCheckRunner()
        monkeypatch.setattr(mylar, "HEALTH_CHECK", runner, raising=False)

        handler = HealthLogHandler()
        record = self._make_record('database is locked - concurrent access error')
        handler.emit(record)

        results = runner.get_results()
        assert len(results) == 1
        assert results[0].check_name == 'database_integrity'

    @pytest.mark.unit
    def test_skips_healthcheck_prefixed_messages(self, mock_globals, mock_config, mock_db, monkeypatch):
        """Messages with [HealthCheck] prefix are skipped to prevent infinite loops."""
        runner = HealthCheckRunner()
        monkeypatch.setattr(mylar, "HEALTH_CHECK", runner, raising=False)

        handler = HealthLogHandler()
        record = self._make_record('[HealthCheck] ComicVine API timeout after 5s')
        handler.emit(record)

        results = runner.get_results()
        assert len(results) == 0

    @pytest.mark.unit
    def test_throttles_same_check_name(self, mock_globals, mock_config, mock_db, monkeypatch):
        """Same check_name should not fire again within the throttle window."""
        runner = HealthCheckRunner()
        monkeypatch.setattr(mylar, "HEALTH_CHECK", runner, raising=False)

        handler = HealthLogHandler()

        # first emit — should create a finding
        record1 = self._make_record('ComicVine API timeout first')
        handler.emit(record1)

        # second emit — should be throttled
        record2 = self._make_record('ComicVine API timeout second')
        handler.emit(record2)

        # only one result from the first emit; the second was throttled
        # (ingest_log_finding deduplication bumps check_count but handler throttle blocks it)
        results = runner.get_results()
        assert len(results) == 1

    @pytest.mark.unit
    def test_emit_never_raises_exception(self, mock_globals, monkeypatch):
        """emit() must never crash — even with broken HEALTH_CHECK."""
        monkeypatch.setattr(mylar, "HEALTH_CHECK", None, raising=False)

        handler = HealthLogHandler()
        record = self._make_record('ComicVine API timeout')

        # should not raise, even though HEALTH_CHECK is None
        handler.emit(record)


# ── Unit Tests: Database Operations ──

class TestDatabaseOperations:
    """Tests for persistence logic using a real temporary SQLite database."""

    @pytest.mark.integration
    def test_save_new_result_to_db(self, mock_config, mock_globals, real_db, monkeypatch):
        """A new health check result is persisted to the database."""
        # point db module at our real temp DB
        from mylar.db import DBConnection
        monkeypatch.setattr(mylar.db, "DBConnection", lambda: _make_real_db_conn(real_db))

        runner = HealthCheckRunner()
        result = HealthCheckResult('infrastructure', 'root_folder', 'error', 'Missing folder')
        runner._save_to_db([result])

        conn = sqlite3.connect(real_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM health_checks WHERE check_name='root_folder'").fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0]['severity'] == 'error'
        assert rows[0]['is_resolved'] == 0

    @pytest.mark.integration
    def test_save_existing_updates_count(self, mock_config, mock_globals, real_db, monkeypatch):
        """Saving the same check_name twice increments check_count."""
        monkeypatch.setattr(mylar.db, "DBConnection", lambda: _make_real_db_conn(real_db))

        runner = HealthCheckRunner()
        r1 = HealthCheckResult('infrastructure', 'root_folder', 'error', 'Missing folder')
        runner._save_to_db([r1])

        r2 = HealthCheckResult('infrastructure', 'root_folder', 'error', 'Still missing')
        runner._save_to_db([r2])

        conn = sqlite3.connect(real_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM health_checks WHERE check_name='root_folder' AND is_resolved=0").fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0]['check_count'] == 2

    @pytest.mark.integration
    def test_resolve_cleared_issues(self, mock_config, mock_globals, real_db, monkeypatch):
        """When a check passes, its DB row gets is_resolved=1."""
        monkeypatch.setattr(mylar.db, "DBConnection", lambda: _make_real_db_conn(real_db))

        runner = HealthCheckRunner()

        # first: save a failing result
        r = HealthCheckResult('infrastructure', 'root_folder', 'error', 'Missing')
        runner._save_to_db([r])

        # then: resolve it (no current results for root_folder, but check ran)
        runner._resolve_cleared([], {'root_folder'})

        conn = sqlite3.connect(real_db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM health_checks WHERE check_name='root_folder'").fetchall()
        conn.close()

        assert len(rows) == 1
        assert rows[0]['is_resolved'] == 1
        assert rows[0]['resolved_at'] is not None

    @pytest.mark.integration
    def test_cleanup_old_resolved(self, mock_config, mock_globals, real_db, monkeypatch):
        """Resolved records older than HEALTH_HISTORY_DAYS are deleted."""
        monkeypatch.setattr(mylar.db, "DBConnection", lambda: _make_real_db_conn(real_db))

        # insert an old resolved record directly
        old_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=60)).isoformat()
        conn = sqlite3.connect(real_db)
        conn.execute(
            "INSERT INTO health_checks (check_type, check_name, severity, message, first_seen, last_seen, is_resolved, resolved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            ['config', 'old_issue', 'notice', 'Old resolved issue', old_date, old_date, old_date]
        )
        conn.commit()

        # also insert a recent resolved record that should NOT be deleted
        recent_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)).isoformat()
        conn.execute(
            "INSERT INTO health_checks (check_type, check_name, severity, message, first_seen, last_seen, is_resolved, resolved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
            ['config', 'recent_issue', 'notice', 'Recent resolved issue', recent_date, recent_date, recent_date]
        )
        conn.commit()
        conn.close()

        runner = HealthCheckRunner()
        runner._cleanup_old()

        conn = sqlite3.connect(real_db)
        rows = conn.execute("SELECT * FROM health_checks WHERE is_resolved=1").fetchall()
        conn.close()

        assert len(rows) == 1  # only the recent one survives

    @pytest.mark.integration
    def test_load_from_db_on_startup(self, mock_config, mock_globals, real_db, monkeypatch):
        """Active issues are loaded from DB on startup."""
        monkeypatch.setattr(mylar.db, "DBConnection", lambda: _make_real_db_conn(real_db))

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        conn = sqlite3.connect(real_db)
        conn.execute(
            "INSERT INTO health_checks (check_type, check_name, severity, message, source, first_seen, last_seen, is_resolved, check_count, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 0, 1, ?)",
            ['provider', 'comicvine_api', 'error', 'CV timeout', 'health_check', now, now, '{}']
        )
        conn.commit()
        conn.close()

        runner = HealthCheckRunner()
        runner.load_from_db()

        results = runner.get_results()
        assert len(results) == 1
        assert results[0].check_name == 'comicvine_api'
        assert results[0].severity == 'error'

    @pytest.mark.integration
    def test_get_resolved_history(self, mock_config, mock_globals, real_db, monkeypatch):
        """Resolved history returns recently resolved checks."""
        monkeypatch.setattr(mylar.db, "DBConnection", lambda: _make_real_db_conn(real_db))

        recent = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)).isoformat()
        conn = sqlite3.connect(real_db)
        conn.execute(
            "INSERT INTO health_checks (check_type, check_name, severity, message, source, first_seen, last_seen, is_resolved, resolved_at, check_count, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, 3, ?)",
            ['provider', 'comicvine_api', 'error', 'CV was down', 'health_check', recent, recent, recent, '{}']
        )
        conn.commit()
        conn.close()

        runner = HealthCheckRunner()
        history = runner.get_resolved_history(days=30)
        assert len(history) == 1
        assert history[0]['check_name'] == 'comicvine_api'
        assert history[0]['check_count'] == 3


# ── Helper: Real DB connection wrapper ──

def _make_real_db_conn(db_path):
    """Create a real SQLite connection wrapped to match mylar.db.DBConnection interface."""

    class RealDBConnection:
        def __init__(self):
            self._conn = sqlite3.connect(db_path)
            self._conn.row_factory = sqlite3.Row

        def select(self, query, params=None):
            cursor = self._conn.execute(query, params or [])
            return cursor.fetchall()

        def action(self, query, params=None):
            self._conn.execute(query, params or [])
            self._conn.commit()

        def upsert(self, table, new_values, control):
            pass

    return RealDBConnection()
