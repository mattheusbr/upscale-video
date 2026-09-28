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

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Input, ProgressBar, RadioButton, RadioSet, RichLog, Select, Sparkline, Static

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


class UpscaleScreen(App[None]):
    CSS_PATH = "tui.tcss"

    BINDINGS = [
        ("ctrl+c", "quit_app", "Sair"),
        ("ctrl+s", "start_processing", "Iniciar"),
        ("ctrl+p", "pause_processing", "Pausar"),
        ("f1", "show_help", "Ajuda"),
        ("q", "quit_app", "Sair"),
    ]

    progress_value = reactive(0)
    audio_enabled = reactive(True)
    app_state = reactive("READY")

    def __init__(self, input_path: Optional[str] = None) -> None:
        super().__init__()
        self.input_path = input_path or ""
        self.output_path = Path("output")
        self._last_ctrl_c = 0.0
        self._processing = False
        self._paused = False
        self._processing_started_at = 0.0
        self._monitor_timer = None
        if self.input_path:
            self.output_path = build_output_path(self.input_path, "clean", "medio")

    def _current_input_value(self) -> str:
        if not self.is_mounted:
            return self.input_path
        widget = self.query_one("#input-path", Input)
        value = widget.value.strip().strip('"').strip("'")
        if value:
            self.input_path = value
        return self.input_path

    def _default_output_path(self) -> Path:
        value = self._current_input_value()
        if not value:
            return Path("output")
        profile = self._selected_profile_name()
        level = self._selected_level_name()
        return build_output_path(value, profile, level)

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

                with Vertical(id="right-column"):
                    with StatusLogPanel(id="status-log-panel"):
                        yield Static("Processing Frame: 45% (2000/4500 frames)", id="status-display")
                        yield ProgressBar(total=100, show_eta=False, show_percentage=False, id="progress")
                        yield RichLog(highlight=True, markup=True, auto_scroll=True, id="log")
                    with PerformancePanel(id="performance-panel"):
                        yield Static("Performance Monitor", classes="panel-title")
                        yield Horizontal(id="monitor")
                        yield Sparkline(data=[0, 2, 1, 3, 2, 5, 4, 6, 5, 8], id="cpu-sparkline")
                        yield Sparkline(data=[0, 1, 2, 1, 4, 3, 5, 4, 7, 6], id="gpu-sparkline")

            with Horizontal(id="stats-strip"):
                yield Static("Memória Usada: 10MB | Tempo Decorrido: 00:00:00", classes="metric")
                yield Static("READY", classes="state-chip", id="state-chip")

        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#progress", ProgressBar).update(progress=0)
        log = self.query_one("#log", RichLog)
        self.output_path = self._default_output_path()
        log.write("[grey]07:23:03[/grey] [INFO] sistema inicializado.")
        log.write(f"[grey]07:23:04[/grey] [INFO] saída padrão: {self.output_path}")
        log.write("[grey]07:23:04[/grey] [WARN] aguardando entrada do usuário.")
        self._sync_state_chip()
        self._refresh_monitor()

    def _sync_state_chip(self) -> None:
        chip = self.query_one("#state-chip", Static)
        chip.remove_class("busy", "error", "idle")
        if self.app_state == "PROCESSING":
            chip.add_class("busy")
        elif self.app_state == "COMPLETE":
            chip.add_class("idle")
        else:
            chip.add_class("idle")
        chip.update(self.app_state)

    def watch_audio_enabled(self, value: bool) -> None:
        button = self.query_one("#audio-toggle", Button)
        if value:
            button.remove_class("inactive")
            button.label = "✓ sem áudio X"
        else:
            button.add_class("inactive")
            button.label = "✗ com áudio"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "audio-toggle":
            self.audio_enabled = not self.audio_enabled
        elif event.button.id == "primary-action":
            self.action_start_processing()

    @staticmethod
    def _extract_backend_progress(message: str) -> int | None:
        match = re.search(r"(\d{1,3})\s*%", message)
        if not match:
            return None
        value = int(match.group(1))
        return max(0, min(100, value))

    def _read_machine_metrics(self) -> tuple[float | None, float | None]:
        if psutil is None:
            return None, None
        try:
            cpu_percent = float(psutil.cpu_percent(interval=None))
            memory_percent = float(psutil.virtual_memory().percent)
            return cpu_percent, memory_percent
        except Exception:
            return None, None

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

        lowered = message.lower()
        if any(token in lowered for token in ("inference", "processing", "frame", "tile", "fps", "video")):
            self._append_log(f"[grey]{time.strftime('%H:%M:%S')}[/grey] [INFO] {message}")

    def action_start_processing(self) -> None:
        self.output_path = self._default_output_path()
        self._append_log(f"[cyan][INFO][/cyan] saída: {self.output_path}")
        self._processing = True
        self._paused = False
        self._processing_started_at = time.monotonic()
        self.app_state = "PROCESSING"
        self._sync_state_chip()
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
            source_long_edge = max(metadata.width, metadata.height)
            outscale = max(1.0, min(4.0, target_long_edge / source_long_edge))

            options = UpscaleOptions(
                input_path=source,
                output_path=self.output_path,
                profile=selected_profile,
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
            result = upscale(options)
            self.call_from_thread(self._append_log, f"[green][INFO][/green] processamento concluído: {result.output_path}")
            self.call_from_thread(self._mark_complete, result.output_path)
        except Exception as exc:  # pragma: no cover - UI feedback path
            self.call_from_thread(self._mark_error, str(exc))

    def _mark_complete(self, output: Path) -> None:
        self._processing = False
        self.app_state = "COMPLETE"
        self._sync_state_chip()
        self.query_one("#progress", ProgressBar).update(progress=100)
        self.query_one("#status-display", Static).update(f"Processing Frame: 100% | Arquivo: {output.name}")
        if self._monitor_timer is not None:
            self._monitor_timer.stop()
            self._monitor_timer = None

    def _mark_error(self, message: str) -> None:
        self._processing = False
        self.app_state = "ERROR"
        self._sync_state_chip()
        self._append_log(f"[red][ERROR][/red] {message}")
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

    def action_show_help(self) -> None:
        self._append_log("[cyan][INFO][/cyan] atalhos: Ctrl+S iniciar, Ctrl+P pausar, Ctrl+C sair.")

    def action_quit_app(self) -> None:
        now = time.monotonic()
        if self._last_ctrl_c and (now - self._last_ctrl_c) <= 1.5:
            self.exit()
            return
        self._last_ctrl_c = now
        self.notify("Pressione Ctrl+C novamente para fechar", timeout=1.5)


def launch_tui(input_path: str | None = None) -> int:
    app = UpscaleScreen(input_path=input_path)
    app.run()
    return 0
