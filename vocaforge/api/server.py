"""Agent RPC server (stdlib http.server, zero extra deps).

Protocol: POST /vf with JSON body. Recognized actions:
  - ``info``                  -> 200, framework + backend info
  - ``models``                -> 200, list of registered libraries
  - ``resolve`` / ``load``    -> 404 if absent, 103 if found + loaded
  - ``synth``                 -> 404 if model absent, else 200 with audio meta
                                 (writes WAV to ``out`` when provided)
"""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional, Tuple

from ..core.engine import VocaForgeEngine
from ..core.exceptions import VFModelNotFound, VocaForgeError
from ..synth.project import SynthProject
from .protocol import NOT_FOUND, LOADED, OK, BAD_REQUEST, ERROR, envelope


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    _engine_instance: Optional[VocaForgeEngine] = None

    # ---- helpers ----
    def _engine(self) -> VocaForgeEngine:
        return _Handler._engine_instance or VocaForgeEngine()

    def _send(self, code: int, body: Dict[str, Any]) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def log_message(self, *args: Any) -> None:  # silence default logging
        return

    # ---- routing ----
    def do_GET(self):
        if self.path.rstrip("/") in ("", "/", "/vf"):
            self._send(OK, envelope(OK, "VocaForge Agent RPC is alive. POST JSON to /vf."))
        else:
            self._send(BAD_REQUEST, envelope(BAD_REQUEST, "use POST /vf"))

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            req = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError) as exc:
            self._send(BAD_REQUEST, envelope(BAD_REQUEST, f"invalid JSON: {exc}"))
            return

        action = (req.get("action") or "synth").lower()
        try:
            resp_code, body = self._dispatch(action, req)
        except VFModelNotFound as exc:
            self._send(NOT_FOUND, envelope(NOT_FOUND, str(exc)))
            return
        except VocaForgeError as exc:
            self._send(ERROR, envelope(ERROR, str(exc)))
            return
        except Exception as exc:  # noqa: BLE001
            self._send(ERROR, envelope(ERROR, f"{type(exc).__name__}: {exc}"))
            return
        self._send(resp_code, body)

    def _dispatch(self, action: str, req: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        engine = self._engine()
        if action in ("info", "ping"):
            return OK, envelope(OK, "info", {
                "version": _version(),
                "backends": ["stub", "diffsinger"],
                "models": len(engine.list_models()),
            })
        if action == "models":
            return OK, envelope(OK, "models", {
                "models": [m.to_dict() for m in engine.list_models()],
            })
        if action in ("resolve", "load"):
            key = _model_key(req)
            if not engine.exists(key):
                raise VFModelNotFound(f"model not found: {key!r}")
            spec = engine.resolve(key)
            # 103 = found and loaded. HTTP 103 is a 1xx informational code and
            # cannot be a terminal status for HTTP clients, so we surface 103 in
            # the JSON envelope while returning HTTP 200 as the terminal status.
            return OK, envelope(LOADED, "model found and loaded", {"model": spec.to_dict()})
        if action == "synth":
            key = _model_key(req)
            if not engine.exists(key):
                raise VFModelNotFound(f"model not found: {key!r}")
            project = _project_from(req)
            audio = engine.synthesize(key, project)
            out = req.get("out")
            meta: Dict[str, Any] = {"bytes": len(audio), "model": key}
            if out:
                with open(out, "wb") as fh:
                    fh.write(audio)
                meta["saved_to"] = out
            return OK, envelope(OK, "synthesis complete", meta)
        return BAD_REQUEST, envelope(BAD_REQUEST, f"unknown action: {action!r}")


def _model_key(req: Dict[str, Any]) -> str:
    model = req.get("model")
    if isinstance(model, dict):
        return model.get("id") or model.get("name") or ""
    return str(model or "")


def _project_from(req: Dict[str, Any]) -> SynthProject:
    proj = req.get("project")
    if isinstance(proj, dict):
        return SynthProject.from_dict(proj)
    lyrics = req.get("lyrics") or req.get("text") or ""
    midi = int(req.get("midi", 60))
    dur = float(req.get("duration", 0.35))
    return SynthProject.from_lyrics(lyrics, midi=midi, duration=dur)


def _version() -> str:
    from .. import __version__
    return __version__


def run_server(
    host: str = "127.0.0.1", port: int = 8765, engine: Optional[VocaForgeEngine] = None
) -> None:
    _Handler._engine_instance = engine
    httpd = HTTPServer((host, port), _Handler)
    print(f"[VocaForge] Agent RPC listening on http://{host}:{port}  (POST /vf)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
