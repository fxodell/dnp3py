"""
DNP3 Counter objects.

Counter objects represent accumulated count values such as:
- Kilowatt-hours
- Pulse counts
- Transaction counts
"""

import struct
from dataclasses import dataclass
from enum import IntFlag
from typing import Optional

# Required bytes per object for Counter.from_bytes and parse_counters (variation -> size)
COUNTER_VARIATION_SIZES = {1: 5, 2: 3, 3: 5, 4: 3, 5: 4, 6: 2, 7: 4, 8: 2}


class CounterFlags(IntFlag):
    """Flags byte for counter objects."""

    ONLINE = 0x01  # Point is online
    RESTART = 0x02  # Point has been restarted
    COMM_LOST = 0x04  # Communication lost
    REMOTE_FORCED = 0x08  # Value forced by remote
    LOCAL_FORCED = 0x10  # Value forced by local
    ROLLOVER = 0x20  # Counter has rolled over
    DISCONTINUITY = 0x40  # Value discontinuity
    RESERVED = 0x80  # Reserved


@dataclass
class Counter:
    """
    DNP3 Counter (Group 20).

    Represents an accumulated count value.
    """

    index: int
    value: int
    flags: int = CounterFlags.ONLINE
    timestamp: Optional[int] = None  # Milliseconds since epoch

    @property
    def is_online(self) -> bool:
        """Check if point is online."""
        return bool(self.flags & CounterFlags.ONLINE)

    @property
    def has_rollover(self) -> bool:
        """Check if counter has rolled over."""
        return bool(self.flags & CounterFlags.ROLLOVER)

    @property
    def comm_lost(self) -> bool:
        """Check if communication is lost."""
        return bool(self.flags & CounterFlags.COMM_LOST)

    @classmethod
    def from_bytes(cls, data: bytes, index: int, variation: int = 1) -> "Counter":
        """
        Parse counter from bytes.

        Args:
            data: Raw bytes
            index: Point index
            variation: Object variation (1-8)

        Returns:
            Parsed Counter

        Raises:
            ValueError: If data is too short or variation is unsupported.
        """
        required = COUNTER_VARIATION_SIZES.get(variation)
        if required is None:
            raise ValueError(f"Unsupported variation: {variation}")
        if len(data) < required:
            raise ValueError(
                f"Insufficient data for counter variation {variation}: "
                f"need {required} bytes, got {len(data)}"
            )

        flags = CounterFlags.ONLINE
        value = 0

        if variation == 1:
            flags = data[0]
            value = struct.unpack("<I", data[1:5])[0]
        elif variation == 2:
            flags = data[0]
            value = struct.unpack("<H", data[1:3])[0]
        elif variation == 3:
            flags = data[0]
            value = struct.unpack("<i", data[1:5])[0]  # Signed for delta
        elif variation == 4:
            flags = data[0]
            value = struct.unpack("<h", data[1:3])[0]  # Signed for delta
        elif variation == 5:
            value = struct.unpack("<I", data[:4])[0]
        elif variation == 6:
            value = struct.unpack("<H", data[:2])[0]
        elif variation == 7:
            value = struct.unpack("<i", data[:4])[0]
        elif variation == 8:
            value = struct.unpack("<h", data[:2])[0]

        return cls(index=index, value=value, flags=flags)

    def to_bytes(self, variation: int = 1) -> bytes:
        """Serialize to bytes.

        Args:
            variation: Object variation to serialize as

        Returns:
            Serialized bytes

        Raises:
            ValueError: If value is out of range for the specified variation
            TypeError: If value cannot be converted to int
        """
        try:
            val = int(self.value)
        except (TypeError, ValueError) as e:
            raise TypeError(
                f"Counter value must be an integer, got {type(self.value).__name__}"
            ) from e

        result = bytearray()

        if variation == 1:
            if not 0 <= val <= 4294967295:
                raise ValueError(
                    f"Value {val} out of range for 32-bit unsigned counter (0-4294967295)"
                )
            result.append(self.flags)
            result.extend(struct.pack("<I", val))
        elif variation == 2:
            if not 0 <= val <= 65535:
                raise ValueError(f"Value {val} out of range for 16-bit unsigned counter (0-65535)")
            result.append(self.flags)
            result.extend(struct.pack("<H", val))
        elif variation == 3:
            if not -2147483648 <= val <= 2147483647:
                raise ValueError(f"Value {val} out of range for 32-bit signed delta")
            result.append(self.flags)
            result.extend(struct.pack("<i", val))
        elif variation == 4:
            if not -32768 <= val <= 32767:
                raise ValueError(f"Value {val} out of range for 16-bit signed delta")
            result.append(self.flags)
            result.extend(struct.pack("<h", val))
        elif variation == 5:
            if not 0 <= val <= 4294967295:
                raise ValueError(
                    f"Value {val} out of range for 32-bit unsigned counter (0-4294967295)"
                )
            result.extend(struct.pack("<I", val))
        elif variation == 6:
            if not 0 <= val <= 65535:
                raise ValueError(f"Value {val} out of range for 16-bit unsigned counter (0-65535)")
            result.extend(struct.pack("<H", val))
        elif variation == 7:
            if not -2147483648 <= val <= 2147483647:
                raise ValueError(f"Value {val} out of range for 32-bit signed delta")
            result.extend(struct.pack("<i", val))
        elif variation == 8:
            if not -32768 <= val <= 32767:
                raise ValueError(f"Value {val} out of range for 16-bit signed delta")
            result.extend(struct.pack("<h", val))
        else:
            raise ValueError(f"Unsupported counter variation: {variation}")

        return bytes(result)

    def __repr__(self) -> str:
        online = "online" if self.is_online else "offline"
        rollover = ", rollover" if self.has_rollover else ""
        return f"Counter(idx={self.index}, value={self.value}, {online}{rollover})"


@dataclass
class FrozenCounter:
    """
    DNP3 Frozen Counter (Group 21).

    Represents a frozen (snapshot) counter value.
    """

    index: int
    value: int
    flags: int = CounterFlags.ONLINE
    timestamp: Optional[int] = None

    @classmethod
    def from_bytes(cls, data: bytes, index: int, variation: int = 1) -> "FrozenCounter":
        """Parse frozen counter from bytes (same format as regular counter).

        Raises:
            ValueError: If data is too short or variation is unsupported (from Counter.from_bytes).
        """
        counter = Counter.from_bytes(data, index, variation)
        return cls(
            index=counter.index,
            value=counter.value,
            flags=counter.flags,
        )

    def to_bytes(self, variation: int = 1) -> bytes:
        """Serialize to bytes."""
        counter = Counter(
            index=self.index,
            value=self.value,
            flags=self.flags,
        )
        return counter.to_bytes(variation)

    def __repr__(self) -> str:
        return f"FrozenCounter(idx={self.index}, value={self.value})"


def parse_counters(
    data: bytes,
    start_index: int,
    count: int,
    variation: int,
) -> list[Counter]:
    """
    Parse multiple counters from response data.

    Args:
        data: Raw data bytes
        start_index: Starting point index
        count: Number of points
        variation: Object variation

    Returns:
        List of Counter objects

    Raises:
        ValueError: If variation is unsupported or count/start_index is negative.
    """
    if count < 0:
        raise ValueError(f"count must be >= 0, got {count}")
    if start_index < 0:
        raise ValueError(f"start_index must be >= 0, got {start_index}")

    obj_size = COUNTER_VARIATION_SIZES.get(variation)
    if obj_size is None:
        raise ValueError(f"Unsupported counter variation: {variation}")

    counters = []
    offset = 0

    for i in range(count):
        if offset + obj_size > len(data):
            break
        counters.append(
            Counter.from_bytes(data[offset : offset + obj_size], start_index + i, variation)
        )
        offset += obj_size

    return counters
