"""langs：语言注册表 / 路径派生 / 长度单位 / 运行期选择解析的机制契约。

zh 全部路径与既有字面路径逐字节相等是向后兼容的硬约束（存量集零改动可用）；
en 的 `.en` 后缀 / `audio/en/` 子目录形态在此钉死——消费者只许经本模块派生
路径、不得内联拼接（内联即第二事实源）。tts.py 的内联镜像表（导入边界所迫）
与 LANGS 的一致性钉在 test_tts_lang_mirror.py，此处不重复执法。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import langs  # noqa: E402


def test_registry_pins_mechanism_constants():
    """注册表四元组是 tts 码 / 音色 / 长度单位的唯一事实源（TS 侧镜像受
    test_skeleton 执法，Python 侧消费者全经 LANGS 取值）。"""
    assert langs.PRIMARY == "zh"
    assert langs.LANGS["zh"].tts_code == "ZH"
    assert langs.LANGS["en"].tts_code == "EN"
    assert langs.LANGS["zh"].edge_voice == "zh-CN-YunxiNeural"
    assert langs.LANGS["en"].edge_voice == "en-US-AndrewNeural"
    assert langs.LANGS["zh"].unit == "字"
    assert langs.LANGS["en"].unit == "词"


def test_zh_paths_are_byte_identical_to_legacy_literals():
    """主语言不加后缀：全部产物路径逐字节等于改造前的字面拼接。"""
    root = Path("/ws/ep")
    assert langs.suffix("zh") == ""
    assert langs.narration_md(root, "zh") == root / "script" / "narration.md"
    assert langs.narration_json(root, "zh") == root / "script" / "narration.json"
    assert langs.lock(root, "zh") == root / "script" / "narration.lock.json"
    assert langs.audio_dir(root, "zh") == root / "video" / "public" / "audio"
    assert langs.manifest(root, "zh") == (
        root / "video" / "public" / "audio" / "manifest.json"
    )
    assert langs.captions(root, "zh", "srt") == root / "out" / "captions.srt"
    assert langs.captions(root, "zh", "vtt") == root / "out" / "captions.vtt"
    assert langs.render_out(root, "draft", "zh") == root / "out" / "draft.mp4"
    assert langs.render_out(root, "final", "zh") == root / "out" / "final.mp4"
    assert langs.frames_dir(root, "zh") == root / "out" / "frames"


def test_en_paths_add_suffix_and_audio_subdir():
    """非主语言：文件名主干后加 `.en`（movie.en.srt 业界惯例）、配音落同名子目录
    （独立 .engine 签名与 manifest 的护栏前提）。"""
    root = Path("/ws/ep")
    assert langs.suffix("en") == ".en"
    assert langs.narration_md(root, "en") == root / "script" / "narration.en.md"
    assert langs.narration_json(root, "en") == root / "script" / "narration.en.json"
    assert langs.lock(root, "en") == root / "script" / "narration.en.lock.json"
    assert langs.audio_dir(root, "en") == (root / "video" / "public" / "audio" / "en")
    assert langs.manifest(root, "en") == (
        root / "video" / "public" / "audio" / "en" / "manifest.json"
    )
    assert langs.captions(root, "en", "srt") == root / "out" / "captions.en.srt"
    assert langs.render_out(root, "draft", "en") == root / "out" / "draft.en.mp4"
    assert langs.render_out(root, "final", "en") == root / "out" / "final.en.mp4"
    assert langs.frames_dir(root, "en") == root / "out" / "frames.en"


def test_render_out_rejects_unknown_kind():
    with pytest.raises(ValueError, match="kind"):
        langs.render_out(Path("/ws"), "stills", "en")


def test_length_units():
    """zh 数码点（与既有 len 口径一致，防黄金漂移）；en 数词（撇号/连字符内连
    各计 1 词，小数点切词）。"""
    assert langs.length("一句话六个字呀", "zh") == 7
    assert langs.length("IndexTTS 2.5", "en") == 3  # IndexTTS / 2 / 5
    assert langs.length("don't stop", "en") == 2  # 撇号内连：don't 计 1 词
    assert langs.length("state-of-the-art models", "en") == 2
    assert langs.length("Hello, world!", "en") == 2
    # en/em dash 是断词标点（X—Y 为标准英文排版），只有连字符内连
    assert langs.length("The loop—and the harness—matter.", "en") == 6
    assert langs.length("3–5 steps", "en") == 3
    assert langs.length("non‑breaking hy‐phen", "en") == 2  # U+2011 / U+2010


def test_validate_unknown_lang_raises_with_registry():
    """未知语言大声失败并报出合法集——静默回落会产出错版视频。"""
    with pytest.raises(ValueError, match="注册表"):
        langs.validate("ja")
    with pytest.raises(ValueError, match="注册表"):
        langs.suffix("english")


def test_parse_selection_semantics():
    declared = ["zh", "en"]
    # None → None：缺省策略归调用方（昂贵命令显式化，两种缺省语义不同）
    assert langs.parse_selection(None, declared) is None
    assert langs.parse_selection("all", declared) == ["zh", "en"]
    assert langs.parse_selection("en,zh", declared) == ["en", "zh"]  # 保序
    assert langs.parse_selection("zh,zh,en", declared) == ["zh", "en"]  # 去重保序
    assert langs.parse_selection(" all ", declared) == ["zh", "en"]  # 首尾空白容错


def test_parse_selection_rejects_bad_values():
    declared = ["zh", "en"]
    # 已注册但未在本集声明（防在未声明 en 的集上静默跑半套）
    with pytest.raises(ValueError, match="未在本集"):
        langs.parse_selection("en", ["zh"])
    # 未注册语言
    with pytest.raises(ValueError, match="注册表"):
        langs.parse_selection("zh,fr", declared)
    # 空串 / 空白项
    for bad in ("", "   ", "zh,", ",zh", "zh,,en"):
        with pytest.raises(ValueError, match="非法"):
            langs.parse_selection(bad, declared)
