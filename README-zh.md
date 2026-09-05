# VocaForge（中文文档）

> [English](./README.md)

**VocaForge** 是一个基于 [DiffSinger](https://github.com/openvpi/DiffSinger) 的**纯 Python AI 声库框架**：
无 GUI、无控制台窗口，并附带 `vf-cli` —— 供 AI Agent 操作 VocaForge 的命令行工具。

```text
Agent / CLI  ──JSON──►  VocaForgeEngine  ──►  模型注册表 (models/manifest.json)
                                      │                │  get(key) -> ModelSpec | 抛 404
                                      ▼
                                可插拔后端
                                  ├── DiffSingerAdapter  (真实推理；懒加载 diffsinger)
                                  └── StubBackend        (无模型 / 无 GPU 也能跑)
                                      │
                                      ▼
                                  音频 (WAV 字节)
```

## 为什么用 VocaForge

- **纯库、无控制台。** 任何 Python 进程里 `import vocaforge` 即可，不弹窗。
- **可插拔后端。** 在 GPU 机器上用 `DiffSingerAdapter` 接真实 DiffSinger 推理；`StubBackend` 让框架在
  零模型情况下也能完整运行与自测。
- **对 Agent 友好。** `vf-cli`（英文输出）与 HTTP RPC（`POST /vf`）让 Agent 列声库、解析模型
  （缺失→404，命中→103）、合成音频。
- **零重依赖。** 核心仅用 Python 标准库；DiffSinger 为可选懒加载依赖。

## 安装

```bash
pip install -e .        # 安装 vocaforge 包 + vf-cli 命令
# 或不安装直接运行：
python vf_cli.py --help
```

需要 Python 3.9+。使用框架与 stub 后端**不需要**安装 DiffSinger。

## 快速上手（库）

```python
from vocaforge import VocaForgeEngine
from vocaforge.synth.project import Note, SynthProject

engine = VocaForgeEngine()                       # 读取 models/manifest.json
project = SynthProject(notes=[
    Note("do", 60, 0.4), Note("re", 62, 0.4),
    Note("mi", 64, 0.4), Note("fa", 65, 0.5),
])
audio: bytes = engine.synthesize("stub-zh", project)   # 16-bit PCM WAV 字节
with open("out.wav", "wb") as fh:
    fh.write(audio)
```

## vf-cli（英文输出）

| 命令 | 说明 |
|------|------|
| `vf-cli info` | 显示版本、Python、后端可用性 |
| `vf-cli models` | 列出已注册声库 |
| `vf-cli synth --model <id> --lyrics <text> --out <wav>` | 由歌词合成 |
| `vf-cli export --project <json> --model <id> --out <wav>` | 由工程 JSON 导出 |
| `vf-cli serve --host 127.0.0.1 --port 8765` | 启动 Agent RPC 服务 |
| `vf-cli api --host 0.0.0.0 --port 8080` | 启动 Architecture REST 网关（`/api/v1`） |

```bash
vf-cli synth --model stub-zh --lyrics "你好世界" --out hello.wav
```

## Agent RPC

`vf-cli serve` 启动 HTTP 服务（标准库 `http.server`，零额外依赖）。
发送 `POST /vf`，请求体为 JSON：

```json
{ "action": "synth", "model": { "id": "stub-zh" }, "lyrics": "测试", "out": "rpc.wav" }
```

状态约定（读取 JSON 信封里的 `code` 字段；HTTP 103 是 1xx 信息码、不能作为终态，因此 103 放在信封内）：

| HTTP | `code` | 含义 |
|------|--------|------|
| 404 | 404 | 注册表中找不到该声库 |
| 200 | 103 | 找到并加载 |
| 200 | 200 | 成功（如合成完成） |

动作：`info`、`models`、`resolve`/`load`、`synth`。

## Architecture API（让别人接入）

VocaForge 是个**能被别人在其项目之上构建**的框架。Architecture API 提供两个公开扩展点
与一个版本化 REST 网关。

**扩展点 1 — `Backend`（合成引擎）。** 实现它并在引擎上注册；不做自动发现，由你的项目
显式接入。

```python
from vocaforge import Backend, VocaForgeEngine, ModelSpec, SynthProject

class MyBackend(Backend):
    name = "myengine"
    api_version = "1.0"
    def load_model(self, artifact):        # artifact: ModelArtifact
        return {"spec": artifact.spec}
    def synthesize(self, project, handle):
        ...                                # -> 16-bit PCM WAV 字节
    def unload(self, handle):
        pass

engine = VocaForgeEngine()
engine.register_backend(MyBackend())
engine.add_model(ModelSpec(id="x", name="X", type="synthesizer", path="", backend="myengine"))
```

**扩展点 2 — `ModelLoader`（模型存储解析器）。** 把「模型存在哪」与「如何推理」解耦。可实现
从数据库、对象存储或加密包加载。

```python
from vocaforge import ModelLoader, ModelArtifact

class DbModelLoader(ModelLoader):
    name = "db"
    def load(self, spec):  return ModelArtifact(spec=spec, assets={"root": spec.path})
    def release(self, artifact):  pass

engine.register_model_loader(DbModelLoader())
```

**REST 网关（`/api/v1`）。** 启动后让外部服务/网站通过 HTTP 接入（开启 CORS，OpenAPI 3.0 在
`/api/v1/openapi.json`）。

| 方法 | 路径 | 用途 | 未找到 |
|------|------|------|--------|
| GET | `/api/v1/health` | 存活 + 能力 | — |
| GET | `/api/v1/version` | 框架版本 | — |
| GET | `/api/v1/models` | 列出声库 | — |
| POST | `/api/v1/models` | 注册声库 | — |
| GET | `/api/v1/models/{id}` | 单个声库规格 | 404 |
| POST | `/api/v1/resolve` | 解析 id → 规格 | 404 |
| POST | `/api/v1/synth` | 合成 → WAV（原始或 JSON） | 404 |
| GET | `/api/v1/openapi.json` | OpenAPI 文档 | — |

```bash
vf-cli api --host 0.0.0.0 --port 8080
curl -X POST http://127.0.0.1:8080/api/v1/synth?format=wav \
     -H 'Content-Type: application/json' \
     -d '{"model":"stub-zh","lyrics":"你好世界"}' -o out.wav
```

**客户端 SDK**（零依赖），供 Python 远程接入：

```python
from vocaforge.client import VocaForgeClient
client = VocaForgeClient("http://127.0.0.1:8080")
wav: bytes = client.synth(model="stub-zh", lyrics="你好世界", as_wav=True)
```

完整契约、版本策略与接入指南见 [Architecture-API-zh.md](./Architecture-API-zh.md)。

## 注册真实 DiffSinger 声库

在 `models/manifest.json` 增加一项，并在 `vocaforge/backends/diffsinger.py` 实现推理：

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

然后 `pip install diffsinger` 并补全 `DiffSingerAdapter.synthesize()`。

## 打包 `vf-cli.exe`（Nuitka）

在装有 C 编译器（MSVC 或 MinGW-w64）的机器上：

```bash
pip install nuitka
python build_vf_cli.py        # -> dist/vf-cli.exe
```

采用 Nuitka（沿用 ctn.exe 工作流）以规避 Defender 的 `Wacatac` 误报。编写本框架的沙箱无 C 编译器，
故 exe 在开发机上构建。

## 目录结构

```
VocaForge/
├── vocaforge/            # 框架库
│   ├── core/             # 引擎、后端接口、模型加载器、异常
│   ├── backends/         # diffsinger 适配器 + stub 后端
│   ├── models/           # 注册表 + manifest
│   ├── synth/            # SynthProject（音符/歌词/时长）
│   ├── api/              # Agent RPC（404/103）+ Architecture REST（/api/v1）+ OpenAPI
│   ├── cli/              # vf-cli
│   ├── client.py         # VocaForgeClient（REST 客户端 SDK）
│   └── util/             # WAV 编码
├── vf_cli.py             # 命令行入口
├── build_vf_cli.py       # Nuitka 打包脚本
├── models/manifest.json  # 本地声库注册表
├── examples/             # 示例 + RPC 客户端 + 接入示例
├── README.md / README-zh.md
├── LICENSE               # Available License
└── index.html            # 对外公开落地页
```

## 许可证

[Available License](https://license.kscm.top/available.md)
