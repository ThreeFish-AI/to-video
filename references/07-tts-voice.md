# Stage ⑦ TTS 配音：草声与克隆档位（skill 规格 · 07）

> 目标读者：执行配音阶段的代理/操作者。**参数与实测数据一律以 [VOICE-CLONING.md](VOICE-CLONING.md) §三–§六为准（链接非复制）**；本文件只承载操作顺序与决策点。
> 上游能力面、机制循证与提升路线图见 [INDEXTTS-2.5-ADVANCED.md](INDEXTTS-2.5-ADVANCED.md)；读音标注台账见 [PRON-GLOSSARY.md](PRON-GLOSSARY.md)。

## 两档生命周期（RSI-034）

| 档 | 引擎 | 时机 | 成本 |
|---|---|---|---|
| 草声 | edge 预置音色（scaffold 默认 `engine = "edge"`） | 制作全程：写稿→校验→成文→分镜→草渲→抽帧 QA→多轮评审 | 秒级、免费、需联网、免样本 |
| 终声 | IndexTTS-2.5 + 本人声音（`tts.style` 终声档锚点，默认 story） | **仅用户显式触发**：整集评审通过后重配（下节）/ 追配英文版 | 小时级长跑 |

草声期预算门：估算口径按终声档锚点分档（story=254，写稿即按终声语速预算）；**实测口径跳过**（edge 语速≠终声档，`check` 会点名）——升档中间态（toml 已翻 indextts、`.engine` 标记还是 edge）同样跳过，重配完成后门自动恢复实测执法。以 edge 为终声交付的集**删除 `tts.style` 锚点**恢复实测门。

## 决策树

**第 0 闸——草声即可？** `engine = "edge"`（新集默认）：直接 `pipeline.py tts`（自动注入 `--with edge-tts`，秒级需联网），无样本/指纹/试听/排期要求。以下 1–6 闸全部是**升档重配的前置**，草声期不需要。

**升档闸（engine=indextts，按序过闸，任何一闸不过不进长跑）**：

1. **样本就位？** `uv run --no-project $T/scripts/refs.py list` → 缺失则 `refs.py rebuild --name <样本>`（源录音是本人私有文件，路径记录在 `voices/refs.toml`）。
2. **指纹一致？** `refs.py verify --name <样本>` 必须全绿——sha1 与清单不符说明源文件/裁剪参数变了，**勿在未核验音色上烧 10 小时**；新样本须先过第 4 步试听再回填清单。
3. **风格定档？** 终声档锚点建集已声明（默认 **`story` 段落演绎**，[VOICE-CLONING §4.5](VOICE-CLONING.md)）；**升档前试听定档**：`tts_sample.py --ref <样本> --style story --play`。写稿阶段应已同产 `script/narration.cues.toml`（[references/03](./03-narration.md) 台本规约；无台本也能跑——自动分块 + 预设情绪，但块间情绪对比会打折）；**开篇块（`p0-01` 所在）宜在台本中显式定块、配与钩子匹配的情绪**——自动分块沿用预设情绪向量，开篇值得显式选型（[references/03](./03-narration.md) 开篇钩子铁律的声音通道）。**边听边记读错字**到 [PRON-GLOSSARY.md](PRON-GLOSSARY.md)，用 `<字|读音>` 标注修（写稿规约见 [references/03](./03-narration.md)）。**句尾英文词不赌采样、直接 CMU 标注**（采样层缺陷率约 50%；配方见 [VOICE-CLONING §5.4](VOICE-CLONING.md) take 验收节）。听完 `--cleanup` 或 `pipeline.py clean-samples`（生物特征）。
4. **排期对账？** `pipeline.py tts --plan`（纯本地）：story 档按**块**统计（块=缓存单位，改一句重录整块）+ 墙钟估算。ETA 与预期差 >15% 先查机器负载。
   束宽代价**不是无条件线性**：MPS 上近乎免费（整集 1→3 束实测 +4%），CUDA 上近线性——
   `--plan` 的 3 束常量刻意保守，见 [ADVANCED §6.2](INDEXTTS-2.5-ADVANCED.md)。
5. **做任何参数 A/B 前先固定 `--seed`**：上游 `do_sample` 恒 True 且全链路无种子，同句每次
   合成都是不同的 take，不固定种子听到的差异可能只是采样噪声（实测：带种子字节一致、
   不带则不同）。story 档预设自带 seed 4242（定档 take 可复现）；**`--seed-offset` 是整集口径**
   ——全部块换摘要、整集重录，且 `.engine` 签名不含 seed、护栏不拦；单块换 take 用台本
   `[take] <句id> = N`（只重录该句所在块，[VOICE-CLONING §4.5](VOICE-CLONING.md)）。
   但 **单句补配勿显式传 `--seed`**——seed 进缓存摘要，想重配一句会变成
   整集签名漂移、旧缓存被新签名覆盖（ISSUE-174）；实验性参数一律先 `--plan` 看失配面。
   重掷循环例外：只在带 seed 的隔离 digest 上掷、定稿回存 canonical digest（§5.4 协议；
   story 档改用台本 `[take]`，定稿值留在台本即 canonical、无需回存）。
6. **音色签名护栏**：与上次合成不一致会被 `.engine` 标记硬拦（显式 `--allow-voice-switch` 才放行）——这正是防「README 旧命令静默重录整集」的机制。

## 重配（评审后升档，用户显式触发）

触发话术（示例）：**「使用 index tts 2.5 及本人声音（风格：默认 story 段落演绎）重配本集视频」**——前提是整集已过多重复核与人工评审；未经用户显式要求**不得启动**（机器闸：`.engine` 护栏拦引擎/样本/风格变化，须显式 `--allow-voice-switch`）。存量集换档（sunny-steady → story）同配方，只改 `style` 一键。

流程（narration / storyboard / scenes **零改动**——音频换轨，时间轴随新 manifest 自动重排）：
1. 过上方升档闸 1–6（指纹、试听、排期）；
2. 该集 pipeline.toml `[tts]`：`engine = "indextts"` + 填 `ref` / `ref_sha1`（模板已注释预置，style 锚点已在）；首次上 story 且无 `script/narration.cues.toml` → 按 [references/03](./03-narration.md) 台本规约补写并 `build`；
3. `pipeline.py tts --plan` 对账 → `pipeline.py tts --allow-voice-switch`（幂等长跑，断点续跑/自愈见「调用形态」）；
4. 下游全量重推：`render` → `qa`（全场景 + 尾幕——时间轴位移必须重抽帧）→ `check`（实测门自动恢复执法）→（archify 集加 `check_archify.py`）→ `captions` → `render --final`；`deliver` 仍显式执行；
5. 完成后按 [VOICE-CLONING §5.4](VOICE-CLONING.md) 跑句尾英文词 take 验收；不合格句在台本写 `[take] <句id> = 1`（再不合格递增）重跑，`--plan` 应只显示该块待合成。

## 双语配音（en 版，双语集）

- **追配触发**（示例话术）：「使用 index tts 2.5 及本人声音（风格：xxx）**额外为本集视频配置英文配音**」——在既有 zh 集上追加完整英文版：`narration.langs` 补 `"en"` + `[tts.en]` 声明 `engine = "indextts"` 与跨语种 `ref`/`style`，其后走 [PIPELINE.md §五「双语渲染」](PIPELINE.md) 全轨：`narration.en.md` 句 id 1:1 → `build --lang en`（基线锁）→ `check --lang en` → **跨语种试听（下一条，不可跳）** → `tts --lang en` → `check_archify --lang en` → `render --lang en` + qa → `captions` / `deliver --lang en`（en 版本号独立）。
- **生效配置**：`[tts.en]` 可覆写 `engine / ref / ref_sha1 / style / voice`，缺省**继承 `[tts]` 同一样本与风格**；IndexTTS 的 `lang` 由语言自动解析为 `EN`（zh 版仍 `ZH`，两版 digest 与 `.engine` 签名天然隔离）。`engine = "edge"` 时英文缺省音色 `en-US-AndrewNeural`（注册表 [langs.py](../scripts/langs.py)）。zh 挂终声档锚点而 en 以 edge 为终声时，`[tts.en] style = ""` 可中和继承的锚点、恢复 en 实测门。
- **跨语种克隆必须先试听定档**（决策树第 3 闸的英文版，不可跳过）：`uv run --no-project --with mutagen $T/scripts/tts_sample.py --ref <样本> --lang EN --text "<本集最难英文句>"` ——同一样本跨语种可能带口音、风格档 alpha 是在中文选段上标定的；未试听不得进长跑。
- **en 版需 IndexTTS-2.5 服务**（`lang` 仅 2.5 的 infer 转发；服务版本见 `/health`）。
- **命令**：`uv run --no-project $T/scripts/pipeline.py --project $P tts --lang en`（缺省只跑 zh，显式 `--lang` 才跑英文——昂贵命令显式化）；产物落 `video/public/audio/en/`（独立 `.engine` 护栏与 manifest）；tts-store 按 digest 中英并存，互不覆盖。
- **ETA 口径**：`--plan` 的 4.2 s/句与 tts_progress 的秒/字基线均为 zh 标定——en 侧只作量级参考，热节流判定对 en 跳过（首集英文实测后校准）。

## 迭代与定稿

RSI-034 起**草声档就是最快的迭代载体**：改稿频繁期停在 edge（整集秒级重合成，真 manifest 校时间轴与分镜），多轮评审全用草声；字节冻结 + 评审通过后按「重配」节一次性升档 story。sunny 两遍法（逐句缓存省机器）仅剩存量 indextts 集的意义；story 块缓存改一句重录整块，见 VOICE-CLONING §六。

## 调用形态

- 编排入口（参数读自各集 `pipeline.toml`）：`uv run --no-project $T/scripts/pipeline.py --project $P tts [--plan|--style sunny]`（两可选参仅克隆档：edge 草声直行，`--plan` 会报「仅对 --engine indextts 生效」、`--style` 不生效）
- 直接薄包装（工程内）：`uv run --no-project --with mutagen scripts/tts.py --engine indextts …`（须带 `--expect-ref-sha1`，编排入口会自动带上）
- 服务端启动命令由 `tts.py`/`tts_sample.py` 在不可达时自动打印（可直接粘贴），手册见 [VOICE-CLONING.md §二](VOICE-CLONING.md)
- 长跑旁路监视：`uv run --no-project $T/scripts/tts_progress.py --project $P`（按逐句 mp3 mtime 重建墙钟进度与热漂移告警，story 块合成按 <1s 聚簇并折回每句口径，与合成进程零耦合——nohup 长跑时另开终端跑）
- 长跑自愈编排（RSI-022）：`uv run --no-project --with mutagen $T/scripts/tts_resume.py -- --engine indextts --project $P …`——服务掉线/MPS 挂死时按端口冷重启 + 真实退出码续跑（幂等缓存从断点续）；用法与参数定义见 [PIPELINE.md §三](PIPELINE.md) 脚本表，与本节「服务生命周期」同一端口纪律（重启只杀该端口 LISTEN）

## 服务生命周期：按需启停，用完即关

IndexTTS 服务端（端口取自 `tts.server`，默认 8766，下文命令以默认值示例）是**按需工具，不是常驻设施**：模型加载后常驻 10 GiB 量级 MPS 显存，长跑还会累积服务态（即使有每句 `empty_cache` 对冲，重启也总是最干净的状态复位），而冷启动仅 ~1–2 分钟。**Agent 在一次制片的全部合成需求结束后**（终渲交付完成，或本会话确认不再有 A/B 遍 / 试听 / 补句），必须执行：

1. **判在用**（多 Agent 同机互斥，两者皆空才可关）：
   ```bash
   lsof -nP -iTCP:8766 -sTCP:ESTABLISHED                          # 有非自己的连接 → 有人在用
   pgrep -fl "scripts/tts.py|tts_sample.py|tts_bench.py" # 有他人的合成进程 → 有人在用
   ```
2. **关闭**：`lsof -ti tcp:8766 -sTCP:LISTEN | xargs kill`——按端口只关判据所查的那一个实例；**勿用 `pkill -f tts_server.py`**，它会连带杀掉 8767 上他人的第二个 `tts_server.py` 实例（A/B 用）与改过端口的他人实例（判据面 ≠ 作用面；按端口而非扫 argv 的先例见 `tts_bench.py`）。服务是幂等拉起的——下次任何 tts 调用不可达时会自动打印启动命令，无需记忆。
3. **不预启动**：不要为「可能要用」提前拉服务；`tts --plan` 不触网，`doctor` 对离线服务只报 ⚠️ 不计失败——关停是常态，不是待修的红灯。

先完成者**不得**关闭他人正用的实例（以第 1 步判据为准）；适当重启本身即运维收益——清空累积态、归还显存。完整部署/启停命令见 [VOICE-CLONING.md §二](VOICE-CLONING.md)。

## 完成门（交给 Stage ⑨ 前）

- manifest 句数 = narration 句数；`pipeline.py check` 的实测时长口径落在预算窗内（草声期/升档中间态该口径跳过并点名，见「两档生命周期」——**终声完成后本门必须实测过窗才算交付**）；
- **首轮终声 TTS 完成后校准本集语速**（RSI-021；草声期**不回写**——edge 语速会污染终声口径）：写稿预算门的 `narration.chars_per_min` 默认层按 `tts.style` 分档（story=254、其余=280，档位表住 `scripts/config.py` 的 `STYLE_CHARS_PER_MIN`——**仅 story 有整集实测**，新档位首轮后按下述回写）；首轮完成后用 manifest 实测秒数复算 `本集字数 ÷ 实测分钟数`，与生效默认偏差 >3% 就把实测值写进本集 toml 的 `narration.chars_per_min`（显式覆写恒优先，下一集写稿即按本集实测口径执法）。上游教训：五集系列 ep1 首轮按 280 写 3961 字 → 实测外推 15.62 分超 [13.0, 14.6] 硬窗 → 回 ③ 减脂 317 字 → story 块缓存整失效全量重合成 ~40 分钟；后续四集按 254 直写全部一次过窗零返工；
- sidecar `{id}.sha` 逐句齐备（断点续跑的依据）；`.engine` 标记已更新；
- 句尾英文产品名收尾的句子跑无偏 ASR-与逐字稿 diff（**禁 `initial_prompt`**，判据组合见 [VOICE-CLONING §5.4](VOICE-CLONING.md)；候选管线门——自动化前人工执行）。
