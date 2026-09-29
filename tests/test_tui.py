from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from rich.text import Text
from textual.widgets import Button, Input, OptionList, ProgressBar, RadioSet, Sparkline, Static

from upscaler.tui import (
    ChevronPipeline,
    FileBrowserModal,
    NumberedLog,
    UpscaleScreen,
    build_output_path,
    resolve_input_path,
)


class TestTuiHelpers(unittest.TestCase):
    def test_build_output_path(self) -> None:
        path = build_output_path("video.mp4", "clean", "medio")
        self.assertEqual(path.name, "clean_medio_video.mp4")

    def test_build_output_path_invalid(self) -> None:
        with self.assertRaises(ValueError):
            build_output_path("", "clean", "medio")

    def test_resolve_input_path(self) -> None:
        path = resolve_input_path("C:/videos/test.mp4")
        self.assertTrue(isinstance(path, Path))

    def test_resolve_input_path_empty(self) -> None:
        with self.assertRaises(FileNotFoundError):
            resolve_input_path("")
        with self.assertRaises(FileNotFoundError):
            resolve_input_path(None)

    def test_version_matches_pyproject(self) -> None:
        import tomllib
        import upscaler

        pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with open(pyproject, "rb") as f:
            cfg = tomllib.load(f)
        self.assertEqual(upscaler.__version__, cfg["project"]["version"])



class TestTuiScreenAsync(unittest.IsolatedAsyncioTestCase):
    async def test_tui_composition_and_mounting(self) -> None:
        app = UpscaleScreen()
        async with app.run_test(size=(120, 36)) as pilot:
            self.assertTrue(app.is_mounted)

            # Contêineres e títulos
            settings = app.query_one("#settings-panel")
            status_panel = app.query_one("#status-log-panel")
            perf_panel = app.query_one("#performance-panel")
            self.assertEqual(settings.border_title, "Settings")
            self.assertEqual(status_panel.border_title, "Status & Log")
            self.assertEqual(perf_panel.border_title, "Performance Monitor")

            # Widgets essenciais
            self.assertIsNotNone(app.query_one("#input-path", Input))
            self.assertIsNotNone(app.query_one("#browse-btn", Button))
            self.assertIsNotNone(app.query_one("#profile-list", OptionList))
            self.assertIsNotNone(app.query_one("#level-set", RadioSet))
            self.assertIsNotNone(app.query_one("#audio-toggle", Button))
            self.assertIsNotNone(app.query_one("#start-btn", Button))
            self.assertIsNotNone(app.query_one("#pipeline-chevrons", ChevronPipeline))
            self.assertIsNotNone(app.query_one("#log", NumberedLog))
            self.assertIsNotNone(app.query_one("#cpu-sparkline", Sparkline))
            self.assertIsNotNone(app.query_one("#gpu-sparkline", Sparkline))
            self.assertIsNotNone(app.query_one("#status-display", Static))

    async def test_input_path_sync(self) -> None:
        app = UpscaleScreen(input_path="input/test.mp4")
        async with app.run_test(size=(120, 36)) as pilot:
            input_widget = app.query_one("#input-path", Input)
            self.assertEqual(input_widget.value, "input/test.mp4")
            self.assertIn("clean_medio_test.mp4", str(app._default_output_path()))

            input_widget.value = "another/video.mkv"
            self.assertEqual(app._current_input_value(), "another/video.mkv")
            self.assertIn("clean_medio_video.mkv", str(app._default_output_path()))

    async def test_audio_toggle_action(self) -> None:
        app = UpscaleScreen()
        async with app.run_test(size=(120, 36)) as pilot:
            btn = app.query_one("#audio-toggle", Button)
            self.assertTrue(app.audio_enabled)
            self.assertIn("sem", str(btn.label).lower())

            # Clica no botão de áudio
            await pilot.click("#audio-toggle")
            await pilot.pause()
            self.assertFalse(app.audio_enabled)
            self.assertIn("com", str(btn.label).lower())

            # Clica novamente
            await pilot.click("#audio-toggle")
            await pilot.pause()
            self.assertTrue(app.audio_enabled)
            self.assertIn("sem", str(btn.label).lower())

    async def test_dynamic_action_buttons(self) -> None:
        app = UpscaleScreen(input_path="input/sample.mp4")
        with patch.object(app, "_process_video", return_value=None) as worker:
            async with app.run_test(size=(120, 36)) as pilot:
                start_btn = app.query_one("#start-btn", Button)
                pause_btn = app.query_one("#pause-btn", Button)
                stop_btn = app.query_one("#stop-btn", Button)

                # Inicialmente: apenas o botão [>] Iniciar visível
                self.assertTrue(start_btn.display)
                self.assertFalse(pause_btn.display)
                self.assertFalse(stop_btn.display)

                # Clica em Iniciar -> deve iniciar o worker de processamento
                await pilot.click("#start-btn")
                await pilot.pause()
                self.assertTrue(app._processing)
                self.assertEqual(app.app_state, "PROCESSING")
                worker.assert_called_once()

                # Agora deve ter botões Pausar e Parar visíveis
                self.assertFalse(start_btn.display)
                self.assertTrue(pause_btn.display)
                self.assertTrue(stop_btn.display)
                self.assertIn("Pausar", str(pause_btn.label))

                # Clica em Pausar -> deve mudar label para Retomar
                await pilot.click("#pause-btn")
                await pilot.pause()
                self.assertTrue(app._paused)
                self.assertIn("Retomar", str(pause_btn.label))

                # Clica em Parar -> solicita o cancelamento e volta a READY
                await pilot.click("#stop-btn")
                await pilot.pause()
                self.assertFalse(app._processing)
                self.assertEqual(app.app_state, "READY")
                self.assertTrue(start_btn.display)
                self.assertFalse(pause_btn.display)
                self.assertFalse(stop_btn.display)

    async def test_start_processing_runs_upscale(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "input.mp4"
            source.touch()
            expected_output = Path(tmpdir) / "clean_medio_input.mp4"
            app = UpscaleScreen(input_path=str(source))
            fake_result = SimpleNamespace(output_path=expected_output)
            with (
                patch("upscaler.ui.app.inspect_video", return_value=SimpleNamespace(width=1280, height=720)),
                patch("upscaler.ui.app.upscale", return_value=fake_result) as run_upscale,
            ):
                async with app.run_test(size=(120, 36)) as pilot:
                    await pilot.click("#start-btn")
                    for _ in range(20):
                        if app.app_state == "COMPLETE":
                            break
                        await pilot.pause(0.05)
                    self.assertEqual(app.app_state, "COMPLETE")
                    run_upscale.assert_called_once()
                    options = run_upscale.call_args.args[0]
                    self.assertEqual(options.outscale, 1.5)
                    self.assertFalse(options.audio_enabled)

    async def test_bracket_progress_bar_render(self) -> None:
        app = UpscaleScreen()
        rendered = app._render_bracket_progress_bar(51.2, 2295, 4500, 418)
        self.assertIn("Processing Frame: [", rendered)
        self.assertIn("51.2%", rendered)
        self.assertIn("2295/4500", rendered)
        self.assertIn("ETA:", rendered)
        self.assertIn(">>>", rendered)

    async def test_file_browser_modal_init(self) -> None:
        modal = FileBrowserModal()
        self.assertIsNotNone(modal.current_dir)

    async def test_numbered_log_formatting(self) -> None:
        app = UpscaleScreen()
        async with app.run_test(size=(120, 36)) as pilot:
            log = app.query_one("#log", NumberedLog)
            initial_count = log.line_number
            self.assertGreaterEqual(initial_count, 3)

            log.append_entry("INFO", "Teste mensagem informativa")
            self.assertEqual(log.line_number, initial_count + 1)

            log.append_entry("WARN", "Teste aviso")
            self.assertEqual(log.line_number, initial_count + 2)

            log.append_entry("ERROR", "Teste erro crítico")
            self.assertEqual(log.line_number, initial_count + 3)

            # Testa limpeza de log
            app.action_clear_log()
            self.assertEqual(log.line_number, 1)

    async def test_state_badge_transitions(self) -> None:
        app = UpscaleScreen()
        async with app.run_test(size=(120, 36)) as pilot:
            b_ready = app.query_one("#badge-ready", Static)
            b_proc = app.query_one("#badge-processing", Static)
            b_comp = app.query_one("#badge-complete", Static)
            chevrons = app.query_one("#pipeline-chevrons", ChevronPipeline)

            # Inicialmente READY
            self.assertIn("active", b_ready.classes)
            self.assertNotIn("active", b_proc.classes)
            self.assertEqual(chevrons.stage, 0)

            # Transição para PROCESSING
            app.app_state = "PROCESSING"
            app._sync_state_badges()
            self.assertNotIn("active", b_ready.classes)
            self.assertIn("active", b_proc.classes)
            self.assertEqual(chevrons.stage, 2)

            # Transição para COMPLETE
            app.app_state = "COMPLETE"
            app._sync_state_badges()
            self.assertNotIn("active", b_proc.classes)
            self.assertIn("active", b_comp.classes)
            self.assertEqual(chevrons.stage, 4)

    async def test_visual_screenshot_capture(self) -> None:
        app = UpscaleScreen(input_path=r"C:\videos\Memória_dos_Hackers.mp4")
        async with app.run_test(size=(120, 36)) as pilot:
            with tempfile.TemporaryDirectory() as tmpdir:
                svg_path = Path(tmpdir) / "test_capture.svg"
                app.save_screenshot(filename=str(svg_path.name), path=str(tmpdir))
                self.assertTrue(svg_path.exists())
                content = svg_path.read_text(encoding="utf-8")
                self.assertIn("<svg", content)
                self.assertIn("VidiScale", content)
                self.assertIn("Settings", content)
                self.assertIn("Log", content)
                self.assertIn("Monitor", content)

                # Exporta para assets/screenshots
                assets_dir = Path("assets/screenshots")
                assets_dir.mkdir(parents=True, exist_ok=True)
                svg_dest = assets_dir / "tui_screenshot.svg"
                svg_dest.write_text(content, encoding="utf-8")
                png_path = assets_dir / "tui_screenshot.png"
                try:
                    import resvg_py
                    png_bytes = resvg_py.svg_to_bytes(content)
                    png_path.write_bytes(png_bytes)
                    print(f"\n[TEST PRINT] Screenshot READY salvo em: {png_path.resolve()} e {svg_dest.resolve()}")
                except ImportError:
                    pass

        # Captura screenshot em estado de PROCESSING
        app_proc = UpscaleScreen(input_path=r"...\Memória_dos_Hackers.mp4")
        app_proc._process_video = lambda *args: None
        async with app_proc.run_test(size=(120, 36)) as pilot:
            await pilot.click("#start-btn")
            await pilot.pause()
            app_proc.progress_value = 51
            with tempfile.TemporaryDirectory() as tmpdir:
                svg_path = Path(tmpdir) / "proc_capture.svg"
                app_proc.save_screenshot(filename=str(svg_path.name), path=str(tmpdir))
                content = svg_path.read_text(encoding="utf-8")
                assets_dir = Path("assets/screenshots")
                svg_proc_dest = assets_dir / "tui_processing.svg"
                svg_proc_dest.write_text(content, encoding="utf-8")
                png_path = assets_dir / "tui_processing.png"
                try:
                    import resvg_py
                    png_bytes = resvg_py.svg_to_bytes(content)
                    png_path.write_bytes(png_bytes)
                    print(f"\n[TEST PRINT] Screenshot PROCESSING salvo em: {png_path.resolve()} e {svg_proc_dest.resolve()}")
                except ImportError:
                    pass


if __name__ == "__main__":
    unittest.main()
