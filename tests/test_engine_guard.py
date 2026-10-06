"""tts.py 引擎护栏：漏写 --engine 的克隆参数硬失败 + 音色签名标记。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tts import check_voice_marker, server_launch_hint, write_voice_marker  # noqa: E402

from helpers import timing_constants


def test_engine_guard_blocks_clone_flags_without_engine(tmp_path):
    """照抄文档打了 --ref/--style 却丢了 --engine → 必须退出非零（合成路径不再静默降级）。"""
    import subprocess

    script = Path(__file__).resolve().parents[1] / "scripts" / "tts.py"
    r = subprocess.run(
        [sys.executable, str(script), "--style", "sunny"],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert r.returncode != 0
    assert "--engine indextts" in (r.stderr + r.stdout)


def test_voice_marker_mismatch_blocks(tmp_path, capsys):
    write_voice_marker(tmp_path, "indextts|indextts|passionate|3ed0d9d60d4b")
    try:
        check_voice_marker(
            tmp_path, "indextts|indextts|sunny|54b699cce97f", allow_switch=False
        )
        raise AssertionError("应硬失败")
    except SystemExit as e:
        assert "音色签名与上次合成不一致" in str(e.code)
        assert "--allow-voice-switch" in str(e.code)


def test_voice_marker_same_signature_passes(tmp_path):
    write_voice_marker(tmp_path, "edge|zh-CN-YunxiNeural|+4%")
    check_voice_marker(
        tmp_path, "edge|zh-CN-YunxiNeural|+4%", allow_switch=False
    )  # 不抛即过


def test_voice_marker_explicit_switch_allowed(tmp_path):
    write_voice_marker(tmp_path, "edge|zh-CN-YunxiNeural|+4%")
    check_voice_marker(
        tmp_path, "indextts|indextts|sunny|54b699cce97f", allow_switch=True
    )


def test_voice_marker_absent_passes(tmp_path):
    check_voice_marker(tmp_path, "whatever", allow_switch=False)  # 无标记（首次合成）


def test_server_launch_hint_has_no_placeholder():
    hint = server_launch_hint()
    assert "<仓库路径>" not in hint
    assert "tts_server.py" in hint and "index-tts" in hint
    assert "checkpoints" in hint


# ── RSI-040 人为触发原则主闸 ─────────────────────────────────────────


def test_indextts_synthesis_requires_final_voice(tmp_path):
    """缺 --final-voice 的 indextts 实跑硬失败——闸先于一切工程文件读取，无需 fixture。"""
    import subprocess

    script = Path(__file__).resolve().parents[1] / "scripts" / "tts.py"
    r = subprocess.run(
        [sys.executable, str(script), "--engine", "indextts"],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert r.returncode != 0
    combined = r.stderr + r.stdout
    assert "--final-voice" in combined, "报错须指名授权 flag"
    assert "显式点名" in combined, "报错须说明人为触发原则"


def _indextts_plan_project(tmp_path):
    """最小工程：一句 narration + timing.json + 参考样本（--plan 纯本地可跑）。"""
    proj = tmp_path / "proj"
    (proj / "script").mkdir(parents=True)
    (proj / "script" / "narration.json").write_text(
        '[{"id": "p0-01", "scene": "P0", "text": "想让 AI 自己改进自己。"}]',
        encoding="utf-8",
    )
    (proj / "video" / "src").mkdir(parents=True)
    (proj / "video" / "src" / "timing.json").write_text(
        json.dumps(timing_constants()),
        encoding="utf-8",
    )
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"x" * 16)
    return proj, ref


def test_indextts_plan_exempt_from_final_voice(tmp_path):
    """--plan 纯本地预演免闸：无需授权照常排期（不连服务）。"""
    import subprocess

    proj, ref = _indextts_plan_project(tmp_path)
    script = Path(__file__).resolve().parents[1] / "scripts" / "tts.py"
    r = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project",
            str(proj),
            "--engine",
            "indextts",
            "--ref",
            str(ref),
            "--style",
            "story",
            "--plan",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert r.returncode == 0, r.stderr


def test_final_voice_with_edge_engine_hard_fails(tmp_path):
    """edge + --final-voice：归入 clone_only 硬失败族——授权给了引擎没给，
    照跑会把「本人要的终稿声音」静默降级成 edge 草声且留假授权痕迹。"""
    import subprocess

    script = Path(__file__).resolve().parents[1] / "scripts" / "tts.py"
    r = subprocess.run(
        [sys.executable, str(script), "--final-voice"],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert r.returncode != 0
    combined = r.stderr + r.stdout
    assert "仅对 --engine indextts 生效" in combined
    assert "--final-voice" in combined


def test_preexisting_indextts_marker_still_blocks_without_flag(tmp_path):
    """钉死「同签名放行」缺口：预写 indextts 签名后，同签名实跑无 flag 仍被主闸拦
    （且先于 .engine 比对——报错不提音色签名）。"""
    import hashlib
    import subprocess

    proj, ref = _indextts_plan_project(tmp_path)
    audio = proj / "video" / "public" / "audio"
    audio.mkdir(parents=True)
    ref_sha1 = hashlib.sha1(ref.read_bytes()).hexdigest()[:12]
    (audio / ".engine").write_text(
        f"indextts|indextts|story|{ref_sha1}\n", encoding="utf-8"
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "tts.py"
    r = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project",
            str(proj),
            "--engine",
            "indextts",
            "--ref",
            str(ref),
            "--style",
            "story",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert r.returncode != 0
    combined = r.stderr + r.stdout
    assert "--final-voice" in combined, "主闸须拦同签名无授权实跑"
    assert "音色签名" not in combined, "授权闸应先于签名比对暴露"


def test_wrong_signature_marker_cannot_preempt_gate(tmp_path):
    """顺序性不变量（RSI-040）：授权闸先于 .engine 签名比对——签名**不符** + 无 flag
    时，报错必须是授权错而非「音色签名」错（若未来有人把闸挪到比对之后，本测试
    会先炸出签名消息而红）。"""
    import subprocess

    proj, ref = _indextts_plan_project(tmp_path)
    audio = proj / "video" / "public" / "audio"
    audio.mkdir(parents=True)
    # 刻意写**不一致**的旧签名：闸若在比对后，check_voice_marker 会先行硬失败
    (audio / ".engine").write_text("edge|zh-CN-YunxiNeural|+4%\n", encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "tts.py"
    r = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project",
            str(proj),
            "--engine",
            "indextts",
            "--ref",
            str(ref),
            "--style",
            "story",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )
    assert r.returncode != 0
    combined = r.stderr + r.stdout
    assert "--final-voice" in combined, "授权闸应先于签名比对暴露（不符签名场景）"
    assert "音色签名" not in combined, "闸被挪到比对之后——签名错抢跑了"
