"""
Logging setup for codepulse.

Provides a pre-configured logger using Rich for
colourful terminal output.
"""

from __future__ import annotations

import logging

from rich.logging import RichHandler


def get_logger(name: str = "codepulse") -> logging.Logger:
    """Return a logger with Rich handler attached."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = RichHandler(
            rich_tracebacks=True,
            show_path=False,
            markup=True,
        )
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
