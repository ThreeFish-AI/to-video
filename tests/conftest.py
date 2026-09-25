"""pipeline 测试公共夹具。

落位说明：宿主仓若有 session 级 Postgres 夹具（tests/conftest.py autouse），pytest
只加载 rootdir→测试文件路径上的 conftest，本目录不在那条祖先链上——结构上不可能
被拉起 DB。全部用例无网络、无 TTS、无 ffmpeg、无 Postgres，总时长秒级。

真集锚定是 **env 门控** 的（双锚点架构的必然）：本仓是 skill 仓，机制与内容
物理分离后这里**没有** episodes/；真集只存在于 skill 之外的内容工作区，
由 `TO_VIDEO_TEST_WORKSPACE` 指过来（集成模式）。若改为「自 CWD 向上找哨兵」，
在 skill 仓里跑测试会静默锚到别处或 no-op 得不明不白——env 缺席即明确的
「无真树可守」，不猜。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

PIPELINE_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: 集成模式真树：env 指向的内容工作区（含哨兵与 episodes/ 真集）。
#: None = 纯 skill 仓形态，真集守卫 no-op。
_TEST_WS = os.environ.get("TO_VIDEO_TEST_WORKSPACE")
EPISODES = Path(_TEST_WS).resolve() / "episodes" if _TEST_WS else None
sys.path.insert(0, str(PIPELINE_SCRIPTS))

#: 剪掉的都是 gitignored 产物目录（体积大，且与「受版本控制」无关）
_PRUNE = {"node_modules", "out", "audio", "__pycache__"}


def _episode_tree() -> dict[str, tuple[int, int]]:
    """→ {路径: (字节数, mtime_ns)}。实测 138 文件 / 3ms。"""
    snap: dict[str, tuple[int, int]] = {}
    stack = [EPISODES] if EPISODES and EPISODES.is_dir() else []
    while stack:
        for p in stack.pop().iterdir():
            if p.is_dir():
                if p.name not in _PRUNE:
                    stack.append(p)
                continue
            st = p.stat()
            snap[str(p)] = (st.st_size, st.st_mtime_ns)
    return snap


@pytest.fixture(scope="session", autouse=True)
def _episodes_stay_pristine():
    """真集工程树完整性守卫（env 门控）：本套用例**不得**改动真集工程文件。

    由来：`test_missing_config_announces_skipped_gate` 初版删掉真集的
    `pipeline.toml` 再 `finally` 放回 —— pytest 被 Ctrl-C 或进程被杀就把某集
    **唯一的可执行参数源**留在删除态。同一教训已写在 test_skeleton.py 文件头
    （正控一律在 tmp_path 镜像上做，见其 `mirror()`）。

    用**运行期快照**而非静态扫描：原违规的路径构造与 `unlink()` 分处两行，
    单行正则必漏，而漏报的门等于没门；快照对任何改动机制（含 subprocess 写盘、
    误传真路径的脚手架）一律有效，且 mtime 参与比对 ⇒ 「删掉再原样写回」也会红。

    `TO_VIDEO_TEST_WORKSPACE` 未设时 no-op：本仓（skill 仓）没有 episodes/，
    真树守卫只对 env 指来的内容工作区有意义。
    """
    if EPISODES is None:
        yield
        return
    before = _episode_tree()
    yield
    after = _episode_tree()
    diff = sorted(p for p in {*before, *after} if before.get(p) != after.get(p))
    assert not diff, (
        "用例改动了真集工程文件（请改用 tmp_path 镜像，见 test_skeleton.py::mirror）：\n  "
        + "\n  ".join(Path(p).relative_to(EPISODES).as_posix() for p in diff)
    )


@pytest.fixture()
def constants() -> dict:
    return json.loads((FIXTURES / "timing.json").read_text(encoding="utf-8"))


@pytest.fixture()
def manifest_items() -> list[dict]:
    return json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """最小工程骨架：fixtures 内容铺进临时目录（check/captions 等按真实布局消费）。"""
    root = tmp_path / "fixture-video"
    (root / "script").mkdir(parents=True)
    (root / "video" / "public" / "audio").mkdir(parents=True)
    (root / "video" / "src").mkdir(parents=True)
    for name in ("narration.md", "narration.json", "storyboard.md"):
        (root / "script" / name).write_bytes((FIXTURES / name).read_bytes())
    (root / "video" / "src" / "timing.json").write_bytes(
        (FIXTURES / "timing.json").read_bytes()
    )
    (root / "video" / "src" / "design").mkdir()
    (root / "video" / "src" / "design" / "theme.ts").write_bytes(
        (FIXTURES / "theme.ts").read_bytes()
    )
    (root / "video" / "public" / "audio" / "manifest.json").write_bytes(
        (FIXTURES / "manifest.json").read_bytes()
    )
    return root
