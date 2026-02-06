"""Core DNP3 driver components.

This package provides:
- DNP3Master: main API (thread-safe, use connect() or open()/close())
- DNP3Config: configuration (validate() called on master init)
- PollResult: return type of integrity_poll() and read_class()
- DNP3 exception hierarchy: DNP3Error, DNP3CommunicationError, DNP3TimeoutError,
  DNP3ProtocolError, DNP3CRCError, DNP3FrameError, DNP3ObjectError, DNP3ControlError

Use __all__ as the canonical list of exported names.
"""

from .config import DNP3Config
from .exceptions import (
    DNP3CommunicationError,
    DNP3ControlError,
    DNP3CRCError,
    DNP3Error,
    DNP3FrameError,
    DNP3ObjectError,
    DNP3ProtocolError,
    DNP3TimeoutError,
)
from .master import DNP3Master, PollResult

__all__ = [
    "DNP3Config",
    "DNP3ControlError",
    "DNP3CommunicationError",
    "DNP3CRCError",
    "DNP3Error",
    "DNP3FrameError",
    "DNP3Master",
    "DNP3ObjectError",
    "DNP3ProtocolError",
    "PollResult",
    "DNP3TimeoutError",
]
