"""vf-cli - command line interface for AI Agents to operate VocaForge.

All user-facing output is in English (per project convention).
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .. import __version__
from ..core.engine import VocaForgeEngine
from ..core.exceptions import VocaForgeError
from ..models.manifest import ModelSpec
from ..synth.project import SynthProject


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vf-cli", description="VocaForge command line interface (for AI Agents)."
    )
    p.add_argument("--version", action="version", version=f"vf-cli {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("info", help="show version and backend availability")

    models = sub.add_parser("models", help="list registered voice libraries")
    models.add_argument("action", nargs="?", default="list", choices=["list"])

    synth = sub.add_parser("synth", help="synthesize audio from lyrics/project")
    synth.add_argument("--model", required=True, help="model id or name")
    synth.add_argument("--lyrics", default=None, help="raw lyric text (one note per char)")
    synth.add_argument("--project", default=None, help="path to a project JSON file")
    synth.add_argument("--midi", type=int, default=60, help="base MIDI note for --lyrics")
    synth.add_argument("--duration", type=float, default=0.35, help="per-char duration (s)")
    synth.add_argument("--out", default=None, help="output WAV path")

    export = sub.add_parser("export", help="export audio from a project JSON file")
    export.add_argument("--project", required=True, help="path to project JSON")
    export.add_argument("--model", required=True, help="model id or name")
    export.add_argument("--out", default=None, help="output WAV path")

    serve = sub.add_parser("serve", help="start the Agent RPC server")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    arch = sub.add_parser("api", help="start the Architecture REST gateway (/api/v1)")
    arch.add_argument("--host", default="0.0.0.0")
    arch.add_argument("--port", type=int, default=8080)

    return p


def _print_json(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _dummy_spec() -> ModelSpec:
    return ModelSpec(id="_probe", name="probe", type="synthesizer", path="", backend="diffsinger")


def cmd_info(args) -> int:
    from ..backends.diffsinger import DiffSingerAdapter
    try:
        DiffSingerAdapter().load_model(_dummy_spec())
        ds = "available"
    except VocaForgeError as e:
        ds = f"unavailable: {e}"
    _print_json({
        "tool": "vf-cli",
        "version": __version__,
        "python": sys.version.split()[0],
        "diffsinger_backend": ds,
        "stub_backend": "available",
    })
    return 0


def cmd_models(args) -> int:
    engine = VocaForgeEngine()
    specs = engine.list_models()
    if not specs:
        print("no registered models. add one to models/manifest.json")
        return 0
    _print_json({"count": len(specs), "models": [s.to_dict() for s in specs]})
    return 0


def _load_project_file(path: str) -> SynthProject:
    with open(path, "r", encoding="utf-8") as fh:
        return SynthProject.from_dict(json.load(fh))


def cmd_synth(args) -> int:
    engine = VocaForgeEngine()
    try:
        if args.project:
            project = _load_project_file(args.project)
        else:
            project = SynthProject.from_lyrics(
                args.lyrics or "", midi=args.midi, duration=args.duration
            )
        audio = engine.synthesize(args.model, project)
    except VocaForgeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.out:
        with open(args.out, "wb") as fh:
            fh.write(audio)
        print(f"ok: wrote {len(audio)} bytes to {args.out}")
    else:
        print(f"ok: synthesized {len(audio)} bytes (pass --out to write a WAV)")
    return 0


def cmd_export(args) -> int:
    engine = VocaForgeEngine()
    try:
        project = _load_project_file(args.project)
        audio = engine.synthesize(args.model, project)
    except VocaForgeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    out = args.out or (args.project.rsplit(".", 1)[0] + ".wav")
    with open(out, "wb") as fh:
        fh.write(audio)
    print(f"ok: exported {len(audio)} bytes to {out}")
    return 0


def cmd_serve(args) -> int:
    from ..api.server import run_server
    try:
        run_server(host=args.host, port=args.port)
    except KeyboardInterrupt:
        pass
    return 0


def cmd_api(args) -> int:
    from ..api.arch import run_server as run_arch
    try:
        run_arch(host=args.host, port=args.port)
    except KeyboardInterrupt:
        pass
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "info": cmd_info,
        "models": cmd_models,
        "synth": cmd_synth,
        "export": cmd_export,
        "serve": cmd_serve,
        "api": cmd_api,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
