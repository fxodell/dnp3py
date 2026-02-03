"""
DNP3 Object Group and Variation definitions.

DNP3 data objects are identified by Group and Variation numbers.
Groups identify the type of data (Binary Input, Analog Input, etc.)
Variations identify the specific format of the data.
"""

from enum import IntEnum


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
    BI_PACKED = 1       # Packed format (8 points per byte)
    BI_WITH_FLAGS = 2   # With flags (1 byte per point)

    # Binary Input Event Variations (Group 2)
    BIE_WITHOUT_TIME = 1
    BIE_WITH_ABSOLUTE_TIME = 2
    BIE_WITH_RELATIVE_TIME = 3

    # Binary Output Variations (Group 10)
    BO_PACKED = 1       # Packed format
    BO_WITH_FLAGS = 2   # With flags

    # CROB Variations (Group 12)
    CROB = 1            # Control Relay Output Block
    PCB = 2             # Pattern Control Block
    PM = 3              # Pattern Mask

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
OBJECT_SIZES = {
    # Binary Input (Group 1)
    (1, 1): None,   # Packed (1 bit per point)
    (1, 2): 1,      # With flags

    # Binary Input Event (Group 2)
    (2, 1): 1,      # Without time
    (2, 2): 7,      # 1 + 6 (48-bit absolute time)
    (2, 3): 3,      # 1 + 2 (16-bit relative time)

    # Double-bit Binary Input (Group 3)
    (3, 1): None,   # Packed (2 bits per point)
    (3, 2): 1,      # With flags

    # Double-bit Binary Input Event (Group 4)
    (4, 1): 1,      # Without time
    (4, 2): 7,      # With absolute time
    (4, 3): 3,      # With relative time

    # Binary Output (Group 10)
    (10, 1): None,  # Packed
    (10, 2): 1,     # With flags

    # Binary Output Event (Group 11)
    (11, 1): 1,     # Without time
    (11, 2): 7,     # With absolute time

    # CROB (Group 12)
    (12, 1): 11,    # Control code(1) + count(1) + on_time(4) + off_time(4) + status(1)

    # Binary Output Command Event (Group 13)
    (13, 1): 12,    # CROB(11) + status(1)
    (13, 2): 18,    # CROB(11) + status(1) + time(6)

    # Counter (Group 20)
    (20, 1): 5,     # 32-bit with flag: 4 + 1
    (20, 2): 3,     # 16-bit with flag: 2 + 1
    (20, 3): 5,     # 32-bit delta with flag: 4 + 1
    (20, 4): 3,     # 16-bit delta with flag: 2 + 1
    (20, 5): 4,     # 32-bit without flag
    (20, 6): 2,     # 16-bit without flag
    (20, 7): 4,     # 32-bit delta without flag
    (20, 8): 2,     # 16-bit delta without flag

    # Frozen Counter (Group 21)
    (21, 1): 5,     # 32-bit with flag
    (21, 2): 3,     # 16-bit with flag
    (21, 5): 4,     # 32-bit without flag
    (21, 6): 2,     # 16-bit without flag
    (21, 9): 11,    # 32-bit with flag and time
    (21, 10): 9,    # 16-bit with flag and time

    # Counter Event (Group 22)
    (22, 1): 5,     # 32-bit with flag
    (22, 2): 3,     # 16-bit with flag
    (22, 5): 11,    # 32-bit with flag and time
    (22, 6): 9,     # 16-bit with flag and time

    # Frozen Counter Event (Group 23)
    (23, 1): 5,     # 32-bit with flag
    (23, 2): 3,     # 16-bit with flag
    (23, 5): 11,    # 32-bit with flag and time
    (23, 6): 9,     # 16-bit with flag and time

    # Analog Input (Group 30)
    (30, 1): 5,     # 32-bit signed with flag: 4 + 1
    (30, 2): 3,     # 16-bit signed with flag: 2 + 1
    (30, 3): 4,     # 32-bit signed without flag
    (30, 4): 2,     # 16-bit signed without flag
    (30, 5): 5,     # 32-bit float with flag: 4 + 1
    (30, 6): 9,     # 64-bit double with flag: 8 + 1

    # Frozen Analog Input (Group 31)
    (31, 1): 5,     # 32-bit with flag
    (31, 2): 3,     # 16-bit with flag
    (31, 3): 11,    # 32-bit with flag and time
    (31, 4): 9,     # 16-bit with flag and time
    (31, 5): 4,     # 32-bit without flag
    (31, 6): 2,     # 16-bit without flag
    (31, 7): 5,     # 32-bit float with flag
    (31, 8): 9,     # 64-bit double with flag

    # Analog Input Event (Group 32)
    (32, 1): 5,     # 32-bit with flag
    (32, 2): 3,     # 16-bit with flag
    (32, 3): 11,    # 32-bit with flag and time
    (32, 4): 9,     # 16-bit with flag and time
    (32, 5): 5,     # 32-bit float with flag
    (32, 6): 9,     # 64-bit double with flag
    (32, 7): 11,    # 32-bit float with flag and time
    (32, 8): 15,    # 64-bit double with flag and time

    # Analog Output Status (Group 40)
    (40, 1): 5,     # 32-bit with flag
    (40, 2): 3,     # 16-bit with flag
    (40, 3): 5,     # 32-bit float with flag
    (40, 4): 9,     # 64-bit double with flag

    # Analog Output Block (Group 41)
    (41, 1): 5,     # 32-bit + status: 4 + 1
    (41, 2): 3,     # 16-bit + status: 2 + 1
    (41, 3): 5,     # 32-bit float + status: 4 + 1
    (41, 4): 9,     # 64-bit double + status: 8 + 1

    # Analog Output Event (Group 42)
    (42, 1): 5,     # 32-bit with flag
    (42, 2): 3,     # 16-bit with flag
    (42, 3): 11,    # 32-bit with flag and time
    (42, 4): 9,     # 16-bit with flag and time
    (42, 5): 5,     # 32-bit float with flag
    (42, 6): 9,     # 64-bit double with flag
    (42, 7): 11,    # 32-bit float with flag and time
    (42, 8): 15,    # 64-bit double with flag and time

    # Time and Date (Group 50)
    (50, 1): 6,     # Absolute time (48-bit)
    (50, 4): 6,     # Indexed absolute time
}


def get_object_size(group: int, variation: int) -> int | None:
    """
    Get the size of an object in bytes.

    Args:
        group: Object group number
        variation: Object variation

    Returns:
        Size in bytes, or None if variable/packed
    """
    return OBJECT_SIZES.get((group, variation))


def get_group_name(group: int) -> str:
    """Get human-readable name for a group number."""
    names = {
        1: "Binary Input",
        2: "Binary Input Event",
        3: "Double-bit Binary Input",
        4: "Double-bit Binary Input Event",
        10: "Binary Output",
        11: "Binary Output Event",
        12: "Control Relay Output Block",
        20: "Counter",
        21: "Frozen Counter",
        22: "Counter Event",
        30: "Analog Input",
        31: "Frozen Analog Input",
        32: "Analog Input Event",
        40: "Analog Output Status",
        41: "Analog Output Block",
        42: "Analog Output Event",
        50: "Time and Date",
        60: "Class Objects",
        80: "Internal Indications",
        110: "Octet String",
    }
    return names.get(group, f"Group {group}")
