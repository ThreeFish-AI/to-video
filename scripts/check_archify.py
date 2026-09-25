"""archify 回放的结构性体检（qa_frames.py 是 frozen 档，故另起本脚本）。

只查**结构**，不查画面语义 —— 画面正确性只能靠 `remotion still` 逐帧目视
（`qa_frames --check` 对图层遮挡与时序错位全盲，见 issue.md ISSUE-167/170/177）。

三项判据：
  1. manifest × views 一致：manifest 里每个章节都能在对应 HTML 的 views 里找到；
  2. **rate 预演**：按 TTS 实测 manifest 算每个 cue 的真实 playbackRate，显式写死
     fit='stretch' 且越界 [0.7, 1.35] 即 FAIL 并给出建议，自动挡越界降档 hold/trim
     并列清单 —— 把编排失衡提前到渲染前最便宜的时刻；
  3. 素材完整：webm / 末帧 PNG 存在且非空、逐章有效采集帧率 ≥ 18。

用法（任意目录）：uv run --no-project $T/scripts/check_archify.py --project $P [--lang zh|en]
阈值 rate_min/rate_max/min_fps 走 pipeline.toml [archify]（config.py SCHEMA 默认值层）。
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config  # noqa: E402 - 同目录模块；阈值默认值层的单一事实源
import langs  # noqa: E402 - 语言后缀/manifest 路径的单一事实源
import timeline  # noqa: E402
from check_archify_coverage import extract_cues  # noqa: E402  —— 单一 cue 提取器


def load_manifest(root: Path) -> dict:
    m = re.search(
        r"export const ARCHIFY = ([\s\S]+?) as const",
        (root / "video/src/archify.manifest.ts").read_text("utf-8"),
    )
    if not m:
        raise SystemExit(
            "FAIL: archify.manifest.ts 解析失败——先跑 "
            "$T/scripts/archify_manifest.py --project $P"
        )
    return json.loads(m.group(1))


def scene_cues(root: Path) -> list[tuple[str, str, str, str | None]]:
    """(slug, chapterId, 锚句 id, 显式 fit)——提取本体已上移为管线级单一事实源
    （check_archify_coverage.extract_cues，含计数/at 形态两道硬断言），此处只做
    投影：双份提取器必然漂移（ISSUE-187 教训 6 同族）。"""
    scenes = root / "video/src/scenes"
    return [(slug, cid, sid, fit) for _f, slug, cid, sid, fit in extract_cues(scenes)]


def emit_stills(root: Path, audio: Path, man: dict, cues: list, lang: str) -> None:
    """打印每个 archify cue 的**边界帧**抽帧命令（K1 入场 / K4 退场）。

    刻意不用 qa_frames --stills-plan：它打的是每镜**中点**，而 archify 对位要看的
    恰恰是边界——「章节换了没有」「字幕跟着换了没有」只在边界帧上可判。
    非主语言追加 --props：不传时旧代 Root 会丢弃语言选择、渲出中文画面（静默错版）。
    """
    items = json.loads(audio.read_text("utf-8"))
    c = timeline.load_constants(root)
    rows = {r["id"]: r for r in timeline.compute(items, c)}
    props = "" if lang == langs.PRIMARY else f' --props \'{{"lang":"{lang}"}}\''
    print("# archify 对位抽帧（工程根 video/ 下执行）")
    for slug, cid, sid, _fit in cues:
        if slug not in man:
            continue  # 未知 slug 已由主流程报 FAIL
        r = rows.get(sid)
        ch = next((x for x in man[slug]["chapters"] if x["id"] == cid), None)
        if r is None or ch is None:
            continue
        k1 = r["fromFrame"] + 3
        k4 = r["fromFrame"] + r["durationInFrames"] - 4
        for tag, fr in (("K1入场", k1), ("K4退场", k4)):
            print(
                f"./node_modules/.bin/remotion still src/index.ts Main "
                f"out/k/{slug}--{cid}-{tag}-{fr}.png --frame={fr} --scale=0.5 "
                f"--log=error{props}   # 期望：{ch['label']} · 首拍 {ch['beatNodes'][0]} / "
                f"末拍 {ch['beatNodes'][-1]} · 字幕={sid}"
            )


def main() -> None:
    ap = argparse.ArgumentParser(description="archify 回放结构门")
    ap.add_argument("--project", default=".", help="视频工程根目录（含 pipeline.toml）")
    ap.add_argument(
        "--lang",
        default=langs.PRIMARY,
        choices=list(langs.LANGS),
        help="语言版本（默认 zh；rate 预演读 audio[/lang]/manifest.json——英文锚句"
        "时长不同，en 渲染前必跑本门）",
    )
    ap.add_argument("--stills", action="store_true", help="只打印边界帧抽帧命令")
    args = ap.parse_args()
    root = Path(args.project).resolve()
    archify = root / "video/public/archify"
    audio = langs.manifest(root, args.lang)
    # 阈值默认值在 config.py SCHEMA（机制常数），toml 只写偏离——与全管线同口径
    cfg, _origin, _fails, _warns = config.load(root, required=False)
    arc = cfg.get("archify", {})
    rate_min = arc.get("rate_min", config.default("archify.rate_min"))
    rate_max = arc.get("rate_max", config.default("archify.rate_max"))
    min_fps = arc.get("min_fps", config.default("archify.min_fps"))
    fails: list[str] = []
    warns: list[str] = []
    man = load_manifest(root)

    # ① manifest × views 一致
    for slug, d in man.items():
        vf = archify / "views" / f"{slug}.json"
        if not vf.is_file():
            fails.append(f"{slug}: 缺 views/{slug}.json")
            continue
        vids = {v["id"] for v in json.loads(vf.read_text("utf-8"))}
        for ch in d["chapters"]:
            if ch["id"] not in vids:
                fails.append(f"{slug}/{ch['id']}: manifest 有此章但 views 里没有")

    # ③ 素材完整
    n_ch = 0
    for slug, d in man.items():
        for ch in d["chapters"]:
            n_ch += 1
            for key in ("file", "endStill"):
                p = archify / ch[key]
                if not p.is_file() or p.stat().st_size == 0:
                    fails.append(f"{slug}/{ch['id']}: 缺素材 {ch[key]}")
        sc = archify / f"{slug}.json"
        if sc.is_file():
            # 逐章有效采集帧率，口径同 record_archify 的 `eff`（capture_fps 优先）：
            # CDP 档产物是补帧合成的 CFR 25fps，顶层 measured_fps 恒≈25，按它判门即失明。
            data = json.loads(sc.read_text("utf-8"))
            fpss = [
                f
                for c in data.get("chapters", [])
                if (f := c.get("capture_fps") or c.get("measured_fps"))
            ] or [f for f in [data.get("measured_fps")] if f]
            if fpss and (fps := min(fpss)) < min_fps:
                warns.append(f"{slug}: 录制帧率 {fps} < {min_fps}，建议重录")

    # ② rate 预演（需 TTS manifest）
    cues = scene_cues(root)
    for slug in sorted({s for s, _, _, _ in cues} - set(man)):
        fails.append(f"{slug}: 场景 cue 引用了 manifest 里不存在的图")

    # ④ 录了但没落镜：manifest 里有图、却没有任何 cue 引用它 —— 2026-09-19 实测
    #    evolution-timeline / autopilot-loop 各 3 章白录，而文档仍写着 14 张进片。
    unused = sorted(set(man) - {slug for slug, _, _, _ in cues})
    for slug in unused:
        warns.append(
            f"{slug}: manifest 有此图但无任何 cue 引用（{len(man[slug]['chapters'])} 章白录）"
            "——接进场景或从 manifest 摘掉"
        )

    if args.stills:
        if not audio.is_file():
            raise SystemExit(
                f"需要 {audio.relative_to(root)}（先跑 tts --lang {args.lang}）"
            )
        emit_stills(root, audio, man, cues, args.lang)
        return
    # 显式写死 stretch 的 cue 由 scene_cues() 抽取——受越界门约束（ISSUE-187 防范 2）
    explicit_stretch = {(s, c, sid) for s, c, sid, fit in cues if fit == "stretch"}
    fitted = {"stretch": 0, "hold": 0, "trim": 0}
    holds: list[str] = []
    if not audio.is_file():
        warns.append(
            f"{audio.relative_to(root)} 未生成——**跳过 rate 预演门**（合成后复跑）"
        )
    else:
        items = json.loads(audio.read_text("utf-8"))
        c = timeline.load_constants(root)
        dur = {r["id"]: r["durationInFrames"] for r in timeline.compute(items, c)}
        fps = c["fps"]
        for slug, cid, sid, _fit in cues:
            if slug not in man:
                continue
            ch = next((x for x in man[slug]["chapters"] if x["id"] == cid), None)
            if ch is None:
                fails.append(f"{slug}/{cid}: 场景引用了 manifest 里不存在的章节")
                continue
            if sid not in dur:
                fails.append(f"{slug}/{cid}: 锚句 {sid} 不在 narration/manifest")
                continue
            rate = ch["storySec"] / (dur[sid] / fps)
            # 与 ArchifyRecap.pickFit 同构：越界会自动降到 hold/trim，不是缺陷。
            # 只有**显式写死 fit='stretch'** 且越界才会在渲染期抛错。
            explicit = (slug, cid, sid) in explicit_stretch
            if rate_min <= rate <= rate_max:
                fitted["stretch"] += 1
            elif explicit:
                want = ch["storySec"] / rate_max, ch["storySec"] / rate_min
                fails.append(
                    f"{slug}/{cid} @ {sid}: 显式 fit='stretch' 但 playbackRate "
                    f"{rate:.2f} 越界 [{rate_min}, {rate_max}]；该句需落在 "
                    f"{want[0]:.1f}–{want[1]:.1f}s，或去掉显式 fit 让它自动降档"
                )
            elif rate < rate_min:
                fitted["hold"] += 1
                holds.append(
                    f"{slug}/{cid}@{sid} 章 {ch['storySec']:.1f}s < 句 "
                    f"{dur[sid] / fps:.1f}s → 播完冻结尾帧"
                )
            else:
                fitted["trim"] += 1
                holds.append(
                    f"{slug}/{cid}@{sid} 章 {ch['storySec']:.1f}s > 句 "
                    f"{dur[sid] / fps:.1f}s → 原速播、父级裁切"
                )
        print(
            f"  rate 预演：{len(cues)} 个 cue —— "
            f"变速铺满 {fitted['stretch']} · 冻结补足 {fitted['hold']} · 裁切 {fitted['trim']}"
        )
        for h in holds:
            print(f"    · {h}")

    print(f">> archify 体检 · {len(man)} 图 / {n_ch} 章 / {len(cues)} cue")
    for w in warns:
        print(f"  WARN {w}")
    for f in fails:
        print(f"  FAIL {f}")
    print(f">> FAIL {len(fails)} · WARN {len(warns)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
