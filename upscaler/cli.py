from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .media import MediaError, inspect_video, resolve_binary
from .models import PROFILES
from .pipeline import PipelineError, UpscaleOptions, ensure_output_dir, upscale


def _parse_target(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    try:
        width_text, height_text = value.lower().split("x", 1)
        width, height = int(width_text), int(height_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("target deve estar no formato LARGURAxALTURA, por exemplo 1080x1920") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("target deve ter dimensões positivas")
    return width, height


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--profile", choices=sorted(PROFILES), default="clean")
    parser.add_argument("--target", type=_parse_target, help="Alvo, por exemplo 1080x1920; faz crop central para o aspecto")
    parser.add_argument("--scale", dest="outscale", type=float, help="Escala do modelo; por padrão calcula pelo target ou usa 4x")
    parser.add_argument("--tile", type=int, default=256, help="Tile inicial; 256 é um ponto de partida para 8 GB")
    parser.add_argument("--tile-pad", type=int, default=10)
    parser.add_argument("--denoise", type=float, help="Força de denoise do perfil compressed, entre 0 e 1")
    parser.add_argument("--fp32", action="store_true", help="Usa FP32; FP16 é o padrão para a RTX 3060 Ti")
    parser.add_argument("--no-auto-tile", action="store_true", help="Não reduzir o tile automaticamente em caso de OOM")
    parser.add_argument("--allow-vfr", action="store_true", help="Permite FPS variável com FPS nominal")
    parser.add_argument("--ffmpeg-bin", help="Caminho para ffmpeg.exe")
    parser.add_argument("--ffprobe-bin", help="Caminho para ffprobe.exe")
    parser.add_argument("--realesrgan-dir", type=Path, help="Diretório do checkout oficial do Real-ESRGAN")
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--crf", type=int, default=17, help="CRF final libx264; menor = maior qualidade/tamanho")
    parser.add_argument("--preset", default="slow", help="Preset libx264 final")
    parser.add_argument("--audio-bitrate", default="192k")


def _options_from_args(args: argparse.Namespace, seconds: float | None = None, output: Path | None = None) -> UpscaleOptions:
    return UpscaleOptions(
        input_path=Path(args.input),
        output_path=output or Path(args.output),
        profile=args.profile,
        target=args.target,
        outscale=args.outscale,
        tile=args.tile,
        tile_pad=args.tile_pad,
        denoise_strength=args.denoise,
        fp32=args.fp32,
        auto_tile=not args.no_auto_tile,
        seconds=seconds,
        allow_vfr=args.allow_vfr,
        ffmpeg_bin=args.ffmpeg_bin,
        ffprobe_bin=args.ffprobe_bin,
        realesrgan_dir=args.realesrgan_dir,
        python_executable=args.python_executable,
        crf=args.crf,
        preset=args.preset,
        audio_bitrate=args.audio_bitrate,
    )


def _metadata_dict(metadata: object) -> dict[str, object]:
    return {
        key: (str(value) if isinstance(value, Path) else value)
        for key, value in vars(metadata).items()
    }


def _doctor(args: argparse.Namespace) -> int:
    print(f"Python: {sys.executable}")
    print(f"Version: {sys.version.split()[0]}")
    print(f"GPU probe: {'nvidia-smi encontrado' if shutil.which('nvidia-smi') else 'não encontrado'}")
    if shutil.which("nvidia-smi"):
        probe = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version,compute_cap", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        )
        print(probe.stdout.strip() or probe.stderr.strip())
    for module in ("torch", "torchvision", "basicsr", "realesrgan", "cv2", "ffmpeg"):
        print(f"{module}: {'OK' if importlib.util.find_spec(module) else 'ausente'}")
    for binary in ("ffmpeg", "ffprobe"):
        try:
            print(f"{binary}: {resolve_binary(binary)}")
        except MediaError:
            print(f"{binary}: ausente")
    realesrgan = (args.realesrgan_dir or Path("vendor/Real-ESRGAN")).resolve()
    print(f"Real-ESRGAN: {realesrgan / 'inference_realesrgan_video.py'}")
    return 0


def _inspect(args: argparse.Namespace) -> int:
    try:
        metadata = inspect_video(args.input, args.ffprobe_bin)
    except MediaError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(_metadata_dict(metadata), indent=2, ensure_ascii=False))
    return 0


def _run(args: argparse.Namespace, seconds: float | None = None) -> int:
    try:
        result = upscale(_options_from_args(args, seconds=seconds))
    except (PipelineError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    print(f"Saída: {result.output_path}")
    print(f"Perfil: {result.profile.key} ({result.profile.model_name})")
    print(f"Tile usado: {result.tile_used}")
    print(f"Tempo: {result.elapsed_seconds:.1f}s")
    return 0


def _benchmark(args: argparse.Namespace) -> int:
    output_dir = ensure_output_dir(args.output_dir)
    profiles = args.profiles or sorted(PROFILES)
    records: list[dict[str, object]] = []
    for profile in profiles:
        destination = output_dir / f"{Path(args.input).stem}_{profile}.mp4"
        started = time.perf_counter()
        profile_args = argparse.Namespace(**vars(args))
        profile_args.profile = profile
        try:
            result = upscale(_options_from_args(profile_args, seconds=args.seconds, output=destination))
            records.append(
                {
                    "profile": profile,
                    "model": result.profile.model_name,
                    "output": str(destination),
                    "tile": result.tile_used,
                    "elapsed_seconds": result.elapsed_seconds,
                    "status": "ok",
                }
            )
        except (PipelineError, ValueError) as exc:
            records.append(
                {
                    "profile": profile,
                    "elapsed_seconds": time.perf_counter() - started,
                    "status": "error",
                    "error": str(exc),
                }
            )
    report = output_dir / "benchmark.json"
    report.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Relatório: {report}")
    return 0 if all(item["status"] == "ok" for item in records) else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Upscale local de vídeo com Real-ESRGAN CUDA")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Verifica GPU, dependências e executáveis")
    doctor.add_argument("--realesrgan-dir", type=Path)
    doctor.set_defaults(handler=_doctor)

    inspect = subparsers.add_parser("inspect", help="Inspeciona metadata do vídeo")
    inspect.add_argument("input")
    inspect.add_argument("--ffprobe-bin")
    inspect.set_defaults(handler=_inspect)

    run = subparsers.add_parser("run", help="Processa um vídeo completo")
    run.add_argument("input")
    run.add_argument("output")
    _add_common_options(run)
    run.set_defaults(handler=lambda args: _run(args))

    preview = subparsers.add_parser("preview", help="Processa somente uma janela curta para comparação")
    preview.add_argument("input")
    preview.add_argument("output")
    preview.add_argument("--seconds", type=float, default=5.0)
    _add_common_options(preview)
    preview.set_defaults(handler=lambda args: _run(args, seconds=args.seconds))

    benchmark = subparsers.add_parser("benchmark", help="Compara perfis usando um trecho curto")
    benchmark.add_argument("input")
    benchmark.add_argument("output_dir")
    benchmark.add_argument("--seconds", type=float, default=5.0)
    benchmark.add_argument("--profiles", nargs="+", choices=sorted(PROFILES))
    _add_common_options(benchmark)
    benchmark.set_defaults(handler=_benchmark)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    raise SystemExit(args.handler(args))
