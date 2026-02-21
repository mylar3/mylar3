# Mylar3 Test Suite

## Overview

The test suite covers core Mylar3 functionality and the health check monitoring system. It contains **372 tests** across three test files and runs in under 1 second with zero network calls.

| File | Tests | What it covers |
|------|------:|----------------|
| `test_helpers.py` | 178 | Utility functions in `mylar/helpers.py` |
| `test_filechecker.py` | 57 | Filename parsing in `mylar/filechecker.py` (data-driven) |
| `test_healthcheck.py` | 137 | Health monitoring system in `mylar/healthcheck.py` |

## Prerequisites / Setup

Set up a virtual environment targeting your Python version (3.8+ supported):

```bash
# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows
py -3 -m venv .venv
.venv\Scripts\activate
```

Install both the project dependencies and test dependencies:

```bash
pip install -r requirements.txt
pip install -r tests/requirements.txt
```

Verify the setup by collecting tests without running them:

```bash
pytest tests/ -v --co
```

No Docker, Selenium, or external services are needed. All tests run locally with zero network calls — `conftest.py` auto-patches `requests.get` to raise `RuntimeError` if any test accidentally attempts a real HTTP request.

## Quick Reference

```bash
# Full suite
pytest tests/                                        # Run ALL tests
pytest tests/ -v                                     # Verbose output
pytest tests/ -q --tb=line                           # Minimal output
pytest tests/ -x                                     # Stop on first failure
pytest tests/ -s                                     # Show print() output
pytest tests/ --pdb                                  # Debug on failure

# By marker
pytest tests/ -m unit                                # Unit tests only
pytest tests/ -m integration                         # Integration tests only
pytest tests/ -m "not bench"                         # Skip benchmarks

# Health check tests
pytest tests/test_healthcheck.py -v                  # All health check tests
pytest tests/test_healthcheck.py -m unit -v          # Health check unit tests
pytest tests/test_healthcheck.py -m integration -v   # Health check integration tests

# Other test files
pytest tests/test_helpers.py -v                      # Helper tests only
pytest tests/test_filechecker.py -v                  # File checker tests only

# Targeted runs
pytest tests/test_healthcheck.py -k "comicvine"                                     # Keyword match
pytest tests/test_healthcheck.py::TestComicVineCheck                                 # Single class
pytest tests/test_healthcheck.py::TestComicVineCheck::test_timeout_returns_error      # Single test
```

## Test File Inventory

### test_helpers.py (178 tests)

Tests for `mylar/helpers.py` utility functions: string formatting, issue number parsing, file size formatting, publisher detection, URL construction, DDL cleanup, and environment scripting. Uses `mockito` for mock verification in DDL and script tests.

### test_filechecker.py (57 tests)

Data-driven tests for `mylar/filechecker.py` filename parsing. Each test case is a real-world comic filename with expected parsed fields (series name, issue number, year, volume). Test data is loaded from an external data file.

### test_healthcheck.py (137 tests)

Tests for `mylar/healthcheck.py` — the health monitoring engine, individual checks, log interceptor, and database persistence. Organized into 17 test classes:

| Class | Tests | Marker | Description |
|-------|------:|--------|-------------|
| `TestHealthCheckResult` | 9 | unit | Data container: creation, validation, serialization, `from_db_row` |
| `TestHealthCheckRunner` | 14 | unit | Engine core: results, summary, dismiss, interval gating, thread safety |
| `TestRootFolderCheck` | 6 | unit | Filesystem check: exists, missing, unreadable, multiple paths |
| `TestComicVineCheck` | 8 | unit | API connectivity: success, timeout, errors, rate limit, status codes |
| `TestStuckTasksCheck` | 4 | unit | Scheduler stale task detection with elapsed time thresholds |
| `TestDiskSpaceCheck` | 6 | unit | Storage volume monitoring, warn/error thresholds, mount dedup |
| `TestDownloadClientCheck` | 6 | unit | SABnzbd/NZBGet HTTP connectivity |
| `TestNoIndexersCheck` | 4 | unit | Provider configuration: newznab, torznab, torrent search |
| `TestSimpleChecks` | 15 | unit | API key, download client config, update, permissions, DB integrity, indexer status |
| `TestHealthLogHandler` | 10 | unit | Log interceptor: pattern matching, throttling, loop prevention |
| `TestRunAllChecks` | 6 | unit | Orchestration: disabled mode, exception resilience, severity sorting, carry-forward |
| `TestTorrentClientChecks` | 16 | unit | qBittorrent, Transmission, rTorrent, Deluge, uTorrent connectivity |
| `TestNZBGetCheck` | 6 | unit | NZBGet protocol/URL parsing (https/http/bare) and connectivity |
| `TestFailedPostProcessing` | 4 | unit | Post-processing failure count detection from DB |
| `TestSSEAndHelpers` | 6 | unit | SSE push, clear resolved history, load errors, default days |
| `TestCheckEdgeCases` | 11 | unit | Generic exceptions, blocklist reasons, naive timestamps, deferred stubs |
| `TestDatabaseOperations` | 6 | integration | Real SQLite: save/load round trip, resolve, cleanup, startup load, resolved history |

## Markers

Markers are defined in `pytest.ini` and allow selective test execution:

| Marker | Description |
|--------|-------------|
| `unit` | Fast isolated tests with mocked dependencies (runs in <0.5s) |
| `integration` | Tests using real SQLite databases in temporary directories |
| `bench` | Benchmarking tests (currently disabled — `pytest-benchmark` is commented out in `requirements.txt`) |

Combine markers with standard pytest expressions:

```bash
pytest tests/ -m "unit and not bench"
pytest tests/ -m "unit or integration"
```

## Test Architecture & Patterns

### Network isolation

`conftest.py` auto-patches `requests.get` globally with an `autouse` fixture. All tests run offline by default. When a test needs a fake HTTP response, it re-patches `requests.get` per-test using `monkeypatch`:

```python
class FakeResponse:
    status_code = 200
monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse())
```

To simulate errors, patch with a function that raises:

```python
def fake_timeout(*args, **kwargs):
    raise requests.exceptions.Timeout("timed out")
monkeypatch.setattr(requests, "get", fake_timeout)
```

### Config mocking

Create a real `Config` object pointed at a nonexistent file, then override individual attributes:

```python
config = mylar.config.Config("./nothing")
monkeypatch.setattr(mylar, "CONFIG", config)
monkeypatch.setattr(config, "HEALTH_CHECK_ENABLED", True, raising=False)
```

### DB mocking (unit tests)

`FakeDBConnection` class with `select()`, `action()`, `upsert()` stubs. Pre-load data via `mock_db._data`:

```python
mock_db._data = [{'cnt': 12}]  # what select() will return
```

### DB mocking (integration tests)

The `real_db` fixture creates a real SQLite file in `tmp_path` with the actual `health_checks` table schema. `_make_real_db_conn()` wraps it in the `DBConnection` interface:

```python
monkeypatch.setattr(mylar.db, "DBConnection", lambda: _make_real_db_conn(real_db))
```

### Globals mocking

The `mock_globals` fixture sets all `mylar.*` globals (`MONITOR_STATUS`, `USE_SABNZBD`, `PROVIDER_STATUS`, etc.) to safe defaults so tests start from a known state.

### Fixture composition

The `runner` fixture composes `mock_config` + `mock_globals` + `mock_db` to create a ready-to-use `HealthCheckRunner`:

```python
@pytest.fixture
def runner(mock_config, mock_globals, mock_db):
    return HealthCheckRunner()
```

### Filesystem testing

Uses pytest's `tmp_path` fixture for real temporary directories. Permission tests mock `os.access` via `monkeypatch`.

### Socket mocking

Deluge uses raw TCP (not HTTP), so its tests mock `socket.create_connection`:

```python
monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: FakeSocket())
```

## Code Coverage

Full project coverage:

```bash
pytest tests/ --cov-config=tests/.coveragerc --cov=. tests/
```

Health check module coverage with uncovered line numbers:

```bash
pytest tests/test_healthcheck.py --cov=mylar.healthcheck --cov-config=tests/.coveragerc --cov-report=term-missing -v
```

HTML coverage report:

```bash
pytest tests/test_healthcheck.py --cov=mylar.healthcheck --cov-report=html:htmlcov -v
open htmlcov/index.html
```

**Target**: >=80% for `mylar/healthcheck.py` (currently at 94%).

Lines that are legitimately hard to cover include bare `except Exception: pass` safety nets in private helpers (`_save_to_db`, `_resolve_cleared`, `_cleanup_old`) and generic fallback exception handlers in download client checks.

## Health Check Manual Testing

Automated tests cover the engine, check logic, and data layer. Manual/functional testing of the UI components (dashboard page, persistent banner, nav badge, SSE real-time updates) is documented separately.

Key manual test areas:

- `/health` dashboard page — table rendering, dismiss/recheck buttons
- Persistent banner on every page — shows highest-severity active issue
- Nav badge — error/warning count in the navigation bar
- SSE real-time updates — browser receives `health_update` events without page refresh
- `/ping` endpoint — unauthenticated health probe (returns 200 OK)
- Config settings — enable/disable, thresholds, history retention

See `docs/health-dashboard/TESTING_PLAN.md` for the full manual testing checklist with 20 step-by-step test recipes.

## Test Data Files

Be wary if editing test data files in Excel as it has a habit of making assumptions about column types and making changes. If it becomes frustrating, it may be worth migrating to JSON/XML.

## Adding New Tests

- **Health check tests** go in `test_healthcheck.py` (single file, not split by feature)
- Follow the existing class organization — group by what you're testing
- Mark every test method: `@pytest.mark.unit` or `@pytest.mark.integration`
- Use the existing fixtures: `mock_config`, `mock_globals`, `mock_db`, `runner`, `real_db`
- Network calls are blocked by default — mock `requests.get` per-test when needed
- Use descriptive method names: `test_comicvine_timeout_returns_error` not `test_cv_1`
- Run the full suite after adding tests to check for regressions:

```bash
pytest tests/ -v
```
