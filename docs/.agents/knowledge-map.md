# 知识索引（全仓文档的唯一索引）

本文件是仓内文档的全量索引。README「文档地图」只列入口文档并指向这里；文档目录有增删、改名或迁移时，同一次提交里同步本表。目录布局遵循 [Agent Skills 规范](https://agentskills.io/specification)（RSI-008）。

## 入口与路由

| 文档 | 内容 | 读者 |
|---|---|---|
| [SKILL.md](../../SKILL.md) | Skill 路由壳：任务分流、工作流、九阶段速查、关键不变量、运行时陷阱、按需加载 | Agent（激活即加载） |
| [README.md](../../README.md) | 门面：核心能力、安装、前置依赖、Quickstart、许可 | 人 |
| [CHANGELOG.md](../../CHANGELOG.md) | 版本史与迁移记录 | 人 / Agent |

## 机制契约与阶段规格（references/）

| 文档 | 内容 |
|---|---|
| [PIPELINE.md](../../references/PIPELINE.md) | 机制 SSOT：路径变量 `$T/$W/$P/$V` 唯一定义、环境变量注册表、目录约定、脚本清单、`pipeline.toml` 字段表、交付归档、复用边界、双语渲染、新集脚手架清单 |
| [stages.toml](../../references/stages.toml) | 九阶段唯一机器可读声明（id / 序号 / 规格指针 / 子命令 / 通过门） |
| [01](../../references/01-source-extraction.md) · [02](../../references/02-planning.md) · [03](../../references/03-narration.md) · [04](../../references/04-verification.md) · [05](../../references/05-storyboard.md) | 内容层阶段规格 ①–⑤：信源取证、策划、逐字稿、双重校验、分镜 |
| [07](../../references/07-tts-voice.md) · [06](../../references/06-remotion-implementation.md) · [08](../../references/08-render-qa.md) · [09](../../references/09-final-render.md) | 生产层阶段规格 ⑥–⑨（⑥↔07、⑦↔06 刻意错位） |
| [VOICE-CLONING.md](../../references/VOICE-CLONING.md) | 声音克隆操作手册：部署、样本、风格档、合成、缓存、排障 |
| [INDEXTTS-2.5-ADVANCED.md](../../references/INDEXTTS-2.5-ADVANCED.md) | 上游能力面与进阶：机制循证、配音质量提升路线图 |
| [PRON-GLOSSARY.md](../../references/PRON-GLOSSARY.md) | 易错字台账：发音标注跨集复用表 |
| [MODELING-PLAYBOOK.md](../../references/MODELING-PLAYBOOK.md) | 动效画面建模手册（有界经验库，门 `check_playbook.py`） |

## 元机制、评测与研究

| 文档 | 内容 |
|---|---|
| [RSI.md](../../RSI.md) | 自改进回路：触发分流、台账、子代理协议、四道门、不变量保护清单、建模经验分支 |
| [issue.md](./issue.md) | RSI 台账（`RSI-xxx`） |
| [evals/README.md](../../evals/README.md) | 输出质量评测与触发评测的用法（`evals.json` / `trigger-evals.json`） |
| [modeling-experience-distillation.md](../research/modeling-experience-distillation.md) | 建模经验有界沉淀的理论、证据（IEEE 引用）与方案比选 |
| [pipeline/README.md](../../pipeline/README.md) | 旧 `pipeline/` 布局 → 新布局映射表；`pipeline/scripts` 包装器 ABI 软链说明 |

## 资产

| 路径 | 内容 |
|---|---|
| [assets/video-skeleton/](../../assets/video-skeleton/) | 分集 Remotion 骨架模板（档位与漂移判据见其 `skeleton.toml`） |
| [assets/workspace/](../../assets/workspace/) | 内容工作区模板（`scaffold.py --init-workspace` 实例化） |
| [assets/quickstart/](../../assets/quickstart/) | README Quickstart 的两幕示例场景 |
| [docs/assets/](../assets/) | 架构图（archify HTML / PNG）、mermaid 源、Demo 动图 |
