#!/usr/bin/env python3
"""新集脚手架——从命名的模板实例化，替代「cp -r 任一既有集」。

此前 README 的原话是「以**任一**既有集工程为模板复制 video/ 骨架」。「任一」
就是那个 SSOT 违规：391 行冻结基建因此有 4 个同权真理声明者，而「改一处须同步」
的义务没有判据、从未被执行。本脚本让复制源头有名字，`verify_skeleton.py` 让
义务有判据。

## 刻意不做的三件事

1. **不生成 scenes/**。目录留空，场景骨架样例只在模板里（scenes-EXAMPLE.tsx.txt，
   刻意不用 .tsx 后缀，免得被 tsc 收进去）。切割线是有意的：脚手架只拿走**机械
   复制**（那 391 行你本来就不该逐行读的冻结基建），保留**创作性撰写**（theme
   与 scenes 必须读 references/06 才写得对）。手抄一遍学到的东西不该被一键抹掉。
2. **不改工作区根 .gitignore**。会修改工作区根文件的脚手架是爆炸半径的意外扩张；且
   ignore 规则已通配到分集级，新集自动覆盖，本来就无需这一步。
3. **不写 series.json**。登记发布顺序是内容决策（要定 episode 序号、色板、
   sourceKind），不是机械步骤。⚠️ 漏登**没有阻塞门**：`check_series.py` 只遍历
   series.json，看不见孤儿目录；`verify_skeleton.py` 会点名警告但不计入未登记
   漂移（`--strict` 不失败）。故下方 step 6 必须由人执行，别指望门兜住。

用法：
  uv run --no-project $T/scripts/scaffold.py <slug>-video --title "本集标题"
  uv run --no-project $T/scripts/scaffold.py --init-workspace [dir]
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402 - SKILL 模块级解析；WORKSPACE 惰性（init 须在无工作区处可跑）

#: 模板随 skill 分发（机制），不随内容工作区。
TEMPLATE = paths.SKILL / "assets" / "video-skeleton"
WORKSPACE_TEMPLATE = paths.SKILL / "assets" / "workspace"


def render(text: str, subs: dict[str, str]) -> str:
    for k, v in subs.items():
        text = text.replace(f"{{{{{k}}}}}", v)
    return text


#: 工作区骨架的「点名 → 目标名」映射（模板里不带点前缀，防模板自吞）。
_WS_ARTIFACTS = {
    "to-video-root.tmpl": ".to-video-root",
    "series.json.tmpl": "series.json",
    "series.md.tmpl": "series.md",
    "to-video.toml.tmpl": "to-video.toml",
    "gitignore.tmpl": ".gitignore",
    "README.md.tmpl": "README.md",
    "scripts/pipeline.py.tmpl": "scripts/pipeline.py",
    "scripts/check_series.py.tmpl": "scripts/check_series.py",
    "voices/README.md": "voices/README.md",
    "voices/refs.toml": "voices/refs.toml",
}


def init_workspace(ws: Path, force: bool) -> int:
    """初始化/补全内容工作区：幂等，逐工件 skip-if-exists（--force 覆盖）。

    与建集脚手架同一纪律：只做**机械落盘**（哨兵、空 series、目录、包装器），
    内容决策（登记系列、录样本指纹、填 README）留给使用者，结尾点名。
    """
    ws.mkdir(parents=True, exist_ok=True)
    created, kept = [], []
    for src_name, dst_name in _WS_ARTIFACTS.items():
        src = WORKSPACE_TEMPLATE / src_name
        dst = ws / dst_name
        if dst.exists() and not force:
            kept.append(dst_name)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        created.append(dst_name)
    for d in ("episodes", "source-map"):
        (ws / d).mkdir(parents=True, exist_ok=True)
        (ws / d / ".gitkeep").touch()
    print(f">> 工作区 {ws}")
    print(
        f"   新建 {len(created)} 件 / 保留既有 {len(kept)} 件"
        + ("（--force 可覆盖）" if kept else "")
    )
    print("\n接下来**必须**人工完成的（脚手架刻意不代做）：")
    print("  1. series.json 登记第一个系列（id/title/sourceKind/rule/episodes）")
    print("  2. voices/：prospect_ref 选段 → prepare_ref 裁样 → 把指纹写进 refs.toml")
    print("  3. to-video.toml：按需声明 check_series 的工程级受检面与系列 id 集")
    print("  4. （可选）git init；README.md 按本工作区实态改写")
    print(
        "\n  建集：uv run --no-project "
        f"{Path(__file__).resolve()} <slug>-video --title 本集标题"
        " --ref <样本名> --ref-sha1 <12位指纹> --style <档名>"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="从模板实例化新集工程")
    ap.add_argument(
        "slug", nargs="?", help="工程目录名，须以 -video 结尾（= series.json 的 slug）"
    )
    ap.add_argument(
        "--title", help="本集标题（写入 README 与 package.json；建集模式必填）"
    )
    ap.add_argument("--ref", default="me-bright", help="参考样本名（见 refs.py list）")
    #: 占位符**必须自身合规**（12 位）：config.validate 的位数检查是全节执法，
    #: 而 pipeline.py 对每个子命令都以 scope=None 校验——一个 11 位的占位会让刚
    #: 实例化的新集连 `build`（Stage ③，与 TTS 无关）都跑不起来。指纹不符仍由
    #: doctor 与 tts.py 的 --expect-ref-sha1 硬拦，占位不会被误当成真值。
    ap.add_argument("--ref-sha1", default="TODOTODOTODO", help="样本 12 位指纹")
    ap.add_argument("--style", default="sunny-steady", help="风格预设档名")
    ap.add_argument("--force", action="store_true", help="目标已存在时仍继续（危险）")
    ap.add_argument(
        "--init-workspace",
        nargs="?",
        const=".",
        default=None,
        metavar="DIR",
        help="初始化/补全一个内容工作区（哨兵+series+voices+包装器；幂等，逐工件 skip-if-exists）",
    )
    args = ap.parse_args()

    if args.init_workspace is not None:
        sys.exit(init_workspace(Path(args.init_workspace).resolve(), args.force))
    if args.slug is None or args.title is None:
        ap.error("建集须提供 <slug>-video 与 --title（或改用 --init-workspace [DIR]）")

    if not args.slug.endswith("-video"):
        sys.exit(f"slug 须以 -video 结尾（与既有四集一致）：{args.slug!r}")
    episodes_dir = paths.WORKSPACE / "episodes"
    dest = episodes_dir / args.slug
    if dest.exists() and not args.force:
        sys.exit(f"目标已存在：{dest}（如确要覆盖请加 --force）")

    skel = tomllib.loads((TEMPLATE / "skeleton.toml").read_text(encoding="utf-8"))
    subs = {
        "SLUG": args.slug,
        "TITLE": args.title,
        "REF": args.ref,
        "REF_SHA1": args.ref_sha1,
        "STYLE": args.style,
    }

    #: 只留在模板里、不复制进新集的文件。scenes-EXAMPLE 是刻意的（见文件头
    #: 「不生成 scenes/」）：抄骨架的过程本身有价值，样例留在模板供查阅。
    TEMPLATE_ONLY = {"skeleton.toml", "scenes-EXAMPLE.tsx.txt"}

    copied, rendered = 0, 0
    for src in sorted(TEMPLATE.rglob("*")):
        if not src.is_file() or src.name in TEMPLATE_ONLY:
            continue
        rel = src.relative_to(TEMPLATE)
        if src.suffix == ".tmpl":
            target = dest / rel.with_suffix("")  # 去掉 .tmpl
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                render(src.read_text(encoding="utf-8"), subs), encoding="utf-8"
            )
            rendered += 1
        else:
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            copied += 1

    # 内容层空目录（写作阶段的产物落点，刻意不给模板内容）
    for d in ("research", "script"):
        (dest / d).mkdir(parents=True, exist_ok=True)

    print(f">> 已实例化 {dest}：复制 {copied} 文件 / 渲染 {rendered} 模板\n")
    print("接下来**必须**人工完成的（脚手架刻意不代做）：")
    print(
        "  1. research/ 取证：Stage ① —— A 型论文走 paper_extract.py，B 型走 source_ledger.py"
    )
    print("  2. script/planning.md：Stage ② 六节齐，含本集视觉契约（色彩语义）")
    print(
        "  3. video/src/design/theme.ts：换本集概念色（≥4.5:1，色相不与系列已用色撞车）"
    )
    print(
        "  4. script/narration.md → storyboard.md → video/src/scenes/*.tsx（全部新写）"
    )
    print(
        "  5. video/src/Main.tsx：填 scenes/ import 与 SCENE_COMPONENTS 注册表"
        "（模板两处刻意留空，故新集开箱即 tsc 干净）"
    )
    print(
        "  6. 登记到 series.json（漏登无阻塞门：verify_skeleton.py 会点名警告孤儿目录）"
    )
    print(
        "  7. cd video && pnpm install（裸 install——分集 pnpm-workspace.yaml 已自锚；勿加 --ignore-workspace，会连本工程 workspace 一并忽略致 ERR_PNPM_IGNORED_BUILDS。装完核对根 lockfile 零变更）"
    )
    print(
        f"\n  冻结档位与漂移判据见 {TEMPLATE / 'skeleton.toml'}"
        f"（{len(skel['classes'].get('frozen', []))} 个 frozen 文件已复制，勿改）"
    )
    print("  实例化后立刻跑一次：uv run --no-project $T/scripts/verify_skeleton.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
