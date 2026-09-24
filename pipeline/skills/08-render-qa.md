# Stage ⑧ 草渲 + 抽帧 QA（skill 规格 · 08）

> 草渲的意义：半分辨率快速出片，把「时长/分镜/画面」问题在终渲前暴露。渲染缺陷的**七条红线**沉淀在 [06-remotion-implementation.md](./06-remotion-implementation.md)（SSOT，此处不复制）；本文件覆盖抽帧与自动体检的操作契约。

## 命令闭环

```bash
# 草渲（0.5x，jpeg 60——参数已固化在 remotion.config.ts + pipeline.toml）
uv run --no-project $T/pipeline/scripts/pipeline.py --project $P render

# 抽帧三选一：幕抽样 / 指定句 / 末 N 句（尾幕渐黑缺陷的必查项）
# ⚠️ 草渲 --check 须带 --scale 0.5：字幕带/亮块间隔按全分辨率像素常数计算，不折算则判据双向失真
# ⚠️ 视频路径按 CWD 解析（非 --project 相对）——**直调本脚本**时须写锚定路径 $P/out/draft.mp4；
#    而经 `pipeline.py qa --video` 时 cwd 已是分集工程，须写 out/draft.mp4（两者不可互抄）
uv run --no-project --with pillow --with numpy $T/pipeline/scripts/qa_frames.py \
    --project $P $P/out/draft.mp4 --scene P2 [--check --scale 0.5]
uv run --no-project --with pillow --with numpy $T/pipeline/scripts/qa_frames.py \
    --project $P $P/out/draft.mp4 p6-11 p6-13b --check --scale 0.5
uv run --no-project --with pillow --with numpy $T/pipeline/scripts/qa_frames.py \
    --project $P $P/out/draft.mp4 --last-n 6 --check --scale 0.5

# 主题对比度（零依赖，不需视频；新配色/改 theme.ts 后必跑）
uv run --no-project $T/pipeline/scripts/qa_frames.py --project $P --check-theme

# beat 头部连抽（每 beat 首句起点连抽 N 帧）——入场瞬态的机械补盲：
# ISSUE-170 实证「落位态干净、入场越界」会被句中点采样整段错过（此模式冻帧判定关闭）
uv run --no-project --with pillow --with numpy $T/pipeline/scripts/qa_frames.py \
    --project $P $P/out/draft.mp4 --beat-heads 4 --check --scale 0.5

# A/B 对拍（重制/重构回归）：同帧号抽两版逐帧差异，按差异像素占比降序；
# advisory（有匹配帧时退出码 0；零匹配硬失败）——「意图变更之外的一切差异」都须归因后才能接受
uv run --no-project --with pillow --with numpy $T/pipeline/scripts/qa_frames.py \
    --project $P --compare $P/out/baseline-draft.mp4 $P/out/draft.mp4 --scene P4
# ⚠️ 对拍低差异 ≠ 无回归（ISSUE-177 实证）：低 meanΔ（0.8–1.0%）与 --check FAIL 0 曾双双
#    放过仅占画面 ~2% 的塌陷常驻 badge——数值门只能缩小目检范围、不能替代目检；
#    改动触及跨幕常驻元素（顶栏徽标/角标/水印）时，抽帧必须额外覆盖一个「非改动幕」作对照
#    （该轮改的是 P0/P6 的层板，坏的却是 P1–P6 的常驻条——只看改动幕会全过）
```

## 双语集（en 版）

- 草渲 `uv run --no-project $T/pipeline/scripts/pipeline.py --project $P render --lang en` → `out/draft.en.mp4`；抽帧 `… qa --lang en $P/out/draft.en.mp4 …`（`--lang` 缺省按视频文件名 `.en` 后缀推断，显式冲突即报错）；帧目录 `out/frames.en/`。
- **英文 TTS 之后、英文渲染之前必跑** `uv run --no-project $T/pipeline/scripts/check_archify.py --project $P --lang en`：archify cue 的 playbackRate = 章时长 ÷ 锚句时长，英文锚句时长不同，**显式 `fit='stretch'` 的 cue 越界会在渲染期直接抛错**（zh 版同理但时序不变故无此增量风险）。
- 英文字幕的两行回落几何（盒顶 137 ≤ 单行包络 137.4，字幕带侵入检测两语言照常执法）见 [06](./06-remotion-implementation.md)。

## 自动体检判据与处置

| 判据 | 级别 | 处置 |
|---|---|---|
| 黑帧/早渐黑（均值 <0.02；末 beat 且分镜标「渐黑」豁免） | FAIL | 查尾幕渐黑是否从**末 beat** 而非末句推导（skills/06 红线 4）；查 SceneFade 末幕是否误开淡出 |
| 字幕带侵入（字幕框 x 区间外有独立亮块） | WARN | 角标/图形挪出 bottom≥160px 安全区（角标一律绝对定位并写死 `bottom ≥ 150`） |
| 冻帧（相邻采样帧 16×16 指纹相同） | WARN | 查 beat 窗口是否错位/句子未被分镜覆盖（`check_script.py --check-scenes`） |
| 字幕缺失（字幕带无文字亮度像素） | WARN | 查该句 Subtitle 是否被遮挡或文本为空 |
| 主题对比度 <4.5:1 | FAIL | 换色或加深；概念色清单见 skills/06 视觉契约 |

**FAIL 0 的边界（ISSUE-187 泛化）**：`--check` 只覆盖黑帧/冻帧/字幕带侵入/对比度——对文字朝向、
几何锚点、图层遮挡**全盲**（四类画面缺陷曾在 FAIL 0 · WARN 0 下全部漏网），FAIL 0 不是视觉正确性的
证据，2D 同样必须按分幕复检抽帧目视（3D 侧同款要求见 [06 §3D 验收](./06-remotion-implementation.md)）。
**判据上架纪律（ISSUE-167）**：新增/修改判据必须先在一帧**已知干净**的画面上验证零报警——半透明
字幕底曾让「亮列连通段」判据把每个汉字当侵入物，全片 500+ 假 WARN 让这行输出彻底失去信噪比、
等于关掉检查；判据优先用几何量（尺寸/边距来自代码常量、零自由度）而非亮度阈值（随配色/透明度/
抗锯齿漂移）。

**注意**：`--offset` 有两个触发场景——草渲与终渲时间基准不一致，或对 `remotion render --frames=<区间>`
渲出的**区间产物**抽帧（其时间轴局部归零：区间首帧即第 0 帧，须以区间起点补偿）；每次重合成后
**所有** beat 时间轴位移，抽帧样点必须从新 manifest 重推（工具自动做，但不要复用旧帧目录的旧结论）。
**对拍基线**：重制动手前先渲一版 `baseline-draft.mp4` 存档（后续工作区没有旧产物可回取）；A/B 共用
同一份音频与 manifest 时，总帧数恒等、同帧号对拍才有意义。**接缝成对抽帧（ISSUE-188）**：凡
「A 素材播完接 B 素材」的结构（archify hold 冻结补足 / 跨镜同装置 / 换章），必须抽 `videoFrames-1`
与 `videoFrames` **成对**的帧——接缝类缺陷只存在于两段素材的交界，单点抽帧结构性失明。
**批量抽帧先 render 再抽**：成批量的抽帧先渲出 mp4 再按句 id 抽，勿反复 `remotion still` 逐帧渲
（分幕复检用 still 是因为彼时 draft.mp4 尚不存在；视频可渲之后 still 就不是批量通道）。

## 人工目检清单（自动体检之外的残余）

1. 色彩语义遵守本集契约（每个概念色的指代不串）；
2. 每个 beat 画面与分镜「画面/动效」列语义一致；
3. 金句卡排版（衬线体/居中/角标出处）。
4. **顶部章节条五判据**（规格见 skills/06「顶部章节进度条」）：分段比例≈幕时长占比；
   填充前沿随帧线性推进、无播放头圆点；**段内文字双色随填充前沿揭示**——已填侧深字、未填侧亮字，
   未播章整段暗字（换段帧 `scenes[i+1].from` 前后各抽一帧）；开场淡入与片尾淡出（首/尾帧行为）；
   段内文字与 narration.md 幕标题一致、无溢出截断异常，整带收在 y<56 不与 SceneTag/角标重叠。

## ★ 分幕音画复检（TTS 长跑期间做，不要等成片）

配音是全流程最慢的一环（整集 2 小时量级），而**动画与旁白的错配只在真实时长下才暴露**。
不要干等：**每合成完一幕，就用该幕的真实时长重算 beat 帧位、逐镜抽帧目检**。
做法（`out/draft.mp4` 还不存在时也能做，走 `remotion still` 而非 `qa_frames`）：

1. 混合 manifest：已合成句用 `mutagen` 读实测时长，未合成句按**实测语速**外推
   （首集可用 300 字/分 ÷ 60 = 5 字/秒起步，跑出几十句后改用本集实测值）；
2. 用 `timeline.compute()` 算 beat 帧位（与 `timing.ts` 同构，见 `timeline.py`），
   取每镜中点 + 关键转折句的帧号；
3. `remotion still Main out.png --frame=N --scale=0.4` 逐帧渲（**首帧含打包约 100 秒，
   之后走缓存仅 4–5 秒**，全片 39 镜可负担）；
4. 灰度均值扫一遍查黑帧/重复帧，再人眼看构图与语义。

步骤 1–3 已机械化：`uv run --no-project $T/pipeline/scripts/qa_frames.py --project $P --stills-plan
[--chars-per-sec 5]`（零依赖、不需视频）按混合时间轴逐镜打印 `remotion still` 命令，复制即可执行。

**为什么必须用真实时长**（本集实测，等长外推下三处全部漏检）：

| 缺陷类型 | 症状 | 漏检原因 |
|---|---|---|
| 动画时点写死帧数 | 「三组都排完了，旁白才说到第一组」 | 外推时长恰好对齐，真实时长下错位 |
| 一次性动效 vs 持续陈述 | 冲击波 16 帧衰减完，而该句 4 秒多 → 画面大半时间静止 | 静帧恰好落在动效发生的瞬间（建模方法见[手册 M-003](../MODELING-PLAYBOOK.md)） |
| 画面语义与旁白相反 | 堆叠方向反了，画面说「全局配置最大」而旁白说「公司策略最大」 | 与时长无关，但只有抽帧看清「哪一格被高亮」才发现（反模式见[手册 X-001](../MODELING-PLAYBOOK.md)） |

**纪律**：beat 内的动画时点**一律由句边界推导**（`rel(beat, '句id')`），不得写死帧数——
配音时长一变就脱钩。例外只有「beat 开头即出现的常驻角标」。

## 修复回路

问题 → 改场景组件（或分镜/文稿）→ `tsc --noEmit` → 重草渲 → 复抽帧。**禁止跳过复检直接终渲**。
草渲前若已做过分幕复检，草渲阶段主要验「整片连续性」（转场、字幕带、幕间呼吸），
单镜构图类问题应在复检阶段就已清零。
**建模信号当场留存**：复检中用户对某个建模方法明确认可或否决（且可跨集复用）时，往
[建模手册](../MODELING-PLAYBOOK.md)「候选区」追加一行（`〔+用户〕` 或 `〔-用户〕<集目录名>#<镜号>：…`），不改条目——策展按
[RSI.md](../../RSI.md) 第十节在交付后攒批执行。
