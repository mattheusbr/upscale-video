from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

try:
    import torch
except ImportError:  # pragma: no cover
    torch = None

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Input, ProgressBar, RadioButton, RadioSet, RichLog, Select, Sparkline, Static
from textual.widgets import (
    Button,
    Input,
    OptionList,
    ProgressBar,
    RadioButton,
    RadioSet,
    RichLog,
    Sparkline,
    Static,
)
from textual.widgets.option_list import Option

from .media import inspect_video, resolve_binary
from .models import SIMPLE_LEVELS
from .pipeline import UpscaleOptions, upscale


class SettingsContainer(Vertical):
    pass


class StatusLogPanel(Vertical):
    pass


class PerformancePanel(Vertical):
    pass


def build_output_path(input_path: str | Path, profile: str, level: str) -> Path:
    source = Path(input_path).expanduser()
    if not source.name:
        raise ValueError("Caminho do vídeo inválido")

    stem = source.stem
    safe_profile = str(profile).strip().lower().replace(" ", "_")
    safe_level = str(level).strip().lower().replace(" ", "_")
    candidate = source.with_name(f"{safe_profile}_{safe_level}_{stem}{source.suffix}")

    if not candidate.exists():
        return candidate

    index = 1
    while True:
        candidate = source.with_name(f"{safe_profile}_{safe_level}_{stem}_{index}{source.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def resolve_input_path(value: str | Path | None) -> Path:
    if value is None:
        raise FileNotFoundError("Nenhum caminho de entrada foi informado")
    raw = str(value).strip().strip('"').strip("'")
    if not raw:
        raise FileNotFoundError("Caminho de entrada vazio")
    return Path(raw).expanduser()


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
            ("#00f5d4", 8),
            ("#38bdf8", 8),
            ("#818cf8", 8),
            ("#c084fc", 8),
            ("#f472b6", 8),
            ("#f72585", 8),
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


class UpscaleScreen(App[None]):
    CSS_PATH = "tui.tcss"

    BINDINGS = [
        ("ctrl+c", "quit_app", "Sair"),
        ("ctrl+s", "start_processing", "Iniciar"),
        ("ctrl+p", "pause_processing", "Pausar"),
        ("ctrl+a", "toggle_audio", "Áudio"),
        ("ctrl+l", "clear_log", "Limpar"),
        ("f1", "show_help", "Ajuda"),
        ("ctrl+q", "quit_app", "Sair"),
        ("q", "quit_app", "Sair"),
    ]

    progress_value = reactive(0)
    audio_enabled = reactive(True)
    app_state = reactive("READY")
    selected_profile = reactive("clean")
    selected_level = reactive("medio")

    def __init__(self, input_path: Optional[str] = None) -> None:
        super().__init__()
        self.input_path = input_path or ""
        self.output_path = Path("output")
        self._last_ctrl_c = 0.0
        self._processing = False
        self._paused = False
        self._processing_started_at = 0.0
        self._monitor_timer = None
        self._cpu_history = [5, 8, 12, 18, 15, 25, 45, 30, 20, 15]
        self._gpu_history = [8, 12, 15, 22, 35, 50, 65, 70, 60, 55]
        if self.input_path:
            self.output_path = build_output_path(self.input_path, "clean", "medio")

    def _current_input_value(self) -> str:
        if not self.is_mounted:
            return self.input_path
        widget = self.query_one("#input-path", Input)
        value = widget.value.strip().strip('"').strip("'")
        if value:
            self.input_path = value
        try:
            widget = self.query_one("#input-path", Input)
            value = widget.value.strip().strip('"').strip("'")
            if value:
                self.input_path = value
        except Exception:
            pass
        return self.input_path

    def _default_output_path(self) -> Path:
        value = self._current_input_value()
        if not value:
            return Path("output")
        profile = self._selected_profile_name()
        level = self._selected_level_name()
        return build_output_path(value, profile, level)
        return build_output_path(value, self.selected_profile, self.selected_level)

    def _selected_profile_name(self) -> str:
        selector = self.query_one("#profile", Select) if self.is_mounted else None
        if selector is not None and selector.value:
            return str(selector.value)
        return "clean"

    def _selected_level_name(self) -> str:
        radio_set = self.query_one("#level-set", RadioSet) if self.is_mounted else None
        if radio_set is not None:
            pressed = getattr(radio_set, "pressed", None)
            if pressed is not None:
                return str(pressed.id).replace("level-", "")
        return "medio"

    def compose(self) -> ComposeResult:
        with Container(id="root"):
            with Horizontal(id="main"):
                with SettingsContainer(id="settings-panel"):
                    yield Input(value=self.input_path, placeholder="C:/videos/input.mp4", id="input-path")
                    yield Select(
                        [("clean", "clean"), ("detail", "detail"), ("fast", "fast"), ("anime", "anime")],
                        value="clean",
                        id="profile",
                    )
                    yield RadioSet(
                        RadioButton("baixo", value="baixo", id="level-baixo"),
                        RadioButton("medio", value="medio", id="level-medio"),
                        RadioButton("alto", value="alto", id="level-alto"),
                        RadioButton("max", value="max", id="level-max"),
                        id="level-set",
                    )
                    yield Button("✓ sem áudio X", id="audio-toggle")
                    yield Button("[>] Iniciar", id="primary-action", classes="primary")
            # Header Superior Limpo
            with Vertical(id="header-bar"):
                with Horizontal(id="header-title-row"):
                    yield Static("VidiScale  v1.0.0", id="app-brand")
                    yield Static("Status: v1.0.0", id="app-version-status")
                with Horizontal(id="header-cmd-row"):
                    yield Input(placeholder="Caminho do vídeo ou comando...", id="cmd-input")
                    yield GradientStatusBar(id="gradient-bar")
                    yield Button("Send", id="cmd-send", classes="send-btn")

            # Layout Principal em 2 Colunas
            with Horizontal(id="main-layout"):
                # Coluna Esquerda: Settings
                with Vertical(id="settings-panel"):
                    with Vertical(id="box-input", classes="fieldset-box"):
                        with Horizontal(classes="input-row"):
                            yield Input(value=self.input_path, placeholder="C:/videos/input.mp4", id="input-path")
                            yield Button("📁", id="browse-btn", classes="icon-btn")

                    with Vertical(id="box-profile", classes="fieldset-box"):
                        yield OptionList(
                            Option(Text("clean", style="#f8fafc"), id="opt-clean"),
                            Option(Text("compressed", style="#38bdf8"), id="opt-compressed"),
                            Option(Text("anime", style="#f472b6"), id="opt-anime"),
                            Option(Text("max", style="#fbbf24"), id="opt-max"),
                            id="profile-list",
                        )

                    with Vertical(id="box-level", classes="fieldset-box"):
                        yield RadioSet(
                            RadioButton("baixo", id="level-baixo"),
                            RadioButton("medio", value=True, id="level-medio"),
                            RadioButton("alto", id="level-alto"),
                            RadioButton("max", id="level-max"),
                            id="level-set",
                        )

                    yield Button("✓ sem áudio ✕", id="audio-toggle", classes="pill-audio")
                    yield Button("📁 iniciar", id="primary-action", classes="pill-start")

                # Coluna Direita: Status & Log + Performance Monitor
                with Vertical(id="right-column"):
                    with StatusLogPanel(id="status-log-panel"):
                    with Vertical(id="status-log-panel"):
                        yield Static("Status & Log", classes="panel-header-title")
                        yield Static("Processing Frame: 45% (2000/4500 frames)", id="status-display")
                        yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="progress")
                        yield RichLog(highlight=True, markup=True, auto_scroll=True, id="log")
                    with PerformancePanel(id="performance-panel"):
                        yield Static("Performance Monitor", classes="panel-title")
                        yield Horizontal(id="monitor")
                        yield Sparkline(data=[0, 2, 1, 3, 2, 5, 4, 6, 5, 8], id="cpu-sparkline")
                        yield Sparkline(data=[0, 1, 2, 1, 4, 3, 5, 4, 7, 6], id="gpu-sparkline")
                        yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="progress-bar")
                        yield ChevronPipeline(id="pipeline-chevrons")
                        yield Static("Processing output: ..", id="output-label")
                        with Vertical(id="log-container"):
                            yield NumberedLog(highlight=True, markup=True, auto_scroll=True, id="log")

                    with Vertical(id="performance-panel"):
                        yield Static("Performance Monitor", classes="panel-header-title")
                        with Horizontal(id="perf-split"):
                            with Vertical(id="cpu-col", classes="perf-col"):
                                yield Static("⏱ CPU: 0%", id="cpu-label", classes="perf-col-title")
                                yield Sparkline(data=self._cpu_history, id="cpu-sparkline")
                            with Vertical(id="gpu-col", classes="perf-col"):
                                yield Static("🎛 GPU: 0%", id="gpu-label", classes="perf-col-title")
                                yield Sparkline(data=self._gpu_history, id="gpu-sparkline")

            # Barra de Status e Rodapé
            with Horizontal(id="stats-strip"):
                yield Static("Memória Usada: 10MB | Tempo Decorrido: 00:00:00", classes="metric")
                yield Static("READY", classes="state-chip", id="state-chip")
                yield Static("Memory Usage: [cyan]10MB[/cyan] | Elapsed Time: [white]00:00:00[/white]", id="memory-metric")
                yield Static("App State: ", id="state-label")
                yield Static("READY", id="badge-ready", classes="state-badge active")
                yield Static("PROCESSING", id="badge-processing", classes="state-badge")
                yield Static("COMPLETE", id="badge-complete", classes="state-badge")

        yield Footer()
            with Horizontal(id="custom-footer"):
                yield Static("[#f72585]^s[/] Iniciar   [#f72585]^p[/] Pausar   [#f72585]^a[/] Áudio   [#f72585]^l[/] Limpar   [#f72585]f1[/] Ajuda   [#f72585]^q[/] Sair", id="footer-keys")

    def on_mount(self) -> None:
        self.query_one("#progress", ProgressBar).update(progress=0)
        log = self.query_one("#log", RichLog)
        self.query_one("#settings-panel").border_title = "Settings"
        self.query_one("#box-input").border_title = "arquivo de entrada"
        self.query_one("#box-profile").border_title = "perfil:"
        self.query_one("#box-level").border_title = "Nível:"
        self.query_one("#status-log-panel").border_title = "Status & Log"
        self.query_one("#performance-panel").border_title = "Performance Monitor"

        self.query_one("#progress-bar", ProgressBar).update(progress=0)
        log = self.query_one("#log", NumberedLog)
        self.output_path = self._default_output_path()
        log.write("[grey]07:23:03[/grey] [INFO] sistema inicializado.")
        log.write(f"[grey]07:23:04[/grey] [INFO] saída padrão: {self.output_path}")
        log.write("[grey]07:23:04[/grey] [WARN] aguardando entrada do usuário.")
        self._sync_state_chip()
        log.append_entry("INFO", "Sistema VidiScale inicializado.")
        log.append_entry("INFO", f"Saída padrão configurada: {self.output_path}")
        log.append_entry("WARN", "Aguardando definição de vídeo de entrada.")
        self._sync_state_badges()
        self._refresh_monitor()

    def _sync_state_chip(self) -> None:
        chip = self.query_one("#state-chip", Static)
        chip.remove_class("busy", "error", "idle")
    def _sync_state_badges(self) -> None:
        b_ready = self.query_one("#badge-ready", Static)
        b_proc = self.query_one("#badge-processing", Static)
        b_comp = self.query_one("#badge-complete", Static)

        b_ready.remove_class("active")
        b_proc.remove_class("active")
        b_comp.remove_class("active")

        if self.app_state == "PROCESSING":
            chip.add_class("busy")
            b_proc.add_class("active")
            chevrons = self.query_one("#pipeline-chevrons", ChevronPipeline)
            chevrons.stage = 2
        elif self.app_state == "COMPLETE":
            chip.add_class("idle")
            b_comp.add_class("active")
            chevrons = self.query_one("#pipeline-chevrons", ChevronPipeline)
            chevrons.stage = 4
        else:
            chip.add_class("idle")
        chip.update(self.app_state)
            b_ready.add_class("active")
            chevrons = self.query_one("#pipeline-chevrons", ChevronPipeline)
            chevrons.stage = 0

    def watch_audio_enabled(self, value: bool) -> None:
        button = self.query_one("#audio-toggle", Button)
        if not self.is_mounted:
            return
        btn = self.query_one("#audio-toggle", Button)
        if value:
            button.remove_class("inactive")
            button.label = "✓ sem áudio X"
            btn.remove_class("inactive")
            btn.label = "✓ sem áudio ✕"
        else:
            button.add_class("inactive")
            button.label = "✗ com áudio"
            btn.add_class("inactive")
            btn.label = "✕ com áudio ✓"

    def _render_progress_bar_text(self, progress: int, current_frame: int = 0, total_frames: int = 4500) -> str:
        bar_len = 16
        filled = int(bar_len * (progress / 100))
        arrow_count = min(4, filled)
        eq_count = filled - arrow_count
        dash_count = bar_len - filled
        bar_str = "=" * eq_count + ">" * arrow_count + "-" * dash_count
        return f"Processing Frame: [{bar_str}] {progress}% ({current_frame}/{total_frames} frames)"

    def watch_progress_value(self, value: int) -> None:
        if not self.is_mounted:
            return
        self.query_one("#progress-bar", ProgressBar).update(progress=value)
        status = self.query_one("#status-display", Static)
        status.update(self._render_progress_bar_text(value, int(value * 45), 4500))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "audio-toggle":
            self.audio_enabled = not self.audio_enabled
        elif event.button.id == "primary-action":
        btn_id = event.button.id
        if btn_id == "audio-toggle":
            self.action_toggle_audio()
        elif btn_id == "primary-action":
            self.action_start_processing()
        elif btn_id == "cmd-send":
            self._handle_cmd_send()
        elif btn_id == "browse-btn":
            self.query_one("#input-path", Input).focus()
            self.notify("Digite ou cole o caminho do arquivo de vídeo.")

    @staticmethod
    def _extract_backend_progress(message: str) -> int | None:
        match = re.search(r"(\d{1,3})\s*%", message)
        if not match:
            return None
        value = int(match.group(1))
        return max(0, min(100, value))
    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = event.option.id
        if opt_id:
            profile_name = opt_id.replace("opt-", "")
            self.selected_profile = profile_name
            log = self.query_one("#log", NumberedLog)
            log.append_entry("INFO", f"Perfil alterado para: {profile_name}")

    def _read_machine_metrics(self) -> tuple[float | None, float | None]:
        if psutil is None:
            return None, None
        try:
            cpu_percent = float(psutil.cpu_percent(interval=None))
            memory_percent = float(psutil.virtual_memory().percent)
            return cpu_percent, memory_percent
        except Exception:
            return None, None
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.pressed and event.pressed.id:
            level_name = event.pressed.id.replace("level-", "")
            self.selected_level = level_name
            log = self.query_one("#log", NumberedLog)
            log.append_entry("INFO", f"Nível de qualidade: {level_name}")

    def _handle_cmd_send(self) -> None:
        cmd_input = self.query_one("#cmd-input", Input)
        val = cmd_input.value.strip()
        cmd_input.value = ""
        if not val:
            return

        lowered = val.lower()
        if lowered in ("start", "iniciar"):
            self.action_start_processing()
        elif lowered in ("pause", "pausar"):
            self.action_pause_processing()
        elif lowered in ("audio", "som"):
            self.action_toggle_audio()
        elif lowered in ("clean", "compressed", "anime", "max"):
            self.selected_profile = lowered
            self.notify(f"Perfil: {lowered}")
        elif Path(val).exists() or "/" in val or "\\" in val:
            self.input_path = val
            self.query_one("#input-path", Input).value = val
            self.notify(f"Arquivo definido: {Path(val).name}")
        else:
            self.query_one("#log", NumberedLog).append_entry("INFO", f"Comando recebido: {val}")

    def _read_machine_metrics(self) -> tuple[float | None, float | None, float | None]:
        cpu_percent = None
        memory_mb = None
        gpu_percent = None

        if psutil is not None:
            try:
                cpu_percent = float(psutil.cpu_percent(interval=None))
                process = psutil.Process()
                memory_mb = process.memory_info().rss / (1024 * 1024)
            except Exception:
                pass

        if torch is not None and torch.cuda.is_available():
            try:
                allocated = torch.cuda.memory_allocated()
                reserved = torch.cuda.memory_reserved()
                if reserved > 0:
                    gpu_percent = min(100.0, (allocated / reserved) * 100.0)
                else:
                    gpu_percent = 0.0
            except Exception:
                pass

        return cpu_percent, memory_mb, gpu_percent

    def _format_elapsed(self, seconds: float) -> str:
        total = int(seconds)
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _refresh_monitor(self) -> None:
        if not self.is_mounted:
            return

        elapsed = 0.0
        if self._processing_started_at:
            elapsed = time.monotonic() - self._processing_started_at
        cpu_percent, memory_percent = self._read_machine_metrics()
        cpu_text = "N/D" if cpu_percent is None else f"{cpu_percent:.0f}%"
        memory_text = "N/D" if memory_percent is None else f"{memory_percent:.0f}%"
        stats = self.query_one("#stats-strip", Horizontal)
        stats.query_one(".metric", Static).update(
            f"CPU: {cpu_text} | RAM: {memory_text} | Tempo: {self._format_elapsed(elapsed)}"

        cpu_percent, memory_mb, gpu_percent = self._read_machine_metrics()
        cpu_val = 0 if cpu_percent is None else int(cpu_percent)
        gpu_val = 0 if gpu_percent is None else int(gpu_percent)

        self._cpu_history.append(cpu_val)
        if len(self._cpu_history) > 20:
            self._cpu_history.pop(0)

        self._gpu_history.append(gpu_val if gpu_percent is not None else (cpu_val // 2))
        if len(self._gpu_history) > 20:
            self._gpu_history.pop(0)

        self.query_one("#cpu-sparkline", Sparkline).data = list(self._cpu_history)
        self.query_one("#gpu-sparkline", Sparkline).data = list(self._gpu_history)
        self.query_one("#cpu-label", Static).update(f"⏱ CPU: {cpu_val}%")
        self.query_one("#gpu-label", Static).update(f"🎛 GPU: {gpu_val}%")

        mem_text = f"{memory_mb:.0f}MB" if memory_mb is not None else "10MB"
        self.query_one("#memory-metric", Static).update(
            f"Memory Usage: [cyan]{mem_text}[/cyan] | Elapsed Time: [white]{self._format_elapsed(elapsed)}[/white]"
        )

        if self._processing and self._processing_started_at:
            progress = self.progress_value or 0
            self.query_one("#progress", ProgressBar).update(progress=progress)
            self.query_one("#status-display", Static).update(
                f"Processing Frame: {progress}% | Elapsed: {self._format_elapsed(elapsed)}"
            )

    def _handle_backend_output(self, message: str) -> None:
        if not message:
            return
        progress = self._extract_backend_progress(message)
        if progress is not None:
            self.progress_value = progress
            self.query_one("#progress", ProgressBar).update(progress=progress)
            self.query_one("#status-display", Static).update(
                f"Processing Frame: {progress}% | Elapsed: {self._format_elapsed(time.monotonic() - self._processing_started_at)}"
            )
        match = re.search(r"(\d{1,3})\s*%", message)
        if match:
            val = max(0, min(100, int(match.group(1))))
            self.progress_value = val

        lowered = message.lower()
        if any(token in lowered for token in ("inference", "processing", "frame", "tile", "fps", "video")):
            self._append_log(f"[grey]{time.strftime('%H:%M:%S')}[/grey] [INFO] {message}")
            self.query_one("#log", NumberedLog).append_entry("INFO", message)

    def action_start_processing(self) -> None:
        self.output_path = self._default_output_path()
        self._append_log(f"[cyan][INFO][/cyan] saída: {self.output_path}")
        log = self.query_one("#log", NumberedLog)
        log.append_entry("INFO", f"Iniciando processamento. Saída: {self.output_path.name}")
        self._processing = True
        self._paused = False
        self._processing_started_at = time.monotonic()
        self.app_state = "PROCESSING"
        self._sync_state_chip()
        self._sync_state_badges()
        self._monitor_timer = self.set_interval(0.5, self._refresh_monitor)
        self.run_worker(self._run_real_processing, thread=True, exclusive=True)

    def _run_real_processing(self) -> None:
        try:
            source = resolve_input_path(self._current_input_value())
            source = source.expanduser().resolve()
            if not source.exists():
                raise FileNotFoundError(f"Arquivo de entrada não encontrado: {source}")

            metadata = inspect_video(source, None)
            selected_profile = self._selected_profile_name()
            selected_level = self._selected_level_name()
            target_long_edge = SIMPLE_LEVELS.get(selected_level, SIMPLE_LEVELS["medio"])
            target_long_edge = SIMPLE_LEVELS.get(self.selected_level, SIMPLE_LEVELS["medio"])
            source_long_edge = max(metadata.width, metadata.height)
            outscale = max(1.0, min(4.0, target_long_edge / source_long_edge))

            options = UpscaleOptions(
                input_path=source,
                output_path=self.output_path,
                profile=selected_profile,
                profile=self.selected_profile,
                outscale=outscale,
                tile=256,
                tile_pad=10,
                auto_tile=True,
                allow_vfr=False,
                ffmpeg_bin=resolve_binary("ffmpeg"),
                ffprobe_bin=resolve_binary("ffprobe"),
                python_executable=sys.executable,
                crf=17,
                preset="slow",
                audio_bitrate="192k",
                audio_enabled=self.audio_enabled,
                progress_callback=self._handle_backend_output,
            )

            self.call_from_thread(self._append_log, f"[cyan][INFO][/cyan] processando com perfil {selected_profile} ({selected_level})")
            self.call_from_thread(self.query_one("#log", NumberedLog).append_entry, "INFO", f"Perfil: {self.selected_profile} ({self.selected_level})")
            result = upscale(options)
            self.call_from_thread(self._append_log, f"[green][INFO][/green] processamento concluído: {result.output_path}")
            self.call_from_thread(self.query_one("#log", NumberedLog).append_entry, "INFO", f"Concluído com sucesso: {result.output_path.name}")
            self.call_from_thread(self._mark_complete, result.output_path)
        except Exception as exc:  # pragma: no cover - UI feedback path
        except Exception as exc:  # pragma: no cover
            self.call_from_thread(self._mark_error, str(exc))

    def _mark_complete(self, output: Path) -> None:
        self._processing = False
        self.app_state = "COMPLETE"
        self._sync_state_chip()
        self.query_one("#progress", ProgressBar).update(progress=100)
        self.query_one("#status-display", Static).update(f"Processing Frame: 100% | Arquivo: {output.name}")
        self._sync_state_badges()
        self.progress_value = 100
        self.query_one("#status-display", Static).update(f"Processing Frame: 100% | Concluído: {output.name}")
        if self._monitor_timer is not None:
            self._monitor_timer.stop()
            self._monitor_timer = None

    def _mark_error(self, message: str) -> None:
        self._processing = False
        self.app_state = "ERROR"
        self._sync_state_chip()
        self._append_log(f"[red][ERROR][/red] {message}")
        self._sync_state_badges()
        self.query_one("#log", NumberedLog).append_entry("ERROR", message)
        if self._monitor_timer is not None:
            self._monitor_timer.stop()
            self._monitor_timer = None

    def _append_log(self, message: str) -> None:
        if self.is_mounted:
            self.query_one("#log", RichLog).write(message)

    def _update_progress(self, value: int) -> None:
        self.progress_value = value
        self.query_one("#progress", ProgressBar).update(progress=value)
        self.query_one("#status-display", Static).update(f"Processing Frame: {value}% | Elapsed: {self._format_elapsed(time.monotonic() - self._processing_started_at)}")
        if value % 25 == 0:
            self._append_log(f"[grey]{time.strftime('%H:%M:%S')}[/grey] [INFO] frame {value}% concluído.")

    def action_pause_processing(self) -> None:
        if self._processing:
            self._paused = not self._paused
            self._append_log("[yellow][WARN][/yellow] processamento pausado." if self._paused else "[green][INFO][/green] processamento retomado.")
            log = self.query_one("#log", NumberedLog)
            msg = "Processamento pausado." if self._paused else "Processamento retomado."
            lvl = "WARN" if self._paused else "INFO"
            log.append_entry(lvl, msg)

    def action_toggle_audio(self) -> None:
        self.audio_enabled = not self.audio_enabled

    def action_clear_log(self) -> None:
        log = self.query_one("#log", NumberedLog)
        log.clear()
        log.line_number = 0
        log.append_entry("INFO", "Log limpo pelo usuário.")

    def action_show_help(self) -> None:
        self._append_log("[cyan][INFO][/cyan] atalhos: Ctrl+S iniciar, Ctrl+P pausar, Ctrl+C sair.")
        log = self.query_one("#log", NumberedLog)
        log.append_entry("INFO", "Atalhos: ^s Iniciar | ^p Pausar | ^a Áudio | ^l Limpar | ^q Sair")

    def action_quit_app(self) -> None:
        now = time.monotonic()
        if self._last_ctrl_c and (now - self._last_ctrl_c) <= 1.5:
            self.exit()
            return
        self._last_ctrl_c = now
        self.notify("Pressione Ctrl+C novamente para fechar", timeout=1.5)
        self.notify("Pressione Ctrl+Q novamente para sair", timeout=1.5)


def launch_tui(input_path: str | None = None) -> int:
    app = UpscaleScreen(input_path=input_path)
    app.run()
    return 0
