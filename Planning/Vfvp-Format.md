# Planning — VocaForge .vfvp 声库格式

> 状态：已实现（v0.3.0） · 日期：2026-09-05

## 目标

把 VocaForge 声库的统一分发/加载格式定为 **`.vfvp`** —— 本质是一个**标准 7z 压缩包**，
固定内部布局，让第三方声库（DiffSinger 模型包）可以被打包、分发、注册与加载。

## 包内布局（契约）

```
xxx.vfvp  (= 标准 .7z)
├── model/
│   ├── acoustic.pth      # DiffSinger 声学模型
│   ├── vocoder.pth       # 声码器
│   └── config.json       # 模型结构配置
├── info.json             # 声库元信息（id/name/type/lang/sample_rate/backend/...）
└── phoneme_map.json      # 音素映射表
```

`info.json` 字段直接映射为 `ModelSpec`（`id`、`name`、`type`、`sample_rate`、`lang`、
`backend`、`extra`），因此注册 `.vfvp` 时无需手写 manifest 项。

## 技术选型与 trade-off

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| `py7zr`（纯 Python，lazy import） | 核心保持零依赖；仅加载/打包时才引入；跨平台 | 需 `pip install py7zr` 才能用 7z | ✅ 采纳（用户选定） |
| 调用系统 7z.exe 子进程 | 无 Python 依赖 | 目标机未必装 7-Zip；跨平台差；沙箱/CI 难保证 | ✕ 弃 |
| 内置 zip 自制格式 | 标准库即可 | **不满足用户"标准 7z"要求**，无法与 7-Zip 互通 | ✕ 弃 |

py7zr 版本差异坑：`read()` 内存读成员 API 在 py7zr ≥1.x 已移除，改用
`extract(targets=[name], path=tmp)` 读取单成员。

## 架构改动

1. **`vocaforge/vfvp.py`（新增）**：`VfvpPackage` + `pack_source` / `extract_temp` /
   `read_info` / `validate`。布局常量 `INFO_FILE / PHONEME_MAP_FILE / MODEL_DIR`。
2. **`ModelLoader.supports(spec)`（契约扩展）**：引擎把 spec 路由给第一个
   `supports==True` 的 loader。
3. **`VfvpModelLoader`（新增 loader）**：`supports` = `path` 以 `.vfvp` 结尾；`load`
   解包到临时目录并把规范文件暴露在 `ModelArtifact.assets`
   （`root/acoustic/vocoder/config/phoneme_map/info`）；`release` 删临时目录。
4. **引擎多 loader 链**：默认 `[LocalModelLoader, VfvpModelLoader]`，按 `supports` 路由；
   新增 `list_loaders()` / `discover()`。向后兼容：`register_model_loader` 追加到链尾。
5. **自动发现（显式 + 扫描）**：`ModelRegistry.discover_vfvp(dir)` 扫 `*.vfvp` 读
   `info.json` 自动建 `ModelSpec`；`vf-cli models` 列出前先 discover；`vf-cli models add
   <path.vfvp>` 显式注册。
6. **DiffSingerAdapter**：`load_model` 从 `artifact.assets` 取 acoustic/vocoder/config/
   phoneme_map 路径放入 handle；缺文件在加载期清晰报错。
7. **CLI**：新增 `package`（文件夹→.vfvp）；`models` 支持 `list/add/remove`。
8. **REST**：`POST /api/v1/models` 传 `.vfvp` path 时自动读 info.json 建 spec；health 返回
   全部 loader 名。

## 风险与对策

- py7zr 为可选依赖 → lazy import + 清晰安装提示；`pyproject` 提供
  `[project.optional-dependencies] vfvp = ["py7zr>=0.20"]`。
- 示例不得污染已提交 `models/manifest.json` → 示例/自检均用临时 manifest
  （`VF_MODEL_MANIFEST` 或显式 `ModelRegistry(manifest_path=临时)`）。
- 生成的 `.vfvp` 是构建产物 → 加入 `.gitignore`（`*.vfvp`）。
