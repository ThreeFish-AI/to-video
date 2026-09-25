"""paths 模块（双锚点单一事实源）的行为锁。

每条断言在 paths.py 文件头都有对应的「为什么」：数层数锚点会在目录迁移时
静默指向无辜位置（2026-08 迁移三处根锚点同时失效且都不报错）、env 拼错
必须大声退出而非静默锚错目录、找不到工作区要给出修复动作、WORKSPACE /
PROJECT 惰性解析是为了让 `scaffold --init-workspace` 能在「还不存在工作区」
的目录里运行。机制要改，先改文件头的理由，再让这里变红。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import paths

SCRIPTS = Path(paths.__file__).resolve().parent
#: skill 根 = 本仓根（paths.py 自 __file__ 向上找 SKILL.md 应命中的位置）。
REPO = SCRIPTS.parent


@pytest.fixture(autouse=True)
def _no_env_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    """清掉 env 显式指派：它优先于哨兵搜索，外层（集成模式）设过
    TO_VIDEO_WORKSPACE 会让「哨兵搜索」用例静默走错分支、假绿。"""
    monkeypatch.delenv(paths.ENV_WORKSPACE, raising=False)


# ── find_upward：哨兵搜索原语 ────────────────────────────────────────────────


def test_find_upward_hits_at_start_and_above(tmp_path: Path):
    (tmp_path / ".probe-marker").write_text("", encoding="utf-8")
    leaf = tmp_path / "a" / "b"
    leaf.mkdir(parents=True)
    assert paths.find_upward(tmp_path, (".probe-marker",)) == tmp_path.resolve()
    assert paths.find_upward(leaf, (".probe-marker",)) == tmp_path.resolve()


def test_find_upward_miss_returns_none(tmp_path: Path):
    assert paths.find_upward(tmp_path, (".no-such-marker-pytest",)) is None


# ── skill_root：自 __file__ 的自身位置事实 ──────────────────────────────────


def test_skill_root_hits_repo_from_module_file():
    assert paths.skill_root() == REPO
    assert paths.SKILL == REPO  # 模块级常量与函数同一事实源
    assert (REPO / paths.SKILL_MARKER).is_file()


def test_skill_root_finds_marker_above_explicit_start(tmp_path: Path):
    (tmp_path / "SKILL.md").write_text("# fake skill\n", encoding="utf-8")
    start = tmp_path / "pipeline" / "scripts"
    start.mkdir(parents=True)
    assert paths.skill_root(start) == tmp_path.resolve()


# ── workspace_root：调用侧上下文锚 ──────────────────────────────────────────


def test_workspace_root_hits_new_sentinel(tmp_path: Path):
    ws = tmp_path / "ws"
    (ws / "episodes").mkdir(parents=True)
    (ws / ".to-video-root").write_text("", encoding="utf-8")
    assert paths.workspace_root(ws / "episodes") == ws.resolve()


def test_workspace_root_takes_nearest_when_nested(tmp_path: Path):
    """两层嵌套取最近：深处目录锚到内层——嵌套工作区（宿主仓 apps/ 深处）
    不许越级吸到外层。"""
    outer = tmp_path / "outer"
    inner = outer / "inner"
    (inner / "leaf").mkdir(parents=True)
    (outer / ".to-video-root").write_text("", encoding="utf-8")
    (inner / ".to-video-root").write_text("", encoding="utf-8")
    assert paths.workspace_root(inner / "leaf") == inner.resolve()


def test_env_workspace_wins_over_cwd_search(tmp_path: Path, monkeypatch):
    ws = tmp_path / "by-env"
    cwd_side = tmp_path / "by-cwd"
    ws.mkdir()
    cwd_side.mkdir()
    (cwd_side / ".to-video-root").write_text("", encoding="utf-8")
    (ws / ".to-video-root").write_text("", encoding="utf-8")
    monkeypatch.setenv(paths.ENV_WORKSPACE, str(ws))
    assert paths.workspace_root(cwd_side) == ws.resolve()


def test_env_workspace_without_sentinel_exits_with_fix_hint(tmp_path, monkeypatch):
    """env 指到不含哨兵的目录必须当场失败——静默锚到无辜目录是 2026-08
    迁移教训里最危险的失效形态（「不报错」地用错根）。"""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv(paths.ENV_WORKSPACE, str(empty))
    with pytest.raises(SystemExit) as ei:
        paths.workspace_root(empty)
    msg = str(ei.value)
    assert paths.ENV_WORKSPACE in msg
    assert "哨兵" in msg and "--init-workspace" in msg


def test_workspace_root_without_sentinel_exits_with_init_hint(tmp_path: Path):
    bare = tmp_path / "bare"
    bare.mkdir()
    with pytest.raises(SystemExit) as ei:
        paths.workspace_root(bare)
    msg = str(ei.value)
    assert ".to-video-root" in msg
    assert "--init-workspace" in msg  # 报错必须带修复动作，不只报状态


# ── project_root：.temp/ 与工程级受检面的锚 ─────────────────────────────────


def test_project_root_accepts_git_directory(tmp_path: Path):
    repo = tmp_path / "repo"
    ws = repo / "ws"
    ws.mkdir(parents=True)
    (repo / ".git").mkdir()
    assert paths.project_root(ws) == repo.resolve()


def test_project_root_accepts_git_file_worktree_pointer(tmp_path: Path):
    """`.git` 是文件（git worktree 指针）也必须认——本仓系工作区常以
    worktree 存在，`(p/".git").is_dir()` 会当场失效（选型理由见文件头）。"""
    repo = tmp_path / "repo"
    ws = repo / "ws"
    ws.mkdir(parents=True)
    (repo / ".git").write_text("gitdir: /elsewhere/main.git\n", encoding="utf-8")
    assert paths.project_root(ws) == repo.resolve()


def test_project_root_falls_back_to_workspace(tmp_path: Path):
    """无 .git 祖先 → 工作区自身：独立工作区（暂未 git init）不因此炸。"""
    ws = tmp_path / "ws"
    ws.mkdir()
    assert paths.project_root(ws) == ws.resolve()


# ── 惰性求值：import 不许在工作区缺位时失败 ────────────────────────────────


def test_import_in_workspaceless_cwd_still_resolves_skill(tmp_path: Path):
    """`scaffold --init-workspace` 的前置条件：模块加载只解析 SKILL（自身
    位置事实），WORKSPACE 留到属性访问才求值——加载期解析会让脚手架在创建
    动作发生前先大声退出，永远无法落地。"""
    code = f"""
import sys
sys.path.insert(0, {str(SCRIPTS)!r})
import paths
print(paths.SKILL)
try:
    paths.WORKSPACE
except SystemExit as e:
    print("WORKSPACE-LOUD", e)
"""
    r = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,  # 无哨兵的空目录（pytest tmp 之上不存在任何哨兵）
        capture_output=True,
        encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[0] == str(REPO)
    assert any(ln.startswith("WORKSPACE-LOUD") for ln in r.stdout.splitlines()), (
        "属性访问未按契约大声退出"
    )
    assert "--init-workspace" in r.stdout, "退出消息缺修复动作"


def test_lazy_surface_is_only_workspace_and_project():
    with pytest.raises(AttributeError):
        getattr(paths, "NOT_A_PATH")
