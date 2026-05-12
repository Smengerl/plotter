"""FastAPI application factory and CLI entry point for the Plotter Pipeline GUI server."""

from __future__ import annotations

import argparse
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import pipeline.gui.filesystem as filesystem
import pipeline.gui.job_manager as job_manager
from pipeline.gui.config import ServerConfig
from pipeline.gui.routers import events, images, jobs, output_images, pipelines, plotter

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(cfg: ServerConfig) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        cfg: Server configuration (directories, host, port, etc.).

    Returns:
        Configured FastAPI application instance.
    """
    for attr, label in [
        ("input_dir", "input"),
        ("tools_dir", "tools"),
        ("output_dir", "output"),
    ]:
        directory: Path = getattr(cfg, attr)
        if not directory.exists():
            logger.warning("Directory '%s' (%s) does not exist — creating it.", label, directory)
            directory.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        """Initialise cache and job manager on startup; wait for worker on shutdown."""
        loop = asyncio.get_event_loop()
        filesystem.init_cache(cfg)
        job_manager.init(loop)
        logger.info("Plotter GUI server started (input=%s, tools=%s, output=%s)",
                    cfg.input_dir, cfg.tools_dir, cfg.output_dir)
        yield
        # Shutdown: give any running worker up to 10 s to finish
        logger.info("Shutting down — waiting up to 10 s for worker thread …")
        deadline = 10.0
        step = 0.1
        elapsed = 0.0
        while job_manager.get_current_job() is not None and elapsed < deadline:
            await asyncio.sleep(step)
            elapsed += step
        if elapsed >= deadline:
            logger.warning("Worker did not finish within 10 s — forcing shutdown.")

    app = FastAPI(title="Plotter Pipeline Manager", version="0.1.0", lifespan=lifespan)

    # Attach config so routers can access it via request.app.state.cfg
    app.state.cfg = cfg

    # Static files
    app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    # Routers
    app.include_router(pipelines.router, prefix="/api/pipelines", tags=["pipelines"])
    app.include_router(images.router, prefix="/api/input_images", tags=["input_images"])
    app.include_router(output_images.router, prefix="/api/output_images", tags=["output_images"])
    app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
    app.include_router(events.router, prefix="/api/events", tags=["events"])
    app.include_router(plotter.router, prefix="/api/plotter", tags=["plotter"])

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(_STATIC_DIR / "index.html")

    return app


def _parse_args() -> ServerConfig:
    """Parse CLI arguments and return a ServerConfig.

    Returns:
        ServerConfig populated from CLI arguments.
    """
    defaults = ServerConfig()

    parser = argparse.ArgumentParser(
        prog="server.py",
        description="Plotter Pipeline Manager — web GUI server",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=defaults.input_dir,
        help=f"Directory for input images (default: {defaults.input_dir})",
    )
    parser.add_argument(
        "--tools-dir",
        type=Path,
        default=defaults.tools_dir,
        help=f"Directory for pipeline YAML configs (default: {defaults.tools_dir})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=defaults.output_dir,
        help=f"Directory for output images (default: {defaults.output_dir})",
    )
    parser.add_argument(
        "--host",
        default=defaults.host,
        help=f"Bind host (default: {defaults.host})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=defaults.port,
        help=f"Bind port (default: {defaults.port})",
    )
    parser.add_argument(
        "--log-level",
        default=defaults.log_level,
        choices=["debug", "info", "warning", "error", "critical"],
        help=f"Log level (default: {defaults.log_level})",
    )

    args = parser.parse_args()
    return ServerConfig(
        input_dir=args.input_dir,
        tools_dir=args.tools_dir,
        output_dir=args.output_dir,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )


def main() -> None:
    """Entry point for the ``pipeline-server`` CLI command.

    Starts the FastAPI web server for the pipeline GUI.
    Installed by pip as ``.venv/bin/pipeline-server`` via ``[project.scripts]``.
    """
    cfg = _parse_args()
    app = create_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level=cfg.log_level)


if __name__ == "__main__":
    main()
