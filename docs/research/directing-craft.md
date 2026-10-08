# 导演手艺知识库的引入：调研综合、方案比选与数据契约 roadmap

> **结论先行**：以按需读取的工艺层知识库（[references/DIRECTING-CRAFT.md](../../references/DIRECTING-CRAFT.md)）承载「怎么导」的导演知识（景别/运镜/转场/节奏/构图/动画原则），五个阶段规格只注入指针+核心规范；镜头语言用约定写法落位（`@shot:` 景别落画面列——`check_script.py` 的 `--check-motion` 只读动效列 `cells[3]`，零 parser 改动）；机械门族（词表门/eye-trace/read-time lint）作为后续 RSI roadmap 显式存证于本文，「先有数据再有门」。协议：RSI-048（[台账](../.agents/issue.md)）。

## 一、问题：夹缝层的系统性缺失

双 Explore 实证（2026-10-07）：`景别`/`运镜`/`anticipation`/`staging`/`eye-trace`/`转场语义`/`视觉节奏曲线` 在 references/scripts/tests/SKILL **全仓零命中**。既有视觉质量资产是「实战事故驱动的补丁式积累」（四定式 RSI-032、Visual Hook RSI-039、Morph Continuity、MODELING-PLAYBOOK）——每条有实证锚点但无理论坐标系组织，未知失败形态（节奏均质化、焦点漂移、眼动跳切、镜头无动机）无判据可依。

**夹缝定位**：08 运动层（frozen）管「怎么动」的机制正确；MODELING-PLAYBOOK 管「画什么」的策略经验；[03:99-107](../../references/03-narration.md) 已有**声音表演导演学**（故事弧分块+情绪起伏曲线+表演标点）——「怎么导」（镜头语言层）恰是两者都不管的夹缝，且视觉侧没有声音侧导演学的对应物。

## 二、六路调研 → 落位映射（17 原则）

调研维度：动画十二原则（Disney）[1] / 镜头语言（cinematography for motion graphics）/ 剪辑与节奏（Murch [2]、认知心理学 [3]）/ 视觉叙事（Kurzgesagt、3B1B 访谈、信息可视化文献 [4][7][8]）/ 科普频道方法论（TED-Ed、Veritasium——misconception-first 实证 [6]）/ 导演工作流（Pixar 访谈、storyboard 教学 [9]）。综合排序 17 条原则——完整索引表见 DIRECTING-CRAFT 头部（原则 → 手册节 → 执法面三列映射），此处只记映射决策：

| 调研原则簇 | 既有纹理可挂靠 | 零覆盖需新建 |
|---|---|---|
| 旁白锚定时序 | 08 铁律「`rel(beat,'句id')` 句边界推导」 | 词级落点（Land on the Word）、画面先行 0–0.5s [5] |
| Overview-First | 四定式 1「全景坐标先行」 | 回看密度规则（每 2–3 局部镜回拉全景） |
| 消融对比/基线标尺 | 四定式 3/4 | — |
| 情绪曲线 | 03 声音导演规则 | 视觉张力曲线（景别行程、呼吸幕） |
| 隐喻角色化 | MODELING-PLAYBOOK 策展回路 | 隐喻注册表（02 视觉语言节增量） |
| 运镜/景别/转场 | `@动词` 词表 + pushIn 唯一先例 | 五档景别、动机律、转场语义三分法 |
| 节奏系统 | 记忆点 60–90s | 1/f 长短交替、时长底线、重音镜、呼吸幕 |
| 动画原则 | DUR 六档/easing 四条/spring 三档（token 已备） | AAS、Suppression、Eye-Trace 判据 |
| 数据本体红线 | 3D「弹簧过冲要钳行程」实践 | 泛化为 2D 全域红线 |

## 三、方案比选（G2）

### 3.1 知识落位比选

| 方案 | 取舍 | 决策 |
|---|---|---|
| A 知识库 + 指针注入（新建 references/DIRECTING-CRAFT.md，规格只带指针+核心规范） | 大写跨阶段手册家族先例（VOICE-CLONING 551 行 / INDEXTTS 784 行）；按需读取不常驻；08 已 6150 字全仓最大，继续追加 bury 新知识于中段（长上下文中段利用率下降） | **采纳** |
| B 全写进各阶段规格正文 | 违反 RSI.md:129 转移熵禁令精神；02「六节节名不动」gate 约束 | 否决 |
| C 进 MODELING-PLAYBOOK | 定位不同（建模=策略层经验、导演=语言本体）；手册 CAP=3000 撑不下；未验证的调研知识不是「经验条目」（不变量 15 精神——证据驱动策展） | 否决 |

### 3.2 镜头语言标注落位比选

| 方案 | 取舍 | 决策 |
|---|---|---|
| A 约定写法：`@shot:` 落画面列（archify 标注同列先例）、运镜复用动效列 `@动词`+动机散文 | **零 parser 改动**（check_motion 只读 cells[3]——check_script.py:973 实证）；误写动效列得「不在词表」WARN=免费护栏 | **采纳（本期）** |
| B 扩第六列（Camera 列） | Visual Lock「第 5 列=人工契约」定位被稀释；三份表格面同步；景别是画面属性与验收契约语义不符 | 否决 |
| C parser 扩展（`@cam/@frame/@focus` 落动效列 + parse_shot_tags + 词表门） | 执法强，但 `@cam:pushIn@p2-04` 不剥离时 MOTION_TAG_RE 污染出 `['cam','p2']` 双假动词（正则实测）——剥离顺序修正必须钉死回归；改动面大 | **deferred（roadmap）** |

### 3.3 交付形态比选

| 方案 | 取舍 | 决策 |
|---|---|---|
| 单 RSI-048（知识+约定+目检，零机器门） | 最小干预；首集实践产出校准数据 | **采纳** |
| 三期 RSI-048/049/050（契约→知识→门） | 执法强但公式常数未经本仓校准（eye-trace 九宫格/read-time 公式误报风险中级）；ISSUE-167/188 前车之鉴（假 WARN 毁信噪比） | 降级为 roadmap |

## 四、数据契约 roadmap（后续 RSI 的显式设计——本期不实施）

**「先有数据再有门」顺序论证**：本期约定写法先落，首集 `@shot` 实际使用率与失约样本恰是未来门族的校准输入；未校准的公式直接上门有 ISSUE-167（判据必须先在干净帧上验证零报警）与 ISSUE-188 的前车之鉴。

**触发条件**（满足其一即评估立项）：
1. ≥2 集实际使用 `@shot` 标注（有数据可校准）；
2. 出现「约定失真」事故（拼错档位无护栏漏到成片 / 运镜动机缺失成片后才发现）；
3. `tts.py` 词级时间戳（WordBoundary）落地（Land on the Word 机械审计的前置）。

**契约设计存证**（Plan B 调研产出，直接可用）：

```
动效列（第 4 列）标注族（与 @动词 同格同列）：
  @cam:<move>[@<句id>]   move ∈ {hold, pushIn, pullOut, pan, settle, tracking}
                         move≠hold 必须带动机锚句 id（锚句不存在 → FAIL，ISSUE-190 同类）
  @frame:<tier>          tier ∈ {ECU, CU, MS, WS, EWS}
  @focus:<cell>          cell ∈ 九宫格 {C,L,R,T,B,TL,TR,BL,BR}
  @stagger:<n>           波次数（read-time 预算输入）
  eye-trace-ok: <理由>   豁免注记（caption-dup-ok 立场：逃逸口必须存在且被记录）

门族（check_script.py，zh 完整门缺省）：
  [cam-vocab]      WARN   词表外 move（封闭枚举，声明了才管）
  [cam-anchor]     FAIL   动机锚句 id 不在 narration.json（渲染期才炸的跳号引用）
  [cam-motivation] WARN→FAIL（校准后晋升）  move≠hold 无锚句
  [eye-trace]      WARN   幕内相邻镜焦点 Chebyshev ≥2 格且无 pan/tracking 引导/豁免
  [read-time]      WARN   beatSec < 1.5 + 元素数×0.8–1.2（元素数取 @stagger:n，缺省 distinct @动词数）
报告（qa_frames.py）：--pacing  exit 0——逐幕 beat 时长表/方差/pattern-interrupt 密度

parser 顺序修正（必钉回归测试）：parse_motion_tags 先剥离 @cam/@frame/@focus 前缀 token
再跑 MOTION_TAG_RE——否则 @cam:pushIn@p2-04 污染出 ['cam','p2'] 双假动词（正则实测确认）。
词表 SSOT = check_script.py 模块常量 + docstring（check_playbook 常量先例）；
未来 frozen 相机原语落地后词表迁 hooks.ts use* 派生（与 @动词 同构）。
```

**frozen 化触发条件**（08 注入条款的存证）：≥2 集真实使用 pullOut/pan 且评审出现「组合约定失真」事故 ⇒ 另立 RSI 评估（届时 `@cam` 实现对账并入 `--check-motion`）。

## 五、撤销条件与已知局限

- **撤销条件**：若 `@shot` 约定在 ≥3 集中零使用（Agent 不认领），说明约定写法的摩擦大于价值——撤销画面列约定、改走 roadmap 的动效列契约或纯目检路线；DIRECTING-CRAFT 知识本体不受影响（§二–§七判据独立于标注形态）。
- **已知局限**：① `@shot` 拼写错误本期无机器护栏（目检兜底）；② read-time 公式常数（1.5s 基线、0.8–1.2s/元素——segmenting 口径 [3]；13 CPS——通用阅读速度估值）来自文献未经本仓校准，仅作人工判据参考；③ eye-trace 「1/3 屏宽」是文献阈值的一维近似 [2]，帧上人工判读有主观带；④ 声音 cue 轨（原则 17）不落地——BGM 留空轨是 02「不做的事」既有边界，推翻须用户决策。

## References

[1] F. Thomas and O. Johnston, *The Illusion of Life: Disney Animation*. New York: Disney Editions, 1981（动画十二原则原始出处）.
[2] W. Murch, *In the Blink of an Eye: A Perspective on Film Editing*, 2nd ed. Los Angeles: Silman-James Press, 2001（剪辑六律、eye-trace）.
[3] R. E. Mayer, *Multimedia Learning*, 3rd ed. Cambridge: Cambridge Univ. Press, 2020（redundancy/signaling/segmenting 原则）.
[4] J. Heer and G. Robertson, "Animated transitions in statistical data graphics," *IEEE Trans. Vis. Comput. Graph.*, vol. 13, no. 6, pp. 1240–1247, 2007（动画转场优于静态跳切的实证）.
[5] ITU-R BT.1359-1, *Relative time-advance of sound with vision*. Geneva: ITU, 1998（音画异步感知不对称阈）.
[6] D. E. Muller, "Designing effective multimedia for physics education," Ph.D. dissertation, Univ. of Sydney, Sydney, Australia, 2008（clear-explanation 零增益与 misconception-first 三段式实证——Veritasium 创始人的博士研究）.
[7] J. Hullman, "Why authors don't visualize uncertainty," *IEEE Trans. Vis. Comput. Graph.*, vol. 26, no. 1, pp. 10–14, 2020（图解叙事的注意力引导）.
[8] B. Tversky, J. B. Morrison, and M. Bétrancourt, "Animation: Can it facilitate?," *Int. J. Hum.-Comput. Stud.*, vol. 57, no. 4, pp. 247–262, 2002（动画有效性的边界条件——时机与编排）.
[9] Kurzgesagt 团队制作流程与色彩策略的公开分享 [Online]. Available: https://kurzgesagt.org/；3Blue1Brown（G. Sanderson）关于 Manim 设计哲学与动画作为注意力语言的公开访谈 [Online]. Available: https://www.dwarkesh.com/p/grant-sanderson；TED-Ed 动画协作模式（educator–animator collaboration，动画承载讲解的一部分）[Online]. Available: https://ed.ted.com/。
