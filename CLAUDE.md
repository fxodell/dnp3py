# CLAUDE.md - AI Assistant Guide for pydnp3

## Project Overview

**pydnp3** is a pure Python implementation of the DNP3 (Distributed Network Protocol 3) protocol for SCADA communications over TCP/IP. It implements master station functionality to communicate with DNP3 outstations.

- **Package Name**: `dnp3_driver`
- **Version**: 1.0.0
- **Python Support**: 3.9, 3.10, 3.11, 3.12
- **Dependencies**: None (pure Python, standard library only)
- **Dev Dependencies**: pytest>=7.0, pytest-cov>=4.0

## Repository Structure

```
pydnp3/
├── __init__.py           # Package exports (DNP3Master, DNP3Config, exceptions)
├── setup.py              # Package configuration (setuptools)
├── README.md             # Project documentation
├── CLAUDE.md             # This file
├── .gitignore            # Git ignore patterns
│
├── core/                 # Core protocol components
│   ├── master.py         # DNP3Master class - main API interface
│   ├── config.py         # DNP3Config, enums (ControlCode, AppLayerFunction, etc.)
│   └── exceptions.py     # Exception hierarchy (DNP3Error and subclasses)
│
├── layers/               # Protocol layer implementations
│   ├── datalink.py       # Data Link Layer - FT3 frames, CRC
│   ├── transport.py      # Transport Layer - segmentation/reassembly
│   └── application.py    # Application Layer - requests/responses
│
├── objects/              # DNP3 data object definitions
│   ├── binary.py         # Binary Input/Output (Groups 1, 2, 10, 12)
│   ├── analog.py         # Analog Input/Output (Groups 30, 32, 40, 41)
│   ├── counter.py        # Counter objects (Groups 20, 22)
│   └── groups.py         # ObjectGroup and ObjectVariation enums
│
├── utils/                # Utility modules
│   ├── crc.py            # CRC-16 implementation (DNP3 polynomial)
│   └── logging.py        # Logging configuration utilities
│
├── examples/             # Usage examples
│   ├── basic_usage.py    # Basic read/write/control examples
│   └── async_example.py  # Threading-based async patterns
│
└── tests/                # Unit tests (pytest)
    ├── test_crc.py       # CRC calculation tests
    ├── test_datalink.py  # Data Link Layer tests
    ├── test_transport.py # Transport Layer tests
    ├── test_application.py # Application Layer tests
    └── test_objects.py   # Object parsing tests
```

## Quick Reference

### Common Commands

```bash
# Install in development mode
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ -v --cov=dnp3_driver --cov-report=html

# Run specific test file
pytest tests/test_crc.py -v

# Run specific test class or method
pytest tests/test_crc.py::TestCRC16DNP3::test_known_value -v
```

### Import Patterns

```python
# Main imports (from package root)
from dnp3_driver import DNP3Master, DNP3Config
from dnp3_driver import DNP3Error, DNP3TimeoutError, DNP3CRCError

# Specific module imports
from dnp3_driver.core.config import ControlCode, AppLayerFunction, QualifierCode
from dnp3_driver.core.exceptions import DNP3ProtocolError, DNP3ControlError
from dnp3_driver.objects.binary import BinaryInput, BinaryOutput
from dnp3_driver.objects.analog import AnalogInput, AnalogOutput
from dnp3_driver.utils.crc import CRC16DNP3
```

## Architecture

### Protocol Stack

The implementation follows the DNP3 layered architecture:

```
┌─────────────────────────────────┐
│    Application Layer            │  Request/response formatting
│    (layers/application.py)      │  Function codes, object headers
├─────────────────────────────────┤
│    Transport Layer              │  Message segmentation
│    (layers/transport.py)        │  FIR/FIN flags, sequence numbers
├─────────────────────────────────┤
│    Data Link Layer              │  FT3 frame format
│    (layers/datalink.py)         │  CRC-16 error checking
├─────────────────────────────────┤
│    TCP/IP Socket                │  Network communication
└─────────────────────────────────┘
```

### Key Classes

| Class | Location | Purpose |
|-------|----------|---------|
| `DNP3Master` | `core/master.py` | Main API interface for master station |
| `DNP3Config` | `core/config.py` | Configuration dataclass with all settings |
| `DataLinkFrame` | `layers/datalink.py` | Frame construction and parsing |
| `TransportLayer` | `layers/transport.py` | Segmentation and reassembly |
| `ApplicationLayer` | `layers/application.py` | Request/response handling |
| `CRC16DNP3` | `utils/crc.py` | CRC-16 calculation |

## Code Conventions

### Naming

- **Classes**: PascalCase (`DNP3Master`, `BinaryInput`, `DataLinkFrame`)
- **Functions/Methods**: snake_case (`build_frame`, `parse_response`, `integrity_poll`)
- **Constants**: UPPER_CASE (`MAX_USER_DATA`, `START_BYTES`, `FIR_FLAG`)
- **Private members**: Leading underscore (`_socket`, `_rx_buffer`, `_sequence`)
- **Module variables**: snake_case (`crc_table`, `object_sizes`)

### Type Hints

All code uses type hints from the `typing` module:

```python
from typing import Optional, List, Union, Tuple, Callable

def parse_response(data: bytes) -> Optional[List[BinaryInput]]:
    ...

def build_frame(self, destination: int, source: int,
                function: LinkLayerFunction, user_data: bytes = b"") -> bytes:
    ...
```

### Dataclasses

Use `@dataclass` for data structures:

```python
from dataclasses import dataclass, field

@dataclass
class DNP3Config:
    host: str = "127.0.0.1"
    port: int = 20000
    master_address: int = 1
    ...
```

### Enums

Use `IntEnum` for protocol constants:

```python
from enum import IntEnum

class ControlCode(IntEnum):
    NUL = 0x00
    PULSE_ON = 0x01
    LATCH_ON = 0x03
```

### Exception Handling

Custom exceptions inherit from `DNP3Error`:

```python
class DNP3Error(Exception):
    """Base exception for all DNP3-related errors."""
    pass

class DNP3CRCError(DNP3Error):
    def __init__(self, message: str, expected_crc: int = None, actual_crc: int = None):
        self.expected_crc = expected_crc
        self.actual_crc = actual_crc
        super().__init__(message)
```

### Docstrings

Use triple-quoted docstrings for all public classes and methods:

```python
def integrity_poll(self) -> PollResult:
    """
    Perform an integrity poll (Class 0 read).

    Returns all static data from the outstation including binary inputs,
    analog inputs, counters, and their current values.

    Returns:
        PollResult containing all data points

    Raises:
        DNP3TimeoutError: If no response within timeout
        DNP3CommunicationError: If connection fails
    """
```

## Testing Conventions

### Test Structure

- One test file per module: `test_<module>.py`
- Test classes named `Test<ClassName>`
- Test methods named `test_<behavior>`

```python
"""Tests for DNP3 CRC-16 calculation."""

import pytest
from dnp3_driver.utils.crc import CRC16DNP3

class TestCRC16DNP3:
    """Tests for CRC16DNP3 class."""

    def test_empty_data(self):
        """Test CRC of empty data."""
        crc = CRC16DNP3.calculate(b"")
        assert crc == 0xFFFF

    def test_verify_correct_crc(self):
        """Test verification of correct CRC."""
        data = b"hello world"
        crc = CRC16DNP3.calculate(data)
        assert CRC16DNP3.verify(data, crc) is True
```

### Test Patterns

- Use `pytest` fixtures for common setup
- Parametric testing for multiple variations
- Known value tests for protocol compliance
- Edge case coverage (empty data, max sizes, boundary conditions)

## Protocol-Specific Notes

### DNP3 Addressing

- Valid addresses: 0-65519
- Address 65520-65535 reserved for broadcast
- Master typically uses address 1
- Outstations typically use addresses 10+

### Frame Structure

- Start bytes: `0x05 0x64`
- Max user data per frame: 250 bytes
- CRC-16 calculated every 16 bytes (block CRC)
- Little-endian byte ordering

### Object Groups

| Group | Type | Description |
|-------|------|-------------|
| 1, 2 | Binary Input | Static and event |
| 10, 12 | Binary Output | Static and CROB |
| 20, 22 | Counter | Static and event |
| 30, 32 | Analog Input | Static and event |
| 40, 41 | Analog Output | Static and command |
| 60 | Class | Class 0/1/2/3 data |

### Control Operations

1. **Direct Operate**: Immediate execution
2. **Select-Before-Operate (SBO)**: Two-step safety mechanism
3. **Pulse**: Timed on/off control with count

## Development Guidelines

### Adding New Features

1. Follow the layered architecture - changes should respect layer boundaries
2. Add appropriate exceptions to `core/exceptions.py`
3. Update `__init__.py` exports if adding public API
4. Write tests for all new functionality
5. Use type hints consistently

### Modifying Protocol Implementation

1. Reference IEEE Std 1815 for protocol compliance
2. Test against real DNP3 devices when possible
3. Maintain backward compatibility for existing API
4. Document any deviations from the standard

### Error Handling

- Always use specific exception types
- Include context information in exceptions
- Clean up resources (sockets, buffers) on errors
- Use context managers for connection lifecycle

## Important Caveats

1. **Production Use**: This is a reference implementation. For production SCADA systems, consider certified libraries like OpenDNP3 or the ChargePoint pydnp3.

2. **Threading**: The `DNP3Master` class uses a lock for thread safety on `_send_request`. Concurrent operations from multiple threads are serialized.

3. **No Outstation Mode**: This implementation only supports master station functionality.

4. **TCP Only**: Currently supports TCP/IP communication only, not serial.

## Useful Patterns

### Context Manager for Connection

```python
master = DNP3Master(config)
with master.connect():
    result = master.integrity_poll()
    # Connection automatically closed on exit
```

### Continuous Polling

```python
with master.connect():
    while True:
        result = master.read_class(class_id=1)  # Event data
        process_events(result)
        time.sleep(config.class_1_poll_interval)
```

### Control with Status Check

```python
try:
    success = master.direct_operate_binary(index=0, value=True)
    if not success:
        logger.warning("Control operation not acknowledged")
except DNP3ControlError as e:
    logger.error(f"Control failed with status: {e.status_code}")
```
