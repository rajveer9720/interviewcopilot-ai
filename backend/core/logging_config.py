"""
Central logging configuration, built on `structlog` (already a dependency,
previously never wired up).

`configure_logging()` is called once at app startup (see main.py). It
installs a `structlog`-driven formatter as the *root* stdlib logging
handler, so every existing `logging.getLogger(__name__)` call site in the
codebase immediately gets consistent, leveled, timestamped output — without
needing to migrate all of them at once. New code should call `get_logger`
instead; existing call sites are migrated file-by-file as each refactor
phase touches that file.
"""

import logging
import sys

import structlog

from backend.config import settings

_SHARED_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


def configure_logging() -> None:
    renderer = (
        structlog.dev.ConsoleRenderer()
        if settings.ENV == "development"
        else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[
            *_SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.LOG_LEVEL)

    # Some libraries (SQLAlchemy's `echo=True` in particular — see
    # core/database.py) attach their own handler directly to a named logger
    # at *import time*, which runs before this function does. Left alone,
    # that produces every line twice: once from the library's own handler,
    # once more from ours via propagation. Strip any handlers a library
    # already installed so this root handler is the single source of truth.
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
