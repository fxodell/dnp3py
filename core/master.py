"""
DNP3 Master Station implementation.

The Master class provides high-level DNP3 communication capabilities
over TCP/IP, coordinating all protocol layers.
"""

import socket
import time
import threading
from typing import Optional, List, Callable, Union
from dataclasses import dataclass, field
from contextlib import contextmanager

from pydnp3.core.config import (
    DNP3Config,
    AppLayerFunction,
    QualifierCode,
    IINFlags,
    ControlStatus,
)
from pydnp3.core.exceptions import (
    DNP3Error,
    DNP3CommunicationError,
    DNP3TimeoutError,
    DNP3ProtocolError,
    DNP3CRCError,
    DNP3FrameError,
    DNP3ControlError,
)
from pydnp3.layers.datalink import DataLinkLayer, DataLinkFrame
from pydnp3.layers.transport import TransportLayer
from pydnp3.layers.application import (
    ApplicationLayer,
    ApplicationResponse,
    ObjectHeader,
)
from pydnp3.objects.binary import (
    BinaryInput,
    BinaryOutput,
    BinaryOutputCommand,
    parse_binary_inputs,
    parse_binary_outputs,
)
from pydnp3.objects.analog import (
    AnalogInput,
    AnalogOutput,
    AnalogOutputCommand,
    parse_analog_inputs,
    parse_analog_outputs,
)
from pydnp3.objects.counter import Counter, parse_counters
from pydnp3.objects.groups import ObjectGroup, ObjectVariation, get_object_size
from pydnp3.utils.logging import get_logger, log_frame


@dataclass
class PollResult:
    """Result of a polling operation."""

    success: bool
    iin: Optional[IINFlags] = None
    binary_inputs: List[BinaryInput] = field(default_factory=list)
    binary_outputs: List[BinaryOutput] = field(default_factory=list)
    analog_inputs: List[AnalogInput] = field(default_factory=list)
    analog_outputs: List[AnalogOutput] = field(default_factory=list)
    counters: List[Counter] = field(default_factory=list)
    error: Optional[str] = None
    raw_response: Optional[bytes] = None


class DNP3Master:
    """
    DNP3 Master Station for IP communication.

    Provides methods for communicating with DNP3 outstations over TCP/IP.
    Supports reading data points, controlling outputs, and handling events.

    Usage:
        config = DNP3Config(host="192.168.1.100", port=20000)
        master = DNP3Master(config)

        with master.connect():
            # Read all binary inputs
            inputs = master.read_binary_inputs(0, 10)

            # Control an output
            master.direct_operate_binary(0, True)
    """

    def __init__(self, config: Optional[DNP3Config] = None):
        """
        Initialize DNP3 Master.

        Args:
            config: Configuration settings (uses defaults if not provided)
        """
        self.config = config or DNP3Config()
        self.config.validate()

        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._lock = threading.Lock()

        # Protocol layers
        self._datalink = DataLinkLayer(
            master_address=self.config.master_address,
            outstation_address=self.config.outstation_address,
        )
        self._transport = TransportLayer()
        self._application = ApplicationLayer()

        # Receive buffer
        self._rx_buffer = bytearray()

        # Logger
        self._logger = get_logger()

        # Callback for unsolicited responses
        self._unsolicited_callback: Optional[Callable[[ApplicationResponse], None]] = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to outstation."""
        return self._connected and self._socket is not None

    @contextmanager
    def connect(self):
        """
        Context manager for connection.

        Usage:
            with master.connect():
                # Do operations
        """
        try:
            self.open()
            yield self
        finally:
            self.close()

    def open(self) -> None:
        """
        Open connection to the outstation.

        Raises:
            DNP3CommunicationError: If connection fails
        """
        with self._lock:
            if self._connected:
                return

            sock = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.config.connection_timeout)
                sock.connect((self.config.host, self.config.port))
                self._socket = sock
                self._connected = True
                self._rx_buffer.clear()
                self._logger.info(f"Connected to {self.config.host}:{self.config.port}")

                # Optional: Reset link state
                # self._reset_link()

            except socket.timeout as e:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                self._socket = None
                self._connected = False
                raise DNP3TimeoutError(
                    f"Connection timeout to {self.config.host}:{self.config.port}",
                    timeout_seconds=self.config.connection_timeout,
                ) from e
            except socket.error as e:
                if sock:
                    try:
                        sock.close()
                    except Exception:
                        pass
                self._socket = None
                self._connected = False
                raise DNP3CommunicationError(
                    f"Failed to connect: {e}",
                    host=self.config.host,
                    port=self.config.port,
                ) from e

    def close(self) -> None:
        """Close connection to the outstation."""
        with self._lock:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
            self._connected = False
            self._rx_buffer.clear()
        self._logger.info("Connection closed")

    def _send_frame(self, frame: bytes) -> None:
        """
        Send a data link frame.

        Args:
            frame: Complete frame bytes to send

        Raises:
            DNP3CommunicationError: If send fails
        """
        if not self._socket:
            raise DNP3CommunicationError("Not connected")

        try:
            if self.config.log_raw_frames:
                log_frame(frame, "TX", self._logger)
            self._socket.sendall(frame)
        except socket.error as e:
            raise DNP3CommunicationError(f"Send failed: {e}")

    def _receive_frame(self, timeout: Optional[float] = None) -> DataLinkFrame:
        """
        Receive a data link frame.

        Args:
            timeout: Receive timeout in seconds (uses config default if None)

        Returns:
            Parsed DataLinkFrame

        Raises:
            DNP3TimeoutError: If timeout occurs
            DNP3CRCError: If CRC check fails
            DNP3CommunicationError: If receive fails
        """
        if not self._socket:
            raise DNP3CommunicationError("Not connected")

        timeout = timeout or self.config.response_timeout
        self._socket.settimeout(timeout)
        start_time = time.time()

        while True:
            # Check for timeout
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                raise DNP3TimeoutError(
                    "Response timeout",
                    timeout_seconds=timeout,
                )

            # Try to parse frame from buffer
            frame_start = self._datalink.find_frame_start(self._rx_buffer)
            if frame_start > 0:
                # Discard bytes before frame start
                del self._rx_buffer[:frame_start]
            elif frame_start < 0 and len(self._rx_buffer) > 1:
                # No frame start found, keep last byte (might be partial start)
                del self._rx_buffer[:-1]

            # Check if we have enough data for header
            if len(self._rx_buffer) >= 10:
                try:
                    # Get expected frame size
                    frame_size = self._datalink.calculate_frame_size(self._rx_buffer[2])

                    if len(self._rx_buffer) >= frame_size:
                        # Log raw frame before parsing (if enabled)
                        if self.config.log_raw_frames:
                            log_frame(bytes(self._rx_buffer[:frame_size]), "RX", self._logger)

                        frame, consumed = self._datalink.parse_frame(bytes(self._rx_buffer[:frame_size]))
                        del self._rx_buffer[:consumed]

                        return frame
                except (DNP3CRCError, DNP3FrameError):
                    # Invalid frame, skip first byte and try again
                    del self._rx_buffer[:1]
                    continue

            # Need more data
            try:
                remaining_timeout = timeout - (time.time() - start_time)
                if remaining_timeout <= 0:
                    raise DNP3TimeoutError("Response timeout", timeout_seconds=timeout)

                self._socket.settimeout(remaining_timeout)
                data = self._socket.recv(1024)
                if not data:
                    raise DNP3CommunicationError("Connection closed by remote")
                self._rx_buffer.extend(data)
            except socket.timeout:
                raise DNP3TimeoutError("Response timeout", timeout_seconds=timeout)
            except socket.error as e:
                raise DNP3CommunicationError(f"Receive failed: {e}")

    def _send_request(
        self,
        apdu: bytes,
        expect_response: bool = True,
        timeout: Optional[float] = None,
    ) -> Optional[ApplicationResponse]:
        """
        Send an application layer request and optionally wait for response.

        Args:
            apdu: Application Protocol Data Unit to send
            expect_response: Whether to wait for response
            timeout: Response timeout

        Returns:
            ApplicationResponse if expect_response is True, else None
        """
        with self._lock:
            # Segment APDU
            segments = self._transport.segment(apdu)

            # Send each segment as a data link frame
            for segment in segments:
                confirmed = self.config.confirm_required
                frame = self._datalink.build_frame(
                    segment,
                    confirmed=confirmed,
                    fcv=confirmed,
                )
                self._send_frame(frame)
                if confirmed:
                    self._datalink.toggle_fcb()

            if not expect_response:
                return None

            # Receive and reassemble response
            return self._receive_response(timeout)

    def _receive_response(self, timeout: Optional[float] = None) -> ApplicationResponse:
        """
        Receive and reassemble a complete application response.

        Handles multi-fragment responses by collecting all fragments
        until FIN flag is set.

        Args:
            timeout: Response timeout (total time for all fragments)

        Returns:
            Complete ApplicationResponse (merged if multi-fragment)
        """
        timeout = timeout or self.config.response_timeout
        start_time = time.time()
        self._transport.reset()  # Reset transport layer state

        # Storage for multi-fragment responses
        fragments: List[ApplicationResponse] = []
        max_fragments = 100  # Safety limit to prevent infinite loops

        while len(fragments) < max_fragments:
            # Calculate remaining timeout
            elapsed = time.time() - start_time
            remaining_timeout = timeout - elapsed
            if remaining_timeout <= 0:
                raise DNP3TimeoutError(
                    "Multi-fragment response timeout",
                    timeout_seconds=timeout,
                )

            frame = self._receive_frame(remaining_timeout)

            # Reassemble transport layer
            apdu, complete = self._transport.reassemble(
                frame.user_data,
                timeout_seconds=remaining_timeout,
            )

            if complete and apdu is not None:
                response = self._application.parse_response(apdu)
                fragments.append(response)

                # Check for errors in IIN
                if response.iin.has_errors():
                    self._logger.warning(f"Response has IIN errors: {response.iin}")
                if response.iin.has_reserved_bits():
                    self._logger.warning(
                        "Response has reserved IIN bits set (raw=0x%02X 0x%02X, decoded=%s)",
                        response.iin1,
                        response.iin2,
                        response.iin,
                    )

                # Handle confirmation if required
                if response.confirm_required:
                    confirm = self._application.build_confirm(
                        response.sequence,
                        response.unsolicited,
                    )
                    segments = self._transport.segment(confirm)
                    for segment in segments:
                        confirm_frame = self._datalink.build_frame(segment)
                        self._send_frame(confirm_frame)

                # Check if this is the final fragment
                if response.final:
                    break

                # Reset transport layer for next fragment
                self._transport.reset()

        # Merge fragments if multiple received
        if len(fragments) == 1:
            return fragments[0]

        return self._merge_fragments(fragments)

    def _merge_fragments(self, fragments: List[ApplicationResponse]) -> ApplicationResponse:
        """
        Merge multiple application layer fragments into a single response.

        When merging fragments, object data_offset values must be adjusted to
        account for the concatenation of raw_data from previous fragments.

        Args:
            fragments: List of response fragments

        Returns:
            Merged ApplicationResponse with adjusted data offsets
        """
        if not fragments:
            raise DNP3ProtocolError("No fragments to merge")

        # Use the first fragment as base
        first = fragments[0]

        # Collect all objects and raw data from all fragments
        # Track cumulative offset to adjust object data_offset values
        all_objects = []
        all_raw_data = bytearray()
        cumulative_offset = 0

        for frag in fragments:
            # Adjust data_offset for each object in this fragment
            # to account for raw_data from previous fragments
            for obj in frag.objects:
                # Create a copy with adjusted offset to avoid modifying original
                adjusted_obj = ObjectHeader(
                    group=obj.group,
                    variation=obj.variation,
                    qualifier=obj.qualifier,
                    range_start=obj.range_start,
                    range_stop=obj.range_stop,
                    count=obj.count,
                    data=obj.data,
                    data_offset=obj.data_offset + cumulative_offset,
                )
                all_objects.append(adjusted_obj)

            # Append this fragment's raw_data and update cumulative offset
            all_raw_data.extend(frag.raw_data)
            cumulative_offset += len(frag.raw_data)

        # Return merged response with last fragment's IIN (most current state)
        return ApplicationResponse(
            function=first.function,
            sequence=fragments[-1].sequence,
            first=True,  # Merged response is complete
            final=True,
            confirm_required=False,
            unsolicited=first.unsolicited,
            iin=fragments[-1].iin,  # Use last IIN for most current state
            iin1=fragments[-1].iin1,
            iin2=fragments[-1].iin2,
            objects=all_objects,
            raw_data=bytes(all_raw_data),
        )

    def _reset_link(self) -> None:
        """Send a Reset Link frame to the outstation."""
        frame = self._datalink.build_reset_link()
        self._send_frame(frame)
        self._datalink.reset_fcb()

        # Wait for ACK (optional, depends on outstation configuration)
        try:
            response_frame = self._receive_frame(timeout=2.0)
            self._logger.debug(f"Reset link response: {response_frame}")
        except DNP3TimeoutError:
            self._logger.debug("No response to reset link (may be normal)")

    # =========================================================================
    # High-level read operations
    # =========================================================================

    def integrity_poll(self) -> PollResult:
        """
        Perform an integrity poll (read all classes).

        Returns:
            PollResult with all data points
        """
        try:
            apdu = self._application.build_integrity_poll()
            response = self._send_request(apdu)

            if response is None:
                return PollResult(success=False, error="No response received")

            return self._parse_poll_response(response)
        except DNP3Error as e:
            return PollResult(success=False, error=str(e))

    def read_class(self, class_num: int) -> PollResult:
        """
        Read a specific data class.

        Args:
            class_num: Class number (0, 1, 2, or 3)

        Returns:
            PollResult with data from the specified class
        """
        try:
            apdu = self._application.build_class_poll(class_num)
            response = self._send_request(apdu)

            if response is None:
                return PollResult(success=False, error="No response received")

            return self._parse_poll_response(response)
        except DNP3Error as e:
            return PollResult(success=False, error=str(e))

    def read_binary_inputs(
        self,
        start: int = 0,
        stop: int = 0,
    ) -> List[BinaryInput]:
        """
        Read binary input points.

        Args:
            start: Start index
            stop: Stop index (inclusive)

        Returns:
            List of BinaryInput objects
        """
        apdu = self._application.build_read_request(
            group=ObjectGroup.BINARY_INPUT,
            variation=0,  # Any variation
            start=start,
            stop=stop,
        )
        response = self._send_request(apdu)

        if response is None:
            return []

        return self._parse_binary_inputs(response)

    def read_analog_inputs(
        self,
        start: int = 0,
        stop: int = 0,
    ) -> List[AnalogInput]:
        """
        Read analog input points.

        Args:
            start: Start index
            stop: Stop index (inclusive)

        Returns:
            List of AnalogInput objects
        """
        apdu = self._application.build_read_request(
            group=ObjectGroup.ANALOG_INPUT,
            variation=0,
            start=start,
            stop=stop,
        )
        response = self._send_request(apdu)

        if response is None:
            return []

        return self._parse_analog_inputs(response)

    def read_counters(
        self,
        start: int = 0,
        stop: int = 0,
    ) -> List[Counter]:
        """
        Read counter points.

        Args:
            start: Start index
            stop: Stop index (inclusive)

        Returns:
            List of Counter objects
        """
        apdu = self._application.build_read_request(
            group=ObjectGroup.COUNTER,
            variation=0,
            start=start,
            stop=stop,
        )
        response = self._send_request(apdu)

        if response is None:
            return []

        return self._parse_counters(response)

    def read_binary_outputs(
        self,
        start: int = 0,
        stop: int = 0,
    ) -> List[BinaryOutput]:
        """
        Read binary output status.

        Args:
            start: Start index
            stop: Stop index (inclusive)

        Returns:
            List of BinaryOutput objects
        """
        apdu = self._application.build_read_request(
            group=ObjectGroup.BINARY_OUTPUT,
            variation=0,
            start=start,
            stop=stop,
        )
        response = self._send_request(apdu)

        if response is None:
            return []

        return self._parse_binary_outputs(response)

    def read_analog_outputs(
        self,
        start: int = 0,
        stop: int = 0,
    ) -> List[AnalogOutput]:
        """
        Read analog output status.

        Args:
            start: Start index
            stop: Stop index (inclusive)

        Returns:
            List of AnalogOutput objects
        """
        apdu = self._application.build_read_request(
            group=ObjectGroup.ANALOG_OUTPUT,
            variation=0,
            start=start,
            stop=stop,
        )
        response = self._send_request(apdu)

        if response is None:
            return []

        return self._parse_analog_outputs(response)

    # =========================================================================
    # Control operations
    # =========================================================================

    def direct_operate_binary(
        self,
        index: int,
        value: bool,
        control_code: Optional[int] = None,
    ) -> bool:
        """
        Directly operate a binary output point.

        Args:
            index: Point index
            value: Desired state (True=ON, False=OFF)
            control_code: Optional specific control code

        Returns:
            True if successful
        """
        if control_code is None:
            cmd = BinaryOutputCommand.latch_on(index) if value else BinaryOutputCommand.latch_off(index)
        else:
            cmd = BinaryOutputCommand(index=index, control_code=control_code)

        return self._direct_operate_crob(cmd)

    def direct_operate_analog(
        self,
        index: int,
        value: Union[int, float],
    ) -> bool:
        """
        Directly operate an analog output point.

        Args:
            index: Point index
            value: Desired setpoint value

        Returns:
            True if successful
        """
        cmd = AnalogOutputCommand.create(index, value)
        return self._direct_operate_aob(cmd)

    def select_operate_binary(
        self,
        index: int,
        value: bool,
        control_code: Optional[int] = None,
    ) -> bool:
        """
        Select-Before-Operate control for binary output.

        Args:
            index: Point index
            value: Desired state
            control_code: Optional specific control code

        Returns:
            True if successful
        """
        if control_code is None:
            cmd = BinaryOutputCommand.latch_on(index) if value else BinaryOutputCommand.latch_off(index)
        else:
            cmd = BinaryOutputCommand(index=index, control_code=control_code)

        return self._select_operate_crob(cmd)

    def pulse_binary(
        self,
        index: int,
        on_time: int,
        off_time: int = 0,
        count: int = 1,
        pulse_on: bool = True,
    ) -> bool:
        """
        Pulse a binary output.

        Args:
            index: Point index
            on_time: On time in milliseconds
            off_time: Off time in milliseconds
            count: Number of pulses
            pulse_on: True for pulse-on, False for pulse-off

        Returns:
            True if successful
        """
        if pulse_on:
            cmd = BinaryOutputCommand.pulse_on(index, on_time, off_time, count)
        else:
            cmd = BinaryOutputCommand.pulse_off(index, on_time, off_time, count)

        return self._direct_operate_crob(cmd)

    def _direct_operate_crob(self, cmd: BinaryOutputCommand) -> bool:
        """Direct operate a Control Relay Output Block."""
        obj_header = ObjectHeader(
            group=ObjectGroup.CONTROL_RELAY_OUTPUT_BLOCK,
            variation=1,
            qualifier=QualifierCode.UINT8_COUNT_UINT16_INDEX,
            count=1,
            data=bytes([cmd.index & 0xFF, (cmd.index >> 8) & 0xFF]) + cmd.to_bytes(),
        )

        apdu = self._application.build_request(
            AppLayerFunction.DIRECT_OPERATE,
            [obj_header],
        )

        response = self._send_request(apdu)
        if response is None:
            return False

        return self._check_control_response(response)

    def _select_operate_crob(self, cmd: BinaryOutputCommand) -> bool:
        """Select-Before-Operate a Control Relay Output Block."""
        obj_header = ObjectHeader(
            group=ObjectGroup.CONTROL_RELAY_OUTPUT_BLOCK,
            variation=1,
            qualifier=QualifierCode.UINT8_COUNT_UINT16_INDEX,
            count=1,
            data=bytes([cmd.index & 0xFF, (cmd.index >> 8) & 0xFF]) + cmd.to_bytes(),
        )

        # SELECT
        select_start = time.time()
        apdu = self._application.build_request(AppLayerFunction.SELECT, [obj_header])
        response = self._send_request(apdu)

        if response is None or not self._check_control_response(response):
            return False

        # Check if we're still within the select timeout window
        elapsed = time.time() - select_start
        if elapsed >= self.config.select_timeout:
            self._logger.error(
                f"SELECT timeout exceeded: {elapsed:.2f}s >= {self.config.select_timeout}s"
            )
            return False

        # OPERATE - must be sent before select timeout expires
        apdu = self._application.build_request(AppLayerFunction.OPERATE, [obj_header])
        response = self._send_request(apdu)

        if response is None:
            return False

        return self._check_control_response(response)

    def _direct_operate_aob(self, cmd: AnalogOutputCommand) -> bool:
        """Direct operate an Analog Output Block."""
        obj_header = ObjectHeader(
            group=ObjectGroup.ANALOG_OUTPUT_BLOCK,
            variation=1,  # 32-bit integer
            qualifier=QualifierCode.UINT8_COUNT_UINT16_INDEX,
            count=1,
            data=bytes([cmd.index & 0xFF, (cmd.index >> 8) & 0xFF]) + cmd.to_bytes(1),
        )

        apdu = self._application.build_request(
            AppLayerFunction.DIRECT_OPERATE,
            [obj_header],
        )

        response = self._send_request(apdu)
        if response is None:
            return False

        return self._check_control_response(response)

    def _check_control_response(self, response: ApplicationResponse) -> bool:
        """Check if control response indicates success.

        Args:
            response: The application response to check

        Returns:
            True if all control operations succeeded, False otherwise
        """
        if response.iin.has_errors():
            self._logger.error(f"Control failed with IIN errors: {response.iin}")
            return False

        # Check for control status in response data
        # The response should echo back the control object with status
        for obj_header in response.objects:
            group = obj_header.group
            raw_data = response.raw_data
            qualifier = obj_header.qualifier

            # Determine index prefix size based on qualifier
            # Control responses typically use indexed qualifiers
            index_prefix_size = 0
            if qualifier == QualifierCode.UINT8_COUNT_UINT8_INDEX:
                index_prefix_size = 1
            elif qualifier in (QualifierCode.UINT8_COUNT_UINT16_INDEX,
                             QualifierCode.UINT16_COUNT_UINT16_INDEX):
                index_prefix_size = 2

            # CROB response (Group 12)
            if group == ObjectGroup.CONTROL_RELAY_OUTPUT_BLOCK:
                data_offset = obj_header.data_offset
                obj_size = get_object_size(group, obj_header.variation)

                if obj_size is None or obj_size < 11:
                    self._logger.warning(
                        f"Skipping CROB response with unexpected size: "
                        f"variation={obj_header.variation}, size={obj_size}"
                    )
                    continue

                # Total size per object includes index prefix (if present) + object data
                total_obj_size = index_prefix_size + obj_size

                for i in range(obj_header.count):
                    offset = data_offset + i * total_obj_size

                    # Skip past index prefix to get to actual CROB data
                    crob_data_offset = offset + index_prefix_size

                    if crob_data_offset + obj_size > len(raw_data):
                        self._logger.warning(
                            f"CROB data extends beyond response buffer at index {i}"
                        )
                        break

                    # Status byte is the last byte of CROB (11 bytes total)
                    status = raw_data[crob_data_offset + 10]
                    if status != ControlStatus.SUCCESS:
                        status_name = "UNKNOWN"
                        try:
                            status_name = ControlStatus(status).name
                        except ValueError:
                            pass
                        self._logger.error(
                            f"Control operation failed at index {i} with status: "
                            f"{status} ({status_name})"
                        )
                        return False

            # Analog Output Block response (Group 41)
            elif group == ObjectGroup.ANALOG_OUTPUT_BLOCK:
                data_offset = obj_header.data_offset
                obj_size = get_object_size(group, obj_header.variation)

                if obj_size is None:
                    self._logger.warning(
                        f"Skipping AOB response with unknown size: "
                        f"variation={obj_header.variation}"
                    )
                    continue

                # Total size per object includes index prefix (if present) + object data
                total_obj_size = index_prefix_size + obj_size

                for i in range(obj_header.count):
                    offset = data_offset + i * total_obj_size

                    # Skip past index prefix to get to actual AOB data
                    aob_data_offset = offset + index_prefix_size

                    if aob_data_offset + obj_size > len(raw_data):
                        self._logger.warning(
                            f"AOB data extends beyond response buffer at index {i}"
                        )
                        break

                    # Status byte is at the end of AOB
                    status = raw_data[aob_data_offset + obj_size - 1]
                    if status != ControlStatus.SUCCESS:
                        status_name = "UNKNOWN"
                        try:
                            status_name = ControlStatus(status).name
                        except ValueError:
                            pass
                        self._logger.error(
                            f"Analog control operation failed at index {i} with status: "
                            f"{status} ({status_name})"
                        )
                        return False

        return True

    # =========================================================================
    # Response parsing helpers
    # =========================================================================

    def _parse_poll_response(self, response: ApplicationResponse) -> PollResult:
        """Parse a poll response into a PollResult."""
        result = PollResult(
            success=True,
            iin=response.iin,
            raw_response=response.raw_data,
        )

        raw_data = response.raw_data

        for obj_header in response.objects:
            group = obj_header.group
            variation = obj_header.variation
            count = obj_header.count

            if count == 0:
                continue

            # Use the data_offset from the header
            data_offset = obj_header.data_offset

            # Indexed qualifiers include per-point indices in the data
            if obj_header.qualifier in (
                QualifierCode.UINT8_COUNT_UINT8_INDEX,
                QualifierCode.UINT8_COUNT_UINT16_INDEX,
                QualifierCode.UINT16_COUNT_UINT16_INDEX,
            ):
                index_size = 1 if obj_header.qualifier == QualifierCode.UINT8_COUNT_UINT8_INDEX else 2
                obj_size = get_object_size(group, variation)
                if obj_size is None:
                    self._logger.warning(
                        f"Skipping indexed object with unknown size: group={group}, variation={variation}"
                    )
                    continue

                for i in range(count):
                    offset = data_offset + i * (index_size + obj_size)
                    end = offset + index_size + obj_size
                    if end > len(raw_data):
                        self._logger.warning(
                            f"Indexed object exceeds response data: offset={offset}, "
                            f"size={index_size + obj_size}, raw_data_len={len(raw_data)}"
                        )
                        break

                    index = int.from_bytes(raw_data[offset:offset + index_size], "little")
                    obj_data = raw_data[offset + index_size:end]

                    if group == ObjectGroup.BINARY_INPUT:
                        result.binary_inputs.append(BinaryInput.from_bytes(obj_data, index, variation))
                    elif group == ObjectGroup.BINARY_OUTPUT:
                        result.binary_outputs.append(BinaryOutput.from_bytes(obj_data, index, variation))
                    elif group == ObjectGroup.ANALOG_INPUT:
                        result.analog_inputs.append(AnalogInput.from_bytes(obj_data, index, variation))
                    elif group == ObjectGroup.ANALOG_OUTPUT:
                        result.analog_outputs.append(AnalogOutput.from_bytes(obj_data, index, variation))
                    elif group == ObjectGroup.COUNTER:
                        result.counters.append(Counter.from_bytes(obj_data, index, variation))
                    elif group == ObjectGroup.BINARY_INPUT_EVENT:
                        result.binary_inputs.append(BinaryInput.from_bytes(obj_data, index, variation))
                    elif group == ObjectGroup.BINARY_OUTPUT_EVENT:
                        result.binary_outputs.append(BinaryOutput.from_bytes(obj_data, index, variation))
                    elif group == ObjectGroup.ANALOG_INPUT_EVENT:
                        result.analog_inputs.append(AnalogInput.from_bytes(obj_data, index, variation))
                    elif group == ObjectGroup.COUNTER_EVENT:
                        result.counters.append(Counter.from_bytes(obj_data, index, variation))

                continue

            # Calculate data size based on group/variation
            obj_size = get_object_size(group, variation)
            if obj_size is not None:
                data_size = obj_size * count
            elif group in (ObjectGroup.BINARY_INPUT, ObjectGroup.BINARY_OUTPUT) and variation == 1:
                # Packed binary: 1 bit per point
                data_size = (count + 7) // 8
            else:
                # Unknown size - skip
                self._logger.warning(
                    f"Skipping unknown object size: group={group}, variation={variation}"
                )
                continue

            if data_offset + data_size > len(raw_data):
                self._logger.warning(
                    f"Object data extends beyond response: offset={data_offset}, "
                    f"size={data_size}, raw_data_len={len(raw_data)}"
                )
                continue

            obj_data = raw_data[data_offset:data_offset + data_size]

            if group == ObjectGroup.BINARY_INPUT:
                result.binary_inputs.extend(
                    parse_binary_inputs(obj_data, obj_header.range_start, count, variation)
                )
            elif group == ObjectGroup.BINARY_OUTPUT:
                result.binary_outputs.extend(
                    parse_binary_outputs(obj_data, obj_header.range_start, count, variation)
                )
            elif group == ObjectGroup.ANALOG_INPUT:
                result.analog_inputs.extend(
                    parse_analog_inputs(obj_data, obj_header.range_start, count, variation)
                )
            elif group == ObjectGroup.ANALOG_OUTPUT:
                result.analog_outputs.extend(
                    parse_analog_outputs(obj_data, obj_header.range_start, count, variation)
                )
            elif group == ObjectGroup.COUNTER:
                result.counters.extend(
                    parse_counters(obj_data, obj_header.range_start, count, variation)
                )
            # Handle event groups (map to their static counterparts)
            elif group == ObjectGroup.BINARY_INPUT_EVENT:
                result.binary_inputs.extend(
                    parse_binary_inputs(obj_data, obj_header.range_start, count, variation)
                )
            elif group == ObjectGroup.BINARY_OUTPUT_EVENT:
                result.binary_outputs.extend(
                    parse_binary_outputs(obj_data, obj_header.range_start, count, variation)
                )
            elif group == ObjectGroup.ANALOG_INPUT_EVENT:
                result.analog_inputs.extend(
                    parse_analog_inputs(obj_data, obj_header.range_start, count, variation)
                )
            elif group == ObjectGroup.COUNTER_EVENT:
                result.counters.extend(
                    parse_counters(obj_data, obj_header.range_start, count, variation)
                )

        return result

    def _parse_binary_inputs(self, response: ApplicationResponse) -> List[BinaryInput]:
        """Parse binary inputs from response."""
        result = self._parse_poll_response(response)
        return result.binary_inputs

    def _parse_analog_inputs(self, response: ApplicationResponse) -> List[AnalogInput]:
        """Parse analog inputs from response."""
        result = self._parse_poll_response(response)
        return result.analog_inputs

    def _parse_counters(self, response: ApplicationResponse) -> List[Counter]:
        """Parse counters from response."""
        result = self._parse_poll_response(response)
        return result.counters

    def _parse_binary_outputs(self, response: ApplicationResponse) -> List[BinaryOutput]:
        """Parse binary outputs from response."""
        result = self._parse_poll_response(response)
        return result.binary_outputs

    def _parse_analog_outputs(self, response: ApplicationResponse) -> List[AnalogOutput]:
        """Parse analog outputs from response."""
        result = self._parse_poll_response(response)
        return result.analog_outputs

    # =========================================================================
    # Utility methods
    # =========================================================================

    def cold_restart(self) -> bool:
        """
        Request a cold restart of the outstation.

        Returns:
            True if successful
        """
        apdu = self._application.build_request(AppLayerFunction.COLD_RESTART)
        try:
            response = self._send_request(apdu, timeout=30.0)
            return response is not None
        except DNP3Error:
            return False

    def warm_restart(self) -> bool:
        """
        Request a warm restart of the outstation.

        Returns:
            True if successful
        """
        apdu = self._application.build_request(AppLayerFunction.WARM_RESTART)
        try:
            response = self._send_request(apdu, timeout=30.0)
            return response is not None
        except DNP3Error:
            return False

    def enable_unsolicited(self, class_mask: int = 0x07) -> bool:
        """
        Enable unsolicited responses for specified classes.

        Args:
            class_mask: Bit mask for classes (1=Class1, 2=Class2, 4=Class3)

        Returns:
            True if successful
        """
        objects = []
        if class_mask & 0x01:
            objects.append(ObjectHeader(group=ObjectGroup.CLASS_OBJECTS, variation=ObjectVariation.CLASS_1, qualifier=QualifierCode.ALL_OBJECTS))
        if class_mask & 0x02:
            objects.append(ObjectHeader(group=ObjectGroup.CLASS_OBJECTS, variation=ObjectVariation.CLASS_2, qualifier=QualifierCode.ALL_OBJECTS))
        if class_mask & 0x04:
            objects.append(ObjectHeader(group=ObjectGroup.CLASS_OBJECTS, variation=ObjectVariation.CLASS_3, qualifier=QualifierCode.ALL_OBJECTS))

        apdu = self._application.build_request(AppLayerFunction.ENABLE_UNSOLICITED, objects)
        response = self._send_request(apdu)
        return response is not None and not response.iin.has_errors()

    def disable_unsolicited(self, class_mask: int = 0x07) -> bool:
        """
        Disable unsolicited responses for specified classes.

        Args:
            class_mask: Bit mask for classes

        Returns:
            True if successful
        """
        objects = []
        if class_mask & 0x01:
            objects.append(ObjectHeader(group=ObjectGroup.CLASS_OBJECTS, variation=ObjectVariation.CLASS_1, qualifier=QualifierCode.ALL_OBJECTS))
        if class_mask & 0x02:
            objects.append(ObjectHeader(group=ObjectGroup.CLASS_OBJECTS, variation=ObjectVariation.CLASS_2, qualifier=QualifierCode.ALL_OBJECTS))
        if class_mask & 0x04:
            objects.append(ObjectHeader(group=ObjectGroup.CLASS_OBJECTS, variation=ObjectVariation.CLASS_3, qualifier=QualifierCode.ALL_OBJECTS))

        apdu = self._application.build_request(AppLayerFunction.DISABLE_UNSOLICITED, objects)
        response = self._send_request(apdu)
        return response is not None and not response.iin.has_errors()

    def set_unsolicited_callback(
        self,
        callback: Optional[Callable[[ApplicationResponse], None]],
    ) -> None:
        """
        Set callback for unsolicited responses.

        Args:
            callback: Function to call when unsolicited response received
        """
        self._unsolicited_callback = callback

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"DNP3Master({self.config.host}:{self.config.port}, {status})"
