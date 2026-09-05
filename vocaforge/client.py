"""VocaForgeClient - thin Python client for the VocaForge Architecture REST API.

Zero-dependency (stdlib ``urllib``). Use this when your project integrates
VocaForge *remotely* (e.g. a website or service calls a running gateway) instead
of importing the library directly.

    from vocaforge.client import VocaForgeClient

    client = VocaForgeClient("http://127.0.0.1:8080")
    print(client.health())
    wav_bytes = client.synth(model="stub-zh", lyrics="你好世界", as_wav=True)
"""
from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional
from urllib import request as urllib_request
from urllib.error import HTTPError


class VocaForgeClient:
    """HTTP client for the ``/api/v1`` VocaForge Architecture API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ---- raw ----
    def _call(
        self, method: str, path: str, body: Optional[Dict[str, Any]] = None, accept: str = "application/json"
    ) -> tuple:
        url = self.base_url + path
        data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib_request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", accept)
        try:
            with urllib_request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except HTTPError as exc:  # surface status + body for callers to handle
            return exc.code, dict(exc.headers), exc.read()

    # ---- high level ----
    def health(self) -> Dict[str, Any]:
        _, _, raw = self._call("GET", "/api/v1/health")
        return json.loads(raw or b"{}")

    def version(self) -> Dict[str, Any]:
        _, _, raw = self._call("GET", "/api/v1/version")
        return json.loads(raw or b"{}")

    def list_models(self) -> List[Dict[str, Any]]:
        _, _, raw = self._call("GET", "/api/v1/models")
        return json.loads(raw or b"{}").get("models", [])

    def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        status, _, raw = self._call("GET", f"/api/v1/models/{model_id}")
        if status == 404:
            return None
        return json.loads(raw or b"{}").get("model")

    def resolve(self, model: str) -> Optional[Dict[str, Any]]:
        status, _, raw = self._call("POST", "/api/v1/resolve", {"model": model})
        if status == 404:
            return None
        return json.loads(raw or b"{}").get("model")

    def register_model(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        _, _, raw = self._call("POST", "/api/v1/models", spec)
        return json.loads(raw or b"{}")

    def synth(
        self,
        model: str,
        lyrics: Optional[str] = None,
        project: Optional[Dict[str, Any]] = None,
        midi: int = 60,
        duration: float = 0.35,
        out: Optional[str] = None,
        as_wav: bool = False,
    ) -> Any:
        """Synthesize. Returns raw WAV ``bytes`` when ``as_wav`` else a JSON dict.

        When ``as_wav`` is True the gateway is asked for ``audio/wav``; otherwise the
        JSON envelope (with ``audio_base64``) is returned and decoded here into bytes.
        """
        payload: Dict[str, Any] = {"model": model}
        if project is not None:
            payload["project"] = project
        else:
            payload["lyrics"] = lyrics or ""
            payload["midi"] = midi
            payload["duration"] = duration
        if out:
            payload["out"] = out

        if as_wav:
            status, headers, raw = self._call("POST", "/api/v1/synth?format=wav", payload, accept="audio/wav")
            if status == 404:
                raise VocaForgeClientError(f"model not found: {model}")
            if status != 200:
                raise VocaForgeClientError(f"synth failed ({status}): {raw.decode('utf-8', 'ignore')}")
            return raw

        status, _, raw = self._call("POST", "/api/v1/synth", payload)
        data = json.loads(raw or b"{}")
        if status == 404:
            raise VocaForgeClientError(f"model not found: {model}")
        if status != 200:
            raise VocaForgeClientError(f"synth failed ({status}): {data}")
        if "audio_base64" in data:
            data["audio"] = base64.b64decode(data["audio_base64"])
        return data


class VocaForgeClientError(Exception):
    """Raised when the gateway returns a non-success status."""
