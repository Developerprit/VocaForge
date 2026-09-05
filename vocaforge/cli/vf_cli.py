"""vf-cli - command line interface for AI Agents to operate VocaForge.

All user-facing output is in English (per project convention).
"""
from __future__ import annotations

import argparse
import json
import os
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

    models = sub.add_parser("models", help="list/register/remove voice libraries")
    models_sub = models.add_subparsers(dest="models_action", required=False)
    models_sub.add_parser("list", help="list registered libraries")
    models_add = models_sub.add_parser("add", help="register a .vfvp package")
    models_add.add_argument("path", help="path to a .vfvp file")
    models_remove = models_sub.add_parser("remove", help="remove a registered library by id/name")
    models_remove.add_argument("key", help="model id or name")

    package = sub.add_parser("package", help="pack a folder into a .vfvp (7z) voice library")
    package.add_argument("--source", required=True, help="source folder with model/, info.json, phoneme_map.json")
    package.add_argument("--out", default=None, help="output .vfvp path (default: <source>.vfvp)")
    package.add_argument("--overwrite", action="store_true", help="overwrite an existing output file")

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

    midi = sub.add_parser("midi", help="MIDI: edit / generate / render into voice")
    midi_sub = midi.add_subparsers(dest="midi_action", required=True)

    m_info = midi_sub.add_parser("info", help="show MIDI file info")
    m_info.add_argument("midi", help="path to a .mid file")

    m_gen = midi_sub.add_parser("gen", help="generate a .mid file")
    m_gen.add_argument("--notes", default=None, help="pitch duration pairs, e.g. 'C4 0.4 E4 0.4 G4 0.4'")
    m_gen.add_argument("--project", default=None, help="generate from a project JSON instead of --notes")
    m_gen.add_argument("--lyrics", default=None, help="optional lyrics (one char per note)")
    m_gen.add_argument("--bpm", type=float, default=120.0, help="tempo in BPM")
    m_gen.add_argument("--name", default="melody")
    m_gen.add_argument("--out", default=None, help="output .mid path (default: <name>.mid)")

    m_edit = midi_sub.add_parser("edit", help="edit a .mid file")
    m_edit.add_argument("--midi", required=True, help="input .mid path")
    m_edit.add_argument("--out", required=True, help="output .mid path")
    m_edit.add_argument("--transpose", type=int, default=0, help="shift notes by semitones")
    m_edit.add_argument("--tempo", type=float, default=None, help="new BPM")
    m_edit.add_argument("--rate", type=float, default=None, help="time multiplier (>1 slows down)")
    m_edit.add_argument("--clip", default=None, help="keep window [start:end] in seconds, e.g. 1.5:3")
    m_edit.add_argument("--lyrics", default=None, help="reassign lyrics (one char per note)")

    m_render = midi_sub.add_parser("render", help="render a MIDI into singing WAV via a voice model")
    m_render.add_argument("--midi", required=True, help="input .mid path")
    m_render.add_argument("--model", default="stub-zh", help="voice library id (default: stub-zh)")
    m_render.add_argument("--lyrics", default=None, help="optional lyrics (one char per note)")
    m_render.add_argument("--out", default=None, help="output WAV path (default: <midi>.wav)")

    m_export = midi_sub.add_parser("export", help="export a MIDI to a project JSON")
    m_export.add_argument("--midi", required=True, help="input .mid path")
    m_export.add_argument("--lyrics", default=None, help="optional lyrics (one char per note)")
    m_export.add_argument("--out", default=None, help="output project JSON path")

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
    action = getattr(args, "models_action", None) or "list"
    if action == "add":
        return _cmd_models_add(args)
    if action == "remove":
        return _cmd_models_remove(args)
    # default: list (auto-discover *.vfvp in the models dir)
    engine = VocaForgeEngine()
    engine.discover()
    specs = engine.list_models()
    if not specs:
        print("no registered models. add one with: vf-cli models add <path.vfvp>")
        return 0
    _print_json({"count": len(specs), "models": [s.to_dict() for s in specs]})
    return 0


def _cmd_models_add(args) -> int:
    engine = VocaForgeEngine()
    try:
        spec = engine.registry.spec_from_vfvp(args.path)
    except VocaForgeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    engine.add_model(spec)
    _print_json({"added": True, "model": spec.to_dict()})
    return 0


def _cmd_models_remove(args) -> int:
    engine = VocaForgeEngine()
    try:
        engine.registry.remove(args.key)
    except Exception as e:  # noqa: BLE001
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"ok: removed {args.key}")
    return 0


def cmd_package(args) -> int:
    from ..vfvp import VfvpPackage, VfvpError

    out = args.out or (os.path.splitext(args.source)[0] + ".vfvp")
    try:
        pkg = VfvpPackage.create(args.source, out, overwrite=args.overwrite)
    except VfvpError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    rep = pkg.report()
    print(f"ok: packaged {args.source} -> {out}")
    print(f"    valid: {rep['valid']}  members: {len(rep['members'])}")
    if not rep["valid"]:
        print(f"    missing: {rep['missing']}")
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


# ---- midi ----------------------------------------------------------------
def cmd_midi(args) -> int:
    fn = {
        "info": _cmd_midi_info,
        "gen": _cmd_midi_gen,
        "edit": _cmd_midi_edit,
        "render": _cmd_midi_render,
        "export": _cmd_midi_export,
    }[args.midi_action]
    return fn(args)


def _cmd_midi_info(args) -> int:
    from ..midi import MidiError, read_midi

    try:
        mf = read_midi(args.midi)
    except (MidiError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    _print_json(mf.to_dict())
    return 0


def _cmd_midi_gen(args) -> int:
    from ..midi import MidiError, MidiFile, MidiNote, midi_from_project, parse_seq

    try:
        if args.project:
            mf = midi_from_project(_load_project_file(args.project),
                                   tempo_bpm=args.bpm, name=args.name)
        elif args.notes:
            seq = parse_seq(args.notes)
            cursor = 0.0
            mf = MidiFile(tempo=int(60_000_000 / args.bpm), name=args.name)
            for midi, dur in seq:
                mf.notes.append(MidiNote(midi=midi, start=cursor, duration=dur))
                cursor += dur
            if args.lyrics:
                mf.set_lyrics(args.lyrics)
        else:
            print("error: provide --notes or --project", file=sys.stderr)
            return 1
        out = args.out or f"{args.name}.mid"
        mf.write(out)
    except (MidiError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    _print_json({"ok": True, "file": out, "name": mf.name, "notes": len(mf.notes),
                 "bpm": round(mf.bpm, 2), "duration": round(mf.duration, 3)})
    return 0


def _cmd_midi_edit(args) -> int:
    from ..midi import MidiError, read_midi

    try:
        mf = read_midi(args.midi)
        if args.transpose:
            mf.transpose(args.transpose)
        if args.rate is not None:
            mf.retime(args.rate)
        if args.tempo is not None:
            mf.set_tempo(args.tempo)
        if args.clip:
            parts = args.clip.split(":")
            start = float(parts[0])
            end = float(parts[1]) if len(parts) > 1 else None
            mf.trim(start, end)
        if args.lyrics:
            mf.set_lyrics(args.lyrics)
        mf.write(args.out)
    except (MidiError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    _print_json({"ok": True, "file": args.out, "name": mf.name, "notes": len(mf.notes),
                 "bpm": round(mf.bpm, 2), "duration": round(mf.duration, 3)})
    return 0


def _cmd_midi_render(args) -> int:
    from ..midi import render_midi

    out = args.out or (os.path.splitext(args.midi)[0] + ".wav")
    try:
        audio = render_midi(args.midi, model=args.model, lyrics=args.lyrics, out=out)
    except VocaForgeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(f"ok: rendered {len(audio)} bytes to {out}  (model: {args.model})")
    return 0


def _cmd_midi_export(args) -> int:
    from ..midi import MidiError, midi_to_project, read_midi

    try:
        mf = read_midi(args.midi)
        base = os.path.splitext(os.path.basename(args.midi))[0]
        proj = midi_to_project(mf, lyrics=args.lyrics, name=base)
        out = args.out or (os.path.splitext(args.midi)[0] + ".project.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(proj.to_dict(), fh, ensure_ascii=False, indent=2)
    except (MidiError, ValueError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"ok: exported {len(proj.notes)} notes to {out}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "info": cmd_info,
        "models": cmd_models,
        "package": cmd_package,
        "synth": cmd_synth,
        "export": cmd_export,
        "serve": cmd_serve,
        "api": cmd_api,
        "midi": cmd_midi,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
