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
from .models import PROFILES, PROFILE_ALIASES, SIMPLE_LEVELS, resolve_profile_name
from .pipeline import PipelineError, UpscaleOptions, _default_realesrgan_dir, ensure_output_dir, upscale


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
    profile_choices = sorted(set(PROFILES) | set(PROFILE_ALIASES))
    parser.add_argument("--profile", choices=profile_choices, default="clean", help="Perfil amigável: clean, max, compressed, anime, general, real, etc.")
    parser.add_argument("--target", type=_parse_target, help="Alvo, por exemplo 1080x1920; faz crop central para o aspecto")
    parser.add_argument("--scale", dest="outscale", type=float, help="Escala do modelo; por padrão calcula pelo target ou usa 4x")
    parser.add_argument("--tile", type=int, default=256, help="Tile inicial; 256 é um ponto de partida para 8 GB")
    parser.add_argument("--tile-pad", type=int, default=10)
    parser.add_argument("--denoise", type=float, help="Força de denoise do perfil compressed, entre 0 e 1")
    parser.add_argument("--fp32", action="store_true", help="Usa FP32; FP16 é o padrão para a RTX 3060 Ti")
    parser.add_argument(
        "--device",
        help="Dispositivo CUDA para usar, por exemplo cuda:0, cuda:1 ou 1. Quando omitido, o projeto usa a GPU padrão.",
    )
    parser.add_argument("--gpu", dest="device", help=argparse.SUPPRESS)
    parser.add_argument("--no-auto-tile", action="store_true", help="Não reduzir o tile automaticamente em caso de OOM")
    parser.add_argument("--allow-vfr", action="store_true", help="Permite FPS variável com FPS nominal")
    parser.add_argument("--ffmpeg-bin", help="Caminho para ffmpeg.exe")
    parser.add_argument("--ffprobe-bin", help="Caminho para ffprobe.exe")
    parser.add_argument("--realesrgan-dir", type=Path, help="Diretório do checkout oficial do Real-ESRGAN")
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--crf", type=int, default=17, help="CRF final libx264; menor = maior qualidade/tamanho")
    parser.add_argument("--preset", default="slow", help="Preset libx264 final")
    parser.add_argument("--audio-bitrate", default="192k")
    parser.add_argument("--no-audio", action="store_true", help="Não re-encoda nem preserva o áudio do vídeo final")


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
        device=getattr(args, "device", None),
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
        audio_enabled=not getattr(args, "no_audio", False),
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
    realesrgan = (args.realesrgan_dir or _default_realesrgan_dir()).resolve()
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
    print("Processando vídeo...", flush=True)
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


def _simple(args: argparse.Namespace) -> int:
    source = Path(args.input).expanduser().resolve()
    try:
        metadata = inspect_video(source, args.ffprobe_bin)
        selected_profile = resolve_profile_name(getattr(args, "profile", "clean")) if getattr(args, "profile", None) else resolve_profile_name(getattr(args, "model", "RealESRGAN_x4plus"))
        if getattr(args, "profile", None) is None:
            selected_profile = resolve_profile_name(getattr(args, "model", "RealESRGAN_x4plus"))
        target_long_edge = SIMPLE_LEVELS[args.nivel]
        source_long_edge = max(metadata.width, metadata.height)
        outscale = max(1.0, min(4.0, target_long_edge / source_long_edge))
        output = source.with_name(f"{source.stem}_upscaled_{args.nivel}{source.suffix}")
        if getattr(args, "profile", None) is None and hasattr(args, "model"):
            model_to_profile = {
                "RealESRGAN_x4plus": "clean",
                "realesr-general-x4v3": "compressed",
                "realesr-animevideov3": "anime",
            }
            selected_profile = "max" if args.nivel == "max" and args.model == "RealESRGAN_x4plus" else model_to_profile[args.model]
        if getattr(args, "benchmark", False):
            benchmark_dir = ensure_output_dir(Path(args.input).with_suffix("").name + "_benchmark")
            benchmark_args = argparse.Namespace(
                input=args.input,
                output_dir=benchmark_dir,
                seconds=5.0,
                profiles=[selected_profile],
                profile=selected_profile,
                target=None,
                outscale=None,
                tile=256,
                tile_pad=10,
                denoise=None,
                fp32=False,
                no_auto_tile=False,
                allow_vfr=False,
                ffmpeg_bin=args.ffmpeg_bin,
                ffprobe_bin=args.ffprobe_bin,
                realesrgan_dir=args.realesrgan_dir,
                python_executable=args.python_executable,
                crf=17,
                preset="slow",
                audio_bitrate="320k",
                no_audio=args.no_audio,
            )
            print(f"Benchmark rápido: perfil={selected_profile}, nivel={args.nivel}", flush=True)
            return _benchmark(benchmark_args)
        simple_args = argparse.Namespace(
            input=source,
            output=output,
            profile=selected_profile,
            target=None,
            outscale=outscale,
            tile=256,
            tile_pad=10,
            denoise=None,
            fp32=False,
            device=getattr(args, "device", None),
            no_auto_tile=False,
            allow_vfr=False,
            ffmpeg_bin=args.ffmpeg_bin,
            ffprobe_bin=args.ffprobe_bin,
            realesrgan_dir=args.realesrgan_dir,
            python_executable=args.python_executable,
            crf=17,
            preset="slow",
            audio_bitrate="320k",
            no_audio=args.no_audio,
        )
        print(
            f"Nível {args.nivel}: {metadata.width}x{metadata.height} -> "
            f"aproximadamente {int(metadata.width * outscale)}x{int(metadata.height * outscale)}",
            flush=True,
        )
        model_name = PROFILES[resolve_profile_name(selected_profile)].model_name
        print(f"Perfil: {selected_profile} ({model_name})", flush=True)
        if args.no_audio:
            print("Áudio: sem processamento de áudio no arquivo final", flush=True)
        return _run(simple_args)
    except (MediaError, PipelineError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2


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

    simple = subparsers.add_parser("simple", help="Processa um vídeo usando apenas um nível de qualidade")
    simple.add_argument("input")
    simple.add_argument("--nivel", choices=sorted(SIMPLE_LEVELS), default="medio")
    simple.add_argument(
        "--profile",
        choices=sorted(set(PROFILES) | set(PROFILE_ALIASES)),
        default=None,
        help="Perfil amigável: clean, max, compressed, anime, general, real, etc.",
    )
    simple.add_argument(
        "--model",
        choices=["RealESRGAN_x4plus", "realesr-general-x4v3", "realesr-animevideov3"],
        default="RealESRGAN_x4plus",
        help="Modelo do super-resolução; o padrão é RealESRGAN_x4plus",
    )
    simple.add_argument("--ffmpeg-bin", help="Caminho para ffmpeg.exe")
    simple.add_argument("--ffprobe-bin", help="Caminho para ffprobe.exe")
    simple.add_argument("--realesrgan-dir", type=Path, help="Diretório do checkout oficial do Real-ESRGAN")
    simple.add_argument("--python-executable", default=sys.executable)
    simple.add_argument("--device", help="Dispositivo CUDA para usar, por exemplo cuda:0, cuda:1 ou 1")
    simple.add_argument("--gpu", dest="device", help=argparse.SUPPRESS)
    simple.add_argument("--no-audio", action="store_true", help="Não re-encoda nem preserva o áudio do vídeo final")
    simple.add_argument("--benchmark", action="store_true", help="Executa uma avaliação curta do perfil selecionado antes de processar o vídeo completo")
    simple.set_defaults(handler=_simple)

    max_profile = subparsers.add_parser("max", help="Alias para qualidade máxima usando o melhor modelo disponível")
    max_profile.add_argument("input")
    max_profile.add_argument("output")
    max_profile.add_argument("--tile", type=int, default=256)
    max_profile.add_argument("--ffmpeg-bin", help="Caminho para ffmpeg.exe")
    max_profile.add_argument("--ffprobe-bin", help="Caminho para ffprobe.exe")
    max_profile.add_argument("--realesrgan-dir", type=Path, help="Diretório do checkout oficial do Real-ESRGAN")
    max_profile.add_argument("--python-executable", default=sys.executable)
    max_profile.add_argument("--crf", type=int, default=17)
    max_profile.add_argument("--preset", default="slow")
    max_profile.add_argument("--audio-bitrate", default="320k")
    max_profile.set_defaults(
        handler=lambda args: _run(
            argparse.Namespace(
                input=args.input,
                output=args.output,
                profile="max",
                target=None,
                outscale=None,
                tile=args.tile,
                tile_pad=10,
                denoise=None,
                fp32=False,
                no_auto_tile=False,
                allow_vfr=False,
                ffmpeg_bin=args.ffmpeg_bin,
                ffprobe_bin=args.ffprobe_bin,
                realesrgan_dir=args.realesrgan_dir,
                python_executable=args.python_executable,
                crf=args.crf,
                preset=args.preset,
                audio_bitrate=args.audio_bitrate,
            )
        )
    )

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
    benchmark.add_argument("--profiles", nargs="+", choices=sorted(set(PROFILES) | set(PROFILE_ALIASES)))
    _add_common_options(benchmark)
    benchmark.set_defaults(handler=_benchmark)

    tui = subparsers.add_parser("tui", help="Abre uma interface interativa em terminal usando Textual")
    tui.add_argument("--input", help="Arquivo de entrada opcional para pré-preencher a tela")
    tui.set_defaults(handler=lambda args: _launch_tui(args))
    return parser


def _launch_tui(args: argparse.Namespace) -> int:
    try:
        from .tui import launch_tui
    except ModuleNotFoundError as exc:
        print("A biblioteca Textual não está instalada. Instale com: python -m pip install textual", file=sys.stderr)
        return 2
    return launch_tui(args.input)


def normalize_argv(argv: list[str]) -> list[str]:
    if not argv:
        return argv
    known_commands = {"doctor", "inspect", "run", "simple", "max", "preview", "benchmark", "tui", "-h", "--help"}
    if argv[0] not in known_commands:
        return ["simple", *argv]
    return argv


def main(argv: list[str] | None = None) -> None:
    args_list = sys.argv[1:] if argv is None else argv

    # The frozen executable acts as its own Python worker for Real-ESRGAN.
    # This keeps CUDA/PyTorch imports in the packaged runtime instead of
    # requiring a separately installed Python interpreter.
    if args_list and args_list[0] == "--_upscale-worker":
        from .core.runner import main as run_worker

        sys.argv = [sys.argv[0], *args_list[1:]]
        run_worker()
        return

    parser = build_parser()

    if not args_list:
        parser.print_help()
        raise SystemExit(0)

    args = parser.parse_args(normalize_argv(args_list))
    raise SystemExit(args.handler(args))
