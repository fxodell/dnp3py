"""Tests for object sizes and event decoding."""

import struct

import pytest

from dnp3py.core.master import DNP3Master
from dnp3py.layers.application import ApplicationResponse
from dnp3py.objects.analog import AnalogInput
from dnp3py.objects.binary import BinaryInput, BinaryOutput
from dnp3py.objects.counter import Counter
from dnp3py.objects.events import decode_event, event_size
from dnp3py.objects.groups import get_object_size, get_packed_size

TIME = (1_700_000_000_123).to_bytes(6, "little")


class TestObjectSizes:
    """Sizes in octets of one object, from the DNP3 object library."""

    @pytest.mark.parametrize(
        ("group", "variation", "size"),
        [
            (13, 1, 1),  # binary command event without time
            (13, 2, 7),  # with time
            (21, 1, 5),
            (21, 2, 3),
            (21, 5, 11),  # 32-bit with flag and time
            (21, 6, 9),  # 16-bit with flag and time
            (21, 7, 11),
            (21, 8, 9),
            (21, 9, 4),  # 32-bit without flag
            (21, 10, 2),  # 16-bit without flag
            (21, 11, 4),
            (21, 12, 2),
            (50, 4, 11),  # indexed absolute time and long interval
            (110, 5, 5),  # octet string: the variation is the length
            (111, 12, 12),
        ],
    )
    def test_size(self, group, variation, size):
        assert get_object_size(group, variation) == size

    @pytest.mark.parametrize(
        ("group", "variation", "count", "size"),
        [
            (1, 1, 9, 2),
            (3, 1, 5, 2),  # 2 bits per point
            (10, 1, 8, 1),
            (80, 1, 16, 2),
        ],
    )
    def test_packed_size(self, group, variation, count, size):
        assert get_object_size(group, variation) is None
        assert get_packed_size(group, variation, count) == size

    def test_headers_after_packed_double_bit_are_parsed(self):
        """A g3v1 header no longer stops the parser."""
        apdu = bytes([0xC0, 0x81, 0x00, 0x00])
        apdu += bytes([3, 1, 0x00, 0, 4]) + bytes([0x55, 0x01])  # 5 points, 2 octets
        apdu += bytes([30, 2, 0x00, 0, 0]) + bytes([0x01, 0x2A, 0x00])
        response = ApplicationResponse.from_bytes(apdu)
        assert [(h.group, h.variation) for h in response.objects] == [(3, 1), (30, 2)]


class TestDecodeEvent:
    """Event variations are decoded with their own layout: flags, value, time."""

    def test_binary_input_event_without_time(self):
        event = decode_event(2, 1, bytes([0x81]), 4)
        assert isinstance(event, BinaryInput)
        assert (event.index, event.value, event.flags, event.timestamp) == (4, True, 0x81, None)

    def test_binary_input_event_with_time(self):
        event = decode_event(2, 2, bytes([0x01]) + TIME, 0)
        assert (event.value, event.timestamp) == (False, 1_700_000_000_123)

    def test_binary_output_event_with_time(self):
        event = decode_event(11, 2, bytes([0x81]) + TIME, 2)
        assert isinstance(event, BinaryOutput)
        assert (event.value, event.timestamp) == (True, 1_700_000_000_123)

    def test_counter_event_with_time(self):
        event = decode_event(22, 5, bytes([0x01]) + struct.pack("<I", 123461) + TIME, 0)
        assert isinstance(event, Counter)
        assert (event.value, event.flags, event.timestamp) == (123461, 0x01, 1_700_000_000_123)

    def test_analog_input_event_float_with_time(self):
        event = decode_event(32, 7, bytes([0x01]) + struct.pack("<f", 1.5) + TIME, 3)
        assert isinstance(event, AnalogInput)
        assert (event.value, event.timestamp) == (1.5, 1_700_000_000_123)

    def test_analog_input_event_double(self):
        event = decode_event(32, 6, bytes([0x01]) + struct.pack("<d", -2.25), 3)
        assert (event.value, event.timestamp) == (-2.25, None)

    @pytest.mark.parametrize(("group", "variation"), [(22, 5), (32, 8), (2, 3)])
    def test_size_matches_object_table(self, group, variation):
        assert event_size(group, variation) == get_object_size(group, variation)

    def test_short_data(self):
        with pytest.raises(ValueError):
            decode_event(22, 5, bytes(5), 0)

    def test_unsupported_event(self):
        with pytest.raises(ValueError):
            decode_event(4, 1, bytes(1), 0)


class TestPollResultEvents:
    """A poll response with events reports their values and times."""

    @staticmethod
    def poll(objects):
        apdu = bytes([0xC0, 0x81, 0x00, 0x00]) + objects
        return DNP3Master()._parse_poll_response(ApplicationResponse.from_bytes(apdu))

    def test_counter_event_with_time(self):
        """g22v5 with qualifier 0x17, one event at index 0."""
        result = self.poll(
            bytes([22, 5, 0x17, 1, 0]) + bytes([0x01]) + struct.pack("<I", 123461) + TIME
        )
        assert [(c.index, c.value, c.timestamp) for c in result.counters] == [
            (0, 123461, 1_700_000_000_123)
        ]

    def test_analog_event_with_time(self):
        """g32v3 with qualifier 0x17, one event at index 2."""
        result = self.poll(
            bytes([32, 3, 0x17, 1, 2]) + bytes([0x01]) + struct.pack("<i", -7) + TIME
        )
        assert [(a.index, a.value, a.timestamp) for a in result.analog_inputs] == [
            (2, -7, 1_700_000_000_123)
        ]

    def test_binary_event_without_time(self):
        """g2v1 with qualifier 0x17: the state is bit 7 of the flags."""
        result = self.poll(bytes([2, 1, 0x17, 1, 1, 0x81]))
        assert [(b.index, b.value, b.flags) for b in result.binary_inputs] == [(1, True, 0x81)]
