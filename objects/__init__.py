"""
DNP3 data object implementations.

This package provides:
- Data types: BinaryInput, BinaryOutput, BinaryOutputCommand; AnalogInput, AnalogOutput,
  AnalogOutputCommand; Counter.
- Group/variation enums and helpers: ObjectGroup, ObjectVariation, get_object_size,
  get_group_name.

For parsing response data, use the submodules directly:
- dnp3py.objects.binary: parse_binary_inputs, parse_binary_outputs
- dnp3py.objects.analog: parse_analog_inputs, parse_analog_outputs
- dnp3py.objects.counter: parse_counters
"""

from dnp3py.objects.analog import AnalogInput, AnalogOutput, AnalogOutputCommand
from dnp3py.objects.binary import BinaryInput, BinaryOutput, BinaryOutputCommand
from dnp3py.objects.counter import Counter
from dnp3py.objects.groups import (
    ObjectGroup,
    ObjectVariation,
    get_group_name,
    get_object_size,
)

__all__ = [
    "AnalogInput",
    "AnalogOutput",
    "AnalogOutputCommand",
    "BinaryInput",
    "BinaryOutput",
    "BinaryOutputCommand",
    "Counter",
    "ObjectGroup",
    "ObjectVariation",
    "get_object_size",
    "get_group_name",
]
