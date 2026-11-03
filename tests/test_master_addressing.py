"""Tests for the address check on frames the master receives."""

import socket

import pytest

from dnp3py.core.config import DNP3Config
from dnp3py.core.exceptions import DNP3TimeoutError
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


RESPONSE = response_segment()
OTHER = response_segment(iin=b"\x00\x04")  # IIN2.2 marks a response meant for someone else


class TestDestinationAddressCheck:
    """Only frames from the outstation to this master are processed."""

    @pytest.mark.parametrize(
        ("destination", "source", "control"),
        [
            (7, OUTSTATION_ADDRESS, 0x44),  # another master
            (MASTER_ADDRESS, 11, 0x44),  # another outstation
            (MASTER_ADDRESS, OUTSTATION_ADDRESS, 0xC4),  # DIR set: sent by a master
        ],
    )
    def test_foreign_frame_is_dropped(self, destination, source, control):
        """A frame for another station is skipped; the next one for this master is returned."""
        master = make_master(
            [
                outstation_frame(OTHER, control=control, destination=destination, source=source),
                outstation_frame(RESPONSE),
            ],
            confirm_required=False,
        )
        response = master._send_request(master._application.build_integrity_poll())
        assert response is not None
        assert not response.iin.parameter_error

    def test_only_foreign_frames_time_out(self):
        """A response addressed to another master is not accepted."""
        master = make_master(
            [outstation_frame(RESPONSE, destination=7)],
            confirm_required=False,
            master_address=MASTER_ADDRESS,
        )
        with pytest.raises(DNP3TimeoutError):
            master._send_request(master._application.build_integrity_poll())
