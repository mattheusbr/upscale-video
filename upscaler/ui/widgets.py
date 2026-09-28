from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import DirectoryTree, RichLog, Static


class ChevronPipeline(Static):
    """Renderiza as fases do pipeline em formato de blocos/chevrons inspirados no design do VidiScale."""

    stage = reactive(0)
    spinner_idx = reactive(0)

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    STAGES = ["INSPEC", "EXTRAIR", "UPSCALE", "ENCODE", "FINAL"]

    def on_mount(self) -> None:
        self.set_interval(0.2, self._tick_spinner)

    def _tick_spinner(self) -> None:
        self.spinner_idx = (self.spinner_idx + 1) % len(self.SPINNER_FRAMES)

    def render(self) -> Text:
        t = Text()
        spinner = self.SPINNER_FRAMES[self.spinner_idx]
        total = len(self.STAGES)

        for idx, name in enumerate(self.STAGES):
            if idx < self.stage:
                # Concluído
                t.append(f"[ {name}  ✓ ]", style="bold #022c22 on #10b981")
            elif idx == self.stage:
                # Ativo no momento
                t.append(f"[ {name} {spinner} ]", style="bold #032030 on #38bdf8")
            else:
                # Pendente
                sym = ">>>" if idx == total - 1 else "   "
                t.append(f"[ {name} {sym} ]", style="#64748b on #162030")

            if idx < total - 1:
                t.append("  ", style="default on default")

        return t


class GradientStatusBar(Static):
    """Barra decorativa com degradê segmentado cyberpunk."""

    def render(self) -> Text:
        t = Text()
        segments = [
            ("#00f5d4", 4),
            ("#38bdf8", 4),
            ("#818cf8", 4),
            ("#c084fc", 4),
            ("#f472b6", 4),
            ("#f72585", 4),
        ]
        for color, count in segments:
            t.append("█" * count, style=f"{color}")
        return t


class NumberedLog(RichLog):
    """Log estruturado com contagem sequencial de linhas, timestamps precisos e tags coloridas."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.line_number = 0

    def append_entry(self, level: str, message: str) -> None:
        self.line_number += 1
        now = time.strftime("%H:%M:%S") + f".{int((time.time() % 1) * 1000):03d}"
        lvl = level.upper().strip()
        if lvl == "INFO":
            lvl_fmt = "[#00f5d4 bold]INFO [/]"
        elif lvl in ("WARN", "WARNING"):
            lvl_fmt = "[#fbbf24 bold]WARN [/]"
        elif lvl in ("ERROR", "ERR"):
            lvl_fmt = "[#f87171 bold]ERROR[/]"
        else:
            lvl_fmt = f"[cyan bold]{lvl:<5}[/]"

        formatted = f"[dim #64748b]{self.line_number:5d}[/] [dim #38bdf8][{now}][/] {lvl_fmt}  [#e2e8f0]{message}[/]"
        self.write(formatted)


class VideoDirectoryTree(DirectoryTree):
    """Árvore de diretórios otimizada que exibe pastas e arquivos de vídeo suportados."""

    VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv", ".ts", ".wmv", ".m4v"}

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [
            p for p in paths
            if p.is_dir() or p.suffix.lower() in self.VIDEO_EXTENSIONS
        ]
