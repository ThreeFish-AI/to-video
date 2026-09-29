"""tts_server remedy ↔ 客户端 _deterministic_mps_oom 的跨文件字符串契约执法。

服务端把确认命中 MPS high watermark 的 OOM 转成以「MPS 显存上限不足」开头的
500 detail，客户端按该前缀转 NonRetryableError 跳过 4 轮重试；未确认触顶和未设上限
分支均以「MPS 显存耗尽」开头、留在 5xx 重试桶。契约是纯字符串约定
（tts_server.py / tts.py / VOICE-CLONING §七三载体），任一侧改写措辞会静默改变
重试策略。此处用 AST 抽取 remedy 与纯函数 helper（不 import fastapi/torch），并以
mock urlopen 验证两个 http_* 封装的分流及确定性失败的句 id 包装。
"""

from __future__ import annotations

import ast
import asyncio
import io
import json
import os
import re
import sys
import types
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tts  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _expr_text(node: ast.expr) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            part.value if isinstance(part, ast.Constant) else "15.98"
            for part in node.values
        )
    return ""


def _remedy_literals() -> tuple[list[str], list[str]]:
    """AST 抽 tts_server.py 三个 remedy 的隐式拼接全文。

    确认触顶分支应恰一处；未确认触顶与未设上限两个分支都必须保持可重试。
    """
    tree = ast.parse((SCRIPTS / "tts_server.py").read_text(encoding="utf-8"))
    capped: list[str] = []
    retryable: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "remedy"
            for target in node.targets
        ):
            continue
        text = _expr_text(node.value)
        if text.startswith("MPS 显存上限不足"):
            capped.append(text)
        elif text.startswith("MPS 显存耗尽"):
            retryable.append(text)
    return capped, retryable


def _server_helpers() -> dict[str, object]:
    """只执行与 MPS OOM/上限相关的顶层定义，隔离 Web 与模型依赖。"""
    tree = ast.parse((SCRIPTS / "tts_server.py").read_text(encoding="utf-8"))
    function_names = {"_is_mps_oom", "_mps_limit_exceeded", "_apply_mps_limit"}
    body: list[ast.stmt] = []
    for node in tree.body:
        if (isinstance(node, ast.FunctionDef) and node.name in function_names) or (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "_MPS_SIZE_RE"
                for target in node.targets
            )
        ):
            body.append(node)
    namespace: dict[str, object] = {"STATE": {}, "os": os, "re": re}
    module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    exec(compile(module, str(SCRIPTS / "tts_server.py"), "exec"), namespace)  # noqa: S102
    return namespace


def test_remedy_prefixes_pin_client_matcher():
    """仅确认触顶分支命中不可重试前缀，其余两个分支均保留重试。"""
    capped, retryable = _remedy_literals()
    assert len(capped) == 1, (
        f"确认触顶 remedy 应恰一处，实得 {len(capped)}——客户端 startswith 匹配"
        "依赖其前缀，多处或零处都是契约漂移"
    )
    assert len(retryable) == 2, f"可重试 remedy 应恰有两处，实得 {len(retryable)}"
    tail = " 原始错误: MPS backend out of memory (...)"
    assert tts._deterministic_mps_oom(capped[0] + tail) is True
    assert all(
        tts._deterministic_mps_oom(remedy + tail) is False for remedy in retryable
    )


def test_mps_oom_type_fallback_is_scoped_to_mps_device():
    helpers = _server_helpers()
    state = helpers["STATE"]
    is_mps_oom = helpers["_is_mps_oom"]
    oom_type = type("OutOfMemoryError", (RuntimeError,), {})

    state["device"] = "cpu"
    assert is_mps_oom(oom_type("allocation failed")) is False
    state["device"] = "cuda"
    assert is_mps_oom(oom_type("allocation failed")) is False
    state["device"] = "mps"
    assert is_mps_oom(oom_type("allocation failed")) is True


def test_mps_limit_exceeded_requires_confirmed_high_watermark_hit():
    limit_exceeded = _server_helpers()["_mps_limit_exceeded"]
    hit = (
        "MPS backend out of memory (MPS allocated: 7.50 GiB, other allocations: "
        "256.00 MiB, max allowed: 8.00 GiB). Tried to allocate 512.00 MiB"
    )
    below = (
        "MPS backend out of memory (MPS allocated: 6.00 GiB, other allocations: "
        "256.00 MiB, max allowed: 8.00 GiB). Tried to allocate 512.00 MiB"
    )
    unknown = "MPS backend out of memory. Tried to allocate 512.00 MiB"

    assert limit_exceeded(hit) is True
    assert limit_exceeded(below) is False
    assert limit_exceeded(unknown) is False


def test_explicit_zero_overrides_inherited_high_watermark(monkeypatch):
    apply_limit = _server_helpers()["_apply_mps_limit"]
    calls: list[float] = []
    fake_torch = types.ModuleType("torch")
    fake_torch.backends = types.SimpleNamespace(
        mps=types.SimpleNamespace(is_available=lambda: True)
    )
    fake_torch.mps = types.SimpleNamespace(
        recommended_max_memory=lambda: 16 * 1024**3,
        set_per_process_memory_fraction=calls.append,
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setenv("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.75")

    assert apply_limit(0, "mps") is None
    assert os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] == "0.0"
    assert calls == [0.0]


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
    capped, retryable = _remedy_literals()
    tail = " 原始错误: MPS backend out of memory (...)"
    _patch_urlopen(monkeypatch, capped[0] + tail, retryable[0] + tail)

    with pytest.raises(tts.NonRetryableError) as ei:
        tts.http_synthesize("http://s", "CAP", "ref.wav", None, 1.0, 1.0, "zh")
    assert "MPS 显存上限不足" in str(ei.value)

    with pytest.raises(RuntimeError) as ei2:
        tts.http_synthesize("http://s", "text", "ref.wav", None, 1.0, 1.0, "zh")
    assert not isinstance(ei2.value, tts.NonRetryableError)


def test_http_synthesize_block_splits_deterministic_oom(monkeypatch):
    """块路径同款分流（story 档主路径）。"""
    capped, retryable = _remedy_literals()
    tail = " 原始错误: MPS backend out of memory (...)"
    _patch_urlopen(monkeypatch, capped[0] + tail, retryable[0] + tail)

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
