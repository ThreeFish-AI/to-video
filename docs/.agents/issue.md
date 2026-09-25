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

**后续防范**：兼容义务以「显式决策 + 台账 + 版本号」为界——新增任何兼容读/回退/别名前，先问「删除它的 major 版本在哪」，无删除计划就不许加。skeleton 登记表只登记「当前合法偏离」，别仓集名不得进本仓模板。skill 仓不携带任何指向具体内容工作区的名字（系列 id、集 slug、仓名）。评审回归（2026-09-25）：文件号互换只改了带路径的链接，漏了三类写法——裸编号散文（RSI.md G2「不重述 06 机制与红线」、test_docs_paths 注释「06 规格」）、带新前缀但编号未换的 `references/05→06`、研究文档里的 `skills/06` 简写（4 处）；另有同一版本内 RSI-008 的 CHANGELOG 条目仍写「软链禁删 / 零改动可用 / 错位不变 / 不变量 16」，与 Breaking 节矛盾。现已全部改正。研究文档已纳入 `test_no_legacy_layout_paths` 受检面（`skills/NN` 简写入拦）。裸编号散文无法泛化检测（会与时间、序号误撞），今后改编号须对旧编号全仓 grep，并按上下文语义逐处判定。未发版的条目在发版前要改写到终态，被同版推翻的子句不得留在发布说明里。

**同类问题影响**：本仓 CHANGELOG/issue 台账中的历史叙述按记录保留，未随兼容面删除。破坏面与未兼容旧功能清单已同步登记到 negentropy 侧（[ISSUE-200](https://github.com/ThreeFish-AI/negentropy/pull/1174)，PR [#1174](https://github.com/ThreeFish-AI/negentropy/pull/1174)，2026-09-25），待其适配后逐项验证关闭：

**A. negentropy（apps/negentropy-influence，14 集）破坏面——按 2.0.0 CHANGELOG 三步适配后逐项验证**

| # | 破坏面 | 修复 | 验证 |
|---|---|---|---|
| A1 | 61 个薄包装器（14×tts/build_narration/qa_frames + 17 个 archify 类 + 2 工作区包装器）探测 `pipeline/scripts`，全部「找不到 to-video skill」 | 探测行 `pipeline" / "scripts` → `scripts`（与 2.0.0 模板字节一致） | 任一分集 `scripts/tts.py --help` 可跑；`TO_VIDEO_HOME=<新 skill>` 下 `verify_skeleton.py` 对模板零漂移 |
| A2 | pre-commit `series-consistency-check` 走工作区包装器，触及 influence 的提交被拦 | 同 A1（工作区 2 份包装器） | 暂存一处 influence 内改动，钩子 Passed 而非报「找不到 skill」 |
| A3 | 旧哨兵 `.influence-root` 不再识别，依赖 WORKSPACE 锚的脚本大声退出 | 工作区根补空 `.to-video-root` | 工作区内任意目录直跑 `check_series.py`，rc=0 |
| A4 | tts-store 旧目录（实测 65M / 1815 句）回退删除，缓存全 miss（重渲一集重合成 2.5–3.5h） | `mv ~/Library/Application Support/negentropy-influence/tts-store ~/Library/Application Support/to-video/tts-store` | 任一集 `pipeline.py tts`（不改稿）零重合成、全部命中缓存 |
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

**后续防范**：skill 仓只放机制；任何「指向具体集/系列」的数据（登记、豁免、花名册）一律住工作区，新增此类配置前先问「它随内容变还是随机制变」。发布说明里的迁移步骤必须能照做——写「须登记到 X」前先确认 X 存在读取入口。删除数据条目时区分「条目」与「格式说明」：前者可清零，后者是机制文档，删了即留悬空指针。

**同类问题影响**：negentropy 侧 A5 由「整组同步或接受红」扩为可登记（CHANGELOG 第 ④ 步）；旧版在 skill 侧登记的写法在 2.0.0 被拒收（RSI-009 B 节同步改写）。
