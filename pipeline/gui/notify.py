"""Thin notify helper for pushing cross-cutting events into the SSE queue.

All functions are thread-safe (use ``loop.call_soon_threadsafe``).
No FastAPI or HTTP concerns belong here.

Usage example::

    from pipeline.gui import notify

    # At job completion (worker thread or async context):
    notify.emit_refresh()
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def emit_refresh() -> None:
    """Push a ``{"type": "refresh"}`` item into the job_manager log queue.

    Thread-safe: uses ``loop.call_soon_threadsafe`` so it can be called
    from any thread or async context.

    Silently does nothing if the job_manager has not been initialised yet.
    """
    # Import here to avoid circular imports at module level
    from pipeline.gui import job_manager  # noqa: PLC0415

    loop = job_manager._loop
    queue = job_manager._log_queue

    if loop is None or queue is None:
        logger.debug("emit_refresh called before job_manager.init() — ignored")
        return

    loop.call_soon_threadsafe(queue.put_nowait, {"type": "refresh"})
    logger.debug("emit_refresh enqueued")
