"""record_archify 会话生命周期：异常路径浏览器/context 必关（RSI-031）。

browser.close 与每章 ctx.close 原是顺序语句非结构保证——pump_until/encode_frames
的 sys.exit、wait_for_* 的 TimeoutError、激活失败等路径全部跳过关闭，长批次一次
超时即残留整套 headless 系统 Chrome。本文件用 MagicMock 假 browser/context 钉住
结构不变量（不起真 Chrome）；真 argv 取证与窄域清理命令见 PIPELINE.md §十。
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytest.importorskip("playwright")  # 被测模块顶部 import playwright，缺则跳过


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


def test_run_batch_reuses_single_browser_across_multiple_diagrams(tmp_path):
    """RSI-033：正常批次跨图共享同一 Headless Chrome 实例，全程只 launch 1 次、close 1 次。"""
    import record_archify_all as raa

    chromium, browser = _chromium()
    browser.is_connected.return_value = True
    seen_browsers = []

    def fake_record(b, html, sidecar, **kwargs):
        seen_browsers.append(b)
        return {"slug": kwargs.get("slug") or html.stem}

    tasks = [
        {
            "slug": f"d{i}",
            "html": tmp_path / f"d{i}.html",
            "sidecar": tmp_path / f"d{i}.json",
            "out_dir": tmp_path,
        }
        for i in (1, 2, 3)
    ]
    done, failed = raa.run_batch_reusing_browser(chromium, tasks, record_fn=fake_record)
    assert done == ["d1", "d2", "d3"]
    assert failed == []
    chromium.launch.assert_called_once_with(
        channel="chrome",
        headless=True,
        args=list(ra.BROWSER_LAUNCH_ARGS),
    )
    assert seen_browsers == [browser, browser, browser]
    browser.close.assert_called_once()


def test_run_batch_restarts_browser_after_diagram_failure(tmp_path, capsys):
    """RSI-033：单图抛 SystemExit/Exception 时立即关闭旧 browser、污染既有产物 mtime 防下次静默跳过，并在下张图重拉新实例。"""
    import json
    import time

    import record_archify_all as raa

    chromium = MagicMock()
    b1, b2 = MagicMock(), MagicMock()
    b1.is_connected.return_value = True
    b2.is_connected.return_value = True
    chromium.launch.side_effect = [b1, b2]
    seen_browsers = []

    # 预先给 d2 造一份旧产物 + 新于产物的 sidecar（模拟 --force 首章早崩前的干净旧现场）
    old_mp4 = tmp_path / "d2--c1.mp4"
    old_png = tmp_path / "d2--c1-end.png"
    old_mp4.write_bytes(b"old")
    old_png.write_bytes(b"old")
    d2_views = tmp_path / "d2.views.json"
    d2_views.write_text(json.dumps([{"id": "c1"}]), encoding="utf-8")
    d2_sidecar = tmp_path / "d2.json"
    time.sleep(0.02)
    d2_sidecar.write_text(
        json.dumps(
            {
                "slug": "d2",
                "type": "lifecycle",
                "chapters": [
                    {"id": "c1", "file": old_mp4.name, "end_still": old_png.name}
                ],
            }
        ),
        encoding="utf-8",
    )
    assert raa.stale_reason(d2_sidecar, d2_views, [old_mp4, old_png]) == ""

    def fake_record(b, html, sidecar, **kwargs):
        seen_browsers.append(b)
        if html.stem == "d2":
            raise SystemExit("FAIL: 模拟单图 CDP 泵超时")
        return {"slug": html.stem}

    tasks = [
        {
            "slug": "d0",
            "skip": True,
            "progress_line": "[1/4] 跳过 d0",
        },
        {
            "slug": "d1",
            "html": tmp_path / "d1.html",
            "sidecar": tmp_path / "d1.json",
            "out_dir": tmp_path,
            "progress_line": "[2/4] 录制 d1",
        },
        {
            "slug": "d2",
            "html": tmp_path / "d2.html",
            "sidecar": d2_sidecar,
            "out_dir": tmp_path,
            "progress_line": "[3/4] 录制 d2",
        },
        {
            "slug": "d3",
            "html": tmp_path / "d3.html",
            "sidecar": tmp_path / "d3.json",
            "out_dir": tmp_path,
            "progress_line": "[4/4] 录制 d3",
        },
    ]
    done, failed = raa.run_batch_reusing_browser(chromium, tasks, record_fn=fake_record)
    assert done == ["d1", "d3"]
    assert failed == ["d2"]
    assert chromium.launch.call_count == 2
    assert seen_browsers == [b1, b1, b2]
    b1.close.assert_called_once()
    b2.close.assert_called_once()
    # 验证 [1/4]..[4/4] 严格按序输出，且 d2 失败后 sidecar 的 type 保住但产物被标记为新于 sidecar
    out_lines = [
        ln for ln in capsys.readouterr().out.splitlines() if ln.startswith("[")
    ]
    assert out_lines == [
        "[1/4] 跳过 d0",
        "[2/4] 录制 d1",
        "[3/4] 录制 d2",
        "[4/4] 录制 d3",
    ]
    assert raa.prior_type(d2_sidecar) == "lifecycle"
    assert "新于 sidecar" in raa.stale_reason(d2_sidecar, d2_views, [old_mp4, old_png])


def test_run_batch_launch_failure_isolated_per_diagram(tmp_path, capsys):
    """RSI-033 回归：chromium.launch 失败按单图失败隔离——不穿透 for 循环、逐图重试、
    既有产物被 taint、failed 全记录（与 --no-reuse-browser 子进程路径语义对齐）。"""
    import json
    import time

    import record_archify_all as raa

    chromium = MagicMock()
    chromium.launch.side_effect = Exception(
        "Failed to launch chromium channel=chrome（模拟资源紧张/缺 Chrome）"
    )

    # d1 预置「已齐且新鲜」现场（产物旧于 sidecar）：launch 失败后必须被 taint 标脏
    old_mp4 = tmp_path / "d1--c1.mp4"
    old_png = tmp_path / "d1--c1-end.png"
    old_mp4.write_bytes(b"old")
    old_png.write_bytes(b"old")
    d1_views = tmp_path / "d1.views.json"
    d1_views.write_text(json.dumps([{"id": "c1"}]), encoding="utf-8")
    d1_sidecar = tmp_path / "d1.json"
    time.sleep(0.02)
    d1_sidecar.write_text(
        json.dumps(
            {
                "slug": "d1",
                "type": "lifecycle",
                "chapters": [
                    {"id": "c1", "file": old_mp4.name, "end_still": old_png.name}
                ],
            }
        ),
        encoding="utf-8",
    )
    assert raa.stale_reason(d1_sidecar, d1_views, [old_mp4, old_png]) == ""

    record_spy = MagicMock()

    tasks = [
        {
            "slug": "d1",
            "html": tmp_path / "d1.html",
            "sidecar": d1_sidecar,
            "out_dir": tmp_path,
            "progress_line": "[1/2] 录制 d1",
        },
        {
            "slug": "d2",
            "html": tmp_path / "d2.html",
            "sidecar": tmp_path / "d2.json",
            "out_dir": tmp_path,
            "progress_line": "[2/2] 录制 d2",
        },
    ]
    # 不抛异常即通过：launch 失败被单图异常面吃掉
    done, failed = raa.run_batch_reusing_browser(chromium, tasks, record_fn=record_spy)
    assert done == []
    assert failed == ["d1", "d2"]
    assert chromium.launch.call_count == 2  # 每图各自重试，与子进程路径一致
    record_spy.assert_not_called()
    assert raa.prior_type(d1_sidecar) == "lifecycle"  # taint 不动 type
    assert "新于 sidecar" in raa.stale_reason(d1_sidecar, d1_views, [old_mp4, old_png])
    err = capsys.readouterr().err
    assert "启动浏览器失败" in err and "d1" in err and "d2" in err
