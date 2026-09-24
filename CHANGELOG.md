# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- 双语渲染（RSI-004）：「语言」成为与九阶段正交的独立维度，支持为同一集产出中文与英文两版视频（或择一）。机制三层：新增 `pipeline/scripts/langs.py` 语言注册表（tts 码 / edge 音色 / 长度单位 / 产物路径派生 / `--lang` 解析的唯一事实源；tts.py 因 paths.py 导入边界持内联镜像表，与注册表的一致性由测试钉住）+ `pipeline.toml` 新键（`narration.langs` 策略声明、`narration.words_per_min` 机制常数、`[narration.en]`/`[tts.en]` 覆写表，`config.for_lang` 覆写视图 + 逐语言必填重放）+ `pipeline.py --lang` 运行期选择（昂贵命令显式化：tts/render/deliver/all 缺省只跑主语言、显式多值才顺序执行且完成行按语言分打；qa 恒单语言按文件名后缀推断；build/check/captions/status 缺省覆盖全部声明语言）。内容层：英文译稿 `narration.en.md` 与主稿句 id 1:1 硬对齐门 + 基线锁 `narration.en.lock.json`（翻译时主稿句 digest 快照，主稿改稿后 check 点名失配句，防译稿静默失鲜）；`check_script --lang en` 新门集（禁汉字 / 必含拉丁字母 / 禁全角标点——上游 `use_chinese()` 逐句嗅探的路由风险、词数预算、字幕两行容量上限、`--check-scenes` 未翻译画面文字 WARN 报告）；chapters.json 条目可选 `i18n.en` 章节标题；series.json 可选 `i18n` 经 series-layers 透传。生产层：tts `--narration-lang`（en 落 `audio/en/` 独立 `.engine` 护栏，store 按 digest 中英并存）、captions/渲染/交付按语言后缀（`captions.en.*` / `draft/final.en.mp4` / `<标题> vN.en.mp4` 版本独立）、英文渲染前旧骨架预检（i18n.tsx 存在性 + 五 frozen 文件指纹 + manifest 句 id 对账——旧代集渲染英文会静默产出中文版）、`check_archify --lang en`（英文时长会改变 cue playbackRate，显式 stretch 越界将渲染期抛错）、tts_progress 对 en 跳过未标定的热节流判定。渲染层：新增 frozen `video/src/i18n.tsx`（`useLang`/`useL`/`<L zh en>` 内联双语对，en 缺省回落 zh；React context 穿透 Sequence，@react-three/fiber Canvas 自动桥接），Root/NarrationAudio/Subtitle/ChapterProgress/Main 加语言维度（zh 渲染逐像素不变；英文字幕两行回落几何守恒 `35+24+2×30×1.3=137 ≤ 137.4`，字幕带侵入检测两语言共用判据）。骨架治理：`skeleton.toml` 新增 `[[generation]]` 旧代指纹**原子分组**（显式花名册 + 旧代模板指纹；`verify_skeleton.py` 放行整代停留、报 `GENERATION-MIXED` 拦半同步集——只换 Main 不拷 i18n.tsx 会 tsc 红；既有 18 条 drift 的撤销指引同步改写为整组同步），以 6 行登记替代约 50 条逐集 drift。硬约束：既有集 zh 全产物（narration.json / manifest / digest / `.engine` / 渲染命令 / 交付命名）字节不变，由既有黄金测试 + 真树只读回归执法。

- RSI 建模经验分支（RSI-003）：制片中被用户或主 Agent 认可/否决、可跨集复用的**动效画面建模方法**（概念 → 画面/母题/构图/动效强度，策略层「画什么」，与 skills/06 运动层「怎么动」正交）有了沉淀通道——新增有界经验库 `pipeline/MODELING-PLAYBOOK.md`（建模方法 / 反模式 / 候选区三节；单行条目含「当/故/非/验/据/证」字段，「验」为成片帧上可观测判据、「证」为 `<集目录名>#镜号（YYYY-MM）` 锚点；编号 M-/X- 只增不复用）与规则唯一实现 `pipeline/scripts/check_playbook.py`（汉字每字 + 英文每词计 1、链接目标不计；**CAP 3000 字硬上限、HIGH 2700 触发压缩、压至 TARGET 2250** 的滞回水位；w 权重生命周期：新增 2/1、认可 +1、否决 −1、归零移出，定式须 w≥3 且证覆盖 ≥2 集）。RSI.md 分流表加「建模经验」一行、主代理只读例外扩为「台账 + 候选区」两处仅追加面、第九节不变量加第 15 条、新增第十节策展协议（Generator/Reflector/Curator 分权、⑨ 后攒批、候选原文交接且合入后撤回主检出在途行（至多一个策展 PR 在途，每条信号只计一次）、四门映射、六级压缩阶梯「淘汰→同键合并→下沉执法→归纳→冷退→措辞精简」、禁整文件重写与搬进规格正文腾预算、回潮信号恢复过度压缩条目）。消费点：02 视觉语言读手册、05 分镜标注〔M-xxx〕、06 LoopRing 适用列与「以静写闷」迁入手册改指针、08 修复回路当场追加候选、09 RSI 复查项扩写、SKILL.md 挂点与尾部指针。播种 4 条（M-001 恒定视觉锚 / M-002 以静写闷 / M-003 持续陈述配持续态 / X-001 空间隐喻逆旁白，均溯源自 claude-code-explained-video，全部为试行）。测试新增 test_modeling_playbook（计数黄金含「URL 紧跟中文」、水位分级、违规逐类报错、候选正负号三种字形、引号内句号不误切、同集双锚点不得晋升、提交态候选区须为空；共 49 例）并把手册纳入 test_docs_paths 受检面；设计依据与 IEEE 引用落 `docs/research/modeling-experience-distillation.md`（配 archify 回路图）。撤销条件：连续 3 集手册零引用（无〔M-xxx〕标注、无候选追加）⇒ 降级为手册只读、停止策展。

- RSI 自改进钩子：制片中（Agent 或用户）发现 Skill 自身的缺陷与流程/制度/方法改进项，登记 `docs/.agents/issue.md` 台账（`RSI-xxx` 三位编号，与上游 ISSUE-xxx 前缀隔离）后**另起子代理**调研改进并核验；四道门全过（G1 问题属实可复现 / G2 方案比选正确——须充分调研仓内先例与业界最佳实践、评选最佳，最小干预、不造第二事实源 / G3 正向收益可验证，缺陷类强制新增回归测试 / G4 无损历史——14 条不变量清单逐项三档核对）后自动向本仓发起 PR（base=main，中文标题/描述附四门核验表）并回报链接。制作期间 `$T` 机制文件对主代理只读（唯一例外：登记台账）、`$W`/`$P`/`$V` 对子代理只读（双锚点的运行时延伸）；阻断性缺陷走快速通道但一门不省；`$T` 非 git 安装时大声退出走 GitHub Issue 或 clone 迁移。协议正文落根级 RSI.md（元机制与 pipeline/ 视频机制正交，可直接作子代理 prompt 底稿），test_docs_paths 受检面扩至 RSI.md（围栏/链接/变量定义/混锚执法）；SKILL.md 加「自改进回路（RSI）」短节与 1 条关键不变量，skills/09 交付件清单加 1 个非阻断复查 checkbox（含种子条目 RSI-001 记录本机制落地）。撤销条件：若 RSI 产出的低质量 PR 噪声大于收益、或四门核验成本显著拖慢制片，可降级为「仅登记台账、PR 由用户手动发起」。

- 顶部分段式章节进度条（frozen `ChapterProgress.tsx`）：新集开箱自带全片顶部 overlay——段宽∝幕时长、已播 `text@0.9` 填充随帧推进（无播放头，进度仅由填充深浅表达）、**章节名内嵌段内居中**（sans 18，标题缺失回退 mono 幕码），段内文字**双色随填充前沿揭示**（已填侧深字 `bg` 压亮填充、未填侧亮字：当前章 `text`/未播章 `dim`，左右两层同显式 px 宽裁切保 ellipsis 逐像素一致）；段高 28（y14–42，圆角 4），整带仍收在 y<56 零碰撞带（各幕内容 y≥56 起、SceneTag top:64 不动），开场 12 帧淡入、片尾 tail ≤30 帧淡出（均从 props 推导零写死帧数）。数据面两条链：段边界/占比走 `computeTimeline` 的 `scenes`（TTS 重跑自动重定时）；标题走 `build_narration.py` 新派生的 `video/src/chapters.json`（`## Pn 幕标题` 此前被 SCENE_RE 丢弃，占位 `[]` 时组件自渲染 null）。档位登记：组件 frozen（同 Subtitle 性质）、chapters.json seeded（机器生成同 pnpm-lock 先例）；Main.tsx 挂载属 regioned 承重区改动，10 个既有集（9 已发布 + context-layer-video 待审）按 Subtitle 分代先例登记 Main drift 指纹 `179be60ed605`，ChapterProgress.tsx 各集缺失按 cards.tsx 先例钉「缺失」哨兵（保持现状态；撤销条件统一为下次重渲时同步模板 Main + 组件并重跑 build 派生 chapters.json）。配套规格：skills/03「幕标题即章节标签」、skills/05 顶部安全带、skills/06「顶部章节进度条」节 + 红线 2b + HarnessBadge 共存定案项（EP2–5 同步窗口）、skills/08 目检五判据；测试新增 test_skeleton 2 条（档位归属 + 挂载承重）与 test_build_narration 2 条（chapters 派生黄金 + 分隔符形态）。
- `deliver` 子命令（⑨ 交付归档）：`out/final.mp4` → `<根>/<系列id>/<集标题> vN.mp4` 统一归档。根路径两渠道——`--root`（一次性/prompt 指定）与 env `TO_VIDEO_DELIVER_ROOT`（持久统一配置；机器属性不进受版本控制 toml，同 tts.server / tts-store 立场）；系列子目录与集标题取自 series.json，版本号扫目录自增（同字节重投跳过不升版、`.part` 原子落位、绝不覆写既有版本）；显式子命令，不串联进 `render --final`（完成行信号契约），亦不可 `--series` 扇出。

## [1.0.0] - 2026-09-21

### Added

- 自 [ThreeFish-AI/negentropy](https://github.com/ThreeFish-AI/negentropy) `apps/negentropy-influence/pipeline/` 抽取为独立可安装技能：九阶段科普视频流水线（信源取证→策划→逐字稿→双重校验→分镜→TTS 声音克隆→Remotion 场景→草渲抽帧 QA→终渲交付）。
- 双锚点架构：skill 根（SKILL.md 哨兵，随安装位置）与内容工作区根（`.to-video-root` 哨兵，兼容 `.influence-root`）物理分离；`scaffold.py --init-workspace` 初始化任意目录为工作区。
- 分集/工作区薄包装器改为 skill 解析器（`TO_VIDEO_HOME` → `~/.claude/skills/to-video` → `~/.agents/skills/to-video`，未命中大声失败）。
- tts-store 默认目录迁至 `to-video`（旧目录自动回退兼容，内容寻址零缓存失效）。
  存量用户彻底搬走旧缓存（可选，一次性）：

  ```bash
  mv ~/Library/Application\ Support/negentropy-influence/tts-store \
     ~/Library/Application\ Support/to-video/tts-store
  ```

  （若新目录已被创建，先用 `rsync -a` 合并内容再删除旧目录，勿直接 `mv` 套娃。）
- `check_series` 工程级受检面与课程/下期卡系列 id 集配置化（工作区 `to-video.toml`）。
