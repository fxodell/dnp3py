# dnp3py – Project Context

## What this project is

**dnp3py** is a pure Python implementation of the DNP3 (Distributed Network Protocol 3) protocol for SCADA communications over TCP/IP. It acts as a **master station** talking to DNP3 outstations (slaves): reading points (binary, analog, counter), controlling outputs, and handling events.

## Stack and layout

- **Root** – `dnp3py/__init__.py` exports `DNP3Master`, `DNP3Config`, DNP3 exceptions, and `__version__`; this is the main entry point for `from dnp3py import ...`.
- **core/** – `DNP3Master` (main API in `core/master.py`: thread-safe, `connect()` context manager; communication errors include host/port), `DNP3Config`, `PollResult` (return type of integrity_poll/read_class), and DNP3 exceptions. `core/__init__.py` re-exports all of these; top-level `dnp3py` exports a subset (see root `__init__.py`). `core/config.py` holds `DNP3Config` and protocol enums (LinkLayerFunction, AppLayerFunction, QualifierCode, ControlCode, ControlStatus, IINFlags). `validate()` coerces and validates all config fields (host, port, addresses 0-65519, timeouts, max_frame_size 1-250, max_apdu_size 1-65536, log_level); `IINFlags.from_bytes` validates iin1/iin2. `core/exceptions.py` defines `DNP3Error` and subclasses (Communication, Timeout, Protocol, CRC, Frame, Object, Control) with optional context attributes; see `__all__` and module docstring. The master coordinates connection, request/response, and parsing.
- **layers/** – Data Link (frames, CRC), Transport (segmentation), Application (function codes, object headers, IIN). `layers/__init__.py` re-exports `DataLinkLayer`, `TransportLayer`, and `ApplicationLayer`; frame/segment/request types and constants are in the datalink, transport, and application submodules. Used by the master; not typically used directly by callers.
- **objects/** – DNP3 data types: binary, analog, counter, plus `groups.py` (object group/variation definitions and sizes). `objects/__init__.py` re-exports the data types, `ObjectGroup`, `ObjectVariation`, `get_object_size`, and `get_group_name`; parse functions live in the binary, analog, and counter submodules.
- **utils/** – CRC-16 DNP3 (`crc.py`) and logging (`logging.py`). `utils/__init__.py` re-exports `CRC16DNP3`, `calculate_frame_crc`, `setup_logging`, `get_logger`, `log_frame`, and `log_parsed_frame`. CRC validates input types; logging validates level and frame/frame_info types; file handler uses UTF-8; logger has `propagate=False`.

## Conventions and recent work

- **Install**: `pip install -e .` from repo root (or `pip install -e ".[dev]"` for tests, lint, and security). `setup.py` maps `package_dir={"dnp3py": "."}` and excludes the `tests` package from installation; version is read from `__init__.py`. Dev extras: pytest, pytest-cov, bandit, ruff, pyright. Config for bandit, ruff, and pyright lives in `pyproject.toml`. `dnp3py` is the top-level package. Subpackages use relative imports; public API is declared via `__all__` in each `__init__.py`.
- **Git**: `.gitignore` covers bytecode, build/dist, `*.egg-info/`, venvs, IDE dirs, pytest/coverage and tool caches (e.g. `.ruff_cache/`, `.mypy_cache/`), `*.log`, and `.claude/settings.local.json`. The `dnp3py.egg-info/` directory is created by `pip install -e .` and is ignored; do not commit it.
- **Config**: `DNP3Config.validate()` normalizes and validates host, port, addresses (0-65519), timeouts (float, positive), max_frame_size (1-250), max_apdu_size (1-65536), poll intervals (≥0), and log_level (DEBUG/INFO/WARNING/ERROR/CRITICAL); it coerces numeric fields and is called when creating a `DNP3Master`. `IINFlags.from_bytes` validates iin1/iin2.
- **Objects**: Binary, analog, and counter modules validate input length and value ranges in `from_bytes`/`to_bytes` and in `parse_*`; invalid data raises clear `ValueError` or `TypeError`. Analog (`objects/analog.py`) validates `data` type, `index` ≥ 0, `variation` range (1–6 or 1–4), and value ranges; `AnalogOutputCommand.create()` and `parse_analog_inputs`/`parse_analog_outputs` validate their arguments.
- **Layers**: Data Link validates addresses in `build_frame`, `build_request_link_status`, and `build_reset_link`; frame length and CRCs are validated on parse. Transport validates APDU length and `max_payload` in `segment()`, segment size in `from_bytes()`, and header in `parse_header()`; reassembly enforces sequence, size limit, and timeout. Application validates `ObjectHeader` (group/variation/qualifier and range/count) in `to_bytes()` and offset in `from_bytes()`; `build_confirm()` and `build_read_request()` validate sequence and group/variation/start/stop.
- **Exceptions**: All DNP3 exceptions inherit from `DNP3Error`; subclasses expose optional context (e.g. `DNP3CommunicationError.host`/`port`, `DNP3TimeoutError.timeout_seconds`, `DNP3CRCError.expected_crc`/`actual_crc`, `DNP3ObjectError.group`/`variation`). Defined in `core/exceptions.py` with `__all__`; top-level `dnp3py` exports the five most common; `DNP3FrameError`, `DNP3ObjectError`, `DNP3ControlError` from `dnp3py.core`.
- **Security**: No `eval`, `exec`, untrusted `__import__`, or `pickle.loads` on network data; parsing is binary-only. Bandit is run in CI; see README **Security** section for reporting.

## Testing, lint, and CI

- **Unit tests**: `pytest tests/ -v` from project root (with dnp3py installed).
- **Lint**: `ruff check .` and `ruff format --check .` (config in `pyproject.toml`; target py39, line-length 100).
- **Security**: `bandit -r . -c pyproject.toml -x tests,.venv,venv` (excludes tests; intentional try/except/pass in `core/master.py` are marked with `# nosec B110`).
- **Type check** (optional): `pyright` (requires `reportMissingImports = false` in pyproject when package is not installed in the env).
- **Local check** (full pass before push):  
  `pytest tests/ -q && ruff check . && ruff format --check . && bandit -r . -c pyproject.toml -x tests,.venv,venv`
- **CI** (`.github/workflows/ci.yml`): On push/PR to `main` or `master`, runs **test** (pytest on Python 3.9–3.12), **lint** (ruff check + format), and **security** (bandit).
- **Live test**: Edit `test_connection.py` (host, port, outstation address) and run `python test_connection.py`.
- **Examples**: `examples/basic_usage.py` (interactive), `examples/async_example.py` (background polling). Examples assume `pip install -e .`; no `sys.path` hacks.

## References

- IEEE Std 1815 (DNP3)
- [DNP Users Group](https://www.dnp.org/)
- [OpenDNP3](https://github.com/automatak/dnp3) (reference implementation)
