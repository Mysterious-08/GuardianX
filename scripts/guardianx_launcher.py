from __future__ import annotations

import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit


PROJECT_DIR = Path(__file__).resolve().parents[1]
BAT_FILE = PROJECT_DIR / "scripts" / "start_guardianx_monitoring.bat"
HOST = "127.0.0.1"
PORT = 8765
MAX_REQUEST_BYTES = 16_384
monitor_process: subprocess.Popen[bytes] | None = None


class LauncherHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _set_cors_headers(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True

        parsed_origin = urlsplit(origin)
        if parsed_origin.scheme != "http" or parsed_origin.hostname not in {"localhost", "127.0.0.1"}:
            self.send_error(403, "Only localhost browser origins are allowed")
            return False

        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Vary", "Origin")
        return True

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._set_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _origin_is_allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if not origin:
            return True
        parsed_origin = urlsplit(origin)
        return parsed_origin.scheme == "http" and parsed_origin.hostname in {"localhost", "127.0.0.1"}

    def do_OPTIONS(self) -> None:
        if not self._origin_is_allowed():
            self.send_error(403, "Only localhost browser origins are allowed")
            return
        self.send_response(204)
        self._set_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._origin_is_allowed():
            self.send_error(403, "Only localhost browser origins are allowed")
            return
        if self.path != "/status":
            self._send_json(404, {"error": "not_found"})
            return

        running = _is_monitor_running()
        self._send_json(200, {"running": running})

    def do_POST(self) -> None:
        if not self._origin_is_allowed():
            self.send_error(403, "Only localhost browser origins are allowed")
            return
        if self.path == "/start":
            self._start_monitoring()
        elif self.path == "/stop":
            self._stop_monitoring()
        else:
            self._send_json(404, {"error": "not_found"})

    def _start_monitoring(self) -> None:
        global monitor_process

        if _is_monitor_running():
            self._send_json(200, {"status": "already_running", "running": True})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "invalid_content_length"})
            return
        if content_length <= 0 or content_length > MAX_REQUEST_BYTES:
            self._send_json(400, {"error": "invalid_request_size"})
            return

        try:
            request_body = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send_json(400, {"error": "invalid_json"})
            return

        access_token = request_body.get("access_token") if isinstance(request_body, dict) else None
        if not isinstance(access_token, str) or not access_token.strip():
            self._send_json(400, {"error": "access_token_required"})
            return

        environment = os.environ.copy()
        environment["GUARDIANX_ACCESS_TOKEN"] = access_token
        try:
            monitor_process = subprocess.Popen(
                [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", "call", str(BAT_FILE)],
                cwd=PROJECT_DIR,
                env=environment,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except OSError:
            monitor_process = None
            self._send_json(500, {"error": "failed_to_start"})
            return

        self._send_json(200, {"status": "started", "running": True})

    def _stop_monitoring(self) -> None:
        global monitor_process

        if not _is_monitor_running():
            self._send_json(200, {"status": "not_running", "running": False})
            return

        process = monitor_process
        assert process is not None
        result = subprocess.run(
            ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0 and process.poll() is None:
            self._send_json(500, {"error": "failed_to_stop", "running": True})
            return

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._send_json(500, {"error": "failed_to_stop", "running": True})
            return
        monitor_process = None
        self._send_json(200, {"status": "stopped", "running": False})


def _is_monitor_running() -> bool:
    global monitor_process
    if monitor_process is None:
        return False
    if monitor_process.poll() is None:
        return True
    monitor_process = None
    return False


def main() -> None:
    server = HTTPServer((HOST, PORT), LauncherHandler)
    print(f"GuardianX launcher listening on http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
