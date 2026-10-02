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

**处理方式**：RSI 增「建模经验分支」——新增有界经验库 [pipeline/MODELING-PLAYBOOK.md](../../references/MODELING-PLAYBOOK.md)（条目化、权重生命周期、候选区攒批策展）+ 规则唯一实现 `pipeline/scripts/check_playbook.py`（3000 字硬上限、2700 触发压缩、压至 2250，滞回）+ RSI.md 策展协议与六级压缩阶梯 + 不变量第 15 条 + 02/05/06/08/09 消费指针 + test_modeling_playbook 执法；设计依据见 [docs/research/modeling-experience-distillation.md](../research/modeling-experience-distillation.md)。PR：[#12](https://github.com/ThreeFish-AI/to-video/pull/12)（commit `53ea0d9` 机制与测试、`56163ae` 研究文档与回路图）。

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

## RSI-008 Skill 不合 Agent Skills 规范：frontmatter 被官方校验器拒收，路由壳缺渐进披露与条件加载，速查门列漂移

**表因**：以 Agent Skills 规范（agentskills.io 规范、官方参考校验器 skills-ref、Anthropic skill authoring best practices）审计本 Skill，发现五类差距：① `skills-ref validate` 失败，报 `Found ugly disallowed JSONesque flow mapping`，位置在 SKILL.md:5 的 `metadata: {…}`；② `allowed-tools` 用逗号分隔（规范为空格分隔），缺 `compatibility`，description 里塞了 1080p30、`--root`、vN 等实现细节，缺英文触发词和负向边界；③ SKILL.md 九阶段速查的「通过门」列是 stages.toml `gate` 的手抄件，9 行里 6 行已漂移（③⑤⑥⑧⑨ 截短或改写，⑦ 内容不同）；④ 快速通道第 5 步教 `npx tsc --noEmit`，与 06 规格「工具一律 `./node_modules/.bin/` 直调」矛盾；⑤ 路由壳没有任务分流，也没说明何时读哪份文件（VOICE-CLONING 等手册要两跳才能到），env 表的 SSOT 放在每次激活都全量加载的 SKILL.md 里，超过 100 行的 5 份规格没有目录，仓内没有评测资产，目录也不合规范的 `scripts/ references/ assets/` 惯例。

**复现**：`git archive <旧提交> | tar -x -C /tmp/x/to-video` 后执行 `uvx --from "git+https://github.com/agentskills/agentskills#subdirectory=skills-ref" skills-ref validate /tmp/x/to-video`，退出码 1。门列逐行对比（SKILL.md 抄件 → stages.toml `gate`）：③ `build_narration.py 通过` → 缺「（narration.json 是派生物）」；⑤ `beat 覆盖率无缺句` → 缺「（--check-scenes 分镜↔代码互比）」；⑥ 缺「排期」；⑦ `七条渲染红线 + 运动层铁律` ↔ `tsc --noEmit 零错误 + 七条渲染红线`；⑧ 缺 `qa --check`，「含尾幕」写成「尾幕」；⑨ 缺「pipeline.toml 的」。`grep -n "npx tsc" SKILL.md` 命中第 38 行。新门在旧 SKILL.md 上会变红：`test_skill_spec` 8 项 ERROR（第 5 行 flow mapping），`test_router_gates_match_stages` 点名 6 行，`test_no_npx_for_remotion_tools` 点名 1 处。

**根因**：SKILL.md 是从 negentropy 的 `.agent` 路由壳演化来的，写的时候对照的是仓内纪律（路由壳只给指针、速查表恰 9 行），没有对照 Agent Skills 规范。frontmatter 从没被任何校验器解析过，Claude Code 能宽容解析 flow style 和逗号分隔，缺陷因此一直不可见。门列只有「链接覆盖 9 篇规格」这一条执法，文本本身无人校验，于是逐步漂移。

**定性**：非阻断改进，含两处缺陷：门列漂移、npx 命令矛盾。在其他宿主上，frontmatter 不合规会直接导致上传失败或触发失效。

**方案比选**：A 只修 frontmatter、门列与 npx，不动布局；B 全量迁移到规范布局，并保留 `pipeline/scripts` ABI 软链；C 迁移但不留软链。C 直接排除：会打断全部已部署的 frozen 包装器，而这些包装器无法从本仓更新。规范本身允许任意目录，A 与 B 都合规；B 是用户在方案评审时的显式选择（2026-09-24，用户在会话中选「全量迁移 scripts/references/assets」），代价是历史相对链接与外链的迁移成本（见「同类问题影响」）。

**处理方式**：[PR #16](https://github.com/ThreeFish-AI/to-video/pull/16)，分三次提交（另有一次按核验反馈补强）：[0b82a71](https://github.com/ThreeFish-AI/to-video/commit/0b82a71) 目录迁移、[14c5b22](https://github.com/ThreeFish-AI/to-video/commit/14c5b22) SKILL.md 与文档重构及执法测试、[43427f1](https://github.com/ThreeFish-AI/to-video/commit/43427f1) 台账与 CHANGELOG、[71b06f4](https://github.com/ThreeFish-AI/to-video/commit/71b06f4) 核验反馈修正。① 用 `git mv` 迁到规范布局，`pipeline/scripts → ../scripts` 保留为软链。这条软链是已部署 frozen 薄包装的定位路径（ABI），5 份包装器的解析函数与全部 frozen 文件字节不变。`pipeline/README.md` 改为迁移桩，全仓 Markdown 链接按旧位置重算。② frontmatter 只保留规范六字段：metadata 改块式、allowed-tools 改空格分隔、新增 compatibility，description 改写为「做什么 + Use when + 不用于」。SKILL.md 重构为：任务分流 → 工作流（显式修复重跑循环）→ 速查（门列逐字等于 stages.toml，⑦ 的 gate 补上「运动层铁律」）→ 不变量（新增包装器 ABI）→ 运行时陷阱 → 按需加载。env 表迁入 PIPELINE.md 并补 `INDEXTTS_SERVER`，5 份长规格各加一行目录，新建 docs/.agents/knowledge-map.md。③ 新增 evals/（3 个输出评测、20 条触发评测，含近邻负例）；新增 `tests/test_skill_spec.py`（只用标准库，是比 strictyaml 更严的 frontmatter 子集解析器，并覆盖字段约束、正文预算、加载期标记、目录行、evals 结构、全仓链接网）；新增门列同源、npx、旧路径三条回归门，以及 ABI 软链两条执法。顺带修正两处迁移前就失实的文案：`prepare_ref.py --out` 的帮助文本和 tts 指纹不符提示，都曾指向不存在的 `pipeline/voices/`，现改为 `$V`。G3 的 evals 新旧对拍推迟到合并后执行：个人级 `~/.claude/skills/to-video` 指向另一份 clone，会遮蔽 worktree 里的同名 skill，合并前测到的只会是旧 description（见 evals/README.md）。

**后续防范**：改 frontmatter 后必须过 test_skill_spec，必要时一次性跑官方 skills-ref。不得为 Claude Code 专有能力引入规范外字段，否则牺牲可移植性，要引入须显式决策。SKILL.md 里任何与 stages.toml、PIPELINE.md 重复的文本，都必须挂逐字同源的执法，否则只留指针。不得删除 `pipeline/scripts` 软链，也不得修改包装器解析函数（该句已被 RSI-009 推翻：兼容面整体移除，解析函数探测路径随之改指 `scripts/`）。改 description 前后，按 evals/README 做触发评测对拍。评审回归（2026-09-25）：旧路径门曾漏掉两类形态——脚本注释里省略 `pipeline/` 前缀的 `templates/<子目录>`，以及 mermaid 图源首行的 `%% source:`（该目录不在受检面内）。现已把两者纳入执法，并修正全部 8 处失效指针。其中 3 处无法泛化检测，只能人工复核：跨目录的相对指针 `../README.md`、不带子目录的 `templates/`、仍作为迁移桩存在的 `pipeline/README.md`。今后搬迁目录时，受检面须覆盖所有「指回文档」的非 Markdown 文件。二次评审（2026-09-25）：工作流 ⑧ 的裸 `pipeline.py … qa`（旧 SKILL.md 就有）必在 qa_frames 处 parser.error（缺 `<video>` 与选择器），修复循环到不了零 FAIL，已改为 `qa --video out/draft.mp4 --last-n 6 --check`，新增 `test_router_qa_commands_pass_both_parsers`：让 SKILL.md 的 qa 实参真跑过 pipeline.py 与 qa_frames.py 两层 argparse。教训：复制即跑的命令要用真解析器判定，文本启发式（只查带不带 `--video`）会放过「有视频、缺选择器」的形态。模板 `README.md.tmpl` 第一条 `qa --video out/draft.mp4 --check` 正是这个形态、同样必败，登记为跟进项：它的现有门 `test_template_readme_qa_commands_are_runnable` 只查 `--video`，未拦住。

**同类问题影响**：已发布分集和工作区经软链零改动继续可用。它们 README 里的 `$T/pipeline/scripts/…` 命令仍然有效。已部署分集 README 与 pipeline.toml 里的 GitHub blob 外链，按 negentropy 14 集实测：`pipeline/README.md` 27 处会落到迁移桩；另有 15 处在合并后 404，分别是 `pipeline/VOICE-CLONING.md` 6 处、`pipeline/templates/video-skeleton/skeleton.toml` 8 处、`pipeline/skills/06-remotion-implementation.md` 1 处。这 15 处属于内容侧的 seeded 文件（可改），RSI 回路对 `$W` 只读，故登记为 negentropy 侧跟进项：批量把外链改到 `references/…` 与 `assets/video-skeleton/skeleton.toml`。本仓不加重定向桩，避免在旧位置造出第二份文件。frozen 文件注释里的旧路径（如 SceneFade 的 `pipeline/skills/06…`）有意保留，按迁移桩里的映射表换算。复制式安装（`npx skills add --copy`）如果丢失软链，所有分集与工作区包装器都会失效（模板沿用同一解析函数，新建的也不例外），README 安装节已注明。

## RSI-009 按 2.0.0 全新维护：移除全部历史兼容面（软链 ABI / 旧哨兵 / 旧 env 与缓存回退 / skeleton 历史登记 / 阶段编号错位）

**表因**：RSI-008 迁移到 Agent Skills 规范布局时，为已部署的 negentropy14 集薄包装保留了 `pipeline/scripts` 软链 ABI、旧哨兵 `.influence-root`、旧 env `NE_TTS_STORE` 与旧缓存目录回退、skeleton.toml 内 33 条 `[[drift]]` 与 2 组 `[[generation]]` 历史登记，以及「⑥↔07、⑦↔06 编号错位」（当初因入链 ≥5 处、改名代价大而保留）。这些兼容物使 skill 仓持续背着历史包袱：frozen 文件注释里的旧路径不能改、迁移桩与不变量 16 须永久维护、skeleton.toml 一半篇幅是别仓集名。

**复现**：`grep -rn 'influence-root\|NE_TTS_STORE\|LEGACY_STORE' --exclude-dir=.git .` 命中 scripts/tests/assets/references 共 10 个文件；`awk '/^\[\[drift\]\]/{c++} END{print c}' assets/video-skeleton/skeleton.toml` = 33；`ls pipeline/` = 迁移桩 README + 软链。negentropy 侧实测依赖面：14 集 61 个包装器探测 `pipeline/scripts`、pre-commit `series-consistency-check` 走工作区包装器、tts-store 65M/1815 句在旧目录。

**根因**：RSI-008 的方案比选以「已部署包装器无法更新」为前提排除了「迁移但不留软链」。该前提是历史包袱的根源：兼容义务一旦背上就单调增长（软链→旧哨兵→旧 env→登记表→不可改的 frozen 注释），每次机制演进都要先问历史集答不答应。

**定性**：破坏性改进（semver major，2.0.0）。negentropy 侧破坏面已知且用户决策（2026-09-25）由其仓自行适配，不在本仓留任何迁移工程。

**方案比选**：A 只删 pipeline/ 目录——不可行，包装器解析函数探测 `<skill>/pipeline/scripts/pipeline.py`，只删目录连新 scaffold 都找不到 skill；B 保留软链等兼容面、仅停止增长——与用户决策相悖，且兼容物维护成本（frozen 注释冻结、迁移桩、不变量执法）持续存在；C **兼容面整体移除 + 包装器探测改指 `scripts/`（采纳）**——推翻 RSI-008 对「迁移但不留软链」的否决，推翻依据：其前提「已部署包装器无法更新」被用户决策废除（negentropy 自行适配）。negentropy 侧适配三步（本仓不代做）：61 个包装器探测路径 `pipeline" / "scripts` → `scripts`（与模板字节同步）、补 `.to-video-root` 哨兵、`mv` tts-store 目录。

**处理方式**：PR #16 内分两批提交。①兼容面移除：`git rm -r pipeline/`；5 份包装器探测路径与 docstring 改指 `scripts/`（test_wrapper_resolver 的 fake_skill 布局与 argv 锚同步，删 2 条 ABI 软链执法）；`WORKSPACE_MARKERS` 收敛为 `.to-video-root`（scaffold 去旧哨兵探测；test_paths/test_init_workspace/test_check_series 删旧哨兵用例）；tts.py 删 `NE_TTS_STORE` 兼容读与 `LEGACY_STORE` 回退（store_root 解析序收敛为 env → 默认目录；test_tts_store 删 2 条兼容用例）；test_docs_paths 删 `$I/$R` 旧锚门与 `COMMAND_SPAN_RE` 的 I/R 记号、`_LEGACY_PATH_RE` 收紧为 `pipeline/` 前缀整体入拦；skeleton.toml 清零 drift/generation 登记、删 `baselineOf` 与 `.npmrc` 占位（verify_skeleton 的 baseline 机制保留，面向将来多模板；test_skeleton 放宽分代表非空前提、删 baselineOf 点名正控）。②编号对齐与资产清理：06-tts-voice / 07-remotion-implementation 文件互换与全量引用同步、错位警示与 test_stages 错位执法反转为对齐执法；influence--* 资产更名 pipeline-layers；frozen 文件陈旧注释修正；SKILL.md version 2.0.0 与 CHANGELOG 破坏性条目。

**后续防范**：兼容义务以「显式决策 + 台账 + 版本号」为界——新增任何兼容读/回退/别名前，先问「删除它的 major 版本在哪」，无删除计划就不许加。skeleton 登记表只登记「当前合法偏离」，别仓集名不得进本仓模板。skill 仓不携带任何指向具体内容工作区的名字（系列 id、集 slug、仓名）。评审回归（2026-09-25）：文件号互换只改了带路径的链接，漏了三类写法——裸编号散文（RSI.md G2「不重述 06 机制与红线」、test_docs_paths 注释「06 规格」）、带新前缀但编号未换的 `references/05→06`、研究文档里的 `skills/06` 简写（4 处）；另有同一版本内 RSI-008 的 CHANGELOG 条目仍写「软链禁删 / 零改动可用 / 错位不变 / 不变量 16」，与 Breaking 节矛盾。现已全部改正。研究文档已纳入 `test_no_legacy_layout_paths` 受检面（`skills/NN` 简写入拦）。裸编号散文无法泛化检测（会与时间、序号误撞），今后改编号须对旧编号全仓 grep，并按上下文语义逐处判定。未发版的条目在发版前要改写到终态，被同版推翻的子句不得留在发布说明里。二次评审（2026-09-25）：包装器探测标记改为 `<c>/scripts/pipeline.py` 后与工作区根布局同形（`--init-workspace` 生成 `$W/scripts/pipeline.py`），`TO_VIDEO_HOME` 误指工作区时工作区包装器把自己认成 skill 入口、无界自递归（沙箱 3 秒串起 42 个子进程），分集包装器则去跑不存在的 `$W/scripts/tts.py`；旧标记 `pipeline/scripts` 不与任何工作区布局相撞，故为本次迁移引入。五份包装器命中判据加 `SKILL.md` 哨兵（与 `paths.SKILL_MARKER` 同口径），`test_home_pointing_at_workspace_falls_through` 五形态参数化执法（进程组超时整组 kill，旧实现下 5 条全红），A1 修复口径同步；negentropy 侧 ISSUE-200 的 A1 须同步此条件。教训：改探测标记时，须对照「可能被误指的目录」（工作区、分集、skill 旧版）的真实布局逐一核对是否同形，标记要取对方结构上不可能有的文件。三次评审（2026-09-25）：09 规格的字体重启触发器指针由 `pipeline/README「字体可复现性」`机械改写为 `references/PIPELINE.md「字体可复现性」`，但该事实条一直在 07 规格（main 上的旧指针即已悬空），同批 Subtitle.tsx 的同一指针却已改对；已改为指向 07 的可跳转链接，新增 `test_pipeline_section_refs_resolve`：`PIPELINE.md …「节名」` 形态的指针须命中 PIPELINE.md 真实标题（旧文案下红、点名 09:33）。教训：搬迁时改写的是「文件名」，节名是否仍在目标文件要单独核对；链接可达门只验文件、不验节名。

**同类问题影响**：本仓 CHANGELOG/issue 台账中的历史叙述按记录保留，未随兼容面删除。破坏面与未兼容旧功能清单已同步登记到 negentropy 侧（[ISSUE-200](https://github.com/ThreeFish-AI/negentropy/pull/1174)，PR [#1174](https://github.com/ThreeFish-AI/negentropy/pull/1174)，2026-09-25），待其适配后逐项验证关闭：

**A. negentropy（apps/negentropy-influence，14 集）破坏面——按 2.0.0 CHANGELOG 自适配步骤完成后逐项验证**

| # | 破坏面 | 修复 | 验证 |
|---|---|---|---|
| A1 | 61 个薄包装器（14×tts/build_narration/qa_frames + 17 个 archify 类 + 2 工作区包装器）探测 `pipeline/scripts`，全部「找不到 to-video skill」 | `_skill_scripts` 与 2.0.0 模板同步（探测 `pipeline" / "scripts` → `scripts`，并加 `SKILL.md` 哨兵条件）；分集 frozen 包装器按 2.0.0 模板整文件覆盖（docstring 同批改过，只改探测行字节不等） | 任一分集 `scripts/tts.py --help` 可跑；`TO_VIDEO_HOME=<新 skill>` 下 `verify_skeleton.py` 对模板零漂移 |
| A2 | pre-commit `series-consistency-check` 走工作区包装器，触及 influence 的提交被拦 | 同 A1（工作区 2 份包装器） | 暂存一处 influence 内改动，钩子 Passed 而非报「找不到 skill」 |
| A3 | 旧哨兵 `.influence-root` 不再识别，依赖 WORKSPACE 锚的脚本大声退出 | 工作区根补空 `.to-video-root` | 工作区内任意目录直跑 `check_series.py`，rc=0 |
| A4 | tts-store 旧目录（实测 65M / 1815 句）回退删除，缓存全 miss（重渲一集重合成 2.5–3.5h） | `mkdir -p ~/Library/Application\ Support/to-video` 后 `mv ~/Library/Application\ Support/negentropy-influence/tts-store ~/Library/Application\ Support/to-video/tts-store`（新目录已存在时改 `rsync -a` 合并，勿 mv 嵌套） | 任一集 `pipeline.py tts`（不改稿）零重合成、全部命中缓存 |
| A5 | skeleton 登记清零 + frozen 模板字节变更（包装器探测行、remotion.config.ts 与 frozen 组件注释、.npmrc 删除），旧集 `verify_skeleton --strict` 大量 STALE/DRIFT 红 | 逐集整组同步模板（拷齐再 `tsc --noEmit`）；仍成立的偏离按 [RSI-010](#rsi-010-骨架合法偏离登记面在-skill-侧工作区无登记入口) 加 `skeleton.` 前缀登记进 `$W/to-video.toml` | 同步过的集 `--strict` rc=0 |
| A6 | 已发布集 README/pipeline.toml 的 GitHub blob 外链 42 处（15 处本已 404 + 27 处指向已删迁移桩） | 批量改指 `references/…` 与 `assets/video-skeleton/skeleton.toml` | 抽检 5 处链接可达 |

**B. 未兼容的旧版功能（2.0.0 有意不支持；用于后续「未回归」核对）**：`.influence-root` 哨兵识别；`NE_TTS_STORE` 旧 env 名与旧默认目录回退；`$T/pipeline/scripts/…` 命令路径与 `pipeline/README.md` 迁移桩；`baselineOf` 模板缺省值（机制保留、模板不设）；**skill 侧 skeleton 登记**——旧版在 skill 侧登记内容仓集名的 drift/generation；2.0.0 起 skill 侧登记键被 verify_skeleton 拒收，登记面迁至工作区（见 RSI-010）；模板 `.npmrc` 占位文件。

**C. 本机其他依赖**：`to-video-e2e/mini-video` 测试工作区包装器失效（重建即可）；真树回归语料（`TO_VIDEO_TEST_WORKSPACE` 指 negentropy 树）待 A1/A3 完成后恢复——扫描类门（`--check-scenes` 等）的红绿对拍在此之前不可用，不得以单行构造样例替代（见 RSI-007 教训）。

**D. 跟进项（非破坏，已在 RSI-008 评审回归段登记，不重复维护）**：模板 `README.md.tmpl` 首条 `qa --video out/draft.mp4 --check` 缺选择器、照抄必败。

## RSI-010 骨架合法偏离登记面在 skill 侧，工作区无登记入口

**表因**：RSI-009 清空 skeleton.toml 的 33 条 `[[drift]]` 与 2 组 `[[generation]]` 后，2.0.0 CHANGELOG 写「旧内容工作区的既有漂移须重新登记到各自工作区」，但 `verify_skeleton.py` 只读 skill 侧 `$T/assets/video-skeleton/skeleton.toml`，工作区无任何登记入口；同批删掉的登记格式说明（指纹口径、「缺失」哨兵、分代语义）仍被 `pipeline.py` 英文渲染预检报错与 `verify_skeleton.py` docstring 三处指向。

**复现**：`grep -n 'skel.get("drift"\|skel.get("generation"' scripts/verify_skeleton.py` 命中两处，均取自 `SKELETON_TOML`；skeleton.toml 内 `grep -c '分代'` = 0，而 `pipeline.py:643` 报错文案指向「skeleton.toml 分代说明」。

**根因**：登记表在机制与内容同址时代（skill 住在 negentropy 工作区内）放进了模板；抽取为独立 skill 后，登记条目指向的具体集属于**内容**，却仍只能写进**机制**侧——任何用户停用/魔改 frozen 文件都得改已安装的 `$T`，违反 RSI「制片期 `$T` 只读」，且下次 `git pull` 冲突。RSI-009 台账 B 节已把「工作区侧登记」列为另立条目的长期解，CHANGELOG 却按已实现来写。

**定性**：机制缺陷（缺登记面）+ 文档指针悬空；随 2.0.0 同版修复，免得登记位置日后再迁一次、又造成一次破坏性变更。

**方案比选**：A **登记面迁至工作区 `to-video.toml` 的 `[skeleton]`（采纳）**——与该文件既有定位「内容策略随内容走，skill 不携带具体系列身份」同构（同 check_series 的系列 id 集）；键名不变、表名加前缀即可原样搬运旧条目。B 只改 CHANGELOG 文案——零代码，但「改偏离须改 `$T`」的缺口延到下个版本，届时迁移又是一次 breaking。A 的子选择：与 skill 侧**合并**读取被否决（两处登记 = split-brain，且合法条目必含集名、skill 侧不存在正当用途），改为 skill 侧出现 `drift`/`generation` 键即大声退出；`baselineOf` 是模板级声明，维持 skill 侧（RSI-009 已定，面向将来多模板）。

**处理方式**：`verify_skeleton.py` 新增 `load_registry()`（skill 侧登记键 → `sys.exit` 点名迁移方式；读 `$W/to-video.toml` 的 `skeleton` 表，缺失 = 无登记）；已登记偏离报告改为全部列出，指向 series.json 未知集的条目标「陈旧登记」旁注（登记本地化后「他工作区登记是噪音」的过滤理由不再成立）。skeleton.toml 恢复「合法偏离登记」「骨架分代」两节格式说明（不含条目），三处既有指针随之重新生效；工作区模板 `to-video.toml.tmpl` 加 `[skeleton]` 注释示例，scaffold init 提示同步；07 / PIPELINE.md / CHANGELOG（negentropy 适配增第 ④ 步）指针同步。test_skeleton 的 `register_drift` / `inject_generation` 改写工作区 to-video.toml（既有 6 条分代正控与 2 条 drift 正控随之覆盖新路径），新增 skill 侧登记被拒、模板零登记、陈旧登记旁注三条用例；三条真树用例改读工作区登记。

**后续防范**：skill 仓只放机制；任何「指向具体集/系列」的数据（登记、豁免、花名册）一律住工作区，新增此类配置前先问「它随内容变还是随机制变」。发布说明里的迁移步骤必须能照做——写「须登记到 X」前先确认 X 存在读取入口。删除数据条目时区分「条目」与「格式说明」：前者可清零，后者是机制文档，删了即留悬空指针。评审回归（2026-09-25）：三处漏改——① DRIFT-CHANGED 的处置文案仍写「请复核后更新 skeleton.toml」，照做会被 `load_registry()` 拒收，已改指 `$W/to-video.toml` 的 `[[skeleton.drift]]`，并在 `test_registered_drift_is_pinned_to_its_fingerprint` 断言该行指向工作区；② CHANGELOG 第 ① 步称包装器同步后「verify_skeleton 随之对齐」不成立——同版 7 个 frozen TS/TSX 的纯注释修正改变了 md5，英文渲染预检（直比字节、不查登记）会拦下全部既有集，已补为第 ② 步（当代集整组拷齐、旧代集只拷组外文件），分集包装器亦须整文件覆盖而非只改探测行；③ test_skeleton 分代节注释仍写「登记落在镜像 skeleton.toml」。教训：迁移登记面后，须全仓 grep 旧落点名（含报错文案与测试注释）；迁移步骤里「随之对齐」之类的结论要用字节比对实测，不凭推断。二次评审（2026-09-25）：① skill 侧拒收守卫只查顶层 `drift` / `generation` 键，而 skeleton.toml 格式说明里的示例本身就是 `[[skeleton.drift]]`——原样贴进 skill 侧时解析为 `skeleton.drift`，守卫不触发、登记被静默忽略（沙箱实测：带正确指纹仍 `--strict` rc=1 且无指路）。已把拒收键扩为 `LEAK_KEYS`（旧表名 + `skeleton`），`test_skill_side_registry_is_refused` 参数化覆盖两种写法（旧守卫下新用例红）；② skeleton.toml 与 check_script、verify_skeleton、test_skeleton 注释里仍有 9 处旧表名 `[[drift]]`，已统一为 `[[skeleton.drift]]`（测试里刻意注入的旧写法除外）。教训：拒收守卫要按「格式说明里示例的原样形态」建反例，而不只按旧形态建。三次评审（2026-09-25）：① 登记迁到工作区后，drift「必钉指纹」等策略断言只剩真树用例（集成模式、单一工作区）在跑，普通工作区写一条缺 fingerprint 的登记即被 `exempt()` 无条件放行、该文件永久免检。已新增 `registry_problems()` 载入期校验（drift 四字段必填、指纹 12 位 hex 或「缺失」、路径在受门档位、同集同文件不重复；generation 的 id / reason / 花名册 / legacy 非空，legacy 在受门档位且 ≠ 当前模板指纹），非法即大声退出，`exempt()` 删去「未钉即放行」分支；两条真树用例改为委托该函数（规则单一实现），另加离线正反控 10 条与端到端 1 条（旧实现下红）。用 origin/main 旧 skeleton.toml 模拟第 ⑤ 步搬运：33 条 drift 与 bilingual-i18n 全过，仅 `npmrc-inert-key`（`.npmrc` 已退出受门）被拒，CHANGELOG 第 ⑤ 步已注明勿搬；② 拒收文案对已带 `skeleton.` 前缀的形态仍教「加前缀」，照做得 `[[skeleton.skeleton.drift]]`、登记被静默忽略，已按泄漏写法分支指路；③ CHANGELOG 第 ④ 步与 RSI-009 A4 的 `mv` 缺 `mkdir -p`（1.x 在旧目录存在时从不建新目录，本机实测父目录不存在，mv 必报 No such file or directory），且丢了 1.0.0「目标已存在改 rsync 合并、勿 mv 嵌套」的提醒，已补。教训：策略从「本仓测试执法」迁到「用户数据」时，执法点须同步迁到运行期；迁移命令要在目标机器的真实初态上走一遍，不能只在干净环境里推演。

**同类问题影响**：negentropy 侧 A5 由「整组同步或接受红」扩为可登记（CHANGELOG 第 ⑤ 步）；旧版在 skill 侧登记的写法在 2.0.0 被拒收（RSI-009 B 节同步改写）。

## RSI-011 默认配音「朗读感」：合成结构而非情绪强度

**表因**：用户连续两轮否决调优结果（2026-09-25）——α≤1 的语调迁移「过于保守」，α>1 外推「情绪够但仍是朗读、且像别人」。按句内起伏幅度调参无法收敛。

**根因**：朗读感来自**合成结构**，不是情感强度——① 逐句独立合成（跨句零上下文，句尾一律降调收束，无故事弧）；② 全片单一全局情绪（每句同一种劲）；③ 句间隔恒定 0.32s（无戏剧停顿）；④ `tts_text()` 把 `……` 压成 `。`（上游本把 `…` 当独立 token 给拖长停顿，文本层的表现力线索被客户端删掉）。实测证据：pYIN 口径下第一批（被否「保守」）已达博主句内起伏的 104%，用户仍判朗读 ⇒ 句内幅度不是区分维度；换成连续故事段落后，段落合成 + 块情绪 + 表演标点的组合把全段弧线由 −0.35（持续下滑）转正、句尾收束多样性 13.0→15.1、停顿多样性 0.55→0.68，同时音色门（WavLM 独立 SV）0.959/0.926 为全部候选最稳。

**定性**：Skill 缺陷（合成单位与情感粒度的架构限制），非参数问题。

**处理方式**：新增 `story` 档（段落演绎）并为新集默认——同幕连续句按故事块一次合成（上游 front.py 对 ≤118 token 合并单段连续生成），服务端按句界切回逐句 mp3（静音正中丢弃恰好 `sentenceGapSec`、时间轴加回同值 ⇒ 听感＝自然停顿原值；块末垫 0.18s+0.32s 句距＝0.5s 块间停顿）；块情绪由配音台本 `script/narration.cues.toml`（写稿阶段同产，references/03 规约）驱动，无台本自动分块 + 预设向量兜底；`……`→`…` 仅 story 档生效（默认映射不动，存量 2 集含 `……` 的重合成行为不漂移）；块=缓存单位（改一句重录整块）；EN 未验证自动回退逐句；切分失败逐句兜底。验证：真管线复现 #07 定档 take——4 块音频时长逐块一致（12.85/12.38/7.86/11.66s，同 seed）、全指标在噪声内（演绎度三轴、WavLM 0.959/0.939、CER 0.098）；P1 17 句自动分块 0 fallback。

**后续防范**：声音风格类调优先问「合成结构与情感粒度对不对」，再调强度参数；试听素材必须用连续故事段落（零散句子听不出演绎）。切分算法的量尺教训：句界停顿 0.31–0.55s 与句内逗号停顿 0.14–0.42s 区间重叠，不能「取最长 N−1 静音」，按字符占比期望位就近选（DP）。评审回归（2026-09-25）：① 切分失败的逐句兜底在 `async with sem` 内递归、再次获取同一 `Semaphore(1)` ⇒ 首个切分失败块即整集挂死（stub 复现：WARN 后零请求永久阻塞）；已把锁收窄到单次请求、兜底在锁外逐句请求，兜底沿用块情绪并按块成员摘要落盘（旧兜底写单句摘要，复跑永不命中、每次重试整块）；② 块合成路径的 `durationSec` 取服务端 PCM 时长、命中路径取 `mp3_duration`，lameenc 下每句差 +0.06–0.075s ⇒ 无改动复跑即令时间轴漂移（百句约 6s），已统一取 mp3 实测；③ 块路径丢了逐句路径的编码器守卫，服务端无 MP3 编码器时 WAV 字节被静默写成 `.mp3`——clip 现回传 `format`，非 mp3 硬拒不落盘；④ `tts_progress` 聚簇后墙钟与**上一簇**字数配对（逐句模式同受波及）且末簇从不入列，已改为配对下一簇并补末簇，单簇无样本时报不足而非 StatisticsError。6 条回归用例在旧实现下全红（兜底用例为 5s 超时）。教训：新增「同一函数内再次请求」的降级路径时，先查外层持有的锁是否可重入；同一产物的派生量（时长）必须与缓存状态无关，合成路径与命中路径取同一量尺。评审回归二（2026-09-25）：① `plan_blocks` 把块数下界 max(⌈n/3⌉,⌈ΣL/90⌉) 当成定值，「多句块 ≤90 字」装箱约束下恰好 k 块常切不出，整段 run 直接退化逐句——14 集语料对拍 2303 句切出 1207 块、单句块 619（multiagent 134 句 118 个单句），已改为逐层放宽到首个可行块数：块数与暴力最少可行值逐集一致、单句块 619→3，旧算法可行的 run 改写 0；② 台本段超限被自动拆开时，后续子块首句无 cue、静默退回预设向量，已改为子块继承段首 cue（块首句浅拷贝注入，narration items 原件不改）；③ `block_synth_text` 对 `，：、——` 结尾也追加 `。`，拼出 `，。`（上游 `,.` 双标点）并把续接改成句末降调（语料约 10% 的行），已改为保留软停顿标点、仅无标点结尾补 `。`，块后缀 `split=v1→v2` 换键（改动时无 story 存量音频，零重录成本）；④ `--plan` 块口径 ETA 未扣版本库可整块回收的块，已同逐句 `n − store_hits` 口径；⑤ 块路径本地整块命中时不回填版本库，已补齐；⑥ `tts_sample --all-styles` 只按 neutral 解析采样口径，story 档丢了预设 seed，已改为逐档解析（原「预设带 sampling 即拒绝」门随之失效移除）。6 条新增用例在旧实现下全红。教训：「下界即解」只在无约束时成立——带装箱约束的 DP 必须从下界向上找可行解；划分类算法改动先在真实语料上对拍「旧可行解是否零改写」再合入；改变合成文本却不改成员文本的算法变更必须显式换键。评审回归三（2026-09-25）：① 台本 `[say]` 的标注校验只查「say 里还有没有标注」，全等比较又先 strip_marks ⇒ 两处标注删一处、或改读音都能过（多音字读错只能靠听发现），已改为保留标注只去标点再比，标注集合/位置/读音逐个钉死；② 逐句兜底的每个单句请求都带 `tail_pad_sec`，服务端单句路径无条件补垫 ⇒ 兜底块内每句多 0.18s 停顿，已改为仅末句补垫（同块合成口径）；③ 收引号/括号结尾（`不可能！”`）的末字判为非停顿，拼出 `！”。` 双标点，已改为剥掉收引号再判末字（14 集语料恰 3/2303 句受影响，其余零改写）；②③ 改变合成结果而成员文本不变 ⇒ 块后缀 `split=v2→v3` 换键；④ `pipeline.py status` 的 narration.json 新鲜度只比 narration.md，只改台本时误报「✅ 新鲜」而 `tts` 不自动重 build ⇒ 拿旧 cue 合成入缓存，已把 cues.toml 纳入主稿依赖。5 条新增用例在旧实现下全红。教训：「只许改 X」类校验须比较「保留 X 以外全部信息」的规范形，而不是先抹掉受保护信息再查存在性；新增派生输入（sidecar）时同步所有新鲜度/依赖面。评审回归四（2026-09-26）：① 无台本段的自动分块是整段全局 DP（Σlen²），块界依赖段内全部句长——9 句×31 字一幕末句 +1 字，5 个块边界全部平移、整幕重录，与「改一句重录整块」的契约不符；14 集语料逐句 ±2/±8 字模拟：改字爆炸半径均值 3.73 / p95 11 / max 34 句。对拍了定长窗（3/6/9 句）+窗内 DP、左到右贪心、id 哈希锚定窗（CDC）等 13 种候选：贪心仍会向右级联（max 31）；CDC 能把插/删句波及从均值 ~12 压到 ~4，但块数 +11–20%（缝多即朗读感回潮）；选 6 句定长窗 + 1 句尾窗并入前窗：爆炸半径 max 34→7、p95 11→3、仅本块 88.8%→94.7%，块数 836→858（+2.6%）、单句块 0.4%。插/删句仍按位置重排同段其后各窗（旧算法同样整段重排，均值 11.6→14.0 句，未恶化量级），台本块起点是硬边界可把波及收在段内，已写进 §4.5。② 台本 `[say]` 去标点比对连数字里的半角 `.,:` 一并剥掉，`3.5%`→`35%`、`10:30`→`1030` 能过校验（念成另一个数而字幕不变），已改为夹在两数字之间的不剥。③ `[block]` 值写成字符串（TOML 合法）时 `spec.get` 抛 AttributeError、`alpha = "x"` 的 `float()` 在 try 外，build 以 traceback 退出——已统一汇入 FAIL 清单（含 `[block]`/`[say]` 本身不是表、`alpha` 为 bool、`emo` 非字符串）。3 条新增用例在旧实现下全红（另 1 条尾窗守卫为新设计兜底）。教训：以缓存为单位的划分算法，目标函数必须是局部的——全局最优的划分对局部改动不稳定，评审「改一处波及多少」要用真实语料做逐句扰动模拟，而不是只看一例；「去掉 X 再比」的 X 要按上下文判定（数字里的 `.` 不是标点）。评审回归五（2026-09-26）：① 台本 cue 方向归一后 Σ 浮点可为 1.0000000000000002（如 `afraid:0.01,surprised:0.04,calm:0.13`），build 按 (0, 0.8] 放行的 `alpha = 0.8` 在 `resolve_block_vec` 与服务端 Σ×α≤0.8 护栏上以 1 ulp 之差被拒（α=0.8 时随机方向约 0.7% 的组合；只放宽客户端比较会把误拒挪到服务端、变成合成中途的 400），已改为 α>0.8 才报错、仅踩边界时把最大分量逐 ulp 下调（≤2 步，偏差 <1e-15，未踩边界的向量与摘要逐位不变）；② `[say]` 比对无条件剥掉全角标点，往数字串里插 `，`（`1200`→`12，00`、`2026年`→`20，26年`）或删掉两数之间的标点（`2020，2026`→`20202026`）都能过校验，逐字符判定还会被 `12……00` 这类多字符串绕过，已改为按标点串整体判定：夹在两数字之间的单个半角 `.,:` 原样保留、其余归一为分隔符（两数之间换表演标点照常放行）。2 条新增用例在旧实现下全红；14 集语料均无台本文件，零波及。教训：两端各设一道同口径护栏时，边界修复要让**发出的数据**本身合规，而不是只放宽一端；「只许改标点」的规范形要以标点串为单位判定上下文，逐字符判定会被连写绕过。评审回归六（2026-09-26）：① 回归三的「保留标注去标点再比」连标注内部的标点一起剥，`<行|HANG，2>` ≡ `<行|HANG2>`，build 放行并把非法标注写进 ttsText（`pron_marks.validate` 判非法；走 pipeline 要到 pre-TTS 门才红，直跑 tts.py 或 `--skip-pre-tts` 会原样送合成），已追加 `PRON_MARK_RE.findall` 逐字全等；② `split_block_pcm` 末段起点即末个切点，静音只是低于 p95−35 dB 而非零值，中间段两端淡变而末段只淡出 ⇒ 每个多句块末句起播有底噪阶跃，已改为每段两端淡变——时长不变、差异落在静音内不可听，**不换键**（换键口径写进 `block_digest_suffix`：只有送合成文本或切段时长变了才递增，否则存量音频为不可听差异整块重录）；③ `--steady` 冲突检查排在 EN 回退之前，EN 版本已回退逐句却仍被拒（报错文案还指向块合成），已把检查移到回退之后。3 条新增用例在旧实现下全红。教训：「规范形比较」要先界定哪些片段是不透明的——标注是整体，内部字符不参与规范化；同一路径上的降级（EN 回退）会让后续互斥检查的前提失效，互斥检查须排在所有降级之后。 评审回归七（2026-09-26）：① story 档的「换 take」口径不可用——文档让用 `--seed-offset`，但它叠加在全局种子上，全部块的 `|seed=` 后缀一起变 ⇒ 整集重录，且 `.engine` 签名不含 seed、护栏不拦（即 ISSUE-174 同型陷阱）；§5.4 的「隔离 seed 摘要重掷单句 → 回存 canonical」在块模式下做不了（canonical 恒含 seed 4242 与块后缀、台本无逐块种子），一句句尾英文词不合格就只能整集重掷。已新增台本 `[take] <句id> = N`（1–999，build 校验）：该句所在块种子 +N、只重录这一块，定稿值留在台本即 canonical；同块多条 take 在 `--plan` 即报错；`--plan` 与合成共用 `block_sampling` 同一口径（变异验证：只让 --plan 丢 take 即红）；无 take 的块摘要逐位不变（存量零波及）。② CHANGELOG 的块摘要后缀写成 `|block=<sha12>|pos=k/n`，代码实为 `|block=<sha12>|k/n`，VOICE-CLONING §六 公式表也缺采样与块后缀——已改文档对齐代码（不改代码：改摘要格式会令已产 story 音频整块失配）。5 条新增用例在旧实现下全红（另 1 条为 plan/合成口径一致性守卫）。教训：引入新的缓存单位（块）时，所有「按旧单位定义」的操作原语（换 take、单句补配、回存 canonical）都要按新单位重新审一遍；全局参数（种子）在粗粒度缓存下的波及面是全量，逐单位的覆盖须落在单一事实源（台本）里。 评审回归八（2026-09-26）：① `apply_cues` 只读 `block`/`say`/`take` 三表与块表的 `emo`/`alpha` 两键，其余一律无声忽略——`[blocks.p0-01]` 返回 0 块 0 错、`alhpa = 0.5` 落盘时丢 alpha 回落预设 0.28，`[takes]`/`[says]` 同理：`--plan` 显示无块待重录，写稿人却以为 take/cue 已生效。已改为未知顶层表/键与块表未知键汇入 FAIL 清单；② `[say]` 的标点类 `CUES_PUNCT_RE` 缺 `—`，而本管线把 `——` 当停顿标点（`tts_text` 映射为 `，`、`block_synth_text` 视作软停顿结尾），`——`→`…` 或新增破折号被报「改字」拒收（14 集语料 226/2303 句含破折号）；已计入标点，夹在两数之间时同其余标点归一为分隔符（删掉仍拒）。2 条新增用例在旧实现下全红；14 集均无台本文件，零波及。教训：sidecar 的形态校验要白名单化——只校验「认得的键长什么样」会放过「根本没认出来的键」，拼错即静默失效；「只许改标点」的标点集要与管线其他环节（`tts_text`、块拼接的停顿判定）对「什么算停顿」的口径一致。 评审回归九（2026-09-26）：① `/health` 的 `supports_blocks=false` 有三种成因——服务端代码过旧（字段缺失）、IndexTTS-2（`--version 2`）、上游 low_vram（CUDA 显存 <10 GB 自动开启）——客户端一律报「代码过旧，请重启」，后两种重启不会变，而 story 已是 scaffold 默认档 ⇒ 这类主机开箱即卡死在空转重启；已让 `/health` 回报 `low_vram`、客户端 `blocks_unsupported_hint` 按成因分诊并给出换逐句档（`sunny`）出路；② `--list-styles` 表内无种子/块模式列，页脚称「均取上游默认 … seed=None」，story 的 seed=4242 与块合成在唯一对外视图里隐身；已在行尾标注。2 条新增用例在旧实现下全红（MPS 主路径 `low_vram` 恒 False，零波及）。教训：能力位为 false 时要回报**成因**而非只回报结论——同一个 false 背后「可修复（升级）」与「固有形态（换档）」的处置相反，报错只按最常见成因写会把少数主机引进死循环。 评审回归十（2026-09-26）：① 台本 `[say]` 让 `ttsText` 成了第二个写稿面，而 `check_reading_traps` 只扫字幕面 `text`——`2020、2026` 配 say `2020—2026` 能过去标点比对（两数之间标点归一为分隔符），`tts_text` 不映射单个 `—`，送合成即 `2020—2026`，命中 FAIL 陷阱「数字区间连字符读成减」而门零报；已改为同扫去标注后的合成面（仅 say 句与字幕面不同），同一陷阱两面都中只报字幕面一次，合成面命中点名「台本 [say]」；② `tts_sample` 为 story 补了逐档 seed 却漏了同属预设合成口径的 `perform_punct`，含 `……` 的试听句 story 小样念 `。`、成片念 `…`；已按档传 `perform`，`--all-styles` 下表演标点档的预处理文本分行回显；③ `tts_progress` 按 mtime 聚簇后墙钟单位变成「一次合成」（块模式约 3 句），输出仍标「每句墙钟」「滚动 30 句」——数值约为真实每句的 3 倍、窗口实覆盖约 90 句，易误读为变慢；已改为簇墙钟 ÷ 簇内句数、窗口按句数取尾部簇（逐句档 180 组随机序列与旧输出逐字节一致）。3 条新增用例在旧实现下全红；14 集语料 pre-TTS 读法陷阱门新旧输出逐集一致（均无台本）。教训：新增一个写稿面（sidecar 覆写送合成文本）时，所有「按文本判定」的门都要重新确认扫的是哪个面；预设新增一项合成口径时，所有复刻合成路径的入口（管线、小样）要逐项对齐，不能只补被点名的那一项；聚合改变统计单位时，标签与窗口语义要随单位一起折算。

**同类问题影响**：14 个存量集仍锁 sunny-steady（用户确认先不动；手工重制时按 references/06「重制存量集」流程切 story + 补台本）。

## RSI-012 文档谎报上游情感混合行为：向量在场时音频被整个丢弃

**表因**：第三轮实验中 `--emo-ref` + `--emo-vector` 同传（实验服务放行）的输出与纯向量**逐字节一致**（p04/p11 cmp 相同）。

**根因**：上游 `infer_v2_5.py:582-585` 只要给了 `emo_vector` 就把 `emo_audio_prompt` 置 None——音频被整个丢弃。本仓 `tts_server.py` 注释与 `INDEXTTS-2.5-ADVANCED.md` §3.1 均声称「音频仍会以 (1−Σw) 权重混进最终 emovec」，**错误**：`(1−Σw)` 份额实际来自本人 `spk_audio_prompt` 的情感编码（emo_audio_prompt 回落为 spk 自身）。生产端行为无影响（服务本就拒绝同传），但误导调参方向——第三轮实验有一个对照组（「博主语调 × 段落」）实际从未用到博主音频，标签失实。

**处理方式**：tts_server.py 请求模型注释与 ADVANCED §3.1 勘误（附源码行号与字节级实测证据）；第三轮试听页 #07 的真实配方同步勘误（纯本人音色的段落演绎——这也解释了它音色门全场最稳）。

**后续防范**：涉及上游行为的文档断言须附源码行号锚点；「A 与 B 组合生效」类机制声明，用「同传 A+B vs 只传 A 输出逐字节比对」验证过才可写。

## RSI-013 流水线缺「写顺」环节：AI 稿件语义与段落断断续续、不按人的阅读习惯组织

**表因**：用户反馈（2026-09-25）：流水线产出的逐字稿、策划案、分镜等稿件语义与段落之间断断续续，不按人的阅读理解习惯（总分总、结论先行、段间过渡）组织，读起来是 AI 写的。

**复现（真实语料只读扫描，negentropy 14 集已发布逐字稿，2303 句）**：书面腔禁词（综上所述 / 值得注意的是 / 首先 / 其次…）**0 处**；逗号或顿号收尾、语义跨到下一行的半句 110 处；冒号收尾、下一行才给答案 81 处；「不是……而是……」42 处；破折号 231 处；9/14 集幕内零空行分段（一幕 20–36 句平铺）。扫描命令与逐集明细见 [docs/research/prose-refinement.md](../research/prose-refinement.md) §一。

**根因**：流水线有「写对」（③ 写作纪律）与「查对」（④ 双重校验），没有「写顺」。④ 易懂性评审的 5 条判据全部是句级局部判据（术语降落、指代距离、抽象连段、金句密度、连读歧义），篇章层（幕内推进、段间衔接、开头的问题有没有兑现）没有任何环节负责；03 的书面腔禁令只管词汇层，而语料证明词汇层早已干净。叠加生成机制本身：自回归逐段生成没有全局篇章规划，段间的承接无人负责。

**定性**：非阻断改进（用户点名启动）。

**方案比选**（详见研究文档 §四）：落位——内嵌子步骤（最小干预）vs **正式阶段**（用户决策采纳：阶段地位显式、有独立的门，代理不会跳过）；插入位置——③↔④ 之间 vs **④ 之后、分镜之前**（采纳：优化对象是已校验稿，只对改动句回跑 ④A；beat 分段直接喂给切镜；④ 不动）vs 分镜之后（否决：破坏句区间与锚句，违反配音「文稿冻结」前置）；执法——**不加内容类机器门**（用户决策；语料证明词表门拦不住真实病灶，结构层无法可靠正则化）。

**处理方式**：新增 `references/05-prose-refinement.md`（四层 pass + 四稿专属规则 + 中文去机器味检查表 + 改动审计与复核），原 05–09 `git mv` 顺移为 06–10；stages.toml 插入 `prose-refinement`（authored、无子命令）；SKILL.md / README / PIPELINE.md / knowledge-map / evals / 脚本文案 / 模板与 frozen 注释中的阶段序号与文件名全量同步；RSI.md 不变量 1、8、11 与对应测试去数字化；新增文档完整性门 `test_spec_references_resolve`；两张架构图重生成。[PR #18](https://github.com/ThreeFish-AI/to-video/pull/18)，commit `c3834c4`。

**后续防范**：① 执法测试与不变量**不写死阶段数量或具体序号**，一律从 stages.toml 推导（本次三条测试与三条不变量都曾写死「9」）；② 规格文件名出现在注释与散文里时，改名必须过 `test_spec_references_resolve`，不能只靠 Markdown 链接门；③ 裸写的 `references/07` 这类简写不在门内，改名时须用 `git grep` 搜出所有「references/ + 两位数字」且后面不跟连字符的写法，人工逐条核对；④ 内容层新规则上线前，先在真实语料上量化病灶，避免给已经干净的层级加门。评审回归（2026-09-26）：① 通过门里的「成文评审 REWRITE=0」在规格中找不到产出它的步骤：第九节只定义了改动句回 ④A 复核，第十节只是勾选表，执行 ⑤ 的代理无法判门。已在第九节补第 3 步「成文评审」：独立子代理只拿规格、改后稿件和改动表，按第三至第八节的具名规则判 REWRITE；给不出规则编号的意见不算。② 改动句复核判 REWRITE 时只写了「按 ④ 修正」，门里却只查 RISKY=0。门改为「成文评审 REWRITE=0 且改动句复核 RISKY=0、REWRITE=0」，与 ④ 同口径，stages.toml / SKILL.md / README / CHANGELOG / evals 与 `prose-refinement--passes` 图同步更新。教训：authored 阶段的 prompt 门没有测试兜底，门里每个判定量都要能在规格里找到「谁产出、按什么判」；引用上游门的判定时，连同上游的放行口径一起引用。二次评审（2026-09-26）：① 第九节的 RISKY 回退按单句粒度，但第四节第 9 条允许在相邻 id 间搬运文本，只回退其中一句会让被搬运的文本丢失或重复，且回退句不再送评审、无环节兜底。已改为：重新分配涉及的几个 id 在改动表合写一行，回退以行为单元整组回退。② scaffold 结尾提示「润色四稿再切镜」与规格时序矛盾（分镜在 ⑥ 才产出），改为润色笔记 / 策划 / 逐字稿后切镜、分镜定稿前回调 ⑤ 第七节。③ 研究文档方案 A 一行残留旧序号「②③⑤」，改为 ②③⑥。教训：规则允许跨单元搬运内容时，回退、复核等补偿动作的粒度必须与搬运的粒度一致；重编号后，研究文档里描述候选方案的旧序号同样要按 `git grep` 圈号逐条核对。三次评审（2026-09-26）：① 第九节第 1 步「在 git 下即以 git diff 定位改动」默认稿件已提交，而新集稿件在 ⑤ 时多半未被 git 跟踪，`git diff` 看不到，复核范围与 RISKY 回退都失去基准。已改为：稿件在 ④ 清零时已 commit 才用 `git diff HEAD` / `git show HEAD:`，否则一律复制到 `$P/.temp/prose-before/`；不拿暂存区当留底（改稿中途再 `git add` 即覆盖），没有留底不得开始改稿；evals #1 的 ⑤ 断言补「改前留底」。② 改动句复核只跑 ④A，而 ⑤ 的话题链改主语、跨 id 搬运正好会让 ④B 的术语降落、指代距离、抽象连段退步，定稿时无环节再核。复核范围扩为「A 节四级判定 + B 节前三条（连同前后句一起看）」，门的字面不变（B 只产出 REWRITE，已含在「REWRITE=0」内），04 规格、SKILL.md、stages.toml 注释、CHANGELOG、evals 与研究文档同步。③ `prose-refinement--passes` 图的输入仍是含分镜的「四稿」，与时序矛盾（分镜在 ⑥ 才产出）：输入改为三稿，顶部新增「⑥ 分镜回调」泳道（定稿 →切镜→ ⑥ 分镜，定稿前回调第七节），复核节点标注 ④A + ④B 前三条；archify showcase 9/9、0 错 0 警、无回折尖刺，visual-check 通过，重导 dark/light PNG，mmd 与 alt 文本同步。④ 新增的 `spec_reference_files()` 与既有 `current_docs_and_code()` 逐项重复，已删除并把知识索引并入后者（反控：向知识索引注入旧文件名即红）。教训：留底、回退这类补偿动作要先确认基准在真实初态下存在（新集 = 未跟踪文件）；上游门拆成 A/B 两半时，下游复核要写明复核哪一半，不能只引半边；修正一处时序表述后，要把同一说法的所有载体（脚本提示、图、alt 文本、规格步骤）一起 grep。四次评审（2026-09-26）：① 第九节第 1 步的留底基准写成 `HEAD`，而 HEAD 在 ⑤ 中途任何一次提交后都会移走：`git diff HEAD` 只剩最后一次提交之后的改动，更早改过的句子漏出 ④ 复核；RISKY 回退用 `git show HEAD:` 取回的也是改了一半的文本。已改为开工前 `git rev-parse HEAD` 记下基准 SHA，diff/show 一律用它。② 第四节第 9 条的跨 id 搬运对已有分镜的集不安全：SKILL.md「润色成稿」路由与第二节第 6 条都允许对已制作的集跑 ⑤，而分镜画面列、场景 `rel(beat,'句id')` / `at()` 时点、archify cue 锚句都按 id 绑定内容，文本搬走后画面比口播早或晚一句，`check` 查不出。已补护栏：分镜已存在时，搬运前在分镜与 `video/src/scenes/` 里 grep 涉及的 id，有画面锚在被搬走的文字上就同步改分镜与场景，或放弃搬运；第十节加一条对应勾选。CHANGELOG 同步。教训：留底基准要钉成不可变引用（SHA），不能用会随操作移动的引用（HEAD、暂存区）；研究文档里否决某方案的理由（这里是「破坏分镜句区间与锚句」），在规格仍允许该情形出现的路径上（已制作集）同样要设防。合并 main（2026-09-26，PR #17 story 配音已合入）：① 本条由 RSI-011 顺延改号为 RSI-013，现行文案、测试 docstring、mermaid 注释与 CHANGELOG 同步；② PR #17 新增文案里的 `references/06-tts-voice.md`（tts.py 两处）改指 07，CHANGELOG [Unreleased] 的「重制流程见 references/06」改为 07；③ ⑤ 规格与 story 档衔接：第二节第 6 条改为「逐句档改一句重配一句、story 档改一句重录整块」并补台本 `[say]` 同步义务（去标点全等，否则 build FAIL），第四节「与配音分块的关系」去掉「若采用」假设、写明 beat 首句应是台本块起点，研究文档 §五 同步。教训：并行分支各自预留台账编号时，后合入者合并前要先 `git grep` 对方已占用的编号；对方合入后，本分支里「尚未合入 / 若采用」这类以对方状态为前提的表述要逐条改成现状。五次评审（2026-09-26）：第九节第 5 步与第十节要求 ⑤ 定稿时「`build` + `check` 零 FAIL」，但新集走主路径（④ 后先润色、再切镜）时还没有 `storyboard.md`，`check_script.py` 的主稿完整门遇缺分镜直接退出（`storyboard.md 不存在`，rc=1；临时工作区实测复现），`pipeline.py check` 又在 zh 失败后短路、en 失配句也点不出——代理要么卡住，要么提前写分镜违反时序。已改为按分镜是否存在分流：已存在跑完整 `check`；新集跑 `check_script.py --pre-tts`（时长预算 / 读法陷阱 / 发音标注，实测 rc=0），双语集另跑 `--lang en`（en 门不读分镜，实测点名基线锁失配）；完整 `check` 移到 ⑥ 之后。SKILL.md 速查表 ⑤ 行与「润色成稿」路由、`prose-refinement--passes` 图（定稿节点改「build + 机器门零 FAIL」、⑥ 节点补「全量 check」；archify showcase 9/9、0 错 0 警、9 条边无回折尖刺，visual-check 通过，重导 dark/light PNG）、mmd 与研究文档 alt 文本同步；工具不改（缺分镜即 FAIL 是完整门的既定语义）。教训：规格里点名的每条命令，都要在该阶段的真实初态（新集 = 分镜未产出）下实跑一次；插入新阶段后，下游产物尚不存在，沿用上游门的命令前先查它对缺失输入是否硬失败。六次评审（2026-09-26）：① 第九节第 4 步把研究笔记的改动句也送回 ④A，但 ④A 以 paper-notes 为锚，笔记本身就是 ④A 的事实源，改写后的主旨综述段只能自己核自己，笔记一旦漂移，后续逐字稿复核也以漂移后的笔记为准。已改为：研究笔记的改动句仍做 A 节四级判定，锚点换成信源原文（A 型 `paper_extract.py find`，B 型按 `research/sources.toml` 登记的 URL 回查）；04 规格「输出」节与 CHANGELOG 同步，④A 的判定口径不变，故 `prose-refinement--passes` 图不动。② L1 把调序、补「转」、兑现开头的问题列为可改项，而第二节第 2 条禁止重排与增句、只给拆句 / 并句指了回 ③ 的出路，第十节第一项在 ⑤ 内可能无法合法达成，代理只能违反 id 冻结或在不相邻 id 间搬文本（锚点回查与相邻 id 回退单元都不覆盖）。已在第二节第 2 条写明 ⑤ 对逐字稿只做 beat 分组与相邻 id 间文本重分配，拆 / 并 / 调序 / 补句一律回 ③、连同已做的 ⑤ 改动重过 ④，回来后重新留底；L1 行加指针，第十节 id 集合基准改为「回过 ③ 的以重新留底时为准」，CHANGELOG 同步。③ 第二节第 5 条仍无条件要求「改完必须重跑 `check`」，是五次评审在第九节修掉的同一问题的残留载体，改为「按第九节第 5 步重跑机器门」，并注明复述门只在分镜与场景已存在时触发。教训：规格让某个事实源本身可被改写时，复核锚点必须上溯到它的上游，不能以它自己为锚；某一层 pass 的「改什么」若与护栏冲突，必须在护栏里给出合法出路，否则验收项形同虚设。 七次评审（2026-09-26）：① SKILL.md「润色成稿」路由写成「`check`（尚无分镜时改跑 `--pre-tts` 门）」，路由壳里反引号命令默认指 `pipeline.py` 子命令，照抄成 `pipeline.py check --pre-tts` 会被 argparse 拒收（实测 `unrecognized arguments`，只有 `check_script.py` 认这个 flag）。已改为直写 `check_script.py --pre-tts`，05 第十节同一写法一并对齐。② `tests/test_docs_paths.py` 两处 docstring 仍用重编号前的简写（「与 07 命令闭环矛盾」「09 规格…该事实条在 07」），改为 08 / 10 / 08；`test_spec_references_resolve` 只认带文件名的完整写法，这类简写正是后续防范第 ③ 条所说的门外盲区。③ 05 规格参考文献 [24] 只给站点根域名，换成 Zeigler 教材 §9.1 的完整页面 URL（已核对该页确有「现在时、主动语态、只写看得见听得见的」依据）。教训：flag 只属于某个脚本时，文档里要连脚本名一起写，不能挂在另一条命令后面；引用 URL 要落到具体页面，核对时顺带确认该页支撑规格里的那条论断。八次评审（2026-09-26）：CHANGELOG「Breaking」第 2 条把旧代集的登记面写成 `[[skeleton.drift]]`。drift 是按「集 × 文件」钉指纹的特有偏离豁免，14 个存量集要为 5 个 frozen 文件逐条登记（至多约 70 条）；整组停在旧代应登记一组 `[[skeleton.generation]]`（skeleton.toml「骨架分代」：一次模板升级 = 一代；`verify_skeleton` 的 I1/I2 均认 `generation_hit`，半同步集报 GENERATION-MIXED）。已改为 generation，并注明 legacy 的旧指纹从 `verify_skeleton` 报告里取。教训：写迁移指引时，逃逸口要按它在机制里的语义选（代际滞后 → generation，特有偏离 → drift），不能按名字像不像来选。九次评审（2026-09-26）：`tests/test_stages.py` 的 `ORDINALS` 注释称覆盖「20 以内」，字符串却只到 ⑫——阶段数过 12 时 `test_stage_numbers_align_spec_files` 在 `ORDINALS.index` 抛 ValueError，`test_ordinals_are_a_contiguous_run_from_one` 则把正确的声明误报为「无重无缺」违规，等于在刚去数字化的测试里又藏了一个写死上限。已补齐为 Unicode 连续码位 ①–⑳（U+2460–U+2473），注释同步。教训：去数字化时，推导所依赖的查表本身也是上限，要么覆盖到符号集的自然边界，要么在注释里写明真实上限。二次合并 main（2026-09-26，PR #19 story 块合成回归七~十已合入，未占用新台账号）：CHANGELOG [Unreleased] 的 story 条目两侧都改过，取 main 新版正文、保留本分支的「重制流程见 references/07」；其 TTS 规格改动随改名识别落入 `07-tts-voice.md`，新增文案无旧规格指针。

**同类问题影响**：negentropy 已发布集的 frozen 骨架注释指针会落后于模板（md5 变化、`verify_skeleton --strict` 报 STALE），仅注释差异、行为零改动，按 CHANGELOG「Breaking」第 2 条自适配；PR #17 先于本条合入 main（`3b1607a`，占用 RSI-011/012），本条合并 main 时由 RSI-011 顺延改号为 RSI-013（合并前的 commit message 仍写 RSI-011，以本台账为准）；其 TTS 规格改动随 git 改名识别自动落入 `references/07-tts-voice.md`，RSI-011 / RSI-012 两条台账里的 `references/06` 指当时的 TTS 规格（现 07），按历史记录保留原文；尚未发版的 CHANGELOG [Unreleased] 与现行文案里的同类旧指针已随本次合并改为新编号。

## RSI-014 多音字候选报告非门且无语义消歧：高危读音零拦截直到终渲才靠人耳发现

**表因**：jev-decision-model-video v1（negentropy `37692b45d`）终渲后发现全片 26 处「行(háng)」被 TTS 读成 xíng（修复提交 `8974c2f3f` 标 27 处 HANG2：26 处 v1 位置 + 1 处 v2 改写新增句）——`check_script.py --pron-candidates` 是非门报告（exit 恒 0），`POLYPHONE_CANDIDATES` 仅按「字符在场」列两种候选读音、不做上下文消歧，全片零拦截；PRON-GLOSSARY 台账仅 1 条已确认记录（英文专名 Context），03 规格的纪律是「确认读错才回填台账」——纯被动、无预防，系统性读错只能等终渲后的人耳。

**复现（修复前）**：对含 `每一行都要重新算。` 的最小工程跑 `check_script.py --pron-candidates` → 输出仅「银行/一行代码 háng · 行走/运行 xíng → 若听出错读：`<行|HANG2>` / `<行|XING2>`」，exit 0。真实语料对拍：把 jev 集 v2 稿（negentropy `8974c2f3f`，分支 ThreeFish-AI/jev-video-remake，经 [negentropy#1176](https://github.com/ThreeFish-AI/negentropy/pull/1176) 合入 feature/1.x.x 于 `57987b28b`；27 处 `<行|HANG2>` + 1 处 `<行|XING2>`）剥掉标注模拟 v1——语义规则表在这份语料上命中 27 处 HANG2，与专家标注集逐句对应；对真 v1（`37692b45d`，未标注）直接命中 26 处，除 v2 改写新增句 p0-20 外逐一对应。全 14 集存量对拍（negentropy feature/1.x.x@`95f5a532e`）51 处命中、全部 HANG2，以「一行+量词」（一行日志/一行字）与「行业」语境为主，每集 ≤9 处（origin@`57987b28b` 已漂移为 15 集 58 处）。

**根因**：① `pron_marks.py` 的候选表是纯「字符存在→列双候选」报告；② `check_script.py` 的 pron-candidates 子命令 exit 恒 0，不参与任何门禁；③ 03 规格发音标注节的纪律只写了「确认读错才回填台账」，没有区分「字典级确定读音的高危面」与「歧义候选面」——前者的标注时机应是写稿阶段而非事后；④ 台账作为唯一证据入口没有反哺机制的通道。

**定性**：非阻断改进（发现集已由内容侧修复；机制缺陷是防线缺位，同类错读在每集都可能复发）。

**方案比选**：规则面宽度三选——A 仅 行→HANG2 单向（采纳）；B 行 双向全量（HANG2+XING2 词表）；C 全部 9 个候选字都配语义规则词表。实测校准否决 B/C：v1 全片 36 个「行」中 26 处实证错读（háng 向）、其余 10 处 xíng 向语境专家仅防御性标了 1 处（放行 p6-39）——**xíng 是 TTS 的默认倾向**（错读方向恒是 háng→xíng），给默认读对的方向设规则只会产出批量冗余标注（B 要多标 9 处、C 更多），门退化成噪声然后被绕开。规则入表纪律沿用 READING_TRAPS 的「先探针后成门」：某字经试听证实系统性读错后其高危方向才入表（台账是证据入口）。门粒度二选——句级「句中有任一标注即过」被否决：同句「银行已标注 + 每行未标注」会放过第二个 occurrence，按 occurrence 粒度判定（标注几何与 `strip_marks` 剥离几何逐字符对齐）。已标注 occurrence 即便读音与推荐不同也不拦：语义规则是建议不是权威，作者的不同标注是合法异议（规则表本身可能错）。

**处理方式**：分支 `ThreeFish-AI/rsi-014-015-pron-gate-and-layperson-check`（[PR #20](https://github.com/ThreeFish-AI/to-video/pull/20)）。① `pron_marks.py`：`POLYPHONE_CANDIDATES` 每字扩 `semantic_rules` 字段（`(正则, 推荐读音)`，正则必须含本字、覆盖判定按「匹配区间盖住 occurrence」，三条结构门测试钉住）；新增 `semantic_missing()` 纯函数——occurrence 粒度语义消歧，规则命中而无任何标注 → 建议清单；规则只挂 行→HANG2（三条正则：复合词/量词/`的行`，均带负面预查防 一行人/类行为/的行程 误收）。② `check_script.py`：`--pron-gate` flag 把「规则命中而未标注」升为 FAIL 门（缺省仍为报告；与 `--pre-tts`/`--term-density`/`--lang en` 互斥）。③ 03 规格发音标注节补「高危多音字（语义规则命中→建议标注）写稿阶段标好，不要等试听」。④ PRON-GLOSSARY 加「语义规则速查」节（由测试从 `POLYPHONE_CANDIDATES` 渲染钉住，与代码同源不漂移），候选纪律改为两段式：规则命中写稿即标、无规则依据不预防性标注。⑤ 回归测试 `tests/test_pron_gate.py`（CLI 门：不加标注 FAIL / 加标注过 / 作者异议不拦 / 报告面保持非门 / xíng 向零误报 / 互斥）+ `test_pron_marks.py` 扩语义面（规则锚本字、读音合法、速查同源、occurrence 精度、多字词标注覆盖、作者接管）。

**后续防范**：语义规则宁缺勿错——错规则会把可能读对强推成必然读错（上游丢弃原字无兜底）；新规则须有试听/探针证据再入表，入表同 PR 必须带正反控用例（正例：该语境会被推荐；反例：默认读对的方向零误报）。门的退出码语义不可混：报告面（候选注意力）与门面（FAIL）分 flag，互斥执法。文档里的规则速查表必须与代码同源钉住（测试渲染比对），手抄表必漂移。评审回归（2026-09-28）：① 规则误报面——`的行` 预查缺 xíng 复合词续字（的行文/行事/行踪/行李/行星/行进 全部误报 HANG2，`--pron-gate` 对正确稿 FAIL 并指示加必然读错的标注），量词面 `同`/`前一?`/`后一?` 前缀与 行为/各行其是 续字误收（结伴同行/前行/这一行为/三思而后行）；「xíng 向零误报」只在已扫 14 集语料上成立、泛化为假。已收紧：`的行` 预查扩 事文踪李星进、量词续字预查补 为/其、`同行` 只收实证形态 `同行(?=的)`（jev p3-19）、前/后 前缀删除（前一行/后一行 由裸 `一` 覆盖）；**行动 歧义（一行动字 háng vs 这一行动 xíng）局部正则不可分，按实证取 háng、预查不排除 动**——收紧后 14 集仍 51 处、jev 27/27 不变（对拍复验）。教训：「零误报」类声称必须写明语料边界；黑名单是开放集，对抗样例（常见 xíng 复合词枚举）须与正控同 PR 入测；同一字同一读法在多条规则里立场必须一致（改前「这一行为」经 一 前缀命中而「的行为」被 的行 预查排除，自相矛盾）。二次评审（2026-09-28）：① 黑名单仍漏 驶/使/医/善/贿（的行驶/的行使/的行医/的行善/的行贿 误报）——已补；② 量词面续字集与 `的行` 黑名单对齐（改前 的行星 排除而 某行星 命中，同一复合词两条规则判决相反——已统一为同一份续字集，唯 业 不入量词面：各行各业 是真 háng；一行文字 类真 háng 漏报为对齐的镜像代价、落回候选面）；③ `同行(?=的)` 的 tóngxíng de（同行的伙伴）歧义面成文。收紧后 14 集仍 51 处、jev 27/27 不变（对拍复验）。教训：续字黑名单一次列全并两条规则共用同一份，不各改各的。② 引文失实——negentropy#1173 实为画面去复述、与 HANG2 标注无关，27 处标注真源是 `8974c2f3f`（分支 ThreeFish-AI/jev-video-remake，经 negentropy#1176 合入 `57987b28b`）；「~30 处」无任何提交/台账出处（真 v1=`37692b45d` 规则命中 26 处，27=26+1 处 v2 改写新增句）；「现稿已标注」未钉版本；行→HANG2 未按自立的「台账是证据入口」入台账。已全部勘误钉 SHA 并补台账证据行。教训：引文落笔前跑一手核验（`gh pr view` + `git log -S`）；立规与执行必须同 PR 闭环。③ 门面缺陷——`--pron-gate` 把非法标注当有效作者接管放行（rc=0 假绿）；`--json`/`--check-scenes`/`--check-motion` 在 pron 面被静默丢弃；zh-only 报错点名用户未传的 flag；速查表同源测试单向（文档多脏行不红）。已修：门面先跑 `validate` 非法即 FAIL（报告面点名不判死、维持退出码恒 0）、互斥对称化并按实际 flag 点名、速查表改双向集合断言。教训：「已标注=接管」类前提要先校验前提本身；新门面的互斥矩阵要一次列全——静默丢弃等于门没跑却让人以为跑了；同源测试要双向（存在 + 无脏行）。

**同类问题影响**：14 集存量对拍（feature/1.x.x@`95f5a532e`）51 处规则命中（全部 HANG2），均为已发布成片，本仓不改其内容；各集重制/重配音时跑 `--pron-gate` 即可逐处补标（jev 集自 negentropy origin/feature/1.x.x@`57987b28b` 起已标注 27 处、门过 0 命中；更早的 #1172/#1173 版 0 命中系全片无 háng 语境，并非已标注）。英文专名（CMU 通道）不属本门范围——句尾英文词读法按既有「标注兜底、不赌采样」纪律走 PRON-GLOSSARY 台账。

## RSI-015 ④B 易懂性检查全是句级局部判据：解释存在≠解释到达时观众还在线

**表因**：jev-decision-model-video v1 过了 ④B 五条全检（术语降落/指代距离/抽象连段/金句密度/听觉友好），普通观众反馈「一脸懵」——三个名词系统（集中度/门槛/计费单位）全部「先用后讲」：每个术语首现时旁边都有「解释」，但解释本身又用了未解释概念（递归不自懂），且解释常在术语已承担载荷**之后**才到达。

**根因**：④B 五条全是句级局部判据——①「前一句**或后一句**内有解释」允许解释迟到（载荷已压在未解释的词上，观众已掉线）；②只检查「解释存在」，不检查解释本身是否可懂（比喻建立在另一个未解释概念上 = 零信息）；③无密度预算（一个 beat 塞三个新术语，逐个解释也来不及）；④无消除路径（超载时不知道该拆 beat 还是换白话）；⑤无机器面（密度可机判的那半没人算）。

**定性**：非阻断改进（评审判据缺位；机器面 WARN 级，不新增 FAIL 门）。

**处理方式**：分支 `ThreeFish-AI/rsi-014-015-pron-gate-and-layperson-check`（[PR #20](https://github.com/ThreeFish-AI/to-video/pull/20)）。① 04 规格 B 节在既有五条后追加「外行瞬时理解三判据」：**解释可懂性**（递归一层检查——比喻不能建立在另一个未解释概念上）、**先释后用**（术语首次承担载荷——参与因果/触发动作/被比较——时解释须已在前一句出现，不能靠后一句补救）、**密度预算**（每 beat 新术语 ≤2、每幕 ≤8，超出拆 beat 或白话替代）。② `check_script.py` 新增 `--term-density`（WARN 级）：逐 beat 统计**首现术语**个数、逐幕汇总；中文术语经 `--terms` 逗号清单显式声明（④B 评审员圈定后喂入——机器分不出「集中度」是不是术语，声明优于猜测）+ 拉丁字母词自动面（≥2 字符 token，casefold 归并）；beat 边界读 `build_narration.py` 新派生的 `beatStart` 键（幕首句与幕内空行后首句落 True，`>` 备注行不断 beat——与 03 格式契约「幕内空行 = 一个 beat」同源），旧版 json 缺该键时 beat 级点名跳过、幕级照跑；`--pre-tts` 模式同样可跑（④B 评审时分镜未写）。与 `--pron-candidates/--pron-gate/--lang en` 互斥。③ 03/05 规格里「分段不影响派生物」的旧口径同步改写（分段现落 beatStart 标记，仍不影响配音/字幕/时间轴）。④ 测试：`test_build_narration` 黄金更新 + beatStart 边界用例（备注不断 beat/连续空行/换幕）；`test_check_script` 新增 6 条密度测试（beat 超载/幕超载/预算内静默——同时钉住拉丁字母自动面/无 beatStart 降级/`--terms` 单独用大声退/pre-tts 模式）。

**后续防范**：易懂性判据升级为「解释到达时观众还在线」——评审术语首现时先问三个问题（解释自己可懂吗/载荷前解释到了吗/这一 beat 还有几个新词）。密度门的术语清单由评审员声明，机器不猜术语（猜错的密度门比没有门更糟：噪声会淹没真信号）。beat 边界以 narration.md 的空行为 SSOT（经 build 的 beatStart 派生），不得在消费者里另写 md 解析器。评审回归（2026-09-28）：① 密度门——`--terms` 子串匹配与拉丁自动面对同一 token 双计（声明 AI 命中 OpenAI 内嵌子串且 openai 再计、门槛/高门槛 同处双计），声明词全片零命中静默（圈词与稿子措辞失配时该术语系统的密度门无声失效）。已修：拉丁声明词整 token 匹配、中文声明词重叠最长优先占位、零命中点名 WARN；补幕级 at-8 预算边界反控（恰 8 静默）。教训：计数类门的匹配语义必须定义 token 边界——子串计数天然双计；「门没测到」与「测了合规」必须可区分。二次评审（2026-09-28）：被更长声明词占位命中（门槛 ⊂ 已命中的 高门槛）不算「全片未命中」失配——改前 WARN 会把评审员引向「稿子没写门槛」的错误结论，已按占位关系豁免。② 口径面——build 注释 05 规格指针写错章节（第八节实为去机器味表，beat 规则在第四节第 8 条）；「无台本⇒逐字节一致」旧声明被 beatStart 无条件落键证伪未同步（两处已收窄为「除该键外逐字节一致」）；台账 7 条密度用例实为 6 条；PIPELINE 脚本表未登记两个新 flag。已修。教训：新增派生键时 grep 全部「逐字节一致/零波及」类既有声明；测试计数以 `--collect-only` 实测为准。

**同类问题影响**：`beatStart` 是 narration.json 的**新增**派生键——旧版 json 不含它，`--term-density` 幕级照跑、beat 级点名跳过；存量集重跑 build 即得（配音/字幕/时间轴零波及，tts 摘要只算文本）。04 规格「输出」节的改动句复核口径（A 节 + B 节前三条）未扩到新三判据——新三判据在 ④B 主体评审执法，⑤ 改动句复核是否纳入待下一集实证后再议。

## RSI-016 依赖版本策略缺位与渲染引擎/CAD 资产选型悬置

**表因**：用户提出（2026-09-27）：① 本技能所涉依赖的使用版本未优先指定到最新版（如 Remotion 模板钉 4.0.512），且每次使用时无「直接用最新版」的提醒；② HyperFrames 与 Remotion 的取舍、text-to-cad 是否引入作为 3D/2D 建模工具，两项选型悬置待调研。

**根因**：模板 `assets/video-skeleton/video/package.json.tmpl` 混排钉版——`remotion`/`@remotion/cli` 用 `^4.0.0` 而 `layout-utils`/`media` 精确钉 4.0.512，在 Remotion「全家桶版本严格一致」的官方硬约束下，`pnpm update` 会让 ^ 组分叉触发版本不一致错误；且「优先最新稳定版」从未成文（版本指引只指向 README 地板 pnpm ≥ 12 / Node ≥ 23.6，模板钉版会被读成停留旧版的许可）。选型侧：渲染引擎证据停在 negentropy 2026-09-04 调研（HyperFrames 0.8.27），未随上游三个月演进复核；text-to-cad 从未评估。

**定性**：非阻断改进（用户点名启动）。

**方案比选**（详见 [docs/research/dependency-policy-and-asset-tools.md](../research/dependency-policy-and-asset-tools.md)）：版本策略三案——混排现状（否决：update 后分叉）/ 全 caret（否决：静默漂移击穿 structured 门）/ **全精确钉版 + 追新协议（采纳）**，「最新版优先」由协议而非说明符语法承担。HyperFrames 复核（2026-09-27：0.8.79 / 53.4k★ / Apache-2.0）结论维持 negentropy 既定 B 轨单集试点观望：不替代（静默失败模式 + pre-1.0 API 漂移 + 负向知识清零成本）、不共用双引擎（击穿时序 SSOT 与骨架字节门体系）；触发器增补「1.0 + API 稳定承诺」「Remotion 5.0 license 收紧」。text-to-cad 三案——常驻依赖（否决：交集极小 + 70–80MB + cadgen 高频 churn）/ 固化子步骤（否决：低频需求设常驻流程面）/ **按集 opt-in 独立工具（采纳）**：仅装 cad 单 skill，GLB-only 零转换链直通 GLTFLoader，宪法与 md5 验收照旧（宪法 1 对 CAD 资产的放宽口径见 08「宪法适配」条）。

**处理方式**：模板四包统一精确钉 4.0.529（撰写时最新稳定版）+ lockfile 重生成（js-yaml 安全 override 保留）；`references/PIPELINE.md` 新增「§九 依赖与版本策略」（SSOT）并在 §七 补复核结论一句；提醒面四处——SKILL.md（工作流第 5 步注释 + 关键不变量一条）、`scaffold.py` 建集结尾动态打印模板钉版与 `npm view remotion version` 对照命令、08 命令闭环注释、README 前置依赖表地板注；08 事实条 Remotion 5.0 触发器补两则（numberOfSharedAudioTags 默认将改 0、license 复读）并新增「外部 CAD 资产（可选 opt-in）」小节（SKILL.md「相邻技能协作」cad 行同步登记）；研究文档与 knowledge-map 登记；CHANGELOG [Unreleased] Breaking 节给存量集自适配指引（generation vs drift 两口径）。[PR #21](https://github.com/ThreeFish-AI/to-video/pull/21)，commits `a48df28` / `15a961e` / `945face`。独立核验子代理四门全过（2026-09-27），其建议已并入：新增 test_template_pins_remotion_family_exact_and_identical 机器门、08 宪法适配补相机纪律半句、CHANGELOG Breaking 节标题涵盖 RSI-013/016

**后续防范**：① 新增任何依赖须同时给出「查最新」的一手命令与追新口径；Remotion 家族（按依赖表实际集合，不写死包名）钉版一律精确且整组一致，禁止混排说明符。② 外部工具选型结论必须带数据快照日期与再评估触发器；上游 pre-1.0 的结论有效期以触发器为准，不写「永久结论」。③ 对抗性复核推翻过的表述（动机叙事、可伪造的输出元数据、API 归属错误）不得回流正文。评审回归（2026-09-27）：① 新增的 `test_template_pins_remotion_family_exact_and_identical` 先按精确版本号过滤再判「只剩一个版本」，带 `^`/`~` 的值被滤掉不参与判定——只要四包中有一包精确钉版，main 上的原混排形态（remotion/cli `^4.0.0` + 另两包精确）照样通过，门恰好放行它要防的病灶。已改为先断言四包全部精确、再断言版本全等；正控（当前模板）绿，三则反控（原混排 / 三包 caret / 全精确但版本不等）全红。② 研究文档方案 C 判定栏「与 go mod vendor 式治理同构 [3]」引的是 Remotion License 页，撑不起该类比；改指 skeleton.toml 文件头的原文依据，[3] 挪到 §2.2 的 Remotion 许可陈述上。教训：「全部满足 X」的断言不能写成「过滤出满足 X 的再计数」——过滤会吞掉违例；新门必须用被修复前的真实病灶形态做一次反控。引文编号改动后逐条核对「引用处 ↔ 条目」双向对应，不能只查条目存在。二次评审（2026-09-27）：① `scaffold.py` 结尾的钉版提示读渲染后的 `video/package.json`，而 `--title` 原样插进 description——标题含 ASCII 双引号时产物不是合法 JSON，scaffold 在全部文件落盘后 traceback 退出（rc=1，其后提示被吞；改前同输入 rc=0）。改读渲染前的 `package.json.tmpl`（钉版本是模板属性），新增 `test_scaffold_pin_hint_reads_template_not_rendered_output`（改前红、改后绿）；标题未转义即插进 JSON 属既有问题，不在本条范围。② §九「同系列续集跟随该系列版本」在门上两头不成立（沙箱 `verify_skeleton --strict` 实测）：首集追新登记 drift 后，续集停在模板版 rc=0 放行（系列里仍有一集等于模板指纹时 I1 参照系取模板）；续集照做却不另登记则 I2 STALE（drift 按「集 × 文件」登记）。§九改为续集逐集登记 drift，并如实写明此时系列内一致靠人工核对；新增 `test_family_bump_needs_drift_per_episode` 钉住逐集登记路径，CHANGELOG 与 scaffold 提示同步。③ §九「四包整组」只覆盖模板四包，08「3D 点缀」路径会让单集自加 `@remotion/three`（对 remotion 的 peer 精确锁定），按字面追新会留下旧版、造成全家桶分叉；改为「该集 package.json 里全部 `remotion` / `@remotion/*` 整组」，CHANGELOG 同口径。教训：提示类代码只读机制侧的真理源（模板），不读掺了用户输入的渲染产物；写追新/迁移协议时，要沿门的真实判定路径（参照系选择、登记键粒度）把每一步实跑一次，不能凭直觉宣称「门执法」；「整组」类约束按该集实际依赖集合表述，不按模板的静态集合表述。三次评审（2026-09-27）：① 08「外部 CAD 资产」的宪法适配条写「三条宪法同样生效」，但该节适用条件恰是「只做直角体」词表表达不了的时候——齿轮/轴类 CAD 几何自带曲面，启用即违反宪法 1，适配清单却只交代了颜色/光照/相机，照办的代理要么拒绝该路径、要么违规而不自知；研究文档 §3.3 与 CHANGELOG 还把三条宪法概括成「几何进 CAD、颜色归 theme、零光源」，与 08 原文（直角体/相机/读色）编号对不上。已改为「宪法 1 按边界放宽：曲面只许来自 CAD 模型、手搭仍守直角体词表，母题独占约束（圆被不变量母题独占的画面不出曲面体）照旧」，三处概括同步，并补一句 GLTFLoader 默认 MeshStandardMaterial 在零光源下渲染为黑——覆写材质是启用前提而非可选项（防代理见黑加灯、反向违反宪法 3）。② 钉版门 `test_template_pins_remotion_family_exact_and_identical` 写死四包，模板日后新增 `@remotion/*`（如 `@remotion/paths`）即对混排失明——恰是二次评审教训③「整组按实际依赖集合」所防形态在测试自身的复发。已抽 `remotion_family(deps)` 按依赖表实际集合取（含「家族非空」断言），追新正控的整组改版同用该函数；反控重跑：正控绿，三反控（家族新成员带 `^`——旧写死四包的门对此 GREEN、全 caret、精确但不等）全红。教训：转述他人规约（宪法、门、协议）时逐条对照原文编号，不自造摘要——摘要一旦换词，执行方就多出一套互相矛盾的口径；「整组」约束的执法面（测试）与立规面（协议正文）必须同取「实际集合」，写死名单的执法会让立规随时间失真。四次评审（2026-09-27）：① 本条后续防范①「一律……四包整组一致」自身写死四包，恰是三次评审②所防形态在台账立规语句的残留——执法面（`remotion_family`）与协议正文（§九）均已随二次评审③/三次评审②改为实际集合口径，唯独此句未同步，模板日后新增 `@remotion/*` 时按字面即失去约束。已改为「（按依赖表实际集合，不写死包名）……整组一致」。教训：修「写死名单」类缺陷时，把同口径的全部载体 grep 一遍（测试、协议正文、台账立规语句一并）——漏掉立规语句会让同一条目内的教训自相矛盾。五次评审（2026-09-27）：① `remotion_family` 的「实际集合」只覆盖包名轴、漏了依赖节轴——devDependencies 里的 `@remotion/*`（规范位置即 devDeps 的 `@remotion/testing` 等）会同时逃过钉版门与追新正控，恰是三次评审②所防形态在另一维度的复发；已改为收整份 package.json（两节并扫），正控整组改版按节就地更新。② 追新正控探针写死 4.0.999，模板追平该值时 update 变 no-op、断言以一份全绿 stdout 假红且无线索指向版本碰撞（沙箱复现）；已改为模板钉版 patch+1 推导，与钉版永不相撞。③ 08「整库含 13 个制造域 skill」比其自引事实源（研究文档写 13–14）更精确且无来源支撑，若实为 14 即事实错误；08 已对齐 13–14。④ 本条「提醒面四处」括注混入 cad 行，与 CHANGELOG/研究文档同清单（SKILL.md 只列两项、cad 行归 CAD 功能条目）不一致，且该行是装配指引、无版本提醒语义；已移入 CAD 分句。教训：转述规约的执法面按规约的域取整（整份 package.json），不按现状已实体化的面取；测试魔法字面量与被测事实存在可撞值域时，从事实源推导或断言不相撞；下游摘要不得比自引事实源更精确——未核实的精确化即事实风险。六次评审（2026-09-27）：① 五次评审①把 `remotion_family` 扩成两节并扫时，合并 `{**dev, **deps}` 在同名家族包两节并存且取值不同时静默保留 dependencies 一节——devDependencies 的 `^`/异版说明符被遮蔽，钉版门对跨节混排失明（npm/pnpm 均接受跨节同名 manifest，搬节忘删残留即触发；改前以 devDeps 残留 `^4.0.0` 的合成 package.json 实测，全精确 + 全等断言照样通过）。已改为同名两节取值不同即 ValueError（同值重复条目照常收编），新增反控 `test_remotion_family_rejects_cross_section_duplicate`。② 研究文档 §2.1「近 4 天 7 个 patch」与 npm registry time 字段实测不符：0.8.69–0.8.79 共 11 个 patch 发布于 09-24–09-26 三个日历日（任何锚定快照日的 4 天窗口 ≥10 个），「7」只匹配约 2.2 天的窗口且**低估** churn——该数字支撑「pre-1.0 API 漂移风险真实」结论与再评估触发器的节奏判断；已改为有源计数「09-24–09-26 三个日历日连发 11 个 patch（0.8.69–0.8.79）」。③ 参考文献 [6] 把 "Remotion's bet is React components; HyperFrames' bet is plain HTML" 归属到所链对比页，而该页 HTML 与上游 .mdx 源均零命中（该句逐字出自仓库 README 的同名对比节）；引语已移入 [4] README 括注，[6] 换为该页逐字可查的原有措辞（"One pure function of the frame number, no timeline to register, no contract to get subtly wrong"）。教训：多节视图合并前先判同名键冲突，静默遮蔽会让执法面对自己刚扩的域失明；快照类计数与直接引语落笔前对一手源逐字核对（registry time 字段 / 页面与源文件双查），不以转述或记忆为源。七次评审（2026-09-27，外部评审实证复核）：① §九总则「仓内出现的一切版本号只有两种身份」是排他性列举，而 `.pre-commit-config.yaml` 的 ruff rev v0.14.5 是第三种身份（执法工具硬钉自身）——钉版原因此前只存于维护者个人记忆、仓内零沉淀，按总则「都不是停留在旧版的理由」逐字追新的代理会顺手升 rev 致 lint 大面积红（0.16.7 实测：扫描面 77 处 noqa 误报 RUF100 62 处，0.14.5 全绿）。已在 §九 加唯一例外括注、`.pre-commit-config.yaml` 头注释沉淀钉版原因与升版判据（`ruff==<new>` 全量 lint 零误报才动 rev），CHANGELOG 同口径。② 参考文献 [5] 只给站点根域名且所注页面名非根级路径——rules-and-anti-patterns 实际位于 /prompting/、rendering 位于 /guides/，按条目页面名拼根级路径 404，读者无法直达 §2.2 两条承重引语的一手页面；已落两个完整 URL（llms.txt 索引 + 200/404 实测）。③ §3.1「7 周 37 版」与 PyPI time 字段不符：首发 08-11、末版 09-21、间隔 41 天 ≈ 5.9 周（算到快照日也仅 6.7 周），「37 版」「09-21」属实；已改「08-11–09-21 共 41 天 37 版」——恰是六次评审②同标准的漏网形态。教训：「一切 X」类排他性总则落笔前先 grep 仓内全部同类载体（版本号不只模板与 README 两处：pre-commit rev、CI action 版本皆在其列），例外须与规则同处沉淀并写在钉版所在文件；同一文档已立的计数/引语核对标准要对后续新增段落同等执行，不能只回扫被点名的那一处。八次评审（2026-09-27，外部评审实证复核）：① §3.3 否决行括注「playwright+chromium 已因 QA 预装」归因失实——QA 抽帧（qa_frames.py）走 `pnpm exec remotion ffmpeg`，全文无 playwright；全仓唯一 playwright 消费者是 archify 录制（record_archify.py，Stage ⑥/⑧ 图示资产路径），且经 `uv run --with playwright` 按需解析（README 前置依赖表明言「按需取依赖，无需预装环境」）、以 channel="chrome" 启动系统 Chrome 连 chromium 下载都不触发，「预装」双重失实；已改「playwright 非预装：archify 图解录制同经 `uv run --with playwright` 按需解析，浏览器启动系统 Chrome」。② 参考文献 [8]「PyPI license 元数据缺失，MIT 经仓库 API 确认」前半句可证伪——pypi.org/pypi/cadgen/json 的 info.license 固为 None（旧式文本字段确缺），但 license_expression='MIT'（PEP 639；实测首发 0.4.1 起各版本均带、按版本不可变），项目页侧栏据此显示 MIT；已改「license_expression: MIT——PEP 639 元数据，项目页据此显示」。教训：仓内机制归因（谁拉入哪个依赖）落笔前 grep 全仓消费者并对照 README 安装口径，不凭「该环节大概在用什么」的印象为源；「元数据缺失」类断言先查新式字段是否已取代旧字段（PEP 639 license_expression 取代 license 文本/classifiers）——旧字段为空不等于元数据缺失。九次评审（2026-09-27，外部评审实证复核）：① 七次评审①给「一切版本号只有两种身份」补 ruff 唯一例外时的载体清点（点名 pre-commit rev 与 CI action 版本）漏了模板 `video/pnpm-workspace.yaml` 的 `overrides: js-yaml '>=4.3.2 <5.0.0'`——上界是文件头注释明言的「限 <5 避免 major 跳跃」成文停留理由（父包 cosmiconfig 声明 ^4.1.0、npm 最新已 5.x），既非快照非地板亦非 ruff 例外，与总则「都不是停留在旧版的理由」直接文本冲突；该文件属 frozen 档随每集复制，逐字照办会把 GHSA-2883-xcg3-v3hh 审计得出的安全封顶当作总则宣称不存在的「停留理由」顺手摘除。已把「唯一例外」改为例外并列两条（ruff 硬钉 + js-yaml 封顶，原因各自沉淀在被钉文件头注释，解除上界须先确认传递链兼容并过渲染回归），CHANGELOG 同口径；按版本约束语法全仓复扫（overrides/resolutions/engines/packageManager/.nvmrc/pyproject）确认无第四种载体。教训：排他性总则的载体清点不能只按点名枚举（pre-commit rev、CI action）——枚举本身就是写死名单，要按版本约束语法全仓 grep 后再落笔，与四次评审「写死名单」同病灶的另一形态。十次评审（2026-09-27，外部评审实证复核）：① 七次评审①沉淀的钉版头注释写「最新版（0.16.7 实测）」，但 PyPI time 字段实测 0.16.8（2026-09-16）/0.16.9（2026-09-24，当日 latest）均先于注释落盘（d803cac，2026-09-27）——实测当天 0.16.7 已落后两个版本，「最新版」的主语与实测版本错位；§九 例外①以同口径指向该注释，读者会误以为当前最新版已验证过误报。已以 0.16.9 复测（`uv run --with ruff==0.16.9` 全量 lint：RUF100 仍误报 62 处，与 0.16.7 同数；0.14.5 全绿对照同步复现）后把注释改为「最新版（0.16.9 实测 62 处，2026-09-27；0.16.7 同数）」——钉版依据对真实最新版成立，措辞与事实对齐。教训：「最新版」这类随时间漂移的主语，落笔时须钉住「实测版本 + 当日是否确为最新」双要素（对 PyPI time 字段核一次当日 latest）；实测解析通道（uv 缓存等）可能给出落后于 registry 的版本——「实测到的版本号」≠「最新版本号」，两者错位时「最新版」主语即是事实错误，恰是六次评审②「快照类计数对一手源逐字核对」同标准的漏网形态。

## RSI-017 IndexTTS 长跑可把统一内存拉爆致系统卡顿：MPS 水位线缺位

**表因**：用户提出（2026-09-28）IndexTTS 合成会把 M4/24GB 统一内存吃满导致整机卡顿，问能否限制显存预防。既有同族症状：长跑数十分钟后合成全 500 而 `/health` 假绿（`tts_server.py` 「MPS 长跑泄漏对冲」注释实测 ~40 分钟击穿 30 GiB、VOICE-CLONING §七既有记录；RSI-002 曾把 empty_cache 移入 finally 对冲）。

**根因**：torch MPS 分配器默认高水位 `PYTORCH_MPS_HIGH_WATERMARK_RATIO=1.7` × recommendedMaxWorkingSetSize 17.76 GiB ≈ **30.2 GiB > 24 GB 物理统一内存**——分配器放行一切直到系统级换页/压缩才表现为整机卡顿，水位 OOM 来不及先触发（libtorch 二进制实串自证该机制存在：超水位报错尾句劝调该 env，见 ADVANCED §6.8 与本条四轮④）。上游 indextts 全仓无任何 MPS 内存限制（`set_per_process_memory_fraction` 0 命中；`torch.cuda.empty_cache()` 全仓 16 处——indextts/ 包 12 + backends/trt/export 4，`infer_v2_5.py` 占 2——在 MPS 上全是 no-op），low_vram 自动降载只查 `torch.cuda`（`infer_v2_5.py:125-129`，MPS 恒 False）。每句 empty_cache 只治累积**速率**不设天花板，且不防单次峰值（CFM 25 步 `sol.append(x)` 死存储 `flow_matching.py:110` + BigVGAN 整段上采样 `infer_v2_5.py:849` + beam3 fp32 KV ~1.2 GB）。

**定性**：部署形态机制缺口（缺资源护栏，长跑阻断级），非上游 bug。

**处理方式**：`tts_server.py` 服务端 `--mps-mem-limit-gib`（缺省策略 `min(0.90×recommended, 16)` GiB；0=禁用 high watermark、unlimited 并承担系统内存耗尽风险）在 lifespan 模型加载**之前**经 `torch.mps.set_per_process_memory_fraction` 设置进程水位线（模型加载本身即最大分配波）；`/health` 回显 `mps_mem_limit_gib`；水位线 OOM 捕获签名（`"MPS backend out of memory"`，torch 2.8.0 实测的 RuntimeError 文本）转可操作 500 detail（三出路；未设上限时改述实际状态，不劝「关闭已关」）；手册 VOICE-CLONING §2.3/§2.5（内存治理三层分工表）/§七（症状行）与 ADVANCED §6.8（机制循证）。选型：flag+setter 优于纯 env——同一底层旋钮，但 /health 可见 + 启动命令三副本零漂移。

评审回归（2026-09-28，外部评审九条全采纳，关键项均本机实测复核；二轮对抗审计又出七条、已并入）：① 缺省下限保底——0.9×recommended 在 16 GB 机型算得 ≈9.6 GiB、贴平 fp32 常驻（INDEXTTS-2.5-ADVANCED §6.5 的 10.00 GB 系 /1e9 十进制 ≈9.31 GiB），缺省额度跌破「常驻 + ~1 GiB」时自动不设限并打印原因；常驻口径含 --use-qwen-emo 的 +1.5 GiB（保底与告警线随之上移），显式传参不受保底约束、仅告警；② 低上限告警阈值 2→常驻口径（四轮③订正：此处原记「v2 fp16 减半、对其偏保守」系误读——缺省 --device auto 下上游 MPS 分支强制 fp32，v2 常驻与 v2.5 同量级）；③ `--device cpu` 不设不上报（原只看 mps.is_available()，CPU 部署 /health 误报非 null）；④ OOM 500 raise 前服务端补记全量栈；客户端**只对「MPS 显存上限不足」分支**（上限在场≈确定性）转 NonRetryableError 跳过 4 轮分钟级空跑——超限判定取 MTLDevice currentAllocatedSize 只计本进程分配（四轮①订正：此处原记「含其它进程占用（other allocations 项实证）」系误读），未设上限分支为本进程缓存累积/单次峰值触默认水位、保留重试；且「未设上限」remedy 删去「显式设上限」出路（更低的进程水位不会凭空多出内存，反让本进程更早触顶）；⑤ env 兜底须配 `PYTORCH_MPS_LOW_WATERMARK_RATIO`（单设 HIGH<1.4 首个 MPS 分配即抛 invalid low watermark ratio，venv 实测复现）；⑥ §6.8 调参建议 ~17.5 与 fraction≤0.98 互斥，订正为 ~17.4；⑦ 裸锚点 `:849` 写全 `infer_v2_5.py:849`（flow_matching.py 仅 186 行，就近绑定断链）；⑧ VOICE-CLONING §2.5 悬空 §6.5 引用补文件限定链接；⑨ 8767 归属勘误（是第二 tts_server 实例而非 tts_bench 直调）——二轮审计发现同错误还存于 07-tts-voice.md 与 VOICE-CLONING §2.5 pkill 注释两处载体，一并改正；§2.5 分工表「缺省即生效」与 §七「结构性兜住」两处恒真式表述补小机型例外限定。

三轮评审（2026-09-29）：① --help 与文件头 docstring 把缺省自动不设限阈值写死「~11 GiB」，未随 --use-qwen-emo 的常驻口径联动（`residency_gib + 1.0` 保底实为 ~12.5 GiB；两份手册因带「16 GB 级机型」限定不受影响，本台账一轮①已记录「保底随之上移」，唯独 CLI/文件头两处漏限定词）——已补「，--use-qwen-emo 时随常驻上移至 ~12.5」。同轮对抗验证否决一条候选（遗留单设 HIGH<1.4 env 下 `_apply_mps_limit` 的 fail-open 文案「继续以 torch 默认水位运行」与事实相反）：本机实证 setter 确在该 env 下自身抛 invalid low watermark ratio，但该 env 下无论有无本 diff、load_model 首个 MPS 分配都抛同一错误、服务同样必死（预存环境毒化，非本 diff 引入），且 env 配对规则已由一轮⑤裁决——不修。

四轮评审（2026-09-29，五维对抗评审 workflow：5 维度 finder + 每条发现 2 名独立验证者，候选 11 条确认 4 条独立问题）：① **一轮④「含其它进程占用（other allocations 项实证）」系机制误读**——torch 2.8.0 `MPSAllocator.h:330` 注释明写 currentAllocatedSize 统计 "total GPU memory allocated **in the process**"，`other allocations` 是本进程 MPS/MPSGraph 框架的隐式分配而非其它进程；本机双进程实测复核：外部进程持 1.5 GiB 时，本进程在 1 GiB 水位线下分配 0.8 GiB 照常成功、OOM 消息 other allocations 仅 464 KiB。已订正六处载体（tts_server docstring/except 注释/未设上限 remedy、tts.py `_deterministic_mps_oom` docstring、tts_sample ATTEMPTS 注释、CHANGELOG、本台账一轮④）：未设上限分支重试依据改述为「本进程缓存累积/单次峰值触默认水位（finally 归还缓存后重试可自愈）」，remedy 删「释放其它 GPU 进程」无效出路。② 确定性 OOM 的客户端最终报错丢句/块 id——NonRetryableError 在两个重试循环里原样透传、绕过 `{sid} 合成失败`/`块合成失败（{label}）` 包装（改动前 4 轮重试耗尽的报错带 sid），而 remedy 恰要求「拆短该句/块」；已改为 re-raise 前与重试耗尽分支同款包装。③ 常驻口径注释「v2 fp16 常驻减半」误读——缺省 `--device auto` 时上游 `infer_v2.py` MPS 分支强制 `use_fp16=False`（显式 mps 也仅 GPT `.half()` ~1.9 GB），两版本 fp32 常驻同量级，一轮②括注同步订正。④ ADVANCED §6.8 引文非逐字（漏 "for memory allocations"）且性质错置——该串是 "MPS backend out of memory (…)" 报错的尾句而非「内置警告字符串」，原表述「torch 全程不报 OOM」自相矛盾，改述为「水位 OOM 来不及先触发」（根因行同口径）。⑤ 新增 `tests/test_tts_mps_oom_contract.py`：AST 抽 tts_server 两个 remedy 首字面量（不 import fastapi/torch）钉住客户端 `_deterministic_mps_oom` 跨文件契约（「上限不足」必命中/「显存耗尽」必不命中正反控）+ mock urlopen 验证 `http_synthesize`/`http_synthesize_block` 的 NonRetryable/RuntimeError 分流。同轮对抗验证否决两条候选：CUDA 主机类型名兜底误报「MPS 显存耗尽」（本管线仅 macOS 部署、`--device` 无 cuda 选项，场景不可达且原始错误随 detail 透传）；residency 10.0 与手册 ~9.3 GiB 双口径（系一轮①明确裁决的 GB/GiB 呈现，非冲突）。**教训**：字段名 "other" 的语义不能望文生义——平台层计数口径要以「源码注释 + 受控实验」双证落笔（本条把误读标成「实证」写进台账，恰是六次评审②「快照类计数对一手源逐字核对」标准的漏网形态：注释原文就写在 venv 头文件里，却只读了报错消息）。

**后续防范**：平台分配器默认值不可默认信任为安全值（CUDA 默认也允许接近全部显存）——新增长跑型 GPU 服务（渲染、whisper、whisperX 等）上线前先查其内存上限语义并设进程级水位线；MPS 侧优先进程级 setter 而非全局 `iogpu.wired_limit_mb`（后者全局影响所有 Metal 应用，仅应急）。同 venv 无 flag 的 ad-hoc 脚本用 `PYTORCH_MPS_HIGH_WATERMARK_RATIO` env 兜底，**须配** `PYTORCH_MPS_LOW_WATERMARK_RATIO`（默认 low=1.4 > 所设 high 即初始化崩溃）。

**同类问题影响**：同 venv 的 `tts_bench.py` 等直调 infer 的脚本不受本 flag 保护（单进程各自设限），已在 §2.5 注记 env 兜底；webui.py 同理（本管线不用）。8767 上的 A/B 实例是第二个 `tts_server.py`，拉起即应用缺省上限。上限按进程计，多实例并行时总量仍需人工控制。

五轮评审（2026-09-29）：① CPU/CUDA `OutOfMemoryError` 类型兜底仅在实际 `mps` device 下启用，避免非 MPS 部署收到错误的显存排障指引；② 显式 `--mps-mem-limit-gib 0` 在 allocator 初始化前覆盖继承的 `PYTORCH_MPS_HIGH_WATERMARK_RATIO`，并调用 `set_per_process_memory_fraction(0.0)`，保证「不限」不随 shell 环境漂移；③ 只有解析到 `MPS allocated + other allocations + Tried to allocate > max allowed` 才进入不可重试的「MPS 显存上限不足」契约，普通 MPS OOM、系统内存压力、碎片化与解析不完整均保留重试；④ 解析器兼容 PyTorch 的 `MiB/GiB` 及十进制单位，新增 helper、环境覆盖与客户端分流测试，相关测试与全量回归通过。

## RSI-018 archify 建图产物三重静默缺陷，录制前置校验缺位

**表因**：上游五集系列重制（[negentropy ISSUE-201](https://github.com/ThreeFish-AI/negentropy/blob/master/docs/.agents/issue.md)，2026-10-02）四起同类：①ep4 两图建图产物缺 guided-views 嵌入——全局 archify CLI 3.0.0 删除了该模块，用全局 CLI 的产物天然无嵌入，录制空转不报错；②ep2 三图漏 `claude-code--` 前缀（html_pattern 失配，dry-run 有报但在建图完成数小时后）；③ep1 四图漏 sidecar type（图型多样性门晚期才红）；④两图 sidecar type=state 被录制器 argparse choices 拒绝、退出码 2——archify 出图词汇含 state 而录制器词表不含，规格与录制器词表不一致是机制内矛盾。

**根因**：`record_archify_all.py` 的 `--dry-run` 只校验「views/ slug → HTML 文件存在」映射，不校验 HTML 内 guided-views 数据非空、不校验 sidecar type 合法性——三重缺陷全部拖到录制中段（或更晚的覆盖门）才暴露，而录制是整链路最贵的一步。

**定性**：阻断级缺陷（建图完成数小时后的录制批次中途失败/静默空转）。

**方案比选**：预检落位三选——A 只挂 `--dry-run` 分支（工单字面形态）：漏跑 dry-run 的真录批次仍在中段撞墙，等于留后门；B 检查下沉到录制器 `record_archify.py`：空 views 已有开浏览器前 FAIL、type 词表已有 argparse 执法，缺的是**批次级前置门 + 映射指路**，且 dry-run 不经录制器；**C 扩既有「映射 + 源图存在性」预检循环（采纳）**——dry-run 与真录共用同一段（本脚本既有 doctrine「全部先验完再开录」），零新代码路径。词表事实源二选：驱动内镜像 + AST 一致性测试（tts.py 镜像表先例）vs **提升为 `record_archify.DIAGRAM_TYPES` 模块常量、驱动 import（采纳）**——零漂移由构造保证，3 行改动（触碰 record_archify.py，白名单扩圈一处，理由即此）。guided-views 判空复用录制器 `read_views`（同一提取器——预检与录制对「什么算空」永不各说各话，不写第二份判据）。

**处理方式**：分支 `ThreeFish-AI/rsi-018-record-preflight`，[PR #23](https://github.com/ThreeFish-AI/to-video/pull/23)（合并前主代理评审后回填）。①`record_archify.py` 图型词表提升为 `DIAGRAM_TYPES`（argparse choices 同源引用）；②`record_archify_all.py` 预检循环扩两查：HTML 缺/空 `archify-guided-views-data` 容器 → FAIL（提示「产物可能出自删除该模块的 archify 版本（全局 CLI 3.0.0 起无 guided-views）」）；sidecar type 越表 → FAIL（报全词表 + state→lifecycle 映射 + sidecar 顶层改写位置）；③references/06 archify 资产标注规范补词表脚注（工单所指「图型预算表」在现行 06 不存在，最小落位 = 标注规范纪律列表）。回归测试 5 条（CLI 级，钉门语义而非纯函数）：无容器 / 空容器 / type=state → exit 1 且指路文案在场；真录（不带 --dry-run）同样在起浏览器前被拦；健康现场 → exit 0「预演 1」——前四条在修复前形态下全红（红绿对拍实测）。

**后续防范**：录制链新增静默缺陷形态时先进 dry-run 预检、再谈运行期兜底；跨工具词表（archify 出图词汇 vs 录制器 `--type` 词表）以消费端 choices 为 SSOT，规格只写映射不复制词表；前置校验与运行期校验共用同一提取器/常量，不写第二份判据。

**同类问题影响**：`check_archify_coverage.py` 的图型多样性门按 sidecar type 去重计数、不验词表——越表值（如 state 与 lifecycle 并存）会虚增图型数；预检把越表拦在建图侧后该路径不可达。所有用全局 archify CLI 新建的图都带①的风险，预检 FAIL 即「须用仍含 guided-views 的版本重新出图」的信号。

合并前评审留白（2026-09-29）：canonical 门命令（pyproject.toml 头注释 SSOT）缺 `--with playwright`——本条 5 条预检回归测试随整个 test_record_archify_all 被 `importorskip` 在门跑中静默跳过（本轮回填证据：playwright 变体实跑 813 passed / 19 skipped，含该文件全部 11 条）；把 `--with playwright` 纳入 SSOT 命令登记为待办。

## RSI-019 @remotion/lottie 在 headless ANGLE 渲染确定性挂死，边界无文档

**表因**：上游 [negentropy ISSUE-202](https://github.com/ThreeFish-AI/negentropy/blob/master/docs/.agents/issue.md)（2026-10-02）：ep4 草渲五连崩（Target closed / 静默死，崩点漂移 10170/13727/1199/3339 + swap 耗尽 38GB 表象），ep5 同款两崩。

**根因**：`LottieEmphasis`（fetch + delayRender + @remotion/lottie）在 chrome-headless-shell + ANGLE 后端下对**特定 JSON** 初始化挂死，`Waiting for Lottie animation to load` 的 delayRender 永不解除；结构等价的另一 JSON 同环境可用（plug-pulse 实测）——按资产触发、非全量失效。本仓侧缺陷：该渲染确定性边界无任何文档，新 Lottie 资产入片没有冒烟关口；排障侧也没有「随机崩 vs 确定性崩点」的分诊方法论（上游三试浪费：降并发 / 换机器 / 清缓存后才定位）。

**定性**：非阻断改进（纯文档；机制不变——处置仍是换实现，文档把关口前移到入片前）。

**处理方式**：分支同 RSI-018，[PR #23](https://github.com/ThreeFish-AI/to-video/pull/23)。references/08 事实条新增「Lottie 资产渲染边界」：新 Lottie 资产入片前必须先过 100 帧段渲冒烟（`./node_modules/.bin/remotion render Main /tmp/smoke.mp4 --frames=<起点>-<起点+100> --concurrency=1`，起点取该资产出场帧位），挂死即弃用该 JSON、换原生 SVG / 运动层实现（上游以原生组件替换实证）；references/09 修复回路新增「渲染崩溃分诊」：崩点漂移 + 系统内存压力表象时先按确定性崩点处理——分段 100 帧窗渲染定位 + 禁用法二分（同段全过即定位到组件），勿先降并发 / 换机器 / 清缓存。测试面由既有 test_docs_paths（链接可达 / 命令锚定 / 围栏平衡）覆盖，无新增机制代码。

**后续防范**：新资产类型入片先问「它在 headless 渲染后端下有已知确定性边界吗」，有则先冒烟；崩溃排障先分诊「随机 vs 确定」再动手——漂移 + 资源压力的表象会掩盖确定性崩点。

**同类问题影响**：「fetch + delayRender」形态的资产加载组件在此环境均有同款潜在风险，冒烟纪律不限于 Lottie。
## RSI-020 场景渲染内容为空无门可拦：108 秒纯黑+字幕段靠人工事故后发现

**表因**：五集系列重制 ep4（上游 negentropy 分支 ThreeFish-AI/learn-claude-code-5-episode-revamp，ep4 交付 commit `a783411f2`；上游台账 https://github.com/ThreeFish-AI/negentropy/blob/master/docs/.agents/issue.md ），场景分片并行代理在文件头声称「另一半场由另一文件承担」但该文件不存在——`check_script --check-scenes` 查句覆盖与场景互比，不查场景渲染内容是否为空；成片草渲后 52.8s/55.5s 两段仅字幕无画面，集成期人工发现。`qa_frames --check` 判据族（黑帧/重复帧/安全区/字幕带）无「连续纯底色段」：帧均值被字幕带抬高（事故帧 ≈0.106 > 黑帧阈值 0.02，黑帧门放行），相邻采样帧字幕文本不同、16×16 指纹也不同（冻帧门放行）。

**根因**：`--check` 的判据都是**帧内**判据，无跨帧时序判据（「连续 N 秒画面区近黑但字幕带在场」）；「画面有没有内容」从未进入自动体检判据族，只能靠人工全片目检兜底。

**定性**：阻断级缺陷（门形同虚设：分钟级空段绿着门进终渲）。

**方案比选**：判据落位三案——A **并入 qa_frames --check 作跨帧时序门（采纳）**：与既有判据族同址、草渲后随既有命令自动执法；B 独立扫描脚本（ffmpeg 全片亮度带采样）——第二工具面、与抽帧 QA 分叉，违反最小干预；C 只升格文档步骤（人工扫描）——上游已实证人工兜底会漏（集成期才发现），门不承载等于没升格。「有内容」信号比选：整帧均值（被字幕带抬高，事故形态下恒过黑帧门——无效）；内容区均值（底色 0.065 与 panel 0.108 分离度不足）；**内容区亮像素占比（采纳）**——平底+JPEG 噪声 <0.09、设计系统最弱结构元素 panelBorder 0.194，阈值 0.15 居中零贴边（ISSUE-167：亮度阈值须在已知干净帧零报警）。片尾渐黑区分取**末幕豁免（只检 N-1 幕）**而非渐黑感知窗：无新自由度，末幕纯黑已由黑帧门+渐黑豁免覆盖，8s 时长阈值本身也天然区分 <2s 的渐变与数十秒的空段。run 不跨幕：幕间 SceneFade 淡出尾会让两侧帧短暂近底色，跨幕累计会把合法转场拼成假空段。阈值 `qa.max_dark_sec` 住 SCHEMA（默认 8s，toml 可覆写，0=关闭——逃逸口须存在且可声明）。

**处理方式**：`qa_frames.py --check` 新增纯底色段门——`check_frames` 增 `timeline`/`max_dark_sec` 参数，逐帧算**画面内容区**（顶部安全带 y<56 之下、字幕带之上；几何 SSOT 来自 ChapterProgress 零碰撞带契约「各幕内容 y≥56 起」）亮像素占比 <5e-4 判「无内容」，同幕连续无内容帧按「首帧中点−半句距 .. 末帧中点+半句距」计持续时长，≥ `qa.max_dark_sec` → FAIL；末幕按**全集时间轴**最后一幕豁免；`--beat-heads` 头帧不在时间轴里、判据自然不参与（头帧落在淡入瞬态，近底色是合法态）。config SCHEMA 新键 `qa.max_dark_sec`（默认 8.0、负值 FAIL、0=关闭）。[09](../../references/09-render-qa.md) 把「草渲后全片亮度带扫描」从经验散条升格为 ⑨ 必做步骤（`--scene` 全幕传齐 + `--check`，每幕 ~8 帧 ≈5–7s 采样形态，门按持续时长在样点间内插）+ 判据表新行 + FAIL 0 边界句与修复回路同步；[PIPELINE.md](../../references/PIPELINE.md) 字段表/工具表登记。回归测试 4 组（整幕空段 FAIL／干净帧零报警含末幕豁免与亚阈值暗段／阈值可配与关门／run 不跨幕）。实施：[PR #24](https://github.com/ThreeFish-AI/to-video/pull/24)。

合并前评审加固（2026-09-29）：①`--check` 消费 config 不再丢弃 validate FAIL——带病 `[qa]`（类型错→阈值比较处裸 traceback、负值→借「0=关闭」分支无声关门假绿）改为点名 FAIL 拒跑；独立直调本命令正是 09 ⑨ 必做路径，不能赌 pipeline.py check 先跑过全量 validate（回归测试 2 条：字符串/负值对拍）。②09 FAIL 0 边界句的体检清单与 PIPELINE.md 工具表/模块 docstring 同构化（补「字幕缺失」、对比度归位 `--check-theme`——原句继承 main 旧口径漏 WARN 级「字幕缺失」而混入对比度）。③RSI-021 回归测试计数订正（4 函数 5 断言面，见下）。

**后续防范**：自动体检新增判据先问「它是帧内性质还是跨帧性质」——时长/连续性类缺陷（空段、卡死、整段丢字幕）单帧判据结构性失明；场景分片并行代理的交付面须含「本文件实际渲染哪些 beat」的机器可核声明（`--check-scenes` 只对账分镜↔代码句覆盖，文件级互相推诿它看不见）；草渲后全片内容带扫描未跑不得进终渲（09 ⑨ 必做项）。

**同类问题影响**：门只认句中点采样形态（`--beat-heads` 不查）；未来若有合法的 >8s 纯底色艺术段，本集 toml 覆写 `qa.max_dark_sec` 并在分镜留决策记录。

## RSI-021 chars_per_min 默认值不区分 tts.style，story 档首轮必超窗返工

**表因**：五集系列 ep1（上游同分支，ep1 交付 commit `6f58fac2e`）首轮按默认 280 字/分写 3961 字 → TTS 实测外推 15.62 分超 [13.0, 14.6] 硬窗 → 回 ③ 减脂 317 字 → story 档块缓存整失效全量重合成（~40 分钟浪费）；后续四集按实测 254 直写全部一次过窗零返工（ep2–ep5 的 pipeline.toml 已显式 `chars_per_min = 254`——内容侧自发的手工 workaround，正是 B 案的存量形态）。

**根因**：`config.py` chars_per_min 默认 280 是 sunny 档（逐句）含停顿等效口径；story 档（块级情绪演绎）实测纯语音 274 字/分、含停顿等效 254——档位间语速差未被机制感知，每集靠人把教训抄进 toml。

**定性**：非阻断改进（有手工 workaround，但每个新系列首轮必复发一次「超窗 → 减脂 → 块缓存全量重合成」返工）。

**方案比选**：A **SCHEMA 分档默认（采纳）**——`resolve()` 在默认层按 tts.style 分档（story=254、其余=280，档位表 `STYLE_CHARS_PER_MIN` 紧邻 SCHEMA），显式 toml 覆写恒优先；check_script / build_narration 的既有读取路径零改动即生效（scope 加载同样过 resolve）。B 只在 07 文档教「story 集手写 254」——每集手工重复、漏写即复发。C 消费者按 style 分支——两处内联档位逻辑即第二事实源，违反不变量 7 与 `test_consumers_do_not_inline_schema_defaults` 的执法精神。分档默认住 SCHEMA 侧，不变量 7（默认值唯一来源）合规。

**处理方式**：`config.py`：SCHEMA 的 narration.chars_per_min 注明分档 + `STYLE_CHARS_PER_MIN = {"story": 254}`（注释写明仅 story 有整集实测、新档位首轮 TTS 后以 manifest 实测回写）；`resolve()` 尾部对「默认层 chars_per_min + tts.style 命中档位表」生效分档（origin 保持 default；显式 toml 优先；非字符串 style 不崩——类型执法归 validate）。[07](../../references/07-tts-voice.md) 完成门新增「首轮 TTS 完成后校准本集语速」操作指引（manifest 实测分钟复算，偏差 >3% 写本集 toml）；[PIPELINE.md](../../references/PIPELINE.md) 字段表同步。回归测试 4 函数 5 断言面（story→254／sunny→280 并把分档表与基础默认钉在 SCHEMA、toml 覆写优先、toml 端到端、非字符串 style 不崩）。实施：[PR #24](https://github.com/ThreeFish-AI/to-video/pull/24)。

**后续防范**：STYLE_PRESETS 新增风格档时，检查所有「按档位变化的口径常数」（语速/停顿/种子）是否需入 `STYLE_CHARS_PER_MIN` 一类分档表——首轮后以 manifest 实测回写，不拿单集标定当普适；预算门超窗先查生效 chars_per_min 的来源（doctor 打印 default/pipeline.toml 分层），再回 ③ 减脂。

**同类问题影响**：en 版走 words_per_min（词/分）不受本分档影响（首集英文实测后按 07 完成门同模式校准）；14 个存量 sunny-steady 集默认值不变（280），零波及；已显式写 254 的 story 集（上游五集）走 toml 覆写路径，行为不变。
## RSI-022 TTS 长跑自愈缺官方载体：服务掉线/客户端依赖缺失/退出码误读三坑无脚本兜底

**表因（上游实证）**：五集系列 TTS 长跑（每集 149-170 句）反复遇到：①IndexTTS 服务掉线或 MPS 挂死（需按端口冷重启 + `PYTORCH_MPS_HIGH_WATERMARK_RATIO` 参数，与本仓 RSI-017 同族——长跑显存击穿后合成全 500 而 `/health` 假绿、自愈循环须含「连续失败→按端口重启服务」）；②客户端 mutagen 依赖缺失在**首句合成成功后**才崩（uv --no-project 裸调形态：tts.py 的 mutagen 是惰性 import，只在写完 mp3 测时长时才 ModuleNotFoundError）；③自制自愈脚本踩 `cmd | tail; $?` 陷阱（取的是 tail 退出码 → 失败检测恒失效）。上游已验证一套 .sh 形态自愈循环（连续失败→按端口冷重启服务→客户端续跑，五集全部跑通），但只存在于用户内容仓的未跟踪文件（`negentropy 工作区 .context/tts-run/resume.sh`，未入 git 无 URL，已原文核对：`kill $(lsof -tnP -iTCP:8766 -sTCP:LISTEN)` + `PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0` nohup 拉起 + 子 shell 取 rc + 60×5s 健康轮询 grep `'"ok": *true'`），未回流机制仓。工单草稿曾引「上游 ISSUE-202」为同族——核对为 remotion lottie headless 挂死条目、非 TTS 族，此引用不成立已弃（同族依据改为 RSI-017 与上游脚本原文）。

**根因**：`scripts/tts.py` 只管单轮合成；服务生命周期管理与长跑续跑编排无官方载体；`pipeline.py` doctor 不预检客户端依赖。

**定性**：非阻断改进（上游有 .sh 兜底、五集已跑通；但每次新长跑都要重搓 shell——正是陷阱③的来源，且该 .sh 未入版本控制、一次 clean 即失传）。

**方案比选**：A 原样回流 .sh——零改动已验证，但 shell 里退出码/健康检查靠 curl+grep 且无法做状态机单测（G3 缺载体），`$?` 类陷阱是类型系统级缺陷；B 新增 `scripts/tts_resume.py`（**采纳**，纯标准库对齐不变量 14）——`subprocess.run(...).returncode` 结构性消除管道尾食、urllib 健康检查、状态机可单测；对 .sh 的两处刻意微调：首轮健康即不重启（省 1–2 分钟冷启动；失败后仍无条件重启，覆盖 /health 假绿）、放弃上限缺省 3 轮（工单口径，`--max-restarts` 可调回上游实证的 12）；C 并入 tts.py（--resume flag）——超出白名单，且把服务编排塞进单轮合成器、破坏其「可拷进 index-tts venv 单独运行」的导入边界（test_tts_lang_mirror 钉死）；D 只改 doctor+文档记录 .sh 形态——不解决载体缺位。启动命令不另立第二事实源：从 `tts.server_launch_hint` 同构派生并由回归测试钉住 `--with` 集合（hint 仍是人贴终端的 SSOT）。doctor 预检形态：⚠️ 不计失败（对齐「服务离线不计失败」先例——doctor 规范调用本就不带 `--with`，计入失败会让正常态恒红）；**硬门禁放 tts_resume 入口**（它以 sys.executable 跑 tts.py，同解释器依赖在场是硬前提——这才是结构性堵住「首句合成后才崩」的位置）。MPS env 兜底执行 RSI-017 配对纪律：单设正 high 必配 low（默认 low=1.4，high<1.4 首个 MPS 分配即崩），0.0（禁用水位线）为唯一免配对特例。

**处理方式**：新增 `scripts/tts_resume.py`（健康检查 `ok` 判据同上游 .sh → 不健康或客户端失败后按端口冷重启——SIGTERM→等待→SIGKILL，只杀该端口 LISTEN、绝不 `pkill -f`（07「服务生命周期」第 2 步判据面=作用面纪律）→ `subprocess.run` 真实退出码续跑 tts.py（`--` 后参数原样转发，幂等缓存断点续）→ 超上限非零退出；入口门禁 `--engine=indextts` 与 mutagen 在场；服务命令/根/日志/MPS env 全参数化）；`pipeline.py` doctor 的 indextts 节加 mutagen 预检（⚠️ + `--with mutagen` 可操作提示）；[references/PIPELINE.md](../../references/PIPELINE.md) §三脚本表登记（用法定义 SSOT）与 [references/07-tts-voice.md](../../references/07-tts-voice.md) 调用形态指针行；回归测试 [tests/test_tts_resume.py](../../tests/test_tts_resume.py)：退出码管道尾食负例文档化（`/bin/sh` 实测 `(exit 7) | cat; echo $?` → 0）、重启计数状态机（瞬时失败两轮后成功/达上限放弃/首轮不健康先重启/冷启动超时 exit 3）、健康检查 payload 与传输异常分支、启动命令对 hint 的 `--with` 防漂移、MPS 配对、端口纪律（无 pkill、SIGTERM→SIGKILL）、doctor 预检两分支（缺失 ⚠️ 不计失败 / 在场静默）。实施：[PR #25](https://github.com/ThreeFish-AI/to-video/pull/25)。

合并前评审加固（2026-09-29，四条全过对抗验证）：①`server_healthy` 捕获面补 `http.client.HTTPException` 族——BadStatusLine/IncompleteRead 的 MRO 不经 URLError/OSError/ValueError（实测穿透），端口被非 HTTP 进程占用（--server 指错/残留垃圾服务）曾使自愈编排器裸 traceback 崩溃、恰在其职责域内丧失自愈；②`main()` 入口校验 index-tts checkout 存在（缺失时 Popen 在**服务掉线后**才裸炸——靶场景遇配置错误须入口大声退出），`start_server` 再兜一层 FileNotFoundError（覆盖 uv 不在 PATH）；③`mps_env` 拒 nan/-inf/负数（比较恒 False 溜过 `> 0` 配对分支，注入后 torch 崩出不可读错误）；④mock 状态机测试显式 `--index-tts-root` 指向 tmp（消除对本机 `~/tools/index-tts` 真伪的机器依赖）。回归测试 +4 用例（HTTPException×2 参数例、根缺失入口拦、Popen 兜底）+ mps 非有限/负数 3 断言扩入既有用例。

**后续防范**：①长跑编排类脚本禁止 `cmd | tail` 后取 `$?`——一律 `subprocess.run` 直取 returncode（shell 管道退出码陷阱在 Python 侧结构性不可达）；②杀服务按端口不按 argv 模式（判据面=作用面）；③客户端依赖预检要在**编排入口**做（同解释器前提），诊断命令里的预检只报不计失败；④MPS 水位线 env 单设正 high 必配 low（RSI-017）；⑤用户侧验证过的运维脚本须回流机制仓——留在内容仓未跟踪路径等于零版本控制；⑥urllib 的 `except (URLError, OSError)` 窄口径对「读响应体」路径漏 HTTPException 族——凡健康探测类代码须把 `http.client.HTTPException` 计入按不健康处理的异常面。

**同类问题影响**：上游五集长跑的 .sh 可由本脚本替代（`.context/tts-run/resume.sh` 可退役）；edge 引擎无服务端不适用；tts_bench/tts_sample 短调用仍走 tts.py 自动打印的启动命令（server_launch_hint SSOT 不变）。
## RSI-023 覆盖门只认单参 dur 拼写，FAIL 文案未给合规扩窗改法——空窗回填用了门读不到的写法且登记口径失效

**表因**：上游内容仓 E2 第 4 轮评审（2026-09-29）发现：空窗回填提交把 6 处 cue 时长写成双参 `durationInFrames: dur('a','b')`（P1Hangar×3/P5Tarmac×3），`CUE_DUR_RE` 只识别单参对象字面量形态——门一跑即 SystemExit，且该提交未重跑门，series.json/CHANGELOG 里「覆盖门 FAIL 0」的登记口径就此失效（门炸与登记绿并存）。

**根因**：机制层两面——① 双参形态与「求和形态 `dur('a') + dur('b')`（帧数等价、正则可命中首段并与 at 锚对账）」语义完全等价，写法差异纯靠记忆约定；② FAIL 文案只解释了双参为何禁止（与邻句 cue 重叠）并指示「一章锚一句」，未给已定实践（空窗回填求和扩窗，多集在用）的可复制合法拼写——对照 at 分支文案给了具体拼写，dur 分支没有。

**定性**：非阻断文档缺陷（门本身判对了，是文案引导缺位 + 上游流程未重跑门；后者属内容仓纪律不进本台账）。

**处理方式**：`check_archify_coverage.py` FAIL 文案补「确需跨句扩窗（空窗回填）改拼写为 `dur('a') + dur('b')` 求和形态（帧数等价、本门可识别对账，首段句 id 须与 at 锚一致）」；`tests/test_check_archify_coverage.py` 补正反控：求和形态可被识别计数、双参形态触发本 FAIL（若既有测试已覆盖则只钉文案片段）。实施：[PR #26](https://github.com/ThreeFish-AI/to-video/pull/26)。

**后续防范**：扩窗一律求和拼写；改 cue 拼写后必须重跑 `check --check-scenes` 再回写登记口径（登记数字是门的输出快照，不是手填常数）。已知留白：求和形态第二段及以后的句 id 不在门的存在性/重叠审计内（正则只取首段对账 at 锚）——文案已限定「空窗回填」用途（被跨句按定义无邻句 cue），越界使用须自查。

**同类问题影响**：Sequence 级 JSX 等号形态（`durationInFrames={dur('a','b')}`）不在此门管辖（正则只查对象字面量冒号形态），该形态合法勿误改。

## RSI-024 zh 字幕单行宽度无门：超限句横向溢出画布只靠稿风纪律

**表因**：上游内容仓两起实测——E3 曾 81 字散文句在 30px 最小字号下两侧各溢出 1920 画布 ~255px；E2 重制评审（2026-09-29）确认构造仍在（当时最长 39 字不触发，复活门槛 ≈51 全角字）。

**根因**：frozen 模板 `Subtitle.tsx` 对 zh 恒单行（`twoLine = !isZh && fitted < MIN_FONT_SIZE`——两行回退仅 en）、字号下限钳 30px、`nowrap` 不折行——「不溢出」⇔ 全角当量 ≤ floor(1528/30) = 50，但该物理上限只存在于渲染层，build/check 期无门；「超宽句压短」的稿风纪律不执法。zh 组件层加两行回退属 frozen 整组同步（见 RSI-028），门是独立于模板的最小干预。

**定性**：阻断性缺陷缺门（缺陷复活门槛低：一次成文放宽即触发，且 qa 帧级检查对字幕盒内文字溢出不敏感）。

**处理方式**：`check_script.py` 新增 `check_subtitle_width`（zh-only，挂 `--pre-tts` 与 zh 完整门两路；en 有两行回退不适用）：全角当量（宽/全角字符 1.0、半角 ~0.55，即模板注释记载的历史估宽口径；比较前 round(·,2) 消半角浮点累积噪声）> 50 即 FAIL，附句 id 与当量值；常量推导链注释钉住渲染侧 SSOT 归属（骨架指纹把守漂移）。**代际感知**：单行前提是当前模板的 `twoLine = !isZh && …` 守卫——旧代 Subtitle（cacb/7faa 指纹代）zh 可折行，门对其点名跳过不误报（拷齐当前模板自动生效）。`tests/test_check_script.py` 正反控五条（51 全角 FAIL / 恰 50 过 / 混排超限 FAIL / --pre-tts 路径 / 旧代跳过）。实施：[PR #26](https://github.com/ThreeFish-AI/to-video/pull/26)。

15 集实测校准（2026-09-29）：25cf 代抓到 2 集 4 句**真溢出**（agent-skills p3-08a=51.1；jev p4-19=54.1/p5-29=57.3/p6-27=50.1——已上线集的真实存量，内容侧待修）；cacb 代 skills-supply-chain 27 句（50.0-80.1）与 7faa 代 openviking 2 句为旧代折行非溢出，跳过后零误报。

**后续防范**：字幕物理类上限钉进门里不钉在稿风里；新增句级门须同时想清 zh/en 归属并在两条分发路径挂载（漏挂即静默缺门）。

## RSI-025 台本 [say] 与正文逐字相同时零告警：no-op 表演标点静默攒批

**表因**：上游 E2 重制（2026-09-29 清理）实测 cues.toml 攒了 8 条 `[say]` 与句原文逐字相同——三处逐字一致（say == text == ttsText），纯假动作；build 只在 say 与正文**改字**时报 FAIL，零改动无任何提示。

**根因**：`apply_cues` 的校验只拦「不一致」（改字/标注漂移），「完全一致」是合法边界但零效果——写的人以为做了句读表演，实际送合成的 ttsText 与不写该条完全一样。

**定性**：非阻断改进（合法但 noisy，攒批只会让台本看起来做了没做的事）。

**处理方式**：`build_narration.py` `apply_cues` 增可选 out-param `warnings`（say == src 逐字相同即记，附「改出真句读或删除该条」出路；不传则丢弃——只影响提醒不影响校验），三元组返回契约不变（既有 14 处调用点零波及：build_narration 生产 1 + 既有测试 13），main 仿 `mark_warnings` 先例输出（`WARN  ` 前缀、stderr）；无 cues 文件零输出契约不变。`tests/test_tts_blocks.py` 正反控（no-op 报 WARN / 真句读不报 / 旧调用面三元组契约回归）。实施：[PR #26](https://github.com/ThreeFish-AI/to-video/pull/26)。

**后续防范**：表演层输入的「零效果边界」与「非法边界」都要有声音——只拦非法会把「写了等于没写」留成静默债。

## RSI-026 选色判据缺「色相距离」维度与未登记色盲区：撞值门全绿仍可同色相撞车

**表因**：上游 E2 流光五色选色（2026-09-29）初选玫红 #E85D75（350°，colorsys 口径），与同系列既有 E3 玫红 #FF6F91（346°）色相仅差 4°——`check_series` 规则 4 只拦精确同值，门全绿、视觉同色相；两次改向后落品红 #D65DB1（318°，全系列空槽；最近占用 E1 紫 #C9A0FF 266° 差 52°）。另发现材料色数组 token（`sourceFlows`）不进 series.json `accents` 清单，机器完全不看见。

**根因**：规则 4 明文「不做色相邻近 WARN」是校准过的决策（ISSUE-167：蓝 #4A9EFF 与青 #2DD4BF 相邻共存是接受态，假报一多门被关掉）——但「机器不判」被读成了「无需人核」，色相错开这一半契约没有承接面；且 occupied 清单数据源只认 accents 声明，未登记色的盲区无人知晓。

**定性**：非阻断改进（不改门——推翻已校准决策需判据级新证据；补人工判据承接面）。

**处理方式**：`references/08-remotion-implementation.md` 色彩契约增第 6 条：新选色对着 INFO 行人工核色相距离（附 6° 撞车实例与换槽解法）；未登记进 accents 的色（材料色数组 token）在 theme.ts 注释自证色相距离、必要时临时并进 accents 比对。check_series 零改动。实施：[PR #26](https://github.com/ThreeFish-AI/to-video/pull/26)。

**后续防范**：「机器不判」的判据必须写明人工承接面在哪，否则契约只有被执法的那一半活着。

## RSI-027 派生产物确定性无门：提交的 narration.json 可相对钉定生成器陈旧

**表因**：上游 E2 第 4 轮（2026-09-29）rebuild 发现提交版 narration.json 与当前生成器输出不一致——生成器在 RSI-015 起派生 `beatStart` 键，提交版是旧生成器产物（0 个 beatStart vs 新 31 个）；无任何门报告这一漂移，语义对账（ids/text/scene/blockStart/cue 五维全等）只能靠人手写脚本。

**根因**：narration.json 是「源（narration.md + cues.toml）× 生成器版本」的二元派生物，生成器演进出新键时存量 json 陈旧但合法可渲染——缺一个「提交的派生物 == 当前生成器重跑结果」的确定性门（类似 lockfile 校验）。

**定性**：非阻断缺门（登记待办；实现面在 `check` 里加 rebuild-diff 子检查，涉及临时输出与耗时预算，攒 RSI 批次后统一定方案）。

**处理方式**：登记待办。落地形状候选：`pipeline.py check` 附 `--determinism`——build_narration 重跑到临时目录与在库 json 做规范化 diff（键序/新增键白名单化），漂移即 FAIL 并提示重跑 build。

**后续防范**：凡「源×生成器」型派生物进 git，都应有确定性门；生成器新增输出键的 RSI（如 RSI-015 之于 beatStart）须在 PR 里点名「存量集 json 将报陈旧，重跑 build 自适配」。

**同类问题影响**：chapters.json/series-layers.json 等同型派生物。

## RSI-028 冻结件整组同步积压六项：单改一集即破 skeleton 字节契约

**表因**：上游 E2 第 4 轮评审（2026-09-29）判「明确不动」清单六项——frozen `Subtitle.tsx` 的 zh 两行回退与 scrim 色值 `rgba(6,8,12,0.68)`（四集共享规范值）、`ArchifyClip.tsx` 内衬色 `#0B0E13` 与注释里指向集内 `scripts/` 的悬空路径、`ArchifyRecap.tsx` 手抄匿名类型断言（应引用导出的 `ArchifyChapter`）、`ArchifyYield.tsx` 零挂载死件、`i18n.tsx` `useL`/`L` 零消费导出（四集字节一致）、`build_narration.py` 侧 zh 句长防线（episode 薄包装受 frozen 字节执法）。

**根因**：这些件的修复面在模板层，但模板改动 = 全集 md5 漂移 + 既有集 generation/drift 登记义务（CHANGELOG Breaking 节的既有口径），单集顺手改即破契约——正确做法是「改模板 + 集中同步批次」。

**定性**：非阻断积压（登记待批；六项均已在上游内容仓经 md5 跨集指纹实证为共享件）。

**处理方式**：登记待办。建议攒一个集中 generation 批次：模板侧六项一次改齐（Subtitle zh 两行回退落地后 RSI-024 的代际守卫消失、门自动退位点名跳过——双保险仅在过渡期成立；scrim/内衬色走 theme 派生；ArchifyYield 删或给活例；类型断言改引用；i18n 死导出删；薄包装注释限定 skill 路径），同步 CHANGELOG Breaking 自适配指引与各集 `[[skeleton.generation]]` 登记。

**后续防范**：跨集共享件的缺陷一律先 md5 抽跨集指纹定性再动手；「本集不修」必须像本条一样落到台账而不是只留在当轮 commit message 里。

## RSI-029 草渲半分辨率下「帧指纹相同」WARN 可假阳：冻帧误报无像素级复核通道

**表因**：上游 E2 v2 草渲 QA（2026-09-29）四条「帧指纹相同（疑似冻帧）」WARN（p1-21b/p1-24、p3-10/p3-11c、p4-01/p4-04、p6-26/p6-27），像素级对账全部证伪——变更像素 3.5–7.7%、diff bbox 非空，是 `--scale 0.5 --jpeg-quality 60` 草渲下指纹分辨率不足的假阳。

**根因**：草渲指纹在小面积/低对比变化上会碰撞（同族既有 ISSUE-181 索引损坏伪冻帧、ISSUE-167 侵入假报，此为第三种假阳形态：分辨率致假阳）；WARN 文案没有给「如何一票证伪」的指引，复核靠人自造脚本。

**定性**：非阻断改进（登记待办）。

**处理方式**：登记待办。候选：WARN 文案附一行像素级对账指引（PIL ImageChops.difference + 变更像素占比，本地秒级）；或指纹改在原分辨率灰度图上取（成本权衡待定）。

**后续防范**：数值/指纹类 WARN 上线时想好「假阳时如何一票证伪」并把证伪命令写进文案——不能复核的告警等于噪声。

合并前评审（2026-09-29）：①编号与并行创建的 RSI-018..022（PR #23/#24/#25，首创在前）撞号，本批七条目整体重编号 018..024 → 023..029（条目内互引同步：024 宽度门 ↔ 028 冻结件）；②文档漂移修复——check_script.py 模块头机制清单/--pre-tts 枚举/--help 三面与 references/05 第九节第 5 条补收 zh 字幕宽度门（门已挂 --pre-tts 与 zh 完整门两路，枚举面漏同步）；③say 条目「既有 15 处调用点」订正为 14 处（build_narration 生产 1 + 既有测试 13，可 grep 复核）。

## RSI-030 guided-learn 精读产物无输入形态：上游《精读与通俗拆解》无法作为一等信源，Stage ① 被迫重复精读

**表因**：用户提出（2026-09-29）——本 Skill 与 guided-learn 配套分工（GL 出《{学习目标} 精读与通俗拆解》文档、to-video 出视频），但 Stage ① 信源分流只有 A 型（论文 PDF）/B 型（活信源）两型：GL 已完成通读、通俗化与循证拆解的冻结本地文档不匹配任何一型——`source_ledger.py` 只吃 URL 且 kind 仅 repo|site、A 型流程假设从原始 PDF 分章重读。同一信源被两套 Skill 各精读一遍，GL 的白话主线/类比/三拍叙事等通俗化成果进不了记忆点原料库。

**根因**：references/01 顶部信源分流表设计先于 GL 产物形态定型，形态枚举封闭；下游 02/03/04/05/PIPELINE.md 十余处硬编码 `paper-notes.md`（B 型 `source-notes.md` 同存命名缺口——02 完全未提），新形态无泛化落点；SKILL.md「先判任务类型」表无 GL 产物入口、description 触发面未枚举该形态、evals 无对应用例。

**定性**：非阻断改进（用户点名启动）。编号自 030 起：018–029 已由 PR #23–#26 消重后占用（018/019=#23、020/021=#24、022=#25、023..029=#26），本条承接其后。

**方案比选**：三案——① `source_ledger.py` 新增 kind="gl" 纳管本地冻结文档（否决：fetch/verify 是「活信源重抓比对」语义，冻结本地文档强挂 kind 制造语义漂移，且违背最小干预）；② 01 新增 C 型规格小节 + 下游指针化泛引（采纳：对齐 A 型「断言回溯到事实源文件小节」地基铁律；穿透抽查复用 paper_extract.py find 与 B 型台账纪律；活源指纹沿用 sources.toml 既有机制，不开第二本笔记；零机制脚本改动）；③ 不设 C 型、仅口头建议先跑 GL（否决：无规格无验收门等于没有，且触发面不含该形态）。

**处理方式**：01 顶部表加 C 行 + 「# C 型信源 · guided-learn 精读产物」大节（冻结快照 / 锚点回溯 / 穿透抽查 / 证据定级 / 补证 / 鲜度登记 / 验收）；02:3/:11/:18/:24、03 头部模板行与素材引用、04 核查表列名、05:17/:145、PIPELINE.md 目录树与脚手架清单的事实源引用泛化为三型指针（顺带修 B 型命名缺口）；SKILL.md 任务表加 GL 产物入口行 + 速查表 ① 行补 C 型（门列不动）+ 相邻技能协作第一条改为输入信源关系 + description 触发面扩充；README 相邻 Skill 行同步；scaffold.py 建集指引补 C 型半句；trigger-evals 追加 1 正 1 负；新增 tests/test_source_types.py 锚定测试。[PR #27](https://github.com/ThreeFish-AI/to-video/pull/27)，commit `1aba7a8`。

**后续防范**：① 新增信源形态先查 01 顶部分流表是否可挂，挂不进 = 规格缺口而非绕路理由；② 下游规格提及事实源一律三型泛引（文件名清单只在 01 顶部表一处枚举，防第四型再复制十余处）；③ 触发面变更必须补 trigger-evals 近邻用例（正负各一）防精度回归。

**同类问题影响**：B 型 source-notes.md 在 02 的命名缺口随本次泛化一并修复；04 核查表列名泛化后 A 型既有集不受影响（锚点语义不变）。

合并前评审（2026-09-30）：穿透抽查口径的出处订正——01「三、穿透抽查」与 CHANGELOG 原写「口径沿 ④ 验收」，但 04 并无该抽样口径（A 节是逐句全扫 + 锚点停在事实源笔记、不穿透原始信源），改为数字全量沿 04 A 节「数字……逐一核对」加严为穿透、非数字抽样沿用本规格 A/B 型验收的抽 10 条（01 与 CHANGELOG 两处同步）。

合并前评审二（2026-09-30）：02:11 与 03:126 的「B/C 型对应素材节」半悬空——C 型在 01 §七「素材映射」有锚点，B 型六节无素材节定义，执行者按指引回 01 找不到落点。订正为三型各有实锚：A 型 paper-notes 第 4 段、B 型 source-notes 叙事正文（B 轨）、C 型 01 §七「素材映射」（02 与 03 两处同步）。

## RSI-031 录制器异常路径泄漏整套系统 Chrome：browser.close 是顺序语句非结构保证，全仓无浏览器纪律成文

**表因**：用户提出（2026-09-29）——要求「能用 Headless Chrome 就用 Headless、用完的孤儿浏览器进程及时清理、能复用则复用」。核查：record_archify.py 是全仓唯一程序化驱动浏览器的脚本（Playwright channel="chrome" headless=True，:616-621，跨章复用单 browser——headless 与复用已达标），但 `browser.close()`（:628）只在正常返回路径执行：pump_until 超时 sys.exit（:684）、encode_frames 三处 sys.exit（:226/:230/:292）、wait_for_selector/wait_for_function 15s 超时抛 TimeoutError（:646/:705）、激活失败（:716 仅此一处先关再退）等路径全部跳过——每章 context（new_ctx :643/:698）异常路径同样泄漏；长批次（record_archify_all 逐图独立子进程 ~45 分钟）一次超时即残留整套 headless 系统 Chrome 常驻内存。文档层全仓无「headless 优先/用后清理/复用」任何表述，且 record_archify_all.py:17-19 与 10-final-render.md:88-90 的串行理由「多实例互抢前台焦点会掉帧」与 headless=True 矛盾（真实机理是 CPU/GPU 资源争抢，错误归因会诱导未来错误优化）。

**根因**：浏览器生命周期关闭是顺序语句而非 try/finally 结构不变量；无异常路径兜底；进程生命周期纪律只存在于 TTS 域（07:55-64 按端口 kill + 防误杀）未泛化到浏览器域；PIPELINE.md §三 脚本表漏登 record_archify*.py、README 依赖表漏 playwright/系统 Chrome，浏览器使用面无 SSOT 登记。

**定性**：非阻断改进（用户点名启动；含阻断级缺陷成分——异常路径资源泄漏）。

**方案比选**：清理路径三案——① 全局 pkill -f Chrome（否决：误杀用户在用的可见 Chrome，违背 TTS 域已确立的防误杀纪律）；② try/finally 结构化保证 + 失败时窄域清理指引（采纳：close 成为结构不变量；SIGKILL 级残留给出「headless + playwright 临时 profile 双特征」窄域检测/清理命令、只指引不自动杀）；③ atexit+signal 兜底（否决：finally 已覆盖全部可捕获路径，信号钩子复杂度收益边际）。context 关闭形状两案：统一 contextmanager 替换三处显式 close（否决：:753 编码前关 context 是刻意次序，统一包裹会改变正常路径生命周期语义）vs 显式关闭保留 + finally 幂等兜底（采纳，正常路径行为不变）。

**处理方式**：record_archify.py 提取 launched_browser contextmanager（launch/close 结构化，SystemExit/TimeoutError 路径必关）+ 每章 context try/finally 幂等兜底；新增 tests/test_record_archify_session.py（importorskip playwright + Mock 假 browser/context，断言异常路径 close 仍被调、正常路径恰一次；--with playwright 专项跑入 PR 记录）；record_archify_all.py 失败汇总后补孤儿复核指引 + 串行理由勘误；PIPELINE.md 新增「浏览器进程纪律」小节（headless 缺省 / 复用既定决策 / Remotion 无头自退 / 两步窄域清理与防误杀禁令）+ §三 脚本表补 record_archify*.py 两行；10:88-90 勘误指向新小节；SKILL.md 运行时陷阱加一行指针；README 依赖表补 playwright 与系统 Chrome。[PR #27](https://github.com/ThreeFish-AI/to-video/pull/27)，commit `1aba7a8`。

**后续防范**：① 浏览器生命周期一律 contextmanager/finally 结构化，禁止裸 close 顺序语句；② 进程清理必须窄域双特征匹配（headless + 临时 profile），严禁全局 pkill Chrome；③ 文档归因须与代码实况对拍（headless 无前台焦点——错误机理描述会诱导错误优化）。

## RSI-032 C 型信源（guided-learn）止步于 Stage ① 取证：类比规则与 GL 四硬律冲突，缺跨模态过程具象化与被动线性收看门禁

**表因**：用户提出（2026-09-30）——RSI-030 虽在 Stage ① 引入了 C 型信源（`research/gl-notes.md` 冻结快照与穿透核查），但下游 Stage ②–⑥ 对如何将《{学习目标} 精读与通俗拆解》从「主动阅读文档」转化为「具有画面感和过程具象化、让小白读者被动收看就能轻松理解的科普视频」存在三处断层：① **类比规则冲突**：guided-learn（`lecture-format.md §1.1`）强制执行类比四硬律（难点准入 ≤5 个、一物一喻、严禁升格为贯穿全篇的剧场/世界观、1–3 句即止并带失配拦截），而 `references/02-planning.md:9` 却硬性要求「一个贯穿全片的拟人化/比喻体系」、`03-narration.md:126` 要求「每个新概念配比喻」，诱导制片时推翻 GL 已核验的局部类比并强造失配大剧场；② **过程具象化映射缺位**：`01 §七` 仍引用 GL 已废除的「PREP 叙事」，且未规定 GL 的「三拍叙事（白话→机制→走查实例）」「动手实验室破坏性实验」「实证数字表」「适用边界」如何映射为分镜动画，压字数时极易删掉具体输入走查（Worked Example）与反例，只剩抽象规则配静态卡片；③ **被动收看门禁缺失**：`04 B 节` 缺「具象走查在场性」与「线性收看零回溯负担」判据，且未打通 GL 已产出的 `archify` 图与 `sources.md` 台账的直通复用。

**根因**：RSI-030 仅解决了「信源真实性回溯（Veracity）」单维，未覆盖「跨模态教学转化（Pedagogical & Visual Translation）」维度；`02/03` 的比喻条款写于 GL 类比四硬律定型之前，两仓规范演进产生 Split-Brain。

**定性**：非阻断改进（用户点名启动）。

**方案比选**：① 仅在 01 补几句提示（否决：02/03 的全片剧场硬约束仍在，下游照旧违背一物一喻，且 04/06 无门禁抓手）；② 跨阶段正交对齐（采纳：01 §一/二/七补齐 GL 台账/类比表/archify 资产承接与五大构件具象化映射；02/03 改为「视觉母题统摄 + 局部类比按难点准入/继承 GL 一物一喻」并确立「宁砍旁支广度、不砍具象走查深度」；04 B 节新增「过程具象化在场」与「线性收看零回溯负担」两判据；06 新增过程具象化四定式）。

**处理方式**：更新 `references/01-source-extraction.md`（§一/二/七 与 Stage ① 浏览器通道纪律）、`references/02-planning.md`（叙事策略与取舍原则）、`references/03-narration.md`（术语降落与三拍走查）、`references/04-verification.md`（B 节新增「被动收看双门」两判据）、`references/06-storyboard.md`（GL 构件动态具象化四定式）；扩展 `tests/test_source_types.py` 锚定 C 型跨模态映射与类比继承不变量。[PR #28](https://github.com/ThreeFish-AI/to-video/pull/28)。

**后续防范**：① 跨 Skill 协作不仅对齐文件格式（语法层），必须同步核心概念约束（语义层：如类比四硬律 vs 全片剧场）；② 压缩长文档为视频逐字稿时，Worked Example（具体输入走查）与破坏性反例属不可裁减的骨架，只许裁旁支章节。

## RSI-033 批量录制 67 图冷启动 67 次 Chrome、可见自动化孤儿进程漏检且无 doctor/Stage ⑩ 终扫闭环

**表因**：用户提出（2026-09-30）——① `record_archify_all.py` 虽在单图内部跨章复用 browser，但跨图仍逐图 `subprocess.run` 冷启动全新 Chrome（如 67 张图连续冷启动并销毁 67 次 macOS Chrome 主进程 + GPU Helper + 67 个临时 profile），系统开销极大；② Stage ① 动态网页取证与 Stage ⑥/⑧/⑨ 预览缺少显式的「三档浏览器通道优先级」，Agent 易调 `open`、`remotion studio` 或非无头工具在桌面弹出多个可见 Chrome 窗口；③ `PIPELINE.md §十` 的孤儿检测命令 `grep -E '[Cc]hrome.*--headless' | grep -F playwright` 只认 `--headless` 且必须含 `playwright`，导致**带自动化 profile 的可见 Chrome 孤儿进程**、Remotion `chrome-headless-shell` 残留及 Stage ① `--dump-dom` 孤儿进程全部漏检，且 `pipeline.py doctor` 与 `10-final-render.md` 收尾均无自动体检与窄域回收入口。

**根因**：① `record_archify_all.py` 将「故障隔离（单图崩不拖垮整批）」与「进程边界（每图新建 OS 进程）」耦合——实际上 Playwright 的状态隔离单位是毫秒级的 `BrowserContext`，单 `Browser` 进程配合每图异常捕获 + 崩溃时按需重启 `Browser`，即可兼得 1 次冷启动复用与 100% 故障隔离；② 孤儿进程判据将 `--headless` 当作必要条件而非特征之一，忽略了 `playwright_chromiumdev_profile-` / `puppeteer_dev_chrome_profile-` / `.temp/.*browser-data` 等沙箱 profile 特征本身即足以与用户日常 Chrome 100% 区分。

**定性**：非阻断改进（用户点名启动；含系统资源开销优化与可见孤儿进程漏检修复）。

**方案比选**：跨图复用三案——① 维持逐图子进程（否决：N 图 N 次冷启动 Chrome，违背复用减负要求）；② 裸共享单 Browser 无恢复（否决：任一图触发 Target closed 或连接断开会连坐后续全部图，违背 RSI-031 历史隔离初衷）；③ 进程内共享单 Headless Browser + 每章独立 Context + 单图异常捕获与 Browser 断连自愈重拉，并保留 `--no-reuse-browser` 逃生舱（采纳：正常批次 N 图仅启动 1 次 Chrome，异常时单图隔离并自动换新 Browser 续跑，显式权衡并升级 RSI-031 的跨图策略）。孤儿清理两案——① 仅更新文档 shell 命令（否决：无自动体检入口易被遗忘）；② `pipeline.py doctor` 内置 `scan_automation_browsers`（覆盖无头与可见自动化沙箱实例、区分 `ppid=1` 确认孤儿与在途实例）+ `doctor --clean-browsers` 按 PID 精准 `SIGTERM` 回收 `ppid=1` 孤儿 + Stage ⑩ 收尾必跑终扫（采纳：零误伤用户日常 Chrome，工具化闭环）。

**处理方式**：`record_archify.py` 提炼 `BROWSER_LAUNCH_ARGS` 与 `record_one_diagram()` 单图入口；`record_archify_all.py` 新增 `run_batch_reusing_browser()`（默认 `--reuse-browser`，支持 `--no-reuse-browser` 回退）；`pipeline.py` 新增 `scan_automation_browsers()` / `clean_orphan_browsers()` 并接入 `cmd_doctor` 与 `doctor --clean-browsers`；同步 `references/PIPELINE.md §十`、`references/10-final-render.md` 与 `CHANGELOG.md`；扩展 `tests/test_record_archify_session.py` 与 `tests/test_stages.py`。[PR #28](https://github.com/ThreeFish-AI/to-video/pull/28)。

**后续防范**：① 性能优化触碰既有隔离决策时，通过「细粒度沙箱（Context）+ 监督器自愈重启（Supervisor Restart）」同时满足低开销与故障隔离；② 孤儿浏览器识别一律以「自动化沙箱特征（profile/headless-shell/headless）× 主进程（非 `--type=`）× 父进程状态（`ppid=1`）」三维判定，兼顾无头与可见孤儿且永不触碰用户日常主 profile。


## RSI-034 配音默认档为 IndexTTS 克隆：制作期被小时级长跑阻塞，评审后重配/多语言追配无显式轨道，升档中间态预算门假红

**表因**：用户提出（2026-10-02）——① `tts.engine` 默认 `indextts`（config.py SCHEMA），新集建集即要求样本指纹（scaffold 写 `TODOTODOTODO` 占位、登记 refs.toml），首轮 `tts` 就是 2.5–3.5 小时克隆长跑，而此时逐字稿还在多轮改稿评审回路里，每轮都付克隆成本（README quickstart 甚至靠 sed 手翻 edge 才能免克隆跑通——README.md:110）；② 「整集评审通过后，用 IndexTTS-2.5 + 本人声音重配本集（story 段落演绎，其余内容零变更）」「额外为本集配英文配音」两类用户诉求在 SKILL 路由与 07 规格里无入口，只有散落的「重制存量集」手工配方；③ toml 已翻 `indextts`、音频目录还是 edge 草声时，`tts --pre-tts` 前置预算门拿旧引擎 manifest 的墙钟对按 story 254 字/分标定的 target_minutes 窗执法，语速差导致假 FAIL，把重配拦死在启动前。

**根因**：① 引擎只有「克隆为主、edge 兜底」的单档语义，缺「草声（制作迭代载体，秒级免费）↔ 终声（交付音色，小时级）」的两档生命周期——成本结构与使用时机错配；② 预算门实测口径假设 manifest 恒属当前生效引擎，未建模「换引擎中间态」；③ 重配/追配无路由行与规格章节，安全闸（`.engine` 签名护栏 + `--allow-voice-switch`）已存在但没有被流程化承接。

**定性**：非阻断改进（用户点名启动）。

**方案比选**：四案——① 仅改文档教每集手改 toml（否决：README sed 即现状痛点证据，缺省值语义未变，每个新集仍默认长跑）；② 新增 `tts.draft` 布尔草稿键（否决：与 style 锚点语义重复，重配要改两个键，第二意图源）；③ 实测门按语速比缩放窗口（否决：edge 无整集实测口径，造第二事实源）；④ `tts.engine` 默认翻 `edge` + `tts.style` 在 edge 期兼作「终声档锚点」（估算门分档机制既有且引擎无关——config.py tier 只读 `tts.style`）+ 实测门双条件跳过（草声锚点在 / `.engine` 标记首 token ≠ 当前生效 engine，后者消掉升档中间态假红，升格为「实测门只对当前生效引擎的 manifest 执法」不变量）（采纳：零新 SCHEMA 键、零新子命令，重配/追配两条触发流全骑既有轨道：`.engine` 护栏、`--allow-voice-switch`、tts-store 按_digest 恢复、双语 `[tts.en]` 混引擎）。

**处理方式**：`config.py`（默认翻转 + 锚点语义）；`check_script.py`（预算门实测口径双条件跳过，各打一行点名）；`pipeline.toml.tmpl`/`scaffold.py`（草声模板：engine=edge、ref/ref_sha1 注释预置、style 标注锚点）；`SKILL.md`（任务表新增「评审后重配音」路由行 + 工作流/⑦ 速查改写，gate 与 stages.toml 双址同步、阶段更名「TTS 配音：草声与克隆档位」）；`references/07-tts-voice.md`（决策树第 0 闸引擎分支 +「重配（评审后升档）」节 + 双语克隆追配要点 + 完成门双条件语义）；`VOICE-CLONING.md`/`PIPELINE.md`/`README.md`（两档策略对齐，quickstart 删 sed 行）；新增 `tests/test_voice_tiers.py` 锚定 + `test_config`/`test_check_script` 回归（含升档中间态钉子）；trigger-evals +1 正（重配话术）/1 负（近邻不触发）。（PR 待回填）

**后续防范**：① 成本差数量级悬殊的同类引擎必须显式分档（草声/终声生命周期），默认档取便宜者，贵的档只由用户显式触发；② 一切「按 manifest 实测执法」的门必须先核 manifest 属不属于当前生效配置——换引擎/换档中间态是常态而非异常；③ 显式触发型重配的安全闸复用既有 `.engine` 护栏与 `--allow-voice-switch`，不另造门；④ 文档声明「默认引擎」处（VOICE-CLONING/PIPELINE/README）与 SCHEMA 默认值必须同 commit 对齐，防再出现「文档说 edge、机制默认 indextts」的 Split-Brain。
