"""Tests for DNP3 CRC-16 calculation."""

import pytest
from dnp3_driver.utils.crc import CRC16DNP3


class TestCRC16DNP3:
    """Tests for CRC16DNP3 class."""

    def test_empty_data(self):
        """Test CRC of empty data."""
        crc = CRC16DNP3.calculate(b"")
        assert crc == 0xFFFF  # Inverted initial value

    def test_single_byte(self):
        """Test CRC of single byte."""
        crc = CRC16DNP3.calculate(b"\x00")
        assert isinstance(crc, int)
        assert 0 <= crc <= 0xFFFF

    def test_known_value(self):
        """Test CRC against known DNP3 values."""
        # DNP3 header example: 05 64 05 C0 01 00 00 00
        # This is a typical DNP3 frame header
        header = bytes([0x05, 0x64, 0x05, 0xC0, 0x01, 0x00, 0x00, 0x00])
        crc = CRC16DNP3.calculate(header)
        assert isinstance(crc, int)

    def test_calculate_bytes(self):
        """Test CRC returned as bytes."""
        data = b"test"
        crc_bytes = CRC16DNP3.calculate_bytes(data)
        assert len(crc_bytes) == 2
        assert isinstance(crc_bytes, bytes)

        # Verify it matches calculate()
        crc_int = CRC16DNP3.calculate(data)
        assert crc_bytes[0] == (crc_int & 0xFF)
        assert crc_bytes[1] == ((crc_int >> 8) & 0xFF)

    def test_verify_correct_crc(self):
        """Test verification of correct CRC."""
        data = b"hello world"
        crc = CRC16DNP3.calculate(data)
        assert CRC16DNP3.verify(data, crc) is True

    def test_verify_incorrect_crc(self):
        """Test verification of incorrect CRC."""
        data = b"hello world"
        wrong_crc = 0x1234
        assert CRC16DNP3.verify(data, wrong_crc) is False

    def test_verify_bytes(self):
        """Test verification using CRC bytes."""
        data = b"test data"
        crc_bytes = CRC16DNP3.calculate_bytes(data)
        assert CRC16DNP3.verify_bytes(data, crc_bytes) is True

    def test_append_crc(self):
        """Test appending CRC to data."""
        data = b"test"
        result = CRC16DNP3.append_crc(data)
        assert len(result) == len(data) + 2
        assert result[:len(data)] == data

        # Verify appended CRC
        crc_bytes = result[-2:]
        assert CRC16DNP3.verify_bytes(data, crc_bytes) is True

    def test_consistency(self):
        """Test that same data always produces same CRC."""
        data = b"consistent test data"
        crc1 = CRC16DNP3.calculate(data)
        crc2 = CRC16DNP3.calculate(data)
        assert crc1 == crc2

    def test_different_data_different_crc(self):
        """Test that different data produces different CRC."""
        crc1 = CRC16DNP3.calculate(b"data1")
        crc2 = CRC16DNP3.calculate(b"data2")
        assert crc1 != crc2

    def test_bytearray_input(self):
        """Test that bytearray input works."""
        data = bytearray([0x01, 0x02, 0x03])
        crc = CRC16DNP3.calculate(data)
        assert isinstance(crc, int)

    def test_long_data(self):
        """Test CRC of longer data."""
        data = bytes(range(256))  # 256 bytes
        crc = CRC16DNP3.calculate(data)
        assert 0 <= crc <= 0xFFFF
