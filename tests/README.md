# GhostHub Test Suite

GhostHub has Python tests for backend services/controllers and JavaScript tests for browser modules. Use Python 3.9 and the project virtual environment for Python commands.

## Setup

```bash
python3.9 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd static/js
npm install
cd ../..
```

## Running Tests

Run everything:

```bash
./venv/bin/python scripts/run_all_tests.py
```

Run only Python tests:

```bash
./venv/bin/python scripts/run_all_tests.py --py
```

Run only JavaScript tests:

```bash
./venv/bin/python scripts/run_all_tests.py --js
```

Run a specific Python test file:

```bash
./venv/bin/python -m pytest tests/test_database_service.py -v
```

Run a specific Python test:

```bash
./venv/bin/python -m pytest tests/test_database_service.py::TestProgressOperations::test_save_progress_basic -v
```

Run JavaScript tests directly:

```bash
cd static/js
npm test
```

Run Python coverage:

```bash
./venv/bin/python -m pytest --cov=app --cov-report=html
```

## Test Categories

- Unit tests cover services, utilities, storage, configuration, media handling, and progress tracking.
- Integration tests cover application factory behavior, SPECTER controllers, routes, socket-facing behavior, and admin workflows.
- JavaScript tests cover frontend modules under `static/js`.

## Key Fixtures

- `app`: creates a test Flask application instance.
- `client`: Flask test client for HTTP requests.
- `app_context`: pushes an application context.
- `test_db`: creates isolated test database state.
- `mock_media_dir`: creates temporary media files.
- `mock_usb_drive`: creates a mock USB drive structure.
- `mock_config`: overrides configuration values for a test.
- `mock_file_storage`: creates mock upload objects.

## Troubleshooting

If imports fail, make sure you are running commands from the project root with the virtual environment Python. If JavaScript tests fail because dependencies are missing, run `npm install` in `static/js`.

If media or thumbnail tests fail locally, verify FFmpeg is installed. Socket tests should use mocks rather than live connections unless a test explicitly documents otherwise.

GitHub release CI runs `python scripts/run_all_tests.py` before packaging release assets.
