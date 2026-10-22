#!/usr/bin/env python3
"""Serve the enterprise-rag evidence replay.

Static hosting needs only ``demo/public/``. The local server also exposes
``/api/query``, which runs the frozen 7-doc/10-chunk baseline -- never the
private 11994-chunk corpus.
"""

from __future__ import annotations

import argparse
import functools
import json
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "demo") not in sys.path:
    sys.path.insert(0, str(ROOT / "demo"))

from payload import build_payload, query_baseline  # noqa: E402

PUBLIC = ROOT / "demo" / "public"
_cache: dict[str, dict | None] = {"payload": None}
_lock = threading.Lock()


def get_payload(force: bool = False) -> dict:
    with _lock:
        if force or _cache["payload"] is None:
            _cache["payload"] = build_payload()
        return _cache["payload"]  # type: ignore[return-value]


class DemoHandler(SimpleHTTPRequestHandler):
    server_version = "EnterpriseRagDemo/1.0"

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[demo] " + (fmt % args) + "\n")

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _payload(self, force: bool = False) -> None:
        try:
            payload = get_payload(force=force)
        except Exception as exc:  # noqa: BLE001
            self._json(500, {"error": type(exc).__name__, "detail": str(exc)})
            return
        self._json(200, payload)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            self._json(200, {"status": "ok", "mode": "live",
                             "demo": "retrieval-evidence"})
            return
        if path in ("/api/results", "/results.json"):
            self._payload()
            return
        if path == "/config.json":
            self._json(200, {
                "mode": "live",
                "note": "本地实时模式：/api/query 跑冻结基线；结果面板是已提交结果回放。",
            })
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/api/run":
            try:
                payload = build_payload()
                with _lock:
                    _cache["payload"] = payload
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": type(exc).__name__,
                                 "detail": str(exc)})
                return
            self._json(200, payload)
            return
        if path == "/api/query":
            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                self._json(400, {"error": "invalid json"})
                return
            query = body.get("query") if isinstance(body, dict) else None
            if not isinstance(query, str) or not query.strip():
                self._json(400, {"error": "query must be a non-empty string"})
                return
            if len(query) > 200:
                self._json(400, {"error": "query too long"})
                return
            try:
                results = query_baseline(query)
            except Exception as exc:  # noqa: BLE001
                self._json(500, {"error": type(exc).__name__,
                                 "detail": str(exc)})
                return
            self._json(200, {
                "query": query,
                "results": results,
                "scope": "7 docs / 10 chunks 冻结基线；不是 11994-chunk 结果",
            })
            return
        self._json(404, {"error": "not found"})


def make_server(host: str = "127.0.0.1", port: int = 0):
    handler = functools.partial(DemoHandler, directory=str(PUBLIC))
    httpd = ThreadingHTTPServer((host, port), handler)
    return httpd, int(httpd.server_address[1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-precompute", action="store_true")
    args = ap.parse_args()

    if not args.no_precompute:
        print("building evidence payload ...", flush=True)
        get_payload()
        print("ready", flush=True)

    httpd, port = make_server(args.host, args.port)
    print(f"demo: http://{args.host}:{port}/", flush=True)
    print("live baseline: POST /api/query", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped", flush=True)
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
