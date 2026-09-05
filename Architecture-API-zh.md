# VocaForge Architecture API（中文）

> 版本：1.0（对应 VocaForge `>=0.2.0`）
> 读者：要在自己项目里接入 VocaForge，或通过 HTTP 调用它的开发者。

VocaForge 是个**框架**，不是封闭应用。Architecture API 是其他人可在其上构建的、稳定且
文档化的接入面。它分两部分：

1. **公开 Python 契约** —— `Backend` 与 `ModelLoader`，两个扩展点，用来把自定义合成引擎 /
   模型存储接入 VocaForge。
2. **REST 网关**（`/api/v1`）—— 版本化 HTTP 接入面，让外部服务与网站远程集成 VocaForge。

设计决议（依项目需求）：**不做插件自动发现**。你*主动*接入 —— import 库、继承、注册。这样
接线显式、可调试。

---

## 1. 公开 Python 契约

### 1.1 `Backend` — 合成引擎（扩展点 1）

```python
from vocaforge import Backend, ModelArtifact, SynthProject

class MyBackend(Backend):
    name = "myengine"      # 稳定 id；可通过 ModelSpec.backend 选中
    api_version = "1.0"    # load_model/synthesize/unload 变更时升版

    def load_model(self, artifact: ModelArtifact):
        # artifact.spec   -> ModelSpec（元数据）
        # artifact.assets -> 已解析的存储（如 {"root": "/models/x"}）
        return {"spec": artifact.spec, "assets": artifact.assets}

    def synthesize(self, project: SynthProject, handle) -> bytes:
        # 返回 16-bit PCM WAV 字节（可用 vocaforge.util.audio.float_to_wav_bytes）。
        ...

    def unload(self, handle) -> None:
        ...
```

注册并使用：

```python
from vocaforge import VocaForgeEngine, ModelSpec

engine = VocaForgeEngine()
engine.register_backend(MyBackend())
engine.add_model(ModelSpec(id="x", name="X", type="synthesizer", path="", backend="myengine"))
wav: bytes = engine.synthesize("x", SynthProject.from_lyrics("hi"))
```

内置的 `StubBackend`（无模型可跑）与 `DiffSingerAdapter`（真实推理，懒加载 `diffsinger`）
都实现了该契约。

### 1.2 `ModelLoader` — 模型存储解析器（扩展点 2）

把「模型存在哪」与「如何推理」解耦。可实现从数据库、对象存储、加密包加载。

```python
from vocaforge import ModelLoader, ModelArtifact, ModelSpec

class DbModelLoader(ModelLoader):
    name = "db"

    def load(self, spec: ModelSpec) -> ModelArtifact:
        # 解析 spec -> 具体 assets，再包装。
        return ModelArtifact(spec=spec, assets={"root": spec.path}, meta={"src": "db"})

    def release(self, artifact: ModelArtifact) -> None:
        # 在此释放临时文件 / 句柄。
        ...

engine.register_model_loader(DbModelLoader())
```

默认 `LocalModelLoader` 校验 `spec.path` 存在于磁盘（允许空 path —— 例如 stub 后端不需要
权重）。

### 1.3 `ModelArtifact`

从 `ModelLoader.load()` 传到 `Backend.load_model()` 的对象。

| 字段 | 类型 | 含义 |
|------|------|------|
| `spec` | `ModelSpec` | 已注册声库元数据 |
| `assets` | `dict` | 已解析存储（路径 / URI / 句柄） |
| `meta` | `dict` | 加载器附加信息（如 `{"src": "db"}`） |

### 1.4 `VocaForgeEngine` 公开方法

| 方法 | 用途 |
|------|------|
| `register_backend(backend)` | 接入自定义 `Backend`（按 `backend.name` 选中） |
| `register_model_loader(loader)` | 安装自定义 `ModelLoader` |
| `add_model(spec)` | 运行时注册声库 |
| `resolve(key)` / `exists(key)` | 按 id 或 name 查声库 |
| `list_models()` / `list_backends()` | 枚举 |
| `synthesize(model_key, project)` | 完整流水线 → WAV 字节 |

---

## 2. REST 网关（`/api/v1`）

用 `vf-cli api` 启动（标准库 `http.server`，零额外依赖，开启 CORS）：

```bash
vf-cli api --host 0.0.0.0 --port 8080
```

### 2.1 端点

| 方法 | 路径 | 用途 | 成功 | 未找到 |
|------|------|------|------|--------|
| GET | `/api/v1/health` | 存活 + 能力 | 200 | — |
| GET | `/api/v1/version` | 框架版本 | 200 | — |
| GET | `/api/v1/models` | 列出声库 | 200 | — |
| POST | `/api/v1/models` | 注册声库 | 201 | — |
| GET | `/api/v1/models/{id}` | 单个规格 | 200 | 404 |
| POST | `/api/v1/resolve` | 解析 id → 规格 | 200 | 404 |
| POST | `/api/v1/synth` | 合成 → WAV | 200 | 404 |
| GET | `/api/v1/openapi.json` | OpenAPI 3.0 文档 | 200 | — |

### 2.2 `synth` 细节

请求体：

```json
{ "model": "stub-zh", "lyrics": "你好世界", "midi": 60, "duration": 0.35,
  "project": null, "out": null }
```

- 提供 `lyrics`（每字一个音符）**或** `project`（一个 `SynthProject` 字典）。
- `out`（服务端路径）会在宿主上写出 WAV 文件；JSON 响应也会回报 `saved_to`。
- 响应格式：
  - `?format=wav` **或** `Accept: audio/wav` → 原始 `audio/wav` 字节。
  - 否则 → JSON：`{"ok": true, "sample_rate": 44100, "bytes": N, "audio_base64": "..."}`。

### 2.3 错误

| HTTP | 含义 |
|------|------|
| 400 | JSON 非法 / 声库规格无效 |
| 404 | 注册表中找不到该声库 |
| 500 | 合成失败（见 `error` 字段） |

> 说明：更简单的 Agent RPC（`POST /vf`，由 `vf-cli serve` 启动）使用 404/103/200 信封约定；
> REST 网关使用标准 HTTP 语义（200/404/500）。

### 2.4 CORS

所有响应都带 `Access-Control-Allow-Origin: *`，浏览器/网站客户端可直接调用。生产环境建议
置于 nginx 之后并收紧来源。

---

## 3. 客户端 SDK

`vocaforge.client.VocaForgeClient` 是零依赖 HTTP 客户端（标准库 `urllib`）。当你的服务
远程接入 VocaForge（而非 import 它）时使用。

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

## 4. 版本策略

- Python 契约：`Backend.api_version`（当前 `"1.0"`）。`load_model`/`synthesize`/`unload`
  签名变更时升版；旧后端仍可被加载。
- REST：URL 带前缀（`/api/v1`）。破坏性变更使用新前缀（`/api/v2`）。
- OpenAPI 文档实时托管于 `/api/v1/openapi.json` —— 可据此生成客户端 / UI。

---

## 5. 接入模式

| 你是… | 用 |
|-------|----|
| 想自定义推理的 Python 项目 | 实现 `Backend`（+ 可选 `ModelLoader`），注册到 `VocaForgeEngine` |
| 调用运行中 VocaForge 的 Python 服务 | 通过 HTTP 使用 `VocaForgeClient` |
| 网站 / 前端 | `fetch()` REST 网关（已开 CORS），或由你的后端代理 |
| Agent | `vf-cli`（英文）或 Agent RPC `POST /vf` |
