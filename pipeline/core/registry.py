"""
pipeline/core/registry.py - Central registry of all pipeline step classes

New steps are registered here - all other parts of the pipeline
(runner, CLI, tests) reference only the name as a string.

Usage
-----
Retrieve a step::

    cls = STEP_REGISTRY["stylise_canny"]
    step = cls(config={"style_res": 1024})

Add custom steps::

    from pipeline.core.registry import STEP_REGISTRY
    from pipeline.steps.my_step import MyStep

    STEP_REGISTRY["my_step"] = MyStep
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pipeline.core.base import PipelineStep

# Native Steps
from pipeline.steps.load_image_step import LoadImageStep
from pipeline.steps.save_image_step import SaveImageStep
from pipeline.steps.stylise_canny_step import StyliseCannyStep
from pipeline.steps.stylise_xdog_step import StyliseXDoGStep
from pipeline.steps.stylise_adaptive_step import StyliseAdaptiveStep
from pipeline.steps.stylise_hed_step import StyliseHEDStep
from pipeline.steps.stylise_dexined_step import StyliseDexiNedStep
from pipeline.steps.stylise_lineart_step import StyliseLineartStep
from pipeline.steps.stylise_informative_step import StyliseInformativeStep
from pipeline.steps.stylise_controlnet_step import StyliseControlNetStep
from pipeline.steps.stylise_img2img_step import StyliseImg2ImgStep
from pipeline.steps.vectorize_step import VectorizeStep
from pipeline.steps.gcode_gen_step import GCodeGenStep
from pipeline.steps.gcode_from_svg_step import GCodeFromSvgStep
from pipeline.steps.save_gcode_step import SaveGCodeStep
from pipeline.steps.send_gcode_step import SendGcodeStep

# Registry: step name (str) -> PipelineStep subclass
STEP_REGISTRY: dict[str, type["PipelineStep"]] = {
    # Image loading/saving - canonical first/last steps for all image pipelines
    "load_image":            LoadImageStep,
    "save_image":            SaveImageStep,
    # Stylizers - selectable by name
    "stylise_canny":         StyliseCannyStep,
    "stylise_xdog":          StyliseXDoGStep,
    "stylise_adaptive":      StyliseAdaptiveStep,
    "stylise_hed":           StyliseHEDStep,
    "stylise_dexined":       StyliseDexiNedStep,
    "stylise_lineart":       StyliseLineartStep,
    "stylise_informative":   StyliseInformativeStep,
    "stylise_controlnet":    StyliseControlNetStep,
    "stylise_img2img":       StyliseImg2ImgStep,
    # Pipeline steps
    "vectorise":             VectorizeStep,
    "gcode_gen":             GCodeGenStep,       # Legacy: custom coordinate transformation
    "gcode_from_svg":        GCodeFromSvgStep,   # TOML-profile-based (vpype-gcode-compatible)
    "save_gcode":            SaveGCodeStep,      # Save GCode to file
    "send_gcode":            SendGcodeStep,
}

