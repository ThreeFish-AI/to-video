#!/usr/bin/env python3
"""双锚点路径单一事实源——skill 根与内容工作区根物理分离后的定位机制。

## 为什么是两个锚点

抽取为独立技能前，脚本住在工作区内部（`negentropy-influence/pipeline/scripts/`），
从 `__file__` 向上找哨兵即可同时定位「机制」与「内容」。抽取后二者物理分离：

  - **skill 根**（`SKILL`）：本脚本所在技能仓的根（含 `SKILL.md`），随安装位置
    变化（`~/.claude/skills/to-video` 软链 / `TO_VIDEO_HOME` / 任意 clone 路径），
    永远从 `__file__` 向上搜索——脚本自己知道自己在哪。
  - **工作区根**（`WORKSPACE`）：内容所在的任意目录（series.json / episodes/
    voices/ 的父目录），从**调用侧上下文**（CWD / `--workspace` / env）向上搜索
    哨兵——脚本不知道用户把工作区放在哪，必须由调用现场提供起点。

## 哨兵法（沿承 2026-08 media/→apps/ 迁移的教训）

数层数（`parents[N]`）把「目录深度」这个**偶然事实**编码进脚本：2026-08 迁移时
三处仓库根锚点同时静默指向 `apps/`，且**都不报错**（doctor 只打印样本缺失、
pre-commit 门整体失效、试听小样写错位置且 git status 不可见）。哨兵搜索对位置
免疫（git 找 `.git`、uv/pytest 找 `pyproject.toml` 的同一惯例）。

  - 哨兵 `.to-video-root`。
  - 为什么不用 `.git` 当工作区哨兵：相关仓的 `.git` 可能是**文件**（git worktree），
    `(p / ".git").is_dir()` 当场失效；测试 fixture 无 `.git`；`~/tools/index-tts`
    是真 `.git` 目录会误锚。`.git` 只用于 `project_root`（且文件/目录皆认）。
  - 找不到即**大声退出**，绝不回退猜测：报错须写明找什么标记、从哪开始、走到
    哪里为止，并给出修复动作（`scaffold.py --init-workspace`）。

## project_root：`.temp/` 与工程级受检面的锚

`.temp/` 按协作协议是**仓库级**约定，须落在工作区所在的 git 仓库根，而非工作区
自身（工作区可嵌在巨仓深处）。故 `project_root` = 工作区最近祖先含 `.git`
（**文件或目录**，worktree 是文件），无 `.git` 时回退工作区自身（独立工作区
自带 git init 时二者本就重合）。`check_series` 的工程级受检面与
`archify.html_dir` 基准同用此锚。

## 惰性求值（承重，勿破）

`SKILL` 在模块加载期解析（脚本永远在 skill 内，不会失败）；`WORKSPACE`/`PROJECT`
经 PEP 562 `__getattr__` **惰性解析**——`scaffold.py --init-workspace` 必须能在
「还不存在工作区」的目录里运行，若模块加载期就解析 WORKSPACE，它会在创建动作
发生前先大声退出，脚手架永远无法落地。消费者照常 `from paths import WORKSPACE`
（触发惰性求值，保持大声失败语义）。

## 导入边界（承重，勿破）

`pipeline.py` / `check_series.py` / `scaffold.py` / `verify_skeleton.py` /
`tts_sample.py` / `refs.py` / `prepare_ref.py` / `deliver.py` / `record_archify.py` /
`record_archify_all.py` 可以 `import paths`。**`tts.py` 与 `tts_server.py` 绝不可以** —— 它们会被拷到
`~/tools/index-tts` 的 venv 里运行并 `from tts import ...`，给它们增加任何同目录
依赖都会断掉那条拷出路径。`tts.py` 全靠入参与环境变量，本就不需要任何根。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

#: skill 根哨兵：技能仓根目录的标志文件（Claude Code Skill 的装载单位）。
SKILL_MARKER = "SKILL.md"

#: 工作区根哨兵。
WORKSPACE_MARKERS = (".to-video-root",)

#: 工作区显式指派（优先于哨兵搜索）；值为工作区根绝对或相对路径。
ENV_WORKSPACE = "TO_VIDEO_WORKSPACE"


def find_upward(start: Path, markers: tuple[str, ...]) -> Path | None:
    origin = start.resolve()
    for p in [origin, *origin.parents]:  # 天然终止于文件系统根，不会无限上溯
        if any((p / m).is_file() for m in markers):
            return p
    return None


def skill_root(start: Path | None = None) -> Path:
    """自 start（默认本模块）向上找 `SKILL.md`，返回 skill 根。

    只会从 `__file__` 出发搜索：skill 根是脚本的**自身位置**事实，与用户
    在哪个目录执行无关。找不到即大声退出（安装不完整，属于环境损坏）。
    """
    origin = (start or Path(__file__)).resolve()
    root = find_upward(origin, (SKILL_MARKER,))
    if root is not None:
        return root
    sys.exit(
        f"找不到 skill 根哨兵 {SKILL_MARKER}（自 {origin} 起向上搜索至"
        f" {origin.parents[-1]}\n  —— 安装不完整：clone 缺 SKILL.md，或本脚本被"
        "单独拷出技能仓运行。"
    )


def workspace_root(start: Path | None = None) -> Path:
    """定位内容工作区根：env 显式指派 > 自 start（默认 CWD）向上搜索哨兵。

    解析顺序：
      1. `TO_VIDEO_WORKSPACE` 指向的目录必须含哨兵之一（防止 env 拼写错误
         静默锚到无辜目录），否则大声退出；
      2. 自 start（默认当前工作目录）向上搜索首个含哨兵的目录；
      3. 都失败则大声退出，报错须写明标记名、搜索起点与修复动作。
    """
    env = os.environ.get(ENV_WORKSPACE)
    if env:
        p = Path(env).expanduser().resolve()
        if any((p / m).is_file() for m in WORKSPACE_MARKERS):
            return p
        sys.exit(
            f"{ENV_WORKSPACE}={env} 指向的目录不含任何哨兵"
            f"（{' / '.join(WORKSPACE_MARKERS)}）\n"
            "  —— 环境变量拼错目录，或该目录尚未 init："
            "先 `scaffold.py --init-workspace` 或补写哨兵文件。"
        )
    origin = (start or Path.cwd()).resolve()
    root = find_upward(origin, WORKSPACE_MARKERS)
    if root is not None:
        return root
    sys.exit(
        f"找不到内容工作区哨兵 {' / '.join(WORKSPACE_MARKERS)}"
        f"（自 {origin} 起向上搜索至 {origin.parents[-1]}）"
        "\n  —— 新工作区先运行 `scaffold.py --init-workspace <dir>`；"
        "或在既有工作区内执行本命令（从工作区任意子目录起均可达）。"
    )


def project_root(workspace: Path) -> Path:
    """工作区所在 git 仓库根：最近祖先含 `.git`（**文件或目录**）者；无则工作区自身。

    仅三处消费：`.temp/` 收敛、check_series 工程级受检面、`archify.html_dir`
    基准。`.git` 是文件（git worktree 指针）与是真目录（普通 clone）皆认。
    """
    for p in [workspace.resolve(), *workspace.resolve().parents]:
        if (p / ".git").exists():
            return p
    return workspace.resolve()


#: skill 根：assets/ 模板与 references/ 文档的定位基准（模块加载期解析，永不失败）。
SKILL = skill_root()


def __getattr__(name: str) -> Path:
    """WORKSPACE / PROJECT 惰性解析（见模块 docstring「惰性求值」节）。"""
    if name == "WORKSPACE":
        return workspace_root()
    if name == "PROJECT":
        return project_root(workspace_root())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
