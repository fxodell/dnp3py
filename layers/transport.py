"""
DNP3 Transport Layer (Transport Function) implementation.

The Transport Layer handles segmentation of Application Layer messages
into smaller fragments suitable for the Data Link Layer.

Transport Header (1 byte):
    - Bit 7 (FIN): Final segment flag
    - Bit 6 (FIR): First segment flag
    - Bits 5-0: Sequence number (0-63)

Maximum segment payload: 249 bytes (250 - 1 byte header)
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

from dnp3_driver.core.exceptions import DNP3FrameError


# Transport layer constants
MAX_SEGMENT_PAYLOAD = 249  # Max bytes per segment (250 - 1 header byte)
SEQUENCE_MASK = 0x3F       # 6-bit sequence number
FIR_FLAG = 0x40            # First segment flag
FIN_FLAG = 0x80            # Final segment flag
MAX_MESSAGE_SIZE = 65536   # Maximum reassembled message size (64KB protection limit)


@dataclass
class TransportSegment:
    """Represents a DNP3 transport layer segment."""

    sequence: int
    is_first: bool
    is_final: bool
    payload: bytes

    @property
    def header(self) -> int:
        """Build the transport header byte."""
        h = self.sequence & SEQUENCE_MASK
        if self.is_first:
            h |= FIR_FLAG
        if self.is_final:
            h |= FIN_FLAG
        return h

    def to_bytes(self) -> bytes:
        """Convert segment to bytes for transmission."""
        return bytes([self.header]) + self.payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "TransportSegment":
        """
        Parse a transport segment from bytes.

        Args:
            data: Raw segment bytes (header + payload)

        Returns:
            Parsed TransportSegment

        Raises:
            DNP3FrameError: If data is empty
        """
        if len(data) < 1:
            raise DNP3FrameError("Transport segment data too short")

        header = data[0]
        sequence = header & SEQUENCE_MASK
        is_first = bool(header & FIR_FLAG)
        is_final = bool(header & FIN_FLAG)
        payload = data[1:]

        return cls(sequence, is_first, is_final, payload)

    def __repr__(self) -> str:
        flags = []
        if self.is_first:
            flags.append("FIR")
        if self.is_final:
            flags.append("FIN")
        flag_str = "|".join(flags) if flags else "none"
        return f"TransportSegment(seq={self.sequence}, flags={flag_str}, len={len(self.payload)})"


class TransportLayer:
    """
    DNP3 Transport Layer encoder/decoder.

    Handles segmentation of application layer messages and
    reassembly of received segments.
    """

    def __init__(self):
        """Initialize Transport Layer."""
        self._tx_sequence = 0
        self._rx_buffer: bytearray = bytearray()
        self._rx_expected_sequence: Optional[int] = None
        self._rx_started = False

    def segment(self, apdu: bytes, max_payload: int = MAX_SEGMENT_PAYLOAD) -> List[bytes]:
        """
        Segment an Application Protocol Data Unit (APDU) for transmission.

        Args:
            apdu: Application layer data to segment
            max_payload: Maximum payload per segment

        Returns:
            List of transport layer segments (as bytes)
        """
        if len(apdu) == 0:
            # Empty APDU - single segment with FIR and FIN
            segment = TransportSegment(
                sequence=self._tx_sequence,
                is_first=True,
                is_final=True,
                payload=b"",
            )
            self._tx_sequence = (self._tx_sequence + 1) & SEQUENCE_MASK
            return [segment.to_bytes()]

        segments = []
        offset = 0
        total_length = len(apdu)

        while offset < total_length:
            remaining = total_length - offset
            payload_size = min(remaining, max_payload)
            payload = apdu[offset:offset + payload_size]

            is_first = (offset == 0)
            is_final = (offset + payload_size >= total_length)

            segment = TransportSegment(
                sequence=self._tx_sequence,
                is_first=is_first,
                is_final=is_final,
                payload=payload,
            )

            segments.append(segment.to_bytes())
            self._tx_sequence = (self._tx_sequence + 1) & SEQUENCE_MASK
            offset += payload_size

        return segments

    def reassemble(self, segment_data: bytes) -> Tuple[Optional[bytes], bool]:
        """
        Process a received transport segment and attempt reassembly.

        Args:
            segment_data: Raw segment bytes from data link layer

        Returns:
            Tuple of (reassembled_apdu or None, is_complete)
            - If reassembly is complete, returns (apdu, True)
            - If more segments needed, returns (None, False)

        Raises:
            DNP3FrameError: If segment is out of sequence, malformed, or exceeds size limit
        """
        segment = TransportSegment.from_bytes(segment_data)

        # Handle first segment
        if segment.is_first:
            self._rx_buffer = bytearray(segment.payload)
            self._rx_expected_sequence = (segment.sequence + 1) & SEQUENCE_MASK
            self._rx_started = True

            if segment.is_final:
                # Single segment message
                result = bytes(self._rx_buffer)
                self._reset_rx()
                return result, True

            return None, False

        # Handle continuation segment
        if not self._rx_started:
            raise DNP3FrameError("Received continuation segment without first segment")

        if segment.sequence != self._rx_expected_sequence:
            self._reset_rx()
            raise DNP3FrameError(
                f"Sequence mismatch: expected {self._rx_expected_sequence}, "
                f"got {segment.sequence}"
            )

        # Check message size limit before extending buffer
        new_size = len(self._rx_buffer) + len(segment.payload)
        if new_size > MAX_MESSAGE_SIZE:
            self._reset_rx()
            raise DNP3FrameError(
                f"Reassembled message exceeds size limit: {new_size} > {MAX_MESSAGE_SIZE}"
            )

        self._rx_buffer.extend(segment.payload)
        self._rx_expected_sequence = (segment.sequence + 1) & SEQUENCE_MASK

        if segment.is_final:
            result = bytes(self._rx_buffer)
            self._reset_rx()
            return result, True

        return None, False

    def _reset_rx(self) -> None:
        """Reset receive state."""
        self._rx_buffer = bytearray()
        self._rx_expected_sequence = None
        self._rx_started = False

    def reset(self) -> None:
        """Reset both transmit and receive state."""
        self._tx_sequence = 0
        self._reset_rx()

    @property
    def tx_sequence(self) -> int:
        """Get current transmit sequence number."""
        return self._tx_sequence

    @property
    def is_receiving(self) -> bool:
        """Check if currently receiving a multi-segment message."""
        return self._rx_started

    @staticmethod
    def parse_header(header_byte: int) -> dict:
        """
        Parse a transport header byte.

        Args:
            header_byte: Single header byte

        Returns:
            Dictionary with sequence, is_first, is_final
        """
        return {
            "sequence": header_byte & SEQUENCE_MASK,
            "is_first": bool(header_byte & FIR_FLAG),
            "is_final": bool(header_byte & FIN_FLAG),
        }
