"""Example: a third-party service/website integrating via the REST gateway.

Spin up the Architecture REST API in-process, then call it through
:class:`vocaforge.client.VocaForgeClient` -- exactly how an external website or
microservice would integrate VocaForge over HTTP.

Run:  python examples/integrate_rest_client.py
"""
from __future__ import annotations

import threading
import time

from http.server import HTTPServer

from vocaforge.api.arch import _Handler
from vocaforge.client import VocaForgeClient


def main() -> None:
    # 1) Start the gateway on an auto-assigned port (a host would run this as a
    #    service, or behind nginx). We bind once to learn the port.
    httpd = HTTPServer(("127.0.0.1", 0), _Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.4)  # let it bind

    # 2) A third-party client integrates over HTTP.
    client = VocaForgeClient(f"http://127.0.0.1:{port}")
    print("health:", client.health())
    print("models:", [m["id"] for m in client.list_models()])

    wav = client.synth(model="stub-zh", lyrics="远程接入成功", as_wav=True)
    out = "examples/rest_client_demo.wav"
    with open(out, "wb") as fh:
        fh.write(wav)
    print(f"[OK] REST client synthesized {len(wav)} bytes -> {out}")


if __name__ == "__main__":
    main()
