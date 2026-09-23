#!/usr/bin/env python3
"""测定每段 archify 章节 webm 的「视频钟零点」并回写 sidecar 的 lead_sec。

动机：录制器在播放前插一帧全屏白闪（场记板）。webm 的前段还含页面加载与
入场落定，**不是**故事起点；用 Python 墙钟去推视频钟会带 ±0.3s 误差（≈9 帧）。
本脚本直接在像素上找白闪的**末帧**，其后一帧即故事第一拍 —— 把估算换成测量。

remotion 内置 ffmpeg 编译时 `--disable-filters`（signalstats/movie 均不可用），
故走「抽帧 + PIL 测亮度」而非 lavfi 滤镜链。

用法（任意目录）：
  uv run --no-project --with pillow $T/pipeline/scripts/archify_lead.py \
      --project $P [--window 6.0]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

WHITE = 200.0  # 白闪判据：32x18 灰度均值（页面底色 #0E1116 ≈ 14）


def probe_lead(
    ffmpeg: Path, cwd: Path, webm: Path, window: float, fps: int = 25
) -> float | None:
    """返回白闪末帧之后的时间戳（秒）；找不到白闪返回 None。"""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td)
        r = subprocess.run(
            [
                str(ffmpeg),
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(webm.resolve()),  # remotion 内置 ffmpeg 对相对路径不稳，一律绝对
                "-t",
                str(window),
                "-vf",
                "scale=32:18",
                "-f",
                "image2",
                str(out / "f%04d.png"),
            ],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(cwd),
            check=False,
        )
        frames = sorted(out.glob("f*.png"))
        if not frames:
            print(f"    ⚠️ 抽帧失败：{r.stderr[:160]}")
            return None
        last_white = -1
        for i, f in enumerate(frames):
            px = list(Image.open(f).convert("L").getdata())
            if sum(px) / len(px) >= WHITE:
                last_white = i
        if last_white < 0:
            return None
        return round((last_white + 1) / fps, 3)


def run(root: Path, window: float) -> None:
    archify = root / "video" / "public" / "archify"
    ffmpeg = root / "video" / "node_modules" / ".bin" / "remotion"
    if not ffmpeg.is_file():
        raise SystemExit("缺 video/node_modules —— 先 pnpm install")

    total = fixed = missing = 0
    for sc in sorted(archify.glob("*.json")):
        d = json.loads(sc.read_text(encoding="utf-8"))
        if not isinstance(d, dict) or not d.get("chapters"):
            continue
        print(f"{sc.stem}")
        for ch in d["chapters"]:
            total += 1
            webm = archify / ch["file"]
            if not webm.is_file():
                print(f"  {ch['id']:<22} ✗ 缺 webm")
                missing += 1
                continue
            # fps 取该章实测值：screencast 是 VFR，抽帧按源片实际帧率逐帧展开，
            # 写死 25 一旦录制掉帧就会把所有 lead_sec 整体缩放（--min-fps 18 拦不住）
            lead = probe_lead(
                ffmpeg,
                root / "video",
                webm,
                window,
                int(round(ch.get("measured_fps") or 25)),
            )
            if lead is None:
                print(
                    f"  {ch['id']:<22} ⚠️ 未找到场记板白闪（保留 lead_sec={ch['lead_sec']}）"
                )
                missing += 1
                continue
            ch["lead_sec"] = lead
            fixed += 1
            print(f"  {ch['id']:<22} lead_sec = {lead:.3f}s")
        # 按本文件自身的结果判定：missing 是跨文件累加的全局计数，直接拿来写
        # 每个 sidecar 会让前一张图的失败污染其后所有图（实测 11/14 被误写 false）
        d["clapper_found"] = all(c["lead_sec"] for c in d["chapters"])
        d["lead_sec"] = d["chapters"][0]["lead_sec"]
        sc.write_text(
            json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    print(
        f"\n>> 场记板测定：{fixed}/{total} 章已回写真实 lead_sec"
        f"{f'（{missing} 章未找到，沿用原值）' if missing else ''}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="场记板白闪实测回写 lead_sec")
    ap.add_argument("--project", default=".", help="视频工程根目录（含 pipeline.toml）")
    ap.add_argument(
        "--window", type=float, default=6.0, help="只在片头这么多秒内找白闪"
    )
    a = ap.parse_args()
    run(Path(a.project).resolve(), a.window)


if __name__ == "__main__":
    main()
