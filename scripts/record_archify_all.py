"""archify 工程图批量重录驱动（遍历分集 views/ 清单，逐图调 record_archify.py）。

用法（任意目录，$T/$P 锚定见 references/PIPELINE.md）：
  uv run --with playwright python $T/scripts/record_archify_all.py --project $P
  uv run --with playwright python $T/scripts/record_archify_all.py --project $P --dry-run
  uv run --with playwright python $T/scripts/record_archify_all.py --project $P --only agent-identity --force

为什么要有这个驱动：mp4 / *-end.png 是派生产物（根 .gitignore 明写「HTML 为 SSOT，
sidecar json 入库」），所以**换一个 worktree 就要全量重录一次**——这是常规操作而非
一次性动作。此前唯一文档化的方式是一条含 <slug> 占位符的单图模板，重录全集要手工
替换 67 次；录制因此成了这条链路上唯一的手工步骤（下游测 lead 与生成 manifest 都自带
遍历）。占位符没替换正是 2026-09-21 那次裸 traceback 的来源。

职责边界（正交分解）：record_archify.py = 机制（怎么录一张图），本驱动 = 策略
（录哪些、跳过谁、失败了怎么报）。不把 --all 塞进录制器，两者各自单一职责。

为什么串行：录制走 channel="chrome" 起真实浏览器（headless），多实例互抢 CPU/GPU
资源会掉帧（headless 无前台焦点，机理见 references/PIPELINE.md §十）；而 --min-fps
只告警不失败，掉帧会**静默**污染产物。本机另有过热导致时序漂移的先例。
宁可慢，不要一批悄悄降质的素材。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import config
from playwright.sync_api import sync_playwright
from record_archify import (
    BROWSER_LAUNCH_ARGS,
    DIAGRAM_TYPES,
    find_remotion,
    read_views,
    record_one_diagram,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402 - WORKSPACE/PROJECT 惰性解析，import 期不触发 workspace_root()

RECORDER = Path(__file__).resolve().parent / "record_archify.py"


def _close_browser_quietly(browser) -> None:
    """异常/重启路径关 browser：吞掉已断连/已关异常，不掩盖原始报错。"""
    if browser is None:
        return
    try:
        browser.close()
    except Exception:
        pass


def _taint_on_failure(sidecar: Path, out_dir: Path) -> None:
    """录制失败时污染首个既有产物 mtime，使下次不带 --force 重跑被 stale_reason 捕获。

    不删 sidecar.json：删除会抹去人工审定的 type（prior_type 无法继承）与 fps_baseline；
    仅刷新一个既有产物的 mtime 使其新于 sidecar，既保住元数据又防下次被静默当作已齐跳过。
    """
    if not sidecar.is_file():
        return
    for p in expected_products(sidecar, out_dir):
        if p.is_file():
            try:
                os.utime(p, None)
                break
            except OSError:
                pass


def run_batch_reusing_browser(
    chromium,
    tasks: list[dict],
    record_fn=record_one_diagram,
) -> tuple[list[str], list[str]]:
    """单 Headless Chrome 跨图复用 + 单图异常隔离重启 supervisor（RSI-033）。

    进程内共享单个 headless browser、每章独立 BrowserContext，省去逐图冷启动浏览器进程树
    的开销；单图抛 Exception / SystemExit 或连接断开时立即关闭旧实例并在下张图按需重拉，
    防止半死浏览器状态跨图传染。
    """
    done: list[str] = []
    failed: list[str] = []
    browser = None
    try:
        for task in tasks:
            if line := task.get("progress_line"):
                print(line)
            if task.get("skip"):
                continue
            slug = task["slug"]
            if browser is not None and hasattr(browser, "is_connected"):
                try:
                    if not browser.is_connected():
                        _close_browser_quietly(browser)
                        browser = None
                except Exception:
                    _close_browser_quietly(browser)
                    browser = None
            if browser is None:
                browser = chromium.launch(
                    channel="chrome",
                    headless=True,
                    args=list(BROWSER_LAUNCH_ARGS),
                )
            try:
                record_fn(
                    browser,
                    task["html"],
                    task["sidecar"],
                    out_dir=task["out_dir"],
                    views_file=task.get("views_file"),
                    slug=slug if task.get("overridden") else None,
                    diagram_type=task.get("diagram_type") or None,
                )
                done.append(slug)
            except (Exception, SystemExit) as exc:
                failed.append(slug)
                _taint_on_failure(task["sidecar"], task["out_dir"])
                print(
                    f"  ✗ {slug} 失败（{exc}）——隔离重启 browser 后继续下一图",
                    file=sys.stderr,
                )
                _close_browser_quietly(browser)
                browser = None
    finally:
        _close_browser_quietly(browser)
    return done, failed


def prior_type(sidecar: Path) -> str:
    """既有 sidecar 里人工审定的图型——重录必须**保住**它。

    录制器对 type 的兜底是指纹嗅探（_sniff_diagram_type），而本集 67 张里有 14 张
    嗅不出（7 张 lifecycle + 7 张无框平铺 architecture）。不透传就会让 lifecycle
    整型消失、图型多样性 5 → 4；而本集 min_diagram_types 恰好是 4，**门照样绿**。
    绿着的门盖住退化的片子，是这条链路上最不该留的缺口。
    """
    if not sidecar.is_file():
        return ""
    try:
        return json.loads(sidecar.read_text(encoding="utf-8")).get("type") or ""
    except (json.JSONDecodeError, OSError):
        return ""


def diagram_types(archify_dir: Path, slugs: list[str]) -> set[str]:
    """→ 这批 slug 当前在库的图型集合（空 type 不计）。"""
    return {t for s in slugs if (t := prior_type(archify_dir / f"{s}.json"))}


def chapter_fps(sidecar: Path) -> dict[str, float]:
    """→ {章 id: 有效采集帧率}；取值与 record_archify 的 `eff` 同构：capture_fps 优先。

    CDP 档（chapter 默认）的产物是槽位补帧合成的 CFR 25fps，measured_fps 恒≈25，
    只有 capture_fps 反映真实采集帧率；playwright 档无 capture_fps，回退 measured_fps。
    """
    try:
        chapters = json.loads(sidecar.read_text(encoding="utf-8")).get("chapters", [])
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        c["id"]: fps
        for c in chapters
        if c.get("id") and (fps := c.get("capture_fps") or c.get("measured_fps"))
    }


def fps_degraded(
    base: dict[str, float], now: dict[str, float], ratio: float = 0.9
) -> list[str]:
    """→ 相对基线掉帧超过 (1-ratio) 的章：`<章> 基线→现值fps`。"""
    return [
        f"{cid} {base[cid]:.1f}→{fps:.1f}fps"
        for cid, fps in now.items()
        if base.get(cid) and fps < base[cid] * ratio
    ]


def expected_products(sidecar: Path, out_dir: Path) -> list[Path]:
    """→ 该图应当存在的产物（视频 + 末帧 PNG）。

    以入库 sidecar 的 chapters[] 为准而非重新推导命名：sidecar 是「上次录成什么样」
    的事实记录，例外图（产物名 ≠ 文件名派生 slug）也只有它说得准。
    读不出就返回空列表 —— 空列表在调用方被当作「无法判定，必须重录」。
    """
    if not sidecar.is_file():
        return []
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    out: list[Path] = []
    for ch in data.get("chapters", []):
        for key in ("file", "end_still"):
            if name := ch.get(key):
                out.append(out_dir / name)
    return out


def stale_reason(sidecar: Path, views: Path, products: list[Path]) -> str:
    """→ 非空理由 = 产物虽齐但不可信，须重录；空串 = 可跳过。

    存在性判据的两道盲区，都在此补上：
      - **mtime 一致性**：录制器逐章写产物、全部录完才写 sidecar，故「产物新于
        sidecar」只能来自一次被打断/失败的重录——留下的新旧章混合素材里，sidecar
        的 lead_sec 仅对旧章成立，静默混剪即废片；
      - **章节集对齐**：sidecar 只记「上次录成什么样」，views JSON 才是「现在要
        什么」；views 增删章后旧清单仍判已齐，新章永远录不上（要等 tsc/渲染期
        才炸，归因极难）。只比集合不比顺序——章序不影响按 id 取材。
    """
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        sc_m = sidecar.stat().st_mtime
    except (json.JSONDecodeError, OSError):
        return ""  # sidecar 读不出：expected_products 已空，调用方判「必须重录」
    if any(p.is_file() and p.stat().st_mtime > sc_m for p in products):
        return "产物新于 sidecar（上次重录未完成，新旧章混合态）"
    try:
        want = {v.get("id") for v in json.loads(views.read_text(encoding="utf-8"))}
    except (json.JSONDecodeError, OSError):
        return ""  # views 读不出：录制器的 --views 注入同样会失败并点名，不重复执法
    have = {c.get("id") for c in data.get("chapters", [])}
    if want != have:
        diff = "、".join(sorted(str(x) for x in want ^ have))
        return f"views 与 sidecar 章节集不一致（{diff}）"
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="archify 工程图批量重录驱动")
    ap.add_argument("--project", required=True, help="分集工程根（如 $P）")
    ap.add_argument("--only", help="逗号分隔的 slug 子集；缺省 = views/ 下全部")
    ap.add_argument(
        "--force", action="store_true", help="产物已齐也重录（缺省跳过已齐的图）"
    )
    ap.add_argument("--dry-run", action="store_true", help="只做映射与预检，不起浏览器")
    ap.add_argument(
        "--reuse-browser",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="进程内跨图复用单个 Headless Chrome 实例（默认开启；传 --no-reuse-browser 退回逐图独立子进程）",
    )
    a = ap.parse_args()

    root = Path(a.project).resolve()
    archify_dir = root / "video" / "public" / "archify"
    views_dir = archify_dir / "views"
    if not views_dir.is_dir():
        sys.exit(
            f"FAIL: views 目录不存在：{views_dir}\n"
            f"      --project 应指向分集工程根（含 video/public/archify/views/）。"
        )

    cfg, _origin, cfg_fails, cfg_warns = config.load(
        root, required=False, scope={"archify"}
    )
    for w in cfg_warns:
        print(f"  WARN {w}", file=sys.stderr)
    if cfg_fails:
        sys.exit("FAIL: pipeline.toml 配置有误：\n      " + "\n      ".join(cfg_fails))
    arch = cfg.get("archify", {})
    html_dir = paths.PROJECT / arch.get("html_dir", config.default("archify.html_dir"))
    pattern = arch.get("html_pattern", config.default("archify.html_pattern"))
    overrides = arch.get("html_overrides", config.default("archify.html_overrides"))

    slugs = sorted(p.stem for p in views_dir.glob("*.json"))
    if not slugs:
        sys.exit(f"FAIL: {views_dir} 下没有 views JSON——无图可录。")
    if a.only:
        want = [s.strip() for s in a.only.split(",") if s.strip()]
        if unknown := [s for s in want if s not in slugs]:
            sys.exit(
                f"FAIL: --only 里有 views/ 下不存在的图名：{', '.join(unknown)}\n"
                f"      清单见 {views_dir}/ 下的文件名。"
            )
        slugs = want

    # 映射 + 源图存在性 + 录制前置预检：全部先验完再开录，免得跑到第 40 分钟才发现
    # 某张缺源图。dry-run 与真录共用这一段——预检只在 dry-run 跑等于给漏跑 dry-run
    # 的批次留一道敞开的门（上游 ISSUE-201：三重静默缺陷全部拖到录制中段才暴露）。
    plan: list[tuple[str, Path, bool]] = []
    missing: list[str] = []
    no_views: list[str] = []
    bad_types: list[str] = []
    for slug in slugs:
        overridden = slug in overrides
        name = overrides[slug] if overridden else pattern.format(slug=slug)
        html = html_dir / name
        if not html.is_file():
            missing.append(f"{slug} → {html}")
            continue
        # ① 源图须含非空 guided-views 数据（与录制器 materialize/read_views 同一
        # 提取器，预检与录制对「什么算空」永不各说各话）。
        if not read_views(html):
            no_views.append(f"{slug} → {html}")
            continue
        # ② 既有 sidecar 的审定图型须在录制器词表内——越表 type 重录时被 argparse
        # 拒绝（退出码 2），这里提前拦并给出映射指路。
        if (t := prior_type(archify_dir / f"{slug}.json")) and t not in DIAGRAM_TYPES:
            bad_types.append(f"{slug}（type={t}）")
            continue
        plan.append((slug, html, overridden))
    if missing:
        sys.exit(
            "FAIL: 以下图找不到源 HTML（约定 = html_pattern，例外走 html_overrides）：\n      "
            + "\n      ".join(missing)
        )
    if no_views:
        sys.exit(
            "FAIL: 以下源图缺非空 guided-views 数据（archify-guided-views-data 容器"
            "缺位或为空）：\n      "
            + "\n      ".join(no_views)
            + "\n      产物可能出自删除该模块的 archify 版本（全局 CLI 3.0.0 起无"
            " guided-views）——须用仍含该模块的版本重新出图并落 html_dir。"
        )
    if bad_types:
        sys.exit(
            "FAIL: 以下 sidecar type 越出录制器图型词表（"
            + "/".join(DIAGRAM_TYPES)
            + "）：\n      "
            + "\n      ".join(bad_types)
            + "\n      state 型（archify 出图词汇）在本管线映射为 lifecycle——在"
            " video/public/archify/<slug>.json 顶层改写 type；词表以录制器 --type"
            " 为准（references/06 archify 资产标注规范）。"
        )

    if find_remotion() is None:
        # dry-run 的用途正是「装依赖之前先把映射核对干净」，故此处降为告警。
        msg = (
            "未找到任何集的 video/node_modules/.bin/remotion——先 pnpm install"
            "（cdp 采集用它的内置 ffmpeg 编码）"
        )
        if a.dry_run:
            print(f"  WARN {msg}", file=sys.stderr)
        else:
            sys.exit(f"FAIL: {msg}\n      此处预检，免得录完才失败。")

    done, skipped, failed = [], [], []
    batch_tasks: list[dict] = []
    types_before = diagram_types(archify_dir, [s for s, _h, _o in plan])
    # 帧率基线（录前快照 = 检出版本的 committed sidecar）：录后逐章比对，
    # 退化超 10% 点名补录——screencast 帧率受前台聚焦/负载影响，静默退化会让
    # trimBefore 掐点整体漂移，而既有 --min-fps 18 只拦「绝对低」不拦「相对掉」。
    fps_baseline = {s: chapter_fps(archify_dir / f"{s}.json") for s, _h, _o in plan}
    mode_desc = (
        "串行·跨图复用单 Headless Chrome" if a.reuse_browser else "串行·逐图独立进程"
    )
    print(f"计划重录 {len(plan)} 图（{mode_desc}）；源图目录 {html_dir}")
    for i, (slug, html, overridden) in enumerate(plan, 1):
        sidecar = archify_dir / f"{slug}.json"
        views = views_dir / f"{slug}.json"
        products = expected_products(sidecar, archify_dir)
        # 「已齐」= 文件齐**且**不属于混合/陈旧态；不可信的产物要点名重录，
        # 静默当作已齐等于把两代素材混进成片（两道判据见 stale_reason）。
        gap = stale_reason(sidecar, views, products) if products else ""
        if (
            not a.force
            and products
            and not gap
            and all(p.is_file() and p.stat().st_size > 0 for p in products)
        ):
            skipped.append(slug)
            skip_line = f"[{i}/{len(plan)}] 跳过 {slug}（{len(products)} 个产物已齐）"
            if a.reuse_browser and not a.dry_run:
                batch_tasks.append(
                    {"slug": slug, "skip": True, "progress_line": skip_line}
                )
            else:
                print(skip_line)
            continue

        cmd = [
            sys.executable,
            str(RECORDER),
            str(html),
            "/dev/null",
            str(sidecar),
            "--mode",
            "chapter",
            "--all-chapters",
            "--out-dir",
            str(archify_dir),
        ]
        if views.is_file():
            cmd += ["--views", str(views)]
        # 例外图的文件名派生 slug 与产物名对不上，必须显式钉住，否则产出的 mp4
        # 叫不上 manifest 期望的名字，渲染期才 throw。
        if overridden:
            cmd += ["--slug", slug]
        # 审定图型必须活过重录：嗅探对 14/67 张无效，不透传即静默丢型。
        saved_type = prior_type(sidecar)
        if saved_type:
            cmd += ["--type", saved_type]

        label = f"{slug}（例外源图 {html.name}）" if overridden else slug
        why = f"；{gap}" if gap else ""
        progress_line = f"[{i}/{len(plan)}] 录制 {label}{why}"
        if a.dry_run:
            print(progress_line)
            done.append(slug)
            continue
        if a.reuse_browser:
            batch_tasks.append(
                {
                    "slug": slug,
                    "skip": False,
                    "html": html,
                    "sidecar": sidecar,
                    "out_dir": archify_dir,
                    "views_file": views if views.is_file() else None,
                    "overridden": overridden,
                    "diagram_type": saved_type,
                    "progress_line": progress_line,
                }
            )
            continue
        # 退回模式（--no-reuse-browser）：逐图独立进程。
        print(progress_line)
        r = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=False)
        if r.returncode == 0:
            done.append(slug)
        else:
            failed.append(slug)
            _taint_on_failure(sidecar, archify_dir)
            print(f"  ✗ {slug} 退出码 {r.returncode}", file=sys.stderr)

    if batch_tasks:
        if any(not t.get("skip") for t in batch_tasks):
            with sync_playwright() as p:
                b_done, b_failed = run_batch_reusing_browser(p.chromium, batch_tasks)
                done.extend(b_done)
                failed.extend(b_failed)
        else:
            for t in batch_tasks:
                if line := t.get("progress_line"):
                    print(line)

    verb = "预演" if a.dry_run else "录成"
    print(f"\n{verb} {len(done)} · 跳过 {len(skipped)} · 失败 {len(failed)}")
    # 跳过项必须点名：无声截断等于谎报覆盖。
    if skipped:
        print(f"  跳过（产物已齐，--force 可强制重录）：{', '.join(skipped)}")
    if failed:
        print(f"  失败：{', '.join(failed)}")
        print(
            "  失败图的浏览器已由录制器 finally 兜底关闭；若曾 kill -9 / 裸 kill "
            "强杀驱动（SIGKILL/SIGTERM 均绕过 finally），运行 "
            "`uv run --no-project $T/scripts/pipeline.py --project $P doctor --clean-browsers` "
            "一键回收孤儿进程（详见 references/PIPELINE.md §十）。"
        )

    lost: set[str] = set()
    if not a.dry_run:
        types_after = diagram_types(archify_dir, [s for s, _h, _o in plan])
        if lost := types_before - types_after:
            print(
                f"  FAIL 图型在重录中丢失：{sorted(lost)}"
                f"——覆盖门的 min_diagram_types 可能恰好放行这次退化，勿忽略"
            )
        # 帧率相对退化点名（对录前基线，口径见 chapter_fps）：绝对门 --min-fps 18
        # 只拦「低」，拦不住「从 25 掉到 19」这类相对退化。
        degraded = [
            f"{slug}/{d}"
            for slug in done
            for d in fps_degraded(
                fps_baseline.get(slug, {}), chapter_fps(archify_dir / f"{slug}.json")
            )
        ]
        if degraded:
            print(
                "  WARN 帧率相对退化超 10%（对录前基线，建议逐章补录）：\n    "
                + "\n    ".join(degraded)
            )
    if not a.dry_run and done:
        print(
            "  下一步：$T/scripts/archify_lead.py --project $P 测定 lead_sec"
            "（录制器恒写 0.0，漏跑则每章片头把场记板白闪播进成片）"
            "→ $T/scripts/archify_manifest.py --project $P"
        )
    if failed or lost:
        sys.exit(1)


if __name__ == "__main__":
    main()
