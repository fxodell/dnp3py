#!/usr/bin/env python3
"""
Async DNP3 driver example using threading.

This demonstrates how to use the DNP3 driver with background polling
and event handling.
"""

import sys
import time
import threading
from queue import Queue
from typing import Optional

sys.path.insert(0, "../..")

from pydnp3 import DNP3Master, DNP3Config
from pydnp3.core.config import IINFlags
from pydnp3.utils.logging import setup_logging


class DNP3PollingClient:
    """
    DNP3 client with background polling capability.

    This class wraps the DNP3Master and provides:
    - Background polling thread
    - Event queue for data changes
    - Thread-safe data access
    """

    def __init__(self, config: DNP3Config):
        self.config = config
        self.master = DNP3Master(config)

        # Polling configuration
        self.integrity_interval = 60.0  # seconds
        self.event_poll_interval = 1.0  # seconds

        # State
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._data_lock = threading.Lock()

        # Current data cache
        self._binary_inputs = {}
        self._analog_inputs = {}
        self._counters = {}
        self._last_iin: Optional[IINFlags] = None

        # Event queue for data changes
        self.event_queue: Queue = Queue()

    def start(self) -> None:
        """Start the polling client."""
        self.master.open()
        self._running = True

        # Start background polling thread
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def stop(self) -> None:
        """Stop the polling client."""
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=5.0)
        self.master.close()

    def _poll_loop(self) -> None:
        """Background polling loop."""
        last_integrity = 0.0

        while self._running:
            try:
                current_time = time.time()

                # Integrity poll at configured interval
                if current_time - last_integrity >= self.integrity_interval:
                    self._do_integrity_poll()
                    last_integrity = current_time
                else:
                    # Event poll for classes 1, 2, 3
                    self._do_event_poll()

                time.sleep(self.event_poll_interval)

            except Exception as e:
                print(f"Polling error: {e}")
                time.sleep(5.0)  # Back off on error

    def _do_integrity_poll(self) -> None:
        """Perform integrity poll and update cache."""
        result = self.master.integrity_poll()

        if result.success:
            with self._data_lock:
                self._last_iin = result.iin

                # Update binary inputs
                for bi in result.binary_inputs:
                    old_value = self._binary_inputs.get(bi.index)
                    if old_value is None or old_value.value != bi.value:
                        self.event_queue.put(("binary_input", bi))
                    self._binary_inputs[bi.index] = bi

                # Update analog inputs
                for ai in result.analog_inputs:
                    old_value = self._analog_inputs.get(ai.index)
                    if old_value is None or old_value.value != ai.value:
                        self.event_queue.put(("analog_input", ai))
                    self._analog_inputs[ai.index] = ai

                # Update counters
                for ctr in result.counters:
                    old_value = self._counters.get(ctr.index)
                    if old_value is None or old_value.value != ctr.value:
                        self.event_queue.put(("counter", ctr))
                    self._counters[ctr.index] = ctr

    def _do_event_poll(self) -> None:
        """Poll for event data (class 1, 2, 3)."""
        # Check IIN for pending events
        if self._last_iin:
            if self._last_iin.class_1_events:
                result = self.master.read_class(1)
                self._process_event_result(result)

            if self._last_iin.class_2_events:
                result = self.master.read_class(2)
                self._process_event_result(result)

            if self._last_iin.class_3_events:
                result = self.master.read_class(3)
                self._process_event_result(result)

    def _process_event_result(self, result) -> None:
        """Process event poll result."""
        if result.success:
            self._last_iin = result.iin

            for bi in result.binary_inputs:
                self.event_queue.put(("binary_input_event", bi))
                with self._data_lock:
                    self._binary_inputs[bi.index] = bi

            for ai in result.analog_inputs:
                self.event_queue.put(("analog_input_event", ai))
                with self._data_lock:
                    self._analog_inputs[ai.index] = ai

    def get_binary_input(self, index: int):
        """Get cached binary input value."""
        with self._data_lock:
            return self._binary_inputs.get(index)

    def get_analog_input(self, index: int):
        """Get cached analog input value."""
        with self._data_lock:
            return self._analog_inputs.get(index)

    def get_counter(self, index: int):
        """Get cached counter value."""
        with self._data_lock:
            return self._counters.get(index)

    def operate_binary(self, index: int, value: bool) -> bool:
        """Operate a binary output point."""
        return self.master.direct_operate_binary(index, value)

    def operate_analog(self, index: int, value: float) -> bool:
        """Operate an analog output point."""
        return self.master.direct_operate_analog(index, value)


def main():
    """Main example function."""
    setup_logging(level="INFO")

    config = DNP3Config(
        host="192.168.1.100",
        port=20000,
        master_address=1,
        outstation_address=10,
    )

    client = DNP3PollingClient(config)

    try:
        print("Starting DNP3 polling client...")
        client.start()

        # Process events from the queue
        print("Listening for events (Ctrl+C to stop)...")
        while True:
            try:
                event_type, data = client.event_queue.get(timeout=1.0)
                print(f"Event: {event_type} - {data}")
            except:
                pass  # Queue timeout, continue

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        client.stop()
        print("Stopped")


if __name__ == "__main__":
    main()
