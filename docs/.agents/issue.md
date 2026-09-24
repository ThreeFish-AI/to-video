# Issue 台账（RSI 回路的登记面）

本仓缺陷与改进的唯一登记处，由 [RSI.md](../../RSI.md) 回路消费。编号 `RSI-xxx` 三位递增，从 RSI-001 起——**刻意不用 `ISSUE-` 前缀**：本仓正文里的 ISSUE-162/170/175/188 等全部指向上游 [negentropy 的台账](https://github.com/ThreeFish-AI/negentropy/blob/master/docs/.agents/issue.md)，本地复用前缀必然混淆；引用上游教训一律写全 URL，不裸写编号。

纪律：

- 发现即登记，新条目追加文件末尾；同一问题只维护一处，复发不新开编号（在原条目追加带日期的复盘点）；
- 条目字段六段式：表因 / 根因 / 定性 / 处理方式 / 后续防范 / 同类问题影响（可选）；
- 登记本身不等于启动处理——处理走 RSI 回路（另起子代理 + 四道门 + PR）。

---

## RSI-001 Skill 缺陷与改进无处留存，经验随会话蒸发

**表因**：制片过程中（Agent 或用户）发现的本 Skill 缺陷与流程/制度/方法改进项，没有结构化留存处——README 只提供「开 Issue」一条人工渠道，AI Agent 的发现与改进经验随会话结束消失，同类问题跨会话反复踩坑。

**根因**：自 negentropy `apps/negentropy-influence/pipeline/` 抽取为独立技能时，带走了九阶段流水线，未带走 issue 台账与改进回流协议（上游 ISSUE 台账留在原仓）。

**定性**：非阻断改进（机制缺口，不卡单次制片，但侵蚀长期演化能力）。

**处理方式**：落地 RSI 钩子——根级 RSI.md 协议（触发分流、台账、子代理协议、四道门、两种模式、PR 规范、失败出路、降级路径、不变量保护清单）+ 本台账 + SKILL.md 挂点（自改进回路短节、关键不变量 1 条、尾部指针）+ skills/09 交付件清单复查项 + test_docs_paths 受检面扩至 RSI.md。

**后续防范**：发现即登记，禁止「顺手改」；制片中 `$T` 机制文件对主代理只读（例外：登记台账本身），机制改动一律另起子代理过门；非阻断改进默认排队，防「顺手重构」借道 RSI。

**同类问题影响**：上游 negentropy 的 ISSUE-161/164/168/170/188 等历史教训此前只能以 URL 外链引用、无法在本仓续写——本台账启用后，本仓新教训有了本地归宿（上游教训仍写全 URL 引用，不迁移）。

## RSI-002 帧率门读错字段：CDP 档 measured_fps 恒 25，退化门与素材完整门双双失明

**表因**：PR #9 评审（2026-09-23）发现，`record_archify_all.py` 新增的「帧率相对退化 >10% 点名补录」与 `check_archify.py` 素材完整门（`min_fps` 18）都按 sidecar 的 `measured_fps` 判定——在 chapter 默认的 `--capture cdp` 档下两道门永不触发；同批文档（skills/09 换机 runbook）却写的是 `capture_fps`，代码、文档、录制器三处口径分叉。

**根因**：CDP 档产物是「槽位补帧 + `-framerate 25` 合成」的 **CFR 25fps**，对输出文件实测的 `measured_fps` 按构造恒≈25；真实采集帧率只记录在逐章 `capture_fps`。录制器自身按 `eff = capture_fps or measured_fps` 判低帧率（record_archify.py 章节 sidecar 构造处），下游门从旧 playwright 档（VFR，measured 即真值）沿用了字段名，没随采集档切换而换口径；且 `test_record_archify_all.py` 以 `importorskip("playwright")` 守门，默认依赖集下整文件被跳过，新增逻辑从未被执行。

**定性**：阻断级缺陷（门形同虚设：降质素材绿着门进片，trimBefore 掐点整体漂移）。

**处理方式**：两处统一为与录制器 `eff` 同构的逐章口径（`capture_fps` 优先、回退 `measured_fps`）——`record_archify_all.chapter_fps()` / `fps_degraded()` 抽为纯函数并补用例；`check_archify` ③ 改逐章取 min，新增 `tests/test_check_archify.py`（含 CFR 伪装用例：measured 25 / capture 12 → WARN）。同 PR 一并修正：lead_sec 全 0 门由全局判改按图判（增量重录形态漏报）、`tts_server` 的 `empty_cache` 移入 `finally`（失败路径同样归还缓存）。

**后续防范**：凡读 fps 的门一律消费「有效采集帧率」而非输出文件帧率；新增门必须附一条「在默认档真实形态下会红」的用例（CFR 伪装型输入）；受 `importorskip` 守门的测试文件，改动其被测模块时须带齐依赖（`--with playwright` + `TO_VIDEO_WORKSPACE` 哨兵）显式跑一次。

**同类问题影响**：`archify_lead.py` 以 `measured_fps` 做帧号→时间换算，CDP 档下恰好正确（输出即 CFR 25），playwright 档（VFR）仅近似——若后续改采集档或输出帧率，须同步复核该换算。

## RSI-003 动效画面建模经验无沉淀通道，且沉淀面无体量约束

**表因**：制片中被用户或主 Agent 认可/否决的建模方法（概念 → 画面/母题/构图/动效强度的映射，如「恒定视觉锚」「以静写闷」）只能以散文偶然埋进 skills/06 母题表、skills/08 缺陷表等规格正文——跨集可复用却无结构化入口、无认可强度记录、无淘汰机制；若放任逐集追加，规格正文会单调膨胀（skills/06 已约 6150 字，为全仓最大），新经验被埋进中段（context rot / lost in the middle）。

**根因**：RSI-001 落地的回路只分流「Skill 自身缺陷 / 流程制度改进」两类，未覆盖「内容创作经验」这一第三类信号；且全仓没有任何文档体量执法先例，经验沉淀面天然无界。

**定性**：非阻断改进（不卡单次制片，但创作经验随会话蒸发、跨集重复试错）。

**处理方式**：RSI 增「建模经验分支」——新增有界经验库 [pipeline/MODELING-PLAYBOOK.md](../../pipeline/MODELING-PLAYBOOK.md)（条目化、权重生命周期、候选区攒批策展）+ 规则唯一实现 `pipeline/scripts/check_playbook.py`（3000 字硬上限、2700 触发压缩、压至 2250，滞回）+ RSI.md 策展协议与六级压缩阶梯 + 不变量第 15 条 + 02/05/06/08/09 消费指针 + test_modeling_playbook 执法；设计依据见 [docs/research/modeling-experience-distillation.md](../research/modeling-experience-distillation.md)。PR：[#12](https://github.com/ThreeFish-AI/to-video/pull/12)（commit `53ea0d9` 机制与测试、`56163ae` 研究文档与回路图）。

**后续防范**：经验只从显式信号入库（用户认可/否决、复用后的返工），主 Agent 自评为弱信号（w=1）、不得单独晋升定式；超限只许按阶梯逐级压缩，禁止整文件重写（ACE context collapse）与「把条目搬进规格正文腾预算」（转移熵而非减熵）。

**同类问题影响**：PRON-GLOSSARY 是同构的跨集沉淀台账，目前体量小（约 530 字）未设上限；若其增长到数千字量级，可复用本机制的计数器与压缩阶梯。

## RSI-004 全链路单语言单槽位，无法产出英文版视频

**表因**：用户提出双语需求（2026-09-24）：逐字稿、字幕、配音等制作过程支持中英双模式，可同时产出两版或择一。现状全链路每类产物只有一个路径槽位（`narration.json` / `audio/{id}.mp3` / `captions.srt` / `final.mp4`），且多处硬编码中文假设：`check_script.py` 整句无汉字即 FAIL、预算门按 280 字/分计 `len(text)`、`captions.py`/`Subtitle.tsx` 只剥 `。`、edge 音色硬编码 `zh-CN-YunxiNeural`、IndexTTS `lang` 恒 `ZH`。

**根因**：管线抽取自纯中文制作实践，语言从未作为独立维度建模——既无语言注册表（tts_code/音色/长度单位/路径后缀的唯一事实源），也无分集级语言声明与运行期选择；Remotion frozen 骨架（Root/NarrationAudio/Subtitle/ChapterProgress）静态锚定 `audio/manifest.json` 与 `chapters.json` 中文标题。

**定性**：非阻断改进（能力缺口，不卡既有制片）。

**处理方式**：双语渲染改造（分支 ThreeFish-AI/palembang-v1，PR 见回填）——新增 `pipeline/scripts/langs.py` 语言注册表（机制）+ `pipeline.toml` 新键 `narration.langs` / `narration.words_per_min` / `[narration.en]` / `[tts.en]`（策略）+ `pipeline.py --lang`（执行）；英文稿 `narration.en.md` 与主稿句 id 1:1 对齐 + 基线锁 `narration.en.lock.json`；配音/字幕/渲染/交付按语言加后缀槽位（`audio/en/`、`captions.en.*`、`*.en.mp4`）；Remotion 经 `--props {"lang"}` + `i18n.tsx` context 切换；骨架分代引入 `[[generation]]` 旧代指纹原子登记（替代逐集 drift）。zh 全产物字节不变为硬约束。

**后续防范**：语言相关常数（音色/语速/长度单位/路径后缀）一律进 `langs.py` 或 `config.SCHEMA`，禁止在消费者内联；tts.py 受 paths.py 导入边界约束不得 import 同目录模块，其内联镜像表由一致性测试钉住；新增门遵循「先探针后成门」（英文读法陷阱须有 TextNormalizer 实测证据）。评审回归（2026-09-24）六条经验：① 失鲜锁不得「重建即刷新」——缺省 `build` 先 zh 后 en 会在 check 前抹掉信号，锁合并取 gettext fuzzy 语义（译句未动则主稿基线不前移，`--accept` 显式确认）；② 逐语言覆写值复用基础层同一校验（`config._is_window`），否则坏窗口只降级为跳门 WARN；③ status/doctor 这类容忍配置 FAIL 的诊断路径，对声明值须先滤非法项再派生路径；④ 分代原子性判定须把 `[[drift]]` 放行的旧文件计入组，否则半同步对 drift 集隐身；⑤ 跨引擎通用的一致性校验须在参数解析处统一执法，不得只挂在某个引擎分支的护栏里（`tts.py` 的 `--lang` / `--narration-lang` 冲突此前仅 edge 拦截，indextts 会以 ZH 归一化合成英文稿）；⑥ 从多个输入推断同一维度时，每个输入都须参与推断并互校（qa `--compare` 两路径曾被忽略，en 对拍静默取 zh 时间轴）。

**同类问题影响**：`tts_progress.py` 秒/字基线与 `tts.py` `--plan` 4.2 s/句均为 zh 标定，en 侧只报不判（首集英文实测后校准）；series.json 标题仅 zh，`check_series` 他集标题互查与 `deliver` 英文命名暂以 zh 标题为事实源。
