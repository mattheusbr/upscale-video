from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .media import MediaError, finalize_video, inspect_video, preprocess_video, resolve_binary
from .models import ModelProfile, get_profile, tile_candidates


class PipelineError(RuntimeError):
    """Raised when an upscale job cannot be completed."""


@dataclass(frozen=True)
class UpscaleOptions:
    input_path: Path
    output_path: Path
    profile: str = "clean"
    target: tuple[int, int] | None = None
    outscale: float | None = None
    tile: int = 256
    tile_pad: int = 10
    denoise_strength: float | None = None
    fp32: bool = False
    device: str | None = None
    auto_tile: bool = True
    seconds: float | None = None
    allow_vfr: bool = False
    ffmpeg_bin: str | None = None
    ffprobe_bin: str | None = None
    realesrgan_dir: Path | None = None
    python_executable: str = sys.executable
    crf: int = 17
    preset: str = "slow"
    audio_bitrate: str = "192k"
    audio_enabled: bool = True


@dataclass(frozen=True)
class UpscaleResult:
    output_path: Path
    profile: ModelProfile
    tile_used: int
    elapsed_seconds: float
    input_metadata: object


def _default_realesrgan_dir() -> Path:
    configured = os.environ.get("REAL_ESRGAN_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[1] / "vendor" / "Real-ESRGAN"


def _is_out_of_memory(error: BaseException) -> bool:
    text = str(error).lower()
    return "out of memory" in text or "cuda error" in text or "cublas_status_alloc_failed" in text


def _find_result(directory: Path) -> Path:
    candidates = sorted(directory.glob("*_upscaled.mp4"))
    if not candidates:
        candidates = sorted(directory.glob("*.mp4"))
    if not candidates:
        raise PipelineError(f"Real-ESRGAN terminou sem gerar MP4 em {directory}")
    return candidates[0]


def _even_output_scale(width: int, height: int, requested: float) -> float:
    """Keep the Real-ESRGAN intermediate dimensions compatible with libx264."""
    scale = requested
    while True:
        output_width = int(width * scale)
        output_height = int(height * scale)
        if output_width % 2 == 0 and output_height % 2 == 0:
            return scale

        candidates: list[float] = []
        if output_width % 2:
            candidates.append((output_width - 1) / width)
        if output_height % 2:
            candidates.append((output_height - 1) / height)
        scale = min(candidates)


def _visible_cuda_device(device: str | None) -> str | None:
    if not device:
        return None
    value = str(device).strip().lower()
    if not value or value in {"cpu", "cpu:0"}:
        return None
    if value.startswith("cuda:"):
        value = value.split(":", 1)[1]
    if value.startswith("cuda"):
        value = value[4:]
    value = value.strip(":")
    if value and value.isdigit():
        return value
    return None


def _run_realesrgan(
    source: Path,
    output_dir: Path,
    options: UpscaleOptions,
    profile: ModelProfile,
    tile: int,
    ffmpeg_bin: str,
    outscale: float,
) -> Path:
    root = (options.realesrgan_dir or _default_realesrgan_dir()).resolve()
    script = root / "inference_realesrgan_video.py"
    if not script.is_file():
        raise PipelineError(
            f"Script do Real-ESRGAN não encontrado: {script}. Execute scripts\\bootstrap.ps1 ou passe --realesrgan-dir."
        )

    compatibility_runner = Path(__file__).with_name("realesrgan_runner.py")
    command = [
        options.python_executable,
        str(compatibility_runner),
        str(script),
        "-i",
        str(source),
        "-o",
        str(output_dir),
        "-n",
        profile.model_name,
        "-s",
        str(outscale),
        "-t",
        str(tile),
        "--tile_pad",
        str(options.tile_pad),
        "--ffmpeg_bin",
        ffmpeg_bin,
        "--num_process_per_gpu",
        "1",
    ]
    if profile.key == "compressed":
        denoise = options.denoise_strength
        if denoise is None:
            denoise = profile.default_denoise
        if denoise is not None:
            if not 0 <= denoise <= 1:
                raise PipelineError("denoise_strength deve estar entre 0 e 1")
            command += ["-dn", str(denoise)]
    if options.fp32:
        command.append("--fp32")

    child_env = os.environ.copy()
    ffmpeg_directory = str(Path(ffmpeg_bin).resolve().parent)
    child_env["PATH"] = ffmpeg_directory + os.pathsep + child_env.get("PATH", "")
    visible_device = _visible_cuda_device(options.device)
    if visible_device is not None:
        child_env["CUDA_VISIBLE_DEVICES"] = visible_device
    process = subprocess.Popen(
        command,
        cwd=root,
        env=child_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    output_chunks: list[str] = []
    if process.stdout is not None:
        while True:
            chunk = process.stdout.read(256)
            if not chunk:
                break
            output_chunks.append(chunk)
            sys.stdout.write(chunk)
            sys.stdout.flush()
    returncode = process.wait()
    combined = "".join(output_chunks)
    if returncode != 0:
        raise PipelineError(combined.strip() or "Real-ESRGAN falhou sem mensagem")
    result = _find_result(output_dir)
    return result


def upscale(options: UpscaleOptions) -> UpscaleResult:
    started = time.perf_counter()
    source = options.input_path.expanduser().resolve()
    destination = options.output_path.expanduser().resolve()
    if source == destination:
        raise PipelineError("A saída deve ser diferente da entrada")
    destination.parent.mkdir(parents=True, exist_ok=True)

    profile = get_profile(options.profile)
    try:
        ffmpeg_bin = resolve_binary("ffmpeg", options.ffmpeg_bin)
        metadata = inspect_video(source, options.ffprobe_bin)
    except MediaError as exc:
        raise PipelineError(str(exc)) from exc

    if metadata.is_vfr and not options.allow_vfr:
        raise PipelineError(
            "O vídeo parece ter FPS variável. Normalize-o para CFR ou use --allow-vfr conscientemente; "
            "o backend atual trabalha frame a frame com um FPS nominal."
        )
    if metadata.color_transfer in {"smpte2084", "arib-std-b67"}:
        raise PipelineError(
            "HDR detectado. A saída BT.709 exige uma política explícita de tone mapping; "
            "essa conversão não é feita automaticamente no primeiro MVP."
        )

    if options.target:
        target_width, target_height = options.target
        target_aspect = target_width / target_height
        source_aspect = metadata.aspect_ratio
        needs_crop = abs(source_aspect - target_aspect) > 0.001
    else:
        needs_crop = False

    with tempfile.TemporaryDirectory(prefix="upscale-video-") as temp_name:
        temp = Path(temp_name)
        if needs_crop or options.seconds is not None:
            prepared = temp / "prepared.mp4"
            prepared_width, prepared_height = preprocess_video(
                source,
                prepared,
                ffmpeg_bin,
                ffprobe_bin=options.ffprobe_bin,
                target=options.target if needs_crop else None,
                seconds=options.seconds,
            )
            inference_input = prepared
        else:
            prepared_width, prepared_height = metadata.width, metadata.height
            inference_input = source

        if options.outscale is not None:
            outscale = options.outscale
        elif options.target:
            outscale = max(options.target[0] / prepared_width, options.target[1] / prepared_height)
        else:
            outscale = 4.0
        if outscale <= 0:
            raise PipelineError("outscale deve ser maior que zero")
        outscale = _even_output_scale(prepared_width, prepared_height, outscale)

        last_error: BaseException | None = None
        processed: Path | None = None
        used_tile: int | None = None
        for candidate_tile in tile_candidates(options.tile, options.auto_tile):
            attempt_dir = temp / f"realesrgan-tile-{candidate_tile}"
            attempt_dir.mkdir()
            try:
                processed = _run_realesrgan(
                    inference_input,
                    attempt_dir,
                    options,
                    profile,
                    candidate_tile,
                    ffmpeg_bin,
                    outscale,
                )
                used_tile = candidate_tile
                break
            except (PipelineError, OSError) as exc:
                last_error = exc
                if not options.auto_tile or not _is_out_of_memory(exc):
                    raise

        if processed is None or used_tile is None:
            raise PipelineError(f"Não foi possível processar com os tiles disponíveis: {last_error}")

        try:
            finalize_video(
                processed,
                source,
                destination,
                ffmpeg_bin,
                options.target,
                options.crf,
                options.preset,
                options.audio_bitrate,
                options.seconds,
                options.audio_enabled,
            )
        except MediaError as exc:
            raise PipelineError(str(exc)) from exc

    return UpscaleResult(
        output_path=destination,
        profile=profile,
        tile_used=used_tile,
        elapsed_seconds=time.perf_counter() - started,
        input_metadata=metadata,
    )


def ensure_output_dir(path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    return output
