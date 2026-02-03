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

from dnp3_driver.core.config import ControlCode, ControlStatus
from dnp3_driver.objects.groups import ObjectGroup, ObjectVariation


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
            variation: Object variation

        Returns:
            Parsed BinaryInput
        """
        if variation == 1:
            # Packed format - single bit
            value = bool(data[0] & 0x01)
            flags = BinaryFlags.ONLINE
        elif variation == 2:
            # With flags format
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
        online = "online" if self.is_online else "offline"
        return f"BinaryInput(idx={self.index}, {state}, {online})"


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
        """Parse binary output from bytes."""
        if variation == 1:
            value = bool(data[0] & 0x01)
            flags = BinaryFlags.ONLINE
        elif variation == 2:
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
        """Serialize to bytes (Group 12, Variation 1 format)."""
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
        """Parse CROB from bytes."""
        if len(data) < 11:
            raise ValueError(f"CROB data too short: {len(data)} < 11")

        control_code, count, on_time, off_time, status = struct.unpack("<BBIIB", data[:11])

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
    """
    inputs = []
    offset = 0

    if variation == 1:
        # Packed format - 8 bits per byte
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
        # With flags - 1 byte per point
        for i in range(count):
            if offset >= len(data):
                break
            inputs.append(BinaryInput.from_bytes(data[offset:offset + 1], start_index + i, variation))
            offset += 1
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
    """
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
