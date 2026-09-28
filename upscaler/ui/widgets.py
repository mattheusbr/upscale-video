from __future__ import annotations

import time
from pathlib import Path
from typing import Iterable

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import DirectoryTree, RichLog, Sparkline, Static


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


class MetricSparkline(Sparkline):
    """Sparkline de métrica contínua com escala fixa de 0 a 100%, renderização multi-linha e auto-refresh."""

    BAR_TIERS = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

    def __init__(
        self,
        data: Iterable[float] | None = None,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        init_data = list(data) if data is not None else [0.0] * 24
        super().__init__(data=init_data, id=id, classes=classes)
        self._metric_data: list[float] = list(init_data)

    @property
    def data(self) -> list[float]:
        return self._metric_data

    @data.setter
    def data(self, values: Iterable[float]) -> None:
        self._metric_data = [float(v) for v in values]
        self.refresh()

    def add_value(self, val: float, max_len: int = 24) -> None:
        self._metric_data.append(float(val))
        if len(self._metric_data) > max_len:
            self._metric_data = self._metric_data[-max_len:]
        self.refresh()

    def render(self) -> Text:
        width = max(1, self.content_size.width or len(self._metric_data))
        height = max(1, self.content_size.height or 1)
        pts = self._metric_data[-width:] if len(self._metric_data) >= width else self._metric_data
        if len(pts) < width:
            pts = [0.0] * (width - len(pts)) + list(pts)

        lines: list[Text] = []
        for i in reversed(range(height)):
            row_min = i * (100.0 / height)
            row_max = (i + 1) * (100.0 / height)
            row_text = Text()
            for v in pts:
                pct = max(0.0, min(100.0, float(v)))
                if pct >= row_max:
                    char = "█"
                elif pct <= row_min:
                    char = " " if i > 0 else " "
                else:
                    ratio = (pct - row_min) / (row_max - row_min)
                    idx = int(round(ratio * (len(self.BAR_TIERS) - 1)))
                    char = self.BAR_TIERS[idx]

                if pct >= 80:
                    style = "bold #ef4444"
                elif pct >= 50:
                    style = "#fbbf24"
                elif pct >= 20:
                    style = "#38bdf8"
                elif pct > 0:
                    style = "#0284c7"
                else:
                    style = "#1e293b" if i == 0 else "default"
                row_text.append(char, style=style)
            lines.append(row_text)

        return Text("\n").join(lines)

