"""Tests for the link service of the master's application confirm."""

import socket

from dnp3py.core.config import DNP3Config
from dnp3py.core.master import DNP3Master
from dnp3py.layers.datalink import ControlByte, DataLinkLayer, PrimaryFunction
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


CON_RESPONSE = response_segment(app_control=0xE0)  # FIR|FIN|CON, sequence 0


class TestApplicationConfirmLinkService:
    """The application confirm uses the link service configured for requests."""

    def test_unconfirmed_when_confirm_not_required(self):
        """With confirm_required=False the confirm is UNCONFIRMED_USER_DATA."""
        master = make_master([outstation_frame(CON_RESPONSE)], confirm_required=False)
        master._send_request(master._application.build_integrity_poll())

        request, confirm = sent_frames(master)
        for frame in (request, confirm):
            assert frame.function_code == PrimaryFunction.USER_DATA_UNCONFIRMED
            assert not frame.fcv
        assert confirm.user_data[1:] == bytes([0xC0, 0x00])  # FIR|FIN seq 0, CONFIRM

    def test_confirmed_frames_toggle_fcb(self):
        """With confirm_required=True the confirm continues the request's FCB sequence."""
        master = make_master([outstation_frame(CON_RESPONSE)], confirm_required=True)
        master._send_request(master._application.build_integrity_poll())

        request, confirm = sent_frames(master)
        for frame in (request, confirm):
            assert frame.function_code == PrimaryFunction.USER_DATA_CONFIRMED
            assert frame.fcv
        assert request.fcb != confirm.fcb
        assert request.control & ControlByte.DIR
