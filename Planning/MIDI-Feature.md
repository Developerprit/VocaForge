# Planning — VocaForge MIDI 功能

> 状态：已实现（v0.4.0） · 日期：2026-09-05

## 目标

给 VocaForge 加 **MIDI 操作能力**：编辑 MIDI、生成 MIDI、并把 MIDI **渲染成歌声**（MIDI
音符 → 声库合成 → `.wav`）。按用户答复：嵌入 = MIDI 渲染成歌声；MIDI 引擎「你自己看着办」
→ 选用**手写 SMF 读写（零依赖）**，延续框架核心 stdlib-only 哲学；形态 = 库 API + CLI 全套。

## 设计

新增包 `vocaforge/midi/`：

| 文件 | 职责 |
|------|------|
| `notes.py` | 音名 ↔ MIDI 号（`C4`=60, `A4`=69），`parse_seq("C4 0.4 E4 0.4")` 解析 CLI 音序 |
| `smf.py` | 手写 SMF 读写：`MidiNote`/`MidiFile`；解析 format 0/1、tempo meta、lyric meta（FF 05）；note-on/off 配对 → 绝对秒；写出 format 0（tempo + 可选歌词 meta）；编辑 `transpose / set_tempo / retime / trim / set_lyrics` |
| `project.py` | `midi_from_project`（SynthProject→MidiFile，间隔自动成休止）、`midi_to_project`（→SynthProject，间隙插休止 Note(midi=0)）、`render_midi`（MIDI+声库→歌声 WAV，走 `engine.synthesize`） |

MIDI 歌词来源：MIDI 无歌词 → 渲染时可用 `--lyrics`（逐非休止音符分配字符，不足补 `a`），
或依赖包内 lyric meta（我们的生成器会写入 `FF 05`）。

## 技术选型与 trade-off

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| 手写 SMF（struct + VLQ） | 核心零依赖；SMF 规范简单可控；无版本/信任风险 | 只实现子集（无 SMPTE/多轨精确还原） | ✅ 采纳 |
| mido（lazy import） | 功能全 | 加可选依赖；API 泛 | ✕（用户交我定，选零依赖） |
| pretty_midi | 高层便捷 | 依赖 scipy 等较重 | ✕ |

时间模型：`MidiFile.notes` 以**绝对秒**存储（读时 tick→秒，写时秒→tick 用 ppqn=480 +
tempo µs/拍换算），编辑直观；`set_tempo(bpm)` 按新旧 tempo 比值重定标所有时间，保持音符
数量不变、播放速度变化（音乐语义正确）。

## CLI（`vf-cli midi`，英文输出）

- `midi info <x.mid>` — 格式/轨数/BPM/音符数/时长/音域 JSON
- `midi gen --notes "C4 0.4 E4 0.4 ..." [--lyrics] [--bpm] [--out]` — 生成 .mid（也支持 --project json）
- `midi edit --midi x.mid --out y.mid [--transpose N] [--tempo BPM] [--rate F] [--clip s:e] [--lyrics]`
- `midi render --midi x.mid --model stub-zh [--lyrics] [--out wav]` — **MIDI→歌声 WAV**
- `midi export --midi x.mid --out proj.json` — 导出工程 JSON

## 风险与对策

- SMF 是二进制定长/变长混合 → 自检用「生成→解析回→对比」回环 + 与标准字段交叉核对。
- 多轨/节奏复杂 MIDI 只合并为主旋律 → 文档写明子集；读不出处默认 120BPM、单音域合并。
- 歌词语义缺失 → lyric meta + CLI `--lyrics` 双通道，缺省 `a`。
