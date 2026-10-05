"""过渡/loop CLI 互斥参数回归。"""

import sys

import pytest

import qa_frames


def test_custom_sampling_rejects_legacy_selector(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qa_frames.py",
            "--transition",
            "p0-02:6",
            "--last-n",
            "1",
            "draft.mp4",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        qa_frames.main()

    assert exc.value.code == 2
    assert "只可与 --scene 组合" in capsys.readouterr().err
