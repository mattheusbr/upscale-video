from __future__ import annotations

import time
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import RichLog, Static


class ChevronPipeline(Static):
    """Renderiza as fases do pipeline em formato de chevrons coloridos (>>>>>)."""

    stage = reactive(0)

    STAGES = [
        ("INSPEC", "#10b981", "#022c22"),
        ("EXTRAIR", "#0284c7", "#ffffff"),
        ("UPSCALE", "#d946ef", "#ffffff"),
        ("ENCODE", "#334155", "#94a3b8"),
        ("FINAL", "#1e1e38", "#c084fc"),
    ]

    def render(self) -> Text:
        t = Text()
        total = len(self.STAGES)
        for idx, (name, bg, fg) in enumerate(self.STAGES):
            if idx <= self.stage:
                symbol = " ✓ " if idx < self.stage else (" ⠋ " if idx == total - 1 else " >>> ")
                t.append(f" {name}{symbol}", style=f"{fg} on {bg} bold")
            else:
                t.append(f" {name} >>> ", style=f"#64748b on #1e293b")
            if idx < total - 1:
                t.append(" ", style="default on default")
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

        formatted = f"[dim #64748b]{self.line_number:2d}[/] [dim #38bdf8][{now}][/] {lvl_fmt}  [#e2e8f0]{message}[/]"
        self.write(formatted)
