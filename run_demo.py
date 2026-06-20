#!/usr/bin/env python3
"""Start the AlpineFlow local demo with one command.

The script provides the calendar API directly from the scored daily CSV and
starts the Vite frontend. No FastAPI process is required for the local demo.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from concurrent.futures import TimeoutError as FutureTimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from agent.tools.api_handlers import ChatSessionRegistry, handle_hourly_explanation
from agent.tools.calendar_data import calendar_traffic_loader


PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"
PITCH_DIR = PROJECT_ROOT / "pitch"
CHAT_TIMEOUT_SECONDS = 180


class DemoApiHandler(BaseHTTPRequestHandler):
    chat_sessions: ChatSessionRegistry
    agent_loop: asyncio.AbstractEventLoop

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("Request body is required")
        return json.loads(self.rfile.read(content_length).decode("utf-8"))

    def run_agent_coroutine(self, coroutine):
        future = asyncio.run_coroutine_threadsafe(coroutine, self.agent_loop)
        return future.result(timeout=CHAT_TIMEOUT_SECONDS)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/":
            self.send_json(
                200,
                {
                    "service": "AlpineFlow local demo",
                    "status": "running",
                    "chat": "/api/chat",
                },
            )
            return

        # Natural-language factor explanation for the map page's GLOBAL radar.
        # /api/explain/{date}/{hour}?road=A8&lang=en
        if parsed.path.startswith("/api/explain/"):
            self.handle_explain(parsed)
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

    def handle_explain(self, parsed) -> None:
        parts = [p for p in parsed.path[len("/api/explain/"):].split("/") if p]
        if len(parts) != 2:
            self.send_json(404, {"detail": "Not found"})
            return
        date = unquote(parts[0]).strip()
        try:
            hour = int(parts[1])
        except ValueError:
            self.send_json(400, {"detail": "hour must be an integer"})
            return

        params = parse_qs(parsed.query)
        road = params.get("road", ["A8"])[0]
        lang = params.get("lang", ["en"])[0]

        try:
            payload = self.run_agent_coroutine(
                handle_hourly_explanation(date, hour, road, lang)
            )
        except FutureTimeoutError:
            self.send_json(504, {"detail": "The explanation agent timed out"})
            return
        except Exception as error:
            self.send_json(500, {"detail": str(error)})
            return

        self.send_json(200, payload)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/chat":
            self.send_json(404, {"detail": "Not found"})
            return

        try:
            request = self.read_json()
            query = str(request.get("query", "")).strip()
            if not query:
                raise ValueError("query is required")

            payload = self.run_agent_coroutine(
                self.chat_sessions.chat(
                    query=query,
                    user_type=request.get("user_type", "traveler"),
                    session_id=request.get("session_id"),
                )
            )
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"detail": str(error) or "Invalid JSON body"})
            return
        except FutureTimeoutError:
            self.send_json(504, {"detail": "The planning agent timed out"})
            return
        except Exception as error:
            self.send_json(500, {"detail": str(error)})
            return

        self.send_json(200, payload)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        prefix = "/api/chat/"
        if not parsed.path.startswith(prefix):
            self.send_json(404, {"detail": "Not found"})
            return

        session_id = unquote(parsed.path[len(prefix):]).strip()
        if not session_id:
            self.send_json(400, {"detail": "session_id is required"})
            return

        try:
            cleared = self.run_agent_coroutine(
                self.chat_sessions.clear(session_id)
            )
        except Exception as error:
            self.send_json(500, {"detail": str(error)})
            return

        self.send_json(
            200,
            {"success": True, "cleared": cleared, "session_id": session_id},
        )

    def log_message(self, format: str, *args) -> None:
        if self.path != "/":
            print(f"[demo-api] {self.address_string()} {format % args}")


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


def run_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    asyncio.set_event_loop(loop)
    loop.run_forever()


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


def ensure_node_dependencies(directory: Path, npm: str, label: str) -> None:
    vite_binary = directory / "node_modules" / ".bin" / "vite"
    if vite_binary.exists():
        return

    print(f"[setup] {label} dependencies are missing; running npm install...")
    subprocess.run([npm, "install"], cwd=directory, check=True)


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
    parser.add_argument("--pitch-port", type=int, default=5180)
    parser.add_argument(
        "--no-pitch",
        action="store_true",
        help="Do not start the pitch deck, only the web demo.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the pitch automatically.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    npm = shutil.which("npm")
    if not npm:
        print("Error: npm was not found. Install Node.js first.", file=sys.stderr)
        return 1

    start_pitch = not args.no_pitch
    agent_loop = asyncio.new_event_loop()
    DemoApiHandler.agent_loop = agent_loop
    DemoApiHandler.chat_sessions = ChatSessionRegistry()
    agent_thread = threading.Thread(
        target=run_event_loop,
        args=(agent_loop,),
        daemon=True,
    )
    agent_thread.start()

    try:
        ensure_node_dependencies(WEB_DIR, npm, "Frontend")
        if start_pitch:
            ensure_node_dependencies(PITCH_DIR, npm, "Pitch")
        api_server = ReusableThreadingHTTPServer(
            (args.host, args.backend_port),
            DemoApiHandler,
        )
    except OSError as error:
        print(
            f"Error: cannot start the local API on port {args.backend_port}: {error}",
            file=sys.stderr,
        )
        agent_loop.call_soon_threadsafe(agent_loop.stop)
        agent_thread.join(timeout=2)
        agent_loop.close()
        return 1
    except subprocess.CalledProcessError:
        print("Error: npm install failed.", file=sys.stderr)
        agent_loop.call_soon_threadsafe(agent_loop.stop)
        agent_thread.join(timeout=2)
        agent_loop.close()
        return 1

    api_thread = threading.Thread(target=api_server.serve_forever, daemon=True)
    api_thread.start()

    environment = os.environ.copy()
    environment["DEMO_API_PORT"] = str(args.backend_port)
    frontend_process = None
    pitch_process = None
    browser_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    frontend_base = f"http://{browser_host}:{args.frontend_port}"
    calendar_url = f"{frontend_base}/#/calendar"
    pitch_url = f"http://{browser_host}:{args.pitch_port}/"

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

        if start_pitch:
            pitch_environment = os.environ.copy()
            # Point the pitch's "Live Demo" links at the web app this script
            # just launched, regardless of the port chosen.
            pitch_environment["VITE_FRONTEND_BASE"] = frontend_base
            pitch_process = subprocess.Popen(
                [
                    npm,
                    "run",
                    "dev",
                    "--",
                    "--host",
                    args.host,
                    "--port",
                    str(args.pitch_port),
                    "--strictPort",
                ],
                cwd=PITCH_DIR,
                env=pitch_environment,
            )

        print(f"[demo] Calendar API: http://{browser_host}:{args.backend_port}")
        print(f"[demo] Web frontend: {calendar_url}")
        if start_pitch:
            print(f"[demo] Pitch deck:   {pitch_url}")
        print("[demo] Press Ctrl+C to stop all services.")

        # The pitch is the presentation front door; fall back to the calendar
        # when the pitch is disabled.
        open_url = pitch_url if start_pitch else calendar_url
        open_port = args.pitch_port if start_pitch else args.frontend_port
        if not args.no_browser:
            def open_when_ready() -> None:
                if wait_for_port(args.host, open_port):
                    webbrowser.open(open_url)

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
        stop_process(pitch_process)
        api_server.shutdown()
        api_server.server_close()
        agent_loop.call_soon_threadsafe(agent_loop.stop)
        agent_thread.join(timeout=2)
        agent_loop.close()


if __name__ == "__main__":
    raise SystemExit(main())
