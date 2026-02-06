#!/usr/bin/env python3
"""Quick test of dnp3py with specified connection parameters."""

from dnp3py import DNP3Master, DNP3Config
from dnp3py.utils.logging import setup_logging

def main():
    setup_logging(level="INFO")

    config = DNP3Config(
        host="10.248.111.2",
        port=4001,
        master_address=1,
        outstation_address=10004,
        response_timeout=5.0,
    )

    master = DNP3Master(config)

    try:
        print(f"Connecting to {config.host}:{config.port} (master=1, outstation=10004)...")
        master.open()
        print("Connected.\n--- Integrity Poll ---")

        result = master.integrity_poll()

        if result.success:
            print(f"IIN: {result.iin}")
            if result.binary_inputs:
                print(f"Binary Inputs ({len(result.binary_inputs)}):")
                for bi in result.binary_inputs[:10]:
                    print(f"  {bi}")
                if len(result.binary_inputs) > 10:
                    print(f"  ... and {len(result.binary_inputs) - 10} more")
            if result.analog_inputs:
                print(f"Analog Inputs ({len(result.analog_inputs)}):")
                for ai in result.analog_inputs[:10]:
                    print(f"  {ai}")
                if len(result.analog_inputs) > 10:
                    print(f"  ... and {len(result.analog_inputs) - 10} more")
            if result.counters:
                print(f"Counters ({len(result.counters)}):")
                for c in result.counters[:10]:
                    print(f"  {c}")
                if len(result.counters) > 10:
                    print(f"  ... and {len(result.counters) - 10} more")
            if not (result.binary_inputs or result.analog_inputs or result.counters):
                print("(No points returned)")
        else:
            print(f"Poll failed: {result.error}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        master.close()
        print("\nDisconnected.")

if __name__ == "__main__":
    main()
