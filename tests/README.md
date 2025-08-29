# Running Mylar Test Suite

This guide explains how to set up and run this test suite using `pytest`.

## Setup Environment

It is recommended that you set up your pytest environment in a new venv, preferably targeting the lowest supported version of Python for Mylar (3.8 at time of writing).  For Windows hosts, you can use the [Python Launcher](https://docs.python.org/3/using/windows.html#launcher) to call different installed versions more easily.

#### Linux
```bash
python3.8 -m venv /path/to/your/env
```

#### Windows
```bat
py -3.8 -m venv C:\YourNewEnv
```

Once you have activated your environment, be install both the core Mylar `requirements.txt` in the project root, and those in the tests folder.  The latter will install pytest and any additional plugins that are in use.

## Running the Tests

From the root of the project, run the following command to execute all tests:

```bash
pytest tests
```

Verbosity is default, with some additional information on xpass/xfail results.

## Using Markers

This project uses custom pytest markers, which are configured in `pytest.ini`. Markers allow you to categorize and selectively run tests. For example, to just run the unit tests:

```bash
pytest -m unit tests
```

or to run the unit tests, but exclude the benchmarking tests:

```bash
pytest -m unit -m "not benchmark" tests
```

Refer to `pytest.ini` for a list and description of all available markers.

## Test data files

Be wary if editing test data files in Excel as it has a habit of making assumptions about column types and making changes.  If it becomes frustrating, it may be worth migrating to json / xml.

## Code Coverage

A `.coveragerc` file is provided to test code coverage using [pytest-cov](https://pytest-cov.readthedocs.io/en/latest/).  This can be executed from the root of the project with:

```bash
pytest --cov-config=tests/.coveragerc --cov=. tests
```