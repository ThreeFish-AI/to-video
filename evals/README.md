# to-video evals

to-video Skill 的评测资产（格式遵循 agentskills.io 官方规范），不参与流水线运行。

| 文件 | 用途 |
|---|---|
| [evals.json](./evals.json) | output eval：3 个真实 prompt + expected_output + assertions，衡量 Skill 带来的产出质量增益 |
| [trigger-evals.json](./trigger-evals.json) | trigger eval：20 条 query（10 正例 / 10 近邻负例），衡量 description 的触发准确率 |

## Output eval

1. **前置 fixture**：id 2/3 依赖 [README §四](../README.md) quickstart 在 `W=~/videos/ws` 跑通的 hello-video；id 3 另需该集已登记 `series.json` 且草渲 qa 零 FAIL，实投会写 `~/Documents/video`，建议在隔离 HOME 中运行。三例均免 IndexTTS 与入库 PDF（`files: []`），id 1 需联网取 arXiv。
2. **baseline**：改 Skill 前先 `cp -r <skill 根> <workspace>/skill-snapshot/` 冻结旧版；每例各跑 `with_skill`（当前版）与 `old_skill`（快照）。
3. **隔离**：每次 run 都是 fresh context（独立子代理或新会话），且从同一 fixture 状态出发（跑前还原工作区）。
4. **评分**：逐条 assertion 判 PASS/FAIL，引用 transcript 或产物作 evidence，写入 `grading.json`；聚合 `benchmark.json` 看 delta，两组恒过或恒挂的 assertion 下一轮替换。
5. **workspace**：结果落 `to-video-workspace/iteration-N/eval-<id>/{with_skill,old_skill}/`，置于本仓之外，**永不提交**。

## Trigger eval

1. 每条 query 跑 3 次算 trigger rate：正例 > 0.5、负例 < 0.5 为通过。
2. 固定 60/40 切分：下标 `i % 5 ∈ {0,1,2}` 入 train（12 条），其余入 validation（8 条）；文件正负交替排列，两集正负各半，跨迭代不改。
3. 只用 train 失败项指导改写，按 validation pass rate 选最佳 description（未必是最后一版）；不得把失败 query 的关键词抄进 description（过拟合），应提炼其所属类别；改后复核 ≤1024 字符。
4. ⚠️ **同名遮蔽**：个人级 `~/.claude/skills/to-video` 会遮蔽同名的项目级 / worktree 副本——候选 description 须合入并更新已安装 clone 后再测（或临时把安装指向候选版本），否则测到的仍是旧 description。

结构合法性（frontmatter 字段、命名、长度上限等）由 [tests/test_skill_spec.py](../tests/test_skill_spec.py) 执法。

参考：[Evaluating skill output quality](https://agentskills.io/skill-creation/evaluating-skills) · [Optimizing skill descriptions](https://agentskills.io/skill-creation/optimizing-descriptions) · [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
