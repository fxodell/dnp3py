"""
DNP3 CRC-16 implementation.

DNP3 uses a 16-bit CRC with polynomial 0x3D65 (reversed: 0xA6BC).
The CRC is calculated over data blocks and then inverted before
being appended to the frame.

The polynomial used is x^16 + x^13 + x^12 + x^11 + x^10 + x^8 + x^6 + x^5 + x^2 + 1
which is 0x3D65 in normal form.
"""

from typing import Union


class CRC16DNP3:
    """
    DNP3 CRC-16 calculator.

    Uses a lookup table for efficient CRC calculation.
    Polynomial: 0x3D65 (reflected: 0xA6BC)
    Initial value: 0x0000
    Final XOR: 0xFFFF (inversion)
    """

    # Pre-computed CRC lookup table for DNP3 polynomial (0xA6BC reflected)
    _CRC_TABLE = None

    @classmethod
    def _init_table(cls) -> list[int]:
        """Initialize the CRC lookup table."""
        if cls._CRC_TABLE is not None:
            return cls._CRC_TABLE

        table = []
        polynomial = 0xA6BC  # Reflected polynomial

        for i in range(256):
            crc = i
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ polynomial
                else:
                    crc >>= 1
            table.append(crc)

        cls._CRC_TABLE = table
        return table

    @classmethod
    def calculate(cls, data: Union[bytes, bytearray]) -> int:
        """
        Calculate DNP3 CRC-16 for the given data.

        Args:
            data: Bytes to calculate CRC for (must not be empty for meaningful CRC)

        Returns:
            16-bit CRC value (inverted as per DNP3 spec)

        Note:
            An empty input returns 0xFFFF (the final XOR value with no data).
            This is technically correct but may indicate a usage error.

        Raises:
            ValueError: If data is None.
            TypeError: If data is not bytes or bytearray.
        """
        if data is None:
            raise ValueError("CRC input data cannot be None")
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(f"CRC input must be bytes or bytearray, got {type(data).__name__}")

        table = cls._init_table()
        crc = 0x0000

        for byte in data:
            crc = (crc >> 8) ^ table[(crc ^ byte) & 0xFF]

        # DNP3 requires final inversion
        return crc ^ 0xFFFF

    @classmethod
    def calculate_bytes(cls, data: Union[bytes, bytearray]) -> bytes:
        """
        Calculate CRC and return as little-endian bytes.

        Args:
            data: Bytes to calculate CRC for

        Returns:
            2-byte CRC in little-endian format
        """
        crc = cls.calculate(data)
        return bytes([crc & 0xFF, (crc >> 8) & 0xFF])

    @classmethod
    def verify(cls, data: Union[bytes, bytearray], expected_crc: int) -> bool:
        """
        Verify that data matches the expected CRC.

        Args:
            data: Data bytes to verify
            expected_crc: Expected CRC value

        Returns:
            True if CRC matches, False otherwise
        """
        return cls.calculate(data) == expected_crc

    @classmethod
    def verify_bytes(cls, data: Union[bytes, bytearray], crc_bytes: bytes) -> bool:
        """
        Verify CRC using CRC bytes in little-endian format.

        Args:
            data: Data bytes to verify
            crc_bytes: 2-byte CRC in little-endian format

        Returns:
            True if CRC matches, False otherwise

        Raises:
            ValueError: If crc_bytes is None or not exactly 2 bytes.
            TypeError: If crc_bytes is not bytes or bytearray.
        """
        if crc_bytes is None:
            raise ValueError("CRC bytes cannot be None")
        if not isinstance(crc_bytes, (bytes, bytearray)):
            raise TypeError(f"CRC bytes must be bytes or bytearray, got {type(crc_bytes).__name__}")
        if len(crc_bytes) != 2:
            raise ValueError(f"CRC bytes must be exactly 2 bytes, got {len(crc_bytes)}")
        expected = crc_bytes[0] | (crc_bytes[1] << 8)
        return cls.verify(data, expected)

    @classmethod
    def append_crc(cls, data: Union[bytes, bytearray]) -> bytes:
        """
        Append CRC to data block.

        Args:
            data: Data bytes

        Returns:
            Data with CRC appended
        """
        return bytes(data) + cls.calculate_bytes(data)


def calculate_frame_crc(frame_data: Union[bytes, bytearray]) -> tuple[bytes, list[bytes]]:
    """
    Calculate CRCs for a complete DNP3 frame.

    DNP3 frames have:
    - Header CRC: CRC of the first 8 bytes (start, length, control, addresses)
    - Block CRCs: CRC every 16 bytes of user data

    Args:
        frame_data: Frame data without CRCs (bytes or bytearray)

    Returns:
        Tuple of (header_crc_bytes, list_of_block_crc_bytes)

    Raises:
        TypeError: If frame_data is not bytes or bytearray.
    """
    if not isinstance(frame_data, (bytes, bytearray)):
        raise TypeError(f"frame_data must be bytes or bytearray, got {type(frame_data).__name__}")
    header = frame_data[:8]
    header_crc = CRC16DNP3.calculate_bytes(header)

    user_data = frame_data[8:] if len(frame_data) > 8 else b""
    block_crcs = []

    # Calculate CRC for each 16-byte block
    for i in range(0, len(user_data), 16):
        block = user_data[i : i + 16]
        block_crcs.append(CRC16DNP3.calculate_bytes(block))

    return header_crc, block_crcs


# Pre-initialize the table at module load
CRC16DNP3._init_table()
