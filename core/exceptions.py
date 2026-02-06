"""DNP3 driver exception classes.

All DNP3 exceptions inherit from DNP3Error. Catch DNP3Error to handle any
driver or protocol error. Use specific subclasses for finer-grained handling
or to access optional context attributes.

Exception hierarchy and optional context:
- DNP3Error: base (no context)
- DNP3CommunicationError: host, port
- DNP3TimeoutError: timeout_seconds
- DNP3ProtocolError: function_code, iin
- DNP3CRCError: expected_crc, actual_crc
- DNP3FrameError: (no context)
- DNP3ObjectError: group, variation
- DNP3ControlError: status_code (control/CROB/AOB failures)
"""

from typing import Optional

__all__ = [
    "DNP3Error",
    "DNP3CommunicationError",
    "DNP3TimeoutError",
    "DNP3ProtocolError",
    "DNP3CRCError",
    "DNP3FrameError",
    "DNP3ObjectError",
    "DNP3ControlError",
]


class DNP3Error(Exception):
    """Base exception for all DNP3-related errors."""

    pass


class DNP3CommunicationError(DNP3Error):
    """Raised when communication with the outstation fails (connect, send, receive)."""

    def __init__(
        self,
        message: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.host = host
        self.port = port


class DNP3TimeoutError(DNP3Error):
    """Raised when a response or connection timeout occurs."""

    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.timeout_seconds = timeout_seconds


class DNP3ProtocolError(DNP3Error):
    """Raised when a protocol-level error is detected (invalid response, etc.)."""

    def __init__(
        self,
        message: str,
        function_code: Optional[int] = None,
        iin: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.function_code = function_code
        self.iin = iin


class DNP3CRCError(DNP3Error):
    """Raised when CRC validation fails on a frame or block."""

    def __init__(
        self,
        message: str,
        expected_crc: Optional[int] = None,
        actual_crc: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.expected_crc = expected_crc
        self.actual_crc = actual_crc


class DNP3FrameError(DNP3Error):
    """Raised when frame parsing or construction fails (format, length, segment)."""

    pass


class DNP3ObjectError(DNP3Error):
    """Raised when object parsing or construction fails (header, qualifier, data)."""

    def __init__(
        self,
        message: str,
        group: Optional[int] = None,
        variation: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.group = group
        self.variation = variation


class DNP3ControlError(DNP3Error):
    """Raised when a control operation fails (e.g. CROB/AOB status not success)."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
