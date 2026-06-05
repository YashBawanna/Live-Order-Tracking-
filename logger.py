"""
logger.py — Centralised logging configuration.
Every module imports get_logger() from here instead of using print().

Usage in any module:
    from logger import get_logger
    logger = get_logger(__name__)
    logger.info("Something happened")
    logger.warning("Something looks off")
    logger.error("Something went wrong")
"""

import logging
import sys

LOG_FORMAT  = "%(asctime)s  %(levelname)-8s  %(name)-25s  %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt=DATE_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)],
)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for a module."""
    return logging.getLogger(name)
