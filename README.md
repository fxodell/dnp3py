# DNP3 Driver for Python

A pure Python implementation of the DNP3 (Distributed Network Protocol 3) protocol for SCADA communications over TCP/IP.

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

## Installation

```bash
# Clone or copy the pydnp3 directory to your project
pip install -e pydnp3/
```

Or simply add the pydnp3 directory to your Python path.

## Quick Start

```python
from pydnp3 import DNP3Master, DNP3Config

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

## Architecture

```
pydnp3/
├── __init__.py           # Package exports
├── core/
│   ├── master.py         # DNP3Master class (main interface)
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
│   └── async_example.py  # Async/threading example
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

```python
from pydnp3 import (
    DNP3Error,
    DNP3CommunicationError,
    DNP3TimeoutError,
    DNP3ProtocolError,
    DNP3CRCError,
)

try:
    with master.connect():
        result = master.integrity_poll()
except DNP3TimeoutError:
    print("Communication timeout")
except DNP3CommunicationError as e:
    print(f"Connection failed: {e}")
except DNP3CRCError:
    print("CRC validation failed")
except DNP3Error as e:
    print(f"DNP3 error: {e}")
```

## Running Tests

```bash
cd pydnp3
pytest tests/ -v
```

## References

- IEEE Std 1815 - DNP3 Standard
- [DNP Users Group](https://www.dnp.org/)
- [DNP3 Protocol Overview](https://www.trianglemicroworks.com/docs/default-source/referenced-documents/DNP3_Overview.pdf)

## License

This implementation is provided as-is for educational and development purposes.

## Disclaimer

This is a reference implementation. For production SCADA systems, consider using certified DNP3 libraries such as:
- [OpenDNP3](https://github.com/automatak/dnp3)
- [pydnp3](https://github.com/ChargePoint/pydnp3)
