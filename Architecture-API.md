# VocaForge Architecture API

> Version: 1.0 (targets VocaForge `>=0.3.0`)
> Audience: developers integrating VocaForge into their own project or calling it over HTTP.

VocaForge is a *framework*, not a closed app. The Architecture API is the stable,
documented surface other projects build on. It has two parts:

1. **Public Python contracts** — `Backend` and `ModelLoader`, the two extension points
   you implement to plug a custom synthesis engine / model storage into VocaForge.
2. **REST gateway** (`/api/v1`) — a versioned HTTP surface so external services and
   websites can integrate VocaForge remotely.

Design decisions (per project brief): **no plugin auto-discovery**. You integrate
*actively* — import the library, subclass, and register. This keeps wiring explicit and
debuggable.

---

## 1. Public Python contracts

### 1.1 `Backend` — synthesis engine (extension point #1)

```python
from abc import ABC
from vocaforge import Backend, ModelArtifact, SynthProject

class MyBackend(Backend):
    name = "myengine"      # stable id; selectable via ModelSpec.backend
    api_version = "1.0"    # bump when load_model/synthesize/unload change

    def load_model(self, artifact: ModelArtifact):
        # artifact.spec  -> ModelSpec (metadata)
        # artifact.assets -> resolved storage (e.g. {"root": "/models/x"})
        return {"spec": artifact.spec, "assets": artifact.assets}

    def synthesize(self, project: SynthProject, handle) -> bytes:
        # Return 16-bit PCM WAV bytes (use vocaforge.util.audio.float_to_wav_bytes).
        ...

    def unload(self, handle) -> None:
        ...
```

Register and use:

```python
from vocaforge import VocaForgeEngine, ModelSpec

engine = VocaForgeEngine()
engine.register_backend(MyBackend())
engine.add_model(ModelSpec(id="x", name="X", type="synthesizer", path="", backend="myengine"))
wav: bytes = engine.synthesize("x", SynthProject.from_lyrics("hi"))
```

The built-in `StubBackend` (runnable without models) and `DiffSingerAdapter` (real
inference, lazy-imports `diffsinger`) both implement this contract.

### 1.2 `ModelLoader` — model storage resolver (extension point #2)

Separates *where the model lives* from *how to run inference*. Implement to load from a
database, object store, encrypted pack, etc.

```python
from vocaforge import ModelLoader, ModelArtifact, ModelSpec

class DbModelLoader(ModelLoader):
    name = "db"

    def load(self, spec: ModelSpec) -> ModelArtifact:
        # resolve spec -> concrete assets, then wrap.
        return ModelArtifact(spec=spec, assets={"root": spec.path}, meta={"src": "db"})

    def release(self, artifact: ModelArtifact) -> None:
        # free temp files / handles here.
        ...

engine.register_model_loader(DbModelLoader())
```

**Loader routing.** The engine keeps an ordered chain of loaders and sends each spec to
the first loader whose `supports(spec)` returns `True` (override it to narrow a loader to
certain specs — the base returns `True`). Registering a loader appends it to the chain.

**Built-in loaders.**
- `LocalModelLoader` (default) — validates that `spec.path` exists on disk (an empty path
  is allowed — e.g. the stub backend needs no weights).
- `VfvpModelLoader` — handles `spec.path` ending in `.vfvp` (the standard-7z voice-library
  package): extracts to a temp dir and exposes the canonical assets below. Registered by
  default; `engine.discover(dir)` / `vf-cli models` auto-scan a directory for `*.vfvp` and
  register them from their `info.json`.

### 1.3 `ModelArtifact`

The object passed from `ModelLoader.load()` to `Backend.load_model()`.

| Field | Type | Meaning |
|-------|------|---------|
| `spec` | `ModelSpec` | the registered library metadata |
| `assets` | `dict` | resolved storage (paths / URIs / handles) |
| `meta` | `dict` | loader-provided extras (e.g. `{"src": "db"}`) |

**Assets produced for a `.vfvp` package** (`VfvpModelLoader`):

| Key | Extracted file |
|-----|----------------|
| `root` | temp extraction dir |
| `acoustic` | `model/acoustic.pth` |
| `vocoder` | `model/vocoder.pth` |
| `config` | `model/config.json` |
| `phoneme_map` | `phoneme_map.json` |
| `info` | `info.json` |

A `Backend` implementing real DiffSinger inference reads these paths from
`artifact.assets` (see `DiffSingerAdapter.load_model`).

### 1.4 `VocaForgeEngine` public methods

| Method | Purpose |
|--------|---------|
| `register_backend(backend)` | plug a custom `Backend` (selected by `backend.name`) |
| `register_model_loader(loader)` | append a custom `ModelLoader` to the routing chain |
| `list_loaders()` | names of loaders in the routing chain |
| `discover(dir=None)` | scan `dir` (default: manifest dir) for `*.vfvp` and register them |
| `add_model(spec)` | register a voice library at runtime |
| `resolve(key)` / `exists(key)` | look up a library by id or name |
| `list_models()` / `list_backends()` | enumerate |
| `synthesize(model_key, project)` | full pipeline → WAV bytes |

---

## 2. REST gateway (`/api/v1`)

Start it with `vf-cli api` (stdlib `http.server`, zero extra deps, CORS enabled):

```bash
vf-cli api --host 0.0.0.0 --port 8080
```

### 2.1 Endpoints

| Method | Path | Purpose | Success | Not-found |
|--------|------|---------|---------|-----------|
| GET | `/api/v1/health` | liveness + capabilities | 200 | — |
| GET | `/api/v1/version` | framework version | 200 | — |
| GET | `/api/v1/models` | list libraries | 200 | — |
| POST | `/api/v1/models` | register a library | 201 | — |
| GET | `/api/v1/models/{id}` | one spec | 200 | 404 |
| POST | `/api/v1/resolve` | resolve id → spec | 200 | 404 |
| POST | `/api/v1/synth` | synthesize → WAV | 200 | 404 |
| GET | `/api/v1/openapi.json` | OpenAPI 3.0 document | 200 | — |

> `POST /api/v1/models` accepts either a full `ModelSpec` JSON **or** just a
> `{"path": "/x/voice.vfvp"}` — in the latter case the spec is filled from the package's
> `info.json` automatically.

### 2.2 `synth` details

Request body:

```json
{ "model": "stub-zh", "lyrics": "你好世界", "midi": 60, "duration": 0.35,
  "project": null, "out": null }
```

- Supply `lyrics` (one note per character) **or** `project` (a `SynthProject` dict).
- `out` (server-side path) writes the WAV file on the host; the JSON response also
  reports `saved_to`.
- Response format:
  - `?format=wav` **or** `Accept: audio/wav` → raw `audio/wav` bytes.
  - otherwise → JSON: `{"ok": true, "sample_rate": 44100, "bytes": N, "audio_base64": "..."}`.

### 2.3 Errors

| HTTP | Meaning |
|------|---------|
| 400 | malformed JSON / invalid model spec |
| 404 | model not found in the registry |
| 500 | synthesis failed (see `error` field) |

> Note: the simpler Agent RPC (`POST /vf`, started by `vf-cli serve`) uses the 404/103/200
> envelope convention. The REST gateway uses standard HTTP semantics (200/404/500).

### 2.4 CORS

All responses include `Access-Control-Allow-Origin: *` so browser/website clients can
call the gateway directly. For production, put it behind nginx and tighten the origin.

---

## 3. Client SDK

`vocaforge.client.VocaForgeClient` is a zero-dependency HTTP client (stdlib `urllib`).
Use it when your service integrates VocaForge remotely instead of importing it.

```python
from vocaforge.client import VocaForgeClient

client = VocaForgeClient("http://127.0.0.1:8080")
print(client.health())
models = client.list_models()
wav: bytes = client.synth(model="stub-zh", lyrics="你好世界", as_wav=True)
spec = client.resolve("stub-zh")
client.register_model({"id": "x", "name": "X", "type": "synthesizer", "path": "", "backend": "stub"})
```

---

## 4. Versioning

- Python contract: `Backend.api_version` (currently `"1.0"`). Bump when the
  `load_model` / `synthesize` / `unload` signature changes; old backends stay loadable.
- REST: URL-prefixed (`/api/v1`). New breaking changes get a new prefix (`/api/v2`).
- OpenAPI doc is served live at `/api/v1/openapi.json` — generate clients/UI from it.

---

## 5. Integration patterns

| You are… | Use |
|----------|-----|
| A Python project wanting custom inference | implement `Backend` (+ optional `ModelLoader`), register on `VocaForgeEngine` |
| A Python service calling a running VocaForge | `VocaForgeClient` over HTTP |
| A website / frontend | `fetch()` the REST gateway (CORS on), or proxy through your backend |
| An Agent | `vf-cli` (English) or the Agent RPC `POST /vf` |
