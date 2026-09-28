from __future__ import annotations

# Compatibility shim redirecting to upscaler.core.pipeline
from .core.pipeline import *
from .core.pipeline import (
    _default_realesrgan_dir,
    _even_output_scale,
    _find_result,
    _is_out_of_memory,
    _run_realesrgan,
    _visible_cuda_device,
)
