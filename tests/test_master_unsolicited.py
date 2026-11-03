"""Tests for unsolicited responses that arrive while the master awaits a solicited one."""

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


# FIR|FIN|CON|UNS, sequence 0, UNSOLICITED_RESPONSE, IIN1.7 DEVICE_RESTART
NULL_UNSOLICITED = response_segment(app_control=0xF0, function=0x82, iin=b"\x80\x00")
SOLICITED = response_segment(app_control=0xC1, function=0x81, iin=b"\x00\x00")


class TestUnsolicitedDuringRequest:
    """An unsolicited response is not taken as the answer to a request."""

    def test_solicited_response_is_returned(self):
        """The null unsolicited response is skipped; the solicited response is returned."""
        master = make_master(
            [outstation_frame(NULL_UNSOLICITED), outstation_frame(SOLICITED)],
            confirm_required=False,
        )
        received = []
        master.set_unsolicited_callback(received.append)

        response = master._send_request(master._application.build_integrity_poll())

        assert response is not None
        assert response.function == 0x81
        assert not response.unsolicited
        assert response.sequence == 1
        assert [r.function for r in received] == [0x82]

    def test_unsolicited_response_is_confirmed(self):
        """The skipped unsolicited response is still confirmed, with UNS set."""
        master = make_master(
            [outstation_frame(NULL_UNSOLICITED), outstation_frame(SOLICITED)],
            confirm_required=False,
        )
        master._send_request(master._application.build_integrity_poll())

        confirms = [f.user_data[1:] for f in sent_frames(master) if f.user_data[2:3] == b"\x00"]
        assert confirms == [bytes([0xD0, 0x00])]  # FIR|FIN|UNS seq 0, CONFIRM

    def test_callback_exception_does_not_fail_the_request(self):
        """A failing callback is logged; the request still gets its response."""

        def fail(response):
            raise RuntimeError("callback failure")

        master = make_master(
            [outstation_frame(NULL_UNSOLICITED), outstation_frame(SOLICITED)],
            confirm_required=False,
        )
        master.set_unsolicited_callback(fail)
        response = master._send_request(master._application.build_integrity_poll())
        assert response is not None and response.function == 0x81

    def test_receive_any_response(self):
        """With solicited=False the next response is returned, unsolicited or not."""
        master = make_master([outstation_frame(NULL_UNSOLICITED)], confirm_required=False)
        response = master._receive_response(solicited=False)
        assert response.unsolicited
        assert response.function == 0x82
