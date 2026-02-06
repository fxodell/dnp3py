# nfm-dnp3 (dnp3py) – Claude project instructions

Use this file for project-specific context when editing or reviewing code.

## Project summary

PyPI package: **nfm-dnp3**. Pure Python DNP3 master driver for SCADA over TCP/IP. Main entry: `from dnp3py import DNP3Master, DNP3Config`. Repo root is the package (`package_dir={"dnp3py": "."}`).

## Where to look

- **Full context**: `docs/CONTEXT.md` – stack layout, conventions, validation, testing.
- **User-facing docs**: `README.md` – install, quick start, architecture, development notes.
- **Main API**: `core/master.py` (`DNP3Master`), `core/config.py` (`DNP3Config`).
- **Layers**: `layers/datalink.py`, `layers/transport.py`, `layers/application.py`.
- **Objects**: `objects/binary.py`, `objects/analog.py`, `objects/counter.py`, `objects/groups.py`.
- **Utils**: `utils/crc.py`, `utils/logging.py`.

## Conventions

- **Validation**: Config, layers, and objects validate inputs (types, ranges); raise `ValueError`/`TypeError`/`DNP3*Error` with clear messages.
- **Exports**: Each package uses `__all__` in `__init__.py`; root `dnp3py` exports a subset; use `dnp3py.core`, `dnp3py.layers`, `dnp3py.objects`, `dnp3py.utils` for full APIs.
- **Tests**: `pytest tests/ -v` from repo root; require `pip install -e ".[dev]"`.
- **Version**: Single source in root `__init__.py`; `setup.py` reads it from there.

## When changing code

- Preserve existing validation and error messages; add validation for new public APIs.
- Keep `__all__` and docstrings in sync with exports and `Raises` sections.
- After edits, run relevant tests and fix linter issues.
