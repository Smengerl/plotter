# pipeline/steps/base/__init__.py
#
# Public re-exports for the base module.
# Import base classes from here to avoid deep import paths.

from pipeline.steps.base.pipeline_step import (
    MissingContextError,
    PipelineStep,
)
from pipeline.steps.base.stylizer_base import (
    CVBaseStep,          # backward-compatible alias for StylizerStep
    CVStylizerStep,      # backward-compatible alias for StylizerStep
    StylizerStep,
    load_gray,
    ensure_odd,
    resolve_device,
)
from pipeline.steps.base.nn_stylizer_base import (
    NNStylizerStep,
    _CONTROLNET_AUX_INSTALL_HINT,
)
from pipeline.steps.base.diffusion_stylizer_base import (
    DiffusionStylizerStep,
    _DIFFUSERS_INSTALL_HINT,
)

__all__ = [
    # Core abstractions
    "PipelineStep",
    "MissingContextError",
    # Stylizer hierarchy
    "StylizerStep",
    "CVStylizerStep",
    "CVBaseStep",
    "NNStylizerStep",
    "DiffusionStylizerStep",
    # Utilities
    "load_gray",
    "ensure_odd",
    "resolve_device",
    # Install hints
    "_CONTROLNET_AUX_INSTALL_HINT",
    "_DIFFUSERS_INSTALL_HINT",
]
