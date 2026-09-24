# Stage ⑥ TTS 配音：声音克隆决策树（skill 规格 · 07）

> 目标读者：执行配音阶段的代理/操作者。**参数与实测数据一律以 [VOICE-CLONING.md](VOICE-CLONING.md) §三–§六为准（链接非复制）**；本文件只承载操作顺序与决策点。
> 上游能力面、机制循证与提升路线图见 [INDEXTTS-2.5-ADVANCED.md](INDEXTTS-2.5-ADVANCED.md)；读音标注台账见 [PRON-GLOSSARY.md](PRON-GLOSSARY.md)。

## 决策树（按序过闸，任何一闸不过不进长跑）

1. **样本就位？** `uv run --no-project $T/scripts/refs.py list` → 缺失则 `refs.py rebuild --name <样本>`（源录音是本人私有文件，路径记录在 `voices/refs.toml`）。
2. **指纹一致？** `refs.py verify --name <样本>` 必须全绿——sha1 与清单不符说明源文件/裁剪参数变了，**勿在未核验音色上烧 10 小时**；新样本须先过第 4 步试听再回填清单。
3. **风格定档？** 首次/换风格必过小样 A/B：`tts_sample.py --ref <样本> --all-styles --play`；再用**领航片段**（本集最难的 6–8 句：长分句/枚举清单/带小数点数字/含英文专名/含多音字）在该风格下整句合成试听。**边听边记读错字**到 [PRON-GLOSSARY.md](PRON-GLOSSARY.md)，用 `<字|读音>` 标注修（写稿规约见 [references/03](./03-narration.md)）。**句尾英文词不赌采样、直接 CMU 标注**（采样层缺陷率约 50%；配方见 [VOICE-CLONING §5.4](VOICE-CLONING.md) take 验收节）。听完 `--cleanup` 或 `pipeline.py clean-samples`（生物特征）。
4. **排期对账？** `pipeline.py tts --plan`（纯本地）：待合成句数 × 束宽档 + 墙钟估算。ETA 与预期差 >15% 先查机器负载。
   束宽代价**不是无条件线性**：MPS 上近乎免费（整集 1→3 束实测 +4%），CUDA 上近线性——
   `--plan` 的 3 束常量刻意保守，见 [ADVANCED §6.2](INDEXTTS-2.5-ADVANCED.md)。
5. **做任何参数 A/B 前先固定 `--seed`**：上游 `do_sample` 恒 True 且全链路无种子，同句每次
   合成都是不同的 take，不固定种子听到的差异可能只是采样噪声（实测：带种子字节一致、
   不带则不同）。但 **单句补配勿显式传 `--seed`**——seed 进缓存摘要，想重配一句会变成
   整集签名漂移、旧缓存被新签名覆盖（ISSUE-174）；实验性参数一律先 `--plan` 看失配面。
   重掷循环例外：只在带 seed 的隔离 digest 上掷、定稿回存 canonical digest（§5.4 协议）。
6. **音色签名护栏**：与上次合成不一致会被 `.engine` 标记硬拦（显式 `--allow-voice-switch` 才放行）——这正是防「README 旧命令静默重录整集」的机制。

## 双语配音（en 版，双语集）

- **生效配置**：`[tts.en]` 可覆写 `engine / ref / ref_sha1 / style / voice`，缺省**继承 `[tts]` 同一样本与风格**；IndexTTS 的 `lang` 由语言自动解析为 `EN`（zh 版仍 `ZH`，两版 digest 与 `.engine` 签名天然隔离）。`engine = "edge"` 时英文缺省音色 `en-US-AndrewNeural`（注册表 [langs.py](../scripts/langs.py)）。
- **跨语种克隆必须先试听定档**（决策树第 3 闸的英文版，不可跳过）：`uv run --no-project --with mutagen $T/scripts/tts_sample.py --ref <样本> --lang EN --text "<本集最难英文句>"` ——同一样本跨语种可能带口音、风格档 alpha 是在中文选段上标定的；未试听不得进长跑。
- **en 版需 IndexTTS-2.5 服务**（`lang` 仅 2.5 的 infer 转发；服务版本见 `/health`）。
- **命令**：`uv run --no-project $T/scripts/pipeline.py --project $P tts --lang en`（缺省只跑 zh，显式 `--lang` 才跑英文——昂贵命令显式化）；产物落 `video/public/audio/en/`（独立 `.engine` 护栏与 manifest）；tts-store 按 digest 中英并存，互不覆盖。
- **ETA 口径**：`--plan` 的 4.2 s/句与 tts_progress 的秒/字基线均为 zh 标定——en 侧只作量级参考，热节流判定对 en 跳过（首集英文实测后校准）。

## 两遍法（长片的既定工作法）

草稿遍 `--style sunny`（快 ≈3.4×）拿真 manifest 校时间轴与分镜 → 定稿遍回到成片档（`sunny-steady`，beams=3）。**改稿只废改动句；换档全量重合成**（摘要含 style/ref/束宽，见 VOICE-CLONING §六）。B 遍必须在文稿字节冻结后启动。

## 调用形态

- 编排入口（参数读自各集 `pipeline.toml`）：`uv run --no-project $T/scripts/pipeline.py --project $P tts [--plan|--style sunny]`
- 直接薄包装（工程内）：`uv run --no-project --with mutagen scripts/tts.py --engine indextts …`（须带 `--expect-ref-sha1`，编排入口会自动带上）
- 服务端启动命令由 `tts.py`/`tts_sample.py` 在不可达时自动打印（可直接粘贴），手册见 [VOICE-CLONING.md §二](VOICE-CLONING.md)
- 长跑旁路监视：`uv run --no-project $T/scripts/tts_progress.py --project $P`（按逐句 mp3 mtime 重建墙钟进度与热漂移告警，与合成进程零耦合——nohup 长跑时另开终端跑）

## 服务生命周期：按需启停，用完即关

IndexTTS 服务端（端口取自 `tts.server`，默认 8766，下文命令以默认值示例）是**按需工具，不是常驻设施**：模型加载后常驻 10 GiB 量级 MPS 显存，长跑还会累积服务态（即使有每句 `empty_cache` 对冲，重启也总是最干净的状态复位），而冷启动仅 ~1–2 分钟。**Agent 在一次制片的全部合成需求结束后**（终渲交付完成，或本会话确认不再有 A/B 遍 / 试听 / 补句），必须执行：

1. **判在用**（多 Agent 同机互斥，两者皆空才可关）：
   ```bash
   lsof -nP -iTCP:8766 -sTCP:ESTABLISHED                          # 有非自己的连接 → 有人在用
   pgrep -fl "scripts/tts.py|tts_sample.py|tts_bench.py" # 有他人的合成进程 → 有人在用
   ```
2. **关闭**：`lsof -ti tcp:8766 -sTCP:LISTEN | xargs kill`——按端口只关判据所查的那一个实例；**勿用 `pkill -f tts_server.py`**，它会连带杀掉 `tts_bench.py` 的 8767 A/B 实例与改过端口的他人实例（判据面 ≠ 作用面；按端口而非扫 argv 的先例见 `tts_bench.py`）。服务是幂等拉起的——下次任何 tts 调用不可达时会自动打印启动命令，无需记忆。
3. **不预启动**：不要为「可能要用」提前拉服务；`tts --plan` 不触网，`doctor` 对离线服务只报 ⚠️ 不计失败——关停是常态，不是待修的红灯。

先完成者**不得**关闭他人正用的实例（以第 1 步判据为准）；适当重启本身即运维收益——清空累积态、归还显存。完整部署/启停命令见 [VOICE-CLONING.md §二](VOICE-CLONING.md)。

## 完成门（交给 Stage ⑧ 前）

- manifest 句数 = narration 句数；`pipeline.py check` 的实测时长口径落在预算窗内；
- sidecar `{id}.sha` 逐句齐备（断点续跑的依据）；`.engine` 标记已更新；
- 句尾英文产品名收尾的句子跑无偏 ASR-与逐字稿 diff（**禁 `initial_prompt`**，判据组合见 [VOICE-CLONING §5.4](VOICE-CLONING.md)；候选管线门——自动化前人工执行）。
