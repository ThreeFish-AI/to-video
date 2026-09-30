"""record_archify 会话生命周期：异常路径浏览器/context 必关（RSI-031）。

browser.close 与每章 ctx.close 原是顺序语句非结构保证——pump_until/encode_frames
的 sys.exit、wait_for_* 的 TimeoutError、激活失败等路径全部跳过关闭，长批次一次
超时即残留整套 headless 系统 Chrome。本文件用 MagicMock 假 browser/context 钉住
结构不变量（不起真 Chrome）；真 argv 取证与窄域清理命令见 PIPELINE.md §十。
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("playwright")  # 被测模块顶部 import playwright，缺则跳过

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import record_archify as ra  # noqa: E402


def _chromium() -> tuple[MagicMock, MagicMock]:
    chromium, browser = MagicMock(), MagicMock()
    chromium.launch.return_value = browser
    return chromium, browser


def test_launched_browser_closes_on_system_exit():
    """pump_until / encode_frames 的 sys.exit 出口：SystemExit 也必关（RSI-031 表因）。"""
    chromium, browser = _chromium()
    with pytest.raises(SystemExit):
        with ra.launched_browser(chromium, channel="chrome", headless=True):
            raise SystemExit("FAIL: 模拟 pump_until 超时 sys.exit")
    chromium.launch.assert_called_once_with(channel="chrome", headless=True)
    browser.close.assert_called_once()


def test_launched_browser_closes_on_timeout_shaped_exception():
    """wait_for_selector / wait_for_function 的 TimeoutError 形态（内置 Exception）出口。"""
    chromium, browser = _chromium()
    with pytest.raises(Exception, match="Timeout 15000ms exceeded"):
        with ra.launched_browser(chromium):
            raise Exception("Timeout 15000ms exceeded")
    browser.close.assert_called_once()


def test_launched_browser_closes_exactly_once_on_normal_path():
    chromium, browser = _chromium()
    with ra.launched_browser(chromium, headless=True) as browser_in_block:
        assert browser_in_block is browser
    browser.close.assert_called_once()


def test_close_ctx_quietly_swallows_already_closed():
    """兜底关闭对已关/非法态静默——不得盖掉原始异常，也不得在幂等二次调用时外抛。"""
    ctx = MagicMock()
    ctx.close.side_effect = RuntimeError(
        "Target page, context or browser has been closed"
    )
    ra._close_ctx_quietly(ctx)  # 不外抛即通过
    assert ctx.close.call_count == 1
    ra._close_ctx_quietly(ctx)  # 幂等可二次调用
    assert ctx.close.call_count == 2


def test_record_chapters_activation_failure_closes_ctx(tmp_path):
    """激活失败路径的每章 context 兜底：手工 close 已收敛进 finally，仍必须关。"""
    browser, ctx = MagicMock(), MagicMock()
    browser.new_context.return_value = ctx
    page = ctx.new_page.return_value
    answers = iter([None, "showAll()"])  # evaluate 依次 = activate() / active()
    page.evaluate.side_effect = lambda *a, **k: next(answers)
    a = SimpleNamespace(
        all_chapters=True,
        capture="cdp",
        scale=2,
        settle_ms=1200,
        min_fps=18.0,
        encode="h264",
        crf=16,
    )
    views = [{"id": "v1", "focus": ["n1"]}]
    src = tmp_path / "src.html"
    src.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(SystemExit, match="激活失败"):
        ra.record_chapters(browser, src, tmp_path, tmp_path, "s", views, a)
    ctx.close.assert_called_once()  # 恰一次 = finally 兜底，无双关
