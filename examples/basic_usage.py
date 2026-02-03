#!/usr/bin/env python3
"""
Basic DNP3 driver usage examples.

This script demonstrates how to use the DNP3 driver to communicate
with a DNP3 outstation over TCP/IP.
"""

import sys
import time

# Add parent directory to path for imports
sys.path.insert(0, "../..")

from dnp3_driver import DNP3Master, DNP3Config
from dnp3_driver.utils.logging import setup_logging


def basic_read_example():
    """Basic example of reading data points."""
    # Set up logging
    setup_logging(level="INFO")

    # Configure connection to outstation
    config = DNP3Config(
        host="192.168.1.100",  # Replace with your outstation IP
        port=20000,           # Standard DNP3 port
        master_address=1,     # Master station address
        outstation_address=10,  # Outstation address
        response_timeout=5.0,
    )

    # Create master instance
    master = DNP3Master(config)

    try:
        # Connect to outstation
        master.open()
        print(f"Connected to {config.host}:{config.port}")

        # Perform integrity poll (read all data)
        print("\n--- Integrity Poll ---")
        result = master.integrity_poll()

        if result.success:
            print(f"IIN: {result.iin}")

            if result.binary_inputs:
                print(f"\nBinary Inputs ({len(result.binary_inputs)}):")
                for bi in result.binary_inputs:
                    print(f"  {bi}")

            if result.analog_inputs:
                print(f"\nAnalog Inputs ({len(result.analog_inputs)}):")
                for ai in result.analog_inputs:
                    print(f"  {ai}")

            if result.counters:
                print(f"\nCounters ({len(result.counters)}):")
                for ctr in result.counters:
                    print(f"  {ctr}")
        else:
            print(f"Poll failed: {result.error}")

        # Read specific binary inputs
        print("\n--- Read Binary Inputs 0-9 ---")
        inputs = master.read_binary_inputs(0, 9)
        for bi in inputs:
            print(f"  {bi}")

        # Read specific analog inputs
        print("\n--- Read Analog Inputs 0-4 ---")
        analogs = master.read_analog_inputs(0, 4)
        for ai in analogs:
            print(f"  {ai}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        master.close()
        print("\nDisconnected")


def control_example():
    """Example of controlling binary outputs."""
    setup_logging(level="INFO")

    config = DNP3Config(
        host="192.168.1.100",
        port=20000,
        master_address=1,
        outstation_address=10,
    )

    master = DNP3Master(config)

    try:
        master.open()

        # Direct operate - turn on output 0
        print("Direct operate: Turn ON output 0")
        success = master.direct_operate_binary(index=0, value=True)
        print(f"  Result: {'Success' if success else 'Failed'}")

        time.sleep(1)

        # Direct operate - turn off output 0
        print("Direct operate: Turn OFF output 0")
        success = master.direct_operate_binary(index=0, value=False)
        print(f"  Result: {'Success' if success else 'Failed'}")

        time.sleep(1)

        # Select-Before-Operate control
        print("Select-Before-Operate: Turn ON output 1")
        success = master.select_operate_binary(index=1, value=True)
        print(f"  Result: {'Success' if success else 'Failed'}")

        time.sleep(1)

        # Pulse output
        print("Pulse output 2: 500ms on, 500ms off, 3 pulses")
        success = master.pulse_binary(index=2, on_time=500, off_time=500, count=3)
        print(f"  Result: {'Success' if success else 'Failed'}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        master.close()


def analog_control_example():
    """Example of controlling analog outputs."""
    setup_logging(level="INFO")

    config = DNP3Config(
        host="192.168.1.100",
        port=20000,
        master_address=1,
        outstation_address=10,
    )

    master = DNP3Master(config)

    try:
        master.open()

        # Set analog output to a specific value
        print("Set analog output 0 to 50.0")
        success = master.direct_operate_analog(index=0, value=50.0)
        print(f"  Result: {'Success' if success else 'Failed'}")

        # Read back the value
        outputs = master.read_analog_outputs(0, 0)
        if outputs:
            print(f"  Current value: {outputs[0].value}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        master.close()


def context_manager_example():
    """Example using context manager for automatic connection handling."""
    setup_logging(level="INFO")

    config = DNP3Config(
        host="192.168.1.100",
        port=20000,
    )

    master = DNP3Master(config)

    # Using context manager ensures connection is properly closed
    with master.connect():
        result = master.integrity_poll()
        if result.success:
            print(f"Found {len(result.binary_inputs)} binary inputs")
            print(f"Found {len(result.analog_inputs)} analog inputs")
            print(f"Found {len(result.counters)} counters")


def polling_loop_example():
    """Example of continuous polling."""
    setup_logging(level="INFO")

    config = DNP3Config(
        host="192.168.1.100",
        port=20000,
    )

    master = DNP3Master(config)

    try:
        master.open()

        # Initial integrity poll
        print("Initial integrity poll...")
        master.integrity_poll()

        # Continuous class polling
        print("\nStarting continuous polling (Ctrl+C to stop)...")
        while True:
            # Poll Class 1 (high priority events)
            result = master.read_class(1)
            if result.success and (result.binary_inputs or result.analog_inputs):
                print(f"Class 1 events: {len(result.binary_inputs)} BI, {len(result.analog_inputs)} AI")

            # Poll Class 2 (medium priority events)
            result = master.read_class(2)
            if result.success and (result.binary_inputs or result.analog_inputs):
                print(f"Class 2 events: {len(result.binary_inputs)} BI, {len(result.analog_inputs)} AI")

            time.sleep(1)  # Poll interval

    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        master.close()


if __name__ == "__main__":
    print("DNP3 Driver Usage Examples")
    print("=" * 50)
    print("1. Basic read example")
    print("2. Binary control example")
    print("3. Analog control example")
    print("4. Context manager example")
    print("5. Polling loop example")
    print()

    choice = input("Select example (1-5): ").strip()

    if choice == "1":
        basic_read_example()
    elif choice == "2":
        control_example()
    elif choice == "3":
        analog_control_example()
    elif choice == "4":
        context_manager_example()
    elif choice == "5":
        polling_loop_example()
    else:
        print("Invalid choice")
