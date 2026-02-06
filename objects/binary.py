"""
DNP3 Binary Input and Output objects.

Binary objects represent two-state (on/off) devices such as:
- Circuit breakers
- Switches
- Relays
- Alarms
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import IntFlag
import struct

from dnp3py.core.config import ControlCode, ControlStatus


class BinaryFlags(IntFlag):
    """Flags byte for binary objects."""

    ONLINE = 0x01           # Point is online
    RESTART = 0x02          # Point has been restarted
    COMM_LOST = 0x04        # Communication lost
    REMOTE_FORCED = 0x08    # Value forced by remote
    LOCAL_FORCED = 0x10     # Value forced by local
    CHATTER_FILTER = 0x20   # Chatter filter active
    RESERVED = 0x40         # Reserved
    STATE = 0x80            # Binary state (0=OFF, 1=ON)


@dataclass
class BinaryInput:
    """
    DNP3 Binary Input (Group 1).

    Represents the state of a two-state input device.
    """

    index: int
    value: bool
    flags: int = BinaryFlags.ONLINE
    timestamp: Optional[int] = None  # Milliseconds since epoch

    @property
    def is_online(self) -> bool:
        """Check if point is online."""
        return bool(self.flags & BinaryFlags.ONLINE)

    @property
    def has_restart(self) -> bool:
        """Check if point has been restarted."""
        return bool(self.flags & BinaryFlags.RESTART)

    @property
    def comm_lost(self) -> bool:
        """Check if communication is lost."""
        return bool(self.flags & BinaryFlags.COMM_LOST)

    @classmethod
    def from_bytes(cls, data: bytes, index: int, variation: int = 2) -> "BinaryInput":
        """
        Parse binary input from bytes.

        Args:
            data: Raw bytes
            index: Point index
            variation: Object variation (1, 2 for Group 1; 1, 2, 3 for Group 2 events)

        Returns:
            Parsed BinaryInput

        Supported variations:
            Group 1 (Binary Input):
                - Variation 1: Packed format (1 bit per point)
                - Variation 2: With flags (1 byte)

            Group 2 (Binary Input Event):
                - Variation 1: Without time (1 byte flags)
                - Variation 2: With absolute time (1 byte flags + 6 bytes time)
                - Variation 3: With relative time (1 byte flags + 2 bytes time)
        """
        timestamp = None

        if variation == 1:
            # Packed format (Group 1 Var 1) - single bit
            if len(data) < 1:
                raise ValueError("Insufficient data for binary input variation 1: need 1 byte")
            value = bool(data[0] & 0x01)
            flags = BinaryFlags.ONLINE
        elif variation == 2:
            # With flags format (Group 1/2 Var 2)
            # Or event with absolute time (Group 2 Var 2)
            if len(data) < 1:
                raise ValueError("Insufficient data for binary input variation 2")
            flags = data[0]
            value = bool(flags & BinaryFlags.STATE)

            # Check for timestamp (Group 2 Var 2: 1 + 6 = 7 bytes)
            if len(data) >= 7:
                # 48-bit timestamp in milliseconds since epoch (little-endian)
                timestamp = int.from_bytes(data[1:7], "little")
        elif variation == 3:
            # Event with relative time (Group 2 Var 3: 1 + 2 = 3 bytes)
            if len(data) < 3:
                raise ValueError("Insufficient data for binary input event variation 3")
            flags = data[0]
            value = bool(flags & BinaryFlags.STATE)
            # 16-bit relative timestamp in milliseconds
            timestamp = int.from_bytes(data[1:3], "little")
        else:
            raise ValueError(f"Unsupported binary input variation: {variation}")

        return cls(index=index, value=value, flags=flags, timestamp=timestamp)

    def to_bytes(self, variation: int = 2) -> bytes:
        """Serialize to bytes.

        Args:
            variation: Object variation to serialize as

        Returns:
            Serialized bytes

        Supported variations:
            1: Packed format (1 byte with LSB as value)
            2: With flags (1 byte) or with absolute time (7 bytes if timestamp set)
            3: With flags and relative time (3 bytes)
        """
        if variation == 1:
            return bytes([0x01 if self.value else 0x00])
        elif variation == 2:
            flags = self.flags
            if self.value:
                flags |= BinaryFlags.STATE
            else:
                flags &= ~BinaryFlags.STATE

            result = bytearray([flags])

            # Include timestamp if present (for events)
            if self.timestamp is not None:
                ts = int(self.timestamp)
                if ts < 0 or ts > (1 << 48) - 1:
                    raise ValueError(
                        f"Timestamp for variation 2 must be 0 to 2^48-1, got {self.timestamp}"
                    )
                result.extend(ts.to_bytes(6, "little"))

            return bytes(result)
        elif variation == 3:
            # Event with relative time
            flags = self.flags
            if self.value:
                flags |= BinaryFlags.STATE
            else:
                flags &= ~BinaryFlags.STATE

            result = bytearray([flags])

            # 16-bit relative timestamp
            ts = int(self.timestamp) if self.timestamp is not None else 0
            if ts < 0 or ts > 0xFFFF:
                raise ValueError(
                    f"Relative timestamp for variation 3 must be 0 to 65535, got {self.timestamp}"
                )
            result.extend(ts.to_bytes(2, "little"))

            return bytes(result)
        else:
            raise ValueError(f"Unsupported binary input variation: {variation}")

    def __repr__(self) -> str:
        state = "ON" if self.value else "OFF"
        online = "online" if self.is_online else "offline"
        ts_str = f", ts={self.timestamp}" if self.timestamp is not None else ""
        return f"BinaryInput(idx={self.index}, {state}, {online}{ts_str})"


@dataclass
class BinaryOutput:
    """
    DNP3 Binary Output (Group 10).

    Represents the state of a two-state output device.
    """

    index: int
    value: bool
    flags: int = BinaryFlags.ONLINE

    @classmethod
    def from_bytes(cls, data: bytes, index: int, variation: int = 2) -> "BinaryOutput":
        """Parse binary output from bytes.

        Raises:
            ValueError: If data is too short or variation is unsupported.
        """
        if variation == 1:
            if len(data) < 1:
                raise ValueError("Insufficient data for binary output variation 1: need 1 byte")
            value = bool(data[0] & 0x01)
            flags = BinaryFlags.ONLINE
        elif variation == 2:
            if len(data) < 1:
                raise ValueError("Insufficient data for binary output variation 2: need 1 byte")
            flags = data[0]
            value = bool(flags & BinaryFlags.STATE)
        else:
            raise ValueError(f"Unsupported variation: {variation}")

        return cls(index=index, value=value, flags=flags)

    def to_bytes(self, variation: int = 2) -> bytes:
        """Serialize to bytes."""
        if variation == 1:
            return bytes([0x01 if self.value else 0x00])
        elif variation == 2:
            flags = self.flags
            if self.value:
                flags |= BinaryFlags.STATE
            else:
                flags &= ~BinaryFlags.STATE
            return bytes([flags])
        else:
            raise ValueError(f"Unsupported variation: {variation}")

    def __repr__(self) -> str:
        state = "ON" if self.value else "OFF"
        return f"BinaryOutput(idx={self.index}, {state})"


@dataclass
class BinaryOutputCommand:
    """
    DNP3 Control Relay Output Block (CROB) - Group 12.

    Used to command binary output points.
    """

    index: int
    control_code: int = ControlCode.LATCH_ON
    count: int = 1
    on_time: int = 0       # Milliseconds for pulse on
    off_time: int = 0      # Milliseconds for pulse off
    status: int = ControlStatus.SUCCESS

    def __post_init__(self) -> None:
        """Validate control code combinations."""
        base_op = self.control_code & 0x0F
        allowed_base_ops = {
            ControlCode.NUL,
            ControlCode.PULSE_ON,
            ControlCode.PULSE_OFF,
            ControlCode.LATCH_ON,
            ControlCode.LATCH_OFF,
        }
        if base_op not in allowed_base_ops:
            raise ValueError(f"Invalid CROB base control code: 0x{base_op:02X}")

        allowed_flags = (
            ControlCode.QUEUE |
            ControlCode.CLEAR |
            ControlCode.TRIP_CLOSE_TRIP |
            ControlCode.TRIP_CLOSE_CLOSE
        )
        if self.control_code & ~allowed_flags & 0xF0:
            raise ValueError(f"Invalid CROB control flag bits: 0x{self.control_code:02X}")

        if (self.control_code & 0xC0) == 0xC0:
            raise ValueError("Invalid CROB control code: TRIP and CLOSE both set")

    @property
    def operation(self) -> str:
        """Get human-readable operation name."""
        op = self.control_code & 0x0F
        ops = {
            ControlCode.NUL: "NUL",
            ControlCode.PULSE_ON: "PULSE_ON",
            ControlCode.PULSE_OFF: "PULSE_OFF",
            ControlCode.LATCH_ON: "LATCH_ON",
            ControlCode.LATCH_OFF: "LATCH_OFF",
        }
        return ops.get(op, f"0x{op:02X}")

    @classmethod
    def latch_on(cls, index: int) -> "BinaryOutputCommand":
        """Create a latch-on command."""
        return cls(index=index, control_code=ControlCode.LATCH_ON)

    @classmethod
    def latch_off(cls, index: int) -> "BinaryOutputCommand":
        """Create a latch-off command."""
        return cls(index=index, control_code=ControlCode.LATCH_OFF)

    @classmethod
    def pulse_on(cls, index: int, on_time: int, off_time: int = 0, count: int = 1) -> "BinaryOutputCommand":
        """Create a pulse-on command."""
        return cls(
            index=index,
            control_code=ControlCode.PULSE_ON,
            count=count,
            on_time=on_time,
            off_time=off_time,
        )

    @classmethod
    def pulse_off(cls, index: int, on_time: int = 0, off_time: int = 0, count: int = 1) -> "BinaryOutputCommand":
        """Create a pulse-off command."""
        return cls(
            index=index,
            control_code=ControlCode.PULSE_OFF,
            count=count,
            on_time=on_time,
            off_time=off_time,
        )

    @classmethod
    def trip(cls, index: int) -> "BinaryOutputCommand":
        """Create a trip command (for breakers/switches)."""
        return cls(index=index, control_code=ControlCode.TRIP_CLOSE_TRIP | ControlCode.LATCH_ON)

    @classmethod
    def close(cls, index: int) -> "BinaryOutputCommand":
        """Create a close command (for breakers/switches)."""
        return cls(index=index, control_code=ControlCode.TRIP_CLOSE_CLOSE | ControlCode.LATCH_ON)

    def to_bytes(self) -> bytes:
        """Serialize to bytes (Group 12, Variation 1 format).

        Raises:
            ValueError: If count, on_time, off_time, or status is out of range.
        """
        if not 0 <= self.count <= 255:
            raise ValueError(f"count must be 0-255, got {self.count}")
        if self.on_time < 0:
            raise ValueError(f"on_time must be >= 0, got {self.on_time}")
        if self.off_time < 0:
            raise ValueError(f"off_time must be >= 0, got {self.off_time}")
        if not 0 <= self.status <= 255:
            raise ValueError(f"status must be 0-255, got {self.status}")
        return struct.pack(
            "<BBIIB",  # Little-endian: byte, byte, uint32, uint32, byte
            self.control_code,
            self.count,
            self.on_time,
            self.off_time,
            self.status,
        )

    @classmethod
    def from_bytes(cls, data: bytes, index: int) -> "BinaryOutputCommand":
        """Parse CROB from bytes.

        Raises:
            ValueError: If data is too short or parsed count/status are out of range.
        """
        if len(data) < 11:
            raise ValueError(f"CROB data too short: {len(data)} < 11")

        control_code, count, on_time, off_time, status = struct.unpack("<BBIIB", data[:11])

        if not 0 <= count <= 255:
            raise ValueError(f"CROB count must be 0-255, got {count}")
        if not 0 <= status <= 255:
            raise ValueError(f"CROB status must be 0-255, got {status}")

        return cls(
            index=index,
            control_code=control_code,
            count=count,
            on_time=on_time,
            off_time=off_time,
            status=status,
        )

    def __repr__(self) -> str:
        return f"BinaryOutputCommand(idx={self.index}, op={self.operation}, status={self.status})"


def parse_binary_inputs(
    data: bytes,
    start_index: int,
    count: int,
    variation: int,
) -> List[BinaryInput]:
    """
    Parse multiple binary inputs from response data.

    Args:
        data: Raw data bytes
        start_index: Starting point index
        count: Number of points
        variation: Object variation

    Returns:
        List of BinaryInput objects

    Raises:
        ValueError: If variation is unsupported or count/start_index is negative.

    Supported variations:
        Group 1 (Binary Input):
            - Variation 1: Packed format (1 bit per point)
            - Variation 2: With flags (1 byte per point)

        Group 2 (Binary Input Event):
            - Variation 1: Without time (1 byte per point)
            - Variation 2: With absolute time (7 bytes per point)
            - Variation 3: With relative time (3 bytes per point)
    """
    if count < 0:
        raise ValueError(f"count must be >= 0, got {count}")
    if start_index < 0:
        raise ValueError(f"start_index must be >= 0, got {start_index}")

    inputs = []
    offset = 0

    # Size per object based on variation
    # Variation 1 is packed (handled specially), variations 2/3 are fixed sizes
    variation_sizes = {
        1: 1,  # Flags only (or packed - handled separately)
        2: 7,  # Flags + 48-bit absolute time (for events) or just flags (for static)
        3: 3,  # Flags + 16-bit relative time
    }

    if variation == 1:
        # Packed format - 8 bits per byte (Group 1 Var 1)
        # OR 1 byte flags per point (Group 2 Var 1)
        # We assume packed format here (Group 1), as Group 2 Var 1 uses 1 byte per point
        for i in range(count):
            byte_idx = i // 8
            bit_idx = i % 8

            if byte_idx >= len(data):
                break

            value = bool(data[byte_idx] & (1 << bit_idx))
            inputs.append(BinaryInput(
                index=start_index + i,
                value=value,
                flags=BinaryFlags.ONLINE,
            ))
    elif variation == 2:
        # Could be Group 1 Var 2 (1 byte) or Group 2 Var 2 (7 bytes)
        # Determine size based on data available
        obj_size = 1  # Default for Group 1 Var 2

        # Check if we have enough data for event format (7 bytes per point)
        if len(data) >= count * 7:
            obj_size = 7  # Group 2 Var 2 with timestamp
        elif len(data) >= count * 1:
            obj_size = 1  # Group 1 Var 2 without timestamp

        for i in range(count):
            if offset + obj_size > len(data):
                break
            inputs.append(BinaryInput.from_bytes(
                data[offset:offset + obj_size], start_index + i, variation
            ))
            offset += obj_size
    elif variation == 3:
        # Group 2 Var 3: Event with relative time (3 bytes per point)
        obj_size = 3
        for i in range(count):
            if offset + obj_size > len(data):
                break
            inputs.append(BinaryInput.from_bytes(
                data[offset:offset + obj_size], start_index + i, variation
            ))
            offset += obj_size
    else:
        raise ValueError(f"Unsupported binary input variation: {variation}")

    return inputs


def parse_binary_outputs(
    data: bytes,
    start_index: int,
    count: int,
    variation: int,
) -> List[BinaryOutput]:
    """
    Parse multiple binary outputs from response data.

    Args:
        data: Raw data bytes
        start_index: Starting point index
        count: Number of points
        variation: Object variation

    Returns:
        List of BinaryOutput objects

    Raises:
        ValueError: If variation is unsupported or count/start_index is negative.
    """
    if count < 0:
        raise ValueError(f"count must be >= 0, got {count}")
    if start_index < 0:
        raise ValueError(f"start_index must be >= 0, got {start_index}")

    outputs = []
    offset = 0

    if variation == 1:
        # Packed format - 8 bits per byte
        for i in range(count):
            byte_idx = i // 8
            bit_idx = i % 8

            if byte_idx >= len(data):
                break

            value = bool(data[byte_idx] & (1 << bit_idx))
            outputs.append(BinaryOutput(
                index=start_index + i,
                value=value,
                flags=BinaryFlags.ONLINE,
            ))
    elif variation == 2:
        # With flags - 1 byte per point
        for i in range(count):
            if offset >= len(data):
                break
            outputs.append(BinaryOutput.from_bytes(data[offset:offset + 1], start_index + i, variation))
            offset += 1
    else:
        raise ValueError(f"Unsupported binary output variation: {variation}")

    return outputs
