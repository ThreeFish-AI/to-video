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

**后续防范**：声音风格类调优先问「合成结构与情感粒度对不对」，再调强度参数；试听素材必须用连续故事段落（零散句子听不出演绎）。切分算法的量尺教训：句界停顿 0.31–0.55s 与句内逗号停顿 0.14–0.42s 区间重叠，不能「取最长 N−1 静音」，按字符占比期望位就近选（DP）。评审回归（2026-09-25）：① 切分失败的逐句兜底在 `async with sem` 内递归、再次获取同一 `Semaphore(1)` ⇒ 首个切分失败块即整集挂死（stub 复现：WARN 后零请求永久阻塞）；已把锁收窄到单次请求、兜底在锁外逐句请求，兜底沿用块情绪并按块成员摘要落盘（旧兜底写单句摘要，复跑永不命中、每次重试整块）；② 块合成路径的 `durationSec` 取服务端 PCM 时长、命中路径取 `mp3_duration`，lameenc 下每句差 +0.06–0.075s ⇒ 无改动复跑即令时间轴漂移（百句约 6s），已统一取 mp3 实测；③ 块路径丢了逐句路径的编码器守卫，服务端无 MP3 编码器时 WAV 字节被静默写成 `.mp3`——clip 现回传 `format`，非 mp3 硬拒不落盘；④ `tts_progress` 聚簇后墙钟与**上一簇**字数配对（逐句模式同受波及）且末簇从不入列，已改为配对下一簇并补末簇，单簇无样本时报不足而非 StatisticsError。6 条回归用例在旧实现下全红（兜底用例为 5s 超时）。教训：新增「同一函数内再次请求」的降级路径时，先查外层持有的锁是否可重入；同一产物的派生量（时长）必须与缓存状态无关，合成路径与命中路径取同一量尺。评审回归二（2026-09-25）：① `plan_blocks` 把块数下界 max(⌈n/3⌉,⌈ΣL/90⌉) 当成定值，「多句块 ≤90 字」装箱约束下恰好 k 块常切不出，整段 run 直接退化逐句——14 集语料对拍 2303 句切出 1207 块、单句块 619（multiagent 134 句 118 个单句），已改为逐层放宽到首个可行块数：块数与暴力最少可行值逐集一致、单句块 619→3，旧算法可行的 run 改写 0；② 台本段超限被自动拆开时，后续子块首句无 cue、静默退回预设向量，已改为子块继承段首 cue（块首句浅拷贝注入，narration items 原件不改）；③ `block_synth_text` 对 `，：、——` 结尾也追加 `。`，拼出 `，。`（上游 `,.` 双标点）并把续接改成句末降调（语料约 10% 的行），已改为保留软停顿标点、仅无标点结尾补 `。`，块后缀 `split=v1→v2` 换键（改动时无 story 存量音频，零重录成本）；④ `--plan` 块口径 ETA 未扣版本库可整块回收的块，已同逐句 `n − store_hits` 口径；⑤ 块路径本地整块命中时不回填版本库，已补齐；⑥ `tts_sample --all-styles` 只按 neutral 解析采样口径，story 档丢了预设 seed，已改为逐档解析（原「预设带 sampling 即拒绝」门随之失效移除）。6 条新增用例在旧实现下全红。教训：「下界即解」只在无约束时成立——带装箱约束的 DP 必须从下界向上找可行解；划分类算法改动先在真实语料上对拍「旧可行解是否零改写」再合入；改变合成文本却不改成员文本的算法变更必须显式换键。评审回归三（2026-09-25）：① 台本 `[say]` 的标注校验只查「say 里还有没有标注」，全等比较又先 strip_marks ⇒ 两处标注删一处、或改读音都能过（多音字读错只能靠听发现），已改为保留标注只去标点再比，标注集合/位置/读音逐个钉死；② 逐句兜底的每个单句请求都带 `tail_pad_sec`，服务端单句路径无条件补垫 ⇒ 兜底块内每句多 0.18s 停顿，已改为仅末句补垫（同块合成口径）；③ 收引号/括号结尾（`不可能！”`）的末字判为非停顿，拼出 `！”。` 双标点，已改为剥掉收引号再判末字（14 集语料恰 3/2303 句受影响，其余零改写）；②③ 改变合成结果而成员文本不变 ⇒ 块后缀 `split=v2→v3` 换键；④ `pipeline.py status` 的 narration.json 新鲜度只比 narration.md，只改台本时误报「✅ 新鲜」而 `tts` 不自动重 build ⇒ 拿旧 cue 合成入缓存，已把 cues.toml 纳入主稿依赖。5 条新增用例在旧实现下全红。教训：「只许改 X」类校验须比较「保留 X 以外全部信息」的规范形，而不是先抹掉受保护信息再查存在性；新增派生输入（sidecar）时同步所有新鲜度/依赖面。评审回归四（2026-09-26）：① 无台本段的自动分块是整段全局 DP（Σlen²），块界依赖段内全部句长——9 句×31 字一幕末句 +1 字，5 个块边界全部平移、整幕重录，与「改一句重录整块」的契约不符；14 集语料逐句 ±2/±8 字模拟：改字爆炸半径均值 3.73 / p95 11 / max 34 句。对拍了定长窗（3/6/9 句）+窗内 DP、左到右贪心、id 哈希锚定窗（CDC）等 13 种候选：贪心仍会向右级联（max 31）；CDC 能把插/删句波及从均值 ~12 压到 ~4，但块数 +11–20%（缝多即朗读感回潮）；选 6 句定长窗 + 1 句尾窗并入前窗：爆炸半径 max 34→7、p95 11→3、仅本块 88.8%→94.7%，块数 836→858（+2.6%）、单句块 0.4%。插/删句仍按位置重排同段其后各窗（旧算法同样整段重排，均值 11.6→14.0 句，未恶化量级），台本块起点是硬边界可把波及收在段内，已写进 §4.5。② 台本 `[say]` 去标点比对连数字里的半角 `.,:` 一并剥掉，`3.5%`→`35%`、`10:30`→`1030` 能过校验（念成另一个数而字幕不变），已改为夹在两数字之间的不剥。③ `[block]` 值写成字符串（TOML 合法）时 `spec.get` 抛 AttributeError、`alpha = "x"` 的 `float()` 在 try 外，build 以 traceback 退出——已统一汇入 FAIL 清单（含 `[block]`/`[say]` 本身不是表、`alpha` 为 bool、`emo` 非字符串）。3 条新增用例在旧实现下全红（另 1 条尾窗守卫为新设计兜底）。教训：以缓存为单位的划分算法，目标函数必须是局部的——全局最优的划分对局部改动不稳定，评审「改一处波及多少」要用真实语料做逐句扰动模拟，而不是只看一例；「去掉 X 再比」的 X 要按上下文判定（数字里的 `.` 不是标点）。评审回归五（2026-09-26）：① 台本 cue 方向归一后 Σ 浮点可为 1.0000000000000002（如 `afraid:0.01,surprised:0.04,calm:0.13`），build 按 (0, 0.8] 放行的 `alpha = 0.8` 在 `resolve_block_vec` 与服务端 Σ×α≤0.8 护栏上以 1 ulp 之差被拒（α=0.8 时随机方向约 0.7% 的组合；只放宽客户端比较会把误拒挪到服务端、变成合成中途的 400），已改为 α>0.8 才报错、仅踩边界时把最大分量逐 ulp 下调（≤2 步，偏差 <1e-15，未踩边界的向量与摘要逐位不变）；② `[say]` 比对无条件剥掉全角标点，往数字串里插 `，`（`1200`→`12，00`、`2026年`→`20，26年`）或删掉两数之间的标点（`2020，2026`→`20202026`）都能过校验，逐字符判定还会被 `12……00` 这类多字符串绕过，已改为按标点串整体判定：夹在两数字之间的单个半角 `.,:` 原样保留、其余归一为分隔符（两数之间换表演标点照常放行）。2 条新增用例在旧实现下全红；14 集语料均无台本文件，零波及。教训：两端各设一道同口径护栏时，边界修复要让**发出的数据**本身合规，而不是只放宽一端；「只许改标点」的规范形要以标点串为单位判定上下文，逐字符判定会被连写绕过。评审回归六（2026-09-26）：① 回归三的「保留标注去标点再比」连标注内部的标点一起剥，`<行|HANG，2>` ≡ `<行|HANG2>`，build 放行并把非法标注写进 ttsText（`pron_marks.validate` 判非法；走 pipeline 要到 pre-TTS 门才红，直跑 tts.py 或 `--skip-pre-tts` 会原样送合成），已追加 `PRON_MARK_RE.findall` 逐字全等；② `split_block_pcm` 末段起点即末个切点，静音只是低于 p95−35 dB 而非零值，中间段两端淡变而末段只淡出 ⇒ 每个多句块末句起播有底噪阶跃，已改为每段两端淡变——时长不变、差异落在静音内不可听，**不换键**（换键口径写进 `block_digest_suffix`：只有送合成文本或切段时长变了才递增，否则存量音频为不可听差异整块重录）；③ `--steady` 冲突检查排在 EN 回退之前，EN 版本已回退逐句却仍被拒（报错文案还指向块合成），已把检查移到回退之后。3 条新增用例在旧实现下全红。教训：「规范形比较」要先界定哪些片段是不透明的——标注是整体，内部字符不参与规范化；同一路径上的降级（EN 回退）会让后续互斥检查的前提失效，互斥检查须排在所有降级之后。

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

**后续防范**：① 执法测试与不变量**不写死阶段数量或具体序号**，一律从 stages.toml 推导（本次三条测试与三条不变量都曾写死「9」）；② 规格文件名出现在注释与散文里时，改名必须过 `test_spec_references_resolve`，不能只靠 Markdown 链接门；③ 裸写的 `references/07` 这类简写不在门内，改名时须用 `git grep` 搜出所有「references/ + 两位数字」且后面不跟连字符的写法，人工逐条核对；④ 内容层新规则上线前，先在真实语料上量化病灶，避免给已经干净的层级加门。评审回归（2026-09-26）：① 通过门里的「成文评审 REWRITE=0」在规格中找不到产出它的步骤：第九节只定义了改动句回 ④A 复核，第十节只是勾选表，执行 ⑤ 的代理无法判门。已在第九节补第 3 步「成文评审」：独立子代理只拿规格、改后稿件和改动表，按第三至第八节的具名规则判 REWRITE；给不出规则编号的意见不算。② 改动句复核判 REWRITE 时只写了「按 ④ 修正」，门里却只查 RISKY=0。门改为「成文评审 REWRITE=0 且改动句复核 RISKY=0、REWRITE=0」，与 ④ 同口径，stages.toml / SKILL.md / README / CHANGELOG / evals 与 `prose-refinement--passes` 图同步更新。教训：authored 阶段的 prompt 门没有测试兜底，门里每个判定量都要能在规格里找到「谁产出、按什么判」；引用上游门的判定时，连同上游的放行口径一起引用。二次评审（2026-09-26）：① 第九节的 RISKY 回退按单句粒度，但第四节第 9 条允许在相邻 id 间搬运文本，只回退其中一句会让被搬运的文本丢失或重复，且回退句不再送评审、无环节兜底。已改为：重新分配涉及的几个 id 在改动表合写一行，回退以行为单元整组回退。② scaffold 结尾提示「润色四稿再切镜」与规格时序矛盾（分镜在 ⑥ 才产出），改为润色笔记 / 策划 / 逐字稿后切镜、分镜定稿前回调 ⑤ 第七节。③ 研究文档方案 A 一行残留旧序号「②③⑤」，改为 ②③⑥。教训：规则允许跨单元搬运内容时，回退、复核等补偿动作的粒度必须与搬运的粒度一致；重编号后，研究文档里描述候选方案的旧序号同样要按 `git grep` 圈号逐条核对。三次评审（2026-09-26）：① 第九节第 1 步「在 git 下即以 git diff 定位改动」默认稿件已提交，而新集稿件在 ⑤ 时多半未被 git 跟踪，`git diff` 看不到，复核范围与 RISKY 回退都失去基准。已改为：稿件在 ④ 清零时已 commit 才用 `git diff HEAD` / `git show HEAD:`，否则一律复制到 `$P/.temp/prose-before/`；不拿暂存区当留底（改稿中途再 `git add` 即覆盖），没有留底不得开始改稿；evals #1 的 ⑤ 断言补「改前留底」。② 改动句复核只跑 ④A，而 ⑤ 的话题链改主语、跨 id 搬运正好会让 ④B 的术语降落、指代距离、抽象连段退步，定稿时无环节再核。复核范围扩为「A 节四级判定 + B 节前三条（连同前后句一起看）」，门的字面不变（B 只产出 REWRITE，已含在「REWRITE=0」内），04 规格、SKILL.md、stages.toml 注释、CHANGELOG、evals 与研究文档同步。③ `prose-refinement--passes` 图的输入仍是含分镜的「四稿」，与时序矛盾（分镜在 ⑥ 才产出）：输入改为三稿，顶部新增「⑥ 分镜回调」泳道（定稿 →切镜→ ⑥ 分镜，定稿前回调第七节），复核节点标注 ④A + ④B 前三条；archify showcase 9/9、0 错 0 警、无回折尖刺，visual-check 通过，重导 dark/light PNG，mmd 与 alt 文本同步。④ 新增的 `spec_reference_files()` 与既有 `current_docs_and_code()` 逐项重复，已删除并把知识索引并入后者（反控：向知识索引注入旧文件名即红）。教训：留底、回退这类补偿动作要先确认基准在真实初态下存在（新集 = 未跟踪文件）；上游门拆成 A/B 两半时，下游复核要写明复核哪一半，不能只引半边；修正一处时序表述后，要把同一说法的所有载体（脚本提示、图、alt 文本、规格步骤）一起 grep。四次评审（2026-09-26）：① 第九节第 1 步的留底基准写成 `HEAD`，而 HEAD 在 ⑤ 中途任何一次提交后都会移走：`git diff HEAD` 只剩最后一次提交之后的改动，更早改过的句子漏出 ④ 复核；RISKY 回退用 `git show HEAD:` 取回的也是改了一半的文本。已改为开工前 `git rev-parse HEAD` 记下基准 SHA，diff/show 一律用它。② 第四节第 9 条的跨 id 搬运对已有分镜的集不安全：SKILL.md「润色成稿」路由与第二节第 6 条都允许对已制作的集跑 ⑤，而分镜画面列、场景 `rel(beat,'句id')` / `at()` 时点、archify cue 锚句都按 id 绑定内容，文本搬走后画面比口播早或晚一句，`check` 查不出。已补护栏：分镜已存在时，搬运前在分镜与 `video/src/scenes/` 里 grep 涉及的 id，有画面锚在被搬走的文字上就同步改分镜与场景，或放弃搬运；第十节加一条对应勾选。CHANGELOG 同步。教训：留底基准要钉成不可变引用（SHA），不能用会随操作移动的引用（HEAD、暂存区）；研究文档里否决某方案的理由（这里是「破坏分镜句区间与锚句」），在规格仍允许该情形出现的路径上（已制作集）同样要设防。合并 main（2026-09-26，PR #17 story 配音已合入）：① 本条由 RSI-011 顺延改号为 RSI-013，现行文案、测试 docstring、mermaid 注释与 CHANGELOG 同步；② PR #17 新增文案里的 `references/06-tts-voice.md`（tts.py 两处）改指 07，CHANGELOG [Unreleased] 的「重制流程见 references/06」改为 07；③ ⑤ 规格与 story 档衔接：第二节第 6 条改为「逐句档改一句重配一句、story 档改一句重录整块」并补台本 `[say]` 同步义务（去标点全等，否则 build FAIL），第四节「与配音分块的关系」去掉「若采用」假设、写明 beat 首句应是台本块起点，研究文档 §五 同步。教训：并行分支各自预留台账编号时，后合入者合并前要先 `git grep` 对方已占用的编号；对方合入后，本分支里「尚未合入 / 若采用」这类以对方状态为前提的表述要逐条改成现状。五次评审（2026-09-26）：第九节第 5 步与第十节要求 ⑤ 定稿时「`build` + `check` 零 FAIL」，但新集走主路径（④ 后先润色、再切镜）时还没有 `storyboard.md`，`check_script.py` 的主稿完整门遇缺分镜直接退出（`storyboard.md 不存在`，rc=1；临时工作区实测复现），`pipeline.py check` 又在 zh 失败后短路、en 失配句也点不出——代理要么卡住，要么提前写分镜违反时序。已改为按分镜是否存在分流：已存在跑完整 `check`；新集跑 `check_script.py --pre-tts`（时长预算 / 读法陷阱 / 发音标注，实测 rc=0），双语集另跑 `--lang en`（en 门不读分镜，实测点名基线锁失配）；完整 `check` 移到 ⑥ 之后。SKILL.md 速查表 ⑤ 行与「润色成稿」路由、`prose-refinement--passes` 图（定稿节点改「build + 机器门零 FAIL」、⑥ 节点补「全量 check」；archify showcase 9/9、0 错 0 警、9 条边无回折尖刺，visual-check 通过，重导 dark/light PNG）、mmd 与研究文档 alt 文本同步；工具不改（缺分镜即 FAIL 是完整门的既定语义）。教训：规格里点名的每条命令，都要在该阶段的真实初态（新集 = 分镜未产出）下实跑一次；插入新阶段后，下游产物尚不存在，沿用上游门的命令前先查它对缺失输入是否硬失败。六次评审（2026-09-26）：① 第九节第 4 步把研究笔记的改动句也送回 ④A，但 ④A 以 paper-notes 为锚，笔记本身就是 ④A 的事实源，改写后的主旨综述段只能自己核自己，笔记一旦漂移，后续逐字稿复核也以漂移后的笔记为准。已改为：研究笔记的改动句仍做 A 节四级判定，锚点换成信源原文（A 型 `paper_extract.py find`，B 型按 `research/sources.toml` 登记的 URL 回查）；04 规格「输出」节与 CHANGELOG 同步，④A 的判定口径不变，故 `prose-refinement--passes` 图不动。② L1 把调序、补「转」、兑现开头的问题列为可改项，而第二节第 2 条禁止重排与增句、只给拆句 / 并句指了回 ③ 的出路，第十节第一项在 ⑤ 内可能无法合法达成，代理只能违反 id 冻结或在不相邻 id 间搬文本（锚点回查与相邻 id 回退单元都不覆盖）。已在第二节第 2 条写明 ⑤ 对逐字稿只做 beat 分组与相邻 id 间文本重分配，拆 / 并 / 调序 / 补句一律回 ③、连同已做的 ⑤ 改动重过 ④，回来后重新留底；L1 行加指针，第十节 id 集合基准改为「回过 ③ 的以重新留底时为准」，CHANGELOG 同步。③ 第二节第 5 条仍无条件要求「改完必须重跑 `check`」，是五次评审在第九节修掉的同一问题的残留载体，改为「按第九节第 5 步重跑机器门」，并注明复述门只在分镜与场景已存在时触发。教训：规格让某个事实源本身可被改写时，复核锚点必须上溯到它的上游，不能以它自己为锚；某一层 pass 的「改什么」若与护栏冲突，必须在护栏里给出合法出路，否则验收项形同虚设。

**同类问题影响**：negentropy 已发布集的 frozen 骨架注释指针会落后于模板（md5 变化、`verify_skeleton --strict` 报 STALE），仅注释差异、行为零改动，按 CHANGELOG「Breaking」第 2 条自适配；PR #17 先于本条合入 main（`3b1607a`，占用 RSI-011/012），本条合并 main 时由 RSI-011 顺延改号为 RSI-013（合并前的 commit message 仍写 RSI-011，以本台账为准）；其 TTS 规格改动随 git 改名识别自动落入 `references/07-tts-voice.md`，RSI-011 / RSI-012 两条台账里的 `references/06` 指当时的 TTS 规格（现 07），按历史记录保留原文；尚未发版的 CHANGELOG [Unreleased] 与现行文案里的同类旧指针已随本次合并改为新编号。
