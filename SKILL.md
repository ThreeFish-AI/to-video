---
name: to-video
description: 论文/文档/代码信源 → 动效图解科普视频全流程：信源精读取证（A 型论文并行分章 / B 型文档代码固定提交 + 证据三级）、策划、逐字稿 SSOT、真实性 + 易懂性双重校验、分镜、IndexTTS 声音克隆配音、Remotion 代码动画场景、草渲抽帧 QA、终渲 1080p30 交付（srt/vtt 字幕）；含内容工作区初始化与分集脚手架。Use when 用户要制作/迭代科普视频、初始化视频工作区、scaffold 新集、写 narration.md/storyboard.md、跑 TTS/渲染/抽帧 QA，或问及这套流水线的用法。信源精读方法论可配合 /guided-learn，图示制作可配合 /archify。
license: MIT
metadata: {version: "1.0.0", author: ThreeFish-AI, source: "extracted from ThreeFish-AI/negentropy apps/negentropy-influence"}
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# to-video：动效图解科普视频流水线（路由壳）

本 Skill 是**路由层**：内容 SSOT 在 `pipeline/skills/01–09.md`（九篇阶段规格），工具 SSOT 在 `pipeline/scripts/`，九阶段的唯一机器可读声明是 [pipeline/stages.toml](pipeline/stages.toml)；此处只给指针与不变量，不复制任何正文（防第二事实源）。机制全量契约见尾部指针。

命令统一用路径变量（唯一定义处 [pipeline/README.md](pipeline/README.md)）：`$T` = skill 根（如 `~/.claude/skills/to-video`），`$W` = 内容工作区根（含 `.to-video-root` 哨兵），`$P` = `$W/episodes/<slug>-video` 分集工程，`$V` = `$W/voices` 音色样本目录（整目录 gitignored）。

## 快速通道（全新制作的最短序列）

```bash
# 0) 安装（一次性）：clone 后挂进技能目录（或用 TO_VIDEO_HOME 指派，见「双锚点与安装」）
git clone https://github.com/ThreeFish-AI/to-video <目录>
ln -s <目录> ~/.claude/skills/to-video && T=~/.claude/skills/to-video

# 1) 初始化内容工作区（幂等：哨兵、series 骨架、样本目录、工作区级包装器）
uv run --no-project $T/pipeline/scripts/scaffold.py --init-workspace <目录>   # 即 $W

# 2) 建集：复制 frozen 骨架生成 $P；随后人工登记 series.json、把样本指纹写进
#    $V/refs.toml（脚手架刻意不代做，清单见其结尾输出）
uv run --no-project $T/pipeline/scripts/scaffold.py <slug>-video --title "本集标题"

# 3) Stage ①–⑤ 内容层（规格见下表）：$P/research/ 取证 → planning.md →
#    narration.md → storyboard.md，再过内容门（check 自动串联 archify 覆盖门）
uv run --no-project $T/pipeline/scripts/pipeline.py --project $P build
uv run --no-project $T/pipeline/scripts/pipeline.py --project $P check

# 4) Stage ⑥ TTS：先预演排期；正式合成前置 = doctor 自检 + 样本试听（07 规格）
uv run --no-project $T/pipeline/scripts/pipeline.py --project $P tts --plan

# 5) Stage ⑦ 场景实现：$P/video/src/scenes/ 与 Main.tsx 注册表全新撰写（无子命令）
cd $P/video && pnpm install && npx tsc --noEmit

# 6) Stage ⑧⑨ 草渲抽帧 QA → 终渲交付：
uv run --no-project $T/pipeline/scripts/pipeline.py --project $P render   # → $P/out/draft.mp4
uv run --no-project $T/pipeline/scripts/pipeline.py --project $P qa       # 零 FAIL 才放行终渲
uv run --no-project $T/pipeline/scripts/pipeline.py --project $P render --final
uv run --no-project $T/pipeline/scripts/pipeline.py --project $P captions # → $P/out/captions.{srt,vtt}
```

## 九阶段速查

单入口 `pipeline.py`（完整形态 `$T/pipeline/scripts/pipeline.py --project $P <cmd>`，下表只写子命令；工作区内等价 `$W/scripts/pipeline.py <cmd>`）。

| Stage | 做什么 | 规格链接 | 工具/命令 | 通过门 |
|---|---|---|---|---|
| ① 信源精读取证 | A 型论文：并行子代理逐章 + 官方站点补充；B 型文档/代码/站点：固定提交取证 + 证据三级 | [01](pipeline/skills/01-source-extraction.md) | A 型 `paper_extract.py`；B 型 `source_ledger.py` | 全部断言可回溯；RISKY=0 |
| ② 策划案 | 受众/结构/视觉契约（色彩语义映射本集核心概念） | [02](pipeline/skills/02-planning.md) | —（authored） | planning.md 六节齐 |
| ③ 逐字稿 | `narration.md` ★单一事实源 | [03](pipeline/skills/03-narration.md) | `build` | build_narration.py 通过 |
| ④ 双重校验 | 真实性回溯 + 易懂性 | [04](pipeline/skills/04-verification.md) | `check` | RISKY=0 且 REWRITE=0 |
| ⑤ 分镜表 | 镜号 ↔ 句 id 区间 ↔ 画面 ↔ 动效；beat 覆盖性 | [05](pipeline/skills/05-storyboard.md) | `check --check-scenes` | beat 覆盖率无缺句 |
| ⑥ TTS 配音 | 声音克隆（IndexTTS-2.5；备选 edge 预置音色，manifest 契约一致） | [07](pipeline/skills/07-tts-voice.md) | `tts --plan` / `captions` | refs 指纹门 + 试听定档 + ETA |
| ⑦ Remotion 场景 | 代码动画实现；动效走 `src/motion/` 运动模型 | [06](pipeline/skills/06-remotion-implementation.md) | 工程内直调 `tsc --noEmit` 与 motion 测试 | 七条渲染红线 + 运动层铁律 |
| ⑧ 草渲 + 抽帧 QA | 半分辨率快速迭代（`--beat-heads` 补入场瞬态盲区） | [08](pipeline/skills/08-render-qa.md) | `render` + `qa` | 自动体检零 FAIL（尾幕渐黑必查） |
| ⑨ 终渲 + 交付 | 1080p30 成片 + srt/vtt 字幕 | [09](pipeline/skills/09-final-render.md) | `render --final` + `captions` | 实测时长落在预算窗内 |

⚠️ **序号与文件号刻意错位**：Stage ⑥ ↔ `07-tts-voice`、Stage ⑦ ↔ `06-remotion-implementation`（入链 ≥5 处，重命名代价大于收益），由 [tests/test_stages.py](pipeline/tests/test_stages.py) 执法——勿据序号猜文件名，更勿「顺手对齐」。

## 关键不变量

- 逐字稿只改 `narration.md`；`narration.json` / `manifest.json` 是派生物。
- **口播永不出现他集标题与集数序号**——顺序只活在视觉层与 `series.json`（执法：`check_series.py`，建议挂 pre-commit）。
- **B 型三级证据纪律**：「他人对闭源产品源码的分析」属三级证据，口播必须带归属句、不得表述为产品既成事实；活数据（行数/总量/star）不进口播。
- 每集 `pipeline.toml` 是可执行参数唯一来源（默认值在 `config.py` 的 SCHEMA，toml 只写偏离）；README 不复制命令行参数。
- 时序常数只在 `video/src/timing.json`（`timing.ts` 与 Python 双语共读同一 JSON）；运动语汇只在 `video/src/motion/`（frozen，改 = 模板 + 全集同步）。
- 声音样本是生物特征：不入库（`voices/refs.toml` 只存指纹），试听后即删。
- **复用边界**：Python 脚本集中共享（SSOT）；Remotion 原语复制不共享——复制源头是 `pipeline/templates/video-skeleton/`，由 `scaffold.py` 实例化、`verify_skeleton.py` 字节级执法漂移。
- **双锚点**：skill 根随安装位置（脚本自 `__file__` 向上找 `SKILL.md`），工作区根由哨兵搜索定位——机制与内容物理分离，各居任意目录互不牵连。

## 双锚点与安装

- **安装**：`git clone https://github.com/ThreeFish-AI/to-video <目录>` 后 `ln -s <目录> ~/.claude/skills/to-video`，或设 `TO_VIDEO_HOME=<目录>`；分集与工作区内的薄包装器据此自动定位机制代码。
- **工作区哨兵**：`.to-video-root`（兼容识别旧名 `.influence-root`，既有工作区零改动迁移）；找不到哨兵即**大声退出**并提示 `--init-workspace`，绝不静默猜根。
- **包装器解析顺序**（未命中即退出并打印安装指令，静默跳过被禁止）：`TO_VIDEO_HOME` → `~/.claude/skills/to-video` → `~/.agents/skills/to-video`；工作区级包装器同时把自身位置硬性覆写进 `TO_VIDEO_WORKSPACE`（不承袭外部值），故从任意 CWD 调用都锚定本工作区。
- **env 清单**：

| env | 作用 | 缺省 |
|---|---|---|
| `TO_VIDEO_HOME` | skill 根（包装器解析首位） | 无（靠软链命中） |
| `TO_VIDEO_WORKSPACE` | 工作区根显式指派（目录须含哨兵，防拼错静默锚错） | 自 CWD 向上搜索哨兵 |
| `TO_VIDEO_TTS_STORE` | TTS 音频版本库根（兼容读旧名 `NE_TTS_STORE`） | `~/Library/Application Support/to-video/tts-store`（旧默认目录存在则回退） |
| `TO_VIDEO_INDEX_TTS_ROOT` | IndexTTS 服务仓（`tts_server` / `tts_bench` 的运行环境） | `~/tools/index-tts` |
| `TO_VIDEO_TEST_WORKSPACE` | 测试集成模式：指向真实内容工作区做真树回归 | 无（单测用 fixture） |

## 相邻技能协作

- **Stage ① 深读信源**：建议先调 `/guided-learn`——其「全貌解剖（先梳理后总结）+ 底层规律与争议提炼」方法论可直接复用为分章子代理的输出结构约束。
- **Stage ⑤/⑦ 图示资产**：需要架构/流程类图解时调 `/archify` 出图，HTML 落 `$W` 下，再由 `record_archify_all.py` 逐章录制为动效素材；句级锚定覆盖门（`check_archify_coverage.py`）已自动串联进 `check`。

## 尾部指针

- [pipeline/README.md](pipeline/README.md) —— 机制全量契约：路径变量 SSOT、`pipeline.toml` 字段表、复用边界、脚手架清单、许可注意。
- [README.md](README.md) —— 安装与 quickstart。
