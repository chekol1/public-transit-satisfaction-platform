"""Structured JSON logging setup.

The original project used `print()` with raw ANSI color codes for status
messages, which doesn't work with any log aggregator (e.g. ELK). This
configures the stdlib `logging` module to emit JSON lines instead, so it
can be shipped to ELK/CloudWatch/whatever the platform team uses.
"""

from __future__ import annotations

import logging

from pythonjsonlogger import jsonlogger

from transit_satisfaction.config import settings


def configure_logging() -> None:
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(settings.log_level)
