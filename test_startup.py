"""Offline validation: no Docker, network, credentials or root required."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
START = ROOT / "cloud-pc-start.sh"
SPEC = importlib.util.spec_from_file_location("configure_nginx", ROOT / "configure-nginx.py")
NGINX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(NGINX)


class StartupTests(unittest.TestCase):
    def launch(self, **values):
        environment = dict(os.environ)
        for key in ("PORT", "CUSTOM_PORT", "CUSTOM_USER", "PASSWORD", "DESKTOP_WIDTH", "DESKTOP_HEIGHT"):
            environment.pop(key, None)
        environment.update(values)
        return subprocess.run(["bash", str(START), "--check-config"], env=environment,
                              capture_output=True, text=True)

    def test_missing_password_fails_closed(self):
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Set PASSWORD", result.stderr)

    def test_short_password_rejected(self):
        self.assertNotEqual(self.launch(PASSWORD="short").returncode, 0)

    def test_valid_config_default_port_and_user(self):
        result = self.launch(PASSWORD="A_valid_test_password_12345")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("8080", result.stdout)
        self.assertIn("admin", result.stdout)

    def test_runtime_port_is_supported(self):
        result = self.launch(PORT="9200", CUSTOM_USER="captain", PASSWORD="A_valid_test_password_12345")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("9200", result.stdout)
        self.assertIn("captain", result.stdout)

    def test_shared_resolution_stable_by_default(self):
        result = self.launch(PASSWORD="A_valid_test_password_12345")
        self.assertEqual(result.returncode, 0)
        self.assertIn("shared display: 1280x800", result.stdout)

    def test_desktop_dimensions_validated(self):
        for dimension in ("0", "99999", "$(id)"):
            with self.subTest(dimension=dimension):
                result = self.launch(DESKTOP_WIDTH=dimension, PASSWORD="A_valid_test_password_12345")
                self.assertNotEqual(result.returncode, 0)

    def test_unsupported_port_values_rejected(self):
        for port in ("abc", "1023", "65536", "99999999999999999999", "8080;id", "-1", "0"):
            with self.subTest(port=port):
                self.assertNotEqual(self.launch(PORT=port, PASSWORD="A_valid_test_password_12345").returncode, 0)

    def test_internal_ports_rejected(self):
        for port in ("3001", "5000", "5100", "5173", "7801", "8082", "03001"):
            with self.subTest(port=port):
                result = self.launch(PORT=port, PASSWORD="A_valid_test_password_12345")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("internal service", result.stderr)

    def test_leading_zero_port_normalized(self):
        result = self.launch(PORT="08080", PASSWORD="A_valid_test_password_12345")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("port: 8080", result.stdout)

    def test_password_not_printed(self):
        secret = "Sensitive_test_password_12345"
        result = self.launch(PASSWORD=secret)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_invalid_password_not_printed(self):
        secret = "sensitive; invalid\nvalue"
        result = self.launch(PASSWORD=secret)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(secret, result.stdout + result.stderr)

    def test_invalid_user_does_not_execute_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "executed"
            result = self.launch(CUSTOM_USER=f"$(touch {sentinel})", PASSWORD="A_valid_test_password_12345")
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(sentinel.exists())

    def test_health_patch_preserves_authentication(self):
        original = 'server {\n  #auth_basic "Login";\n  #auth_basic_user_file /etc/nginx/.htpasswd;\n  listen 3000 default_server;\n  location / { index index.html; }\n}\n'
        patched = NGINX.add_health_location(original)
        self.assertEqual(patched.count("location = /healthz"), 1)
        self.assertIn('  #auth_basic "Login";', patched)
        self.assertIn("auth_basic off;", patched)
        self.assertIn("location / { index index.html; }", patched)

    def test_changed_upstream_template_fails_build_patch(self):
        with self.assertRaises(ValueError):
            NGINX.add_health_location("server { listen 9000; }")

    def test_duplicate_upstream_template_fails_build_patch(self):
        with self.assertRaises(ValueError):
            NGINX.add_health_location("  listen 3000 default_server;\n" * 2)

    def test_mobile_routes_keep_desktop_location_and_auth(self):
        original = ('server {\n  #auth_basic "Login";\n  listen 3000 default_server;\n'
                    '  location SUBFOLDER { alias /usr/share/selkies/web/; }\n}\n'
                    'server {\n  #auth_basic "Login";\n  listen 3001 ssl;\n'
                    '  location SUBFOLDER { alias /usr/share/selkies/web/; }\n}\n')
        modified = NGINX.add_mobile_routes(NGINX.add_health_location(original))
        self.assertEqual(modified.count('  #auth_basic "Login";'), 2)
        self.assertEqual(modified.count("  location SUBFOLDER {"), 2)
        self.assertEqual(modified.count("  location /mobile-control/ {"), 2)
        self.assertEqual(modified.count("auth_basic off;"), 1)

    def test_shell_syntax(self):
        for path in (START, ROOT / "cloud-brave.sh", ROOT / "init-desktop.sh", ROOT / "smoke.sh", ROOT / "mobile-service.sh", ROOT / "brave-autostart.sh"):
            with self.subTest(file=path.name):
                result = subprocess.run(["bash", "-n", str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

