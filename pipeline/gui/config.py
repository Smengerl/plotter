"""
pipeline/gui/config.py - ServerConfig dataclass

Holds all runtime configuration for the GUI server.
All fields have defaults matching the CLI argument defaults in server.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ServerConfig:
    """Runtime configuration for the Plotter Pipeline Manager GUI server.

    Attributes:
        input_dir: Folder scanned for source images.
        tools_dir: Folder scanned for pipeline YAML configs.
        output_dir: Folder where output artifacts are written.
        host: Uvicorn bind address.
        port: Uvicorn port.
        log_level: Uvicorn log level string.
        plotter_pipeline_stem: Stem of the dedicated plotter pipeline YAML.
    """

    input_dir: Path = field(default_factory=lambda: Path("input"))
    tools_dir: Path = field(default_factory=lambda: Path("configs"))
    output_dir: Path = field(default_factory=lambda: Path("output"))
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"
    plotter_pipeline_stem: str = "plotter"
