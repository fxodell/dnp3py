# nfm-dnp3 (dnp3py)

A pure Python implementation of the DNP3 (Distributed Network Protocol 3) protocol for SCADA communications over TCP/IP. Install from PyPI as **nfm-dnp3**; import in Python as **dnp3py**.

## Overview

This driver implements the DNP3 protocol stack to communicate with DNP3 outstations (slaves) as a master station. It supports reading data points, controlling outputs, and handling events.

## Features

- **Full Protocol Stack**: Implements Data Link, Transport, and Application layers
- **TCP/IP Communication**: Connect to DNP3 devices over IP networks
- **Data Point Support**:
  - Binary Inputs (Group 1, 2)
  - Binary Outputs (Group 10, 12)
  - Analog Inputs (Group 30, 32)
  - Analog Outputs (Group 40, 41)
  - Counters (Group 20, 22)
- **Control Operations**:
  - Direct Operate
  - Select-Before-Operate (SBO)
  - Pulse control
- **Class-Based Polling**: Support for Class 0, 1, 2, 3 data
- **CRC-16 Error Detection**: Compliant with DNP3 CRC polynomial
- **Thread-Safe**: `DNP3Master` supports concurrent use (open/close/requests protected by a lock)

## Requirements

- Python 3.9+

## Installation

```bash
# Clone the repository
git clone https://github.com/fxodell/dnp3py.git
cd dnp3py

# Install from PyPI
pip install nfm-dnp3

# Or install in development mode from source
pip install -e .
```

After installation, use `from dnp3py import ...` from any directory.

## Quick Start

```python
from dnp3py import DNP3Master, DNP3Config

# Configure connection
config = DNP3Config(
    host="192.168.1.100",     # Outstation IP
    port=20000,               # DNP3 port (default: 20000)
    master_address=1,         # Master address
    outstation_address=10,    # Outstation address
)

# Create master instance
master = DNP3Master(config)

# Connect and read data
with master.connect():
    # Integrity poll - read all data
    result = master.integrity_poll()

    if result.success:
        print(f"Binary Inputs: {result.binary_inputs}")
        print(f"Analog Inputs: {result.analog_inputs}")
        print(f"Counters: {result.counters}")

    # Read specific points
    binary_inputs = master.read_binary_inputs(0, 9)
    analog_inputs = master.read_analog_inputs(0, 4)

    # Control a binary output
    master.direct_operate_binary(0, value=True)  # Turn ON
    master.direct_operate_binary(0, value=False)  # Turn OFF

    # Control an analog output
    master.direct_operate_analog(0, value=50.0)
```

**Run the interactive examples** (requires `nfm-dnp3` installed):

```bash
python examples/basic_usage.py
```

## Architecture

```
dnp3py/
├── __init__.py           # Package exports
├── setup.py              # Package setup (pip install -e .)
├── test_connection.py    # Quick connection test (edit host/port/address)
├── core/
│   ├── master.py         # DNP3Master (main interface; thread-safe, connect() context manager)
│   ├── config.py         # Configuration and protocol constants
│   └── exceptions.py     # Custom exceptions
├── layers/
│   ├── datalink.py       # Data Link Layer (frames, CRC)
│   ├── transport.py      # Transport Layer (segmentation)
│   └── application.py    # Application Layer (requests/responses)
├── objects/
│   ├── binary.py         # Binary I/O objects
│   ├── analog.py         # Analog I/O objects
│   ├── counter.py        # Counter objects
│   └── groups.py         # Object group definitions
├── utils/
│   ├── crc.py            # CRC-16 calculation
│   └── logging.py        # Logging utilities
├── examples/
│   ├── basic_usage.py    # Basic usage examples
│   └── async_example.py   # Async/threading example
├── docs/                 # Documentation
└── tests/                # Unit tests
```

## Protocol Layers

### Data Link Layer
- FT3 frame format with 0x0564 start bytes
- Source and destination addressing (0-65519)
- CRC-16 error checking every 16 bytes
- Maximum frame size: 292 bytes (250 bytes user data)

### Transport Layer
- Message segmentation/reassembly
- 1-byte transport header with sequence numbering
- FIR (First) and FIN (Final) segment flags
- Maximum segment payload: 249 bytes

### Application Layer
- Request/Response message formatting
- Function codes (READ, WRITE, SELECT, OPERATE, etc.)
- Object headers with qualifiers
- Internal Indications (IIN) handling

## Configuration Options

`DNP3Config` validates and normalizes values when you create a `DNP3Master` (e.g. host trimmed, port/addresses coerced to int). Invalid settings raise `ValueError` or `TypeError`.

```python
config = DNP3Config(
    # Network
    host="192.168.1.100",
    port=20000,

    # Addressing
    master_address=1,
    outstation_address=10,

    # Timeouts (seconds)
    response_timeout=5.0,
    connection_timeout=10.0,
    select_timeout=10.0,   # SBO: time between SELECT and OPERATE

    # Retries
    max_retries=3,
    retry_delay=1.0,

    # Data Link
    confirm_required=True,
    max_frame_size=250,

    # Logging
    log_level="INFO",
    log_raw_frames=False,
)
```

## Control Operations

### Direct Operate
Immediately executes the control command:

```python
# Turn output ON
master.direct_operate_binary(index=0, value=True)

# Turn output OFF
master.direct_operate_binary(index=0, value=False)

# Set analog setpoint
master.direct_operate_analog(index=0, value=50.0)
```

### Select-Before-Operate (SBO)
Two-step control for safety-critical operations:

```python
# SELECT then OPERATE
master.select_operate_binary(index=0, value=True)
```

### Pulse Control
Generate timed pulses on outputs:

```python
# Pulse ON for 500ms, 3 times
master.pulse_binary(
    index=0,
    on_time=500,    # milliseconds
    off_time=500,   # milliseconds
    count=3,
    pulse_on=True,
)
```

## Exception Handling

All DNP3 exceptions inherit from `DNP3Error`. Catch it for any driver error, or use specific types for context (e.g. `host`/`port` on `DNP3CommunicationError`, `timeout_seconds` on `DNP3TimeoutError`).

```python
from dnp3py import (
    DNP3Error,
    DNP3CommunicationError,
    DNP3TimeoutError,
    DNP3ProtocolError,
    DNP3CRCError,
)

try:
    with master.connect():
        result = master.integrity_poll()
except DNP3TimeoutError as e:
    print(f"Timeout after {e.timeout_seconds}s")
except DNP3CommunicationError as e:
    print(f"Connection failed: {e} (host={e.host}, port={e.port})")
except DNP3CRCError:
    print("CRC validation failed")
except DNP3Error as e:
    print(f"DNP3 error: {e}")
```

For frame, object, or control-specific errors, use `from dnp3py.core import DNP3FrameError, DNP3ObjectError, DNP3ControlError`.

## Running Tests

From the project root (with `nfm-dnp3` or `pip install -e .`):

```bash
pytest tests/ -v
```

To quickly test a live outstation, edit `test_connection.py` with your host, port, and outstation address, then run:

```bash
python test_connection.py
```

**Local check** (tests + lint + security, same as CI):

```bash
pytest tests/ -q && ruff check . && ruff format --check . && bandit -r . -c pyproject.toml -x tests,.venv,venv
```

## References

- IEEE Std 1815 - DNP3 Standard
- [DNP Users Group](https://www.dnp.org/)
- [DNP3 Protocol Overview](https://www.trianglemicroworks.com/docs/default-source/referenced-documents/DNP3_Overview.pdf)

## Development

- **Setup**: `setup.py` uses `package_dir={"dnp3py": "."}` (repo root is the package); `find_packages()` excludes `tests` so the test suite is not installed. Version is read from `__init__.py` as the single source of truth. Long description is taken from `README.md`. Install dev dependencies with `pip install -e ".[dev]"` for pytest, pytest-cov, bandit, ruff, and pyright.
- **Commands**: Run tests: `pytest tests/ -v`. Lint: `ruff check .` and `ruff format --check .`. Security: `bandit -r . -c pyproject.toml`. Type check: `pyright` (optional; requires `reportMissingImports = false` in pyproject until run from an env where `dnp3py` is installed).
- **Git**: `.gitignore` excludes bytecode (`__pycache__/`, `*.pyc`), build artifacts (`build/`, `dist/`, `*.egg-info/`), virtual envs (`.venv/`, `venv/`), IDE/editor dirs (`.idea/`, `.vscode/`), test/cache (`.pytest_cache/`, `.coverage`, `htmlcov/`), tool caches (`.mypy_cache/`, `.ruff_cache/`), `*.log`, and `.claude/settings.local.json`; OS cruft (`.DS_Store`) is ignored. After `pip install -e .`, the `dnp3py.egg-info/` directory appears in the repo root; it is generated metadata and is correctly ignored—do not commit it.
- **Package layout**: Install with `pip install -e .` from the repo root; `dnp3py` is the top-level package. The root `__init__.py` exports `DNP3Master`, `DNP3Config`, the exception classes (`DNP3Error`, `DNP3CommunicationError`, `DNP3TimeoutError`, `DNP3ProtocolError`, `DNP3CRCError`), and `__version__` via `__all__`. Subpackages use relative or absolute imports; each `__init__.py` exposes a public API via `__all__`.
- **Core package**: `core/__init__.py` re-exports `DNP3Master`, `DNP3Config`, `PollResult` (return type of `integrity_poll()` and `read_class()`), and all eight DNP3 exception classes. The top-level `dnp3py` package exports only the five most common exceptions; use `from dnp3py.core import PollResult, DNP3FrameError`, etc., when needed.
- **Master**: `core/master.py` implements `DNP3Master`; it coordinates Data Link, Transport, and Application layers and is thread-safe (open/close and request/response use a single lock). Use the `connect()` context manager or `open()`/`close()` for connection life cycle. `DNP3CommunicationError` is raised with `host` and `port` set from config when send/receive or connection fails, for easier debugging.
- **Config**: `core/config.py` defines `DNP3Config` and protocol enums (LinkLayerFunction, AppLayerFunction, QualifierCode, ControlCode, ControlStatus, IINFlags). `DNP3Config.validate()` normalizes and validates all fields: host (non-empty string), port (1-65535), master/outstation addresses (0-65519), timeouts and retry_delay (coerced to float, positive or ≥0), max_frame_size (1-250), max_apdu_size (1-65536), poll intervals (≥0), and log_level (DEBUG/INFO/WARNING/ERROR/CRITICAL). `IINFlags.from_bytes(iin1, iin2)` validates that iin1/iin2 are coercible to int. Called automatically when creating a `DNP3Master`.
- **Objects**: Binary, analog, and counter modules validate input length and value ranges in `from_bytes`/`to_bytes` and in `parse_*` (e.g. `count`/`start_index` ≥ 0); invalid data raises clear `ValueError`s or `TypeError`. Analog (`objects/analog.py`) additionally validates `data` type (bytes/bytearray), `index` ≥ 0, and `variation` in valid range (1–6 for AnalogInput, 1–4 for AnalogOutput/AnalogOutputCommand) in `from_bytes`/`to_bytes`/`create()` and `parse_analog_inputs`/`parse_analog_outputs`.
- **Objects package**: `objects/__init__.py` re-exports data types (BinaryInput, AnalogInput, Counter, etc.), `ObjectGroup`, `ObjectVariation`, `get_object_size`, and `get_group_name`; parse functions (`parse_binary_inputs`, `parse_analog_inputs`, etc.) are in the binary, analog, and counter submodules.
- **Groups**: `objects/groups.py` defines `ObjectGroup`, `ObjectVariation`, `OBJECT_SIZES`, `get_object_size()`, and `get_group_name()` for protocol and parsing use.
- **Layers**: `layers/__init__.py` re-exports `DataLinkLayer`, `TransportLayer`, and `ApplicationLayer`; frame, segment, and request/response types live in the datalink, transport, and application submodules. Data Link (`layers/datalink.py`) validates addresses in `build_frame`, `build_request_link_status`, and `build_reset_link`; `calculate_frame_size` validates the length byte; frame parsing checks CRCs and length. Transport (`layers/transport.py`) validates APDU length (≤ MAX_MESSAGE_SIZE) and `max_payload` (1..MAX_SEGMENT_PAYLOAD) in `segment()`; `TransportSegment.from_bytes` rejects oversized segments; `parse_header()` validates header byte 0-255; reassembly enforces sequence, size limit, and timeout. Application (`layers/application.py`) validates `ObjectHeader` group/variation/qualifier (0-255) and range/count per qualifier in `to_bytes()`; `ObjectHeader.from_bytes()` validates offset and range; `ApplicationRequest` validates sequence and function; `build_confirm()` and `build_read_request()` validate sequence (0-15) and group/variation/start/stop.
- **Utils**: `utils/__init__.py` re-exports `CRC16DNP3`, `calculate_frame_crc`, `setup_logging`, `get_logger`, `log_frame`, and `log_parsed_frame`. `utils/crc.py` provides DNP3 CRC-16 (polynomial 0x3D65, reflected 0xA6BC, final XOR 0xFFFF); `CRC16DNP3.calculate()` and `calculate_frame_crc()` validate bytes/bytearray; `verify_bytes()` validates 2-byte CRC. `utils/logging.py` validates level (DEBUG/INFO/WARNING/ERROR/CRITICAL), uses UTF-8 for file output, sets `propagate=False`; `log_frame()` and `log_parsed_frame()` validate frame/frame_info types.
- **Exceptions**: `core/exceptions.py` defines the hierarchy: `DNP3Error` (base); `DNP3CommunicationError` (host, port), `DNP3TimeoutError` (timeout_seconds), `DNP3ProtocolError` (function_code, iin), `DNP3CRCError` (expected_crc, actual_crc), `DNP3FrameError`, `DNP3ObjectError` (group, variation), `DNP3ControlError` (status_code). The top-level `dnp3py` package exports the first five; `DNP3FrameError`, `DNP3ObjectError`, and `DNP3ControlError` are available from `dnp3py.core`. All use `Optional` for context attributes.
- **Publishing to PyPI**: This project is published as **nfm-dnp3** on PyPI (Trusted Publisher from GitHub Actions). (1) Bump version in `__init__.py`, (2) tag and push (e.g. `git tag v1.0.1 && git push origin v1.0.1`); the publish workflow uploads to PyPI. For manual upload: `pip install build twine`, `python -m build`, then `twine upload dist/*` with PyPI token.

## Security

- **No unsafe patterns**: The codebase does not use `eval`, `exec`, `__import__` with untrusted input, or `pickle.loads` on network data. Protocol parsing is binary-only; no code execution from DNP3 payloads.
- **Checks**: Run `bandit -r . -c pyproject.toml` (excludes `tests/`) to scan for common issues. CI runs bandit on every push/PR.
- **Reporting**: If you find a security concern, please report it privately (e.g. via the repository's security policy or maintainer contact) rather than in a public issue.

## License

This implementation is provided as-is for educational and development purposes.

## Disclaimer

This is a reference implementation. For production SCADA systems, consider evaluation of certified DNP3 stacks such as [OpenDNP3](https://github.com/automatak/dnp3).
