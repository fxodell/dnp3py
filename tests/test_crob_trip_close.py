"""Tests for the Trip-Close Code of the Control Relay Output Block (g12v1)."""

from dnp3py.core.config import ControlCode
from dnp3py.objects.binary import BinaryOutputCommand


class TestTripCloseCode:
    """Bits 7-6 of the control code: 1 = CLOSE (0x40), 2 = TRIP (0x80)."""

    def test_code_values(self):
        assert ControlCode.TRIP_CLOSE_CLOSE == 0x40
        assert ControlCode.TRIP_CLOSE_TRIP == 0x80

    def test_trip_is_trip_pulse_on(self):
        command = BinaryOutputCommand.trip(3)
        assert command.control_code == 0x81
        assert command.to_bytes()[0] == 0x81

    def test_close_is_close_pulse_on(self):
        command = BinaryOutputCommand.close(3)
        assert command.control_code == 0x41
        assert command.to_bytes()[0] == 0x41

    def test_pulse_times(self):
        command = BinaryOutputCommand.trip(0, on_time=500, off_time=100)
        assert (command.on_time, command.off_time) == (500, 100)
