"""跨测试文件共享的纯 helper（pytest 夹具归 conftest.py，纯函数归此）。

沿革：`_zh_digest`、剥 `TO_VIDEO_*` env、doctor 离线夹具、timing 六键常数此前在
多个测试文件各写一份（乃至同名异义），双份维护必然漂移——收敛到唯一住处。
刻意异值的用例（如 check_script 淡入淡出违约形态的 `sceneCrossFadeSec=0.9`）
仍自持字面量，不从此处取。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import urllib.error

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def zh_digest(text: str) -> str:
    """与 build_narration.zh_digest 同口径（sha1 前 12 位）——锁内容的期望值。"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def to_video_stripped_env() -> dict[str, str]:
    """剥掉 `TO_VIDEO_*`：锚点 env（`TO_VIDEO_WORKSPACE`）优先级高于 CWD 搜索，
    外部残留会让用例静默锚去别处；集成模式的 env 尤其必须挡在门外。"""
    return {k: v for k, v in os.environ.items() if not k.startswith("TO_VIDEO_")}


def timing_constants() -> dict:
    """六键时序常数（与 fixtures/timing.json 同源）。写 timing.json 的用例统一
    从此取值，防第二事实源漂移。"""
    return json.loads((FIXTURES / "timing.json").read_text(encoding="utf-8"))


def offline_doctor_project(tmp_path: Path, monkeypatch) -> dict:
    """doctor「其余检查全绿」夹具：timing.json + 指纹相符样本 + 工作区哨兵 +
    IndexTTS 服务离线桩 →（cfg，engine=indextts 且 ref 指纹与实况一致）。

    沿革：test_stages 离线服务用例与 test_tts_resume._doctor_fixture 原各写一份。
    """
    import pipeline  # noqa: E402 - conftest 已把 scripts/ 注入 sys.path

    (tmp_path / "video" / "src").mkdir(parents=True)
    (tmp_path / "video" / "src" / "timing.json").write_text(
        json.dumps(timing_constants()), encoding="utf-8"
    )
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"RIFF-fixture")
    (tmp_path / ".to-video-root").touch()  # 工作区哨兵：tts.ref 相对工作区根解析
    monkeypatch.setenv("TO_VIDEO_WORKSPACE", str(tmp_path))

    def offline(*_a, **_k):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(pipeline.urllib.request, "urlopen", offline)
    return {
        "tts": {
            "engine": "indextts",
            "ref": "ref.wav",
            "ref_sha1": hashlib.sha1(ref.read_bytes()).hexdigest()[:12],
        }
    }
