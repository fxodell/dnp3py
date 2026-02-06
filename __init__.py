"""
DNP3 Driver - A Python implementation for DNP3 protocol communication over IP.

This driver implements the DNP3 (Distributed Network Protocol 3) protocol
for SCADA communications, supporting master station functionality to communicate
with DNP3 outstations over TCP/IP.

Protocol Structure:
    - Data Link Layer: Frame format with CRC-16 error checking
    - Transport Layer: Message segmentation and reassembly
    - Application Layer: Function codes and data object handling

Supported Features:
    - Binary Inputs (Group 1, 2)
    - Binary Outputs (Group 10, 12)
    - Analog Inputs (Group 30, 32)
    - Analog Outputs (Group 40, 41)
    - Counters (Group 20, 22)
    - Class data polling (Class 0, 1, 2, 3)
    - Select-Before-Operate (SBO) control
    - Direct Operate control
    - Time synchronization
    - Unsolicited responses

Public API (import from dnp3py):
    DNP3Master, DNP3Config, DNP3Error, DNP3CommunicationError,
    DNP3TimeoutError, DNP3ProtocolError, DNP3CRCError, __version__

References:
    - IEEE Std 1815 (DNP3 Standard)
    - DNP3 Technical Bulletin TB2004-001
"""

from dnp3py.core.config import DNP3Config
from dnp3py.core.exceptions import (
    DNP3CommunicationError,
    DNP3CRCError,
    DNP3Error,
    DNP3ProtocolError,
    DNP3TimeoutError,
)
from dnp3py.core.master import DNP3Master

__version__ = "1.0.1"
__author__ = "DNP3 Driver Development"

__all__ = [
    "DNP3CommunicationError",
    "DNP3Config",
    "DNP3CRCError",
    "DNP3Error",
    "DNP3Master",
    "DNP3ProtocolError",
    "DNP3TimeoutError",
    "__version__",
]
