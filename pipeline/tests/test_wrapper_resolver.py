"""分集/工作区薄包装器的 skill 解析与转发契约。

包装器是「机制随 skill 分发、内容留在工作区」的粘合层，失效形态被刻意
设计为**大声退出**——静默跳过等于流水线假绿。这里钉三件事：

  1. 解析命中：TO_VIDEO_HOME 指向的假 skill 被找到，且目标脚本收到的
     `--project`（分集包装器）/ `TO_VIDEO_WORKSPACE`（工作区包装器）恰是
     包装器**自身位置**推导的锚，与调用 CWD 无关；
  2. 解析未命中：三个候选全部列出 + 安装指令——少列一个候选，用户就少
     一条自救路径；
  3. 模板一致性：各形态的包装器正文除目标脚本名外字节一致、解析器体
     跨形态共享。「修缺陷 = 改一处模板 + verify_skeleton 字节执法」的
     前提是副本之间真的同源，破了就是「多份副本各自腐化」的开端。

驱动手法：假 skill 的目标脚本一律换成「把 argv / env 写文件」的探针——
断言的是转发契约本身，不拉起目标脚本的真实依赖（tts / render 一概不碰）。
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import paths

PIPELINE = Path(__file__).resolve().parents[1]
SKEL = PIPELINE / "templates" / "video-skeleton" / "scripts"
WS_TMPL = PIPELINE / "templates" / "workspace" / "scripts"

#: 分集薄包装器（--project 形态，模板里是明文 .py）。
EPISODE_WRAPPERS = ("tts.py", "build_narration.py", "qa_frames.py")
#: 工作区薄包装器（TO_VIDEO_WORKSPACE 形态，模板带 .tmpl 后缀）。
WORKSPACE_WRAPPERS = ("pipeline.py", "check_series.py")

#: 假目标脚本：把收到的 argv 与锚定 env 落盘，供断言转发契约。
PROBE = """\
import json
import os
import sys
from pathlib import Path

Path(os.environ["WRAP_PROBE_OUT"]).write_text(
    json.dumps(
        {"argv": sys.argv, "workspace_env": os.environ.get("TO_VIDEO_WORKSPACE")}
    ),
    encoding="utf-8",
)
"""


def child_env(**overrides: str) -> dict[str, str]:
    """子进程环境：先清掉外层可能渗入的锚定变量，再按用例覆写——
    集成模式整跑时外层 env 不许改变解析走向。"""
    env = dict(os.environ)
    for key in (paths.ENV_WORKSPACE, "TO_VIDEO_HOME"):
        env.pop(key, None)
    env.update(overrides)
    return env


def fake_skill(tmp_path: Path) -> Path:
    """搭一个只够骗过解析器的假 skill：pipeline.py 兼任探测标记与目标脚本。"""
    scripts = tmp_path / "fake-skill" / "pipeline" / "scripts"
    scripts.mkdir(parents=True)
    for name in ("pipeline.py", *EPISODE_WRAPPERS, *WORKSPACE_WRAPPERS):
        (scripts / name).write_text(PROBE, encoding="utf-8")
    return tmp_path / "fake-skill"


def run_wrapper(
    wrapper: Path, *args: str, env: dict[str, str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(wrapper), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


# ── 解析命中：锚来自包装器自身位置，与调用 CWD 无关 ────────────────────────


@pytest.mark.parametrize("name", EPISODE_WRAPPERS)
def test_episode_wrapper_forwards_project_from_own_location(tmp_path, name):
    home = fake_skill(tmp_path)
    episode = tmp_path / "ws" / "episodes" / "probe-video"
    (episode / "scripts").mkdir(parents=True)
    wrapper = episode / "scripts" / name
    shutil.copy2(SKEL / name, wrapper)
    probe_out = tmp_path / f"probe-{name}.json"

    elsewhere = tmp_path / "elsewhere"  # 刻意不在工程内，证明锚与 CWD 无关
    elsewhere.mkdir()
    r = run_wrapper(
        wrapper,
        "--force",
        "extra.wav",
        env=child_env(TO_VIDEO_HOME=str(home), WRAP_PROBE_OUT=str(probe_out)),
        cwd=elsewhere,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    data = json.loads(probe_out.read_text(encoding="utf-8"))
    assert data["argv"] == [
        str(home / "pipeline" / "scripts" / name),
        "--project",
        str(episode.resolve()),
        "--force",
        "extra.wav",
    ]
    # 分集包装器走 --project 传锚，不劫持工作区 env（那是工作区包装器的形态）
    assert data["workspace_env"] is None


@pytest.mark.parametrize("name", WORKSPACE_WRAPPERS)
def test_workspace_wrapper_anchors_env_from_own_location(tmp_path, name):
    """工作区包装器 .tmpl 去后缀落盘后：argv 原样转发，TO_VIDEO_WORKSPACE
    由自身 parent.parent 写回——从任意 CWD 调用都锚定本工作区。"""
    home = fake_skill(tmp_path)
    ws = tmp_path / "ws"
    (ws / "scripts").mkdir(parents=True)
    wrapper = ws / "scripts" / name
    wrapper.write_text(
        (WS_TMPL / f"{name}.tmpl").read_text(encoding="utf-8"), encoding="utf-8"
    )
    probe_out = tmp_path / f"probe-{name}.json"

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    r = run_wrapper(
        wrapper,
        "status",
        "--series",
        "demo",
        env=child_env(TO_VIDEO_HOME=str(home), WRAP_PROBE_OUT=str(probe_out)),
        cwd=elsewhere,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    data = json.loads(probe_out.read_text(encoding="utf-8"))
    assert data["argv"] == [
        str(home / "pipeline" / "scripts" / name),
        "status",
        "--series",
        "demo",
    ]
    assert data["workspace_env"] == str(ws.resolve())


def test_workspace_wrapper_keeps_caller_explicit_env(tmp_path):
    """setdefault 语义：调用方已显式指派 TO_VIDEO_WORKSPACE 时不越权覆写
    （脚本被借去操作另一个工作区是合法通道，预设值须原样透传）。"""
    home = fake_skill(tmp_path)
    ws = tmp_path / "ws"
    (ws / "scripts").mkdir(parents=True)
    wrapper = ws / "scripts" / "pipeline.py"
    wrapper.write_text(
        (WS_TMPL / "pipeline.py.tmpl").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    preset = tmp_path / "another-ws"  # setdefault 不校验存在性，无需真建
    r = run_wrapper(
        wrapper,
        env=child_env(
            TO_VIDEO_HOME=str(home),
            WRAP_PROBE_OUT=str(tmp_path / "probe-preset.json"),
            TO_VIDEO_WORKSPACE=str(preset),
        ),
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    probe = json.loads((tmp_path / "probe-preset.json").read_text(encoding="utf-8"))
    assert probe["workspace_env"] == str(preset)


# ── 解析未命中：大声退出，候选与出路全给 ──────────────────────────────────


def test_unresolved_skill_lists_all_candidates_and_install_hint(tmp_path):
    wrapper = tmp_path / "w" / "tts.py"
    wrapper.parent.mkdir(parents=True)
    shutil.copy2(SKEL / "tts.py", wrapper)

    empty_home = tmp_path / "home"  # 假 home：无 ~/.claude 亦无 ~/.agents
    empty_home.mkdir()
    absent = tmp_path / "no-such-skill"
    r = run_wrapper(
        wrapper,
        env=child_env(TO_VIDEO_HOME=str(absent), HOME=str(empty_home)),
        cwd=tmp_path,
    )
    assert r.returncode != 0
    out = r.stdout + r.stderr
    for candidate in (
        str(absent),
        str(empty_home / ".claude" / "skills" / "to-video"),
        str(empty_home / ".agents" / "skills" / "to-video"),
    ):
        assert candidate in out, f"未列出候选 {candidate}：\n{out}"
    assert "git clone" in out and "TO_VIDEO_HOME" in out


# ── 模板一致性：解析器体共享，正文除目标名外字节一致 ────────────────────────


def _body_after_docstring(path: Path) -> str:
    """→ 模块 docstring 之后的源码（各包装器只允许 docstring 与目标名不同）。"""
    src = path.read_text(encoding="utf-8")
    module = ast.parse(src)
    first = module.body[0]
    assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant), (
        f"{path} 首语句不是 docstring（包装器形态变了？检测器该更新）"
    )
    return "".join(src.splitlines(keepends=True)[first.end_lineno :])


def _normalized(path: Path, name: str) -> str:
    """把 exec 行的目标脚本名换成占位符后返回正文。

    只替换 `str(_skill_scripts() / "<name>")` 这一精确形态：裸替换文件名会
    误伤工作区包装器探测标记里的 `(p / "pipeline.py").is_file()`。
    """
    return _body_after_docstring(path).replace(
        f'str(_skill_scripts() / "{name}")', 'str(_skill_scripts() / "<TARGET>")'
    )


def test_episode_wrapper_bodies_identical_modulo_target():
    norms = {_normalized(SKEL / n, n) for n in EPISODE_WRAPPERS}
    assert len(norms) == 1, "分集包装器正文分叉：解析器/转发体须单源维护"


def test_workspace_wrapper_bodies_identical_modulo_target():
    paths_ = [WS_TMPL / f"{n}.tmpl" for n in WORKSPACE_WRAPPERS]
    norms = {_normalized(p, p.name[: -len(".tmpl")]) for p in paths_}
    assert len(norms) == 1, "工作区包装器正文分叉：解析器/转发体须单源维护"


def test_resolver_function_is_shared_across_all_five():
    """`_skill_scripts` 解析器体在五份包装器间字节一致——候选顺序与退出
    文案的任何改动都须同时作用于全集，不允许某份单独漂移。"""

    def resolver(path: Path) -> str | None:
        src = path.read_text(encoding="utf-8")
        for node in ast.parse(src).body:
            if isinstance(node, ast.FunctionDef) and node.name == "_skill_scripts":
                return ast.get_source_segment(src, node)
        return None

    files = [SKEL / n for n in EPISODE_WRAPPERS] + [
        WS_TMPL / f"{n}.tmpl" for n in WORKSPACE_WRAPPERS
    ]
    segments = {resolver(f) for f in files}
    assert None not in segments, "某包装器丢了 _skill_scripts（形态变了？）"
    assert len(segments) == 1, "解析器体已分叉：五份副本须单源维护"
