"""Tests for DNP3 Application Layer."""

import pytest
from dnp3py.layers.application import (
    ApplicationLayer,
    ApplicationRequest,
    ApplicationResponse,
    ObjectHeader,
    FIR_FLAG,
    FIN_FLAG,
)
from dnp3py.core.config import AppLayerFunction, QualifierCode, IINFlags
from dnp3py.core.exceptions import DNP3ProtocolError, DNP3ObjectError


class TestObjectHeader:
    """Tests for ObjectHeader class."""

    def test_to_bytes_all_objects(self):
        """Test serialization with ALL_OBJECTS qualifier."""
        header = ObjectHeader(
            group=60,
            variation=1,
            qualifier=QualifierCode.ALL_OBJECTS,
        )
        data = header.to_bytes()

        assert data[0] == 60  # Group
        assert data[1] == 1   # Variation
        assert data[2] == QualifierCode.ALL_OBJECTS

    def test_to_bytes_uint8_start_stop(self):
        """Test serialization with 8-bit start/stop."""
        header = ObjectHeader(
            group=1,
            variation=2,
            qualifier=QualifierCode.UINT8_START_STOP,
            range_start=0,
            range_stop=9,
        )
        data = header.to_bytes()

        assert len(data) == 5
        assert data[3] == 0  # Start
        assert data[4] == 9  # Stop

    def test_to_bytes_uint16_start_stop(self):
        """Test serialization with 16-bit start/stop."""
        header = ObjectHeader(
            group=30,
            variation=1,
            qualifier=QualifierCode.UINT16_START_STOP,
            range_start=0,
            range_stop=255,
        )
        data = header.to_bytes()

        assert len(data) == 7
        # Little-endian encoding
        assert data[3] == 0x00  # Start low
        assert data[4] == 0x00  # Start high
        assert data[5] == 0xFF  # Stop low
        assert data[6] == 0x00  # Stop high

    def test_from_bytes_all_objects(self):
        """Test parsing ALL_OBJECTS header."""
        data = bytes([60, 1, QualifierCode.ALL_OBJECTS])
        header, consumed = ObjectHeader.from_bytes(data)

        assert header.group == 60
        assert header.variation == 1
        assert header.qualifier == QualifierCode.ALL_OBJECTS
        assert consumed == 3

    def test_from_bytes_with_range(self):
        """Test parsing header with range."""
        data = bytes([1, 2, QualifierCode.UINT8_START_STOP, 5, 10])
        header, consumed = ObjectHeader.from_bytes(data)

        assert header.group == 1
        assert header.variation == 2
        assert header.range_start == 5
        assert header.range_stop == 10
        assert header.count == 6  # 10 - 5 + 1
        assert consumed == 5

    def test_from_bytes_invalid_range(self):
        """Test parsing header with invalid range raises error."""
        data = bytes([1, 2, QualifierCode.UINT8_START_STOP, 10, 5])
        with pytest.raises(DNP3ObjectError):
            ObjectHeader.from_bytes(data)

    def test_to_bytes_invalid_range(self):
        """Test serialization with invalid range raises error."""
        header = ObjectHeader(
            group=1,
            variation=2,
            qualifier=QualifierCode.UINT16_START_STOP,
            range_start=10,
            range_stop=1,
        )
        with pytest.raises(DNP3ObjectError):
            header.to_bytes()

    def test_to_bytes_invalid_group_variation_qualifier(self):
        """Test serialization with out-of-range group/variation/qualifier raises error."""
        with pytest.raises(DNP3ObjectError, match="group"):
            ObjectHeader(group=256, variation=1, qualifier=QualifierCode.ALL_OBJECTS).to_bytes()
        with pytest.raises(DNP3ObjectError, match="variation"):
            ObjectHeader(group=1, variation=256, qualifier=QualifierCode.ALL_OBJECTS).to_bytes()

    def test_to_bytes_uint8_count_out_of_range(self):
        """Test UINT8 count out of range raises error."""
        header = ObjectHeader(
            group=1, variation=2, qualifier=QualifierCode.UINT8_COUNT, count=256
        )
        with pytest.raises(DNP3ObjectError, match="UINT8 count"):
            header.to_bytes()

    def test_from_bytes_with_offset(self):
        """Test parsing header at offset."""
        data = bytes([0xFF, 0xFF, 60, 1, QualifierCode.ALL_OBJECTS])
        header, consumed = ObjectHeader.from_bytes(data, offset=2)

        assert header.group == 60
        assert consumed == 3

    def test_from_bytes_invalid_offset(self):
        """Test parsing with invalid offset raises error."""
        data = bytes([60, 1, QualifierCode.ALL_OBJECTS])
        with pytest.raises(DNP3ObjectError, match="offset"):
            ObjectHeader.from_bytes(data, offset=-1)
        with pytest.raises(DNP3ObjectError, match="beyond data length"):
            ObjectHeader.from_bytes(data, offset=10)


class TestApplicationRequest:
    """Tests for ApplicationRequest class."""

    def test_control_byte(self):
        """Test control byte construction."""
        request = ApplicationRequest(
            function=AppLayerFunction.READ,
            sequence=5,
            first=True,
            final=True,
            confirm=True,
        )
        control = request.control

        assert control & 0x0F == 5  # Sequence
        assert control & FIR_FLAG
        assert control & FIN_FLAG
        assert control & 0x20  # Confirm

    def test_to_bytes(self):
        """Test request serialization."""
        request = ApplicationRequest(
            function=AppLayerFunction.READ,
            sequence=0,
            objects=[
                ObjectHeader(group=60, variation=1, qualifier=QualifierCode.ALL_OBJECTS),
            ],
        )
        data = request.to_bytes()

        assert data[0] & FIR_FLAG
        assert data[0] & FIN_FLAG
        assert data[1] == AppLayerFunction.READ

    def test_read_class_0(self):
        """Test Class 0 read request creation."""
        request = ApplicationRequest.read_class_0(sequence=3)

        assert request.function == AppLayerFunction.READ
        assert request.sequence == 3
        assert len(request.objects) == 1
        assert request.objects[0].group == 60
        assert request.objects[0].variation == 1

    def test_read_all_classes(self):
        """Test integrity poll request creation."""
        request = ApplicationRequest.read_all_classes(sequence=1)

        assert len(request.objects) == 4
        variations = [obj.variation for obj in request.objects]
        assert variations == [1, 2, 3, 4]  # Class 0, 1, 2, 3

    def test_read_binary_inputs(self):
        """Test binary inputs read request."""
        request = ApplicationRequest.read_binary_inputs(start=0, stop=15, sequence=0)

        assert request.function == AppLayerFunction.READ
        assert request.objects[0].group == 1
        assert request.objects[0].range_start == 0
        assert request.objects[0].range_stop == 15


class TestApplicationResponse:
    """Tests for ApplicationResponse class."""

    def test_from_bytes_minimal(self):
        """Test parsing minimal response."""
        # Control, Function, IIN1, IIN2
        data = bytes([0xC0, 0x81, 0x00, 0x00])
        response = ApplicationResponse.from_bytes(data)

        assert response.function == 0x81  # Response
        assert response.first is True
        assert response.final is True
        assert response.sequence == 0
        assert isinstance(response.iin, IINFlags)

    def test_from_bytes_with_iin_errors(self):
        """Test parsing response with IIN errors."""
        # IIN2 bit 0 = function not supported
        data = bytes([0xC0, 0x81, 0x00, 0x01])
        response = ApplicationResponse.from_bytes(data)

        assert response.iin.no_func_code_support is True
        assert response.iin.has_errors() is True

    def test_from_bytes_unsolicited(self):
        """Test parsing unsolicited response."""
        # UNS flag set
        data = bytes([0xD0, 0x82, 0x00, 0x00])
        response = ApplicationResponse.from_bytes(data)

        assert response.unsolicited is True
        assert response.function == 0x82

    def test_from_bytes_too_short(self):
        """Test parsing response that is too short."""
        data = bytes([0xC0, 0x81, 0x00])  # Missing IIN2
        with pytest.raises(DNP3ProtocolError):
            ApplicationResponse.from_bytes(data)

    def test_from_bytes_invalid_function(self):
        """Test parsing response with invalid function code."""
        data = bytes([0xC0, 0x05, 0x00, 0x00])  # Function code is request
        with pytest.raises(DNP3ProtocolError):
            ApplicationResponse.from_bytes(data)

    def test_from_bytes_reserved_iin_bits(self):
        """Test parsing response with reserved IIN bits set."""
        data = bytes([0xC0, 0x81, 0x00, 0x40])  # IIN2 reserved bit 6 set
        response = ApplicationResponse.from_bytes(data)
        assert response.iin.has_reserved_bits() is True

    def test_confirm_required_flag(self):
        """Test confirm required parsing."""
        # CON flag set
        data = bytes([0xE0, 0x81, 0x00, 0x00])
        response = ApplicationResponse.from_bytes(data)

        assert response.confirm_required is True


class TestApplicationLayer:
    """Tests for ApplicationLayer class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.layer = ApplicationLayer()

    def test_build_request(self):
        """Test building a basic request."""
        apdu = self.layer.build_request(AppLayerFunction.READ)

        assert apdu[1] == AppLayerFunction.READ
        assert apdu[0] & FIR_FLAG
        assert apdu[0] & FIN_FLAG

    def test_build_request_with_objects(self):
        """Test building request with object headers."""
        objects = [
            ObjectHeader(group=60, variation=1, qualifier=QualifierCode.ALL_OBJECTS),
        ]
        apdu = self.layer.build_request(AppLayerFunction.READ, objects)

        assert len(apdu) > 2  # Control + Function + Object header

    def test_sequence_increment(self):
        """Test sequence number increments."""
        seq0 = self.layer.sequence
        self.layer.build_request(AppLayerFunction.READ)
        seq1 = self.layer.sequence

        assert seq1 == (seq0 + 1) & 0x0F

    def test_sequence_wrap(self):
        """Test sequence wraps at 16."""
        self.layer._tx_sequence = 15
        self.layer.build_request(AppLayerFunction.READ)
        assert self.layer.sequence == 0

    def test_build_confirm(self):
        """Test building confirmation."""
        confirm = self.layer.build_confirm(sequence=5, unsolicited=False)

        assert confirm[0] & 0x0F == 5  # Sequence
        assert confirm[1] == AppLayerFunction.CONFIRM

    def test_build_confirm_unsolicited(self):
        """Test building unsolicited confirmation."""
        confirm = self.layer.build_confirm(sequence=3, unsolicited=True)

        assert confirm[0] & 0x10  # UNS flag

    def test_build_confirm_invalid_sequence(self):
        """Test build_confirm with invalid sequence raises error."""
        with pytest.raises(ValueError, match="0-15"):
            self.layer.build_confirm(sequence=16)
        with pytest.raises(ValueError, match="0-15"):
            self.layer.build_confirm(sequence=-1)

    def test_build_integrity_poll(self):
        """Test building integrity poll."""
        apdu = self.layer.build_integrity_poll()

        assert apdu[1] == AppLayerFunction.READ
        # Should contain class 0, 1, 2, 3 object headers

    def test_build_class_poll(self):
        """Test building class-specific poll."""
        apdu = self.layer.build_class_poll(1)
        assert apdu[1] == AppLayerFunction.READ

        with pytest.raises(ValueError):
            self.layer.build_class_poll(5)  # Invalid class

    def test_build_read_request_all_objects(self):
        """Test building read request for all objects."""
        apdu = self.layer.build_read_request(group=1, variation=0)

        assert apdu[1] == AppLayerFunction.READ

    def test_build_read_request_range(self):
        """Test building read request with range."""
        apdu = self.layer.build_read_request(group=30, variation=1, start=0, stop=10)

        assert apdu[1] == AppLayerFunction.READ

    def test_build_read_request_invalid_args(self):
        """Test build_read_request with invalid args raises error."""
        with pytest.raises(ValueError, match="Group"):
            self.layer.build_read_request(group=256, variation=0)
        with pytest.raises(ValueError, match="Start"):
            self.layer.build_read_request(group=1, variation=0, start=-1, stop=5)
        with pytest.raises(ValueError, match="Stop"):
            self.layer.build_read_request(group=1, variation=0, start=0, stop=-1)
        with pytest.raises(ValueError, match="Start must be <= stop"):
            self.layer.build_read_request(group=1, variation=0, start=10, stop=5)

    def test_parse_response(self):
        """Test parsing response."""
        data = bytes([0xC0, 0x81, 0x00, 0x00])
        response = self.layer.parse_response(data)

        assert isinstance(response, ApplicationResponse)
        assert response.function == 0x81

    def test_reset_sequence(self):
        """Test sequence reset."""
        self.layer.build_request(AppLayerFunction.READ)
        self.layer.build_request(AppLayerFunction.READ)
        assert self.layer.sequence > 0

        self.layer.reset_sequence()
        assert self.layer.sequence == 0


class TestApplicationResponseDataOffset:
    """Tests for ApplicationResponse data offset calculation."""

    def test_response_with_object_data_offset(self):
        """Test that response parsing calculates correct data offsets."""
        # Build a response with binary inputs (group 1, variation 2)
        # Control + Function + IIN1 + IIN2 + ObjHeader(g1v2, q=0x00, start=0, stop=1) + 2 bytes data
        data = bytes([
            0xC0,  # Control: FIR|FIN, seq=0
            0x81,  # Function: Response
            0x00, 0x00,  # IIN1, IIN2
            0x01, 0x02, 0x00,  # Group 1, Variation 2, Qualifier UINT8_START_STOP
            0x00, 0x01,  # Range: 0 to 1 (2 points)
            0x81, 0x01,  # Data: 2 bytes for 2 binary inputs with flags
        ])

        response = ApplicationResponse.from_bytes(data)

        assert len(response.objects) == 1
        obj_header = response.objects[0]
        assert obj_header.group == 1
        assert obj_header.variation == 2
        assert obj_header.count == 2
        # data_offset should point to byte 5 in raw_data (after 5-byte header: g,v,q,start,stop)
        assert obj_header.data_offset == 5

    def test_response_with_multiple_objects(self):
        """Test response with multiple object headers."""
        # Response with binary inputs and analog inputs
        data = bytes([
            0xC0, 0x81, 0x00, 0x00,  # Header
            # Object 1: Group 1, Var 2, Q=0x00, range 0-0 (1 point), 1 byte data
            0x01, 0x02, 0x00, 0x00, 0x00, 0x81,
            # Object 2: Group 30, Var 1, Q=0x00, range 0-0 (1 point), 5 bytes data
            0x1E, 0x01, 0x00, 0x00, 0x00, 0x01, 0x64, 0x00, 0x00, 0x00,
        ])

        response = ApplicationResponse.from_bytes(data)

        assert len(response.objects) == 2
        # First object data starts at offset 5
        assert response.objects[0].data_offset == 5
        # Second object data starts after first header (5 bytes) + first data (1 byte) + second header (5 bytes)
        assert response.objects[1].data_offset == 5 + 1 + 5


class TestIINFlags:
    """Tests for IINFlags class."""

    def test_from_bytes(self):
        """Test parsing IIN bytes."""
        # Class 1 events, device restart
        iin = IINFlags.from_bytes(0x82, 0x00)

        assert iin.class_1_events is True
        assert iin.device_restart is True
        assert iin.class_2_events is False

    def test_to_bytes(self):
        """Test converting flags to bytes."""
        iin = IINFlags(class_1_events=True, need_time=True)
        iin1, iin2 = iin.to_bytes()

        assert iin1 & 0x02  # Class 1 events
        assert iin1 & 0x10  # Need time

    def test_has_errors(self):
        """Test error detection."""
        iin = IINFlags()
        assert iin.has_errors() is False

        iin = IINFlags(object_unknown=True)
        assert iin.has_errors() is True

        iin = IINFlags(parameter_error=True)
        assert iin.has_errors() is True
