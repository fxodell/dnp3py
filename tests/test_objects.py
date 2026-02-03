"""Tests for DNP3 data objects."""

import pytest
import struct
from dnp3_driver.objects.binary import (
    BinaryInput,
    BinaryOutput,
    BinaryOutputCommand,
    BinaryFlags,
    parse_binary_inputs,
    parse_binary_outputs,
)
from dnp3_driver.objects.analog import (
    AnalogInput,
    AnalogOutput,
    AnalogOutputCommand,
    AnalogFlags,
    parse_analog_inputs,
)
from dnp3_driver.objects.counter import Counter, CounterFlags, parse_counters
from dnp3_driver.core.config import ControlCode, ControlStatus


class TestBinaryInput:
    """Tests for BinaryInput class."""

    def test_from_bytes_variation_1(self):
        """Test parsing packed binary input."""
        data = bytes([0x01])
        bi = BinaryInput.from_bytes(data, index=0, variation=1)

        assert bi.value is True
        assert bi.index == 0

    def test_from_bytes_variation_2(self):
        """Test parsing binary input with flags."""
        # Online=1, State=1 (ON)
        data = bytes([0x81])
        bi = BinaryInput.from_bytes(data, index=5, variation=2)

        assert bi.value is True
        assert bi.is_online is True
        assert bi.index == 5

    def test_from_bytes_offline(self):
        """Test parsing offline binary input."""
        data = bytes([0x00])  # Not online
        bi = BinaryInput.from_bytes(data, index=0, variation=2)

        assert bi.is_online is False

    def test_to_bytes_variation_2(self):
        """Test serializing binary input with flags."""
        bi = BinaryInput(index=0, value=True, flags=BinaryFlags.ONLINE)
        data = bi.to_bytes(variation=2)

        assert data[0] & BinaryFlags.ONLINE
        assert data[0] & BinaryFlags.STATE

    def test_properties(self):
        """Test binary input properties."""
        bi = BinaryInput(
            index=0,
            value=False,
            flags=BinaryFlags.ONLINE | BinaryFlags.COMM_LOST,
        )

        assert bi.is_online is True
        assert bi.comm_lost is True
        assert bi.has_restart is False


class TestBinaryOutput:
    """Tests for BinaryOutput class."""

    def test_from_bytes(self):
        """Test parsing binary output."""
        data = bytes([0x81])  # Online, ON
        bo = BinaryOutput.from_bytes(data, index=0, variation=2)

        assert bo.value is True
        assert bo.index == 0

    def test_to_bytes(self):
        """Test serializing binary output."""
        bo = BinaryOutput(index=0, value=True, flags=BinaryFlags.ONLINE)
        data = bo.to_bytes(variation=2)

        assert data[0] & BinaryFlags.STATE


class TestBinaryOutputCommand:
    """Tests for BinaryOutputCommand (CROB)."""

    def test_latch_on(self):
        """Test latch on command creation."""
        cmd = BinaryOutputCommand.latch_on(index=5)

        assert cmd.index == 5
        assert cmd.control_code == ControlCode.LATCH_ON

    def test_latch_off(self):
        """Test latch off command creation."""
        cmd = BinaryOutputCommand.latch_off(index=3)

        assert cmd.control_code == ControlCode.LATCH_OFF

    def test_pulse_on(self):
        """Test pulse on command creation."""
        cmd = BinaryOutputCommand.pulse_on(index=0, on_time=1000, off_time=500, count=3)

        assert cmd.control_code == ControlCode.PULSE_ON
        assert cmd.on_time == 1000
        assert cmd.off_time == 500
        assert cmd.count == 3

    def test_to_bytes(self):
        """Test CROB serialization."""
        cmd = BinaryOutputCommand(
            index=0,
            control_code=ControlCode.LATCH_ON,
            count=1,
            on_time=0,
            off_time=0,
            status=ControlStatus.SUCCESS,
        )
        data = cmd.to_bytes()

        assert len(data) == 11
        assert data[0] == ControlCode.LATCH_ON

    def test_from_bytes(self):
        """Test CROB parsing."""
        cmd = BinaryOutputCommand.latch_on(5)
        data = cmd.to_bytes()
        parsed = BinaryOutputCommand.from_bytes(data, index=5)

        assert parsed.control_code == cmd.control_code
        assert parsed.count == cmd.count

    def test_operation_property(self):
        """Test operation name property."""
        cmd = BinaryOutputCommand.latch_on(0)
        assert cmd.operation == "LATCH_ON"

        cmd = BinaryOutputCommand.pulse_off(0, 100)
        assert cmd.operation == "PULSE_OFF"


class TestAnalogInput:
    """Tests for AnalogInput class."""

    def test_from_bytes_int32_with_flag(self):
        """Test parsing 32-bit integer with flag."""
        # Flag + 4-byte value
        value = 12345
        data = bytes([AnalogFlags.ONLINE]) + struct.pack("<i", value)
        ai = AnalogInput.from_bytes(data, index=0, variation=1)

        assert ai.value == value
        assert ai.is_online is True

    def test_from_bytes_int16_with_flag(self):
        """Test parsing 16-bit integer with flag."""
        value = 1000
        data = bytes([AnalogFlags.ONLINE]) + struct.pack("<h", value)
        ai = AnalogInput.from_bytes(data, index=0, variation=2)

        assert ai.value == value

    def test_from_bytes_float_with_flag(self):
        """Test parsing 32-bit float with flag."""
        value = 123.456
        data = bytes([AnalogFlags.ONLINE]) + struct.pack("<f", value)
        ai = AnalogInput.from_bytes(data, index=0, variation=5)

        assert abs(ai.value - value) < 0.001

    def test_from_bytes_double_with_flag(self):
        """Test parsing 64-bit double with flag."""
        value = 123456.789012
        data = bytes([AnalogFlags.ONLINE]) + struct.pack("<d", value)
        ai = AnalogInput.from_bytes(data, index=0, variation=6)

        assert abs(ai.value - value) < 0.000001

    def test_to_bytes_round_trip(self):
        """Test serialization/deserialization round trip."""
        original = AnalogInput(index=5, value=42.5, flags=AnalogFlags.ONLINE)
        data = original.to_bytes(variation=5)
        parsed = AnalogInput.from_bytes(data, index=5, variation=5)

        assert abs(parsed.value - original.value) < 0.001

    def test_properties(self):
        """Test analog input properties."""
        ai = AnalogInput(
            index=0,
            value=100,
            flags=AnalogFlags.ONLINE | AnalogFlags.OVER_RANGE,
        )

        assert ai.is_online is True
        assert ai.is_over_range is True


class TestAnalogOutput:
    """Tests for AnalogOutput class."""

    def test_from_bytes(self):
        """Test parsing analog output."""
        value = 5000
        data = bytes([AnalogFlags.ONLINE]) + struct.pack("<i", value)
        ao = AnalogOutput.from_bytes(data, index=0, variation=1)

        assert ao.value == value

    def test_to_bytes(self):
        """Test serializing analog output."""
        ao = AnalogOutput(index=0, value=1234)
        data = ao.to_bytes(variation=1)

        assert len(data) == 5


class TestAnalogOutputCommand:
    """Tests for AnalogOutputCommand."""

    def test_create(self):
        """Test command creation."""
        cmd = AnalogOutputCommand.create(index=0, value=50.0)

        assert cmd.index == 0
        assert cmd.value == 50.0

    def test_to_bytes_int32(self):
        """Test 32-bit integer serialization."""
        cmd = AnalogOutputCommand(index=0, value=1000)
        data = cmd.to_bytes(variation=1)

        assert len(data) == 5

    def test_to_bytes_float(self):
        """Test float serialization."""
        cmd = AnalogOutputCommand(index=0, value=123.456)
        data = cmd.to_bytes(variation=3)

        assert len(data) == 5

    def test_from_bytes(self):
        """Test parsing."""
        cmd = AnalogOutputCommand(index=5, value=42)
        data = cmd.to_bytes(variation=1)
        parsed = AnalogOutputCommand.from_bytes(data, index=5, variation=1)

        assert parsed.value == cmd.value


class TestCounter:
    """Tests for Counter class."""

    def test_from_bytes_32bit_with_flag(self):
        """Test parsing 32-bit counter with flag."""
        value = 123456
        data = bytes([CounterFlags.ONLINE]) + struct.pack("<I", value)
        ctr = Counter.from_bytes(data, index=0, variation=1)

        assert ctr.value == value
        assert ctr.is_online is True

    def test_from_bytes_16bit_with_flag(self):
        """Test parsing 16-bit counter with flag."""
        value = 1000
        data = bytes([CounterFlags.ONLINE]) + struct.pack("<H", value)
        ctr = Counter.from_bytes(data, index=0, variation=2)

        assert ctr.value == value

    def test_from_bytes_without_flag(self):
        """Test parsing counter without flag."""
        value = 5000
        data = struct.pack("<I", value)
        ctr = Counter.from_bytes(data, index=0, variation=5)

        assert ctr.value == value

    def test_rollover_flag(self):
        """Test rollover flag detection."""
        ctr = Counter(
            index=0,
            value=0,
            flags=CounterFlags.ONLINE | CounterFlags.ROLLOVER,
        )

        assert ctr.has_rollover is True


class TestParseFunctions:
    """Tests for bulk parsing functions."""

    def test_parse_binary_inputs_packed(self):
        """Test parsing packed binary inputs."""
        # 8 bits in one byte
        data = bytes([0b10101010])
        inputs = parse_binary_inputs(data, start_index=0, count=8, variation=1)

        assert len(inputs) == 8
        assert inputs[0].value is False
        assert inputs[1].value is True
        assert inputs[2].value is False
        assert inputs[3].value is True

    def test_parse_binary_inputs_with_flags(self):
        """Test parsing binary inputs with flags."""
        data = bytes([0x81, 0x01, 0x81])  # ON, OFF, ON
        inputs = parse_binary_inputs(data, start_index=0, count=3, variation=2)

        assert len(inputs) == 3
        assert inputs[0].value is True
        assert inputs[1].value is False
        assert inputs[2].value is True

    def test_parse_analog_inputs(self):
        """Test parsing multiple analog inputs."""
        values = [100, 200, 300]
        data = b""
        for v in values:
            data += bytes([AnalogFlags.ONLINE]) + struct.pack("<i", v)

        inputs = parse_analog_inputs(data, start_index=0, count=3, variation=1)

        assert len(inputs) == 3
        for i, ai in enumerate(inputs):
            assert ai.value == values[i]
            assert ai.index == i

    def test_parse_counters(self):
        """Test parsing multiple counters."""
        values = [1000, 2000, 3000]
        data = b""
        for v in values:
            data += bytes([CounterFlags.ONLINE]) + struct.pack("<I", v)

        counters = parse_counters(data, start_index=5, count=3, variation=1)

        assert len(counters) == 3
        for i, ctr in enumerate(counters):
            assert ctr.value == values[i]
            assert ctr.index == 5 + i

    def test_parse_binary_outputs_packed(self):
        """Test parsing packed binary outputs."""
        data = bytes([0b11001100])
        outputs = parse_binary_outputs(data, start_index=0, count=8, variation=1)

        assert len(outputs) == 8
        assert outputs[0].value is False
        assert outputs[1].value is False
        assert outputs[2].value is True
        assert outputs[3].value is True
        assert outputs[4].value is False
        assert outputs[5].value is False
        assert outputs[6].value is True
        assert outputs[7].value is True

    def test_parse_binary_outputs_with_flags(self):
        """Test parsing binary outputs with flags."""
        data = bytes([0x81, 0x01, 0x81])  # ON, OFF, ON
        outputs = parse_binary_outputs(data, start_index=10, count=3, variation=2)

        assert len(outputs) == 3
        assert outputs[0].value is True
        assert outputs[0].index == 10
        assert outputs[1].value is False
        assert outputs[1].index == 11
        assert outputs[2].value is True
        assert outputs[2].index == 12

    def test_parse_binary_outputs_empty_data(self):
        """Test parsing with empty data."""
        outputs = parse_binary_outputs(b"", start_index=0, count=5, variation=2)
        assert len(outputs) == 0

    def test_parse_binary_outputs_partial_data(self):
        """Test parsing with less data than count."""
        data = bytes([0x81, 0x01])  # Only 2 bytes
        outputs = parse_binary_outputs(data, start_index=0, count=5, variation=2)

        assert len(outputs) == 2  # Should only parse what's available
