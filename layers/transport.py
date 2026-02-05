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
import time
from typing import List, Optional, Tuple

from pydnp3.core.exceptions import DNP3FrameError


# Transport layer constants
MAX_SEGMENT_PAYLOAD = 249  # Max bytes per segment (250 - 1 header byte)
SEQUENCE_MASK = 0x3F       # 6-bit sequence number (0-63)
SEQUENCE_MODULUS = 64      # Sequence numbers wrap at 64
FIR_FLAG = 0x40            # First segment flag
FIN_FLAG = 0x80            # Final segment flag
MAX_MESSAGE_SIZE = 65536   # Maximum reassembled message size (64KB protection limit)
DEFAULT_REASSEMBLY_TIMEOUT = 5.0  # Default timeout for multi-segment reassembly


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
            DNP3FrameError: If data is empty or segment is invalid
        """
        if len(data) < 1:
            raise DNP3FrameError("Transport segment data too short")

        header = data[0]
        sequence = header & SEQUENCE_MASK
        is_first = bool(header & FIR_FLAG)
        is_final = bool(header & FIN_FLAG)
        payload = data[1:]

        # Validate: a segment cannot have neither FIR nor FIN set and be empty
        # (would indicate a corrupt or malformed segment in the middle of nowhere)
        # Note: Single-segment messages must have both FIR and FIN set

        return cls(sequence, is_first, is_final, payload)

    def validate(self) -> None:
        """
        Validate the segment structure.

        Raises:
            DNP3FrameError: If segment is structurally invalid
        """
        # Sequence must be in valid range (0-63)
        if not 0 <= self.sequence <= SEQUENCE_MASK:
            raise DNP3FrameError(
                f"Invalid sequence number: {self.sequence}, must be 0-63"
            )

        # Payload size check
        if len(self.payload) > MAX_SEGMENT_PAYLOAD:
            raise DNP3FrameError(
                f"Segment payload exceeds maximum: {len(self.payload)} > {MAX_SEGMENT_PAYLOAD}"
            )

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
        self._rx_last_sequence: Optional[int] = None
        self._rx_start_time: Optional[float] = None
        self._rx_timeout_seconds: Optional[float] = None

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

    def reassemble(
        self,
        segment_data: bytes,
        timeout_seconds: Optional[float] = None,
    ) -> Tuple[Optional[bytes], bool]:
        """
        Process a received transport segment and attempt reassembly.

        Args:
            segment_data: Raw segment bytes from data link layer
            timeout_seconds: Timeout for multi-segment reassembly (uses default if None)

        Returns:
            Tuple of (reassembled_apdu or None, is_complete)
            - If reassembly is complete, returns (apdu, True)
            - If more segments needed, returns (None, False)

        Raises:
            DNP3FrameError: If segment is out of sequence, malformed, or exceeds size limit
        """
        segment = TransportSegment.from_bytes(segment_data)

        # Validate the segment
        segment.validate()

        # Use default timeout if not specified
        if timeout_seconds is None:
            timeout_seconds = DEFAULT_REASSEMBLY_TIMEOUT

        # Handle first segment
        if segment.is_first:
            # If we were already receiving, this resets the reassembly
            # (new message starting)
            self._rx_buffer = bytearray(segment.payload)
            self._rx_expected_sequence = (segment.sequence + 1) & SEQUENCE_MASK
            self._rx_started = True
            self._rx_last_sequence = segment.sequence
            self._rx_start_time = time.monotonic()
            self._rx_timeout_seconds = timeout_seconds

            if segment.is_final:
                # Single segment message (both FIR and FIN set)
                result = bytes(self._rx_buffer)
                self._reset_rx()
                return result, True

            return None, False

        # Handle continuation segment (no FIR flag)
        if not self._rx_started:
            # Received a continuation without a first segment
            # This could happen if we missed the first segment or started listening mid-stream
            raise DNP3FrameError(
                "Received continuation segment without first segment "
                f"(seq={segment.sequence}, FIN={segment.is_final})"
            )

        # Check for reassembly timeout
        if self._rx_start_time is not None and self._rx_timeout_seconds is not None:
            elapsed = time.monotonic() - self._rx_start_time
            if elapsed > self._rx_timeout_seconds:
                self._reset_rx()
                raise DNP3FrameError(
                    f"Reassembly timeout exceeded: {elapsed:.2f}s > {self._rx_timeout_seconds}s"
                )

        # Handle duplicate segment (same sequence as last received)
        if self._rx_last_sequence is not None and segment.sequence == self._rx_last_sequence:
            # Duplicate segment (likely retransmission) - ignore silently
            return None, False

        # Validate sequence number
        # Expected sequence should match, accounting for wraparound at 64
        if segment.sequence != self._rx_expected_sequence:
            expected = self._rx_expected_sequence
            actual = segment.sequence
            self._reset_rx()
            raise DNP3FrameError(
                f"Sequence mismatch: expected {expected}, got {actual}. "
                f"Possible lost segment or out-of-order delivery."
            )

        # Check message size limit BEFORE extending buffer (DoS protection)
        new_size = len(self._rx_buffer) + len(segment.payload)
        if new_size > MAX_MESSAGE_SIZE:
            self._reset_rx()
            raise DNP3FrameError(
                f"Reassembled message exceeds size limit: {new_size} > {MAX_MESSAGE_SIZE} bytes"
            )

        # Append payload and update state
        self._rx_buffer.extend(segment.payload)
        # Sequence wraps at 64 (6-bit counter)
        self._rx_expected_sequence = (segment.sequence + 1) & SEQUENCE_MASK
        self._rx_last_sequence = segment.sequence

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
        self._rx_last_sequence = None
        self._rx_start_time = None
        self._rx_timeout_seconds = None

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
