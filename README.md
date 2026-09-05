# VocaForge

> [中文文档 / Chinese](./README-zh.md)

A **pure Python framework** wrapping [DiffSinger](https://github.com/openvpi/DiffSinger) for AI singing
voice synthesis — with no GUI and no console window — plus `vf-cli`, a command line tool for AI Agents
to operate VocaForge.

```text
Agent / CLI  ──JSON──►  VocaForgeEngine  ──►  ModelRegistry (models/manifest.json)
                                    │                │  get(key) -> ModelSpec | raise 404
                                    ▼
                              Backend (pluggable)
                                ├── DiffSingerAdapter  (real inference; lazy-imports diffsinger)
                                └── StubBackend        (runnable without models / GPU)
                                    │
                                    ▼
                              Audio (WAV bytes)
```

## Why VocaForge

- **Pure library, no console.** `import vocaforge` from any Python process. Nothing pops up a window.
- **Pluggable backend.** Wire real DiffSinger inference through `DiffSingerAdapter` on GPU machines;
  `StubBackend` keeps the framework fully runnable (and testable) with zero models.
- **Agent-friendly.** `vf-cli` (English output) and an HTTP RPC (`POST /vf`) let an AI Agent list voice
  libraries, resolve a model (404 if missing, 103 if loaded), and synthesize audio.
- **MIDI in, voice out.** Edit or generate Standard MIDI Files (stdlib SMF reader/writer), then
  render the melody through a voice library into a singing WAV.
- **Zero heavy deps.** Core uses only the Python standard library; DiffSinger and
  `py7zr` (needed for the `.vfvp` voice-library format) are optional, lazy imports.

## Install

```bash
pip install -e .        # installs the `vocaforge` package + `vf-cli` script
# or just run it without installing:
python vf_cli.py --help
```

Requires Python 3.9+. DiffSinger is **not** required to use the framework or the stub backend.

## Quick start (library)

```python
from vocaforge import VocaForgeEngine
from vocaforge.synth.project import Note, SynthProject

engine = VocaForgeEngine()                       # reads models/manifest.json
project = SynthProject(notes=[
    Note("do", 60, 0.4), Note("re", 62, 0.4),
    Note("mi", 64, 0.4), Note("fa", 65, 0.5),
])
audio: bytes = engine.synthesize("stub-zh", project)   # 16-bit PCM WAV bytes
with open("out.wav", "wb") as fh:
    fh.write(audio)
```

## vf-cli (English output)

| Command | Description |
|---------|-------------|
| `vf-cli info` | Show version, Python, and backend availability |
| `vf-cli models` | List registered voice libraries (auto-scans `*.vfvp`) |
| `vf-cli models add <path.vfvp>` | Register a `.vfvp` package (reads its `info.json`) |
| `vf-cli models remove <id>` | Remove a registered library |
| `vf-cli package --source <dir> --out <x.vfvp>` | Pack a folder into a `.vfvp` library |
| `vf-cli synth --model <id> --lyrics <text> --out <wav>` | Synthesize from lyrics |
| `vf-cli export --project <json> --model <id> --out <wav>` | Export from a project JSON |
| `vf-cli serve --host 127.0.0.1 --port 8765` | Start the Agent RPC server |
| `vf-cli api --host 0.0.0.0 --port 8080` | Start the Architecture REST gateway (`/api/v1`) |
| `vf-cli midi info|gen|edit|render|export ...` | MIDI: inspect / generate / edit, render into voice |

```bash
vf-cli synth --model stub-zh --lyrics "你好世界" --out hello.wav
```

## Agent RPC

`vf-cli serve` starts an HTTP server (stdlib `http.server`, zero extra deps).
Send `POST /vf` with a JSON body:

```json
{ "action": "synth", "model": { "id": "stub-zh" }, "lyrics": "测试", "out": "rpc.wav" }
```

Status contract (read `code` from the JSON envelope; HTTP 103 is informational and cannot be a terminal
status, so 103 is surfaced inside the envelope):

| HTTP | `code` | Meaning |
|------|--------|---------|
| 404 | 404 | model not found in the registry |
| 200 | 103 | model found and loaded |
| 200 | 200 | success (e.g. synthesis complete) |

Actions: `info`, `models`, `resolve`/`load`, `synth`.

## Voice libraries (`.vfvp`)

A voice library is distributed as a **`.vfvp` package — a standard 7z archive** with a
fixed layout (open it with 7-Zip / py7zr, it is a normal `.7z`):

```text
voice.vfvp  (= standard .7z)
├── model/
│   ├── acoustic.pth      # DiffSinger acoustic model
│   ├── vocoder.pth       # vocoder
│   └── config.json       # model structure config
├── info.json             # library meta: id/name/type/lang/sample_rate/backend/...
└── phoneme_map.json      # phoneme -> token mapping
```

`info.json` drives registration, so you never hand-write a manifest entry: drop a
`.vfvp` into `models/` and it is auto-discovered, or register it explicitly.

```bash
# build a library from a folder that follows the layout above
vf-cli package --source ./voice_dir --out voice.vfvp

# register + list (reads info.json for you)
vf-cli models add voice.vfvp
vf-cli models

# or from Python
from vocaforge import VfvpPackage, VocaForgeEngine
VfvpPackage.create("./voice_dir", "voice.vfvp")
engine = VocaForgeEngine()
engine.registry.spec_from_vfvp("voice.vfvp")   # -> ModelSpec filled from info.json
```

Loading is handled by `VfvpModelLoader` (registered in the engine by default): when a
registered `ModelSpec.path` ends with `.vfvp`, the engine routes it there, extracts the
archive to a temp dir and hands `Backend.load_model` canonical assets
(`acoustic` / `vocoder` / `config` / `phoneme_map` / `info`).

> Requires `pip install py7zr` (or `pip install "vocaforge[vfvp]"`). The core stays
> dependency-free — 7z support is loaded only when a `.vfvp` is actually packed or loaded.
> See `examples/vfvp_demo.py` for the full pack → validate → load → synthesize flow.

## MIDI — edit · generate · render into voice

VocaForge reads, writes and edits **Standard MIDI Files** with a hand-rolled, stdlib-only
SMF codec (`vocaforge/midi/`), then hands the melody to a voice backend to produce a
singing WAV. Notes are exposed in absolute seconds; lyrics are embedded as standard
lyric meta events (`FF 05`) and survive round-trips.

```python
from vocaforge import (
    MidiFile, MidiNote, read_midi, parse_seq,
    midi_from_project, midi_to_project, render_midi,
)
from vocaforge.synth.project import Note, SynthProject

# generate from note names
mf = MidiFile(notes=[MidiNote(midi=60, start=0.0, duration=0.5),
                     MidiNote(midi=64, start=0.5, duration=0.5)])
mf.write("hello.mid")

# edit: transpose + re-tempo, then render into a singing WAV
mf = read_midi("hello.mid").transpose(2).set_tempo(130)
wav: bytes = render_midi(mf, model="stub-zh", out="hello.wav")

# or bridge with a SynthProject (rests become silence)
proj = SynthProject(notes=[Note("小", 60, 0.5), Note("星", 60, 0.5)])
render_midi(midi_from_project(proj, tempo_bpm=100), model="stub-zh", out="twinkle.wav")
```

```bash
# generate -> edit -> render (all English output)
vf-cli midi gen --notes "C4 0.4 E4 0.4 G4 0.4 C5 0.6" --lyrics "你好世界" \
        --bpm 110 --name hello --out hello.mid
vf-cli midi info  hello.mid
vf-cli midi edit --midi hello.mid --transpose 2 --tempo 130 --out hi.mid
vf-cli midi render --midi hello.mid --model stub-zh --out hello.wav
vf-cli midi export --midi hello.mid --out hello.project.json   # back to SynthProject JSON
```

`MidiFile` editing methods: `transpose`, `set_tempo` / `retime`, `trim`, `set_lyrics`.
See `examples/midi_demo.py` for a full round-trip demo.

## Architecture API (let others integrate)

VocaForge is a framework others can **build on**. The Architecture API exposes two
public extension points and a versioned REST gateway.

**Extension point 1 — `Backend` (synthesis engine).** Implement it and register on the
engine; no auto-discovery, your project wires it in explicitly.

```python
from vocaforge import Backend, VocaForgeEngine, ModelSpec, SynthProject

class MyBackend(Backend):
    name = "myengine"
    api_version = "1.0"
    def load_model(self, artifact):        # artifact: ModelArtifact
        return {"spec": artifact.spec}
    def synthesize(self, project, handle):
        ...                                # -> 16-bit PCM WAV bytes
    def unload(self, handle):
        pass

engine = VocaForgeEngine()
engine.register_backend(MyBackend())
engine.add_model(ModelSpec(id="x", name="X", type="synthesizer", path="", backend="myengine"))
```

**Extension point 2 — `ModelLoader` (model storage resolver).** Decouples *where models
live* from *how to infer*. Implement to load from a DB, object store, or encrypted pack.

```python
from vocaforge import ModelLoader, ModelArtifact

class DbModelLoader(ModelLoader):
    name = "db"
    def load(self, spec):  return ModelArtifact(spec=spec, assets={"root": spec.path})
    def release(self, artifact):  pass

engine.register_model_loader(DbModelLoader())
```

**REST gateway (`/api/v1`).** Start it and let external services/websites call VocaForge
over HTTP (CORS enabled, OpenAPI 3.0 served at `/api/v1/openapi.json`).

| Method | Path | Purpose | Not-found |
|--------|------|---------|-----------|
| GET | `/api/v1/health` | liveness + capabilities | — |
| GET | `/api/v1/version` | framework version | — |
| GET | `/api/v1/models` | list libraries | — |
| POST | `/api/v1/models` | register a library | — |
| GET | `/api/v1/models/{id}` | one library spec | 404 |
| POST | `/api/v1/resolve` | resolve id → spec | 404 |
| POST | `/api/v1/synth` | synthesize → WAV (raw or JSON) | 404 |
| GET | `/api/v1/openapi.json` | OpenAPI document | — |

```bash
vf-cli api --host 0.0.0.0 --port 8080
curl -X POST http://127.0.0.1:8080/api/v1/synth?format=wav \
     -H 'Content-Type: application/json' \
     -d '{"model":"stub-zh","lyrics":"你好世界"}' -o out.wav
```

**Client SDK** (zero deps) for remote integration from Python:

```python
from vocaforge.client import VocaForgeClient
client = VocaForgeClient("http://127.0.0.1:8080")
wav: bytes = client.synth(model="stub-zh", lyrics="你好世界", as_wav=True)
```

Full contract, versioning, and integration guide: [Architecture-API.md](./Architecture-API.md).

## Registering a real DiffSinger library

The recommended path is a `.vfvp` package (see above): pack your acoustic/vocoder
checkpoints into one, then register it — no manifest hand-editing:

```bash
vf-cli package --source ./my_lib_dir --out my-lib.vfvp
vf-cli models add my-lib.vfvp
```

Manifest entries are still supported for raw (non-packaged) layouts:

```json
{
  "id": "my-lib",
  "name": "My DiffSinger Library",
  "type": "synthesizer",
  "path": "E:/models/my_lib",
  "sample_rate": 44100,
  "lang": "zh",
  "backend": "diffsinger",
  "extra": { "acoustic": "exp/acoustic", "vocoder": "exp/vocoder" }
}
```

Then `pip install diffsinger` and fill in `DiffSingerAdapter.synthesize()`.

## Packaging `vf-cli.exe` (Nuitka)

On a machine with a C compiler (MSVC or MinGW-w64):

```bash
pip install nuitka
python build_vf_cli.py        # -> dist/vf-cli.exe
```

Nuitka is used (per the ctn.exe workflow) to avoid Defender `Wacatac` false positives. The sandbox used
to author VocaForge had no C compiler, so the executable is built on the dev machine.

## Project layout

```
VocaForge/
├── vocaforge/            # the framework library
│   ├── core/             # engine, backend interface, model loader chain, exceptions
│   ├── backends/         # diffsinger adapter + stub backend
│   ├── models/           # registry + manifest + .vfvp discovery
│   ├── synth/            # SynthProject (notes/lyrics/durations)
│   ├── midi/             # SMF codec (stdlib): MidiFile, editors, project bridge, render
│   ├── api/              # Agent RPC (404/103) + Architecture REST (/api/v1) + OpenAPI
│   ├── cli/              # vf-cli
│   ├── client.py         # VocaForgeClient (REST client SDK)
│   ├── vfvp.py           # .vfvp voice-library format (7z) pack/load/validate
│   └── util/             # WAV encoder
├── vf_cli.py             # console entry point
├── build_vf_cli.py       # Nuitka build script
├── models/manifest.json  # local voice-library registry
├── examples/             # demo + rpc client + integration + .vfvp examples
├── README.md / README-zh.md
├── LICENSE               # Available License
└── index.html            # public landing page
```

## License

[Available License](https://license.kscm.top/available.md)
