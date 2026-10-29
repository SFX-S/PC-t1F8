"""Shared-session regression checks; desktop commands are mocked."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("session_control", ROOT / "mobile-control.py")
CONTROL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROL)


class SharedSessionTests(unittest.TestCase):
    def test_repeated_browser_attach_preserves_open_video(self):
        with patch.object(CONTROL, "command", return_value="0x000001 0 host CloudPCBrave.Brave-browser YouTube - playing") as command, \
             patch.object(CONTROL.time, "sleep"), \
             patch.object(CONTROL.subprocess, "Popen") as launch, \
             patch.object(CONTROL, "navigate_browser") as navigate, \
             patch.object(CONTROL, "paste_text") as paste:
            CONTROL.perform({"action": "open-browser"})
            CONTROL.perform({"action": "open-browser"})
        launch.assert_not_called()
        navigate.assert_not_called()
        paste.assert_not_called()
        focus_calls = [call.args[0] for call in command.call_args_list if call.args[0][0] == "wmctrl" and "-ia" in call.args[0]]
        self.assertEqual(focus_calls, [["wmctrl", "-ia", "0x000001"], ["wmctrl", "-ia", "0x000001"]])

    def test_program_launcher_reuses_existing_window(self):
        with patch.object(CONTROL.shutil, "which", return_value="/usr/bin/thunar"), \
             patch.object(CONTROL, "windows", return_value=[("0x12", "thunar.thunar")]), \
             patch.object(CONTROL, "command") as command, \
             patch.object(CONTROL.subprocess, "Popen") as launch:
            CONTROL.perform({"action": "open-program", "app": "files"})
        launch.assert_not_called()
        command.assert_called_once_with(["wmctrl", "-ia", "0x12"])

    def test_unknown_program_cannot_be_used_as_shell_command(self):
        with patch.object(CONTROL.subprocess, "Popen") as launch:
            with self.assertRaises(CONTROL.ControlError):
                CONTROL.perform({"action": "open-program", "app": "sh -c touch /tmp/not-run"})
        launch.assert_not_called()

    def test_focus_only_accepts_real_window_ids(self):
        with patch.object(CONTROL, "windows", return_value=[("0x12", "brave")]), patch.object(CONTROL, "command") as command:
            with self.assertRaises(CONTROL.ControlError):
                CONTROL.perform({"action": "focus-window", "window": "0x12; touch /tmp/no"})
        command.assert_not_called()

    def test_minimize_does_not_close_application(self):
        with patch.object(CONTROL, "active_window", return_value="0x12"), patch.object(CONTROL, "command") as command:
            CONTROL.perform({"action": "minimize"})
        command.assert_called_once_with(["xdotool", "windowminimize", "0x12"])

    def test_maximize_toggle_can_restore_window(self):
        with patch.object(CONTROL, "active_window", return_value="0x12"), patch.object(CONTROL, "command") as command:
            CONTROL.perform({"action": "toggle-maximize"})
        command.assert_called_once_with(["wmctrl", "-ir", "0x12", "-b", "toggle,maximized_vert,maximized_horz"])

    def test_shared_mode_does_not_delete_original_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            profile = home / ".config/BraveSoftware/Brave-Browser"
            profile.mkdir(parents=True)
            cookies = profile / "Cookies"
            cookies.write_text("existing profile sentinel")
            session = home / "session.json"
            session.write_text(json.dumps({"id": "same-server", "width": 1280, "height": 800}))
            with patch.object(CONTROL, "HOME", home), patch.object(CONTROL, "SESSION_FILE", session):
                CONTROL.set_browser_mode("safe")
                a = CONTROL.session_status()
                b = CONTROL.session_status()
                self.assertEqual(a["id"], b["id"])
                self.assertEqual(a["browser_mode"], "safe")
                self.assertEqual(b["browser_mode"], "safe")
                CONTROL.set_browser_mode("normal")
            self.assertEqual(cookies.read_text(), "existing profile sentinel")

    def test_repair_never_forces_deletion_of_profile_locks(self):
        def fake_command(args, **kwargs):
            return "123" if args[0] == "pgrep" else ""
        with patch.object(CONTROL, "command", side_effect=fake_command), \
             patch.object(CONTROL.time, "sleep"), \
             patch.object(CONTROL, "set_browser_mode") as change_mode, \
             patch.object(CONTROL, "browser_window") as launch:
            with self.assertRaises(CONTROL.ControlError):
                CONTROL.perform({"action": "safe-browser"})
        launch.assert_not_called()
        change_mode.assert_not_called()


if __name__ == "__main__":
    unittest.main()
