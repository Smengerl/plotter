"""Log handler that routes pipeline log records into an asyncio.Queue.

The pipeline runner executes in a worker thread (via ``run_in_executor``).
Standard ``logging`` handlers are synchronous and thread-safe, but pushing
records into an asyncio queue from a non-event-loop thread requires
``loop.call_soon_threadsafe`` so the put is scheduled on the correct loop.

Typical usage::

    import asyncio
    from pipeline.gui.log_handler import attach_to_pipeline_logger, detach

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    handler = attach_to_pipeline_logger(queue, loop)
    try:
        # ... run pipeline in executor ...
    finally:
        detach(handler)

No FastAPI or HTTP concerns belong here.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

# Logger hierarchy that the handler is attached to.  Using "pipeline" covers
# all loggers named "pipeline.*" (steps, runner, etc.) without capturing
# unrelated application logs.
_PIPELINE_LOGGER_NAME = "pipeline"

logger = logging.getLogger(__name__)


class QueueLogHandler(logging.Handler):
    """A :class:`logging.Handler` that pushes formatted records to an asyncio queue.

    Because pipeline steps run in a worker thread the handler uses
    ``loop.call_soon_threadsafe`` to schedule each ``queue.put_nowait`` on the
    event loop, making the operation safe across thread boundaries.

    Args:
        queue: The asyncio queue to push log items into.
        loop: The running event loop that owns *queue*.
    """

    def __init__(self, queue: asyncio.Queue[dict[str, Any]], loop: asyncio.AbstractEventLoop) -> None:
        super().__init__()
        self._queue = queue
        self._loop = loop
        # Track the logger this handler was attached to so detach() can find it
        self._attached_logger: logging.Logger | None = None

    def emit(self, record: logging.LogRecord) -> None:
        """Format *record* and schedule a put on the asyncio queue.

        Args:
            record: The log record to emit.
        """
        try:
            item: dict[str, Any] = {
                "level": record.levelname,   # always an uppercase string
                "msg": self.format(record),
            }
            self._loop.call_soon_threadsafe(self._queue.put_nowait, item)
        except Exception:  # noqa: BLE001
            self.handleError(record)


def attach_to_pipeline_logger(
    queue: asyncio.Queue[dict[str, Any]],
    loop: asyncio.AbstractEventLoop,
) -> QueueLogHandler:
    """Create a :class:`QueueLogHandler` and attach it to the pipeline logger.

    The handler is attached to the ``"pipeline"`` logger, which captures all
    records from ``pipeline.*`` loggers (runner, steps, etc.).

    Args:
        queue: Destination asyncio queue for log items.
        loop: The event loop that owns *queue*.

    Returns:
        The newly created handler (keep a reference to pass to :func:`detach`).
    """
    handler = QueueLogHandler(queue, loop)
    pipeline_logger = logging.getLogger(_PIPELINE_LOGGER_NAME)
    pipeline_logger.addHandler(handler)
    handler._attached_logger = pipeline_logger
    logger.debug("QueueLogHandler attached to logger '%s'", _PIPELINE_LOGGER_NAME)
    return handler


def detach(handler: QueueLogHandler) -> None:
    """Remove *handler* from the logger it was attached to.

    Safe to call even if the handler was already removed.

    Args:
        handler: The handler returned by :func:`attach_to_pipeline_logger`.
    """
    target = handler._attached_logger
    if target is not None:
        target.removeHandler(handler)
        handler._attached_logger = None
        logger.debug("QueueLogHandler detached from logger '%s'", target.name)
