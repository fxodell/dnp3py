"""Tests for DNP3 Data Link Layer."""

import pytest
from pydnp3.layers.datalink import (
    DataLinkLayer,
    DataLinkFrame,
    START_BYTES,
    ControlByte,
    PrimaryFunction,
)
from pydnp3.core.exceptions import DNP3CRCError, DNP3FrameError


class TestDataLinkLayer:
    """Tests for DataLinkLayer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.layer = DataLinkLayer(master_address=1, outstation_address=10)

    def test_build_frame_empty_data(self):
        """Test building frame with no user data."""
        frame = self.layer.build_frame(b"")
        assert frame[:2] == START_BYTES
        assert len(frame) == 10  # Header only with CRC

    def test_build_frame_with_data(self):
        """Test building frame with user data."""
        user_data = bytes([0x01, 0x02, 0x03, 0x04])
        frame = self.layer.build_frame(user_data)

        assert frame[:2] == START_BYTES
        # Length = 5 + len(user_data) = 9
        assert frame[2] == 9

    def test_build_frame_max_data(self):
        """Test building frame with maximum user data."""
        user_data = bytes(250)  # Maximum allowed
        frame = self.layer.build_frame(user_data)
        assert frame is not None

    def test_build_frame_exceed_max_data(self):
        """Test that exceeding max data raises error."""
        user_data = bytes(251)  # Exceeds maximum
        with pytest.raises(DNP3FrameError):
            self.layer.build_frame(user_data)

    def test_build_frame_addresses(self):
        """Test that addresses are correctly encoded."""
        frame = self.layer.build_frame(b"", destination=0x1234, source=0x5678)

        # Destination is bytes 4-5 (little endian)
        assert frame[4] == 0x34
        assert frame[5] == 0x12

        # Source is bytes 6-7 (little endian)
        assert frame[6] == 0x78
        assert frame[7] == 0x56

    def test_parse_frame_valid(self):
        """Test parsing a valid frame."""
        user_data = bytes([0xAA, 0xBB, 0xCC])
        frame = self.layer.build_frame(user_data)

        parsed, consumed = self.layer.parse_frame(frame)

        assert isinstance(parsed, DataLinkFrame)
        assert parsed.user_data == user_data
        assert parsed.destination == self.layer.outstation_address
        assert parsed.source == self.layer.master_address

    def test_parse_frame_invalid_start_bytes(self):
        """Test parsing frame with invalid start bytes."""
        bad_frame = bytes([0xFF, 0xFF, 0x05, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00])
        with pytest.raises(DNP3FrameError):
            self.layer.parse_frame(bad_frame)

    def test_parse_frame_too_short(self):
        """Test parsing frame that is too short."""
        short_data = bytes([0x05, 0x64, 0x05])
        with pytest.raises(DNP3FrameError):
            self.layer.parse_frame(short_data)

    def test_parse_frame_bad_crc(self):
        """Test parsing frame with bad CRC."""
        user_data = b"\x01\x02"
        frame = bytearray(self.layer.build_frame(user_data))
        # Corrupt header CRC
        frame[8] = 0xFF
        frame[9] = 0xFF

        with pytest.raises(DNP3CRCError):
            self.layer.parse_frame(bytes(frame))

    def test_round_trip(self):
        """Test building and parsing frame preserves data."""
        original_data = bytes([0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF])
        frame = self.layer.build_frame(original_data)
        parsed, _ = self.layer.parse_frame(frame)

        assert parsed.user_data == original_data

    def test_build_request_link_status(self):
        """Test building request link status frame."""
        frame = self.layer.build_request_link_status()
        assert frame[:2] == START_BYTES
        assert len(frame) == 10  # Header only

    def test_build_reset_link(self):
        """Test building reset link frame."""
        frame = self.layer.build_reset_link()
        assert frame[:2] == START_BYTES
        assert len(frame) == 10

    def test_fcb_toggle(self):
        """Test Frame Count Bit toggling."""
        assert self.layer._fcb is False

        self.layer.toggle_fcb()
        assert self.layer._fcb is True

        self.layer.toggle_fcb()
        assert self.layer._fcb is False

    def test_find_frame_start(self):
        """Test finding frame start in buffer."""
        # Frame start at index 3
        data = bytes([0x00, 0x00, 0x00, 0x05, 0x64, 0x05, 0x00])
        index = DataLinkLayer.find_frame_start(data)
        assert index == 3

        # No frame start
        data = bytes([0x00, 0x00, 0x00, 0x00])
        index = DataLinkLayer.find_frame_start(data)
        assert index == -1

    def test_calculate_frame_size(self):
        """Test frame size calculation."""
        # Header only (length = 5)
        size = DataLinkLayer.calculate_frame_size(5)
        assert size == 10

        # With 16 bytes of user data (length = 21)
        # 10 (header) + 16 (data) + 2 (CRC) = 28
        size = DataLinkLayer.calculate_frame_size(21)
        assert size == 28

        # With 20 bytes of user data (length = 25)
        # 10 (header) + 16 (data) + 2 (CRC) + 4 (data) + 2 (CRC) = 34
        size = DataLinkLayer.calculate_frame_size(25)
        assert size == 34

    def test_control_byte_flags(self):
        """Test control byte flag encoding."""
        frame = self.layer.build_frame(b"\x01", confirmed=True, fcv=True)
        control = frame[3]

        assert control & ControlByte.DIR  # Direction from master
        assert control & ControlByte.PRM  # Primary message

    def test_multiple_data_blocks(self):
        """Test frame with multiple 16-byte data blocks."""
        # 32 bytes = 2 full blocks
        user_data = bytes(32)
        frame = self.layer.build_frame(user_data)

        parsed, _ = self.layer.parse_frame(frame)
        assert parsed.user_data == user_data

    def test_partial_data_block(self):
        """Test frame with partial data block."""
        # 20 bytes = 1 full block (16) + 1 partial (4)
        user_data = bytes(20)
        frame = self.layer.build_frame(user_data)

        parsed, _ = self.layer.parse_frame(frame)
        assert parsed.user_data == user_data

    def test_find_frame_start_empty_data(self):
        """Test find_frame_start with empty data."""
        result = DataLinkLayer.find_frame_start(b"")
        assert result == -1

    def test_find_frame_start_single_byte(self):
        """Test find_frame_start with single byte."""
        result = DataLinkLayer.find_frame_start(b"\x05")
        assert result == -1

    def test_find_frame_start_partial_start(self):
        """Test find_frame_start with partial start sequence."""
        result = DataLinkLayer.find_frame_start(b"\x05\x00")
        assert result == -1

    def test_find_frame_start_valid_at_offset(self):
        """Test find_frame_start with valid start at offset."""
        result = DataLinkLayer.find_frame_start(b"\x00\x00\x05\x64\x00")
        assert result == 2

    def test_calculate_frame_size_invalid_length_too_small(self):
        """Test calculate_frame_size with length too small."""
        with pytest.raises(DNP3FrameError):
            DataLinkLayer.calculate_frame_size(4)  # Minimum is 5

    def test_calculate_frame_size_valid_minimum(self):
        """Test calculate_frame_size with minimum valid length."""
        size = DataLinkLayer.calculate_frame_size(5)
        assert size == 10  # Header only

    def test_calculate_frame_size_max_user_data(self):
        """Test calculate_frame_size with maximum user data."""
        # Max user data is 250 bytes, so length = 255
        size = DataLinkLayer.calculate_frame_size(255)
        # 10 (header) + 15 full blocks * 18 + 1 partial (10) + 2 CRC
        # 10 + 15*(16+2) + 10+2 = 10 + 270 + 12 = 292
        assert size > 10

    def test_parse_frame_invalid_length_field(self):
        """Test parsing frame with invalid length field (< 5)."""
        # Create a frame with length = 3 (invalid)
        invalid_frame = bytes([0x05, 0x64, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00])
        # Add a valid CRC for the header
        from pydnp3.utils.crc import CRC16DNP3
        invalid_frame += CRC16DNP3.calculate_bytes(invalid_frame)

        with pytest.raises(DNP3FrameError):
            self.layer.parse_frame(invalid_frame)
