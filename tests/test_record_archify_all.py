"""record_archify_all 的跳过资格判据 + 录制前置预检（RSI-018）。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("playwright")  # record_archify 模块级依赖，缺则跳过整个文件

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import record_archify_all as raa  # noqa: E402

RAA_SCRIPT = Path(raa.__file__)


def _scene(
    tmp_path: Path,
    views_ids: list[str],
    sidecar_ids: list[str],
    newer_product: bool = False,
) -> tuple[Path, Path, list[Path]]:
    """搭一个 (sidecar, views, products) 现场，落盘顺序复刻真实录制（sidecar 恒最后）。"""
    d = tmp_path / "a"
    d.mkdir()
    products: list[Path] = []
    for cid in sidecar_ids:
        for name in (f"a--{cid}.mp4", f"a--{cid}-end.png"):
            (d / name).write_bytes(b"x")
            products.append(d / name)
    sidecar = d / "a.json"
    sidecar.write_text(
        json.dumps(
            {
                "slug": "a",
                "chapters": [
                    {"id": c, "file": f"a--{c}.mp4", "end_still": f"a--{c}-end.png"}
                    for c in sidecar_ids
                ],
            }
        ),
        encoding="utf-8",
    )
    views = d / "a.views.json"
    views.write_text(json.dumps([{"id": c} for c in views_ids]), encoding="utf-8")
    if newer_product:
        # 半程重录：第 1 章已被新一轮覆盖（mtime 新于 sidecar），其余仍是旧素材
        products[0].write_bytes(b"new-session")
    return sidecar, views, products


def test_clean_products_are_trustworthy(tmp_path):
    sidecar, views, products = _scene(tmp_path, ["c1", "c2"], ["c1", "c2"])
    assert raa.stale_reason(sidecar, views, products) == ""


def test_product_newer_than_sidecar_means_interrupted_rerecord(tmp_path):
    sidecar, views, products = _scene(
        tmp_path, ["c1", "c2"], ["c1", "c2"], newer_product=True
    )
    assert "新于 sidecar" in raa.stale_reason(sidecar, views, products)


def test_views_chapter_drift_beats_stale_sidecar_list(tmp_path):
    # 旧清单的产物全在（存在性判据会误判已齐），但 views 已换章：c2 → c3
    sidecar, views, products = _scene(tmp_path, ["c1", "c3"], ["c1", "c2"])
    reason = raa.stale_reason(sidecar, views, products)
    assert "章节集不一致" in reason and "c2" in reason and "c3" in reason


def test_unreadable_sidecar_defers_to_expected_products(tmp_path):
    sidecar, views, products = _scene(tmp_path, ["c1"], ["c1"])
    sidecar.write_text("{broken", encoding="utf-8")
    assert raa.stale_reason(sidecar, views, products) == ""


def _fps_sidecar(tmp_path: Path, name: str, chapters: list[dict]) -> Path:
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps({"slug": "a", "chapters": chapters}), encoding="utf-8")
    return p


def test_fps_baseline_prefers_capture_fps_over_cfr_measured(tmp_path):
    """CDP 档产物是补帧合成的 CFR 25fps：measured_fps 恒 25，退化只在 capture_fps 上可见。

    按 measured_fps 比对时本门在默认采集档下永不触发（25→25）；口径须与录制器
    `eff = capture_fps or measured_fps` 同构。
    """
    before = _fps_sidecar(
        tmp_path,
        "before",
        [
            {"id": "c1", "measured_fps": 25.0, "capture_fps": 25.0},
            {"id": "c2", "measured_fps": 25.0, "capture_fps": 24.0},
        ],
    )
    after = _fps_sidecar(
        tmp_path,
        "after",
        [
            {"id": "c1", "measured_fps": 25.0, "capture_fps": 19.0},
            {"id": "c2", "measured_fps": 25.0, "capture_fps": 23.5},
        ],
    )
    assert raa.chapter_fps(before) == {"c1": 25.0, "c2": 24.0}
    assert raa.fps_degraded(raa.chapter_fps(before), raa.chapter_fps(after)) == [
        "c1 25.0→19.0fps"
    ]


def test_fps_baseline_falls_back_to_measured_and_tolerates_missing(tmp_path):
    """playwright 档无 capture_fps → 回退 measured_fps；sidecar 缺失/损坏 → 空基线不报。"""
    legacy = _fps_sidecar(tmp_path, "legacy", [{"id": "c1", "measured_fps": 22.0}])
    assert raa.chapter_fps(legacy) == {"c1": 22.0}
    assert raa.chapter_fps(tmp_path / "missing.json") == {}
    broken = tmp_path / "broken.json"
    broken.write_text("{broken", encoding="utf-8")
    assert raa.chapter_fps(broken) == {}
    assert raa.fps_degraded({}, {"c1": 10.0}) == []


# ── 录制前置预检（RSI-018）──────────────────────────────────────────────────
# 病理（上游 ISSUE-201，五集系列重制）：全局 archify CLI 3.0.0 删除 guided-views
# 模块后，建图产物天然无嵌入——录制/预检双双放行，缺陷拖到录制中段或覆盖门才红；
# sidecar 手工回填 type=state（archify 出图词汇含 state）则被录制器 argparse 拒绝
# （退出码 2）。本组用例钉住升级后的门语义：缺/空 guided-views 与越表 type 在
# **起浏览器之前** FAIL（dry-run 与真录共用同一段预检），健康现场照常过。

_VIEWS_JSON = [{"id": "c1", "label": "章节一", "focus": []}]
_GOOD_HTML = (
    '<html><body><script id="archify-guided-views-data" type="application/json">'
    + json.dumps(_VIEWS_JSON)
    + "</script><svg/></body></html>"
)
#: archify 3.0.0 产物形态：模块删除后连容器都没有。
_NO_CONTAINER_HTML = "<html><body><svg/></body></html>"
#: 容器在但为空（json.loads 得 []）。
_EMPTY_CONTAINER_HTML = (
    '<html><body><script id="archify-guided-views-data" type="application/json">'
    "[]</script><svg/></body></html>"
)


def _site(tmp_path: Path, html: str, sidecar: dict | None = None) -> Path:
    """搭最小假现场：工作区哨兵 + archify-html/ 源图 + 分集 views 清单。

    html_dir 是 PROJECT 根相对（无 .git 祖先时 PROJECT = 工作区自身），故源图
    落在工作区根下的 archify-html/（config 默认值路径）。
    """
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / ".to-video-root").write_text("", encoding="utf-8")
    (ws / "archify-html").mkdir()
    (ws / "archify-html" / "a.html").write_text(html, encoding="utf-8")
    arch = ws / "ep" / "video" / "public" / "archify"
    (arch / "views").mkdir(parents=True)
    (arch / "views" / "a.json").write_text(json.dumps(_VIEWS_JSON), encoding="utf-8")
    if sidecar is not None:
        (arch / "a.json").write_text(json.dumps(sidecar), encoding="utf-8")
    return ws


def _run(ws: Path, *extra: str) -> tuple[int, str]:
    """子进程跑驱动（CLI 级门语义——纯函数单测拦不住接线错位）。"""
    r = subprocess.run(
        [sys.executable, str(RAA_SCRIPT), "--project", str(ws / "ep"), *extra],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "TO_VIDEO_WORKSPACE": str(ws)},
    )
    return r.returncode, r.stdout + r.stderr


def test_preflight_fails_on_html_without_guided_views(tmp_path):
    """①的病理正控：archify 3.0.0 形态（无容器）→ 预检 FAIL、exit 1。"""
    ws = _site(tmp_path, _NO_CONTAINER_HTML)
    rc, out = _run(ws, "--dry-run")
    assert rc == 1, out
    assert "guided-views" in out and "a.html" in out
    assert "3.0.0" in out  # 版本成因提示在场，指路而非只报错


def test_preflight_fails_on_empty_guided_views_container(tmp_path):
    """①的另一形态：容器在但内容为空 [] → 同一道门 FAIL（缺/空同罪）。"""
    ws = _site(tmp_path, _EMPTY_CONTAINER_HTML)
    rc, out = _run(ws, "--dry-run")
    assert rc == 1, out
    assert "guided-views" in out


def test_preflight_fails_on_out_of_vocab_sidecar_type(tmp_path):
    """④的病理正控：sidecar type=state → 预检 FAIL，报词表与 state→lifecycle 映射。"""
    ws = _site(tmp_path, _GOOD_HTML, sidecar={"slug": "a", "type": "state"})
    rc, out = _run(ws, "--dry-run")
    assert rc == 1, out
    assert "type=state" in out and "lifecycle" in out
    assert "/".join(raa.DIAGRAM_TYPES) in out


def test_preflight_gates_real_runs_too_not_only_dry_run(tmp_path):
    """门须拦真录：不带 --dry-run 的运行同样在起浏览器之前被越表 type 拦下
    （而非拖到录制中段 argparse 退出码 2）——预检只在 dry-run 跑等于留后门。"""
    ws = _site(tmp_path, _GOOD_HTML, sidecar={"slug": "a", "type": "state"})
    rc, out = _run(ws)
    assert rc == 1, out
    assert "越出录制器图型词表" in out and "type=state" in out


def test_preflight_passes_healthy_site(tmp_path):
    """健康现场 → 过（门拦得住且放得过）：非空 guided-views + 词表内 type 照常预演。"""
    ws = _site(tmp_path, _GOOD_HTML, sidecar={"slug": "a", "type": "lifecycle"})
    rc, out = _run(ws, "--dry-run")
    assert rc == 0, out
    assert "预演 1" in out
