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
- **Zero heavy deps.** Core uses only the Python standard library; DiffSinger is an optional, lazy import.

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
| `vf-cli models` | List registered voice libraries |
| `vf-cli synth --model <id> --lyrics <text> --out <wav>` | Synthesize from lyrics |
| `vf-cli export --project <json> --model <id> --out <wav>` | Export from a project JSON |
| `vf-cli serve --host 127.0.0.1 --port 8765` | Start the Agent RPC server |

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

## Registering a real DiffSinger library

Add an entry to `models/manifest.json` and implement inference in `vocaforge/backends/diffsinger.py`:

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
│   ├── core/             # engine, backend interface, exceptions
│   ├── backends/         # diffsinger adapter + stub backend
│   ├── models/           # registry + manifest
│   ├── synth/            # SynthProject (notes/lyrics/durations)
│   ├── api/              # Agent RPC (404/103 protocol)
│   ├── cli/              # vf-cli
│   └── util/             # WAV encoder
├── vf_cli.py             # console entry point
├── build_vf_cli.py       # Nuitka build script
├── models/manifest.json  # local voice-library registry
├── examples/             # demo + rpc client
├── README.md / README-zh.md
├── LICENSE               # Available License
└── index.html            # public landing page
```

## License

[Available License](https://license.kscm.top/available.md)
