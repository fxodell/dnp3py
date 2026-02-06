"""Tests for DNP3 Transport Layer."""

import pytest
from dnp3py.layers.transport import (
    TransportLayer,
    TransportSegment,
    MAX_SEGMENT_PAYLOAD,
    MAX_MESSAGE_SIZE,
    FIR_FLAG,
    FIN_FLAG,
)
from dnp3py.core.exceptions import DNP3FrameError


class TestTransportSegment:
    """Tests for TransportSegment class."""

    def test_header_construction(self):
        """Test transport header byte construction."""
        segment = TransportSegment(sequence=5, is_first=True, is_final=False, payload=b"")
        header = segment.header
        assert header & 0x3F == 5  # Sequence
        assert header & FIR_FLAG  # FIR set
        assert not (header & FIN_FLAG)  # FIN not set

    def test_header_fin_flag(self):
        """Test FIN flag in header."""
        segment = TransportSegment(sequence=0, is_first=False, is_final=True, payload=b"")
        header = segment.header
        assert header & FIN_FLAG
        assert not (header & FIR_FLAG)

    def test_header_both_flags(self):
        """Test both FIR and FIN flags (single segment message)."""
        segment = TransportSegment(sequence=10, is_first=True, is_final=True, payload=b"")
        header = segment.header
        assert header & FIR_FLAG
        assert header & FIN_FLAG
        assert header & 0x3F == 10

    def test_to_bytes(self):
        """Test segment serialization."""
        payload = bytes([0x01, 0x02, 0x03])
        segment = TransportSegment(sequence=1, is_first=True, is_final=True, payload=payload)

        data = segment.to_bytes()
        assert len(data) == 4  # 1 header + 3 payload
        assert data[1:] == payload

    def test_from_bytes(self):
        """Test segment parsing."""
        # FIR=1, FIN=1, SEQ=5 -> 0xC5
        data = bytes([0xC5, 0xAA, 0xBB, 0xCC])
        segment = TransportSegment.from_bytes(data)

        assert segment.sequence == 5
        assert segment.is_first is True
        assert segment.is_final is True
        assert segment.payload == bytes([0xAA, 0xBB, 0xCC])

    def test_from_bytes_empty_payload(self):
        """Test parsing segment with only header."""
        data = bytes([0xC0])  # FIR=1, FIN=1, SEQ=0
        segment = TransportSegment.from_bytes(data)

        assert segment.is_first is True
        assert segment.is_final is True
        assert segment.payload == b""

    def test_from_bytes_too_short(self):
        """Test parsing empty data raises error."""
        with pytest.raises(DNP3FrameError):
            TransportSegment.from_bytes(b"")

    def test_from_bytes_too_long(self):
        """Test parsing segment exceeding max payload raises error."""
        # 1 header + 250 payload = 251 bytes (max is 250)
        data = bytes([0xC0]) + bytes(250)
        with pytest.raises(DNP3FrameError, match="too long"):
            TransportSegment.from_bytes(data)


class TestTransportLayer:
    """Tests for TransportLayer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.layer = TransportLayer()

    def test_segment_empty_apdu(self):
        """Test segmenting empty APDU."""
        segments = self.layer.segment(b"")
        assert len(segments) == 1
        # Should have FIR and FIN set
        header = segments[0][0]
        assert header & FIR_FLAG
        assert header & FIN_FLAG

    def test_segment_small_apdu(self):
        """Test segmenting APDU smaller than max payload."""
        apdu = bytes(100)
        segments = self.layer.segment(apdu)

        assert len(segments) == 1
        header = segments[0][0]
        assert header & FIR_FLAG
        assert header & FIN_FLAG
        assert segments[0][1:] == apdu

    def test_segment_large_apdu(self):
        """Test segmenting APDU larger than max payload."""
        # 500 bytes will need 3 segments (249 + 249 + 2)
        apdu = bytes(500)
        segments = self.layer.segment(apdu)

        assert len(segments) == 3

        # First segment
        assert segments[0][0] & FIR_FLAG
        assert not (segments[0][0] & FIN_FLAG)
        assert len(segments[0]) == MAX_SEGMENT_PAYLOAD + 1

        # Middle segment
        assert not (segments[1][0] & FIR_FLAG)
        assert not (segments[1][0] & FIN_FLAG)

        # Last segment
        assert not (segments[2][0] & FIR_FLAG)
        assert segments[2][0] & FIN_FLAG

    def test_segment_exact_payload_size(self):
        """Test segmenting APDU exactly equal to max payload."""
        apdu = bytes(MAX_SEGMENT_PAYLOAD)
        segments = self.layer.segment(apdu)

        assert len(segments) == 1
        assert len(segments[0]) == MAX_SEGMENT_PAYLOAD + 1

    def test_sequence_increment(self):
        """Test sequence number increments."""
        apdu = bytes(600)  # Multiple segments
        segments = self.layer.segment(apdu)

        seq0 = segments[0][0] & 0x3F
        seq1 = segments[1][0] & 0x3F
        seq2 = segments[2][0] & 0x3F

        assert seq1 == (seq0 + 1) & 0x3F
        assert seq2 == (seq1 + 1) & 0x3F

    def test_sequence_wrap(self):
        """Test sequence number wraps at 64."""
        self.layer._tx_sequence = 63
        segments = self.layer.segment(bytes(100))
        assert segments[0][0] & 0x3F == 63

        # Next segment should wrap to 0
        segments = self.layer.segment(bytes(100))
        assert segments[0][0] & 0x3F == 0

    def test_reassemble_single_segment(self):
        """Test reassembling single segment message."""
        apdu = bytes([0x01, 0x02, 0x03, 0x04])
        segments = self.layer.segment(apdu)

        result, complete = self.layer.reassemble(segments[0])
        assert complete is True
        assert result == apdu

    def test_reassemble_multi_segment(self):
        """Test reassembling multi-segment message."""
        apdu = bytes(500)
        segments = self.layer.segment(apdu)

        # First segment
        result, complete = self.layer.reassemble(segments[0])
        assert complete is False
        assert result is None

        # Middle segment
        result, complete = self.layer.reassemble(segments[1])
        assert complete is False
        assert result is None

        # Final segment
        result, complete = self.layer.reassemble(segments[2])
        assert complete is True
        assert result == apdu

    def test_reassemble_out_of_sequence(self):
        """Test that out-of-sequence segment raises error."""
        apdu = bytes(500)
        segments = self.layer.segment(apdu)

        # Start with first segment
        self.layer.reassemble(segments[0])

        # Skip to third segment (wrong sequence)
        with pytest.raises(DNP3FrameError):
            self.layer.reassemble(segments[2])

    def test_reassemble_duplicate_segment(self):
        """Test that duplicate segment is ignored."""
        apdu = bytes(300)
        segments = self.layer.segment(apdu)

        # Start with first segment
        result, complete = self.layer.reassemble(segments[0])
        assert complete is False
        assert result is None

        # Duplicate first segment should be ignored
        result, complete = self.layer.reassemble(segments[0])
        assert complete is False
        assert result is None

    def test_reassemble_continuation_without_first(self):
        """Test that continuation segment without first raises error."""
        # Create a middle segment (no FIR)
        segment = TransportSegment(sequence=1, is_first=False, is_final=False, payload=b"data")

        with pytest.raises(DNP3FrameError):
            self.layer.reassemble(segment.to_bytes())

    def test_reset(self):
        """Test layer reset."""
        apdu = bytes(100)
        self.layer.segment(apdu)
        self.layer.segment(apdu)  # Increment sequence

        assert self.layer._tx_sequence > 0

        self.layer.reset()
        assert self.layer._tx_sequence == 0
        assert self.layer._rx_started is False

    def test_round_trip(self):
        """Test segmentation and reassembly preserves data."""
        original_apdu = bytes(range(256)) * 3  # 768 bytes

        # Segment
        segments = self.layer.segment(original_apdu)

        # Reassemble
        self.layer.reset()  # Reset for receive side
        result = None
        for segment in segments:
            result, complete = self.layer.reassemble(segment)
            if complete:
                break

        assert result == original_apdu

    def test_parse_header(self):
        """Test header parsing utility."""
        header = 0xC5  # FIR=1, FIN=1, SEQ=5
        info = TransportLayer.parse_header(header)

        assert info["sequence"] == 5
        assert info["is_first"] is True
        assert info["is_final"] is True

    def test_segment_apdu_exceeds_max_message_size(self):
        """Test segmenting APDU larger than MAX_MESSAGE_SIZE raises error."""
        apdu = bytes(MAX_MESSAGE_SIZE + 1)
        with pytest.raises(DNP3FrameError, match="exceeds maximum message size"):
            self.layer.segment(apdu)

    def test_segment_invalid_max_payload(self):
        """Test segment with invalid max_payload raises error."""
        with pytest.raises(DNP3FrameError, match="max_payload"):
            self.layer.segment(bytes(10), max_payload=0)
        with pytest.raises(DNP3FrameError, match="max_payload"):
            self.layer.segment(bytes(10), max_payload=MAX_SEGMENT_PAYLOAD + 1)

    def test_parse_header_invalid(self):
        """Test parse_header with invalid input raises error."""
        with pytest.raises(DNP3FrameError, match="0-255"):
            TransportLayer.parse_header(256)
        with pytest.raises(DNP3FrameError, match="0-255"):
            TransportLayer.parse_header(-1)

    def test_is_receiving_property(self):
        """Test is_receiving property."""
        assert self.layer.is_receiving is False

        # Start receiving multi-segment message
        segment = TransportSegment(sequence=0, is_first=True, is_final=False, payload=b"data")
        self.layer.reassemble(segment.to_bytes())

        assert self.layer.is_receiving is True

    def test_reassemble_message_size_limit(self):
        """Test message size limit protection during reassembly."""
        from dnp3py.layers.transport import MAX_MESSAGE_SIZE

        # Start with first segment
        first_segment = TransportSegment(
            sequence=0,
            is_first=True,
            is_final=False,
            payload=b"x" * 249,  # Max segment payload
        )
        self.layer.reassemble(first_segment.to_bytes())

        # Keep adding segments until we exceed the limit
        seq = 1
        # Fill buffer close to limit
        while len(self.layer._rx_buffer) < MAX_MESSAGE_SIZE - 249:
            continuation = TransportSegment(
                sequence=seq & 0x3F,
                is_first=False,
                is_final=False,
                payload=b"x" * 249,
            )
            self.layer.reassemble(continuation.to_bytes())
            seq += 1

        # Next segment should exceed limit
        oversized_segment = TransportSegment(
            sequence=seq & 0x3F,
            is_first=False,
            is_final=False,
            payload=b"x" * 249,
        )

        with pytest.raises(DNP3FrameError, match="exceeds size limit"):
            self.layer.reassemble(oversized_segment.to_bytes())

    def test_reassemble_timeout(self):
        """Test reassembly timeout handling."""
        apdu = bytes(300)
        segments = self.layer.segment(apdu)

        # Start receiving with a short timeout
        self.layer.reassemble(segments[0], timeout_seconds=0.01)

        # Simulate timeout expiry
        self.layer._rx_start_time -= 1.0

        with pytest.raises(DNP3FrameError, match="timeout"):
            self.layer.reassemble(segments[1], timeout_seconds=0.01)
