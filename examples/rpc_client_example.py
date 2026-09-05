"""Example Agent RPC client + self-check for VocaForge.

Starts the RPC server on a background thread, then exercises the 404/103/200
protocol with urllib. Run:  python examples/rpc_client_example.py
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

from vocaforge.api.server import _Handler
from vocaforge.core.engine import VocaForgeEngine


def main() -> None:
    engine = VocaForgeEngine()
    _Handler._engine_instance = engine
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)  # port 0 -> OS assigns a free port
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}/vf"

    def post(action: str, payload: dict):
        body = json.dumps({"action": action, **payload}).encode()
        req = urllib.request.Request(
            base, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    print("info      ", post("info", {}))
    print("models    ", post("models", {}))
    print("resolve 103", post("resolve", {"model": {"id": "stub-zh"}}))
    print("resolve 404", post("resolve", {"model": {"id": "nope"}}))
    print("synth 200  ", post("synth", {"model": {"id": "stub-zh"}, "lyrics": "测试", "out": "examples/rpc_test.wav"}))
    print("synth 404  ", post("synth", {"model": {"id": "nope"}, "lyrics": "x"}))

    httpd.shutdown()
    httpd.server_close()


if __name__ == "__main__":
    main()
