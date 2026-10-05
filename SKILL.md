---
name: to-video
description: 把论文、技术文档、代码仓库、课程站点或 guided-learn 精读产物（精读与通俗拆解文档）等信源做成动效图解科普视频（animated explainer video）的十阶段流水线：信源精读取证、策划、逐字稿（单一事实源）、真实性与易懂性校验、成文优化（把 AI 稿改得像人写、适合人读人听）、分镜、声音克隆或预置音色配音（TTS）、Remotion 代码动画、抽帧 QA、终渲字幕与交付归档，支持中英双语版本。Use when 用户想把一篇论文、文档、代码或已有的精读拆解文档讲成视频，制作或迭代科普解说视频（改稿后重配音、重渲染），初始化视频工作区或新建一集，编写或润色 narration.md / storyboard.md，跑配音、渲染、抽帧质检或交付归档，或询问这套流水线的用法——即使没有点名 to-video。不用于剪辑或转码已有视频、通用产品宣传片、幻灯片、单独绘制架构图，或不产出视频的论文精读。
license: MIT
compatibility: 渲染与抽帧 QA 仅支持 macOS（场景字体依赖系统 CJK 字体栈）；需要 uv、pnpm 与 Node.js（版本要求见 README 前置依赖）；制作期 edge-tts 草声默认（需联网），IndexTTS-2.5 本人声音克隆仅本人显式点名启用（实跑带 --final-voice 具名授权，需本地服务）；宿主须能执行 Bash。
metadata:
  version: "2.0.0"
  author: "ThreeFish-AI"
  source: "extracted from ThreeFish-AI/negentropy apps/negentropy-influence"
allowed-tools: Read Write Edit Glob Grep Bash
---

# to-video：动效图解科普视频流水线（路由壳）

本 Skill 是**路由层**：内容 SSOT 在 `references/NN-*.md`，工具 SSOT 在 `scripts/`，阶段唯一机器可读声明是 [references/stages.toml](references/stages.toml)；只给路由、指针与不变量，不复制正文。

命令统一用路径变量（唯一定义处 [PIPELINE.md](references/PIPELINE.md)）：`$T` = skill 根（本文件所在目录；Claude Code 下即 `${CLAUDE_SKILL_DIR}`），`$W` = 内容工作区根（含 `.to-video-root` 哨兵），`$P` = `$W/episodes/<slug>-video` 分集工程，`$V` = `$W/voices` 音色样本目录（gitignored）。

## 先判任务类型

| 任务 | 走法 | 先读 |
|---|---|---|
| 全新制作一集 | 下节「工作流」逐步过门；进每阶段前读速查表对应规格 | 阶段规格 |
| GL 精读产物成片 | 已有 /guided-learn《精读与通俗拆解》→ ① 走 C 型（冻结快照 + 穿透抽查），后续同主流水线 | [01](references/01-source-extraction.md) |
| 改稿迭代（已有集改口播） | 只改 `narration.md` → `build` → `check` → `tts` → `render` + `qa`；只改画面跳过 `tts`；需交付接工作流第 7 步 | 速查表 ③④⑨ |
| 润色成稿（语句断续、像 AI 写的） | 按 ⑤ 规格四层 pass 原地改稿，事实与句 id 冻结；独立子代理成文评审 → 改动句回 ④ 复核 → `build` → `check`（无分镜时改跑 `check_script.py --pre-tts`） | 速查表 ⑤ |
| 出英文版 / 双语 | `pipeline.toml` 声明 `narration.langs = ["zh","en"]` + 句 id 对齐的译稿 `narration.en.md`；tts/render/captions/deliver 加 `--lang en`（build/check 缺省全覆盖，产物加 `.en` 后缀） | [PIPELINE.md §五「双语渲染」](references/PIPELINE.md) |
| 评审后重配音（本人声音） | 零改稿换声：toml 升 indextts＋填 ref 指纹 → tts --allow-voice-switch --final-voice → render → qa → check → captions → render --final；en 追配同轨 [tts.en]（先跨语种试听，独立一次显式要求） | [07](references/07-tts-voice.md) |
| 交付归档 | 终渲后显式 `deliver`；根路径 `--root`（一次性）或 env `TO_VIDEO_DELIVER_ROOT`（持久，不进 toml） | 速查表 ⑩ |
| 环境 / 状态排障 | `pipeline.py doctor`（配置/时序/指纹/TTS/浏览器 `--clean-browsers`）/ `status`（新鲜度） | [PIPELINE.md §三](references/PIPELINE.md) |
| 本 Skill 自身缺陷或改进 | 走「自改进回路（RSI）」，不顺手改 `$T` | [RSI.md](RSI.md) |

## 工作流（全新制作）

每步过门才进下一步；门不过 = 按报错修 → 重跑同一命令至通过。

```bash
# 1) 初始化内容工作区（仅首次；幂等：哨兵、series 骨架、样本目录、包装器）
uv run --no-project $T/scripts/scaffold.py --init-workspace <目录>   # 即 $W

# 2) 建集（$W 内执行）：复制 frozen 骨架生成 $P（开箱即 edge 草声）；随后登记 series.json；
#    样本指纹可选（首次重配前），写进 $V/refs.toml（刻意不代做）
uv run --no-project $T/scripts/scaffold.py <slug>-video --title "本集标题"

# 3) ①–⑥ 内容层：research/ 取证 → planning.md → narration.md →（④ 校验 → ⑤ 成文优化）→ storyboard.md；
#    循环「改稿 → build → check」至零 FAIL
uv run --no-project $T/scripts/pipeline.py --project $P build
uv run --no-project $T/scripts/pipeline.py --project $P check

# 4) ⑦ TTS：edge 草声直跑；克隆升档才需 doctor＋试听＋--plan（见 07）
uv run --no-project $T/scripts/pipeline.py --project $P tts    # 秒级幂等；升档重配见任务表

# 5) ⑧ 场景：$P/video/src/scenes/ 与 Main.tsx 注册表全新撰写；循环至类型零错误
#    装依赖先 npm view remotion version 对照最新（规则见 §九）
cd $P/video && pnpm install && ./node_modules/.bin/tsc --noEmit

# 6) ⑨ 循环「修场景 → render → qa」至零 FAIL，才放行终渲
uv run --no-project $T/scripts/pipeline.py --project $P render   # → $P/out/draft.mp4
uv run --no-project $T/scripts/pipeline.py --project $P qa --video out/draft.mp4 --last-n 6 --check   # --video 按 $P 解析

# 7) ⑩ 终渲 + 字幕 + 交付（deliver 刻意不串联，须显式执行）
uv run --no-project $T/scripts/pipeline.py --project $P render --final
uv run --no-project $T/scripts/pipeline.py --project $P captions  # → $P/out/captions.{srt,vtt}
uv run --no-project $T/scripts/pipeline.py --project $P deliver   # → <根>/<系列id>/<标题> vN.mp4
```

## 十阶段速查

单入口 `pipeline.py`（完整形态 `$T/scripts/pipeline.py --project $P <cmd>`，下表只写子命令；工作区走 `$W` 薄包装）。「通过门」列与 [stages.toml](references/stages.toml) 的 `gate` 逐字同源（测试执法）。

| Stage | 做什么 | 规格链接 | 工具/命令 | 通过门 |
|---|---|---|---|---|
| ① 信源精读取证 | A 型论文：并行逐章；B 型活信源：固定提交取证 + 证据三级；C 型 GL 产物：冻结快照 + 穿透抽查 | [01](references/01-source-extraction.md) | A 型 `paper_extract.py`；B 型 `source_ledger.py` | 全部断言可回溯；RISKY=0 |
| ② 策划案 | 受众/结构/钩子候选矩阵/视觉契约（色彩语义映射核心概念） | [02](references/02-planning.md) | —（authored） | planning.md 六节齐 + 钩子候选矩阵 |
| ③ 逐字稿 | `narration.md` ★单一事实源 | [03](references/03-narration.md) | `build` | build_narration.py 通过（narration.json 是派生物） |
| ④ 双重校验 | 真实性回溯 + 易懂性 | [04](references/04-verification.md) | `check` | RISKY=0 且 REWRITE=0 |
| ⑤ 成文优化 | 四稿按结构→衔接→句子→词句四层 pass 改成人写模样；只改表达不改事实 | [05](references/05-prose-refinement.md) | —（authored；改后 `build` + `check`，无分镜时 `check_script.py --pre-tts`） | 成文评审 REWRITE=0 且改动句复核 RISKY=0、REWRITE=0 |
| ⑥ 分镜表 | 前四列 + 可选 Visual Lock；Morph 见 06 | [06](references/06-storyboard.md) | `check --check-scenes` | beat 覆盖率无缺句（--check-scenes 分镜↔代码互比） |
| ⑦ TTS 配音 | edge 草声直配（制作期）；IndexTTS-2.5 克隆本人点名后升档（manifest 契约一致） | [07](references/07-tts-voice.md) | `tts` / `captions` | edge 草声直行；indextts 另过本人显式授权（--final-voice）+ refs 指纹门 + 试听定档 + ETA 排期 |
| ⑧ Remotion 场景 | 代码动画实现；动效走 `src/motion/` 运动模型 | [08](references/08-remotion-implementation.md) | 工程内直调 `tsc --noEmit` 与 motion 测试 | tsc --noEmit 零错误 + 七条渲染红线 + 运动层铁律 |
| ⑨ 草渲 + 抽帧 QA | 草渲与 Transition/Loop 抽帧 | [09](references/09-render-qa.md) | `render` + `qa` | qa --check 自动体检零 FAIL（含尾幕渐黑必查） |
| ⑩ 终渲 + 交付 | 1080p30 成片 + srt/vtt 字幕 + 按系列/标题 vN 归档 | [10](references/10-final-render.md) | `render --final` + `captions` + `deliver` | 实测时长落在 pipeline.toml 的预算窗内 |

## 关键不变量

- 逐字稿只改 `narration.md`；`narration.json`/`manifest.json` 是派生物。
- **开篇钩子铁律**：首句 `p0-01` 以「这是 XXX ……」破题入场，权重高于标题、3–5 秒留存并抛核心引子；策划案必出 3–5 个候选 Hook 供人决策。
- **口播永不出现他集标题与集数序号**——顺序只活在视觉层与 `series.json`（执法 `check_series.py`）。
- **B 型三级证据纪律**：「他人对闭源产品源码的分析」属三级证据，口播必须带归属句、不得说成产品既成事实；活数据（行数/总量/star）不进口播。
- 每集 `pipeline.toml` 是可执行参数唯一来源（默认值在 `config.py` SCHEMA，toml 只写偏离）；README 不复制命令行参数。
- 时序常数只在 `video/src/timing.json`（TS 与 Python 双语共读同一 JSON）；运动语汇只在 `video/src/motion/`（frozen，改 = 模板 + 全集同步）。
- 声音样本是生物特征：不入库（`voices/refs.toml` 只存指纹），试听后即删。
- **配音人为触发**：IndexTTS 克隆仅本人显式点名时启用（实跑必带 `--final-voice`、zh/en 各算一次，`all` 永不透传；agent 不得主动建议，其余一律 edge 草声）——见 [07](references/07-tts-voice.md)。
- **复用边界**：Python 脚本集中共享（SSOT）；Remotion 原语复制不共享——复制源头 `assets/video-skeleton/`，`scaffold.py` 实例化、`verify_skeleton.py` 字节级执法漂移。
- **依赖版本策略**：优先最新稳定版（模板钉版/README 地板只是快照下限）；建集先 `npm view remotion version` 对照，Remotion 全家桶同 major 整组追新（drift 登记）、跨 major 走 RSI；细则见 [PIPELINE.md §九](references/PIPELINE.md)。
- **双锚点**：skill 根随安装位置（脚本自 `__file__` 向上找 `SKILL.md`），工作区根由哨兵搜索定位——机制与内容物理分离，互不牵连。
- **RSI 纪律**：本 Skill 自身的缺陷与改进一律走 [RSI.md](RSI.md) 回路（登记台账 → 另起子代理 → 四道门 → PR 回流）；制作中 `$T` 机制文件只读（例外仅台账与建模手册候选区两处仅追加），禁顺手改。
- **双语对齐**（双语集）：`narration.en.md` 与主稿句 id 1:1（build/check 执法）+ 基线锁防译稿静默失鲜；语言常数只在 `scripts/langs.py`（tts.py 内联镜像测试钉住）；tts/render/deliver 缺省只跑主语言、显式 `--lang` 才多版本（见 [PIPELINE.md §五「双语渲染」](references/PIPELINE.md)）。

## 运行时陷阱

- **Bash 调用间不保留 shell 变量**：`$T/$W/$P/$V` 是文档记号，命令写实际路径；工作目录保留，先 `cd` 进 `$W`。
- **`$T` 锚定的命令须在工作区内执行**：脚本读 env `TO_VIDEO_WORKSPACE` 或自 CWD 向上找 `.to-video-root`，找不到即大声退出——照报错指引处置，绝不静默猜根；包装器缺 skill 同照其打印指引处置。
- **脚本当黑盒**：优先走 `pipeline.py` 子命令；直调独立脚本先跑 `--help`，用途与调用形态查 [PIPELINE.md §三](references/PIPELINE.md)；不为使用通读源码。
- **机器属性只走 env**：交付根、TTS 音频库、IndexTTS 服务地址等永不进版本控制的 toml，注册表见 [PIPELINE.md「环境变量」](references/PIPELINE.md)。
- **浏览器任务一律 headless**：录制/渲染无头复用；孤儿回收走 `doctor --clean-browsers`，禁全局 pkill。

## 按需加载

| 文件 | 何时读 |
|---|---|
| 阶段规格 `references/NN-*.md` | 进入该阶段时（入口见速查） |
| [PIPELINE.md](references/PIPELINE.md) | 查脚本清单、`pipeline.toml` 字段、路径/环境变量、交付归档、双语、新集脚手架清单 |
| [MODELING-PLAYBOOK.md](references/MODELING-PLAYBOOK.md) | ② 视觉与 ⑥ 分镜设计前（必读） |
| [PRON-GLOSSARY.md](references/PRON-GLOSSARY.md) | 写逐字稿遇多音字/英文专名、复听纠读音时 |
| [VOICE-CLONING.md](references/VOICE-CLONING.md) | 首次部署 IndexTTS、准备样本、选风格档、配音排障 |
| [INDEXTTS-2.5-ADVANCED.md](references/INDEXTTS-2.5-ADVANCED.md) | 上游机制循证、配音质量调优（非日常） |
| [RSI.md](RSI.md) | 发现本 Skill 自身缺陷或改进项时 |
| [README.md](README.md) | 安装、更新、前置依赖版本 |

## 相邻技能协作

- **Stage ① 信源输入**：已有 /guided-learn 产出作 C 型信源直接成片（01「C 型」），不重新精读；无产物可先跑 /guided-learn。
- **Stage ⑥/⑧ 图示资产**：需要架构/流程类图解时调 `/archify` 出图，HTML 落 `$W` 下，`record_archify_all.py` 逐章录成动效素材；句级锚定覆盖门已串联进 `check`。
- **Stage ⑧ 精确 3D 资产（可选）**：信源涉机械结构/硬件、示意级几何不够时，装 text-to-cad 的 **cad 单 skill**（`npx skills add earthtojake/text-to-cad --skill cad`）出 GLB；链路与 3D 宪法见 [08「外部 CAD 资产」](references/08-remotion-implementation.md)。

## 自改进回路（RSI）

制片中发现**本 Skill 自身**缺陷或改进项（脚本报错、命令失败、规格漂移等）走 RSI：登记 [docs/.agents/issue.md](docs/.agents/issue.md) 台账，**另起子代理**调研改进并核验；视频内容问题走既有 QA 回路。四道门全过后发起改进 PR 并回报链接。内容侧例外：认可/否决的**动效建模方法**追加进有界的 [建模手册](references/MODELING-PLAYBOOK.md) 候选区。协议全文：[RSI.md](RSI.md)。
