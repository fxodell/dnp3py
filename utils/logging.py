"""DNP3 driver logging utilities."""

import logging
import sys
from typing import Optional


# Module-level logger
_logger: Optional[logging.Logger] = None


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: Optional[str] = None,
) -> logging.Logger:
    """
    Set up logging for the DNP3 driver.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
        log_format: Optional custom log format string

    Returns:
        Configured logger instance
    """
    global _logger

    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Create logger
    logger = logging.getLogger("pydnp3")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers
    logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(file_handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """
    Get the DNP3 driver logger.

    Returns:
        Logger instance (creates default if not initialized)
    """
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger


def log_frame(frame: bytes, direction: str = "TX", logger: Optional[logging.Logger] = None) -> None:
    """
    Log a DNP3 frame in hex format.

    Args:
        frame: Frame bytes to log
        direction: "TX" for transmitted, "RX" for received
        logger: Optional logger instance (uses default if not provided)
    """
    if logger is None:
        logger = get_logger()

    hex_str = " ".join(f"{b:02X}" for b in frame)
    logger.debug(f"{direction}: [{len(frame)} bytes] {hex_str}")


def log_parsed_frame(
    frame_info: dict,
    direction: str = "TX",
    logger: Optional[logging.Logger] = None,
) -> None:
    """
    Log parsed frame information.

    Args:
        frame_info: Dictionary with parsed frame details
        direction: "TX" for transmitted, "RX" for received
        logger: Optional logger instance
    """
    if logger is None:
        logger = get_logger()

    parts = [f"{direction} Frame:"]

    if "source" in frame_info:
        parts.append(f"src={frame_info['source']}")
    if "destination" in frame_info:
        parts.append(f"dst={frame_info['destination']}")
    if "function" in frame_info:
        parts.append(f"func=0x{frame_info['function']:02X}")
    if "sequence" in frame_info:
        parts.append(f"seq={frame_info['sequence']}")
    if "length" in frame_info:
        parts.append(f"len={frame_info['length']}")

    logger.debug(" ".join(parts))
