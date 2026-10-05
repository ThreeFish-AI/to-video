"""pipeline.py 对新 QA 选择器的转发回归。"""

from pathlib import Path

import pipeline


def test_cmd_qa_forwards_transition_and_loop_selectors(monkeypatch, tmp_path: Path):
    calls: list[tuple[list[str], Path]] = []

    def fake_run(command: list[str], cwd: Path) -> int:
        calls.append((command, cwd))
        return 0

    monkeypatch.setattr(pipeline, "run", fake_run)
    assert (
        pipeline.cmd_qa(
            tmp_path,
            {},
            "out/draft.mp4",
            ["P0"],
            None,
            [],
            True,
            0.5,
            transition=["p0-02:6"],
            loop=["p0-01..p0-03"],
            lang="zh",
        )
        == 0
    )

    command, cwd = calls[0]
    assert cwd == tmp_path
    assert command[-10:] == [
        "--scene",
        "P0",
        "--transition",
        "p0-02:6",
        "--loop",
        "p0-01..p0-03",
        "--check",
        "--scale",
        "0.5",
        "out/draft.mp4",
    ]


def test_cmd_qa_forwards_explicit_zero_selector_values(monkeypatch, tmp_path: Path):
    calls: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path) -> int:
        calls.append(command)
        return 0

    monkeypatch.setattr(pipeline, "run", fake_run)
    pipeline.cmd_qa(
        tmp_path,
        {},
        "draft.mp4",
        None,
        0,
        [],
        False,
        None,
        beat_heads=0,
    )

    assert "--last-n" in calls[0] and "0" in calls[0]
    assert "--beat-heads" in calls[0]
