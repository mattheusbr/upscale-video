from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from textual.widgets import Button, Input, OptionList, ProgressBar, RadioSet, Sparkline, Static

from upscaler.tui import ChevronPipeline, NumberedLog, UpscaleScreen, build_output_path, resolve_input_path


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
            self.assertIsNotNone(app.query_one("#profile-list", OptionList))
            self.assertIsNotNone(app.query_one("#level-set", RadioSet))
            self.assertIsNotNone(app.query_one("#audio-toggle", Button))
            self.assertIsNotNone(app.query_one("#primary-action", Button))
            self.assertIsNotNone(app.query_one("#progress-bar", ProgressBar))
            self.assertIsNotNone(app.query_one("#pipeline-chevrons", ChevronPipeline))
            self.assertIsNotNone(app.query_one("#log", NumberedLog))
            self.assertIsNotNone(app.query_one("#cpu-sparkline", Sparkline))
            self.assertIsNotNone(app.query_one("#gpu-sparkline", Sparkline))
            self.assertIsNotNone(app.query_one("#badge-ready", Static))
            self.assertIsNotNone(app.query_one("#badge-processing", Static))
            self.assertIsNotNone(app.query_one("#badge-complete", Static))

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
            self.assertFalse(app.audio_enabled)
            self.assertIn("com", str(btn.label).lower())

            # Clica novamente
            await pilot.click("#audio-toggle")
            self.assertTrue(app.audio_enabled)
            self.assertIn("sem", str(btn.label).lower())

    async def test_cmd_bar_commands(self) -> None:
        app = UpscaleScreen()
        async with app.run_test(size=(120, 36)) as pilot:
            cmd = app.query_one("#cmd-input", Input)

            # Comando para trocar perfil
            cmd.value = "compressed"
            await pilot.click("#cmd-send")
            await pilot.pause()
            self.assertEqual(app.selected_profile, "compressed")

            # Comando para alternar áudio
            cmd.value = "audio"
            await pilot.click("#cmd-send")
            await pilot.pause()
            self.assertFalse(app.audio_enabled)

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
        app = UpscaleScreen()
        async with app.run_test(size=(120, 36)) as pilot:
            with tempfile.TemporaryDirectory() as tmpdir:
                shot_path = Path(tmpdir) / "test_capture.svg"
                app.save_screenshot(filename=str(shot_path.name), path=str(tmpdir))
                self.assertTrue(shot_path.exists())
                content = shot_path.read_text(encoding="utf-8")
                self.assertIn("<svg", content)
                self.assertIn("VidiScale", content)
                self.assertIn("Settings", content)
                self.assertIn("Log", content)
                self.assertIn("Monitor", content)


if __name__ == "__main__":
    unittest.main()
