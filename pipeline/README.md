# pipeline/（已迁移 · 兼容桩）

本目录的内容已按 [Agent Skills 规范](https://agentskills.io/specification)的目录惯例迁出（RSI-008）。这里只剩两样东西：本说明，以及包装器 ABI 软链 `scripts → ../scripts`。

| 旧路径 | 新路径 |
|---|---|
| `pipeline/scripts/` | [scripts/](../scripts/) |
| `pipeline/skills/NN-*.md` | [references/NN-*.md](../references/)（文件名与 H1 不变） |
| `pipeline/README.md` | [references/PIPELINE.md](../references/PIPELINE.md) |
| `pipeline/{VOICE-CLONING,INDEXTTS-2.5-ADVANCED,PRON-GLOSSARY,MODELING-PLAYBOOK}.md`、`pipeline/stages.toml` | [references/](../references/)（文件名不变） |
| `pipeline/templates/{video-skeleton,workspace}` | [assets/](../assets/) |
| `pipeline/tests/` | [tests/](../tests/) |
| `docs/quickstart/` | [assets/quickstart/](../assets/quickstart/) |

## 为什么保留 `pipeline/scripts` 软链（禁止删除）

分集与工作区的薄包装按 `<skill 根>/pipeline/scripts/pipeline.py` 定位 skill。其中分集那 3 个是 frozen 档，已按字节复制进所有已发布分集；工作区那 2 个，scaffold 只在文件不存在时才写入，旧工作区不会更新。解析函数因此不能改，软链就是它们依赖的稳定 ABI：

- 删掉软链，所有已部署分集与工作区的包装器都会立即报「找不到 to-video skill」；
- 旧文档里的 `$T/pipeline/scripts/<脚本>.py` 命令也经它继续可用。

脚本一律按 `Path(__file__).resolve()` 定位自身，经软链执行时会解析回真实的 `scripts/`。执法见 [tests/test_wrapper_resolver.py](../tests/test_wrapper_resolver.py)。

**安装形态**：请用 `git clone` 加软链安装，或设 `TO_VIDEO_HOME`。复制式安装（如 `npx skills add --copy`）若不保留软链，旧分集包装器会失效。

## frozen 文件注释里的旧路径

`assets/video-skeleton/` 下的 frozen 档文件（包装器、Subtitle、SceneFade、i18n 等）注释里仍写着 `pipeline/…` 或 `skills/06` 之类的旧路径。这是有意保留的：改动一个字节，所有已发布分集都会报 checksum 漂移。遇到时按上表换算。
