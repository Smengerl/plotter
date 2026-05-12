"""SSE endpoint — streams refresh, log, and progress events to the frontend.

A single ``GET /api/events`` endpoint multiplexes all server-push events over
one persistent connection.  Each item drained from the shared
``job_manager.get_log_queue()`` is dispatched by its ``"type"`` field:

* ``refresh``  — frontend should re-fetch jobs and image lists
* ``log``      — a pipeline log record ``{level, msg}``
* ``progress`` — a step-progress update ``{step, total, label}``

A keepalive SSE comment (``": keepalive"``) is sent after 15 s of inactivity
so proxies and browsers do not close the connection.

If the client disconnects the generator exits cleanly without raising.

Endpoints:
  GET /api/events
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from pipeline.gui import job_manager

logger = logging.getLogger(__name__)

router = APIRouter()

_KEEPALIVE_TIMEOUT = 15.0  # seconds


async def _event_generator() -> AsyncGenerator[str, None]:
    """Yield SSE-formatted strings until the client disconnects.

    Yields:
        SSE-formatted strings (``event: …\\ndata: …\\n\\n`` or keepalive comments).
    """
    queue = job_manager.get_log_queue()

    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=_KEEPALIVE_TIMEOUT)
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"
            continue
        except GeneratorExit:
            logger.debug("SSE client disconnected (GeneratorExit)")
            return

        event_type = item.get("type", "unknown")

        if event_type == "refresh":
            data = json.dumps({"type": "refresh"})
            yield f"event: refresh\ndata: {data}\n\n"

        elif event_type == "log":
            data = json.dumps({"level": item.get("level"), "msg": item.get("msg")})
            yield f"event: log\ndata: {data}\n\n"

        elif event_type == "progress":
            data = json.dumps({
                "step": item.get("step"),
                "total": item.get("total"),
                "label": item.get("label"),
            })
            yield f"event: progress\ndata: {data}\n\n"

        else:
            logger.warning("SSE: unknown queue item type '%s' — skipped", event_type)


@router.get("")
async def stream_events() -> StreamingResponse:
    """Stream all pipeline events as Server-Sent Events.

    Returns:
        A streaming ``text/event-stream`` response.
    """
    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
from fastapi import APIRouter

router = APIRouter()
