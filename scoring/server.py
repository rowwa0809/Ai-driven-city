"""
Tiny stdlib HTTP server that exposes the scoring pipeline as a live API.

Endpoints:
  GET  /api/state         → current snapshot (JSON)
  POST /api/refresh       → re-run pipeline, return new snapshot
  GET  /healthz           → "ok"
  GET  /                  → serves the /narrative/ static frontend so a
                            single command boots the whole prototype.

Run:
  python3 -m scoring.server                  # localhost:8787
  PORT=9000 python3 -m scoring.server        # custom port

Why stdlib? No install step. Anyone can clone, run, and see the live
scoring drive the dashboard. In production this is a FastAPI service
behind a CDN/edge cache; the contract above is intentionally identical.
"""

from __future__ import annotations
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
import os
import threading
import time

from pipeline import build_snapshot, SPEC_PATH

ROOT = Path(__file__).resolve().parent.parent
STATIC_ROOT = ROOT  # serves the whole repo (so /narrative/ works)

_lock = threading.Lock()
_cache = {"snap": None, "ts": 0.0}


def get_snapshot(force: bool = False) -> dict:
    with _lock:
        # Throttle: rebuild at most once every 5s unless forced.
        if not force and _cache["snap"] is not None and (time.time() - _cache["ts"]) < 5:
            return _cache["snap"]
        spec = json.loads(SPEC_PATH.read_text())
        snap = build_snapshot(spec)
        _cache.update(snap=snap, ts=time.time())
        # Also persist to /narrative/data.json for the static fallback path.
        out = ROOT / "narrative" / "data.json"
        out.write_text(json.dumps(snap, indent=2))
        return snap


CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg":  "image/svg+xml",
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Quiet by default; flip to print(...) when debugging.
        return

    def _json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self):
        url_path = self.path.split("?")[0].lstrip("/")
        if not url_path:
            url_path = "narrative/index.html"
        # Normalise to avoid path traversal
        target = (STATIC_ROOT / url_path).resolve()
        if STATIC_ROOT.resolve() not in target.parents and target != STATIC_ROOT.resolve():
            self.send_error(403); return
        if target.is_dir():
            target = target / "index.html"
        if not target.exists():
            self.send_error(404); return
        ct = CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            self._json(200, {"status": "ok"}); return
        if self.path.startswith("/api/state"):
            self._json(200, get_snapshot()); return
        self._serve_static()

    def do_POST(self):
        if self.path.startswith("/api/refresh"):
            snap = get_snapshot(force=True)
            self._json(200, snap); return
        self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def main():
    port = int(os.environ.get("PORT", "8787"))
    # Warm cache so the first request is instant.
    get_snapshot(force=True)
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"narrative-intelligence scoring · http://localhost:{port}/")
    print(f"  GET  /api/state    snapshot")
    print(f"  POST /api/refresh  rebuild")
    print(f"  GET  /             frontend (serves /narrative/)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        srv.shutdown()


if __name__ == "__main__":
    main()
