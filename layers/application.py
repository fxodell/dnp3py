"""
DNP3 Application Layer implementation.

The Application Layer handles:
- Request/response message formatting
- Function code processing
- Object header construction and parsing
- Internal Indication (IIN) handling

Application Layer Message Structure:
    Request:  [Control: 1 byte][Function: 1 byte][Object Headers...]
    Response: [Control: 1 byte][Function: 1 byte][IIN: 2 bytes][Object Headers...]

Application Control Byte:
    - Bit 7 (FIR): First fragment
    - Bit 6 (FIN): Final fragment
    - Bit 5 (CON): Confirmation required
    - Bit 4 (UNS): Unsolicited response
    - Bits 3-0: Sequence number (0-15)
"""

from dataclasses import dataclass, field
from typing import Optional

from dnp3py.core.config import (
    AppLayerFunction,
    IINFlags,
    QualifierCode,
)
from dnp3py.core.exceptions import DNP3ObjectError, DNP3ProtocolError

# Application control byte flags
FIR_FLAG = 0x80
FIN_FLAG = 0x40
CON_FLAG = 0x20
UNS_FLAG = 0x10
SEQ_MASK = 0x0F
SEQ_MODULUS = 16  # Sequence numbers are 4-bit (0-15)


@dataclass
class ObjectHeader:
    """
    DNP3 Object Header.

    Specifies the group, variation, and qualifier for data objects.
    """

    group: int
    variation: int
    qualifier: int
    range_start: int = 0
    range_stop: int = 0
    count: int = 0
    data: bytes = b""
    data_offset: int = 0  # Offset in raw_data where this object's data starts

    def to_bytes(self) -> bytes:
        """Serialize object header to bytes."""
        for name, val in (
            ("group", self.group),
            ("variation", self.variation),
            ("qualifier", self.qualifier),
        ):
            if not isinstance(val, int) or not (0 <= val <= 255):
                raise DNP3ObjectError(f"Object header {name} must be an integer 0-255, got {val!r}")
        result = bytearray([self.group, self.variation, self.qualifier])

        # Add range/count based on qualifier
        if self.qualifier == QualifierCode.UINT8_START_STOP:
            if self.range_stop < self.range_start:
                raise DNP3ObjectError(
                    f"Invalid range: start {self.range_start} > stop {self.range_stop}"
                )
            if not 0 <= self.range_start <= 255 or not 0 <= self.range_stop <= 255:
                raise DNP3ObjectError(
                    f"UINT8 range must be 0-255: start={self.range_start}, stop={self.range_stop}"
                )
            result.append(self.range_start & 0xFF)
            result.append(self.range_stop & 0xFF)
        elif self.qualifier == QualifierCode.UINT16_START_STOP:
            if self.range_stop < self.range_start:
                raise DNP3ObjectError(
                    f"Invalid range: start {self.range_start} > stop {self.range_stop}"
                )
            if not 0 <= self.range_start <= 0xFFFF or not 0 <= self.range_stop <= 0xFFFF:
                raise DNP3ObjectError(
                    f"UINT16 range must be 0-65535: start={self.range_start}, stop={self.range_stop}"
                )
            result.extend(self.range_start.to_bytes(2, "little"))
            result.extend(self.range_stop.to_bytes(2, "little"))
        elif self.qualifier == QualifierCode.ALL_OBJECTS:
            pass  # No range field
        elif self.qualifier == QualifierCode.UINT8_COUNT:
            if not isinstance(self.count, int) or not 0 <= self.count <= 255:
                raise DNP3ObjectError(f"UINT8 count must be 0-255, got {self.count!r}")
            result.append(self.count & 0xFF)
        elif self.qualifier == QualifierCode.UINT16_COUNT:
            if not isinstance(self.count, int) or not 0 <= self.count <= 0xFFFF:
                raise DNP3ObjectError(f"UINT16 count must be 0-65535, got {self.count!r}")
            result.extend(self.count.to_bytes(2, "little"))
        elif self.qualifier in (
            QualifierCode.UINT8_COUNT_UINT8_INDEX,
            QualifierCode.UINT8_COUNT_UINT16_INDEX,
        ):
            if not isinstance(self.count, int) or not 0 <= self.count <= 255:
                raise DNP3ObjectError(f"UINT8 count must be 0-255, got {self.count!r}")
            result.append(self.count & 0xFF)
        elif self.qualifier == QualifierCode.UINT16_COUNT_UINT16_INDEX:
            if not isinstance(self.count, int) or not 0 <= self.count <= 0xFFFF:
                raise DNP3ObjectError(f"UINT16 count must be 0-65535, got {self.count!r}")
            result.extend(self.count.to_bytes(2, "little"))
        else:
            raise DNP3ObjectError(f"Unsupported qualifier code: 0x{self.qualifier:02X}")

        # Add data if present
        result.extend(self.data)

        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["ObjectHeader", int]:
        """
        Parse object header from bytes.

        Args:
            data: Raw bytes
            offset: Starting offset in data

        Returns:
            Tuple of (ObjectHeader, bytes consumed)
        """
        if not isinstance(offset, int) or offset < 0:
            raise DNP3ObjectError(f"Invalid offset: must be non-negative integer, got {offset!r}")
        if offset > len(data):
            raise DNP3ObjectError(
                f"Offset beyond data length: offset={offset}, len(data)={len(data)}"
            )
        if len(data) - offset < 3:
            raise DNP3ObjectError("Insufficient data for object header")

        group = data[offset]
        variation = data[offset + 1]
        qualifier = data[offset + 2]
        consumed = 3

        range_start = 0
        range_stop = 0
        count = 0

        # Parse range/count based on qualifier
        if qualifier == QualifierCode.UINT8_START_STOP:
            if len(data) - offset - consumed < 2:
                raise DNP3ObjectError("Insufficient data for range")
            range_start = data[offset + consumed]
            range_stop = data[offset + consumed + 1]
            if range_stop < range_start:
                raise DNP3ObjectError(f"Invalid range: start {range_start} > stop {range_stop}")
            count = range_stop - range_start + 1
            consumed += 2
        elif qualifier == QualifierCode.UINT16_START_STOP:
            if len(data) - offset - consumed < 4:
                raise DNP3ObjectError("Insufficient data for range")
            range_start = int.from_bytes(data[offset + consumed : offset + consumed + 2], "little")
            range_stop = int.from_bytes(
                data[offset + consumed + 2 : offset + consumed + 4], "little"
            )
            if range_stop < range_start:
                raise DNP3ObjectError(f"Invalid range: start {range_start} > stop {range_stop}")
            count = range_stop - range_start + 1
            consumed += 4
        elif qualifier == QualifierCode.ALL_OBJECTS:
            pass  # No range field
        elif qualifier == QualifierCode.UINT8_COUNT:
            if len(data) - offset - consumed < 1:
                raise DNP3ObjectError("Insufficient data for count")
            count = data[offset + consumed]
            consumed += 1
        elif qualifier == QualifierCode.UINT16_COUNT:
            if len(data) - offset - consumed < 2:
                raise DNP3ObjectError("Insufficient data for count")
            count = int.from_bytes(data[offset + consumed : offset + consumed + 2], "little")
            consumed += 2
        elif qualifier == QualifierCode.UINT8_COUNT_UINT8_INDEX:
            if len(data) - offset - consumed < 1:
                raise DNP3ObjectError("Insufficient data for count")
            count = data[offset + consumed]
            consumed += 1
        elif qualifier in (
            QualifierCode.UINT8_COUNT_UINT16_INDEX,
            QualifierCode.UINT16_COUNT_UINT16_INDEX,
        ):
            if qualifier == QualifierCode.UINT8_COUNT_UINT16_INDEX:
                if len(data) - offset - consumed < 1:
                    raise DNP3ObjectError("Insufficient data for count")
                count = data[offset + consumed]
                consumed += 1
            else:
                if len(data) - offset - consumed < 2:
                    raise DNP3ObjectError("Insufficient data for count")
                count = int.from_bytes(data[offset + consumed : offset + consumed + 2], "little")
                consumed += 2
        else:
            raise DNP3ObjectError(f"Unsupported qualifier code: 0x{qualifier:02X}")

        return cls(
            group=group,
            variation=variation,
            qualifier=qualifier,
            range_start=range_start,
            range_stop=range_stop,
            count=count,
            data=b"",  # Data will be parsed separately
        ), consumed

    def __repr__(self) -> str:
        return f"ObjectHeader(g{self.group}v{self.variation}, q=0x{self.qualifier:02X}, count={self.count})"


@dataclass
class ApplicationRequest:
    """DNP3 Application Layer request message."""

    function: int
    sequence: int = 0
    first: bool = True
    final: bool = True
    confirm: bool = False
    objects: list[ObjectHeader] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate request parameters."""
        # Validate sequence number is in valid range (0-15)
        if not 0 <= self.sequence <= SEQ_MASK:
            raise ValueError(f"Sequence number must be 0-15, got {self.sequence}")
        # Validate function code is a valid byte
        if not 0 <= self.function <= 255:
            raise ValueError(f"Function code must be 0-255, got {self.function}")

    @property
    def control(self) -> int:
        """Build the application control byte."""
        ctrl = self.sequence & SEQ_MASK
        if self.first:
            ctrl |= FIR_FLAG
        if self.final:
            ctrl |= FIN_FLAG
        if self.confirm:
            ctrl |= CON_FLAG
        return ctrl

    def to_bytes(self) -> bytes:
        """Serialize request to bytes."""
        result = bytearray([self.control, self.function])
        for obj_header in self.objects:
            result.extend(obj_header.to_bytes())
        return bytes(result)

    @classmethod
    def read_class_0(cls, sequence: int = 0) -> "ApplicationRequest":
        """Create a Class 0 (static data) read request."""
        return cls(
            function=AppLayerFunction.READ,
            sequence=sequence,
            objects=[ObjectHeader(group=60, variation=1, qualifier=QualifierCode.ALL_OBJECTS)],
        )

    @classmethod
    def read_class_1(cls, sequence: int = 0) -> "ApplicationRequest":
        """Create a Class 1 events read request."""
        return cls(
            function=AppLayerFunction.READ,
            sequence=sequence,
            objects=[ObjectHeader(group=60, variation=2, qualifier=QualifierCode.ALL_OBJECTS)],
        )

    @classmethod
    def read_class_2(cls, sequence: int = 0) -> "ApplicationRequest":
        """Create a Class 2 events read request."""
        return cls(
            function=AppLayerFunction.READ,
            sequence=sequence,
            objects=[ObjectHeader(group=60, variation=3, qualifier=QualifierCode.ALL_OBJECTS)],
        )

    @classmethod
    def read_class_3(cls, sequence: int = 0) -> "ApplicationRequest":
        """Create a Class 3 events read request."""
        return cls(
            function=AppLayerFunction.READ,
            sequence=sequence,
            objects=[ObjectHeader(group=60, variation=4, qualifier=QualifierCode.ALL_OBJECTS)],
        )

    @classmethod
    def read_all_classes(cls, sequence: int = 0) -> "ApplicationRequest":
        """Create a read request for all classes (integrity poll)."""
        return cls(
            function=AppLayerFunction.READ,
            sequence=sequence,
            objects=[
                ObjectHeader(group=60, variation=1, qualifier=QualifierCode.ALL_OBJECTS),  # Class 0
                ObjectHeader(group=60, variation=2, qualifier=QualifierCode.ALL_OBJECTS),  # Class 1
                ObjectHeader(group=60, variation=3, qualifier=QualifierCode.ALL_OBJECTS),  # Class 2
                ObjectHeader(group=60, variation=4, qualifier=QualifierCode.ALL_OBJECTS),  # Class 3
            ],
        )

    @classmethod
    def read_binary_inputs(
        cls, start: int = 0, stop: int = 0, sequence: int = 0
    ) -> "ApplicationRequest":
        """Create a binary inputs read request."""
        return cls(
            function=AppLayerFunction.READ,
            sequence=sequence,
            objects=[
                ObjectHeader(
                    group=1,
                    variation=0,  # Variation 0 = any variation
                    qualifier=QualifierCode.UINT16_START_STOP,
                    range_start=start,
                    range_stop=stop,
                )
            ],
        )

    @classmethod
    def read_analog_inputs(
        cls, start: int = 0, stop: int = 0, sequence: int = 0
    ) -> "ApplicationRequest":
        """Create an analog inputs read request."""
        return cls(
            function=AppLayerFunction.READ,
            sequence=sequence,
            objects=[
                ObjectHeader(
                    group=30,
                    variation=0,
                    qualifier=QualifierCode.UINT16_START_STOP,
                    range_start=start,
                    range_stop=stop,
                )
            ],
        )

    @classmethod
    def read_counters(
        cls, start: int = 0, stop: int = 0, sequence: int = 0
    ) -> "ApplicationRequest":
        """Create a counters read request."""
        return cls(
            function=AppLayerFunction.READ,
            sequence=sequence,
            objects=[
                ObjectHeader(
                    group=20,
                    variation=0,
                    qualifier=QualifierCode.UINT16_START_STOP,
                    range_start=start,
                    range_stop=stop,
                )
            ],
        )


@dataclass
class ApplicationResponse:
    """DNP3 Application Layer response message."""

    function: int
    sequence: int
    first: bool
    final: bool
    confirm_required: bool
    unsolicited: bool
    iin: IINFlags
    iin1: int
    iin2: int
    objects: list[ObjectHeader] = field(default_factory=list)
    raw_data: bytes = b""

    @classmethod
    def from_bytes(cls, data: bytes) -> "ApplicationResponse":
        """
        Parse a response from bytes.

        Args:
            data: Raw APDU bytes

        Returns:
            Parsed ApplicationResponse
        """
        if len(data) < 4:
            raise DNP3ProtocolError("Response too short")

        control = data[0]
        function = data[1]
        iin1 = data[2]
        iin2 = data[3]
        if function not in (
            AppLayerFunction.RESPONSE,
            AppLayerFunction.UNSOLICITED_RESPONSE,
            AppLayerFunction.AUTHENTICATION_RESPONSE,
        ):
            raise DNP3ProtocolError(f"Invalid response function code: 0x{function:02X}")

        sequence = control & SEQ_MASK
        first = bool(control & FIR_FLAG)
        final = bool(control & FIN_FLAG)
        confirm_required = bool(control & CON_FLAG)
        unsolicited = bool(control & UNS_FLAG)

        iin = IINFlags.from_bytes(iin1, iin2)

        # Parse object headers and their data from remaining data
        # DNP3 format: [Header1][Data1][Header2][Data2]...
        # raw_data will be data[4:] (everything after control, function, IIN)
        objects = []
        offset = 4  # Start after control(1) + function(1) + IIN(2)
        raw_data_start = 4  # Where raw_data begins in the original data

        while offset < len(data):
            try:
                obj_header, header_consumed = ObjectHeader.from_bytes(data, offset)

                # Calculate data size for this object
                data_size = cls._calculate_object_data_size(
                    obj_header.group,
                    obj_header.variation,
                    obj_header.qualifier,
                    obj_header.count,
                    obj_header.range_start,
                    obj_header.range_stop,
                )

                # Validate we have enough data remaining
                total_object_size = header_consumed + data_size
                if offset + total_object_size > len(data):
                    # Not enough data for this object - truncated response
                    break

                # Set the data offset (relative to raw_data which starts at data[4:])
                # The header ends at (offset + header_consumed), so the data starts there
                # Relative to raw_data (data[4:]), this is:
                data_offset_in_raw = (offset + header_consumed) - raw_data_start

                # Sanity check - should never be negative if parsing is correct
                if data_offset_in_raw < 0:
                    raise DNP3ProtocolError(
                        f"Internal error: computed negative data offset {data_offset_in_raw} "
                        f"for object g{obj_header.group}v{obj_header.variation}"
                    )

                obj_header.data_offset = data_offset_in_raw
                objects.append(obj_header)
                offset += total_object_size

            except DNP3ObjectError:
                # Log and break - no more valid object headers
                break

        return cls(
            function=function,
            sequence=sequence,
            first=first,
            final=final,
            confirm_required=confirm_required,
            unsolicited=unsolicited,
            iin=iin,
            iin1=iin1,
            iin2=iin2,
            objects=objects,
            raw_data=data[4:],
        )

    @staticmethod
    def _calculate_object_data_size(
        group: int,
        variation: int,
        qualifier: int,
        count: int,
        range_start: int,
        range_stop: int,
    ) -> int:
        """
        Calculate the size of object data following a header.

        Args:
            group: Object group number
            variation: Object variation
            qualifier: Qualifier code
            count: Object count
            range_start: Range start index
            range_stop: Range stop index

        Returns:
            Size of object data in bytes
        """
        # Import here to avoid circular dependency
        from dnp3py.objects.groups import get_object_size

        if count == 0:
            return 0

        # Get object size for this group/variation
        obj_size = get_object_size(group, variation)

        if obj_size is not None:
            # Fixed size objects
            return obj_size * count

        # Handle variable-size objects

        # Packed binary (1 bit per point)
        if group in (1, 10) and variation == 1:
            return (count + 7) // 8  # Ceiling division for bits to bytes

        # For indexed qualifiers, the size includes index prefixes
        if qualifier == QualifierCode.UINT8_COUNT_UINT8_INDEX:
            # Each object has 1-byte index prefix
            base_size = get_object_size(group, variation)
            if base_size is None:
                raise DNP3ObjectError(
                    f"Unknown object size for indexed qualifier: group={group}, variation={variation}"
                )
            return count * (1 + base_size)
        elif qualifier == QualifierCode.UINT8_COUNT_UINT16_INDEX:
            # Each object has 2-byte index prefix
            base_size = get_object_size(group, variation)
            if base_size is None:
                raise DNP3ObjectError(
                    f"Unknown object size for indexed qualifier: group={group}, variation={variation}"
                )
            return count * (2 + base_size)
        elif qualifier == QualifierCode.UINT16_COUNT_UINT16_INDEX:
            # Each object has 2-byte index prefix
            base_size = get_object_size(group, variation)
            if base_size is None:
                raise DNP3ObjectError(
                    f"Unknown object size for indexed qualifier: group={group}, variation={variation}"
                )
            return count * (2 + base_size)

        # Unknown size - refuse to guess to avoid misaligned parsing
        raise DNP3ObjectError(
            f"Unknown or variable object size without parser support: "
            f"group={group}, variation={variation}, qualifier=0x{qualifier:02X}"
        )

    def __repr__(self) -> str:
        flags = []
        if self.first:
            flags.append("FIR")
        if self.final:
            flags.append("FIN")
        if self.confirm_required:
            flags.append("CON")
        if self.unsolicited:
            flags.append("UNS")
        flag_str = "|".join(flags) if flags else "none"
        return (
            f"ApplicationResponse(func=0x{self.function:02X}, seq={self.sequence}, "
            f"flags={flag_str}, objects={len(self.objects)})"
        )


class ApplicationLayer:
    """
    DNP3 Application Layer encoder/decoder.

    Handles request/response formatting and parsing.
    """

    def __init__(self):
        """Initialize Application Layer."""
        self._tx_sequence = 0
        self._rx_sequence: Optional[int] = None

    def build_request(
        self,
        function: int,
        objects: Optional[list[ObjectHeader]] = None,
        confirm: bool = False,
    ) -> bytes:
        """
        Build an application layer request.

        Args:
            function: Function code
            objects: List of object headers
            confirm: Request confirmation from outstation

        Returns:
            APDU bytes
        """
        request = ApplicationRequest(
            function=function,
            sequence=self._tx_sequence,
            first=True,
            final=True,
            confirm=confirm,
            objects=objects or [],
        )

        self._tx_sequence = (self._tx_sequence + 1) & SEQ_MASK
        return request.to_bytes()

    def build_confirm(self, sequence: int, unsolicited: bool = False) -> bytes:
        """
        Build an application layer confirmation.

        Args:
            sequence: Sequence number to confirm (0-15)
            unsolicited: True if confirming an unsolicited response

        Returns:
            APDU bytes

        Raises:
            ValueError: If sequence is not in 0-15
        """
        if not isinstance(sequence, int) or not 0 <= sequence <= SEQ_MASK:
            raise ValueError(f"Application sequence must be 0-15, got {sequence!r}")
        control = sequence & SEQ_MASK
        control |= FIR_FLAG | FIN_FLAG
        if unsolicited:
            control |= UNS_FLAG

        return bytes([control, AppLayerFunction.CONFIRM])

    def build_read_request(
        self,
        group: int,
        variation: int = 0,
        start: Optional[int] = None,
        stop: Optional[int] = None,
    ) -> bytes:
        """
        Build a READ request for specific objects.

        Args:
            group: Object group number (0-255)
            variation: Object variation (0 = any, 0-255)
            start: Start index (None for all objects); must be >= 0 if set
            stop: Stop index; must be >= 0 and >= start if set

        Returns:
            APDU bytes

        Raises:
            ValueError: If group/variation/start/stop are out of range
        """
        if not isinstance(group, int) or not 0 <= group <= 255:
            raise ValueError(f"Group must be 0-255, got {group!r}")
        if not isinstance(variation, int) or not 0 <= variation <= 255:
            raise ValueError(f"Variation must be 0-255, got {variation!r}")
        if start is not None:
            if not isinstance(start, int) or start < 0:
                raise ValueError(f"Start index must be non-negative integer, got {start!r}")
        if stop is not None:
            if not isinstance(stop, int) or stop < 0:
                raise ValueError(f"Stop index must be non-negative integer, got {stop!r}")
        if start is not None and stop is not None and start > stop:
            raise ValueError(f"Start must be <= stop, got start={start}, stop={stop}")
        if start is not None and stop is not None:
            obj_header = ObjectHeader(
                group=group,
                variation=variation,
                qualifier=QualifierCode.UINT16_START_STOP,
                range_start=start,
                range_stop=stop,
            )
        else:
            obj_header = ObjectHeader(
                group=group,
                variation=variation,
                qualifier=QualifierCode.ALL_OBJECTS,
            )

        return self.build_request(AppLayerFunction.READ, [obj_header])

    def build_integrity_poll(self) -> bytes:
        """Build an integrity poll (read all classes)."""
        request = ApplicationRequest.read_all_classes(self._tx_sequence)
        self._tx_sequence = (self._tx_sequence + 1) & SEQ_MASK
        return request.to_bytes()

    def build_class_poll(self, class_num: int) -> bytes:
        """
        Build a class poll request.

        Args:
            class_num: Class number (0, 1, 2, or 3)

        Returns:
            APDU bytes
        """
        if class_num == 0:
            request = ApplicationRequest.read_class_0(self._tx_sequence)
        elif class_num == 1:
            request = ApplicationRequest.read_class_1(self._tx_sequence)
        elif class_num == 2:
            request = ApplicationRequest.read_class_2(self._tx_sequence)
        elif class_num == 3:
            request = ApplicationRequest.read_class_3(self._tx_sequence)
        else:
            raise ValueError(f"Invalid class number: {class_num}")

        self._tx_sequence = (self._tx_sequence + 1) & SEQ_MASK
        return request.to_bytes()

    def parse_response(self, data: bytes) -> ApplicationResponse:
        """
        Parse an application layer response.

        Args:
            data: Raw APDU bytes

        Returns:
            Parsed ApplicationResponse
        """
        return ApplicationResponse.from_bytes(data)

    @property
    def sequence(self) -> int:
        """Get current transmit sequence number."""
        return self._tx_sequence

    def reset_sequence(self) -> None:
        """Reset the sequence number to 0."""
        self._tx_sequence = 0
