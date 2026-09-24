"""skill 仓自身的工程卫生（与 toml 配置内容无关，故不并入 test_config.py）。

独立成仓后不再有「仓库根 .gitignore / 兄弟 lockfile」可依赖——受检对象就是
本仓自己。三条不变量共同守护一个声明：**本仓刻意不是可构建的 Python 包**
（pyproject.toml 无 `[project]` 段，只有 `[tool.pytest.ini_options]`；全部脚本
走 `uv run --no-project` + 调用点 `--with` 注入依赖——为 schema/模板工具引入
打包层违反最小干预）：

  - 无 `uv.lock`：uv 没有「拒绝成为项目」的开关，漏打 `--no-project` 的
    `uv run` 会当场把 CWD 当项目根并生成锁文件（negentropy 子项目时期实测
    触发过一次）。一旦入库，就与「不参与任何 uv workspace」的声明直接矛盾。
  - 无 `.venv/`：同一事故的另一形态（`uv venv` / `uv sync` 的产物），存在即
    说明有人在 skill 根里把它当项目跑。
  - pyproject 无 `[project]` 段（及任何非 `[tool.*]` 顶层表，如
    `[build-system]`）：出现即「成为包」的意图回归，`--no-project` 的测试
    运行方式随之失效。
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paths import skill_root  # noqa: E402

#: 受检锚点：skill 仓根（含 SKILL.md 的目录）。由哨兵法派生而非数层数——
#: 数层数把「目录深度」这个偶然事实编码进测试，clone 深度一变即静默错位。
SKILL_ROOT = skill_root()


def test_no_uv_lock_in_skill_repo():
    """锁文件不该真的存在——本仓刻意无 [project]，出现即是漏打旗标的产物。"""
    stray = SKILL_ROOT / "uv.lock"
    assert not stray.is_file(), (
        f"{stray} 存在 —— 大概率是漏打 `--no-project` 的 `uv run` 把 skill 根"
        "当项目根生成的，删掉即可（本仓刻意不是包，不该有锁文件）"
    )


def test_no_venv_in_skill_repo():
    """.venv 是「被当成项目跑」的现场证据，与 uv.lock 同源同修。"""
    venv = SKILL_ROOT / ".venv"
    assert not venv.exists(), (
        f"{venv} 存在 —— `uv venv`/`uv sync` 在 skill 根的产物；本仓无"
        " [project]，运行依赖一律 `uv run --no-project --with` 注入"
    )


def test_pyproject_is_not_a_package():
    """现状 = 只有 [tool.pytest.ini_options]；出现 [project]（或任何非 tool
    顶层表）即打包意图回归。"""
    data = tomllib.loads((SKILL_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    stray = sorted(k for k in data if k != "tool")
    assert not stray, (
        f"pyproject.toml 出现顶层表 {stray} —— 本仓刻意不是可构建的 Python"
        "包（脚本全部 `uv run --no-project` 运行）；工具配置请挂在 [tool.*] 下"
    )
