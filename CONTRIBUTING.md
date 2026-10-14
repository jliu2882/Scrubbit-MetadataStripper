# Contributing

## Setup

```bash
pip install -e ".[gui,heic,dev]"
pytest
ruff check src tests
```

## Layout

- `src/metastrip/core/` - all logic, no GUI or CLI imports. Add new behavior here first.
- `src/metastrip/core/handlers/` - one module per file format. A handler implements `read()` and `strip()`.
- `src/metastrip/cli/` and `src/metastrip/gui/` - thin front-ends over the core.
- `tests/` - pytest suite; sample images are generated in `conftest.py`, so no binary fixtures are checked in.

## Adding a format

1. Create a handler in `core/handlers/` that subclasses `FormatHandler`.
2. Register its signature in `core/handlers/__init__.py` (`detect`) and add its extension to `SUPPORTED_EXTENSIONS`.
3. Add a fixture in `tests/conftest.py` and tests in `tests/test_formats.py`.

## Pull requests

Keep changes focused, add tests for new behavior, and make sure `pytest` and `ruff check` pass.
