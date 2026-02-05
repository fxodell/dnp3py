"""
DNP3 Analog Input and Output objects.

Analog objects represent continuous values such as:
- Voltages
- Currents
- Power measurements
- Temperatures
- Pressures
"""

from dataclasses import dataclass
from typing import Optional, List, Union
from enum import IntFlag
import struct

from pydnp3.core.config import ControlStatus


class AnalogFlags(IntFlag):
    """Flags byte for analog objects."""

    ONLINE = 0x01           # Point is online
    RESTART = 0x02          # Point has been restarted
    COMM_LOST = 0x04        # Communication lost
    REMOTE_FORCED = 0x08    # Value forced by remote
    LOCAL_FORCED = 0x10     # Value forced by local
    OVER_RANGE = 0x20       # Value exceeds range
    REFERENCE_ERR = 0x40    # Reference error
    RESERVED = 0x80         # Reserved


@dataclass
class AnalogInput:
    """
    DNP3 Analog Input (Group 30).

    Represents a measured analog value.
    """

    index: int
    value: Union[int, float]
    flags: int = AnalogFlags.ONLINE
    timestamp: Optional[int] = None  # Milliseconds since epoch

    @property
    def is_online(self) -> bool:
        """Check if point is online."""
        return bool(self.flags & AnalogFlags.ONLINE)

    @property
    def is_over_range(self) -> bool:
        """Check if value is over range."""
        return bool(self.flags & AnalogFlags.OVER_RANGE)

    @property
    def comm_lost(self) -> bool:
        """Check if communication is lost."""
        return bool(self.flags & AnalogFlags.COMM_LOST)

    @classmethod
    def from_bytes(cls, data: bytes, index: int, variation: int = 1) -> "AnalogInput":
        """
        Parse analog input from bytes.

        Args:
            data: Raw bytes
            index: Point index
            variation: Object variation (1-6)

        Returns:
            Parsed AnalogInput
        """
        flags = AnalogFlags.ONLINE
        value: Union[int, float] = 0

        if variation == 1:
            # 32-bit signed with flag
            flags = data[0]
            value = struct.unpack("<i", data[1:5])[0]
        elif variation == 2:
            # 16-bit signed with flag
            flags = data[0]
            value = struct.unpack("<h", data[1:3])[0]
        elif variation == 3:
            # 32-bit signed without flag
            value = struct.unpack("<i", data[:4])[0]
        elif variation == 4:
            # 16-bit signed without flag
            value = struct.unpack("<h", data[:2])[0]
        elif variation == 5:
            # 32-bit float with flag
            flags = data[0]
            value = struct.unpack("<f", data[1:5])[0]
        elif variation == 6:
            # 64-bit double with flag
            flags = data[0]
            value = struct.unpack("<d", data[1:9])[0]
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

        # Get integer value with range checking
        int_val = int(self.value)

        if variation == 1:
            # 32-bit signed with flag
            if not -2147483648 <= int_val <= 2147483647:
                raise ValueError(
                    f"Value {int_val} out of range for 32-bit signed integer"
                )
            result.append(self.flags)
            result.extend(struct.pack("<i", int_val))
        elif variation == 2:
            # 16-bit signed with flag
            if not -32768 <= int_val <= 32767:
                raise ValueError(
                    f"Value {int_val} out of range for 16-bit signed integer"
                )
            result.append(self.flags)
            result.extend(struct.pack("<h", int_val))
        elif variation == 3:
            # 32-bit signed without flag
            if not -2147483648 <= int_val <= 2147483647:
                raise ValueError(
                    f"Value {int_val} out of range for 32-bit signed integer"
                )
            result.extend(struct.pack("<i", int_val))
        elif variation == 4:
            # 16-bit signed without flag
            if not -32768 <= int_val <= 32767:
                raise ValueError(
                    f"Value {int_val} out of range for 16-bit signed integer"
                )
            result.extend(struct.pack("<h", int_val))
        elif variation == 5:
            # 32-bit float with flag
            result.append(self.flags)
            result.extend(struct.pack("<f", float(self.value)))
        elif variation == 6:
            # 64-bit double with flag
            result.append(self.flags)
            result.extend(struct.pack("<d", float(self.value)))
        else:
            raise ValueError(f"Unsupported analog input variation: {variation}")

        return bytes(result)

    def __repr__(self) -> str:
        online = "online" if self.is_online else "offline"
        return f"AnalogInput(idx={self.index}, value={self.value}, {online})"


@dataclass
class AnalogOutput:
    """
    DNP3 Analog Output Status (Group 40).

    Represents the current setpoint value of an analog output.
    """

    index: int
    value: Union[int, float]
    flags: int = AnalogFlags.ONLINE

    @classmethod
    def from_bytes(cls, data: bytes, index: int, variation: int = 1) -> "AnalogOutput":
        """Parse analog output from bytes."""
        flags = AnalogFlags.ONLINE
        value: Union[int, float] = 0

        if variation == 1:
            flags = data[0]
            value = struct.unpack("<i", data[1:5])[0]
        elif variation == 2:
            flags = data[0]
            value = struct.unpack("<h", data[1:3])[0]
        elif variation == 3:
            flags = data[0]
            value = struct.unpack("<f", data[1:5])[0]
        elif variation == 4:
            flags = data[0]
            value = struct.unpack("<d", data[1:9])[0]
        else:
            raise ValueError(f"Unsupported variation: {variation}")

        return cls(index=index, value=value, flags=flags)

    def to_bytes(self, variation: int = 1) -> bytes:
        """Serialize to bytes."""
        result = bytearray()

        if variation == 1:
            result.append(self.flags)
            result.extend(struct.pack("<i", int(self.value)))
        elif variation == 2:
            result.append(self.flags)
            result.extend(struct.pack("<h", int(self.value)))
        elif variation == 3:
            result.append(self.flags)
            result.extend(struct.pack("<f", float(self.value)))
        elif variation == 4:
            result.append(self.flags)
            result.extend(struct.pack("<d", float(self.value)))
        else:
            raise ValueError(f"Unsupported variation: {variation}")

        return bytes(result)

    def __repr__(self) -> str:
        return f"AnalogOutput(idx={self.index}, value={self.value})"


@dataclass
class AnalogOutputCommand:
    """
    DNP3 Analog Output Block (Group 41).

    Used to command analog output setpoints.
    """

    index: int
    value: Union[int, float]
    status: int = ControlStatus.SUCCESS

    @classmethod
    def create(cls, index: int, value: Union[int, float]) -> "AnalogOutputCommand":
        """Create an analog output command."""
        return cls(index=index, value=value)

    def to_bytes(self, variation: int = 1) -> bytes:
        """
        Serialize to bytes.

        Args:
            variation: 1=int32, 2=int16, 3=float32, 4=float64
        """
        result = bytearray()

        if variation == 1:
            result.extend(struct.pack("<i", int(self.value)))
            result.append(self.status)
        elif variation == 2:
            result.extend(struct.pack("<h", int(self.value)))
            result.append(self.status)
        elif variation == 3:
            result.extend(struct.pack("<f", float(self.value)))
            result.append(self.status)
        elif variation == 4:
            result.extend(struct.pack("<d", float(self.value)))
            result.append(self.status)
        else:
            raise ValueError(f"Unsupported variation: {variation}")

        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes, index: int, variation: int = 1) -> "AnalogOutputCommand":
        """Parse analog output command from bytes."""
        value: Union[int, float] = 0
        status = ControlStatus.SUCCESS

        if variation == 1:
            if len(data) < 5:
                raise ValueError(f"Analog output command data too short: {len(data)} < 5")
            value = struct.unpack("<i", data[:4])[0]
            status = data[4]
        elif variation == 2:
            if len(data) < 3:
                raise ValueError(f"Analog output command data too short: {len(data)} < 3")
            value = struct.unpack("<h", data[:2])[0]
            status = data[2]
        elif variation == 3:
            if len(data) < 5:
                raise ValueError(f"Analog output command data too short: {len(data)} < 5")
            value = struct.unpack("<f", data[:4])[0]
            status = data[4]
        elif variation == 4:
            if len(data) < 9:
                raise ValueError(f"Analog output command data too short: {len(data)} < 9")
            value = struct.unpack("<d", data[:8])[0]
            status = data[8]
        else:
            raise ValueError(f"Unsupported variation: {variation}")

        return cls(index=index, value=value, status=status)

    def __repr__(self) -> str:
        return f"AnalogOutputCommand(idx={self.index}, value={self.value}, status={self.status})"


def parse_analog_inputs(
    data: bytes,
    start_index: int,
    count: int,
    variation: int,
) -> List[AnalogInput]:
    """
    Parse multiple analog inputs from response data.

    Args:
        data: Raw data bytes
        start_index: Starting point index
        count: Number of points
        variation: Object variation

    Returns:
        List of AnalogInput objects
    """
    # Size per object based on variation
    sizes = {1: 5, 2: 3, 3: 4, 4: 2, 5: 5, 6: 9}
    obj_size = sizes.get(variation)
    if obj_size is None:
        raise ValueError(f"Unsupported analog input variation: {variation}")

    inputs = []
    offset = 0

    for i in range(count):
        if offset + obj_size > len(data):
            break
        inputs.append(AnalogInput.from_bytes(data[offset:offset + obj_size], start_index + i, variation))
        offset += obj_size

    return inputs


def parse_analog_outputs(
    data: bytes,
    start_index: int,
    count: int,
    variation: int,
) -> List[AnalogOutput]:
    """
    Parse multiple analog outputs from response data.

    Args:
        data: Raw data bytes
        start_index: Starting point index
        count: Number of points
        variation: Object variation

    Returns:
        List of AnalogOutput objects
    """
    sizes = {1: 5, 2: 3, 3: 5, 4: 9}
    obj_size = sizes.get(variation)
    if obj_size is None:
        raise ValueError(f"Unsupported analog output variation: {variation}")

    outputs = []
    offset = 0

    for i in range(count):
        if offset + obj_size > len(data):
            break
        outputs.append(AnalogOutput.from_bytes(data[offset:offset + obj_size], start_index + i, variation))
        offset += obj_size

    return outputs
