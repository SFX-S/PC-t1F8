"""Control API and resource checks. No running desktop is required."""
import http.client
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("mobile_control", ROOT / "mobile-control.py")
MOBILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOBILE)


class MobileHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = MOBILE.ThreadingHTTPServer(("127.0.0.1", 0), MOBILE.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = json.loads(response.read())
        status = response.status
        connection.close()
        return status, data

    def headers(self, **extras):
        return {"Content-Type": "application/json", "X-Cloud-PC-Control": "1", **extras}

    def test_status_reports_only_resource_fields(self):
        status, data = self.request("GET", "/status")
        self.assertEqual(status, 200)
        self.assertIn("limit_mb", data["memory"])
        self.assertNotIn("PASSWORD", json.dumps(data))

    def test_post_without_custom_header_rejected(self):
        with patch.object(MOBILE, "perform") as perform:
            status, _ = self.request("POST", "/command", '{}', {"Content-Type": "application/json"})
        self.assertEqual(status, 403)
        perform.assert_not_called()

    def test_form_post_rejected(self):
        status, _ = self.request("POST", "/command", "action=close-window", {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 403)

    def test_cross_origin_request_rejected(self):
        with patch.object(MOBILE, "perform") as perform:
            status, _ = self.request("POST", "/command", '{}', self.headers(Origin="https://unrelated.example"))
        self.assertEqual(status, 403)
        perform.assert_not_called()

    def test_same_origin_command_dispatched(self):
        origin = "http://127.0.0.1:" + str(self.server.server_port)
        with patch.object(MOBILE, "perform", return_value={"ok": True}) as perform:
            status, data = self.request("POST", "/command", '{"action":"maximize"}', self.headers(Origin=origin))
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        perform.assert_called_once_with({"action": "maximize"})

    def test_invalid_json_rejected(self):
        status, _ = self.request("POST", "/command", "[invalid", self.headers())
        self.assertEqual(status, 400)

    def test_json_array_rejected(self):
        status, _ = self.request("POST", "/command", "[]", self.headers())
        self.assertEqual(status, 400)

    def test_unknown_actions_rejected(self):
        status, _ = self.request("POST", "/command", '{"action":"run-shell"}', self.headers())
        self.assertEqual(status, 409)

    def test_large_request_rejected_before_dispatch(self):
        with patch.object(MOBILE, "perform") as perform:
            status, _ = self.request("POST", "/command", "x" * 32769, self.headers())
        self.assertEqual(status, 413)
        perform.assert_not_called()

    def test_unready_display_has_explanatory_response(self):
        with patch.object(MOBILE, "perform", side_effect=OSError("private debug detail")):
            status, data = self.request("POST", "/command", '{"action":"maximize"}', self.headers())
        self.assertEqual(status, 503)
        self.assertNotIn("private debug detail", data["error"])

    def test_unknown_route_rejected(self):
        status, _ = self.request("GET", "/execute?command=id")
        self.assertEqual(status, 404)


class MemoryAndNavigationTests(unittest.TestCase):
    def test_low_memory_and_actual_oom_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "memory.max").write_text(str(1024 * 1048576))
            (base / "memory.current").write_text(str(900 * 1048576))
            (base / "memory.events").write_text("oom 3\noom_kill 2\n")
            status = MOBILE.memory_status(base)
        self.assertTrue(status["low_memory"])
        self.assertEqual(status["limit_mb"], 1024)
        self.assertEqual(status["used_mb"], 900)
        self.assertEqual(status["oom_kills"], 2)

    def test_no_limit_does_not_invent_memory_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "memory.max").write_text("max")
            (base / "memory.current").write_text("100")
            status = MOBILE.memory_status(base)
        self.assertIsNone(status["limit_mb"])
        self.assertFalse(status["low_memory"])

    def test_cgroup_v1_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "memory").mkdir()
            (base / "memory/memory.limit_in_bytes").write_text(str(4 * 1024 * 1048576))
            (base / "memory/memory.usage_in_bytes").write_text(str(800 * 1048576))
            status = MOBILE.memory_status(base)
        self.assertEqual(status["limit_mb"], 4096)
        self.assertFalse(status["low_memory"])

    def test_search_unicode_and_special_characters_encoded(self):
        target = MOBILE.navigation_url("رياضيات ; $(touch /tmp/nope)")
        self.assertTrue(target.startswith("https://www.google.com/search?q="))
        self.assertNotIn(" ", target)
        self.assertNotIn("$(", target)

    def test_javascript_not_treated_as_executable_url(self):
        self.assertTrue(MOBILE.navigation_url("javascript:alert(1)").startswith("https://www.google.com/search?q="))

    def test_bare_domain_gets_https(self):
        self.assertEqual(MOBILE.navigation_url("google.com"), "https://google.com")

    def test_bad_navigation_values_rejected(self):
        for value in (None, 42, "", "https://example.com/\nrun", "x" * 4097):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(MOBILE.ControlError):
                    MOBILE.navigation_url(value)


if __name__ == "__main__":
    unittest.main()
