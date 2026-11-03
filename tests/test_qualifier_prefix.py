"""Tests for the index-prefix qualifiers 0x17, 0x28 and 0x29."""

from dnp3py.core.config import QualifierCode
from dnp3py.layers.application import ApplicationResponse, ObjectHeader


class TestPrefixedQualifierCount:
    """The count field is 1 octet for 0x17, 2 for 0x28 and 4 for 0x29."""

    def test_0x17_count_is_one_octet(self):
        header = ObjectHeader(group=12, variation=1, qualifier=0x17, count=1)
        assert header.to_bytes() == bytes([12, 1, 0x17, 0x01])

    def test_0x28_count_is_two_octets(self):
        header = ObjectHeader(group=12, variation=1, qualifier=0x28, count=1)
        assert header.to_bytes() == bytes([12, 1, 0x28, 0x01, 0x00])

    def test_0x28_accepts_counts_above_255(self):
        header = ObjectHeader(group=12, variation=1, qualifier=0x28, count=300)
        assert header.to_bytes()[3:] == (300).to_bytes(2, "little")

    def test_0x29_count_is_four_octets(self):
        header = ObjectHeader(group=12, variation=1, qualifier=0x29, count=1)
        assert header.to_bytes() == bytes([12, 1, 0x29, 0x01, 0x00, 0x00, 0x00])

    def test_from_bytes_0x28(self):
        header, consumed = ObjectHeader.from_bytes(bytes([2, 1, 0x28, 0x02, 0x00]))
        assert (header.count, consumed) == (2, 5)

    def test_from_bytes_0x29(self):
        header, consumed = ObjectHeader.from_bytes(bytes([2, 1, 0x29, 0x02, 0x00, 0x00, 0x00]))
        assert (header.count, consumed) == (2, 7)

    def test_qualifier_values(self):
        assert QualifierCode.UINT8_COUNT_UINT16_INDEX == 0x28
        assert QualifierCode.UINT16_COUNT_UINT16_INDEX == 0x29


class TestPrefixedObjectFraming:
    """Each prefixed object takes its index prefix plus its object size."""

    def test_headers_after_a_prefixed_header_are_parsed(self):
        """A g2v1 header with 0x28 is followed by a g32v1 header with 0x17."""
        apdu = bytes([0xC0, 0x81, 0x00, 0x00])
        # g2v1, qualifier 0x28, count 2: index(2) + flags(1) per object
        apdu += bytes([2, 1, 0x28, 0x02, 0x00]) + bytes([0x03, 0x00, 0x81, 0x05, 0x00, 0x01])
        # g32v1, qualifier 0x17, count 1: index(1) + flag(1) + value(4)
        apdu += bytes([32, 1, 0x17, 0x01]) + bytes([0x04, 0x01, 0x2A, 0x00, 0x00, 0x00])

        response = ApplicationResponse.from_bytes(apdu)

        assert [(h.group, h.variation, h.count) for h in response.objects] == [
            (2, 1, 2),
            (32, 1, 1),
        ]
        g32 = response.objects[1]
        assert response.raw_data[g32.data_offset : g32.data_offset + 6] == bytes(
            [0x04, 0x01, 0x2A, 0x00, 0x00, 0x00]
        )

    def test_crob_request_header(self):
        """A control request with 0x28 carries a 2-octet count before the 2-octet index."""
        header = ObjectHeader(
            group=12, variation=1, qualifier=0x28, count=1, data=bytes([0x05, 0x00]) + bytes(11)
        )
        assert header.to_bytes()[:7] == bytes([12, 1, 0x28, 0x01, 0x00, 0x05, 0x00])
