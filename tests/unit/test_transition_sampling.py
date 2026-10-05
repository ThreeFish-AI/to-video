"""Morph/loop 抽帧采样器的纯函数回归。"""

import argparse

import pytest

from qa_frames import (
    _custom_samples,
    loop_samples,
    parse_loop,
    parse_transition,
    transition_samples,
)


TIMELINE = {
    "p0-01": (0.0, 1.0),
    "p0-02": (1.0, 2.0),
    "p0-03": (3.0, 2.0),
    "p1-01": (5.0, 1.0),
}


def test_transition_samples_cover_boundary_and_midpoint():
    samples = transition_samples(TIMELINE, "p0-02", 6, 30)

    assert [name for name, _timestamp in samples] == [
        "p0-02-t6-before",
        "p0-02-t6-start",
        "p0-02-t6-mid",
        "p0-02-t6-end",
        "p0-02-t6-after",
    ]
    assert [round(timestamp, 3) for _name, timestamp in samples] == [
        0.967,
        1.0,
        1.1,
        1.167,
        1.2,
    ]


def test_transition_samples_clip_and_deduplicate_at_timeline_edges():
    samples = transition_samples(TIMELINE, "p0-01", 1, 30)

    assert len(samples) == 2
    assert samples[0][1] == 0.0


def test_loop_samples_preserve_manifest_order_and_same_scene_boundary():
    samples = loop_samples(TIMELINE, "p0-01", "p0-03", 30)

    assert [name for name, _timestamp in samples] == [
        "p0-01-l-head0",
        "p0-01-l-head1",
        "p0-03-l-tail0",
        "p0-03-l-tail1",
    ]
    assert samples[-1][1] < 5.0
    assert loop_samples(TIMELINE, "p1-01", "p0-03", 30) == []


@pytest.mark.parametrize(
    "value",
    ["p0-01", "p0-01:0", "p0-01:-2", "p0-01:2.5"],
)
def test_transition_parser_requires_positive_integer_window(value: str):
    with pytest.raises(argparse.ArgumentTypeError):
        parse_transition(value)


def test_loop_parser_keeps_complete_sentence_ids():
    assert parse_loop("p0-01..p0-03") == ("p0-01", "p0-03")


def test_custom_sampling_rejects_offset_that_removes_transition_boundary():
    parser = argparse.ArgumentParser()
    with pytest.raises(SystemExit):
        _custom_samples(
            TIMELINE,
            [("p0-02", 6)],
            [],
            None,
            30,
            2.0,
            parser,
        )


def test_custom_sampling_accepts_transition_inside_tail_frames():
    parser = argparse.ArgumentParser()
    samples = _custom_samples(
        TIMELINE,
        [("p1-01", 30)],
        [],
        None,
        30,
        0.0,
        parser,
        tail_frames=60,
    )

    assert samples[-1][1] == 6.0


def test_custom_samples_return_chronological_order_across_requests():
    """多请求组合时末位必须是时间轴最后样本：check_frames 的渐黑豁免只认列表末位，
    请求序（transition 先于 loop）会把 loop 末帧 149 放在末位，时间轴最后的
    过渡 after 帧 180 伸入 tailSec 渐黑区时反而拿不到豁免。"""
    parser = argparse.ArgumentParser()
    samples = _custom_samples(
        TIMELINE,
        [("p1-01", 30)],
        [("p0-01", "p0-03")],
        None,
        30,
        0.0,
        parser,
        tail_frames=60,
    )

    timestamps = [timestamp for _name, timestamp in samples]
    assert timestamps == sorted(timestamps)
    assert samples[-1][1] == 6.0
