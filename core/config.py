"""DNP3 driver configuration."""

from dataclasses import dataclass
from enum import IntEnum


class LinkLayerFunction(IntEnum):
    """Data Link Layer control function codes."""

    RESET_LINK = 0x40
    RESET_USER_PROCESS = 0x41
    TEST_LINK = 0x42
    USER_DATA_CONFIRMED = 0x43
    USER_DATA_UNCONFIRMED = 0x44
    REQUEST_LINK_STATUS = 0x49

    # Secondary (outstation) responses
    ACK = 0x00
    NACK = 0x01
    LINK_STATUS = 0x0B
    NOT_SUPPORTED = 0x0F


class AppLayerFunction(IntEnum):
    """Application Layer function codes (IEEE 1815)."""

    # Request function codes
    CONFIRM = 0x00
    READ = 0x01
    WRITE = 0x02
    SELECT = 0x03
    OPERATE = 0x04
    DIRECT_OPERATE = 0x05
    DIRECT_OPERATE_NO_ACK = 0x06
    IMMEDIATE_FREEZE = 0x07
    IMMEDIATE_FREEZE_NO_ACK = 0x08
    FREEZE_CLEAR = 0x09
    FREEZE_CLEAR_NO_ACK = 0x0A
    FREEZE_AT_TIME = 0x0B
    FREEZE_AT_TIME_NO_ACK = 0x0C
    COLD_RESTART = 0x0D
    WARM_RESTART = 0x0E
    INITIALIZE_DATA = 0x0F
    INITIALIZE_APPLICATION = 0x10
    START_APPLICATION = 0x11
    STOP_APPLICATION = 0x12
    SAVE_CONFIGURATION = 0x13
    ENABLE_UNSOLICITED = 0x14
    DISABLE_UNSOLICITED = 0x15
    ASSIGN_CLASS = 0x16
    DELAY_MEASURE = 0x17
    RECORD_CURRENT_TIME = 0x18
    OPEN_FILE = 0x19
    CLOSE_FILE = 0x1A
    DELETE_FILE = 0x1B
    GET_FILE_INFO = 0x1C
    AUTHENTICATE_FILE = 0x1D
    ABORT_FILE = 0x1E

    # Response function codes
    RESPONSE = 0x81
    UNSOLICITED_RESPONSE = 0x82
    AUTHENTICATION_RESPONSE = 0x83


class QualifierCode(IntEnum):
    """Object header qualifier codes."""

    # 8-bit index prefix codes
    UINT8_START_STOP = 0x00  # 8-bit start and stop indices
    UINT16_START_STOP = 0x01  # 16-bit start and stop indices
    ALL_OBJECTS = 0x06  # All objects (no range field)
    UINT8_COUNT = 0x07  # 8-bit single field count
    UINT16_COUNT = 0x08  # 16-bit single field count

    # With object prefix
    UINT8_COUNT_UINT8_INDEX = 0x17  # 8-bit count with 8-bit index prefix
    UINT8_COUNT_UINT16_INDEX = 0x28  # 8-bit count with 16-bit index prefix
    UINT16_COUNT_UINT16_INDEX = 0x29  # 16-bit count with 16-bit index prefix

    # Variable-sized objects
    FREE_FORMAT_UINT16_COUNT = 0x5B  # Free format with 16-bit count


class ControlCode(IntEnum):
    """Control Relay Output Block (CROB) control codes."""

    NUL = 0x00  # No operation
    PULSE_ON = 0x01  # Pulse on
    PULSE_OFF = 0x02  # Pulse off
    LATCH_ON = 0x03  # Latch on
    LATCH_OFF = 0x04  # Latch off

    # Queue flag (OR with above)
    QUEUE = 0x10

    # Clear flag (OR with above)
    CLEAR = 0x20

    # Trip/Close for switches
    TRIP_CLOSE_TRIP = 0x40
    TRIP_CLOSE_CLOSE = 0x80


class ControlStatus(IntEnum):
    """Control operation status codes."""

    SUCCESS = 0x00
    TIMEOUT = 0x01
    NO_SELECT = 0x02
    FORMAT_ERROR = 0x03
    NOT_SUPPORTED = 0x04
    ALREADY_ACTIVE = 0x05
    HARDWARE_ERROR = 0x06
    LOCAL = 0x07
    TOO_MANY_OBJS = 0x08
    NOT_AUTHORIZED = 0x09
    AUTOMATION_INHIBIT = 0x0A
    PROCESSING_LIMITED = 0x0B
    OUT_OF_RANGE = 0x0C
    NOT_PARTICIPATING = 0x7E
    UNDEFINED = 0x7F


@dataclass
class IINFlags:
    """Internal Indications (IIN) bit flags from outstation responses."""

    # First octet (IIN1)
    broadcast: bool = False  # Bit 0: Message was broadcast
    class_1_events: bool = False  # Bit 1: Class 1 events available
    class_2_events: bool = False  # Bit 2: Class 2 events available
    class_3_events: bool = False  # Bit 3: Class 3 events available
    need_time: bool = False  # Bit 4: Time sync required
    local_control: bool = False  # Bit 5: Some outputs in local mode
    device_trouble: bool = False  # Bit 6: Device trouble
    device_restart: bool = False  # Bit 7: Device has restarted

    # Second octet (IIN2)
    no_func_code_support: bool = False  # Bit 0: Function code not supported
    object_unknown: bool = False  # Bit 1: Requested objects unknown
    parameter_error: bool = False  # Bit 2: Parameters invalid
    event_buffer_overflow: bool = False  # Bit 3: Event buffer overflow
    already_executing: bool = False  # Bit 4: Operation already executing
    config_corrupt: bool = False  # Bit 5: Configuration corrupt
    reserved_2_6: bool = False  # Bit 6: Reserved
    reserved_2_7: bool = False  # Bit 7: Reserved

    @classmethod
    def from_bytes(cls, iin1: int, iin2: int) -> "IINFlags":
        """Parse IIN bytes into flags. Values are masked to 0-255.

        Raises:
            TypeError: If iin1 or iin2 is not coercible to int.
        """
        try:
            iin1 = int(iin1) & 0xFF
        except (TypeError, ValueError) as e:
            raise TypeError(f"IIN1 must be an integer (0-255), got {type(iin1).__name__}") from e
        try:
            iin2 = int(iin2) & 0xFF
        except (TypeError, ValueError) as e:
            raise TypeError(f"IIN2 must be an integer (0-255), got {type(iin2).__name__}") from e
        return cls(
            broadcast=(iin1 & 0x01) != 0,
            class_1_events=(iin1 & 0x02) != 0,
            class_2_events=(iin1 & 0x04) != 0,
            class_3_events=(iin1 & 0x08) != 0,
            need_time=(iin1 & 0x10) != 0,
            local_control=(iin1 & 0x20) != 0,
            device_trouble=(iin1 & 0x40) != 0,
            device_restart=(iin1 & 0x80) != 0,
            no_func_code_support=(iin2 & 0x01) != 0,
            object_unknown=(iin2 & 0x02) != 0,
            parameter_error=(iin2 & 0x04) != 0,
            event_buffer_overflow=(iin2 & 0x08) != 0,
            already_executing=(iin2 & 0x10) != 0,
            config_corrupt=(iin2 & 0x20) != 0,
            reserved_2_6=(iin2 & 0x40) != 0,
            reserved_2_7=(iin2 & 0x80) != 0,
        )

    def to_bytes(self) -> tuple[int, int]:
        """Convert flags to IIN bytes."""
        iin1 = (
            (0x01 if self.broadcast else 0)
            | (0x02 if self.class_1_events else 0)
            | (0x04 if self.class_2_events else 0)
            | (0x08 if self.class_3_events else 0)
            | (0x10 if self.need_time else 0)
            | (0x20 if self.local_control else 0)
            | (0x40 if self.device_trouble else 0)
            | (0x80 if self.device_restart else 0)
        )
        iin2 = (
            (0x01 if self.no_func_code_support else 0)
            | (0x02 if self.object_unknown else 0)
            | (0x04 if self.parameter_error else 0)
            | (0x08 if self.event_buffer_overflow else 0)
            | (0x10 if self.already_executing else 0)
            | (0x20 if self.config_corrupt else 0)
            | (0x40 if self.reserved_2_6 else 0)
            | (0x80 if self.reserved_2_7 else 0)
        )
        return iin1, iin2

    def has_errors(self) -> bool:
        """Check if any error flags are set."""
        return (
            self.no_func_code_support
            or self.object_unknown
            or self.parameter_error
            or self.config_corrupt
        )

    def has_reserved_bits(self) -> bool:
        """Check if any reserved IIN bits are set."""
        return self.reserved_2_6 or self.reserved_2_7


@dataclass
class DNP3Config:
    """Configuration for DNP3 master communication."""

    # Network settings
    host: str = "127.0.0.1"
    port: int = 20000

    # DNP3 addressing
    master_address: int = 1  # Master station address (0-65534)
    outstation_address: int = 10  # Outstation address (0-65534)

    # Timing settings (in seconds)
    response_timeout: float = 5.0
    connection_timeout: float = 10.0
    select_timeout: float = 10.0  # Time between SELECT and OPERATE

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0

    # Data link layer settings
    confirm_required: bool = True
    max_frame_size: int = 250  # Max user data per frame (protocol limit: 250)

    # Application layer settings
    max_apdu_size: int = 2048  # Max application layer PDU size
    enable_unsolicited: bool = True

    # Class polling intervals (in seconds, 0 = disabled)
    class_0_poll_interval: float = 60.0  # Integrity poll
    class_1_poll_interval: float = 5.0  # High priority events
    class_2_poll_interval: float = 10.0  # Medium priority events
    class_3_poll_interval: float = 30.0  # Low priority events

    # Logging
    log_level: str = "INFO"
    log_raw_frames: bool = False

    def validate(self) -> None:
        """Validate and normalize configuration values.

        DNP3 addressing rules:
        - Valid range: 0-65519 (0x0000-0xFFEF)
        - Reserved: 65520-65534 (0xFFF0-0xFFFE) for special purposes
        - Broadcast: 65535 (0xFFFF) - not valid for master/outstation addresses

        Raises:
            ValueError: If any value is out of range or invalid.
            TypeError: If host is not a string.
        """
        # Host: non-empty string (strip whitespace)
        if self.host is None or not isinstance(self.host, str):
            raise TypeError(
                f"Host must be a non-empty string, got {type(self.host).__name__ if self.host is not None else 'NoneType'}"
            )
        self.host = self.host.strip()
        if not self.host:
            raise ValueError("Host must be a non-empty string")

        # Port: integer 1-65535 (coerce from integral float if needed)
        try:
            port = int(self.port)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Port must be an integer, got {self.port!r}") from e
        if not 1 <= port <= 65535:
            raise ValueError(f"Port must be 1-65535, got {port}")
        self.port = port

        # DNP3 reserves addresses 65520-65535 for special purposes
        MAX_VALID_ADDRESS = 65519

        try:
            master_address = int(self.master_address)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Master address must be an integer, got {self.master_address!r}"
            ) from e
        if not 0 <= master_address <= MAX_VALID_ADDRESS:
            raise ValueError(
                f"Master address must be 0-65519 (0xFFEF), got {master_address}. "
                "Addresses 65520-65535 are reserved."
            )
        self.master_address = master_address

        try:
            outstation_address = int(self.outstation_address)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Outstation address must be an integer, got {self.outstation_address!r}"
            ) from e
        if not 0 <= outstation_address <= MAX_VALID_ADDRESS:
            raise ValueError(
                f"Outstation address must be 0-65519 (0xFFEF), got {outstation_address}. "
                "Addresses 65520-65535 are reserved."
            )
        self.outstation_address = outstation_address

        # Timeouts (seconds) must be positive; coerce to float
        for name in ("response_timeout", "connection_timeout", "select_timeout"):
            try:
                val = float(getattr(self, name))
            except (TypeError, ValueError) as e:
                raise ValueError(f"{name} must be a number, got {getattr(self, name)!r}") from e
            if val <= 0:
                raise ValueError(f"{name} must be positive, got {val}")
            setattr(self, name, val)

        # Retries
        try:
            max_retries = int(self.max_retries)
        except (TypeError, ValueError) as e:
            raise ValueError(f"max_retries must be an integer, got {self.max_retries!r}") from e
        if max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {max_retries}")
        self.max_retries = max_retries

        try:
            retry_delay = float(self.retry_delay)
        except (TypeError, ValueError) as e:
            raise ValueError(f"retry_delay must be a number, got {self.retry_delay!r}") from e
        if retry_delay < 0:
            raise ValueError(f"retry_delay must be >= 0, got {retry_delay}")
        self.retry_delay = retry_delay

        # Data link: max user data per frame (DNP3 limit 250); coerce to int
        try:
            max_frame_size = int(self.max_frame_size)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"max_frame_size must be an integer, got {self.max_frame_size!r}"
            ) from e
        if not 1 <= max_frame_size <= 250:
            raise ValueError(f"max_frame_size must be 1-250, got {max_frame_size}")
        self.max_frame_size = max_frame_size

        # Application layer: max APDU size (align with transport MAX_MESSAGE_SIZE = 65536)
        try:
            max_apdu_size = int(self.max_apdu_size)
        except (TypeError, ValueError) as e:
            raise ValueError(f"max_apdu_size must be an integer, got {self.max_apdu_size!r}") from e
        if not 1 <= max_apdu_size <= 65536:
            raise ValueError(f"max_apdu_size must be 1-65536, got {max_apdu_size}")
        self.max_apdu_size = max_apdu_size

        # Poll intervals (0 = disabled); coerce to float
        for name in (
            "class_0_poll_interval",
            "class_1_poll_interval",
            "class_2_poll_interval",
            "class_3_poll_interval",
        ):
            try:
                val = float(getattr(self, name))
            except (TypeError, ValueError) as e:
                raise ValueError(f"{name} must be a number, got {getattr(self, name)!r}") from e
            if val < 0:
                raise ValueError(f"{name} must be >= 0, got {val}")
            setattr(self, name, val)

        # Log level: must be valid for logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        if not isinstance(self.log_level, str):
            raise ValueError(f"log_level must be a string, got {type(self.log_level).__name__}")
        normalized = self.log_level.strip().upper()
        if normalized not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(
                f"log_level must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL, got {self.log_level!r}"
            )
        self.log_level = normalized
