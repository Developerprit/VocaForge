"""VocaForge Architecture REST API gateway (stdlib http.server, zero extra deps).

Serves a versioned REST surface at ``/api/v1`` so external projects and websites
can integrate singing-voice synthesis. CORS is enabled for browser clients.

    GET  /api/v1/health
    GET  /api/v1/version
    GET  /api/v1/models
    POST /api/v1/models          (register a library)
    GET  /api/v1/models/{id}
    POST /api/v1/resolve         (id -> spec)
    POST /api/v1/synth           (-> audio/wav or JSON)
    GET  /api/v1/openapi.json

Run with:  python vf_cli.py api --host 0.0.0.0 --port 8080
"""
from __future__ import annotations

import base64
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from ..core.engine import VocaForgeEngine
from ..core.exceptions import VFModelNotFound, VocaForgeError
from ..models.manifest import ModelSpec
from ..synth.project import SynthProject
from .openapi import openapi_doc


CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    _engine_instance: Optional[VocaForgeEngine] = None

    # ---- engine ----
    def _engine(self) -> VocaForgeEngine:
        return _Handler._engine_instance or VocaForgeEngine()

    # ---- low-level send ----
    def _send_json(self, code: int, body: Dict[str, Any]) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _send_wav(self, code: int, data: bytes) -> None:
        self.send_response(code)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def log_message(self, *args: Any) -> None:  # silence default logging
        return

    # ---- routing ----
    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path, qs = self._split()
        if path in ("/api/v1/health",):
            self._send_json(200, self._health())
        elif path in ("/api/v1/version",):
            self._send_json(200, {"version": _version()})
        elif path in ("/api/v1/models",):
            engine = self._engine()
            specs = engine.list_models()
            self._send_json(200, {"count": len(specs), "models": [m.to_dict() for m in specs]})
        elif path.startswith("/api/v1/models/"):
            mid = path[len("/api/v1/models/"):]
            self._get_model(mid)
        elif path in ("/api/v1/openapi.json",):
            self._send_json(200, openapi_doc())
        else:
            self._send_json(404, {"error": "not found", "path": path})

    def do_POST(self):
        path, qs = self._split()
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            req = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError) as exc:
            self._send_json(400, {"error": f"invalid JSON: {exc}"})
            return

        if path in ("/api/v1/models",):
            self._post_model(req)
        elif path in ("/api/v1/resolve",):
            self._post_resolve(req)
        elif path in ("/api/v1/synth",):
            fmt = (qs.get("format") or [None])[0] or req.get("format", "json")
            self._post_synth(req, fmt)
        else:
            self._send_json(404, {"error": "not found", "path": path})

    # ---- helpers ----
    def _split(self) -> Tuple[str, Dict[str, list]]:
        parsed = urlparse(self.path)
        return parsed.path, parse_qs(parsed.query)

    def _health(self) -> Dict[str, Any]:
        engine = self._engine()
        return {
            "status": "ok",
            "version": _version(),
            "backends": engine.list_backends(),
            "loaders": engine.list_loaders(),
        }

    def _get_model(self, mid: str) -> None:
        engine = self._engine()
        try:
            spec = engine.resolve(mid)
        except VFModelNotFound:
            self._send_json(404, {"error": "model not found", "id": mid})
            return
        self._send_json(200, {"model": spec.to_dict()})

    def _post_model(self, req: Dict[str, Any]) -> None:
        engine = self._engine()
        # Convenience: if `path` points at a .vfvp, fill the spec from its info.json.
        path = req.get("path") or ""
        if isinstance(path, str) and path.lower().endswith(".vfvp"):
            try:
                spec = engine.registry.spec_from_vfvp(path)
                # Allow request fields to override the packaged meta (e.g. a display alias).
                spec = ModelSpec.from_dict({**spec.to_dict(), **req})
            except Exception as exc:  # noqa: BLE001
                self._send_json(400, {"error": f"invalid .vfvp: {exc}"})
                return
        else:
            try:
                spec = ModelSpec.from_dict(req)
            except Exception as exc:  # noqa: BLE001
                self._send_json(400, {"error": f"invalid model spec: {exc}"})
                return
        engine.add_model(spec)
        self._send_json(201, {"created": True, "model": spec.to_dict()})

    def _post_resolve(self, req: Dict[str, Any]) -> None:
        key = _model_key(req)
        engine = self._engine()
        try:
            spec = engine.resolve(key)
        except VFModelNotFound:
            self._send_json(404, {"error": "model not found", "model": key})
            return
        self._send_json(200, {"model": spec.to_dict()})

    def _post_synth(self, req: Dict[str, Any], fmt: str) -> None:
        key = _model_key(req)
        engine = self._engine()
        try:
            if req.get("project"):
                project = SynthProject.from_dict(req["project"])
            else:
                project = SynthProject.from_lyrics(
                    req.get("lyrics") or req.get("text") or "",
                    midi=int(req.get("midi", 60)),
                    duration=float(req.get("duration", 0.35)),
                )
            audio = engine.synthesize(key, project)
        except VFModelNotFound:
            self._send_json(404, {"error": "model not found", "model": key})
            return
        except VocaForgeError as exc:
            self._send_json(500, {"error": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001
            self._send_json(500, {"error": f"{type(exc).__name__}: {exc}"})
            return

        out = req.get("out")
        if out:
            with open(out, "wb") as fh:
                fh.write(audio)
        if fmt == "wav":
            self._send_wav(200, audio)
        else:
            self._send_json(200, {
                "ok": True,
                "sample_rate": project.sample_rate,
                "bytes": len(audio),
                "audio_base64": base64.b64encode(audio).decode("ascii"),
                "saved_to": out,
            })


def _model_key(req: Dict[str, Any]) -> str:
    model = req.get("model")
    if isinstance(model, dict):
        return model.get("id") or model.get("name") or ""
    return str(model or "")


def _version() -> str:
    from .. import __version__
    return __version__


def run_server(
    host: str = "0.0.0.0", port: int = 8080, engine: Optional[VocaForgeEngine] = None
) -> None:
    _Handler._engine_instance = engine
    httpd = HTTPServer((host, port), _Handler)
    print(f"[VocaForge] Architecture API listening on http://{host}:{port}  (/api/v1)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
