"""
DNP3 Object Group and Variation definitions.

DNP3 data objects are identified by Group and Variation numbers.
Groups identify the type of data (Binary Input, Analog Input, etc.)
Variations identify the specific format of the data.
"""

from enum import IntEnum
from typing import Optional


class ObjectGroup(IntEnum):
    """DNP3 object group numbers."""

    # Binary Input (BI)
    BINARY_INPUT = 1
    BINARY_INPUT_EVENT = 2

    # Double-bit Binary Input (DBI)
    DOUBLE_BIT_BINARY_INPUT = 3
    DOUBLE_BIT_BINARY_INPUT_EVENT = 4

    # Binary Output (BO)
    BINARY_OUTPUT = 10
    BINARY_OUTPUT_EVENT = 11
    CONTROL_RELAY_OUTPUT_BLOCK = 12
    BINARY_OUTPUT_COMMAND_EVENT = 13

    # Counter (CTR)
    COUNTER = 20
    FROZEN_COUNTER = 21
    COUNTER_EVENT = 22
    FROZEN_COUNTER_EVENT = 23

    # Analog Input (AI)
    ANALOG_INPUT = 30
    FROZEN_ANALOG_INPUT = 31
    ANALOG_INPUT_EVENT = 32
    FROZEN_ANALOG_INPUT_EVENT = 33
    ANALOG_INPUT_DEADBAND = 34

    # Analog Output (AO)
    ANALOG_OUTPUT = 40
    ANALOG_OUTPUT_STATUS = 40  # Alias for clarity
    ANALOG_OUTPUT_BLOCK = 41
    ANALOG_OUTPUT_EVENT = 42
    ANALOG_OUTPUT_COMMAND_EVENT = 43

    # Time and Date
    TIME_AND_DATE = 50
    TIME_AND_DATE_CTO = 51

    # Class Objects (for class-based polling)
    CLASS_OBJECTS = 60

    # File Transfer
    FILE_IDENTIFIER = 70
    FILE_AUTHENTICATION = 71

    # Internal Indications
    INTERNAL_INDICATIONS = 80

    # Device Attributes
    DEVICE_ATTRIBUTES = 0

    # Octet String
    OCTET_STRING = 110
    OCTET_STRING_EVENT = 111

    # Virtual Terminal
    VIRTUAL_TERMINAL_OUTPUT = 112
    VIRTUAL_TERMINAL_EVENT = 113

    # Authentication
    AUTHENTICATION = 120


class ObjectVariation(IntEnum):
    """Common object variations."""

    # Special variation
    ANY = 0  # Outstation chooses variation

    # Binary Input Variations (Group 1)
    BI_PACKED = 1  # Packed format (8 points per byte)
    BI_WITH_FLAGS = 2  # With flags (1 byte per point)

    # Binary Input Event Variations (Group 2)
    BIE_WITHOUT_TIME = 1
    BIE_WITH_ABSOLUTE_TIME = 2
    BIE_WITH_RELATIVE_TIME = 3

    # Binary Output Variations (Group 10)
    BO_PACKED = 1  # Packed format
    BO_WITH_FLAGS = 2  # With flags

    # CROB Variations (Group 12)
    CROB = 1  # Control Relay Output Block
    PCB = 2  # Pattern Control Block
    PM = 3  # Pattern Mask

    # Counter Variations (Group 20)
    CTR_32_WITH_FLAG = 1
    CTR_16_WITH_FLAG = 2
    CTR_32_DELTA_WITH_FLAG = 3
    CTR_16_DELTA_WITH_FLAG = 4
    CTR_32_WITHOUT_FLAG = 5
    CTR_16_WITHOUT_FLAG = 6
    CTR_32_DELTA_WITHOUT_FLAG = 7
    CTR_16_DELTA_WITHOUT_FLAG = 8

    # Analog Input Variations (Group 30)
    AI_32_WITH_FLAG = 1
    AI_16_WITH_FLAG = 2
    AI_32_WITHOUT_FLAG = 3
    AI_16_WITHOUT_FLAG = 4
    AI_FLOAT_WITH_FLAG = 5
    AI_DOUBLE_WITH_FLAG = 6

    # Analog Output Variations (Group 40)
    AO_32_WITH_FLAG = 1
    AO_16_WITH_FLAG = 2
    AO_FLOAT_WITH_FLAG = 3
    AO_DOUBLE_WITH_FLAG = 4

    # Analog Output Block Variations (Group 41)
    AOB_32 = 1
    AOB_16 = 2
    AOB_FLOAT = 3
    AOB_DOUBLE = 4

    # Class Object Variations (Group 60)
    CLASS_0 = 1  # All static data
    CLASS_1 = 2  # Class 1 events
    CLASS_2 = 3  # Class 2 events
    CLASS_3 = 4  # Class 3 events

    # Time Variations (Group 50)
    TIME_ABSOLUTE = 1
    TIME_ABSOLUTE_INTERVAL = 2
    TIME_LAST_RECORDED = 3
    TIME_INDEXED_ABSOLUTE = 4


# Object size lookup (group, variation) -> size in bytes
# None means variable size or size depends on qualifier
# This table is critical for proper frame parsing and should be kept in sync with IEEE 1815
OBJECT_SIZES = {
    # =========================================================================
    # Binary Input (Group 1) - Static data
    # =========================================================================
    (1, 1): None,  # Packed (1 bit per point) - variable size
    (1, 2): 1,  # With flags (1 byte)
    # =========================================================================
    # Binary Input Event (Group 2) - Event data
    # =========================================================================
    (2, 1): 1,  # Without time (flags only)
    (2, 2): 7,  # With absolute time: flags(1) + time(6)
    (2, 3): 3,  # With relative time: flags(1) + time(2)
    # =========================================================================
    # Double-bit Binary Input (Group 3) - Static data
    # =========================================================================
    (3, 1): None,  # Packed (2 bits per point) - variable size
    (3, 2): 1,  # With flags (1 byte)
    # =========================================================================
    # Double-bit Binary Input Event (Group 4) - Event data
    # =========================================================================
    (4, 1): 1,  # Without time
    (4, 2): 7,  # With absolute time: flags(1) + time(6)
    (4, 3): 3,  # With relative time: flags(1) + time(2)
    # =========================================================================
    # Binary Output (Group 10) - Static data
    # =========================================================================
    (10, 1): None,  # Packed (1 bit per point) - variable size
    (10, 2): 1,  # With flags (1 byte)
    # =========================================================================
    # Binary Output Event (Group 11) - Event data
    # =========================================================================
    (11, 1): 1,  # Without time (flags only)
    (11, 2): 7,  # With absolute time: flags(1) + time(6)
    # =========================================================================
    # Control Relay Output Block - CROB (Group 12) - Command
    # =========================================================================
    (12, 1): 11,  # Control code(1) + count(1) + on_time(4) + off_time(4) + status(1)
    (12, 2): None,  # Pattern Control Block - variable
    (12, 3): None,  # Pattern Mask - variable
    # =========================================================================
    # Binary Output Command Event (Group 13) - Event data
    # =========================================================================
    (13, 1): 11,  # Same as CROB without additional status
    (13, 2): 17,  # CROB(11) + time(6)
    # =========================================================================
    # Counter (Group 20) - Static data
    # =========================================================================
    (20, 1): 5,  # 32-bit unsigned with flag: flag(1) + value(4)
    (20, 2): 3,  # 16-bit unsigned with flag: flag(1) + value(2)
    (20, 3): 5,  # 32-bit signed delta with flag: flag(1) + value(4)
    (20, 4): 3,  # 16-bit signed delta with flag: flag(1) + value(2)
    (20, 5): 4,  # 32-bit unsigned without flag
    (20, 6): 2,  # 16-bit unsigned without flag
    (20, 7): 4,  # 32-bit signed delta without flag
    (20, 8): 2,  # 16-bit signed delta without flag
    # =========================================================================
    # Frozen Counter (Group 21) - Static data (frozen snapshot)
    # =========================================================================
    (21, 1): 5,  # 32-bit with flag: value(4) + flag(1)
    (21, 2): 3,  # 16-bit with flag: value(2) + flag(1)
    (21, 3): 5,  # 32-bit delta with flag: value(4) + flag(1)
    (21, 4): 3,  # 16-bit delta with flag: value(2) + flag(1)
    (21, 5): 4,  # 32-bit without flag
    (21, 6): 2,  # 16-bit without flag
    (21, 7): 4,  # 32-bit delta without flag
    (21, 8): 2,  # 16-bit delta without flag
    (21, 9): 11,  # 32-bit with flag and time: flag(1) + value(4) + time(6)
    (21, 10): 9,  # 16-bit with flag and time: flag(1) + value(2) + time(6)
    (21, 11): 11,  # 32-bit delta with flag and time
    (21, 12): 9,  # 16-bit delta with flag and time
    # =========================================================================
    # Counter Event (Group 22) - Event data
    # =========================================================================
    (22, 1): 5,  # 32-bit with flag: flag(1) + value(4)
    (22, 2): 3,  # 16-bit with flag: flag(1) + value(2)
    (22, 3): 5,  # 32-bit delta with flag
    (22, 4): 3,  # 16-bit delta with flag
    (22, 5): 11,  # 32-bit with flag and time: flag(1) + value(4) + time(6)
    (22, 6): 9,  # 16-bit with flag and time: flag(1) + value(2) + time(6)
    (22, 7): 11,  # 32-bit delta with flag and time
    (22, 8): 9,  # 16-bit delta with flag and time
    # =========================================================================
    # Frozen Counter Event (Group 23) - Event data
    # =========================================================================
    (23, 1): 5,  # 32-bit with flag
    (23, 2): 3,  # 16-bit with flag
    (23, 3): 5,  # 32-bit delta with flag
    (23, 4): 3,  # 16-bit delta with flag
    (23, 5): 11,  # 32-bit with flag and time
    (23, 6): 9,  # 16-bit with flag and time
    (23, 7): 11,  # 32-bit delta with flag and time
    (23, 8): 9,  # 16-bit delta with flag and time
    # =========================================================================
    # Analog Input (Group 30) - Static data
    # =========================================================================
    (30, 1): 5,  # 32-bit signed with flag: flag(1) + value(4)
    (30, 2): 3,  # 16-bit signed with flag: flag(1) + value(2)
    (30, 3): 4,  # 32-bit signed without flag
    (30, 4): 2,  # 16-bit signed without flag
    (30, 5): 5,  # 32-bit float with flag: flag(1) + value(4)
    (30, 6): 9,  # 64-bit double with flag: flag(1) + value(8)
    # =========================================================================
    # Frozen Analog Input (Group 31) - Static data (frozen snapshot)
    # =========================================================================
    (31, 1): 5,  # 32-bit with flag: flag(1) + value(4)
    (31, 2): 3,  # 16-bit with flag: flag(1) + value(2)
    (31, 3): 11,  # 32-bit with flag and time: flag(1) + value(4) + time(6)
    (31, 4): 9,  # 16-bit with flag and time: flag(1) + value(2) + time(6)
    (31, 5): 4,  # 32-bit without flag
    (31, 6): 2,  # 16-bit without flag
    (31, 7): 5,  # 32-bit float with flag: flag(1) + value(4)
    (31, 8): 9,  # 64-bit double with flag: flag(1) + value(8)
    # =========================================================================
    # Analog Input Event (Group 32) - Event data
    # =========================================================================
    (32, 1): 5,  # 32-bit with flag: flag(1) + value(4)
    (32, 2): 3,  # 16-bit with flag: flag(1) + value(2)
    (32, 3): 11,  # 32-bit with flag and time: flag(1) + value(4) + time(6)
    (32, 4): 9,  # 16-bit with flag and time: flag(1) + value(2) + time(6)
    (32, 5): 5,  # 32-bit float with flag
    (32, 6): 9,  # 64-bit double with flag
    (32, 7): 11,  # 32-bit float with flag and time
    (32, 8): 15,  # 64-bit double with flag and time
    # =========================================================================
    # Frozen Analog Input Event (Group 33) - Event data
    # =========================================================================
    (33, 1): 5,  # 32-bit with flag
    (33, 2): 3,  # 16-bit with flag
    (33, 3): 11,  # 32-bit with flag and time
    (33, 4): 9,  # 16-bit with flag and time
    (33, 5): 5,  # 32-bit float with flag
    (33, 6): 9,  # 64-bit double with flag
    (33, 7): 11,  # 32-bit float with flag and time
    (33, 8): 15,  # 64-bit double with flag and time
    # =========================================================================
    # Analog Input Deadband (Group 34)
    # =========================================================================
    (34, 1): 2,  # 16-bit deadband
    (34, 2): 4,  # 32-bit deadband
    (34, 3): 4,  # 32-bit float deadband
    # =========================================================================
    # Analog Output Status (Group 40) - Static data
    # =========================================================================
    (40, 1): 5,  # 32-bit with flag: flag(1) + value(4)
    (40, 2): 3,  # 16-bit with flag: flag(1) + value(2)
    (40, 3): 5,  # 32-bit float with flag
    (40, 4): 9,  # 64-bit double with flag
    # =========================================================================
    # Analog Output Block (Group 41) - Command
    # =========================================================================
    (41, 1): 5,  # 32-bit + status: value(4) + status(1)
    (41, 2): 3,  # 16-bit + status: value(2) + status(1)
    (41, 3): 5,  # 32-bit float + status: value(4) + status(1)
    (41, 4): 9,  # 64-bit double + status: value(8) + status(1)
    # =========================================================================
    # Analog Output Event (Group 42) - Event data
    # =========================================================================
    (42, 1): 5,  # 32-bit with flag: flag(1) + value(4)
    (42, 2): 3,  # 16-bit with flag: flag(1) + value(2)
    (42, 3): 11,  # 32-bit with flag and time: flag(1) + value(4) + time(6)
    (42, 4): 9,  # 16-bit with flag and time: flag(1) + value(2) + time(6)
    (42, 5): 5,  # 32-bit float with flag
    (42, 6): 9,  # 64-bit double with flag
    (42, 7): 11,  # 32-bit float with flag and time
    (42, 8): 15,  # 64-bit double with flag and time
    # =========================================================================
    # Analog Output Command Event (Group 43) - Event data
    # =========================================================================
    (43, 1): 5,  # 32-bit with status
    (43, 2): 3,  # 16-bit with status
    (43, 3): 11,  # 32-bit with status and time
    (43, 4): 9,  # 16-bit with status and time
    (43, 5): 5,  # 32-bit float with status
    (43, 6): 9,  # 64-bit double with status
    (43, 7): 11,  # 32-bit float with status and time
    (43, 8): 15,  # 64-bit double with status and time
    # =========================================================================
    # Time and Date (Group 50)
    # =========================================================================
    (50, 1): 6,  # Absolute time (48-bit milliseconds since epoch)
    (50, 2): 10,  # Absolute time with interval
    (50, 3): 6,  # Last recorded time
    (50, 4): 6,  # Indexed absolute time
    # =========================================================================
    # Time and Date CTO (Group 51) - Common Time of Occurrence
    # =========================================================================
    (51, 1): 6,  # Absolute time CTO (48-bit)
    (51, 2): 6,  # Unsynchronized absolute time CTO
    # =========================================================================
    # Time Delay (Group 52)
    # =========================================================================
    (52, 1): 2,  # Coarse time delay (seconds)
    (52, 2): 2,  # Fine time delay (milliseconds)
    # =========================================================================
    # Internal Indications (Group 80)
    # =========================================================================
    (80, 1): 1,  # Internal indications packed
    # =========================================================================
    # Octet String (Group 110, 111) - Variable length
    # =========================================================================
    (110, 0): None,  # Variable length octet string
    (111, 0): None,  # Variable length octet string event
}


def get_object_size(group: int, variation: int) -> Optional[int]:
    """
    Get the size of an object in bytes.

    Args:
        group: Object group number
        variation: Object variation

    Returns:
        Size in bytes, or None if variable/packed or unknown (group, variation)
    """
    return OBJECT_SIZES.get((group, variation))


def get_group_name(group: int) -> str:
    """Get human-readable name for a group number. Unknown groups return 'Group N'."""
    names = {
        1: "Binary Input",
        2: "Binary Input Event",
        3: "Double-bit Binary Input",
        4: "Double-bit Binary Input Event",
        10: "Binary Output",
        11: "Binary Output Event",
        12: "Control Relay Output Block",
        13: "Binary Output Command Event",
        20: "Counter",
        21: "Frozen Counter",
        22: "Counter Event",
        23: "Frozen Counter Event",
        30: "Analog Input",
        31: "Frozen Analog Input",
        32: "Analog Input Event",
        33: "Frozen Analog Input Event",
        34: "Analog Input Deadband",
        40: "Analog Output Status",
        41: "Analog Output Block",
        42: "Analog Output Event",
        43: "Analog Output Command Event",
        50: "Time and Date",
        51: "Time and Date CTO",
        52: "Time Delay",
        60: "Class Objects",
        70: "File Identifier",
        71: "File Authentication",
        80: "Internal Indications",
        110: "Octet String",
        111: "Octet String Event",
        112: "Virtual Terminal Output",
        113: "Virtual Terminal Event",
        120: "Authentication",
    }
    return names.get(int(group), f"Group {group}")
