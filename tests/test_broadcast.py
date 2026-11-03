"""Tests for requests sent to a broadcast address."""

import socket

import pytest

from dnp3py.core.config import AppLayerFunction, DNP3Config
from dnp3py.core.master import DNP3Master
from dnp3py.layers.datalink import DataLinkLayer, PrimaryFunction
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


class TestBroadcastDestination:
    """The broadcast addresses 0xFFFD, 0xFFFE and 0xFFFF are valid destinations."""

    @pytest.mark.parametrize("address", [0xFFFD, 0xFFFE, 0xFFFF])
    def test_build_frame_accepts_broadcast(self, address):
        frame = DataLinkLayer().build_frame(b"\xc0\xc0\x02", destination=address, confirmed=False)
        assert DataLinkLayer().parse_frame(frame)[0].destination == address

    def test_build_frame_still_refuses_reserved_addresses(self):
        with pytest.raises(ValueError):
            DataLinkLayer().build_frame(b"\xc0", destination=0xFFF0)

    @pytest.mark.parametrize("address", [0xFFFD, 0xFFFE, 0xFFFF])
    def test_send_broadcast(self, address):
        """send_broadcast writes one unconfirmed frame and waits for nothing."""
        master = make_master([])
        master.send_broadcast(AppLayerFunction.DISABLE_UNSOLICITED, destination=address)

        (frame,) = sent_frames(master)
        assert frame.destination == address
        assert frame.source == MASTER_ADDRESS
        assert frame.function_code == PrimaryFunction.USER_DATA_UNCONFIRMED
        assert frame.user_data[2] == AppLayerFunction.DISABLE_UNSOLICITED

    def test_send_broadcast_refuses_station_address(self):
        master = make_master([])
        with pytest.raises(ValueError):
            master.send_broadcast(AppLayerFunction.READ, destination=OUTSTATION_ADDRESS)
