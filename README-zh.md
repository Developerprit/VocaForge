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
│   ├── core/             # 引擎、后端接口、异常
│   ├── backends/         # diffsinger 适配器 + stub 后端
│   ├── models/           # 注册表 + manifest
│   ├── synth/            # SynthProject（音符/歌词/时长）
│   ├── api/              # Agent RPC（404/103 协议）
│   ├── cli/              # vf-cli
│   └── util/             # WAV 编码
├── vf_cli.py             # 命令行入口
├── build_vf_cli.py       # Nuitka 打包脚本
├── models/manifest.json  # 本地声库注册表
├── examples/             # 示例 + RPC 客户端
├── README.md / README-zh.md
├── LICENSE               # Available License
└── index.html            # 对外公开落地页
```

## 许可证

[Available License](https://license.kscm.top/available.md)
