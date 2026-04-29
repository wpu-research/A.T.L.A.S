"""
Atlas Browser UI
Replaces tkinter with a WebSocket + HTTP server.
Serves web/atlas.html on http://localhost:7861
WebSocket on ws://localhost:7862
"""
import asyncio
import json
import platform
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import websockets

CONFIG_DIR = Path(__file__).resolve().parent / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"
WEB_DIR    = Path(__file__).resolve().parent / "web"
HTTP_PORT  = 7861
WS_PORT    = 7862


class AtlasUI:
    """Browser-based UI for A.T.L.A.S — Altınbaş University AI Assistant."""

    def __init__(self, face_path=None, size=None):
        self.muted           = False
        self.on_text_command = None
        self._state          = "INITIALISING"
        self._clients: set   = set()
        self._ws_loop        = None
        self._api_key_ready  = self._api_keys_exist()

        # Dummy root so main.py can still call ui.root.mainloop()
        self.root = _DummyRoot(self)

        threading.Thread(target=self._run_http, daemon=True).start()
        threading.Thread(target=self._run_ws,   daemon=True).start()
        time.sleep(1.0)
        print(f"\n{'='*55}")
        print(f"  A.T.L.A.S  →  http://localhost:{HTTP_PORT}")
        print(f"{'='*55}\n")
        threading.Thread(target=self._open_browser, daemon=True).start()

    # ── Public interface ────────────────────────────────────────────────────

    def set_state(self, state: str):
        self._state = state
        self._broadcast({"type": "state", "value": state})

    def write_log(self, text: str):
        self._broadcast({"type": "log", "text": text})

    def wait_for_api_key(self):
        while not self._api_key_ready:
            time.sleep(0.1)

    def run(self):
        """Keep main thread alive (used instead of root.mainloop())."""
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    def _open_browser(self):
        try:
            webbrowser.open(f"http://localhost:{HTTP_PORT}")
        except Exception:
            pass

    # ── Internal ────────────────────────────────────────────────────────────

    def _api_keys_exist(self) -> bool:
        if not API_FILE.exists():
            return False
        try:
            data = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(data.get("gemini_api_key")) and bool(data.get("os_system"))
        except Exception:
            return False

    def _broadcast(self, msg: dict):
        if not self._ws_loop:
            return
        asyncio.run_coroutine_threadsafe(
            self._async_broadcast(json.dumps(msg)), self._ws_loop
        )

    async def _async_broadcast(self, data: str):
        dead = set()
        for client in list(self._clients):
            try:
                await client.send(data)
            except Exception:
                dead.add(client)
        self._clients -= dead

    # ── HTTP server ──────────────────────────────────────────────────────────

    def _run_http(self):
        ui = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = WEB_DIR / "atlas.html"
                body = path.read_bytes() if path.exists() else b"<h1>atlas.html not found</h1>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        HTTPServer(("localhost", HTTP_PORT), Handler).serve_forever()

    # ── WebSocket server ─────────────────────────────────────────────────────

    def _run_ws(self):
        self._ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ws_loop)
        self._ws_loop.run_until_complete(self._ws_serve())

    async def _ws_serve(self):
        async with websockets.serve(self._ws_handler, "localhost", WS_PORT):
            await asyncio.Future()

    async def _ws_handler(self, ws):
        self._clients.add(ws)
        try:
            await ws.send(json.dumps({"type": "state", "value": self._state}))
            await ws.send(json.dumps({"type": "setup_status", "ready": self._api_key_ready}))
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    await self._handle(ws, msg)
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self._clients.discard(ws)

    async def _handle(self, ws, msg: dict):
        t = msg.get("type")

        if t == "text":
            text = msg.get("text", "").strip()
            if text and self.on_text_command:
                threading.Thread(
                    target=self.on_text_command, args=(text,), daemon=True
                ).start()

        elif t == "mute":
            self.muted = not self.muted
            state = "MUTED" if self.muted else "LISTENING"
            self._state = state
            self._broadcast({"type": "state", "value": state})
            self._broadcast({"type": "muted", "value": self.muted})

        elif t == "setup":
            key    = msg.get("key", "").strip()
            os_sys = msg.get("os", "linux").strip()
            if key:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                API_FILE.write_text(
                    json.dumps({"gemini_api_key": key, "os_system": os_sys}, indent=2),
                    encoding="utf-8",
                )
                self._api_key_ready = True
                await ws.send(json.dumps({"type": "setup_done"}))
                self._broadcast({"type": "log",   "text": "SYS: A.T.L.A.S initialised."})
                self._broadcast({"type": "state",  "value": "LISTENING"})


class _DummyRoot:
    """Lets main.py call ui.root.mainloop() without crashing."""

    def __init__(self, ui: AtlasUI):
        self._ui = ui

    def mainloop(self):
        self._ui.run()

# backward-compat alias
JarvisUI = AtlasUI
