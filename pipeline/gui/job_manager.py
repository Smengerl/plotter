"""Single-worker job manager for the Plotter Pipeline GUI.

Enforces that only one pipeline job runs at a time (via an asyncio Lock),
dispatches the blocking ``runner.run()`` call to a thread executor, routes
log records and progress updates to a shared ``asyncio.Queue``, and
maintains an in-memory record of the current (or last completed) job.

No FastAPI or HTTP concerns belong here.

Typical startup sequence::

    import asyncio
    from pipeline.gui import job_manager

    async def lifespan(app):
        job_manager.init(asyncio.get_running_loop())
        yield

Usage from a router::

    await job_manager.run_job(
        image_name="photo.jpg",
        pipeline_path=Path("pipeline/configs/default.yaml"),
        input_path=Path("input/photo.jpg"),
        output_path=Path("output/photo__default.jpg"),
    )
"""

from __future__ import annotations

import asyncio
import copy
import logging
import threading
from pathlib import Path
from typing import Any

from pipeline.core.base import ImageContext
from pipeline.core.runner import PipelineRunner
from pipeline.gui.log_handler import attach_to_pipeline_logger, detach
import pipeline.gui.filesystem as filesystem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_lock: asyncio.Lock | None = None
_cancel_event: threading.Event = threading.Event()
_current_job: dict[str, Any] | None = None
_log_queue: asyncio.Queue[dict[str, Any]] | None = None
_loop: asyncio.AbstractEventLoop | None = None


def init(loop: asyncio.AbstractEventLoop) -> None:
    """Initialise module state.  Must be called once inside the running event loop.

    Args:
        loop: The event loop that will own the asyncio primitives.
    """
    global _lock, _log_queue, _loop  # noqa: PLW0603
    _loop = loop
    _lock = asyncio.Lock()
    _log_queue = asyncio.Queue()
    logger.debug("job_manager initialised")


# ---------------------------------------------------------------------------
# Public query helpers
# ---------------------------------------------------------------------------


def get_current_job() -> dict[str, Any] | None:
    """Return a shallow copy of the current job state, or ``None``.

    Returns:
        Copy of the job dict, or None if no job has been started yet.
    """
    if _current_job is None:
        return None
    return copy.copy(_current_job)


def get_log_queue() -> asyncio.Queue[dict[str, Any]]:
    """Return the shared log/event queue used by the SSE endpoint.

    Raises:
        RuntimeError: If :func:`init` has not been called yet.

    Returns:
        The shared asyncio queue.
    """
    if _log_queue is None:
        raise RuntimeError("job_manager.init() must be called before get_log_queue()")
    return _log_queue


def request_cancel() -> bool:
    """Request cancellation of the currently running job.

    Sets the cancel event that the pipeline runner checks between steps.

    Returns:
        True if a job was running when cancel was requested, False otherwise.
    """
    if _current_job is not None and _current_job.get("status") == "running":
        _cancel_event.set()
        logger.info("Cancellation requested for job '%s'", _current_job.get("image_name"))
        return True
    return False


# ---------------------------------------------------------------------------
# Progress callback (runs in worker thread)
# ---------------------------------------------------------------------------


def _on_progress(step_index: int, total_steps: int, label: str) -> None:
    """Update the current job state and push a progress event to the queue.

    Called by ``PipelineRunner`` after each step, from the worker thread.

    Args:
        step_index: 1-based index of the completed step.
        total_steps: Total number of steps in the pipeline.
        label: Display label of the completed step.
    """
    global _current_job  # noqa: PLW0603

    if _current_job is not None:
        _current_job["step_current"] = step_index
        _current_job["step_total"] = total_steps
        _current_job["step_label"] = label

    if _loop is not None and _log_queue is not None:
        item: dict[str, Any] = {
            "type": "progress",
            "step": step_index,
            "total": total_steps,
            "label": label,
        }
        _loop.call_soon_threadsafe(_log_queue.put_nowait, item)


# ---------------------------------------------------------------------------
# Main job runner
# ---------------------------------------------------------------------------


async def run_job(
    image_name: str,
    pipeline_path: Path,
    input_path: Path,
    output_path: Path,
) -> None:
    """Run a pipeline job asynchronously (non-blocking for the event loop).

    Acquires the single-worker lock, runs the pipeline in a thread executor,
    and updates the job state on completion or error.

    Args:
        image_name: Display name of the input image (filename).
        pipeline_path: Path to the YAML pipeline config file.
        input_path: Path to the input image file.
        output_path: Desired path for the output image.

    Raises:
        RuntimeError: If a job is already running (lock is held).
    """
    global _current_job  # noqa: PLW0603

    if _lock is None or _loop is None or _log_queue is None:
        raise RuntimeError("job_manager.init() must be called before run_job()")

    if _lock.locked():
        raise RuntimeError(
            f"A job is already running for '{_current_job and _current_job.get('image_name')}'"
        )

    async with _lock:
        # ---- setup --------------------------------------------------------
        _cancel_event.clear()

        pipeline_stem = pipeline_path.stem

        _current_job = {
            "image_name": image_name,
            "pipeline_stem": pipeline_stem,
            "pipeline_name": pipeline_stem,       # updated below after from_yaml
            "pipeline_description": None,
            "status": "running",
            "error_reason": None,
            "step_current": 0,
            "step_total": 0,
            "step_label": "",
        }

        log_handler = None
        exc_caught: Exception | None = None

        try:
            # Build runner — may raise FileNotFoundError / ValueError / KeyError
            runner = PipelineRunner.from_yaml(pipeline_path, on_progress=_on_progress)
            _current_job["pipeline_name"] = runner.name
            _current_job["pipeline_description"] = runner.description

            # Attach log handler so pipeline log records flow into _log_queue
            log_handler = attach_to_pipeline_logger(_log_queue, _loop)

            # Build context
            ctx = ImageContext()
            ctx.metadata["source_path"] = input_path
            ctx.metadata["output_path"] = output_path

            logger.info(
                "Starting job: image='%s' pipeline='%s'",
                image_name,
                runner.name,
            )

            # Run blocking inference in executor (keeps event loop free)
            await _loop.run_in_executor(None, runner.run, ctx)

        except Exception as exc:  # noqa: BLE001
            exc_caught = exc
            logger.error("Job failed: %s", exc)

        finally:
            # Always detach log handler
            if log_handler is not None:
                detach(log_handler)

        # ---- post-run -------------------------------------------------------
        if _cancel_event.is_set() or exc_caught is not None:
            # Clean up any partial output
            if output_path.exists():
                try:
                    output_path.unlink()
                    logger.debug("Deleted partial output: %s", output_path)
                except OSError as e:
                    logger.warning("Could not delete partial output %s: %s", output_path, e)

            if _cancel_event.is_set():
                reason = "Cancelled by user"
            else:
                reason = str(exc_caught)

            _current_job["status"] = "error"
            _current_job["error_reason"] = reason
            logger.info("Job ended with error: %s", reason)
        else:
            _current_job["status"] = "done"
            logger.info(
                "Job done: image='%s' pipeline='%s'",
                image_name,
                pipeline_stem,
            )

        # Emit a refresh notification so the frontend updates its state
        filesystem.invalidate("output_images")
        filesystem.invalidate("input_images")
        _emit_refresh()


def _emit_refresh() -> None:
    """Push a refresh notification into the log queue (thread-safe).

    Called at job completion so SSE clients know to re-fetch job state.
    """
    if _loop is not None and _log_queue is not None:
        _loop.call_soon_threadsafe(_log_queue.put_nowait, {"type": "refresh"})
