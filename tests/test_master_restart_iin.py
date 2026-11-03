"""Tests for clearing IIN1.7 DEVICE_RESTART."""

import socket

from dnp3py.core.config import DNP3Config
from dnp3py.core.master import DNP3Master
from dnp3py.layers.datalink import DataLinkLayer
from dnp3py.utils.crc import CRC16DNP3

MASTER_ADDRESS = 1
OUTSTATION_ADDRESS = 10


class FakeSocket:
    """Socket stand-in: recv() returns the queued chunks, sendall() records frames."""

    def __init__(self, chunks):
        self.rx = list(chunks)
        self.sent = []

    def settimeout(self, timeout):
        pass

    def recv(self, size):
        if not self.rx:
            raise socket.timeout
        return self.rx.pop(0)

    def sendall(self, data):
        self.sent.append(bytes(data))

    def close(self):
        pass


def outstation_frame(
    user_data=b"", control=0x44, destination=MASTER_ADDRESS, source=OUTSTATION_ADDRESS
):
    """Build a frame from the outstation (DIR=0); 0x44 is PRM + UNCONFIRMED_USER_DATA."""
    header = bytes([0x05, 0x64, 5 + len(user_data), control])
    header += destination.to_bytes(2, "little") + source.to_bytes(2, "little")
    frame = bytearray(header + CRC16DNP3.calculate_bytes(header))
    for i in range(0, len(user_data), 16):
        block = user_data[i : i + 16]
        frame += block + CRC16DNP3.calculate_bytes(block)
    return bytes(frame)


def response_segment(app_control=0xC0, function=0x81, iin=b"\x00\x00", objects=b""):
    """Transport segment (FIR|FIN, sequence 0) carrying one response fragment."""
    return bytes([0xC0, app_control, function]) + iin + objects


def make_master(chunks, **config):
    """A DNP3Master wired to a FakeSocket that delivers `chunks`."""
    master = DNP3Master(DNP3Config(response_timeout=0.5, **config))
    master._socket = FakeSocket(chunks)
    master._connected = True
    return master


def sent_frames(master):
    """The frames the master wrote, parsed."""
    return [DataLinkLayer().parse_frame(data)[0] for data in master._socket.sent]


RESTARTED = response_segment(iin=b"\x80\x00")  # IIN1.7 DEVICE_RESTART
CLEARED = response_segment(app_control=0xC1, iin=b"\x00\x00")
WRITE_IIN7 = bytes([0x02, 80, 1, 0x00, 7, 7, 0x00])  # WRITE g80v1 start 7 stop 7, value 0


def requests(master):
    """Application function and objects of each request the master sent."""
    return [frame.user_data[2:] for frame in sent_frames(master)]


class TestClearDeviceRestart:
    """The master clears IIN1.7 by writing g80v1 index 7."""

    def test_restart_is_cleared_after_a_response_reports_it(self):
        master = make_master(
            [outstation_frame(RESTARTED), outstation_frame(CLEARED)], confirm_required=False
        )
        response = master._send_request(master._application.build_integrity_poll())

        assert response.iin.device_restart
        poll, write = requests(master)
        assert poll[0] == 0x01  # READ
        assert write == WRITE_IIN7

    def test_clear_restart_method(self):
        master = make_master([outstation_frame(CLEARED)], confirm_required=False)
        assert master.clear_restart()
        assert requests(master) == [WRITE_IIN7]

    def test_clear_restart_reports_a_rejected_write(self):
        rejected = response_segment(iin=b"\x80\x04")  # IIN2.2 PARAMETER_ERROR
        master = make_master([outstation_frame(rejected)], confirm_required=False)
        assert not master.clear_restart()
        assert len(requests(master)) == 1  # no second write for the still-set IIN1.7

    def test_disabled_by_config(self):
        master = make_master(
            [outstation_frame(RESTARTED)], confirm_required=False, clear_restart=False
        )
        master._send_request(master._application.build_integrity_poll())
        assert len(requests(master)) == 1

    def test_failed_clear_does_not_fail_the_request(self):
        """If the write gets no response, the original response is still returned."""
        master = make_master([outstation_frame(RESTARTED)], confirm_required=False)
        response = master._send_request(master._application.build_integrity_poll())
        assert response is not None and response.iin.device_restart
        assert requests(master)[1] == WRITE_IIN7
