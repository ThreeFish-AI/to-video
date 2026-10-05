"""pipeline.py 对新 QA 选择器的转发回归。"""

import sys
from pathlib import Path

import pytest

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


def test_main_qa_forwards_transition_and_loop_as_strings(monkeypatch, tmp_path: Path):
    """穿过真实 argparse：type= 若返回元组，cmd 拼装会让 run() 的 join 崩 TypeError
    （cmd_qa 直传字符串的单测绕过 argparse，拦不住这一类）。"""
    commands: list[list[str]] = []
    monkeypatch.setattr(pipeline, "load_config", lambda root: ({}, {}))
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pipeline.py",
            "--project",
            str(tmp_path),
            "qa",
            "--video",
            "out/draft.mp4",
            "--transition",
            "p0-02:12",
            "--loop",
            "p0-01..p0-02",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        pipeline.main()

    assert exc.value.code == 0
    command = commands[0]
    assert all(isinstance(part, str) for part in command)
    assert command[command.index("--transition") + 1] == "p0-02:12"
    assert command[command.index("--loop") + 1] == "p0-01..p0-02"


@pytest.mark.parametrize(
    "flag, value",
    [("--transition", "p0-02:0"), ("--transition", "p0-02"), ("--loop", "p0-01")],
)
def test_main_qa_rejects_malformed_selector_before_forwarding(
    monkeypatch, tmp_path: Path, capsys, flag: str, value: str
):
    """pipeline 层仍前置校验：非法格式在 argparse 即拒，不转发到 qa_frames。"""
    monkeypatch.setattr(pipeline, "load_config", lambda root: ({}, {}))
    monkeypatch.setattr(pipeline, "run", lambda cmd, cwd=None: pytest.fail("不应转发"))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pipeline.py",
            "--project",
            str(tmp_path),
            "qa",
            "--video",
            "v.mp4",
            flag,
            value,
        ],
    )

    with pytest.raises(SystemExit) as exc:
        pipeline.main()

    assert exc.value.code == 2
    assert "格式必须为" in capsys.readouterr().err


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
