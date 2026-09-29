"""tts_server remedy ↔ 客户端 _deterministic_mps_oom 的跨文件字符串契约执法。

服务端把确定性 MPS 水位线 OOM 转成以「MPS 显存上限不足」开头的 500 detail，客户端
按该前缀转 NonRetryableError 跳过 4 轮重试；未设上限分支以「MPS 显存耗尽」开头、
留在 5xx 重试桶。契约是纯字符串约定（tts_server.py / tts.py / VOICE-CLONING §七
三载体），任一侧改写措辞会静默退回分钟级重试——fail-safe 方向、无报错无红线。
此处用 AST 抽 tts_server 两个 remedy 的首字面量钉住（不 import fastapi/torch，
测试环境可直接运行），并以 mock urlopen 验证两个 http_* 封装的分流，与确定性
失败报错的句 id 包装（remedy「拆短该句」的定位锚点）。
"""

from __future__ import annotations

import ast
import asyncio
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tts  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _remedy_literals() -> tuple[list[str], list[str]]:
    """AST 抽 tts_server.py 两个 remedy 的隐式拼接全文。

    上限在场分支是 f-string 拼接（JoinedStr），槽位以样例值 15.98 代入；
    未设上限分支是纯字面量拼接（Constant）。各应恰一处。
    """
    tree = ast.parse((SCRIPTS / "tts_server.py").read_text(encoding="utf-8"))
    capped: list[str] = []
    unset: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            text = "".join(
                v.value if isinstance(v, ast.Constant) else "15.98" for v in node.values
            )
            if "MPS 显存上限不足" in text:
                capped.append(text)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "MPS 显存耗尽" in node.value:
                unset.append(node.value)
    return capped, unset


def test_remedy_prefixes_pin_client_matcher():
    """上限分支前缀必命中、未设上限分支必不命中（各恰一处，防多处漂移）。"""
    capped, unset = _remedy_literals()
    assert len(capped) == 1, (
        f"上限在场 remedy 应恰一处，实得 {len(capped)}——客户端 startswith 匹配"
        "依赖其前缀，多处或零处都是契约漂移"
    )
    assert len(unset) == 1, f"未设上限 remedy 应恰一处，实得 {len(unset)}"
    tail = " 原始错误: MPS backend out of memory (...)"
    assert tts._deterministic_mps_oom(capped[0] + tail) is True
    assert tts._deterministic_mps_oom(unset[0] + tail) is False


def _http_error_500(detail: str) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "http://127.0.0.1:8766/synthesize",
        500,
        "Internal Server Error",
        None,
        io.BytesIO(json.dumps({"detail": detail}).encode()),
    )


def _patch_urlopen(monkeypatch, detail_capped: str, detail_unset: str) -> None:
    def fake_urlopen(req, timeout=None):  # noqa: ARG001 - 签名对齐真 urlopen
        body = json.loads(req.data.decode())
        detail = detail_capped if body.get("text") == "CAP" else detail_unset
        raise _http_error_500(detail)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def test_http_synthesize_splits_deterministic_oom(monkeypatch):
    """同一 500：上限分支 → NonRetryableError（不重试）；未设上限 → RuntimeError（重试）。"""
    capped, unset = _remedy_literals()
    tail = " 原始错误: MPS backend out of memory (...)"
    _patch_urlopen(monkeypatch, capped[0] + tail, unset[0] + tail)

    with pytest.raises(tts.NonRetryableError) as ei:
        tts.http_synthesize("http://s", "CAP", "ref.wav", None, 1.0, 1.0, "zh")
    assert "MPS 显存上限不足" in str(ei.value)

    with pytest.raises(RuntimeError) as ei2:
        tts.http_synthesize("http://s", "text", "ref.wav", None, 1.0, 1.0, "zh")
    assert not isinstance(ei2.value, tts.NonRetryableError)


def test_http_synthesize_block_splits_deterministic_oom(monkeypatch):
    """块路径同款分流（story 档主路径）。"""
    capped, unset = _remedy_literals()
    tail = " 原始错误: MPS backend out of memory (...)"
    _patch_urlopen(monkeypatch, capped[0] + tail, unset[0] + tail)

    with pytest.raises(tts.NonRetryableError):
        tts.http_synthesize_block(
            "http://s", "CAP", "ref.wav", None, 1.0, 1.0, "zh", 1, [1.0], 0.0, 0.0
        )
    with pytest.raises(RuntimeError) as ei:
        tts.http_synthesize_block(
            "http://s", "text", "ref.wav", None, 1.0, 1.0, "zh", 1, [1.0], 0.0, 0.0
        )
    assert not isinstance(ei.value, tts.NonRetryableError)


def test_deterministic_oom_error_carries_sid(tmp_path, monkeypatch):
    """确定性失败最终报错带句 id：remedy 要求「拆短该句」，丢 id 即丢定位锚点。"""
    capped, _ = _remedy_literals()
    detail = capped[0] + " 原始错误: MPS backend out of memory (...)"

    def fake_http(*args, **kwargs):  # noqa: ARG001
        raise tts.NonRetryableError(f"HTTP 500: {detail}")

    monkeypatch.setattr(tts, "http_synthesize", fake_http)
    with pytest.raises(tts.NonRetryableError) as ei:
        asyncio.run(
            tts.synth_indextts(
                asyncio.Semaphore(1),
                {"id": "s042", "text": "测试句"},
                True,
                "ref.wav",
                "sha",
                "neutral",
                None,
                1.0,
                1.0,
                "zh",
                "v25",
                "http://s",
                tmp_path,
            )
        )
    assert "s042" in str(ei.value), "确定性 OOM 报错须带句 id（与重试耗尽分支同款）"
