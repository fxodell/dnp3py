"""
DNP3 event object decoders (Groups 2, 11, 22 and 32).

An event variation does not share the layout of the static variation with
the same number: every event variation listed here starts with the flags
octet, then the value, then an optional time. For example g22v5 is a 32-bit
counter with flag and time (11 octets), while g20v5 is a 32-bit counter
without flag (4 octets).
"""

import struct
from typing import Union

from dnp3py.objects.analog import AnalogInput
from dnp3py.objects.binary import BinaryFlags, BinaryInput, BinaryOutput
from dnp3py.objects.counter import Counter

# (group, variation) -> (struct format of the value, or None for a binary
# state carried in the flags; octets of time after the value: 0, 2 for a
# relative time, 6 for an absolute DNP3 time)
EVENT_FORMATS: dict[tuple[int, int], tuple[Union[str, None], int]] = {
    # Binary Input Event
    (2, 1): (None, 0),
    (2, 2): (None, 6),
    (2, 3): (None, 2),
    # Binary Output Event
    (11, 1): (None, 0),
    (11, 2): (None, 6),
    # Counter Event (3, 4, 7 and 8 are the obsolete delta counters)
    (22, 1): ("<I", 0),
    (22, 2): ("<H", 0),
    (22, 3): ("<i", 0),
    (22, 4): ("<h", 0),
    (22, 5): ("<I", 6),
    (22, 6): ("<H", 6),
    (22, 7): ("<i", 6),
    (22, 8): ("<h", 6),
    # Analog Input Event
    (32, 1): ("<i", 0),
    (32, 2): ("<h", 0),
    (32, 3): ("<i", 6),
    (32, 4): ("<h", 6),
    (32, 5): ("<f", 0),
    (32, 6): ("<d", 0),
    (32, 7): ("<f", 6),
    (32, 8): ("<d", 6),
}

EVENT_GROUPS = frozenset(group for group, _ in EVENT_FORMATS)

Event = Union[BinaryInput, BinaryOutput, Counter, AnalogInput]


def event_size(group: int, variation: int) -> int:
    """
    Get the size in octets of one event object.

    Raises:
        ValueError: If the group and variation are not a supported event
    """
    fmt = EVENT_FORMATS.get((group, variation))
    if fmt is None:
        raise ValueError(f"Unsupported event object: group={group}, variation={variation}")
    value_format, time_size = fmt
    value_size = 0 if value_format is None else struct.calcsize(value_format)
    return 1 + value_size + time_size


def decode_event(group: int, variation: int, data: bytes, index: int) -> Event:
    """
    Decode one event object.

    Args:
        group: Object group (2, 11, 22 or 32)
        variation: Object variation
        data: The object's octets (without an index prefix)
        index: Point index

    Returns:
        BinaryInput (g2), BinaryOutput (g11), Counter (g22) or AnalogInput
        (g32), with timestamp set for variations that carry a time

    Raises:
        ValueError: If the event is unsupported or data is too short
    """
    size = event_size(group, variation)
    if len(data) < size:
        raise ValueError(
            f"Insufficient data for g{group}v{variation}: need {size} bytes, got {len(data)}"
        )
    value_format, time_size = EVENT_FORMATS[(group, variation)]
    flags = data[0]
    value_size = 0 if value_format is None else struct.calcsize(value_format)
    time_offset = 1 + value_size
    timestamp = (
        int.from_bytes(data[time_offset : time_offset + time_size], "little") if time_size else None
    )

    if value_format is None:
        state = bool(flags & BinaryFlags.STATE)
        if group == 2:
            return BinaryInput(index=index, value=state, flags=flags, timestamp=timestamp)
        return BinaryOutput(index=index, value=state, flags=flags, timestamp=timestamp)

    value = struct.unpack(value_format, data[1:time_offset])[0]
    if group == 22:
        return Counter(index=index, value=value, flags=flags, timestamp=timestamp)
    return AnalogInput(index=index, value=value, flags=flags, timestamp=timestamp)
