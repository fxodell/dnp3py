"""
DNP3 Counter objects.

Counter objects represent accumulated count values such as:
- Kilowatt-hours
- Pulse counts
- Transaction counts
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import IntFlag
import struct


class CounterFlags(IntFlag):
    """Flags byte for counter objects."""

    ONLINE = 0x01           # Point is online
    RESTART = 0x02          # Point has been restarted
    COMM_LOST = 0x04        # Communication lost
    REMOTE_FORCED = 0x08    # Value forced by remote
    LOCAL_FORCED = 0x10     # Value forced by local
    ROLLOVER = 0x20         # Counter has rolled over
    DISCONTINUITY = 0x40    # Value discontinuity
    RESERVED = 0x80         # Reserved


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
        """
        flags = CounterFlags.ONLINE
        value = 0

        if variation == 1:
            # 32-bit with flag
            flags = data[0]
            value = struct.unpack("<I", data[1:5])[0]
        elif variation == 2:
            # 16-bit with flag
            flags = data[0]
            value = struct.unpack("<H", data[1:3])[0]
        elif variation == 3:
            # 32-bit delta with flag
            flags = data[0]
            value = struct.unpack("<i", data[1:5])[0]  # Signed for delta
        elif variation == 4:
            # 16-bit delta with flag
            flags = data[0]
            value = struct.unpack("<h", data[1:3])[0]  # Signed for delta
        elif variation == 5:
            # 32-bit without flag
            value = struct.unpack("<I", data[:4])[0]
        elif variation == 6:
            # 16-bit without flag
            value = struct.unpack("<H", data[:2])[0]
        elif variation == 7:
            # 32-bit delta without flag
            value = struct.unpack("<i", data[:4])[0]
        elif variation == 8:
            # 16-bit delta without flag
            value = struct.unpack("<h", data[:2])[0]
        else:
            raise ValueError(f"Unsupported variation: {variation}")

        return cls(index=index, value=value, flags=flags)

    def to_bytes(self, variation: int = 1) -> bytes:
        """Serialize to bytes.

        Args:
            variation: Object variation to serialize as

        Returns:
            Serialized bytes

        Raises:
            ValueError: If value is out of range for the specified variation
        """
        result = bytearray()

        if variation == 1:
            # 32-bit unsigned with flag
            if not 0 <= self.value <= 4294967295:
                raise ValueError(
                    f"Value {self.value} out of range for 32-bit unsigned counter (0-4294967295)"
                )
            result.append(self.flags)
            result.extend(struct.pack("<I", self.value))
        elif variation == 2:
            # 16-bit unsigned with flag
            if not 0 <= self.value <= 65535:
                raise ValueError(
                    f"Value {self.value} out of range for 16-bit unsigned counter (0-65535)"
                )
            result.append(self.flags)
            result.extend(struct.pack("<H", self.value))
        elif variation == 3:
            # 32-bit signed delta with flag
            if not -2147483648 <= self.value <= 2147483647:
                raise ValueError(
                    f"Value {self.value} out of range for 32-bit signed delta"
                )
            result.append(self.flags)
            result.extend(struct.pack("<i", self.value))
        elif variation == 4:
            # 16-bit signed delta with flag
            if not -32768 <= self.value <= 32767:
                raise ValueError(
                    f"Value {self.value} out of range for 16-bit signed delta"
                )
            result.append(self.flags)
            result.extend(struct.pack("<h", self.value))
        elif variation == 5:
            # 32-bit unsigned without flag
            if not 0 <= self.value <= 4294967295:
                raise ValueError(
                    f"Value {self.value} out of range for 32-bit unsigned counter (0-4294967295)"
                )
            result.extend(struct.pack("<I", self.value))
        elif variation == 6:
            # 16-bit unsigned without flag
            if not 0 <= self.value <= 65535:
                raise ValueError(
                    f"Value {self.value} out of range for 16-bit unsigned counter (0-65535)"
                )
            result.extend(struct.pack("<H", self.value))
        elif variation == 7:
            # 32-bit signed delta without flag
            if not -2147483648 <= self.value <= 2147483647:
                raise ValueError(
                    f"Value {self.value} out of range for 32-bit signed delta"
                )
            result.extend(struct.pack("<i", self.value))
        elif variation == 8:
            # 16-bit signed delta without flag
            if not -32768 <= self.value <= 32767:
                raise ValueError(
                    f"Value {self.value} out of range for 16-bit signed delta"
                )
            result.extend(struct.pack("<h", self.value))
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
        """Parse frozen counter from bytes (same format as regular counter)."""
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
) -> List[Counter]:
    """
    Parse multiple counters from response data.

    Args:
        data: Raw data bytes
        start_index: Starting point index
        count: Number of points
        variation: Object variation

    Returns:
        List of Counter objects
    """
    # Size per object based on variation
    sizes = {1: 5, 2: 3, 3: 5, 4: 3, 5: 4, 6: 2, 7: 4, 8: 2}
    obj_size = sizes.get(variation)
    if obj_size is None:
        raise ValueError(f"Unsupported counter variation: {variation}")

    counters = []
    offset = 0

    for i in range(count):
        if offset + obj_size > len(data):
            break
        counters.append(Counter.from_bytes(data[offset:offset + obj_size], start_index + i, variation))
        offset += obj_size

    return counters
