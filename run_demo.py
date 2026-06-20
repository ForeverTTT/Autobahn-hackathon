#!/usr/bin/env python3
"""Start the AlpineFlow local demo with one command.

The script provides the calendar API directly from the scored daily CSV and
starts the Vite frontend. No FastAPI process is required for the local demo.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from agent.tools.calendar_data import calendar_traffic_loader


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"


class DemoApiHandler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.send_json(200, {"service": "AlpineFlow local demo", "status": "running"})
            return

        if parsed.path != "/api/calendar/daily":
            self.send_json(404, {"detail": "Not found"})
            return

        params = parse_qs(parsed.query)
        try:
            year = int(params["year"][0])
            month = int(params["month"][0])
            road = params.get("road", ["A8"])[0]
            payload = calendar_traffic_loader.query_month(year, month, road)
        except (KeyError, IndexError, ValueError) as error:
            self.send_json(400, {"detail": str(error) or "Invalid query parameters"})
            return
        except FileNotFoundError as error:
            self.send_json(503, {"detail": str(error)})
            return

        self.send_json(200, payload)

    def log_message(self, format: str, *args) -> None:
        if self.path != "/":
            print(f"[demo-api] {self.address_string()} {format % args}")


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def wait_for_port(host: str, port: int, timeout: float = 20) -> bool:
    deadline = time.time() + timeout
    connect_host = "127.0.0.1" if host == "0.0.0.0" else host

    while time.time() < deadline:
        try:
            with socket.create_connection((connect_host, port), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def ensure_frontend_dependencies(npm: str) -> None:
    vite_binary = WEB_DIR / "node_modules" / ".bin" / "vite"
    if vite_binary.exists():
        return

    print("[setup] Frontend dependencies are missing; running npm install...")
    subprocess.run([npm, "install"], cwd=WEB_DIR, check=True)


def stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the AlpineFlow local demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the calendar automatically.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    npm = shutil.which("npm")
    if not npm:
        print("Error: npm was not found. Install Node.js first.", file=sys.stderr)
        return 1

    try:
        ensure_frontend_dependencies(npm)
        api_server = ReusableThreadingHTTPServer(
            (args.host, args.backend_port),
            DemoApiHandler,
        )
    except OSError as error:
        print(
            f"Error: cannot start the local API on port {args.backend_port}: {error}",
            file=sys.stderr,
        )
        return 1
    except subprocess.CalledProcessError:
        print("Error: npm install failed.", file=sys.stderr)
        return 1

    api_thread = threading.Thread(target=api_server.serve_forever, daemon=True)
    api_thread.start()

    environment = os.environ.copy()
    environment["DEMO_API_PORT"] = str(args.backend_port)
    frontend_process = None
    browser_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    calendar_url = (
        f"http://{browser_host}:{args.frontend_port}/#/calendar"
    )

    try:
        frontend_process = subprocess.Popen(
            [
                npm,
                "run",
                "dev",
                "--",
                "--host",
                args.host,
                "--port",
                str(args.frontend_port),
                "--strictPort",
            ],
            cwd=WEB_DIR,
            env=environment,
        )

        print(f"[demo] Calendar API: http://{browser_host}:{args.backend_port}")
        print(f"[demo] Frontend:     {calendar_url}")
        print("[demo] Press Ctrl+C to stop both services.")

        if not args.no_browser:
            def open_when_ready() -> None:
                if wait_for_port(args.host, args.frontend_port):
                    webbrowser.open(calendar_url)

            threading.Thread(target=open_when_ready, daemon=True).start()

        return_code = frontend_process.wait()
        if return_code != 0:
            print(f"Frontend exited with code {return_code}.", file=sys.stderr)
        return return_code
    except KeyboardInterrupt:
        print("\n[demo] Stopping local demo...")
        return 0
    finally:
        stop_process(frontend_process)
        api_server.shutdown()
        api_server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
