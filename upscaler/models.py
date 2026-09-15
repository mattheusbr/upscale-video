from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelProfile:
    key: str
    model_name: str
    description: str
    default_denoise: float | None = None


PROFILES: dict[str, ModelProfile] = {
    "clean": ModelProfile(
        key="clean",
        model_name="RealESRGAN_x4plus",
        description="Live-action relativamente limpo; maior detalhe e textura.",
    ),
    "compressed": ModelProfile(
        key="compressed",
        model_name="realesr-general-x4v3",
        description="Vídeo comprimido, ruidoso ou com artefatos; denoise controlável.",
        default_denoise=0.5,
    ),
    "anime": ModelProfile(
        key="anime",
        model_name="realesr-animevideov3",
        description="Animação e ilustração; não é o perfil padrão para live-action.",
    ),
}

SIMPLE_LEVELS: dict[str, int] = {
    "baixo": 1280,
    "medio": 1920,
    "alto": 3840,
}


def get_profile(name: str) -> ModelProfile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        available = ", ".join(PROFILES)
        raise ValueError(f"Perfil desconhecido: {name}. Use: {available}") from exc


def tile_candidates(start: int, auto_tile: bool = True) -> list[int]:
    if start < 32:
        raise ValueError("tile deve ser pelo menos 32")
    if not auto_tile:
        return [start]

    candidates = sorted(
        {start, int(start * 0.75), start // 2, 96, 64, 32},
        reverse=True,
    )
    result: list[int] = []
    for candidate in candidates:
        if candidate > start:
            continue
        candidate = max(32, candidate)
        if candidate not in result:
            result.append(candidate)
    return result
