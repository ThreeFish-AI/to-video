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

## RSI-005 scaffold 结尾提示仍写 `pnpm install --ignore-workspace`，与 ISSUE-175 后的既定结论相悖

**表因**：`scaffold.py` 的「接下来必须人工完成」结尾提示第 7 条仍打印 `cd video && pnpm install --ignore-workspace`。2026-09 结论反转后（各分集 video/ 已入库 pnpm-workspace.yaml 自锚 + allowBuilds esbuild，见 ISSUE-175），加 `--ignore-workspace` 会把分集自己的 workspace 一并忽略，install 以 ERR_PNPM_IGNORED_BUILDS 非零退出、node_modules 半残——新集首装即踩。

**根因**：提示文案是 ISSUE-175 改造时唯一漏改的第四处声明（机制本体、README、06 规格命令闭环均已改裸 install）；scaffold 输出无人回归（新集脚手架是低频路径）。

**定性**：低危高摩擦——失败形态可自愈（去掉 flag 重跑即过），但非零退出与半残 node_modules 会让首次使用者误判工程损坏。

**处理方式**：scaffold.py:198 结尾提示改为裸 `pnpm install`，并在同句写明「勿加 --ignore-workspace」的理由；新增 `test_docs_paths::test_no_instruction_to_add_ignore_workspace`，在用户可见文案面（scripts/*.py、skills/*.md、README / SKILL.md / RSI.md / 建模手册、templates/ 文本文件）**整文件**匹配 `pnpm install[\s#]+--ignore-workspace` 的命令形态（允许「勿加」式警示散文）。回退修复后该测试点名 `scaffold.py:198` 为红。评审补漏：`templates/video-skeleton/skeleton.toml:13-14` 注释仍写「每集必须 `pnpm install --ignore-workspace` 独立可渲染」——命令被换行断成两行，逐行 grep 与初版逐行测试均漏检；注释已改为裸 install 口径，测试改为跨行匹配并纳入 templates/（修正前该测试点名 `skeleton.toml:13` 为红）。

**后续防范**：命令提示文案与机制命令闭环同源漂移——改命令形态时全仓检索旧 flag，且须跨行检索（注释 / 散文会把命令断行）。

**同类问题影响**：README quickstart、06 / 09 规格与 pipeline.py 机制本体已为裸 install 口径。同一 flag 的配置文件形态——frozen `video/.npmrc` 的 `ignore-workspace=true`——经探针确认为死配置：pnpm 11.25.0 / 12.2.1 下 `pnpm config get ignore-workspace` 恒为 undefined，同文件的 `registry` 照常生效（pnpm ≥11 只从 .npmrc 读认证 / registry 类配置），而它的注释还陈述已被推翻的隔离机制。处理：模板 `.npmrc` 改为只含说明（隔离由 pnpm-workspace.yaml 自锚承担）；已发布的 14 集登记 `[[generation]] npmrc-inert-key`（旧文件指纹 `b632c275ddae`）合法停在旧代，下次重渲时同步，negentropy 侧零改动；RSI-005 测试追加「模板 .npmrc 不得写 ignore-workspace」（旧模板为红）。核验真树骨架门时顺带清掉两处既有未登记漂移：jev 集整组停在 bilingual-i18n 旧代（6 文件指纹与 legacy 逐一相同）但漏入花名册，补入 roster；agent-skills 集 Main.tsx 归一化后与旧代仅差一个空行（regioned 指纹空行陷阱），按逃逸口登记带指纹的 `[[drift]]`。`TO_VIDEO_WORKSPACE=<negentropy-influence> verify_skeleton.py --strict` 由未登记 7 处转为 0 处。

## RSI-006 覆盖门 WARN 的修复指引指向不存在的 scripts/archify_types.py

**表因**：`check_archify_coverage.py` 对「sidecar 缺 type 字段」的 WARN 文案给出修复指引「用 scripts/archify_types.py 回填」，但 skill 仓 `pipeline/scripts/` 下并无该脚本（2026-09-24 实测）。录制器对 lifecycle / 无框 architecture 的指纹嗅探存在已知盲区（14/67 丢型先例），丢型后唯一的人工回填通道是个指向幽灵脚本的提示。jev-decision-model-video 实测 5/13 图丢型，手工改 sidecar JSON 的 type 字段后图型由「untyped 计 1 种」恢复为 5 种。

**根因**：回填脚本从未落地（或曾以 ad-hoc 形态存在过、未随门文案一起入库）；门文案与工具面漂移。

**定性**：低危高摩擦——数据面可手改，但指引失灵会让使用者先在错误路径上找工具。

**处理方式**：方案比选取后者（最小干预）——不新增脚本：录制器已有 `--type` 参数、`record_archify_all.prior_type` 重录时会保住 sidecar 既有 type，缺的只是「丢型后怎么补」的真实指路。覆盖门 WARN、覆盖门注释、archify_manifest 注释三处改为如实指向「在 video/public/archify/<slug>.json 顶层写回 type」；新增 `test_docs_paths::test_script_references_resolve`，用户可见文案面（同 RSI-005 受检面）点名的任何 `scripts/*.py` 必须真实存在。回退修复后该测试点名三处幽灵引用为红。评审补漏两处：① 初版正则以 `(?<![\w/])` 排除了 `$T/pipeline/scripts/x.py` 这一主流写法，scripts/*.py 的 68 处点名只查到 9 处，放宽为 `(?<!\w)` 并扩到文档与模板后受检面为 85 个文件 239 处、全部存在；② 初版 WARN 写「重录时自动保留」不准——只有 `record_archify_all.py` 经 `prior_type` 透传，单图 `record_archify.py` 不带 `--type` 重录会重新嗅探并覆盖（`record_archify.py` 的 `a.type or _sniff_diagram_type(src)`），WARN 与覆盖门注释已如实区分两条路径。

**后续防范**：门文案里凡指名脚本的，加一条「脚本存在性」测试断言（抽取文案中的 scripts/*.py 名单对照文件面）。

**同类问题影响**：与 RSI-005 同型——文案与机制面缺乏一致性执法。

## RSI-007 画面文字逐字复述口播，与烧录字幕叠成上下两层相同文字

**表因**：jev-decision-model-video 成片中，11 句口播在画面里另有一张逐字相同的文字卡（P6 收尾金句卡「当每一次判断都便宜到可以随手来一次——」、P6 用法清单四条、P1「打分不是每个选项各算各的」判词等），底部 frozen Subtitle 又逐句烧录同一句——观众看到上下两层同一句话。用户审片时指为严重问题。

**复现**：对 jev-decision-model-video 修复前的场景代码跑 `check_script.py --project <集> --check-scenes`（本修复后的版本）→ `FAIL 11`，逐条点名文件行号与句 id。评审发现初版门在合入后的 jev 集（negentropy#1172）上报 0 是**假绿**：多行 JSX 文本全漏，残留 9 处（如 `P0Cost.tsx:76`「每个 Agent 系统里，都塞满了各种小判断」serif 33px 上屏）。修订版门在 negentropy 全部 14 集上的存量（初版 → 修订版）：self-improving 10→26、explained 8→9、experience-era 1→8、jev 0→9、agent-skills 5→7、concurrency 6→6、memory 5→6、multiagent 4→4、planning 2→2、context-layer 2→2、openviking 1→2、dream-rsi 0→1、self-evolving 0→3、horizon 0→0，合计 44→85（其中 2 处来自跨行续写拼接：self-evolving `P0Hook.tsx:338` 以 `<br />` 断行的 88px 标题、`P4Eval.tsx:297` 清单块）；抽检 16 条新增命中全部为上屏文字。

**根因**：画面文字的职责没有写进任何规格——05 分镜只要求「写清画面主体与角标」，06 渲染红线查的是位置（字幕带避让）不是内容；自动 QA（qa_frames --check）只看黑帧、冻帧与安全区侵入，对文字是否与字幕重复完全失明。场景代理在「金句卡 / 清单 / 判词」这类装置上最自然的写法就是把口播原句放上屏。

**定性**：内容质量缺陷，但属 Skill 缺陷类（规格缺条款 + 门缺判据，14 集中 13 集复发）——走 RSI。

**处理方式**：`check_script.py` 新增 `check_caption_duplication`，**缺省执法**（不依赖 `--check-scenes`：`pipeline.py check`、`all` 与 ⑨ 重渲前的 check 步骤都会跑到，忘带 flag = 检查面静默缩小，同 ISSUE-168），zh / en 完整门各自对本语言字幕面执法（en 版 `<L en>` 与英文字幕同样会叠层），`--pre-tts` 不跑。提取面：场景代码中的引号 / 反引号字符串、同行 JSX 标签间文本、整行裸文本，以及相邻裸文本行（同一 JSX 文本节点的续写，`<br />` 不断段）的拼接段，归一化（NFKC 后只留字母数字与汉字）后与口播句（narration.json 的 text，即字幕面）比对——整句相等（≥4 字）、≥10 字且覆盖该句 ≥70% 的子串、或 ≥10 字的整句落在字面量内，任一即 FAIL 并点名行号与句 id。覆盖率判据而非裸子串：截去句首「所以」的复述照样拦，「选项之间 ⇄ 互相牵动」这类关键词锚点不误伤。Pn 前缀场景文件只比本幕句子（别幕回扣同句时字幕不在屏上），注释行跳过；章节标题卡、同幕跨镜回扣等刻意复述，在命中行或上一行注 `caption-dup-ok: <理由>` 逐处豁免（理由必填），降为 WARN 留痕——逃逸口必须存在且必须被记录（同 [[drift]] 立场）。05 分镜规格加一条「画面文字不复述口播」指向该门，`--check-scenes` 帮助文案同步改正（此前写「WARN-only」，实际含 ISSUE-190 与本门两类 FAIL）。回归测试 5 组（失败形态含缺省执法 / 七种字面量写法参数化 / 锚点·注释·跨幕回扣不误伤 / 豁免须写理由 / en 字幕面）。

**后续防范**：画面文字只放字幕给不了的信息（关键词 / 数字 / 标签 / 结构）；金句卡若必须存在，与口播措辞拉开（口播完整句、画面关键词）。评审回归（2026-09-24）三条经验：① 源码扫描门的红绿对照必须覆盖该源码的**主流写法**（这里是 JSX 文本独占一行），只拿单行构造样例验证，「修复后 0」会是假绿；② 正则提取成对定界符时不能设长度下限，否则短匹配失败后错位配对会吞掉后文（`at('p0-01')` 后的正文）；③ FAIL 级判据须贴合缺陷的物理条件（同屏）：别幕回扣与注释都不构成两层重复，误报会逼人绕门。

**同类问题影响**：negentropy 13 集有存量（合计 85 处，见复现），均为已发布成片，本 PR 不改其内容。本门缺省执法后，这些集在 `pipeline.py check` / `all` 上会红，重渲前必须先修（或逐处以 `caption-dup-ok` 说明）。jev 集（发现集）的 9 处已于 [negentropy#1173](https://github.com/ThreeFish-AI/negentropy/pull/1173) 处理（2026-09-24）：改为关键词锚点、复述门 FAIL 0、重渲并交付 v3（内容侧记录见 negentropy ISSUE-199）；余 12 集 76 处待各自重渲前处理。
