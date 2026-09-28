from __future__ import annotations

from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Input, Label, ProgressBar, Select


class UpscaleScreen(App[None]):
    CSS = """
    Screen {
        background: #0b1020;
        color: white;
    }

    Container {
        padding: 1 2;
    }

    #controls {
        width: 100%;
        height: auto;
    }

    Input, Select, Button {
        margin-top: 1;
    }

    .status {
        color: #8ad4ff;
        margin-top: 1;
    }

    .value {
        color: #d9f99d;
        margin-top: 1;
    }
    """

    current_step = reactive("pronto")
    progress = reactive(0.0)

    def __init__(self, input_path: Optional[str] = None) -> None:
        super().__init__()
        self.input_path = input_path

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container():
            yield Label("Upscale Video", classes="title")
            yield Input(value=self.input_path or "", placeholder="Arquivo de entrada (.mp4)", id="input")
            yield Select(
                [
                    ("clean", "clean"),
                    ("max", "max"),
                    ("compressed", "compressed"),
                    ("anime", "anime"),
                ],
                value="clean",
                id="profile",
            )
            yield Select(
                [
                    ("baixo", "baixo"),
                    ("medio", "medio"),
                    ("alto", "alto"),
                    ("max", "max"),
                ],
                value="medio",
                id="nivel",
            )
            yield Horizontal(
                Button("Iniciar", id="start", variant="primary"),
                Button("Fechar", id="quit"),
            )
            yield Label("Status: pronto", classes="status", id="status")
            yield ProgressBar(total=100, show_eta=False, show_percentage=True, id="progress")
            yield Label("0%", classes="value", id="progress_text")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#progress", ProgressBar).update(progress=0)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.exit()
        elif event.button.id == "start":
            self.current_step = "processando"
            self.progress = 0.0
            self._update_status("Processando vídeo...")
            for value in range(0, 101, 10):
                self.progress = float(value)
                self.query_one("#progress", ProgressBar).update(progress=value)
                self.query_one("#progress_text", Label).update(f"{value}%")
                if value < 100:
                    self._update_status(f"Processando... {value}%")
            self._update_status("Concluído")

    def _update_status(self, text: str) -> None:
        self.query_one("#status", Label).update(f"Status: {text}")


def launch_tui(input_path: str | None = None) -> int:
    app = UpscaleScreen(input_path=input_path)
    app.run()
    return 0
