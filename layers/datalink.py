"""
DNP3 Data Link Layer implementation.

The Data Link Layer is responsible for:
- Frame construction with proper headers
- CRC calculation and verification
- Source and destination addressing
- Frame Control byte handling

Frame Structure (FT3 format):
    [Start: 2 bytes][Length: 1 byte][Control: 1 byte]
    [Destination: 2 bytes][Source: 2 bytes][Header CRC: 2 bytes]
    [User Data Block 1: up to 16 bytes][Block CRC: 2 bytes]
    [User Data Block 2: up to 16 bytes][Block CRC: 2 bytes]
    ...

Start bytes are always 0x05 0x64.
Maximum user data per frame is 250 bytes.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
from enum import IntFlag

from dnp3py.utils.crc import CRC16DNP3
from dnp3py.core.exceptions import DNP3CRCError, DNP3FrameError


# DNP3 Frame constants
START_BYTES = bytes([0x05, 0x64])
MIN_FRAME_SIZE = 10  # Header (10 bytes with CRC)
MAX_USER_DATA = 250
BLOCK_SIZE = 16


class ControlByte(IntFlag):
    """Data Link Layer control byte flags."""

    # Direction bit
    DIR = 0x80  # 1 = From master, 0 = From outstation

    # Primary bit
    PRM = 0x40  # 1 = Primary message, 0 = Secondary message

    # Frame Count Bit (primary) / Data Flow Control (secondary)
    FCB = 0x20

    # Frame Count Valid (primary) / Reserved (secondary)
    FCV = 0x10

    # Function code mask
    FUNC_MASK = 0x0F


class PrimaryFunction(IntFlag):
    """Primary station (master) function codes."""

    RESET_LINK = 0x00
    RESET_USER_PROCESS = 0x01
    TEST_LINK = 0x02
    USER_DATA_CONFIRMED = 0x03
    USER_DATA_UNCONFIRMED = 0x04
    REQUEST_LINK_STATUS = 0x09


class SecondaryFunction(IntFlag):
    """Secondary station (outstation) function codes."""

    ACK = 0x00
    NACK = 0x01
    LINK_STATUS = 0x0B
    NOT_SUPPORTED = 0x0F


@dataclass
class DataLinkFrame:
    """Represents a DNP3 Data Link Layer frame."""

    destination: int
    source: int
    control: int
    user_data: bytes = b""

    @property
    def is_from_master(self) -> bool:
        """Check if frame is from master (DIR bit set)."""
        return bool(self.control & ControlByte.DIR)

    @property
    def is_primary(self) -> bool:
        """Check if frame is a primary message (PRM bit set)."""
        return bool(self.control & ControlByte.PRM)

    @property
    def function_code(self) -> int:
        """Get the function code from control byte."""
        return self.control & ControlByte.FUNC_MASK

    @property
    def fcb(self) -> bool:
        """Get Frame Count Bit."""
        return bool(self.control & ControlByte.FCB)

    @property
    def fcv(self) -> bool:
        """Get Frame Count Valid bit."""
        return bool(self.control & ControlByte.FCV)

    def __repr__(self) -> str:
        return (
            f"DataLinkFrame(dst={self.destination}, src={self.source}, "
            f"ctrl=0x{self.control:02X}, data_len={len(self.user_data)})"
        )


class DataLinkLayer:
    """
    DNP3 Data Link Layer encoder/decoder.

    Handles frame construction and parsing according to DNP3 FT3 frame format.
    """

    # DNP3 address limits
    MAX_VALID_ADDRESS = 65519  # 0xFFEF - addresses 65520-65535 are reserved
    BROADCAST_ADDRESS = 65535  # 0xFFFF - broadcast address

    def __init__(self, master_address: int = 1, outstation_address: int = 10):
        """
        Initialize Data Link Layer.

        Args:
            master_address: Local master station address (0-65519)
            outstation_address: Remote outstation address (0-65519)

        Raises:
            ValueError: If addresses are outside valid range
        """
        self._validate_address(master_address, "Master")
        self._validate_address(outstation_address, "Outstation")
        self.master_address = master_address
        self.outstation_address = outstation_address
        self._fcb = False  # Frame Count Bit toggle

    @classmethod
    def _validate_address(cls, address: int, name: str) -> None:
        """Validate a DNP3 address.

        Args:
            address: Address to validate
            name: Name for error messages

        Raises:
            ValueError: If address is invalid
        """
        if not isinstance(address, int):
            raise ValueError(f"{name} address must be an integer, got {type(address).__name__}")
        if address < 0:
            raise ValueError(f"{name} address must be non-negative, got {address}")
        if address > cls.MAX_VALID_ADDRESS:
            if address == cls.BROADCAST_ADDRESS:
                raise ValueError(
                    f"{name} address cannot be broadcast address (65535/0xFFFF)"
                )
            raise ValueError(
                f"{name} address must be 0-65519 (0xFFEF), got {address}. "
                f"Addresses 65520-65535 are reserved."
            )

    def build_frame(
        self,
        user_data: bytes,
        destination: Optional[int] = None,
        source: Optional[int] = None,
        confirmed: bool = True,
        fcv: bool = True,
    ) -> bytes:
        """
        Build a complete DNP3 data link frame.

        Args:
            user_data: Transport layer data to encapsulate
            destination: Destination address (defaults to outstation)
            source: Source address (defaults to master)
            confirmed: If True, use confirmed data transfer
            fcv: Frame Count Valid flag

        Returns:
            Complete frame bytes including CRCs

        Raises:
            DNP3FrameError: If user data exceeds maximum size
        """
        if len(user_data) > MAX_USER_DATA:
            raise DNP3FrameError(
                f"User data exceeds maximum size: {len(user_data)} > {MAX_USER_DATA}"
            )

        if destination is None:
            destination = self.outstation_address
        else:
            self._validate_address(destination, "Destination")

        if source is None:
            source = self.master_address
        else:
            self._validate_address(source, "Source")

        # Build control byte
        control = ControlByte.DIR | ControlByte.PRM  # Master to outstation, primary

        if confirmed:
            control |= PrimaryFunction.USER_DATA_CONFIRMED
            if fcv:
                control |= ControlByte.FCV
                if self._fcb:
                    control |= ControlByte.FCB
        else:
            control |= PrimaryFunction.USER_DATA_UNCONFIRMED

        # Length field: control + destination + source + user_data = 5 + len(user_data)
        length = 5 + len(user_data)

        # Build header (8 bytes before CRC)
        header = bytearray(START_BYTES)
        header.append(length)
        header.append(control)
        header.extend(destination.to_bytes(2, "little"))
        header.extend(source.to_bytes(2, "little"))

        # Add header CRC
        frame = bytearray(header)
        frame.extend(CRC16DNP3.calculate_bytes(header))

        # Add user data with block CRCs
        for i in range(0, len(user_data), BLOCK_SIZE):
            block = user_data[i:i + BLOCK_SIZE]
            frame.extend(block)
            frame.extend(CRC16DNP3.calculate_bytes(block))

        return bytes(frame)

    def build_request_link_status(
        self,
        destination: Optional[int] = None,
        source: Optional[int] = None,
    ) -> bytes:
        """
        Build a Request Link Status frame.

        Args:
            destination: Destination address (defaults to outstation)
            source: Source address (defaults to master)

        Returns:
            Frame bytes
        """
        if destination is None:
            destination = self.outstation_address
        else:
            self._validate_address(destination, "Destination")
        if source is None:
            source = self.master_address
        else:
            self._validate_address(source, "Source")

        control = ControlByte.DIR | ControlByte.PRM | PrimaryFunction.REQUEST_LINK_STATUS
        length = 5  # Control + addresses, no user data

        header = bytearray(START_BYTES)
        header.append(length)
        header.append(control)
        header.extend(destination.to_bytes(2, "little"))
        header.extend(source.to_bytes(2, "little"))

        frame = bytearray(header)
        frame.extend(CRC16DNP3.calculate_bytes(header))

        return bytes(frame)

    def build_reset_link(
        self,
        destination: Optional[int] = None,
        source: Optional[int] = None,
    ) -> bytes:
        """
        Build a Reset Link frame.

        Args:
            destination: Destination address (defaults to outstation)
            source: Source address (defaults to master)

        Returns:
            Frame bytes
        """
        if destination is None:
            destination = self.outstation_address
        else:
            self._validate_address(destination, "Destination")
        if source is None:
            source = self.master_address
        else:
            self._validate_address(source, "Source")

        control = ControlByte.DIR | ControlByte.PRM | PrimaryFunction.RESET_LINK
        length = 5

        header = bytearray(START_BYTES)
        header.append(length)
        header.append(control)
        header.extend(destination.to_bytes(2, "little"))
        header.extend(source.to_bytes(2, "little"))

        frame = bytearray(header)
        frame.extend(CRC16DNP3.calculate_bytes(header))

        return bytes(frame)

    def parse_frame(self, data: bytes) -> Tuple[DataLinkFrame, int]:
        """
        Parse a DNP3 data link frame from bytes.

        Args:
            data: Raw bytes potentially containing a frame

        Returns:
            Tuple of (parsed DataLinkFrame, bytes consumed)

        Raises:
            DNP3FrameError: If frame is malformed
            DNP3CRCError: If CRC validation fails
        """
        if len(data) < MIN_FRAME_SIZE:
            raise DNP3FrameError(f"Data too short for frame: {len(data)} < {MIN_FRAME_SIZE}")

        # Check start bytes
        if data[:2] != START_BYTES:
            raise DNP3FrameError(
                f"Invalid start bytes: 0x{data[0]:02X} 0x{data[1]:02X}"
            )

        # Parse header
        length = data[2]
        control = data[3]
        destination = int.from_bytes(data[4:6], "little")
        source = int.from_bytes(data[6:8], "little")

        # Verify header CRC
        header_crc = int.from_bytes(data[8:10], "little")
        calculated_crc = CRC16DNP3.calculate(data[:8])
        if header_crc != calculated_crc:
            raise DNP3CRCError(
                "Header CRC mismatch",
                expected_crc=calculated_crc,
                actual_crc=header_crc,
            )

        # Calculate user data length: length - 5 (control + addresses)
        user_data_length = length - 5

        if user_data_length < 0:
            raise DNP3FrameError(f"Invalid length field: {length}")

        if user_data_length == 0:
            return DataLinkFrame(destination, source, control, b""), 10

        # Parse user data blocks
        user_data = bytearray()
        offset = 10  # After header + header CRC

        remaining_data = user_data_length
        while remaining_data > 0:
            block_size = min(remaining_data, BLOCK_SIZE)
            expected_frame_bytes = block_size + 2  # Block + CRC

            if offset + expected_frame_bytes > len(data):
                raise DNP3FrameError(
                    f"Incomplete frame: need {offset + expected_frame_bytes}, have {len(data)}"
                )

            block = data[offset:offset + block_size]
            block_crc = int.from_bytes(data[offset + block_size:offset + block_size + 2], "little")

            # Verify block CRC
            calculated_block_crc = CRC16DNP3.calculate(block)
            if block_crc != calculated_block_crc:
                raise DNP3CRCError(
                    f"Block CRC mismatch at offset {offset}",
                    expected_crc=calculated_block_crc,
                    actual_crc=block_crc,
                )

            user_data.extend(block)
            offset += expected_frame_bytes
            remaining_data -= block_size

        frame = DataLinkFrame(destination, source, control, bytes(user_data))
        return frame, offset

    def toggle_fcb(self) -> None:
        """Toggle the Frame Count Bit for next transmission."""
        self._fcb = not self._fcb

    def reset_fcb(self) -> None:
        """Reset Frame Count Bit to False."""
        self._fcb = False

    @staticmethod
    def find_frame_start(data: bytes) -> int:
        """
        Find the start of a DNP3 frame in data.

        Args:
            data: Buffer to search

        Returns:
            Index of frame start, or -1 if not found
        """
        if len(data) < 2:
            return -1

        for i in range(len(data) - 1):
            if data[i] == 0x05 and data[i + 1] == 0x64:
                return i
        return -1

    @staticmethod
    def calculate_frame_size(length_byte: int) -> int:
        """
        Calculate total frame size from length byte.

        Args:
            length_byte: The length field from frame header

        Returns:
            Total frame size in bytes

        Raises:
            DNP3FrameError: If length byte is invalid
        """
        try:
            length_byte = int(length_byte)
        except (TypeError, ValueError) as e:
            raise DNP3FrameError(
                f"Length byte must be an integer (0-255), got {type(length_byte).__name__}"
            ) from e
        # DNP3 length must be at least 5 (control + addresses)
        # and at most 255 (5 + 250 max user data)
        if length_byte < 5:
            raise DNP3FrameError(f"Invalid length byte: {length_byte} < 5 (minimum)")
        if length_byte > 255:
            raise DNP3FrameError(f"Invalid length byte: {length_byte} > 255 (maximum)")

        user_data_length = length_byte - 5

        if user_data_length == 0:
            return 10  # Header only

        # Validate user data doesn't exceed protocol limit
        if user_data_length > MAX_USER_DATA:
            raise DNP3FrameError(
                f"User data length {user_data_length} exceeds maximum {MAX_USER_DATA}"
            )

        # Header (10) + user data blocks with CRCs
        num_full_blocks = user_data_length // BLOCK_SIZE
        remaining = user_data_length % BLOCK_SIZE

        size = 10  # Header + header CRC
        size += num_full_blocks * (BLOCK_SIZE + 2)  # Full blocks with CRCs
        if remaining > 0:
            size += remaining + 2  # Partial block with CRC

        return size
