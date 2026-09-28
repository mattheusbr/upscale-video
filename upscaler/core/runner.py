"""Run the upstream Real-ESRGAN script with small dependency shims.

BasicSR 1.4.2 imports torchvision.transforms.functional_tensor, a module that
was removed from newer torchvision releases. The public API used by BasicSR is
still available from torchvision.transforms.functional, so expose that narrow
compatibility module only in the child process that runs upstream code.
"""

from __future__ import annotations

import runpy
import sys
import types
from pathlib import Path


def _install_torchvision_compat() -> None:
    try:
        from torchvision.transforms import functional
    except ImportError:
        return
    module_name = "torchvision.transforms.functional_tensor"
    if module_name in sys.modules:
        return
    compatibility = types.ModuleType(module_name)
    compatibility.rgb_to_grayscale = functional.rgb_to_grayscale
    sys.modules[module_name] = compatibility


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Uso: realesrgan_runner.py caminho-do-script [argumentos]")
    _install_torchvision_compat()
    script = Path(sys.argv[1]).resolve()
    if not script.is_file():
        raise SystemExit(f"Script não encontrado: {script}")
    sys.argv = [str(script), *sys.argv[2:]]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()

