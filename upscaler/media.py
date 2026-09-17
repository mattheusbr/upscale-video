from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


class MediaError(RuntimeError):
    """Raised when media inspection or FFmpeg processing fails."""


@dataclass(frozen=True)
class VideoMetadata:
    path: Path
    width: int
    height: int
    fps: float
    duration: float | None
    frame_count: int | None
    has_audio: bool
    codec: str | None
    pix_fmt: str | None
    color_space: str | None
    color_transfer: str | None
    color_primaries: str | None
    is_vfr: bool

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height


def resolve_binary(name: str, explicit: str | None = None) -> str:
    if explicit:
        candidate = Path(explicit)
        if candidate.exists():
            return str(candidate)
        raise MediaError(f"Executável não encontrado: {explicit}")
    resolved = shutil.which(name)
    if resolved:
        return resolved
    local_binary = Path(__file__).resolve().parents[1] / "tools" / "ffmpeg" / f"{name}.exe"
    if local_binary.is_file():
        return str(local_binary)
    raise MediaError(
        f"{name} não foi encontrado no PATH. Instale FFmpeg/FFprobe ou passe o caminho com a opção correspondente."
    )


def _parse_fraction(value: str | None) -> float:
    if not value or value in {"0/0", "N/A"}:
        return 0.0
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return 0.0


def inspect_video(path: str | Path, ffprobe_bin: str | None = None) -> VideoMetadata:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise MediaError(f"Arquivo de entrada não encontrado: {source}")

    ffprobe = resolve_binary("ffprobe", ffprobe_bin)
    command = [
        ffprobe,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(source),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise MediaError(completed.stderr.strip() or "FFprobe não conseguiu ler o arquivo")
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise MediaError("Resposta inválida do FFprobe") from exc

    streams = data.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    if not video:
        raise MediaError("O arquivo não contém stream de vídeo")

    avg_fps = _parse_fraction(video.get("avg_frame_rate"))
    real_fps = _parse_fraction(video.get("r_frame_rate"))
    fps = avg_fps or real_fps
    if fps <= 0:
        raise MediaError("Não foi possível determinar o FPS do vídeo")

    duration_text = video.get("duration") or data.get("format", {}).get("duration")
    duration = float(duration_text) if duration_text not in (None, "N/A") else None
    frame_text = video.get("nb_frames")
    frame_count = int(frame_text) if frame_text and frame_text != "N/A" else None
    # This is a conservative signal. Exact VFR detection is intentionally left
    # to a future frame-timestamp audit because it can require decoding frames.
    is_vfr = bool(avg_fps and real_fps and abs(avg_fps - real_fps) > 0.001)

    return VideoMetadata(
        path=source,
        width=int(video["width"]),
        height=int(video["height"]),
        fps=fps,
        duration=duration,
        frame_count=frame_count,
        has_audio=any(item.get("codec_type") == "audio" for item in streams),
        codec=video.get("codec_name"),
        pix_fmt=video.get("pix_fmt"),
        color_space=video.get("color_space"),
        color_transfer=video.get("color_transfer"),
        color_primaries=video.get("color_primaries"),
        is_vfr=is_vfr,
    )


def crop_filter_for_aspect(width: int, height: int, target_width: int, target_height: int) -> tuple[str, int, int]:
    if target_width <= 0 or target_height <= 0:
        raise ValueError("As dimensões do alvo devem ser positivas")

    target_aspect = target_width / target_height
    source_aspect = width / height
    if source_aspect > target_aspect:
        crop_height = height
        crop_width = int(height * target_aspect)
    else:
        crop_width = width
        crop_height = int(width / target_aspect)

    # yuv420p requires even dimensions; this also avoids chroma-edge surprises.
    crop_width = max(2, crop_width - crop_width % 2)
    crop_height = max(2, crop_height - crop_height % 2)
    x = max(0, (width - crop_width) // 2)
    y = max(0, (height - crop_height) // 2)
    return f"crop={crop_width}:{crop_height}:{x}:{y}", crop_width, crop_height


def run_ffmpeg(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        details = completed.stderr.strip() or completed.stdout.strip() or "erro desconhecido"
        raise MediaError(f"FFmpeg falhou: {details}")


def preprocess_video(
    source: Path,
    destination: Path,
    ffmpeg_bin: str,
    ffprobe_bin: str | None = None,
    target: tuple[int, int] | None = None,
    seconds: float | None = None,
) -> tuple[int, int]:
    metadata = inspect_video(source, ffprobe_bin)
    filters: list[str] = []
    output_width, output_height = metadata.width, metadata.height
    if target:
        crop_filter, output_width, output_height = crop_filter_for_aspect(
            metadata.width, metadata.height, target[0], target[1]
        )
        filters.append(crop_filter)

    command = [ffmpeg_bin, "-y", "-i", str(source)]
    if seconds is not None:
        command += ["-t", str(seconds)]
    command += ["-map", "0:v:0", "-an"]
    if filters:
        command += ["-vf", ",".join(filters)]
    # Lossless H.264 keeps the pre-crop from adding another generation loss.
    command += [
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-crf",
        "0",
        "-pix_fmt",
        "yuv444p",
        "-fps_mode",
        "passthrough",
        str(destination),
    ]
    run_ffmpeg(command)
    return output_width, output_height


def finalize_video(
    upscaled_video: Path,
    original_video: Path,
    destination: Path,
    ffmpeg_bin: str,
    target: tuple[int, int] | None,
    crf: int,
    preset: str,
    audio_bitrate: str,
    seconds: float | None,
    audio_enabled: bool = True,
) -> None:
    command = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(upscaled_video),
    ]
    if audio_enabled:
        command += ["-i", str(original_video), "-map", "0:v:0", "-map", "1:a?"]
    else:
        command += ["-map", "0:v:0"]
    if target:
        command += ["-vf", f"scale={target[0]}:{target[1]}:flags=lanczos"]
    command += [
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        str(crf),
        "-pix_fmt",
        "yuv420p",
    ]
    if audio_enabled:
        command += [
            "-c:a",
            "aac",
            "-b:a",
            audio_bitrate,
            "-ar",
            "48000",
        ]
    else:
        command += ["-an"]
    command += [
        "-movflags",
        "+faststart",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-shortest",
    ]
    if seconds is not None:
        command += ["-t", str(seconds)]
    command.append(str(destination))
    run_ffmpeg(command)
