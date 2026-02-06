"""
DNP3 utility modules.

This package provides:
- CRC: CRC16DNP3 and calculate_frame_crc (DNP3 CRC-16, used by Data Link).
- Logging: setup_logging, get_logger, log_frame, log_parsed_frame.
"""

from dnp3py.utils.crc import CRC16DNP3, calculate_frame_crc
from dnp3py.utils.logging import (
    get_logger,
    log_frame,
    log_parsed_frame,
    setup_logging,
)

__all__ = [
    "CRC16DNP3",
    "calculate_frame_crc",
    "get_logger",
    "log_frame",
    "log_parsed_frame",
    "setup_logging",
]
