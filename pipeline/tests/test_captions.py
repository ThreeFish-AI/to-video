"""captions 的时间戳与格式（srt/vtt 字节级黄金）+ 双语槽位与句尾剥除。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from captions import (  # noqa: E402
    build_cues,
    fmt_ts_srt,
    fmt_ts_vtt,
    render_srt,
    render_vtt,
    strip_tail,
)

C = {
    "fps": 30,
    "sentenceGapSec": 0.32,
    "sceneGapSec": 0.9,
    "leadInSec": 0.6,
    "tailSec": 2.0,
}

CAPTIONS = Path(__file__).resolve().parents[1] / "scripts" / "captions.py"


def test_timestamp_format():
    assert fmt_ts_srt(3661.5) == "01:01:01,500"
    assert fmt_ts_vtt(3661.5) == "01:01:01.500"


def test_cue_end_excludes_gap():
    """外挂字幕 cue 终点 = 起点 + durationSec（不含句间停顿）——与烧录字幕的有意分歧。"""
    items = [
        {"id": "p0-01", "scene": "P0", "text": "甲。", "durationSec": 3.0},
        {"id": "p0-02", "scene": "P0", "text": "乙。", "durationSec": 2.0},
    ]
    cues = build_cues(items, C)
    assert cues[0][0] == 0.6 and abs(cues[0][1] - 3.6) < 1e-9  # 0.6 + 3.0，非 0.6+3.32
    assert abs(cues[1][0] - 0.6 - round((3.0 + 0.32) * 30) / 30) < 1e-9


def test_srt_golden():
    items = [{"id": "p0-01", "scene": "P0", "text": "你好。", "durationSec": 3.0}]
    srt = render_srt(build_cues(items, C))
    assert (
        srt == "1\n00:00:00,600 --> 00:00:03,600\n你好\n"
    )  # 句尾「。」剥除（2026-09-14 字幕风格）


def test_vtt_header():
    items = [{"id": "p0-01", "scene": "P0", "text": "你好。", "durationSec": 3.0}]
    vtt = render_vtt(build_cues(items, C))
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:00.600 --> 00:00:03.600" in vtt


# ---------------- 双语：en 句尾剥除与输出槽位 ----------------


def test_en_strips_single_trailing_period_only():
    """en 剥**单个**句尾 '.'；省略号形态（'..' 及以上）不剥——悬念是内容不是噪音。"""
    assert strip_tail("Hello world.", "en") == "Hello world"
    assert strip_tail("Wait...", "en") == "Wait..."
    assert strip_tail("Hmm..", "en") == "Hmm.."
    assert strip_tail("No period", "en") == "No period"


def test_zh_strip_unchanged():
    """zh 仍 rstrip「。」——既有黄金口径零漂移。"""
    assert strip_tail("你好。", "zh") == "你好"
    assert strip_tail("真的是这样吗？？", "zh") == "真的是这样吗？？"


def test_en_cues_use_en_text():
    items = [{"id": "p0-01", "scene": "P0", "text": "Hello world.", "durationSec": 3.0}]
    assert build_cues(items, C, lang="en")[0][2] == "Hello world"


def test_en_output_slot_and_missing_manifest_hint(project):
    """--lang en 读 audio/en/manifest.json、写 captions.en.*，不落 zh 槽位；
    en manifest 缺失时报错点名 --narration-lang en。"""
    r = subprocess.run(
        [sys.executable, str(CAPTIONS), "--project", str(project), "--lang", "en"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0
    assert "audio/en/manifest.json" in r.stdout + r.stderr
    assert "--narration-lang en" in r.stdout + r.stderr

    import shutil

    en_dir = project / "video" / "public" / "audio" / "en"
    en_dir.mkdir()
    shutil.copy(
        project / "video" / "public" / "audio" / "manifest.json",
        en_dir / "manifest.json",
    )
    r2 = subprocess.run(
        [sys.executable, str(CAPTIONS), "--project", str(project), "--lang", "en"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r2.returncode == 0, r2.stderr
    assert (project / "out" / "captions.en.srt").is_file()
    assert (project / "out" / "captions.en.vtt").is_file()
    assert not (project / "out" / "captions.srt").exists()  # en 不落 zh 槽位
