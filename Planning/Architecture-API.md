# Planning · VocaForge Architecture API

> Status: planned · Owner: 小织 (Weave) · Date: 2026-09-05
> Parent project: VocaForge (pure Python DiffSinger framework)

## 1. Why this exists

VocaForge shipped as a *pure framework* (import `vocaforge`) + `vf-cli` + an Agent
RPC (`POST /vf`). That is enough to *use* VocaForge internally, but other projects
cannot yet **plug into it** in a stable, documented way.

The Architecture API turns VocaForge into something third parties can build *on*:

- **Other projects actively integrate** (not "plugins auto-discovered"). They
  `import vocaforge`, implement a `Backend` (synthesis engine) and/or a
  `ModelLoader` (model storage resolver), and register them — or they call VocaForge
  over HTTP from their own service / website.
- Two extension points only: **`Backend`** and **`ModelLoader`** (per decision q-2).
- Primary surface: **HTTP/REST gateway** (decision q-0). A documented public Python
  contract backs it (decision q-1: not a plugin system, a contract others code against).

## 2. Architecture

```
 third-party project / website / service
            │  HTTP/REST            │  or  import vocaforge
            ▼                       ▼
 ┌─────────────────────────┐   ┌──────────────────────────────┐
 │  Architecture REST API  │   │  VocaForgeEngine (public API) │
 │  /api/v1  (CORS, OA3)   │   │  register_backend()           │
 └───────────┬─────────────┘   │  register_model_loader()      │
             │                 └───────────┬──────────────────┘
             │                             │
             ▼                             ▼
   ┌─────────────────────────────────────────────┐
   │             VocaForge core pipeline           │
   │  resolve(id) → ModelLoader.load → Backend → WAV│
   └─────────────────────────────────────────────┘
```

### 2.1 Public Python contracts (the "Architecture API")
- `Backend` (ABC) — synthesis engine. `name`, `api_version`, `load_model(artifact)`,
  `synthesize(project, handle)`, `unload(handle)`.
- `ModelLoader` (ABC) — resolves a `ModelSpec` into a `ModelArtifact` (verify local
  paths, fetch remote weights, decrypt packs, ...). `name`, `load(spec)`, `release(artifact)`.
- `ModelArtifact` (dataclass) — `spec` + `assets` + `meta`, handed to `Backend.load_model`.
- `VocaForgeEngine` gains `model_loader` param + `register_backend()` / `register_model_loader()`
  for *active* integration (no auto-discovery).

### 2.2 REST gateway (`/api/v1`, zero extra deps, stdlib only)
| Method | Path | Purpose | Success | Not-found |
|--------|------|---------|---------|-----------|
| GET | `/api/v1/health` | liveness + capabilities | 200 | — |
| GET | `/api/v1/version` | framework version | 200 | — |
| GET | `/api/v1/models` | list registered libraries | 200 | — |
| GET | `/api/v1/models/{id}` | one library spec | 200 | 404 |
| POST | `/api/v1/models` | register a library (active integration) | 201 | — |
| POST | `/api/v1/resolve` | resolve id → spec | 200 | 404 |
| POST | `/api/v1/synth` | synthesize → WAV (raw or JSON) | 200 | 404 |
| GET | `/api/v1/openapi.json` | OpenAPI 3.0 document | 200 | — |

- CORS enabled so browser/website integrations work.
- `synth` returns raw `audio/wav` (`?format=wav` or `Accept: audio/wav`) or JSON
  (`audio_base64`) by default; `out` writes a server-side file (for agents).
- Keeps the 103 semantic only inside the Agent RPC envelope; REST uses standard 200/404.

### 2.3 Client SDK
- `vocaforge.client.VocaForgeClient` (urllib, zero deps) — lets a third-party service
  call the gateway without running VocaForge locally. This is the cleanest "remote
  integration" path for websites.

## 3. Trade-offs

| Choice | Alternative | Why this |
|--------|-------------|----------|
| REST over stdlib `http.server` | Flask/FastAPI | zero-dependency, console-free, matches existing RPC; deploy behind nginx if needed |
| `Backend` + `ModelLoader` split | single `Backend.load_model` | separates *where models live* from *how to infer*; lets third parties ship a loader for their storage without touching inference |
| Programmatic registration, not entry_points | setuptools auto-discovery | user explicitly said "not plugins, projects actively integrate"; explicit > magic |
| OpenAPI 3.0 doc | just prose | lets others generate clients/UI; self-describing gateway |
| Version `0.2.0` | stay 0.1.0 | Architecture API is a public-surface change worth a bump |

## 4. Deliverables
- `vocaforge/core/model_loader.py` (NEW)
- `vocaforge/core/backend.py` (+ `api_version`, artifact-based `load_model`)
- `vocaforge/backends/{stub,diffsinger}.py` (refactor to `ModelArtifact`)
- `vocaforge/core/engine.py` (`model_loader`, `register_*`, pipeline)
- `vocaforge/api/arch.py` + `vocaforge/api/openapi.py` (NEW)
- `vocaforge/client.py` (NEW)
- `vf_cli.py`: `api` subcommand
- `examples/integrate_custom_backend.py`, `examples/integrate_rest_client.py` (NEW)
- `Architecture-API.md` + `Architecture-API-zh.md` (NEW)
- `README.md` / `README-zh.md` updated; `index.html` Architecture API section
- Bump `__version__` / `config.VERSION` → `0.2.0`

## 5. Risks
- **No C compiler in sandbox** → `dist/vf-cli.exe` still built by user on dev machine
  via `build_vf_cli.py` (unchanged).
- **REST binding** may be blocked by sandbox network policy in *this* env; self-test will
  use an auto-assigned port and stop the server cleanly.
- Backend contract change (`load_model(artifact)`) — documented in Architecture-API.md as
  the v1 contract; 0.1.0 had no external backend implementers yet.
