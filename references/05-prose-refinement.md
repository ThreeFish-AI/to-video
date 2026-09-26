# Stage ⑤ 成文优化（skill 规格 · 05）

> Stage ⑤：把已过 ④ 双重校验的稿子，改成**像人写的、适合人读也适合人听**的样子。本文件是优化代理的提示词规格，可直接作为子代理 prompt 底稿；规则的研究依据与语料取证见 [docs/research/prose-refinement.md](../docs/research/prose-refinement.md)。
>
> **一句话边界**：④ 判「对不对、懂不懂」，⑤ 只改「顺不顺、像不像人」——**只改表达，不改事实**。

**目录**：一、定位与输入输出 · 二、硬约束护栏 · 三、四层 pass · 四、逐字稿专属规则 · 五、策划案专属规则 · 六、研究笔记专属规则 · 七、分镜专属规则 · 八、中文去机器味检查表 · 九、改动审计与复核 · 十、验收 · 参考文献

## 一、定位与输入输出

**病在哪**：AI 逐段生成时没有全局篇章规划，每段只顾自己通顺，段与段之间的承接、话题的延续、开头抛出的问题有没有兑现，都没人负责。结果就是句句都对，连起来却断断续续。真实语料里这类稿件的书面腔禁词几乎为零，病灶在篇章结构层，不在词汇层（取证数据见研究文档 §一）。所以修稿必须**自顶向下**：先改结构，再补衔接，然后改句子，最后才改词。只改词汇就像只把表面擦干净，文章没有变好 [1]。

| 稿件 | 路径 | 何时优化 | 读者 |
|---|---|---|---|
| 逐字稿 | `script/narration.md` | ④ 清零后（本阶段主对象） | 听众（耳朵）+ 协作者（眼睛） |
| 策划案 | `script/planning.md` | 同上 | 协作者与后续代理 |
| 研究笔记 | `research/paper-notes.md` / `source-notes.md` | 同上 | 后续代理与复核者 |
| 分镜 | `script/storyboard.md` | ⑥ 写完、定稿前回调本规格第七节 | 场景实现者 |

- **原地改稿**，不另存「优化版」副本——副本就是第二事实源。
- 双语集只优化主稿；en 译稿随基线锁联动（第二节第 6 条）。
- 可由独立子代理执行（fresh context，只给本规格 + 待改稿件 + 事实源），与 ④ 同理，避免写稿者自评自改。

## 二、硬约束护栏（任何一层 pass 都不得越过）

1. **事实冻结**：数字、单位、年份、人名/系统名、限定词（约 / 可能 / 至多 / 官方自报 / 有研究者逆向）、三级证据归属句，一个字都不动。改写后的句子必须还能回溯到事实源的同一条目。
2. **句 id 冻结**：不增、不删、不重排、不改 id。本阶段对逐字稿只做 beat 分组与相邻 id 之间的文本重分配（第四节第 8、9 条），不做结构性增删。需要拆句、并句、调序或补句时（如 L1 发现缺「转」、开头的问题没有兑现），停下来回到 ③ 处理（插句用字母后缀 `p2-37b`），改过的句子连同此前已做的 ⑤ 改动一起重过 ④，并同步分镜；回来后按第九节第 1 步重新留底再继续。
3. **格式契约**：一句一行 `- [id] 文本`；单句 8–35 字为宜、不超过 40 字（[03](./03-narration.md)）；`## Pn 幕标题` 的标题文字就是章节条标签，保持 2–8 字名词短语。
4. **读法与标注**：不得写出 [READING_TRAPS](./03-narration.md) 禁写形态；`<原文|读音>` 标注原样保留（改写所在句时标注随原字走）。
5. **跨门约束**：系列纪律（不出现他集标题与序号词，[check_series.py](../scripts/check_series.py)）；改口播句可能新触发或解除画面文字复述门（[06](./06-storyboard.md)「画面文字不复述口播」；只在分镜与场景已存在时触发）——改完按第九节第 5 步重跑机器门。
6. **下游代价知情**：已配音的集，逐句档改一句重配一句；story 档（新集默认配音）以故事块为缓存单位，改一句重录它所在的整块（[VOICE-CLONING §4.5](VOICE-CLONING.md)）。配音台本 `script/narration.cues.toml` 的 `[say]` 须去标点后与正文全等：改了字的句若有 `say` 条目，同步改字、保留其表演标点与发音标注，否则 `build` 直接 FAIL；表演标点属配音层，不按第八节 Z9 处理。双语集改了主稿，`check --lang en` 会点名失配句 → 重译该句并过 [④C 译文保真](./04-verification.md)，或确认无需改动后 `build --lang en --accept <ids>`。
7. **宁缺毋滥**：没有问题的段落**原样保留**。改动要有规则依据（第九节），不因「换个说法也行」而改。

## 三、四层 pass（按编辑行业层级映射，自顶向下，逐层完成再进下一层）

专业编辑把改稿分成四层，每层各管一件事、互不越界 [2]。本阶段照此执行；**上层问题不许用下层手段掩盖**（结构断裂不能靠加连接词修）。

| 层 | 对应编辑层级 | 改什么 | 不改什么 |
|---|---|---|---|
| **L1 结构** | developmental | 篇章骨架、幕/节/段的顺序与分组、缺失的「转」、开头问题有没有兑现（逐字稿调序、补句回 ③，见第二节第 2 条） | 句子措辞 |
| **L2 衔接** | —（line edit 前半） | 段与段之间的桥、句与句之间的已知→新知流向、话题链 | 事实与分组 |
| **L3 句子** | line edit | 句长节奏、语调单位、名词化、欧化句式 | 段落结构 |
| **L4 词句** | copyedit / proof | 套话、四字格、机械排比、标点、朗读测试 | 句子骨架 |

### L1 结构 pass

1. **先写骨架再动手**：给每幕（或每节）写一句话概括，按顺序连读。连读不通，就是结构问题，先调结构 [3]。
2. **按文体选骨架**，不混用 [3][5]：
   - 叙事、讲解（逐字稿）：钩子 → 问题 → 展开 → **转折** → 揭示 → 收束（起承转合；「转」最常缺，没有它就只是平铺）[5]；
   - 说明、汇报（策划案、研究笔记）：结论先行，下面分组支撑（金字塔原理：上层概括下层、同组同类、组内有序）；
   - 问题类内容：情境 → 问题 → 回应 → 评价（SPRE）[5]。
3. **一段一念**：一个自然段（逐字稿里即一个 beat）只讲一个要点；中途换焦点就另起一段 [6]。
4. **问题要兑现**：开头或幕首抛出的问题，必须在后文明确回答；答不了的，要说明为什么留作开放问题。

### L2 衔接 pass

1. **段间桥**：新段的第一句要接住上一段最后引出的概念，再往前推 [7]。连续两次没接住，读者就会觉得断。
2. **已知在前、新知在后**：每句开头放读者已知道的，句尾放新的信息；句尾是强调位，要记住的东西放在那里 [7][8]。
3. **话题链**：相邻几句的主语尽量指向同一个对象；要换话题，用一句明确的过渡来换，每段最多换一次 [8]。
4. **删掉每段自带的小结**：段末只是把段首换个说法重复一遍的，删掉；收尾句要么推进一步，要么引出下一段。
5. **先调语序，再考虑加连接词**：语序对了，最好的过渡往往是不加任何过渡词 [9]。

### L3 句子 pass

1. **长短交替**：连续三句长度差不多，就打散；关键结论用短句收住 [10]。
2. **动作放动词**：「进行了分析 / 作出了贡献」还原成「分析了 / 贡献了」；主语用具体的人和物，不用一串抽象名词 [8][11]。
3. **嵌套不超过一层**：一句里套两层以上从句就拆开 [12]。
4. **中文按意合写**：逻辑能靠语序和话题链表达的，就不用「因此 / 然而 / 此外」[11][13]。
5. **流水句是合法的**：一个小句接一个小句、按时间或事理铺开，是中文的正常写法，不要按英文 run-on 的标准去判罚；真正要修的是超过四个小句还没句号、话题中途断掉、主语悄悄换了的那种 [4][13]。

### L4 词句 pass

对照第八节检查表逐条过；最后做**朗读测试**：逐句念出声，念着绊嘴、换不过气、听着别扭的句子，重写 [14]。

## 四、逐字稿专属规则（为耳朵写，也为眼睛排版）

逐字稿同时有两类读者：观众只听一遍、不能回放；协作者和后续代理要读它、改它、按它切镜。两个面都要照顾到。

**听觉面**（BBC / NPR 等广播写作规范高度一致 [14][15]）：

1. **一次一个新想法**：人说话时，一个停顿单元大约只装一个新信息点 [16]；一句话里塞两个新概念，就拆成两句。
2. **写给一个人听**：可以直接称呼「你」，用修辞问句带着观众走（「你想想……」）；这是口语的参与感，不是随意 [16]。
3. **用口语的路标词**：段与段之间用「那么 / 接下来 / 但问题是 / 回到刚才那个问题」这类导航词，不用「综上所述 / 此外 / 然而」这类论文连接词 [17]。
4. **先摆出直觉，再纠正**：讲一个反直觉的机制时，先说出观众大概率会有的直觉判断（「你可能会觉得……」），再用证据推翻它。研究表明，讲得清楚流畅的科普视频反而没有学习增益，先暴露误解再纠正的效果显著更好 [18]。注意这里的「困惑」是刻意安排的，和文稿本身断断续续造成的困惑是两回事。
5. **开环与回扣**：幕首抛出的问题就是一个开着的环，在本幕或后续幕里关上；全片结尾回到开场的问题或意象，形成闭环 [19][20]。
6. **类比要交代边界**：用熟悉的事物作锚点解释新概念，并说明这个类比在哪里不成立，否则类比本身会变成新的误解 [21]。
7. **数字要落地**：一句最多一个数字；大数字配一个具体参照；精度仍遵守 03「数字精确」纪律，不为了顺口而改数。

**阅读面**（本阶段新增，零机制成本）：

8. **幕内用空行分 beat**：一幕之内按「一个想法一段」用空行分组，每组 2–8 句，对应 ⑥ 分镜的一个镜头。`build` 只识别幕标题行和句行，空行与 `>` 备注一律跳过，所以分段不影响派生物、配音与字幕。
9. **不许把一句话硬切成两行**：以逗号或顿号收尾、语义要到下一行才完整的句子，在**原有两个 id 之间重新分配文本**，让两行各自是完整的一句（例：「它能读懂你的需求，翻遍整个代码仓库，」＋「一次修改好几个文件……」→「它能读懂你的需求，翻遍整个代码仓库。」＋「它还能一次改好几个文件……」）。两行确实只够说一件事、无法各自成句时，属于并句，按第二节第 2 条回 ③ 处理。已有分镜的集（`script/storyboard.md` 已存在）搬运前，先在分镜与 `video/src/scenes/` 里 grep 涉及的 id：被搬走的那段话若有画面锚在原 id 上（分镜画面列点名的内容、场景里 `rel(beat,'句id')` / `at()` 的时点、archify cue 的锚句），要么同步改分镜与场景、让画面跟着文字走，要么放弃搬运、原样保留——`check` 只查覆盖与逐字复述，查不出画面比口播早一句或晚一句的错位。
10. **悬置只留给真悬念**：以冒号、破折号收尾、下一行才给答案的写法，只在真正需要停顿制造悬念的地方用，其余改成一句说完。
11. **幕尾钩子保留**：03 纪律要求每幕结尾留半句悬念钩到下一幕——这是结构性的，本阶段不删，只检查它和下一幕开头确实接得上。

**与配音分块的关系**：story 档（新集默认配音）按故事块合成，块（≤3 句 / ≤90 字）是配音单位，beat（2–8 句）是阅读与画面单位，块嵌套在 beat 之内，二者不冲突。beat 边界也应是块边界：分好 beat 后复查台本的 `[block.<id>]` 块起点（[03](./03-narration.md)「配音台本」），每个 beat 的首句都应是块起点；无台本时的自动分块不读空行，块界可能跨 beat，属兜底可接受。

## 五、策划案专属规则

1. **结论先行**：每节第一句就是该节的结论；叙事策略节最前面用一句话写清全片主线（logline：主体 + 冲突 + 钩子，不超过 40 字）[22]。
2. **六节节名不动**（[02](./02-planning.md) 的通过门），节内小标题写成**判断句**而不是话题标签：「P2 的难点是……」而不是「P2 难点」。只读小标题连起来，应能还原全片论证 [23]。
3. **分幕结构表的「叙事要点」列**写成一句完整的因果或转折，而不是名词堆叠。
4. **「边界与不做的事」要写出取舍和理由**（「不讲 X，因为 Y」）——没有立场是 AI 策划案最明显的特征之一。
5. 删掉换一个选题也成立的通用段落。

## 六、研究笔记专属规则

1. 每章「主旨综述段」结论先行：第一句写这一章解决了什么问题、得出了什么结论，再展开。
2. 断言按它们回答的问题分组，组内按重要性排序；同一概念全文只用一种译名。
3. **不动取证锚点**：英文原句、图表号、§ 章节号、页码、证据等级标注一律原样——④ 和后续核查都靠它们回溯。
4. 「科普叙事素材」段是逐字稿的原料库，只整理顺序，不删条目。

## 七、分镜专属规则（⑥ 写完、定稿前执行）

1. **画面列与动效列用现在时、主动语态，只写看得见、听得见的东西**：写「蓝色卡片从左侧滑入，第三行高亮」，不写「优雅地展示了……」「让观众感受到……」[24]。
2. **旁白讲画面给不了的**：画面已经呈现的，旁白不再描述；画面文字只放关键词、数字、标签、结构，不复述整句口播——同时呈现画面、旁白和同一句屏幕文字，会增加认知负担而不是强化记忆（多媒体学习的冗余原则）[25][26]。这与 [06](./06-storyboard.md) 的复述口播门同源，门只拦逐字重复，语义重复要靠本条。
3. **镜头名写画面主体**（「小判断清单」「让作家盖章」），不写抽象话题（「背景介绍」）。
4. **不动机器可读部分**：句区间、archify 标注串、〔M-xxx〕、`@动词`、`caption-dup-ok` 注记一律原样——它们是覆盖门与策展计数的输入。

## 八、中文去机器味检查表

只在命中「特征簇」时动手，单个特征人类也会用 [1][27]。

| # | 特征 | 改法 | 依据 |
|---|---|---|---|
| Z1 | 抽象名词做主语、「的的不休」（「他收入的减少改变了他的生活方式」） | 还原成动词短句（「他收入少了，生活方式也变了」） | [11] |
| Z2 | 弱动词（进行 / 作出 / 给予 + 名词） | 直接用动词 | [11] |
| Z3 | 公式化对译（「当……的时候」「关于……」「作为……的它」「最……之一」） | 删掉或改中文常态说法 | [11] |
| Z4 | 被字滥用、「被人们所……」 | 改主动句；「被」只留给真正的受害义 | [11] |
| Z5 | 显性连接词成串（此外 / 同时 / 并且 / 然而） | 靠语序衔接；每段至多一个 | [9][13] |
| Z6 | 「首先……其次……最后」机械排列 | 用内容本身的因果、转折、递进来串 | [1][27] |
| Z7 | 「不是 X，而是 Y」反复出现 | 全片只保留真正需要澄清误解的几处 | [1][27] |
| Z8 | 三项并列、三组四字格成排出现 | 改成两项或四项，或取消平行结构；四字格同义只留最准的一个 | [1][27] |
| Z9 | 破折号、冒号当默认标点 | 只在转折、打断、真悬念处用 | [1] |
| Z10 | 空洞拔高（至关重要 / 深刻改变 / 赋能 / 彰显 / 画卷） | 换成具体数字、名字或例子；给不出就删 | [27][28] |
| Z11 | 每段结尾一句总结 | 删掉，或改成引出下一段的钩子 | [1] |
| Z12 | 段落长短一样、句式一样 | 按内容轻重拉开详略 | [10][29] |
| Z13 | 口播稿里混入书面连接词（因此 / 此外 / 倘若） | 所以 / 还有 / 如果 | [15][17] |

## 九、改动审计与复核

1. **改前留底**：留底是第 4 步复核范围与 RISKY 回退原文的唯一来源，没有留底不得开始改稿。待改稿件在 ④ 清零时已 commit 的，开工前用 `git rev-parse HEAD` 记下基准 SHA，之后一律以 `git diff <基准SHA> -- <路径>` 定位改动、`git show <基准SHA>:<路径>` 取回原文——不写 `HEAD`：⑤ 中途任何一次提交（三稿分开交、评审轮之间提交）都会让 HEAD 移走，更早的改动随之漏出复核范围，回退也只能取回改了一半的文本；否则一律改前复制到 `$P/.temp/prose-before/`，事后清理——新集稿件此时多半还未被 git 跟踪，`git diff` 看不到未跟踪文件，未提交的改动也会与 ③④ 的修改混在一起。不拿暂存区当留底：改稿中途再 `git add` 一次，底就被覆盖了。
2. **改动表**：每处改动一行——`句 id 或位置 | 规则编号（如 L2-1、四-9、Z5）| 一句理由`。规则编号引用本规格的节号与条号。按第四节第 9 条在相邻 id 间重新分配文本的，涉及的几个 id 合写一行（如 `p0-02+p0-03`），这一行即一个回退单元。
3. **成文评审**：改稿者不自评。另起独立子代理（fresh context，只给本规格 + 改后稿件 + 改动表），对照第三至第八节的具名规则与第十节前三项通读全稿；每个问题一行 `位置 | 规则编号 | 理由`，判 REWRITE。给不出规则编号的意见不构成 REWRITE（同第二节第 7 条）。改稿者逐条修正并追加进改动表，再送评审，直到 REWRITE=0。
4. **改动句复核**：以改前留底为基准，只对最终改动过的句子（含评审后的修正）回到 [④](./04-verification.md) 复核：A 节四级判定全做——研究笔记的改动句锚点换成信源原文（A 型 `paper_extract.py find` 定位原文措辞，B 型按 `research/sources.toml` 登记的 URL 回查），笔记本身是 ④A 的事实源，拿它核自己等于没核；B 节前三条（术语降落、指代距离、抽象连段）连同改动句的前后句一起看——话题链改主语、跨 id 搬运文本最容易在这三条上退步。门槛与 ④ 同口径：RISKY 与未处理 REWRITE 均须为零。判 RISKY 即回退原句；回退以改动表的行为单元，同一行的几个 id 整组回退原文——只回退其中一句，被搬运的文本会丢失或重复。回退句不再送评审（事实优先）；判 REWRITE 则按 ④ 修正后复核该句。未改动的句子不重复核查。
5. **重跑机器门**：`uv run --no-project $T/scripts/pipeline.py --project $P build`；分镜已存在时再跑 `check`（双语集会同时点名 en 失配句，按第二节第 6 条处理）。新集此时还没有 `storyboard.md`，`check` 会直接退出，改跑 `uv run --no-project $T/scripts/check_script.py --project $P --pre-tts`（时长预算、读法陷阱、发音标注）；双语集另跑同一脚本的 `--lang en`（en 门不读分镜）点名失配句。完整 `check` 留到 ⑥ 分镜写完后。
6. **版本标注**：逐字稿头部改为 `（vN，已过双重校验与成文优化）`，版本号加一。

## 十、验收

- [ ] 连读每幕 / 每节的一句话概括，论证链完整；开头的问题都有兑现或明确留作开放问题；
- [ ] 逐字稿每幕都已用空行分 beat；没有逗号、顿号收尾的半句；冒号、破折号悬置只剩真悬念；
- [ ] 逐句朗读通过，没有念不顺的句子；
- [ ] 改动表每行都有规则编号；成文评审 REWRITE=0；改动句复核 RISKY=0、REWRITE=0；
- [ ] `build` + 机器门零 FAIL（分镜已存在跑 `check`，新集跑 `check_script.py --pre-tts`，见第九节第 5 步）；句 id 集合与顺序与优化前完全一致（回过 ③ 的，以重新留底时为准）；
- [ ] 已有分镜的集：跨 id 搬运涉及的 id 已回查分镜与场景锚点，画面与改后文字对得上（第四节第 9 条）；
- [ ] **通过门：成文评审 REWRITE=0 且改动句复核 RISKY=0、REWRITE=0**。

## 参考文献

[1] Wikipedia contributors, "Wikipedia:Signs of AI writing," WikiProject AI Cleanup. [Online]. Available: https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing

[2] Editorial Freelancers Association, "Editorial Service Definitions." [Online]. Available: https://www.the-efa.org/editorial-services-definitions

[3] B. Minto, *The Pyramid Principle: Logic in Writing and Thinking*, 3rd ed. London, U.K.: FT Prentice Hall, 2009.

[4] 吕叔湘, 《汉语语法分析问题》. 北京: 商务印书馆, 1979.（「流水句」概念的提出）

[5] M. Hoey, *On the Surface of Discourse*. London, U.K.: George Allen & Unwin, 1983.（Problem-Solution / SPRE 范式；与起承转合的「转—合」同构）

[6] Purdue OWL, "On Paragraphs," Purdue Univ. [Online]. Available: https://owl.purdue.edu/owl/general_writing/academic_writing/paragraphs_and_paragraphing/index.html

[7] H. H. Clark and S. E. Haviland, "Comprehension and the given-new contract," in *Discourse Production and Comprehension*, R. O. Freedle, Ed. Norwood, NJ, USA: Ablex, 1977, pp. 1–40.

[8] J. M. Williams and J. Bizup, *Style: Lessons in Clarity and Grace*, 13th ed. Boston, MA, USA: Pearson, 2021.

[9] UNC Writing Center, "Transitions." [Online]. Available: https://writingcenter.unc.edu/tips-and-tools/transitions/

[10] G. Provost, *100 Ways to Improve Your Writing*. New York, NY, USA: Mentor, 1985.

[11] 余光中, 〈怎样改进英式中文——论中文的常态与病态〉, 《明报月刊》, 1987 年 10 月. [Online]. Available: https://language.chinadaily.com.cn/a/201509/01/WS5b20a851a31001b825720b30.html

[12] F. Karlsson, "Constraints on multiple center-embedding of clauses," *J. Linguistics*, vol. 43, no. 2, pp. 365–392, 2007.

[13] 沈家煊, 〈"零句"和"流水句"——为赵元任先生诞辰120周年而作〉, 《中国语文》, 2012, no. 5, pp. 403–415.

[14] C. Joyce, "Campfire tales: The essentials of writing for radio," NPR Training, 2015. [Online]. Available: https://training.npr.org/2015/03/20/campfire-tales-the-essentials-of-writing-for-radio/

[15] BBC News School Report, "Radio news tips." [Online]. Available: http://news.bbc.co.uk/2/hi/school_report/5275764.stm

[16] W. Chafe and J. Danielewicz, "Properties of spoken and written language," in *Comprehending Oral and Written Language*, R. Horowitz and S. J. Samuels, Eds. San Diego, CA, USA: Academic Press, 1987, pp. 83–113.

[17] D. Schiffrin, *Discourse Markers*. Cambridge, U.K.: Cambridge Univ. Press, 1987.

[18] D. A. Muller, J. Bewes, M. D. Sharma, and P. Reimann, "Saying the wrong thing: Improving learning with multimedia by including misconceptions," *J. Comput. Assist. Learn.*, vol. 24, no. 2, pp. 144–155, 2008, doi: 10.1111/j.1365-2729.2007.00248.x.

[19] G. Loewenstein, "The psychology of curiosity: A review and reinterpretation," *Psychol. Bull.*, vol. 116, no. 1, pp. 75–98, 1994.

[20] B. Snyder, *Save the Cat!* Studio City, CA, USA: Michael Wiese Productions, 2005.

[21] J. Clement, "Using bridging analogies and anchoring intuitions to deal with students' preconceptions in physics," *J. Res. Sci. Teach.*, vol. 30, no. 10, pp. 1241–1257, 1993, doi: 10.1002/tea.3660301007.

[22] Adobe, "Creative briefs: How to write, examples, and best practices," 2025. [Online]. Available: https://business.adobe.com/blog/basics/creative-brief

[23] SlideSpeak, "How to make a McKinsey-style presentation." [Online]. Available: https://slidespeak.co/blog/mckinsey-style-presentation

[24] N. Zeigler, "Screenplay formatting essentials," in *Scriptwriting for Video, Broadcast, and Digital Media*, §9.1. Laney College, Humanities LibreTexts, 2026. [Online]. Available: https://human.libretexts.org/Courses/Laney_College/Scriptwriting_for_Video_Broadcast_and_Digital_Media_(Zeigler)/09%3A_Formatting/9.01%3A_Screenplay_Formatting_Essentials

[25] R. E. Mayer, *Multimedia Learning*, 3rd ed. Cambridge, U.K.: Cambridge Univ. Press, 2020.

[26] M. Rabiger and C. Hurbis-Cherrier, *Directing the Documentary*, 7th ed. New York, NY, USA: Focal Press, 2020.

[27] Pangram Labs, "A comprehensive guide to spotting AI writing patterns." [Online]. Available: https://www.pangram.com/blog/comprehensive-guide-to-spotting-ai-writing-patterns

[28] D. Kobak, R. González-Márquez, E.-Á. Horvát, and J. Lause, "Delving into LLM-assisted writing in biomedical publications through excess vocabulary," *Sci. Adv.*, vol. 11, no. 27, eadt3813, 2025.

[29] Z. Shan, Y. Lee, and S. Hao, "AI writers have a consistent stylometric footprint, but AI editors do not," in *Proc. EMNLP*, 2026, arXiv:2608.27855.
