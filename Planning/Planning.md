# VocaForge — Planning / 项目规划

> Pure Python framework wrapping DiffSinger for AI singing voice synthesis, plus `vf-cli.exe` for AI Agents.
> 基于 DiffSinger 的纯 Python AI 声库框架（无控制台窗口），并附带供 AI Agent 操作的 `vf-cli.exe`。

## 1. Goal / 目标
- **VocaForge** = 纯 Python 库 / SDK（`import vocaforge`），无 GUI、无控制台窗口。把 DiffSinger 的推理能力封装成可被代码与 Agent 调用的统一接口。
- **vf-cli.exe** = 独立打包的命令行工具，**英文输出**，供 AI Agent 作为子进程操作 VF（合成、列声库、起 RPC 服务等）。

## 2. Form / 形态（已确认）
- VocaForge 本体 = **纯 Python 框架库**（q-0 选择「纯Python框架库」）。
- DiffSinger 集成 = **可插拔后端适配器**（q-1，用户表示看不懂，已按推荐默认采用；与 q-3 的「API 传 JSON 查模型」模式天然契合）。
- vf-cli 打包 = **Nuitka**（q-2 选择，沿用 ctn 工具经验以规避 Defender Wacatac 误报）。
- 模型管理 = **API 传 JSON 的 model 数据 → VF 查本地注册表 → 无则 404，有则 103 并加载**（q-3）。

## 3. Architecture / 架构
```
Agent / CLI
   │  JSON {model, project, ...}
   ▼
VocaForgeEngine ──► ModelRegistry (models/manifest.json)
   │                     │  get(key) -> ModelSpec | raise VFModelNotFound(404)
   ▼
Backend (pluggable)
   ├── DiffSingerAdapter  (懒加载 diffsinger；真实环境调 DiffSinger 推理)
   └── StubBackend        (生成可测试 WAV；无 GPU/模型也能跑通 synth，用于自检)
   │
   ▼
Audio (WAV bytes) ──► save / RPC response
```

### 3.1 Pluggable backend / 可插拔后端
统一抽象 `Backend`：`load_model(spec) -> handle`、`synthesize(project, handle) -> bytes`、`unload(handle)`。
- `DiffSingerAdapter`：懒加载 `diffsinger` 包；未安装时抛 `VFMissingBackendError` 并提示 `pip install diffsinger`。是真实推理的集成点。
- `StubBackend`：依工程音符生成带包络的正弦音 WAV，使框架在无 GPU/模型时仍可端到端跑通 `synth`，用于 CI 与本地自检。

### 3.2 Model registry / 模型注册表
- 本地 `models/manifest.json` 列出可用声库：`diffusion` / `synthesizer` / `vocoder` 三类，含路径、采样率、语言等元信息。
- 查询语义（供 Agent）：收到 `{model:{id|name}}` → 命中返回 `103` 并加载；未命中返回 `404`。

### 3.3 Agent API RPC / 代理接口
- 标准库 `http.server`（零额外依赖），`POST /vf` 收 JSON。
- 状态码：`103` = 已找到并加载；`404` = 声库不存在；`200` = 合成成功；`400` = 请求非法；`500` = 内部错误。

## 4. vf-cli commands / 命令（英文输出）
| 命令 | 说明 |
|------|------|
| `vf-cli info` | 打印版本 / Python / 后端可用性 |
| `vf-cli models [list]` | 列出已注册声库 |
| `vf-cli synth --model <id> --lyrics <text> --out <wav>` | 由歌词/工程合成音频 |
| `vf-cli export --project <json> --out <wav>` | 由工程 JSON 导出音频 |
| `vf-cli serve --host 127.0.0.1 --port 8765` | 起 Agent RPC 服务 |

## 5. Tech trade-offs / 技术选型与权衡
| 项 | 选项 | 选择 | 理由 / Trade-off |
|----|------|------|------------------|
| 打包 | Nuitka vs PyInstaller | **Nuitka** | 单 exe；用户 ctn 经验证明可规避 Defender Wacatac 误报；代价是需 C 编译器（本沙箱无，交付 build 脚本） |
| 后端 | 硬集成真实仓库 vs 可插拔适配器 | **可插拔适配器** | 本机无 GPU/模型也能交付、可测；真实环境切 DiffSinger 只需装包。代价：真实推理需另行接模型 |
| RPC | Flask vs stdlib | **stdlib http.server** | 零额外依赖，纯框架不污染用户环境；代价：无异步/路由全家桶（够用） |
| 音频 | soundfile vs stdlib wave | **stdlib wave** | 避免二进制原生依赖，Stub 后端即可写 WAV；代价：仅基础 PCM |
| 模型查找 | 目录扫描 vs manifest | **manifest.json** | 显式、可版本化、Agent 易解析；代价：需维护清单 |

## 6. File layout / 文件结构
```
VocaForge/
├── Planning/Planning.md
├── vocaforge/
│   ├── __init__.py            # 版本 + 公共 API
│   ├── config.py              # 常量（默认 manifest、端口、版本）
│   ├── core/{engine,backend,exceptions}.py
│   ├── backends/{__init__,diffsinger,stub}.py
│   ├── models/{registry,manifest}.py
│   ├── synth/project.py       # SynthProject（音符/歌词/时长）
│   ├── api/{protocol,server}.py  # 404/103 RPC
│   ├── cli/vf_cli.py          # 命令行（英文）
│   └── util/audio.py          # WAV 编码
├── vf_cli.py                  # CLI 入口（免安装运行）
├── build_vf_cli.py            # Nuitka 打包脚本 -> dist/vf-cli.exe
├── models/manifest.json       # 本地声库清单（含示例 stub 声库）
├── examples/{synth_demo.py, manifest.example.json}
├── README.md / README-zh.md   # 中英双语
├── LICENSE                    # Available License
└── index.html                 # 商业风格公开落地页（双主题）
```

## 7. Deliverables / 交付
- 可 `import vocaforge` 的纯框架库。
- vf-cli 源码 + Nuitka 打包脚本（用户开发机一键出 `dist/vf-cli.exe`）。
- README 中英双语 + LICENSE + 商业风格 `index.html`（浅/深双主题）。
- 上传 GitHub：`https://github.com/Developerprit/VocaForge.git`（先认证仓库存在性）。

## 8. Risks / 风险
- **本沙箱无 C 编译器** → Nuitka 无法在此产出 exe；交付 `build_vf_cli.py`，用户在开发机一键构建。
- 真实 DiffSinger 推理需 PyTorch + 声学/声码器模型 + GPU，超出本次交付范围（提供 `DiffSingerAdapter` 与安装指引，未装时优雅降级）。
- `models/manifest.json` 默认含一个 `stub` 声库用于自检；真实声库需用户按 manifest schema 注册。
