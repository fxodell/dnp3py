"""DNP3 driver exception classes."""


class DNP3Error(Exception):
    """Base exception for all DNP3-related errors."""

    pass


class DNP3CommunicationError(DNP3Error):
    """Raised when communication with the outstation fails."""

    def __init__(self, message: str, host: str = None, port: int = None):
        self.host = host
        self.port = port
        super().__init__(message)


class DNP3TimeoutError(DNP3Error):
    """Raised when a response timeout occurs."""

    def __init__(self, message: str, timeout_seconds: float = None):
        self.timeout_seconds = timeout_seconds
        super().__init__(message)


class DNP3ProtocolError(DNP3Error):
    """Raised when a protocol-level error is detected."""

    def __init__(self, message: str, function_code: int = None, iin: int = None):
        self.function_code = function_code
        self.iin = iin
        super().__init__(message)


class DNP3CRCError(DNP3Error):
    """Raised when CRC validation fails."""

    def __init__(self, message: str, expected_crc: int = None, actual_crc: int = None):
        self.expected_crc = expected_crc
        self.actual_crc = actual_crc
        super().__init__(message)


class DNP3FrameError(DNP3Error):
    """Raised when frame parsing or construction fails."""

    pass


class DNP3ObjectError(DNP3Error):
    """Raised when object parsing or construction fails."""

    def __init__(self, message: str, group: int = None, variation: int = None):
        self.group = group
        self.variation = variation
        super().__init__(message)


class DNP3ControlError(DNP3Error):
    """Raised when a control operation fails."""

    def __init__(self, message: str, status_code: int = None):
        self.status_code = status_code
        super().__init__(message)
