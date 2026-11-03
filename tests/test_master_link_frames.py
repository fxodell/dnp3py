"""Tests for link-layer frames the master receives from the outstation."""

import socket

from dnp3py.core.config import DNP3Config
from dnp3py.core.master import DNP3Master
from dnp3py.layers.datalink import ControlByte, DataLinkLayer, SecondaryFunction
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


ACK = 0x00  # secondary, ACK
NACK = 0x01  # secondary, NACK
RESET_LINK = 0x40  # primary, RESET_LINK_STATES
TEST_LINK = 0x42  # primary, TEST_LINK_STATES (FCB clear)
REQUEST_LINK_STATUS = 0x49  # primary, REQUEST_LINK_STATUS
CONFIRMED_FCB1 = 0x73  # primary, FCB=1, FCV=1, CONFIRMED_USER_DATA
CONFIRMED_FCB0 = 0x53  # primary, FCB=0, FCV=1, CONFIRMED_USER_DATA

RESPONSE = response_segment(iin=b"\x00\x00")


def replies(master):
    """Secondary frames (no user data) the master wrote."""
    return [frame for frame in sent_frames(master) if not frame.is_primary]


class TestLinkFramesWithoutUserData:
    """Frames without user data do not break the receive path."""

    def test_secondary_frames_are_skipped(self):
        """ACK and NACK before the response are skipped, the response is returned."""
        master = make_master(
            [
                outstation_frame(control=ACK),
                outstation_frame(control=NACK),
                outstation_frame(RESPONSE),
            ],
            confirm_required=False,
        )
        response = master._send_request(master._application.build_integrity_poll())
        assert response is not None
        assert response.function == 0x81

    def test_request_link_status_is_answered(self):
        """REQUEST_LINK_STATUS is answered with LINK_STATUS."""
        master = make_master(
            [outstation_frame(control=REQUEST_LINK_STATUS), outstation_frame(RESPONSE)],
            confirm_required=False,
        )
        assert master._send_request(master._application.build_integrity_poll()) is not None
        (reply,) = replies(master)
        assert reply.function_code == SecondaryFunction.LINK_STATUS
        assert reply.control & ControlByte.DIR
        assert (reply.destination, reply.source) == (OUTSTATION_ADDRESS, MASTER_ADDRESS)

    def test_test_link_is_acknowledged(self):
        """TEST_LINK_STATES is answered with ACK."""
        master = make_master(
            [outstation_frame(control=TEST_LINK), outstation_frame(RESPONSE)],
            confirm_required=False,
        )
        assert master._send_request(master._application.build_integrity_poll()) is not None
        (reply,) = replies(master)
        assert reply.function_code == SecondaryFunction.ACK


class TestConfirmedUserDataFromOutstation:
    """An outstation that uses link confirms gets its ACKs."""

    def test_reset_and_confirmed_data_are_acknowledged(self):
        """RESET_LINK_STATES and CONFIRMED_USER_DATA are each ACKed; the response is delivered."""
        master = make_master(
            [
                outstation_frame(control=RESET_LINK),
                outstation_frame(RESPONSE, control=CONFIRMED_FCB1),
            ],
            confirm_required=False,
        )
        response = master._send_request(master._application.build_integrity_poll())
        assert response is not None
        assert [reply.function_code for reply in replies(master)] == [
            SecondaryFunction.ACK,
            SecondaryFunction.ACK,
        ]

    def test_repeated_frame_is_acknowledged_not_delivered(self):
        """A repeated frame (same FCB) is ACKed again but not taken as the next response."""
        second = response_segment(iin=b"\x00\x04")  # IIN2.2 marks the second response
        master = make_master(
            [
                outstation_frame(control=RESET_LINK),
                outstation_frame(RESPONSE, control=CONFIRMED_FCB1),
                outstation_frame(RESPONSE, control=CONFIRMED_FCB1),  # repeat
                outstation_frame(second, control=CONFIRMED_FCB0),
            ],
            confirm_required=False,
        )
        first = master._send_request(master._application.build_integrity_poll())
        assert first is not None and not first.iin.parameter_error
        following = master._send_request(master._application.build_integrity_poll())
        assert following is not None and following.iin.parameter_error
        assert len(replies(master)) == 4
