from __future__ import annotations

import importlib.metadata

try:
    __version__ = importlib.metadata.version("upscale-video")
except Exception:
    __version__ = "0.2.0"

from .core.media import MediaError, VideoMetadata, finalize_video, inspect_video, preprocess_video, resolve_binary
from .core.models import PROFILES, PROFILE_ALIASES, SIMPLE_LEVELS, ModelProfile, get_profile, resolve_profile_name, tile_candidates
from .core.pipeline import PipelineError, UpscaleOptions, UpscaleResult, ensure_output_dir, upscale
from .ui.app import UpscaleScreen, launch_tui

__all__ = [
    "__version__",
    "MediaError",
    "VideoMetadata",
    "finalize_video",
    "inspect_video",
    "preprocess_video",
    "resolve_binary",
    "PROFILES",
    "PROFILE_ALIASES",
    "SIMPLE_LEVELS",
    "ModelProfile",
    "get_profile",
    "resolve_profile_name",
    "tile_candidates",
    "PipelineError",
    "UpscaleOptions",
    "UpscaleResult",
    "ensure_output_dir",
    "upscale",
    "UpscaleScreen",
    "launch_tui",
]
