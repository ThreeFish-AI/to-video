---
name: to-video
description: 把论文、技术文档、代码仓库或课程站点等信源做成动效图解科普视频（animated explainer video）的九阶段流水线：信源精读取证、策划、逐字稿（单一事实源）、真实性与易懂性校验、分镜、声音克隆或预置音色配音（TTS）、Remotion 代码动画、抽帧 QA、终渲字幕与交付归档，支持中英双语版本。Use when 用户想把一篇论文、文档或代码讲成视频，制作或迭代科普解说视频（改稿后重配音、重渲染），初始化视频工作区或新建一集，编写 narration.md / storyboard.md，跑配音、渲染、抽帧质检或交付归档，或询问这套流水线的用法——即使没有点名 to-video。不用于剪辑或转码已有视频、通用产品宣传片、幻灯片、单独绘制架构图，或不产出视频的论文精读。
license: MIT
compatibility: 渲染与抽帧 QA 仅支持 macOS（场景字体依赖系统 CJK 字体栈）；需要 uv、pnpm 与 Node.js（版本要求见 README 前置依赖）；声音克隆需本地 IndexTTS-2.5 服务，edge-tts 预置音色兜底需联网；宿主须能执行 Bash。
metadata:
  version: "1.0.0"
  author: "ThreeFish-AI"
  source: "extracted from ThreeFish-AI/negentropy apps/negentropy-influence"
allowed-tools: Read Write Edit Glob Grep Bash
---

# to-video：动效图解科普视频流水线（路由壳）

本 Skill 是**路由层**：内容 SSOT 在 `references/01–09.md`（九篇阶段规格），工具 SSOT 在 `scripts/`，九阶段的唯一机器可读声明是 [references/stages.toml](references/stages.toml)；此处只给路由、指针与不变量，不复制正文（防第二事实源）。

命令统一用路径变量（唯一定义处 [references/PIPELINE.md](references/PIPELINE.md)）：`$T` = skill 根（本文件所在目录；Claude Code 下即 `${CLAUDE_SKILL_DIR}`），`$W` = 内容工作区根（含 `.to-video-root` 哨兵），`$P` = `$W/episodes/<slug>-video` 分集工程，`$V` = `$W/voices` 音色样本目录（整目录 gitignored）。

## 先判任务类型

| 任务 | 走法 | 先读 |
|---|---|---|
| 全新制作一集 | 下节「工作流」逐步过门；进入每个阶段前读速查表对应规格 | 阶段规格 |
| 改稿迭代（已有集改口播） | 只改 `narration.md` → `build` → `check` → `tts`（逐句内容寻址缓存，只重合成改动句）→ `render` + `qa`；只改画面则跳过 `tts`；需交付时接工作流第 7 步 | 速查表 ③④⑧ |
| 出英文版 / 双语 | `pipeline.toml` 声明 `narration.langs = ["zh","en"]` + 句 id 对齐的译稿 `narration.en.md`；tts/render/captions/deliver 显式加 `--lang en`（build/check 缺省覆盖全部声明语言，产物加 `.en` 后缀） | [PIPELINE.md §五「双语渲染」](references/PIPELINE.md) |
| 交付归档 | 终渲后显式 `deliver`；根路径 `--root`（一次性）或 env `TO_VIDEO_DELIVER_ROOT`（持久，写进 shell profile 而非 toml） | 速查表 ⑨ |
| 环境 / 状态排障 | `pipeline.py doctor`（配置、时序 SSOT、样本指纹、IndexTTS 服务自检）/ `pipeline.py status`（阶段新鲜度） | [PIPELINE.md §三](references/PIPELINE.md) |
| 本 Skill 自身缺陷或改进 | 走下文「自改进回路（RSI）」，不顺手改 `$T` | [RSI.md](RSI.md) |

## 工作流（全新制作）

每步过门才进下一步；门不过 = 按报错修 → 重跑同一命令，直到通过（报错会点名文件与句 id）。

```bash
# 1) 初始化内容工作区（仅首次；幂等：哨兵、series 骨架、样本目录、工作区级包装器）
uv run --no-project $T/scripts/scaffold.py --init-workspace <目录>   # 即 $W

# 2) 建集（在 $W 内执行）：复制 frozen 骨架生成 $P；随后人工登记 series.json、
#    把样本指纹写进 $V/refs.toml（脚手架刻意不代做，清单见其结尾输出）
uv run --no-project $T/scripts/scaffold.py <slug>-video --title "本集标题"

# 3) ①–⑤ 内容层：$P/research/ 取证 → planning.md → narration.md → storyboard.md；
#    循环「改稿 → build → check」至零 FAIL（check 自动串联 archify 覆盖门）
uv run --no-project $T/scripts/pipeline.py --project $P build
uv run --no-project $T/scripts/pipeline.py --project $P check

# 4) ⑥ TTS：先预演排期；正式合成前置 = doctor 自检 + 样本试听（07 规格）
uv run --no-project $T/scripts/pipeline.py --project $P tts --plan
uv run --no-project $T/scripts/pipeline.py --project $P tts    # 长跑，幂等续跑

# 5) ⑦ 场景：$P/video/src/scenes/ 与 Main.tsx 注册表全新撰写；循环至类型零错误
cd $P/video && pnpm install && ./node_modules/.bin/tsc --noEmit

# 6) ⑧ 循环「修场景 → render → qa」至零 FAIL，才放行终渲
uv run --no-project $T/scripts/pipeline.py --project $P render   # → $P/out/draft.mp4
uv run --no-project $T/scripts/pipeline.py --project $P qa --video out/draft.mp4 --last-n 6 --check   # --video 按 $P 解析；--scene/--last-n/句 id 三选一

# 7) ⑨ 终渲 + 字幕 + 交付（deliver 刻意不串联，须显式执行）
uv run --no-project $T/scripts/pipeline.py --project $P render --final
uv run --no-project $T/scripts/pipeline.py --project $P captions  # → $P/out/captions.{srt,vtt}
uv run --no-project $T/scripts/pipeline.py --project $P deliver   # → <根>/<系列id>/<标题> vN.mp4
```

## 九阶段速查

单入口 `pipeline.py`（完整形态 `$T/scripts/pipeline.py --project $P <cmd>`，下表只写子命令；工作区内等价 `$W/scripts/pipeline.py <cmd>`）。「通过门」列与 [stages.toml](references/stages.toml) 的 `gate` 逐字同源（测试执法），`pipeline.py stages` 可打印全表。

| Stage | 做什么 | 规格链接 | 工具/命令 | 通过门 |
|---|---|---|---|---|
| ① 信源精读取证 | A 型论文：并行子代理逐章 + 官方站点补充；B 型文档/代码/站点：固定提交取证 + 证据三级 | [01](references/01-source-extraction.md) | A 型 `paper_extract.py`；B 型 `source_ledger.py` | 全部断言可回溯；RISKY=0 |
| ② 策划案 | 受众/结构/视觉契约（色彩语义映射本集核心概念） | [02](references/02-planning.md) | —（authored） | planning.md 六节齐 |
| ③ 逐字稿 | `narration.md` ★单一事实源 | [03](references/03-narration.md) | `build` | build_narration.py 通过（narration.json 是派生物） |
| ④ 双重校验 | 真实性回溯 + 易懂性 | [04](references/04-verification.md) | `check` | RISKY=0 且 REWRITE=0 |
| ⑤ 分镜表 | 镜号 ↔ 句 id 区间 ↔ 画面 ↔ 动效；beat 覆盖性 | [05](references/05-storyboard.md) | `check --check-scenes` | beat 覆盖率无缺句（--check-scenes 分镜↔代码互比） |
| ⑥ TTS 配音 | 声音克隆（IndexTTS-2.5；备选 edge 预置音色，manifest 契约一致） | [07](references/07-tts-voice.md) | `tts --plan` / `captions` | refs 指纹门 + 试听定档 + ETA 排期 |
| ⑦ Remotion 场景 | 代码动画实现；动效走 `src/motion/` 运动模型 | [06](references/06-remotion-implementation.md) | 工程内直调 `tsc --noEmit` 与 motion 测试 | tsc --noEmit 零错误 + 七条渲染红线 + 运动层铁律 |
| ⑧ 草渲 + 抽帧 QA | 半分辨率快速迭代（`--beat-heads` 补入场瞬态盲区） | [08](references/08-render-qa.md) | `render` + `qa` | qa --check 自动体检零 FAIL（含尾幕渐黑必查） |
| ⑨ 终渲 + 交付 | 1080p30 成片 + srt/vtt 字幕 + 按系列/标题 vN 归档 | [09](references/09-final-render.md) | `render --final` + `captions` + `deliver` | 实测时长落在 pipeline.toml 的预算窗内 |

⚠️ **序号与文件号刻意错位**：Stage ⑥ ↔ `07-tts-voice`、Stage ⑦ ↔ `06-remotion-implementation`（入链 ≥5 处，重命名代价大于收益），由 [tests/test_stages.py](tests/test_stages.py) 执法——勿据序号猜文件名，更勿「顺手对齐」。

## 关键不变量

- 逐字稿只改 `narration.md`；`narration.json` / `manifest.json` 是派生物。
- **口播永不出现他集标题与集数序号**——顺序只活在视觉层与 `series.json`（执法：`check_series.py`，建议挂 pre-commit）。
- **B 型三级证据纪律**：「他人对闭源产品源码的分析」属三级证据，口播必须带归属句、不得表述为产品既成事实；活数据（行数/总量/star）不进口播。
- 每集 `pipeline.toml` 是可执行参数唯一来源（默认值在 `config.py` 的 SCHEMA，toml 只写偏离）；README 不复制命令行参数。
- 时序常数只在 `video/src/timing.json`（`timing.ts` 与 Python 双语共读同一 JSON）；运动语汇只在 `video/src/motion/`（frozen，改 = 模板 + 全集同步）。
- 声音样本是生物特征：不入库（`voices/refs.toml` 只存指纹），试听后即删。
- **复用边界**：Python 脚本集中共享（SSOT）；Remotion 原语复制不共享——复制源头是 `assets/video-skeleton/`，由 `scaffold.py` 实例化、`verify_skeleton.py` 字节级执法漂移。
- **双锚点**：skill 根随安装位置（脚本自 `__file__` 向上找 `SKILL.md`），工作区根由哨兵搜索定位——机制与内容物理分离，各居任意目录互不牵连。
- **RSI 纪律**：本 Skill 自身的缺陷与改进一律走 [RSI.md](RSI.md) 回路（登记台账 → 另起子代理 → 四道门 → PR 回流）；制作过程中 `$T` 机制文件只读（例外仅两处仅追加的登记面：台账、建模手册候选区），禁止顺手改。
- **双语对齐**（双语集）：`narration.en.md` 与主稿句 id 1:1（build/check 执法）+ 基线锁防译稿静默失鲜；语言常数只在 `scripts/langs.py`（tts.py 内联镜像由测试钉住）；tts/render/deliver 缺省只跑主语言、显式 `--lang` 才多版本（机制见 [references/PIPELINE.md §五「双语渲染」](references/PIPELINE.md)）。
- **包装器 ABI**：`pipeline/scripts` 是指向 `scripts/` 的软链——已部署分集的 frozen 薄包装按该路径定位 skill，删除即全部失效（迁移映射见 [pipeline/README.md](pipeline/README.md)）。

## 运行时陷阱

- **Bash 调用间不保留 shell 变量**：`$T/$W/$P/$V` 是文档记号，每条命令写成实际路径；工作目录会保留，可先 `cd` 进 `$W`。
- **`$T` 锚定的命令须在工作区内执行**：脚本读 env `TO_VIDEO_WORKSPACE` 或自 CWD 向上找 `.to-video-root`，找不到即大声退出——照报错指引初始化或指派工作区，绝不静默猜根；包装器找不到 skill 时同样照其打印的安装指令处置。
- **脚本当黑盒**：优先走 `pipeline.py` 子命令；直调独立脚本先跑 `--help`，用途与调用形态查 [PIPELINE.md §三](references/PIPELINE.md) 脚本表；不为使用而通读源码（RSI 调研例外）。
- **机器属性只走 env**：交付根、TTS 音频库、IndexTTS 服务地址等永不写进受版本控制的 toml，注册表见 [PIPELINE.md「环境变量」](references/PIPELINE.md)。

## 按需加载

| 文件 | 何时读 |
|---|---|
| 阶段规格 `references/0N-*.md` | 进入该阶段时（入口见速查表） |
| [references/PIPELINE.md](references/PIPELINE.md) | 查脚本清单、`pipeline.toml` 字段、路径变量与环境变量、交付归档、双语机制、新集脚手架清单 |
| [references/MODELING-PLAYBOOK.md](references/MODELING-PLAYBOOK.md) | ② 视觉语言与 ⑤ 分镜设计前（有界短文，必读） |
| [references/PRON-GLOSSARY.md](references/PRON-GLOSSARY.md) | 写逐字稿遇多音字 / 英文专名、复听纠读音时 |
| [references/VOICE-CLONING.md](references/VOICE-CLONING.md) | 首次部署 IndexTTS、准备参考样本、选风格档、配音排障 |
| [references/INDEXTTS-2.5-ADVANCED.md](references/INDEXTTS-2.5-ADVANCED.md) | 上游机制循证、配音质量调优（非日常） |
| [RSI.md](RSI.md) | 发现本 Skill 自身缺陷或改进项时 |
| [README.md](README.md) | 安装、更新、前置依赖版本 |

## 相邻技能协作

- **Stage ① 深读信源**：建议先调 `/guided-learn`——其「全貌解剖（先梳理后总结）+ 底层规律与争议提炼」方法论可直接复用为分章子代理的输出结构约束。
- **Stage ⑤/⑦ 图示资产**：需要架构/流程类图解时调 `/archify` 出图，HTML 落 `$W` 下，再由 `record_archify_all.py` 逐章录制为动效素材；句级锚定覆盖门（`check_archify_coverage.py`）已自动串联进 `check`。

## 自改进回路（RSI）

制片过程中（Agent 或用户）发现**本 Skill 自身**的缺陷或流程/制度/方法改进项——脚本误报漏报、文档命令复制即跑失败、规格与实现漂移等——走 RSI：发现即登记 [docs/.agents/issue.md](docs/.agents/issue.md) 台账，**另起子代理**调研改进并核验；视频内容质量问题不在此列（走 Stage ④/⑧ 既有 QA 回路）。四道门（问题属实 / 方案比选正确 / 正向收益 / 无损历史）全过后自动向本仓发起改进 PR 并回报链接。唯一的内容侧例外：被认可/否决的**动效画面建模方法**追加进有界的 [建模手册](references/MODELING-PLAYBOOK.md) 候选区，交付后由策展子代理攒批并入（字数上限与压缩阶梯见 RSI.md 第十节）。协议全文：[RSI.md](RSI.md)。
