# 成文优化：病灶取证、理论依据与方案比选

> **结论先行**：AI 稿件「断断续续、不像人写」的病灶在**篇章结构层**，不在词汇层。流水线在 ④ 双重校验之后新增正式阶段 **⑤ 成文优化**，按编辑行业的四层分工（结构 → 衔接 → 句子 → 词句）自顶向下改稿，只改表达、不改事实；改完交独立子代理做成文评审，改过的句子再回 ④A 复核兜底。规则正文在 [references/05-prose-refinement.md](../../references/05-prose-refinement.md)，本文只存设计依据（台账：[RSI-011](../.agents/issue.md)）。

**目录**：一、病灶取证 · 二、根因 · 三、理论依据 · 四、方案比选 · 五、与相邻机制的关系 · 六、撤销条件 · 参考文献

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="../assets/architecture/prose-refinement--passes-dark.png">
  <img src="../assets/architecture/prose-refinement--passes-light.png" alt="Stage ⑤ 成文优化：已过 ④ 的四稿依次经过 L1 结构、L2 衔接、L3 句子、L4 词句四层 pass，改动经 diff 进入改动表，交独立子代理按具名规则成文评审、REWRITE 回改至清零，再只对改动句重跑 ④A 复核、判 RISKY 即回退原句；评审与复核清零后定稿，build 与 check 零 FAIL 后文稿冻结。">
</picture>

> 图源：[`prose-refinement--passes.mmd`](../assets/mermaid/prose-refinement--passes.mmd) · 交互版：[`prose-refinement--passes.html`](../assets/architecture/prose-refinement--passes.html)

## 一、病灶取证（真实语料，只读扫描）

语料：negentropy 工作区 14 集已发布逐字稿，共 2303 句（2026-09-25 扫描，未改动任何文件）。

| 症状 | 计数 | 判读 |
|---|---|---|
| 书面腔禁词（综上所述 / 值得注意的是 / 首先 / 其次 / 总而言之…） | **0** | 03 纪律 2 已经管住词汇层——**问题不在这里** |
| 句子以逗号或顿号收尾、语义要到下一行才完整 | 110 | 一句话被切成两条「句」，读起来断 |
| 以冒号收尾、下一行才给答案 | 81 | 悬念钩用得太多，变成了阅读断点 |
| 「不是……而是……」 | 42 | 负向排比，AI 文本的典型结构 |
| 破折号 | 231 | 平均每 10 句一个，稿子显得碎 |
| 整集幕内零空行分段 | 9/14 集 | 一幕 20–36 句平铺成一面墙，没有自然段 |
| ④ 易懂性评审（B 节）判据 | 5 条，全部是句级局部判据 | 没有任何篇章维度：幕内怎么推进、段间怎么接、问题有没有兑现 |

典型片段（节选，逗号收尾的半句与重复信息并存）：

```
- [p0-02] 它能读懂你的需求，翻遍整个代码仓库，
- [p0-03] 一次修改好几个文件，敲命令、跑测试、定位报错、生成补丁。
- [p0-04] 修 bug 对它来说，是定位、打补丁、执行、再修改，一圈又一圈。
```

有 5 集已经自发用空行分段（其中一集 35 处），build / check / tts 全链路正常。这证明「幕内空行 = 自然段」零机制成本：`build_narration.parse_md` 只识别幕标题行与句行，其余行一律跳过。

## 二、根因

1. **生成机制**：自回归逐段生成只求局部最优，没有全局篇章规划；以自身产出为条件继续生成，早期的话题漂移会越滚越大 [1][2]。分段生成时，每段自带「迷你开头 + 迷你总结」，段与段之间的桥没人负责——这正是「段内通顺、段间断裂」最常见的工程成因 [3]。
2. **模态错配**：AI 默认写的是「整合式」书面语（名词化、长从句、信息密度高），而听众要的是「参与式」口语（第一 / 第二人称、动词驱动、一次一个新想法）[4]。
3. **流程缺口**：流水线有「写对」（③ 纪律）和「查对」（④），但没有「写顺」这一环；④ 的易懂性评审是句级的，结构层问题没有任何环节负责。

## 三、理论依据（按四层 pass 组织）

| 层 | 核心依据 | 落到规格的规则 |
|---|---|---|
| 流程分层 | EFA 编辑层级（developmental → line → copyedit → proofread，各层有明确的禁区）[5]；AI 编辑与 AI 生成在文体上是不同信号，支持「定位 + 最小干预」的编辑式改稿 [6] | 四层 pass 自顶向下；上层问题不用下层手段掩盖；没有问题的段落原样保留 |
| L1 结构 | 金字塔原理：结论先行、上层概括下层、同组同类、组内有序 [7]；Problem–Solution / SPRE 范式 [8]；Purdue OWL 段落四要素（一段一念）[9] | 先写一句话骨架再动手；按文体选骨架；补上「转」；开头的问题必须兑现 |
| L2 衔接 | Given-New 契约：句首放已知、句尾放新知 [10]；Williams 的话题链与句尾强调 [11]；过渡词只表达真实的逻辑关系 [12] | 段间桥；话题链；删掉每段的小结；先调语序再考虑加连接词 |
| L3 句子 | 长短句交替 [13]；中心嵌套深度的认知上限 [14]；余光中的欧化中文清单 [15]；流水句是汉语的合法句式 [16][17] | 名词化还原为动词；嵌套不超过一层；意合优先；不按英文 run-on 判罚流水句 |
| L4 词句 | AI 文本特征词簇与结构指纹 [18][19][20]；朗读测试 [21] | 中文去机器味检查表 Z1–Z13；只在命中特征簇时动手 |
| 逐字稿（耳朵） | 广播写作规范（一句一个想法、写给一个人听）[21][22]；语调单位约 6–7 词、只装一个新想法 [4]；话语标记的导航作用 [23]；先呈现误解再纠正，比清楚流畅的讲解学得更好 [24]；好奇心的信息缺口理论 [25]；锚定-桥接类比 [26] | 口语路标词；misconception 先行；开环与回扣；类比交代边界；幕内空行分 beat |
| 分镜 | 多媒体学习的冗余原则：画面 + 旁白 + 同一句屏幕文字会增加负担 [27]；纪录片旁白应「图解或对位」而非描述画面 [28] | 画面列只写看得见的；旁白讲画面给不了的（与 RSI-007 复述门同源） |

## 四、方案比选

### 4.1 落位形态（用户决策：正式阶段）

| 候选 | 做法 | 代价 | 结论 |
|---|---|---|---|
| A 内嵌子步骤 | ②③⑤ 规格各加一节 + ④ 扩一个维度 | 最小；但「写顺」没有独立的通过门，执行时最容易被跳过 | 用户否决（2026-09-25） |
| **B 正式阶段** | 新增 `05-prose-refinement.md`，原 05–09 顺移为 06–10 | 改名 5 个规格文件 + 全仓入链同步 + 3 条执法测试泛化 | **采纳**：阶段地位显式、有独立的门与规格，代理不会跳过 |

B 触碰 RSI 不变量 1、8、11。推翻依据是用户的明确决策；本次同时把这三条改写为**不带数字**的表述（「第 N 阶段 ↔ `NN-*.md`」「速查表行数 = 阶段数」），测试从写死 `9` 改为按 `stages.toml` 推导，以后再增删阶段不必再改不变量本身。

### 4.2 插入位置

| 候选 | 位置 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| C | ③ 与 ④ 之间（先润色再校验） | ④ 天然兜住润色引入的事实漂移 | ④ 的 REWRITE 修正会打乱刚润色好的结构；④ 引用处约 20 处也要顺移 | 否决 |
| **A** | ④ 之后、分镜之前 | 优化对象是已校验的稿子；只对改动句回跑 ④A，复核成本与改动量成正比（编辑惯例：改过的段落重新核实）；优化后的 beat 分段直接喂给 ⑥ 切镜；④ 不动 | 分镜在 ⑥ 才产出，其成文规则需要回调 | **采纳**：06 规格验收加一条指针，规则仍只写在 05（单一事实源） |
| B | 分镜之后，一次处理四稿 | 一次看全四稿 | 逐字稿改写会破坏已写好的分镜句区间与 archify 锚句；违反 ⑦「文稿字节冻结后才跑定稿配音」的前置条件 | 否决 |

### 4.3 执法力度（用户决策：不加内容类机器门）

语料里书面腔禁词零命中，词表类门拦不住真实病灶；结构层（段间衔接、问题兑现）无法用正则可靠判断，硬做只会产生误报（RSI-007 的教训：扫描类门必须在真实语料上对拍）。因此本阶段是 authored 阶段、prompt 门。本次**只新增一道文档完整性门** `test_spec_references_resolve`：重编号后，所有用户可见文案里点名的 `references/NN-*.md` 必须真实存在。它检查的是仓库自身，不检查稿件内容，与用户决策不冲突。

## 五、与相邻机制的关系

- **④ 双重校验**：④ 判「对不对、懂不懂」，⑤ 判「顺不顺、像不像人」。④ B 节保留术语降落、指代距离、抽象连段等句级判据；篇章与节奏归 ⑤，两边不重复。
- **03 写作纪律**：03 管「写对」（事实回溯、口语化、术语降落、节奏、数字精确），⑤ 在此基础上管「写顺」。03 的「幕尾半句悬念钩」是结构性要求，⑤ 保留它，只检查它与下一幕是否接得上。
- **RSI-007 复述门**：门只拦逐字重复，⑤ 第七节补上语义层面的「旁白讲画面给不了的」。
- **配音故事块**（PR #17 提出，尚未合入）：块（≤3 句）是配音单位，beat（2–8 句）是阅读与画面单位，块嵌套在 beat 之内。两者方向一致，不冲突。PR #17 基于旧 `pipeline/` 布局，编号与 main 已合入的 RSI-008/009 撞车；rebase 到新布局时，其 `07-tts-voice.md` 改动正好对应新的 `references/07-tts-voice.md`。
- **双语**：只优化主稿；主稿改动经基线锁点名 en 失配句，按 ④C 重译或显式 `--accept`。

## 六、撤销条件

连续 3 集执行 ⑤ 后，改动句复核都判出 RISKY（说明润色在系统性地损伤事实），或用户评审认为优化稿不比原稿更好读 ⇒ 降级为 ④ 的一个可选维度，并把阶段编号还原（反向走一遍本次的改名与入链同步）。

## 参考文献

[1] A. Holtzman, J. Buys, L. Du, M. Forbes, and Y. Choi, "The curious case of neural text degeneration," in *Proc. ICLR*, 2020.

[2] Wikipedia contributors, "Wikipedia:Signs of AI writing," WikiProject AI Cleanup. [Online]. Available: https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing

[3] J. Zhao, S. Zu, Z. Ji, C. Zhou, and B. Qin, "Writer-R1: Enhancing generative writing in LLMs via memory-augmented replay policy optimization," arXiv:2603.15061, 2026.

[4] W. Chafe and J. Danielewicz, "Properties of spoken and written language," in *Comprehending Oral and Written Language*, R. Horowitz and S. J. Samuels, Eds. San Diego, CA, USA: Academic Press, 1987, pp. 83–113.

[5] Editorial Freelancers Association, "Editorial Service Definitions." [Online]. Available: https://www.the-efa.org/editorial-services-definitions

[6] Z. Shan, Y. Lee, and S. Hao, "AI writers have a consistent stylometric footprint, but AI editors do not," in *Proc. EMNLP*, 2026, arXiv:2608.27855.

[7] B. Minto, *The Pyramid Principle: Logic in Writing and Thinking*, 3rd ed. London, U.K.: FT Prentice Hall, 2009.

[8] M. Hoey, *On the Surface of Discourse*. London, U.K.: George Allen & Unwin, 1983.

[9] Purdue OWL, "On Paragraphs," Purdue Univ. [Online]. Available: https://owl.purdue.edu/owl/general_writing/academic_writing/paragraphs_and_paragraphing/index.html

[10] H. H. Clark and S. E. Haviland, "Comprehension and the given-new contract," in *Discourse Production and Comprehension*, R. O. Freedle, Ed. Norwood, NJ, USA: Ablex, 1977, pp. 1–40.

[11] J. M. Williams and J. Bizup, *Style: Lessons in Clarity and Grace*, 13th ed. Boston, MA, USA: Pearson, 2021.

[12] UNC Writing Center, "Transitions." [Online]. Available: https://writingcenter.unc.edu/tips-and-tools/transitions/

[13] G. Provost, *100 Ways to Improve Your Writing*. New York, NY, USA: Mentor, 1985.

[14] F. Karlsson, "Constraints on multiple center-embedding of clauses," *J. Linguistics*, vol. 43, no. 2, pp. 365–392, 2007.

[15] 余光中, 〈怎样改进英式中文——论中文的常态与病态〉, 《明报月刊》, 1987 年 10 月. [Online]. Available: https://language.chinadaily.com.cn/a/201509/01/WS5b20a851a31001b825720b30.html

[16] 吕叔湘, 《汉语语法分析问题》. 北京: 商务印书馆, 1979.

[17] 沈家煊, 〈"零句"和"流水句"——为赵元任先生诞辰120周年而作〉, 《中国语文》, 2012, no. 5, pp. 403–415.

[18] D. Kobak, R. González-Márquez, E.-Á. Horvát, and J. Lause, "Delving into LLM-assisted writing in biomedical publications through excess vocabulary," *Sci. Adv.*, vol. 11, no. 27, eadt3813, 2025.

[19] W. Liang *et al.*, "Monitoring AI-modified content at scale: A case study on the impact of ChatGPT on AI conference peer reviews," in *Proc. ICML*, PMLR 235, 2024, pp. 29575–29620.

[20] Pangram Labs, "A comprehensive guide to spotting AI writing patterns." [Online]. Available: https://www.pangram.com/blog/comprehensive-guide-to-spotting-ai-writing-patterns

[21] C. Joyce, "Campfire tales: The essentials of writing for radio," NPR Training, 2015. [Online]. Available: https://training.npr.org/2015/03/20/campfire-tales-the-essentials-of-writing-for-radio/

[22] BBC News School Report, "Radio news tips." [Online]. Available: http://news.bbc.co.uk/2/hi/school_report/5275764.stm

[23] D. Schiffrin, *Discourse Markers*. Cambridge, U.K.: Cambridge Univ. Press, 1987.

[24] D. A. Muller, J. Bewes, M. D. Sharma, and P. Reimann, "Saying the wrong thing: Improving learning with multimedia by including misconceptions," *J. Comput. Assist. Learn.*, vol. 24, no. 2, pp. 144–155, 2008, doi: 10.1111/j.1365-2729.2007.00248.x.

[25] G. Loewenstein, "The psychology of curiosity: A review and reinterpretation," *Psychol. Bull.*, vol. 116, no. 1, pp. 75–98, 1994.

[26] J. Clement, "Using bridging analogies and anchoring intuitions to deal with students' preconceptions in physics," *J. Res. Sci. Teach.*, vol. 30, no. 10, pp. 1241–1257, 1993, doi: 10.1002/tea.3660301007.

[27] R. E. Mayer, *Multimedia Learning*, 3rd ed. Cambridge, U.K.: Cambridge Univ. Press, 2020.

[28] M. Rabiger and C. Hurbis-Cherrier, *Directing the Documentary*, 7th ed. New York, NY, USA: Focal Press, 2020.
