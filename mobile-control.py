#!/usr/bin/env python3
"""Loopback-only desktop controls. Public requests must pass Nginx login."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from urllib.parse import quote, urlsplit

LOCK = threading.Lock()
HOME = Path("/config")
SESSION_FILE = Path("/run/cloud-pc/session.json")
APP_CATALOG = {
    "files": {"label": "الملفات", "icon": "▣", "binary": "thunar", "classes": ("thunar",)},
    "terminal": {"label": "الترمينال", "icon": ">_", "binary": "xfce4-terminal", "classes": ("xfce4-terminal",)},
    "editor": {"label": "المفكرة", "icon": "✎", "binary": "mousepad", "classes": ("mousepad",)},
    "monitor": {"label": "مراقبة الموارد", "icon": "▥", "binary": "xfce4-taskmanager", "classes": ("xfce4-taskmanager",)},
    "chromium": {"label": "Chromium البديل", "icon": "◎", "binary": "wrapped-chromium", "classes": ("chromium",)},
    "brave-log": {"label": "سجل أخطاء Brave", "icon": "!", "binary": "mousepad", "classes": ()},
}
KEYS = {"enter": "Return", "escape": "Escape", "tab": "Tab", "backspace": "BackSpace",
        "up": "Up", "down": "Down", "left": "Left", "right": "Right"}


class ControlError(Exception):
    pass


def command(args: list[str], *, input_text: str | None = None, check: bool = True) -> str:
    result = subprocess.run(args, input=input_text, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=5, check=check)
    return result.stdout.strip()


def navigation_url(text: str) -> str:
    if not isinstance(text, str):
        raise ControlError("اكتب عنوان موقع أو عبارة بحث.")
    text = text.strip()
    if not text or len(text) > 4096 or any(ord(c) < 32 for c in text):
        raise ControlError("اكتب عنوان موقع أو عبارة بحث أقصر.")
    parsed = urlsplit(text)
    if parsed.scheme.lower() in ("https", "http") and parsed.hostname:
        return text
    if not parsed.scheme and "." in text and " " not in text and not text.startswith(("/", "\\")):
        return "https://" + text
    return "https://www.google.com/search?q=" + quote(text, safe="")


def memory_status(base: Path = Path("/sys/fs/cgroup")) -> dict:
    def number(path):
        try:
            value = path.read_text().strip()
            return int(value) if value != "max" else None
        except (OSError, ValueError):
            return None
    limit = number(base / "memory.max")
    used = number(base / "memory.current")
    if used is None:
        limit = number(base / "memory/memory.limit_in_bytes")
        used = number(base / "memory/memory.usage_in_bytes")
    if limit and limit > 1 << 50:
        limit = None
    events = {}
    try:
        events = dict(line.split() for line in (base / "memory.events").read_text().splitlines())
    except (OSError, ValueError):
        pass
    return {"limit_mb": round(limit / 1048576) if limit else None,
            "used_mb": round(used / 1048576) if used is not None else None,
            "oom_kills": int(events.get("oom_kill", "0")),
            "low_memory": bool(limit and limit < 1536 * 1048576)}


def windows() -> list[tuple[str, str]]:
    result = []
    for line in command(["wmctrl", "-lx"]).splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4:
            result.append((parts[0], parts[3].lower()))
    return result


def window_details() -> list[dict]:
    result = []
    for line in command(["wmctrl", "-lx"]).splitlines():
        parts = line.split(None, 4)
        if len(parts) >= 4 and "xfdesktop" not in parts[3].lower() and "xfce4-panel" not in parts[3].lower():
            result.append({"id": parts[0], "class": parts[3].lower(), "title": parts[4] if len(parts) > 4 else "نافذة"})
    return result


def available_apps() -> list[dict]:
    return [{"id": key, "label": app["label"], "icon": app["icon"]}
            for key, app in APP_CATALOG.items() if shutil.which(app["binary"])]


def launch_program(app_id: str) -> None:
    app = APP_CATALOG.get(app_id)
    if not app or not shutil.which(app["binary"]):
        raise ControlError("البرنامج غير متاح في هذه النسخة.")
    existing = next((w for w, cls in windows() if any(name in cls for name in app["classes"])), None)
    if existing:
        command(["wmctrl", "-ia", existing])
    else:
        args = [app["binary"]]
        if app_id == "brave-log":
            path = HOME / ".local/state/cloud-pc/brave.stderr.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(mode=0o600, exist_ok=True)
            args.append(str(path))
        subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)


def browser_mode() -> str:
    try:
        return "safe" if (HOME / ".config/cloud-pc/browser-mode").read_text().strip() == "safe" else "normal"
    except OSError:
        return "normal"


def set_browser_mode(mode: str) -> None:
    if mode not in ("normal", "safe"):
        raise ControlError("وضع متصفح غير صالح.")
    path = HOME / ".config/cloud-pc/browser-mode"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(mode + "\n")
    path.chmod(0o600)


def session_status() -> dict:
    try:
        data = json.loads(SESSION_FILE.read_text())
    except (OSError, ValueError):
        data = {"id": "unavailable", "width": 1280, "height": 800}
    data["browser_mode"] = browser_mode()
    return data


def active_window() -> str:
    value = int(command(["xdotool", "getactivewindow"]))
    for window, _ in windows():
        if int(window, 16) == value:
            return window
    raise ControlError("اضغط أولًا داخل النافذة التي تريد التحكم بها.")


def browser_window(*, create: bool = True) -> str:
    def find():
        return next((window for window, cls in windows() if "brave" in cls), None)
    window = find()
    if not window and create:
        log_path = HOME / ".local/state/cloud-pc/brave.stderr.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if log_path.exists() and log_path.stat().st_size > 2 * 1024 * 1024:
            log_path.replace(log_path.with_suffix(".previous.log"))
        with log_path.open("ab") as log:
            log_path.chmod(0o600)
            subprocess.Popen(["/usr/local/bin/cloud-brave", "https://www.google.com/"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=log, start_new_session=True)
        for _ in range(20):
            time.sleep(0.2)
            window = find()
            if window:
                break
    if not window:
        raise ControlError("المتصفح لم يجهز بعد. انتظر قليلًا ثم اضغط Google، وراجع مؤشر الذاكرة.")
    command(["wmctrl", "-ia", window])
    time.sleep(0.08)
    return window


def paste_text(text: str) -> None:
    if not isinstance(text, str) or not text or len(text) > 16000 or "\0" in text:
        raise ControlError("النص فارغ أو طويل جدًا.")
    # xclip owns the selection after forking; discard its descriptors so a
    # clipboard owner cannot keep the request's pipes open indefinitely.
    subprocess.run(["xclip", "-selection", "clipboard", "-in", "-loops", "1"], input=text,
                   text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=3, check=True)
    time.sleep(0.08)
    command(["xdotool", "key", "--clearmodifiers", "ctrl+v"])


def navigate_browser(target: str) -> str:
    window = browser_window()
    command(["xdotool", "key", "--clearmodifiers", "ctrl+l"])
    paste_text(target)
    time.sleep(0.12)
    command(["xdotool", "key", "--clearmodifiers", "Return"])
    return window


def perform(data: dict) -> dict:
    action = data.get("action")
    if action == "open-browser":
        # Attach only: never replace the current YouTube/video/page with Google.
        browser_window()
    elif action == "open-program":
        launch_program(data.get("app"))
    elif action == "focus-window":
        target = data.get("window")
        if not isinstance(target, str) or target not in {w for w, _ in windows()}:
            raise ControlError("هذه النافذة لم تعد مفتوحة.")
        command(["wmctrl", "-ia", target])
    elif action == "navigate":
        target = navigation_url(data.get("text", ""))
        navigate_browser(target)
    elif action in ("back", "reload", "new-tab", "close-tab", "page-zoom-in", "page-zoom-out", "page-zoom-reset"):
        browser_window(create=action != "close-tab")
        chord = {"back": "alt+Left", "reload": "ctrl+r", "new-tab": "ctrl+t", "close-tab": "ctrl+w",
                 "page-zoom-in": "ctrl+equal", "page-zoom-out": "ctrl+minus", "page-zoom-reset": "ctrl+0"}[action]
        command(["xdotool", "key", "--clearmodifiers", chord])
    elif action in ("maximize", "restore", "toggle-maximize", "minimize", "close-window"):
        window = active_window()
        if action == "close-window":
            command(["wmctrl", "-ic", window])
        elif action == "minimize":
            command(["xdotool", "windowminimize", window])
        else:
            mode = {"maximize": "add", "restore": "remove", "toggle-maximize": "toggle"}[action]
            command(["wmctrl", "-ir", window, "-b", mode + ",maximized_vert,maximized_horz"])
    elif action == "paste":
        active_window()
        paste_text(data.get("text"))
    elif action == "key":
        key = KEYS.get(data.get("key"))
        if not key:
            raise ControlError("زر غير مدعوم.")
        active_window()
        command(["xdotool", "key", "--clearmodifiers", key])
    elif action in ("restart-browser", "safe-browser", "normal-browser"):
        command(["pkill", "-TERM", "-x", "brave"], check=False)
        for _ in range(20):
            if not command(["pgrep", "-x", "brave"], check=False):
                break
            time.sleep(0.1)
        else:
            raise ControlError("المتصفح لم يغلق بعد. انتظر قليلًا؛ لم نحذف قفل ملفه أو نقتل العملية بالقوة.")
        if action != "restart-browser":
            set_browser_mode("safe" if action == "safe-browser" else "normal")
        window = browser_window()
        command(["wmctrl", "-ir", window, "-b", "add,maximized_vert,maximized_horz"])
    else:
        raise ControlError("أمر غير مدعوم.")
    return {"ok": True}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        # Never log clipboard content, browsing text or window titles.
        pass

    def reply(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/status":
            return self.reply(404, {"error": "Not found"})
        try:
            open_windows = window_details()
        except (subprocess.SubprocessError, OSError):
            open_windows = []
        return self.reply(200, {"ok": True, "memory": memory_status(), "session": session_status(),
                               "apps": available_apps(), "windows": open_windows})

    def do_POST(self):
        if self.path != "/command":
            return self.reply(404, {"error": "Not found"})
        if self.headers.get("X-Cloud-PC-Control") != "1" or self.headers.get_content_type() != "application/json":
            return self.reply(403, {"error": "Request rejected"})
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).netloc.lower() != self.headers.get("Host", "").lower():
            return self.reply(403, {"error": "Origin rejected"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.reply(400, {"error": "Invalid length"})
        if not 0 < length <= 32768:
            return self.reply(413, {"error": "Request too large"})
        try:
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError
            with LOCK:
                result = perform(data)
            return self.reply(200, result)
        except (ValueError, TypeError):
            return self.reply(400, {"error": "بيانات غير صالحة."})
        except ControlError as error:
            return self.reply(409, {"error": str(error)})
        except (subprocess.SubprocessError, OSError):
            return self.reply(503, {"error": "جلسة سطح المكتب غير جاهزة أو توقفت. انتظر ثم جرّب مجددًا وراجع الذاكرة."})


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 7801), Handler)
    server.serve_forever()
