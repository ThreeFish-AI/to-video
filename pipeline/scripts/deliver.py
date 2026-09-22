#!/usr/bin/env python3
"""交付归档（deliver）——把 out/final.mp4 复制进「系列子目录 + 标题 vN」的统一归档根。

## 为什么需要它

终渲产物 out/final.mp4 是 gitignored 的新鲜渲槽位：每次重渲直接覆盖，跨集
没有统一归档处，改稿历史无从比对。本脚本把成片按

    <root>/<系列 id>/<集标题> v<N>.mp4

归档：系列 id 与集标题的唯一事实源是 $W/series.json（发布顺序 SSOT，此处
不新增任何配置副本）；版本号 N 实时扫描目标目录取既有最大号 +1——与
cmd_status 同哲学：零状态文件，目录内容即事实源。文件名是 series.json
title 的确定性派生：改题后新题另起 v1、旧版本文件原样保留，不做反向映射。

## 根路径：机器属性，永不写进受版本控制的 toml

与 config.py 对 tts.server、tts.py 对 tts-store 的立场一致（执法：
tests/test_config.py::test_machine_property_never_in_toml）——~/Documents/video
这类本机目录 clone 到他机即死数据。解析序只有两层，且只在本模块定义一处：

    --root（一次性 / prompt 指定）> env TO_VIDEO_DELIVER_ROOT（持久统一配置）

两渠道取值一律 strip，空串 = 未配置；expanduser 展开；相对路径锚工作区根
（绝不锚 CWD——本命令常自任意目录调起）。皆无 → 大声退出并列出两渠道。

## 防护（每条都有测试钉住）

  - 同字节跳过：与目标目录内最新版本 sha1 相同 → 打印跳过 exit 0。重跑命令
    /隔日补投不产生 GB 级重复副本；内容变化才升号。
  - 绝不覆写：落盘前 dest.exists() 复查。macOS 默认 APFS 大小写不敏感而
    Python 目录扫描大小写敏感——标题仅大小写变化会误判首投，在 OS 层静默
    覆写已交付版本。命中即大声退出点名既有文件。
  - 原子落位：copy2 → <dest>.part → os.replace；异常清理 .part，不残留
    「看似合法版本」的半写文件。

用法：
  uv run --no-project $T/pipeline/scripts/deliver.py --project $P [--root <路径>] [--dry-run]
  （经单入口等价：pipeline.py --project $P deliver [--root …] [--dry-run]）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402 - 导入边界见 paths.py 文件头（pipeline.py 家族）

#: 持久统一配置渠道（机器属性注册处 = SKILL.md env 表，同 TO_VIDEO_TTS_STORE）。
ENV_ROOT = "TO_VIDEO_DELIVER_ROOT"

#: 文件名/目录名禁用字符：/ 与 : 是 macOS 真实分隔符，\\ ? * " < > | 是迁往
#: exFAT/NTFS 时的常见雷，控制字符无处合法。全角标点与空格保留——用户示例
#: 「Context Layer Blueprint v1.mp4」与真树标题「AI 如何自己变强？」都依赖这点。
_ILLEGAL = re.compile(r'[/\\:?*"<>|\x00-\x1f]')

#: macOS APFS 单文件名上限 255 UTF-8 字节（exFAT 255 UTF-16 码元更宽，从严取）。
MAX_NAME_BYTES = 255


def sanitize(name: str) -> str:
    """→ 文件系统安全名：strip + 非法字符替换为 '-'（幂等、确定性）。"""
    return _ILLEGAL.sub("-", name.strip())


def scan_versions(names: list[str], title: str) -> list[tuple[int, str]]:
    """→ [(版本号, 文件名)] 升序。全名 fullmatch + re.escape：

    - 标题自带「 v2」尾巴（如《X v2 时代的 Y》）不被计入自己的版本号；
    - 前缀重叠标题（"Y" vs "X Y"）互不抬号；
    - 非匹配文件（.DS_Store、手工副本、"t v1 (fixed).mp4"）天然免疫。
    """
    pat = re.compile(re.escape(title) + r" v(\d+)\.mp4")
    return sorted((int(m.group(1)), n) for n in names if (m := pat.fullmatch(n)))


def sha1_of(p: Path) -> str:
    """流式 sha1（成片 GB 级，不做 read_bytes 全量驻留）。"""
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_root(root_arg: str | None) -> tuple[Path, str]:
    """→ (归档根, 来源标记)。解析序 SSOT 在此一处：--root > env TO_VIDEO_DELIVER_ROOT。"""
    if root_arg and root_arg.strip():
        raw, via = root_arg.strip(), "--root"
    elif env := os.environ.get(ENV_ROOT, "").strip():
        raw, via = env, f"env:{ENV_ROOT}"
    else:
        sys.exit(
            "未配置交付归档根路径。两渠道任选其一（机器属性，不进 toml）：\n"
            "  1. 一次性/prompt 指定：pipeline.py --project <工程> deliver"
            " --root ~/Documents/video\n"
            f"  2. 持久统一配置：export {ENV_ROOT}=~/Documents/video"
            "（写进 shell profile 或 Claude Code settings env）"
        )
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = paths.WORKSPACE / p  # 相对路径锚工作区根，绝不锚 CWD
    return p, via


def checked_name(what: str, raw: object) -> str:
    """清洗 + 空值/超长把关 → 文件系统安全名。"""
    name = sanitize(str(raw or ""))
    if not name:
        sys.exit(f"series.json 的{what}清洗后为空（原值 {raw!r}）")
    if len(name.encode("utf-8")) > MAX_NAME_BYTES:
        sys.exit(f"{what}超长（>{MAX_NAME_BYTES} UTF-8 字节）: {name[:32]}…")
    return name


def load_series(ws: Path) -> list[dict]:
    """读 seriesList[]；缺文件/坏 JSON/空清单均大声退出（不裸 traceback）。"""
    sj = ws / "series.json"
    if not sj.is_file():
        sys.exit(
            f"series.json 不存在: {sj}（系列归属与集标题的事实源；"
            "登记步骤见 pipeline/README.md §六）"
        )
    try:
        data = json.loads(sj.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"series.json 不是合法 JSON: {sj}（{e}）")
    if not isinstance(data, dict):
        sys.exit(f"series.json 顶层应为对象: {sj}（实际 {type(data).__name__}）")
    series_list = data.get("seriesList") or []
    if not isinstance(series_list, list) or not all(
        isinstance(s, dict) for s in series_list
    ):
        sys.exit(f"series.json 的 seriesList 应为对象数组: {sj}")
    if not series_list:
        sys.exit(f"series.json 无 seriesList: {sj}")
    for s in series_list:
        # episodes 非列表（字符串/dict/null）会让下游迭代出非 dict 元素——同门把关
        eps = s.get("episodes", [])
        if not isinstance(eps, list) or not all(isinstance(e, dict) for e in eps):
            sys.exit(
                f"series.json：系列 {s.get('id')!r} 的 episodes 应为对象数组: {sj}"
            )
    return series_list


def locate_episode(project: Path) -> tuple[dict, dict]:
    """→ (系列条目, 集条目)。

    主锚 = ep.path（工作区根相对）——与 fanout / check_series.rule_title_order
    的既有消费一致；slug 只作交叉校验（slug↔path 绑定无门执法，不能当主锚）。
    """
    ws = paths.WORKSPACE
    series_list = load_series(ws)

    def ep_root(ep: dict) -> Path | None:
        """条目的工程根；path 缺失/非字符串（null 等）按「无锚」处理，不炸。"""
        p = ep.get("path")
        return (ws / p).resolve() if isinstance(p, str) else None

    hits = [
        (s, ep)
        for s in series_list
        for ep in s.get("episodes", [])
        if ep_root(ep) == project.resolve()
    ]
    if not hits:
        ids = [s.get("id") for s in series_list]
        sys.exit(
            f"{project} 未登记进 {ws / 'series.json'}（按 path 锚未命中；"
            f"现有系列：{ids}）\n"
            "  —— 交付归属（系列子目录/集标题）以登记为准，"
            "请先按 pipeline/README.md §六步骤 4 登记本集。"
        )
    if len(hits) > 1:
        sys.exit(
            f"{project} 在 series.json 命中多条（系列 {[s.get('id') for s, _ in hits]}）"
            "——同一 path 两条登记会让发布顺序 SSOT 自相矛盾，请先修 series.json。"
        )
    s, ep = hits[0]
    if "title" not in ep:
        sys.exit(f"series.json：系列 {s.get('id')!r} 的集 {ep.get('path')!r} 缺 title")
    if ep.get("slug") != project.name:
        print(
            f"  ⚠️  series.json 条目 slug={ep.get('slug')!r} 与工程目录名"
            f" {project.name!r} 不一致（按 path 锚继续交付；建议对齐登记）"
        )
    return s, ep


def warn_if_inside_workspace(root: Path) -> None:
    """交付根落在 $W 内且不在 episodes/ 下时提醒——工作区 .gitignore 只盖
    episodes/**/*.mp4，非 episodes 落点的成片会污染 git status。"""
    ws = paths.WORKSPACE.resolve()
    root_res = root.resolve()
    if root_res != ws and ws not in root_res.parents:
        return
    rel = root_res.relative_to(ws)
    if rel.parts and rel.parts[0] == "episodes":
        return
    print(
        f"  ⚠️  交付根在工作区内（{root_res}）且不在 episodes/ 下——"
        "成片不被 .gitignore 覆盖，会出现在 git status 里"
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="交付归档：out/final.mp4 → <根>/<系列id>/<集标题> vN.mp4（版本号自增）"
    )
    ap.add_argument("--project", required=True, help="分集工程根（含 out/final.mp4）")
    ap.add_argument(
        "--root",
        help=f"交付归档根路径（一次性/prompt 指定；持久统一配置用 env {ENV_ROOT}）",
    )
    ap.add_argument(
        "--dry-run", action="store_true", help="只打印目的地与下一版本号，不写入"
    )
    args = ap.parse_args()

    project = Path(args.project).resolve()
    root, via = resolve_root(args.root)
    series, ep = locate_episode(project)

    src_mp4 = project / "out" / "final.mp4"
    if not src_mp4.is_file():
        sys.exit(f"缺少终渲产物: {src_mp4}（先跑 pipeline.py render --final）")

    sid = checked_name("系列 id", series.get("id"))
    title = checked_name("集标题", ep["title"])
    dest_dir = root / sid
    warn_if_inside_workspace(root)

    # 只收普通文件：同名目录不抬号也不进 sha1（占名冲突由 dest.exists() 复查兜底）。
    # 列举与下方 sha1 读同环境条件（无读权限/并发删除）——同样大声退出，不裸栈。
    names: list[str] = []
    if dest_dir.is_dir():
        try:
            names = sorted(p.name for p in dest_dir.iterdir() if p.is_file())
        except OSError as e:
            sys.exit(f"版本目录列举失败: {e}")
    versions = scan_versions(names, title)
    try:
        if versions and sha1_of(dest_dir / versions[-1][1]) == sha1_of(src_mp4):
            print(f">> 与最新版本字节一致，跳过（{versions[-1][1]}）——内容变化才会升号")
            return 0
    except OSError as e:  # 并发删除/无读权限：比对不了就大声退出，不裸栈
        sys.exit(f"版本比对读取失败: {e}")
    nxt = versions[-1][0] + 1 if versions else 1
    dest = dest_dir / f"{title} v{nxt}.mp4"

    # 长度守卫以**实际创建的最长名**为准：copy2 先打开 .part 中转段（比终名多
    # 5 字节），只把关裸标题或终名会放行 244–248 字节标题到写入期才炸
    # ENAMETOOLONG（checked_name 的裸 255 门拦不住这一段）。
    if len((dest.name + ".part").encode("utf-8")) > MAX_NAME_BYTES:
        sys.exit(
            f"集标题加版本后缀超长（>{MAX_NAME_BYTES} UTF-8 字节，含 .part 中转段）:"
            f" {title[:32]}…"
        )
    if root.exists() and not root.is_dir():
        sys.exit(f"交付根是文件而非目录: {root}")
    if dest_dir.exists() and not dest_dir.is_dir():
        sys.exit(f"系列子目录被文件占名: {dest_dir}")
    if dest.exists():
        sys.exit(
            f"目的地已存在，拒绝覆写: {dest}\n"
            "  —— 大小写不敏感文件系统上的扫描漏网（标题仅大小写变化）；"
            "请先手动处理既有文件。"
        )

    print(f">> deliver{' [dry-run]' if args.dry_run else ''}  {src_mp4}")
    print(f"   系列 {series.get('id')!r} · 标题 {ep['title']!r} · 根来源 {via}")
    print(f"   → {dest}（v{nxt}；目录内既有 {len(versions)} 版）")
    if args.dry_run:
        return 0

    part = dest.with_name(dest.name + ".part")
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_mp4, part)
        os.replace(part, dest)
    except OSError as e:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass  # 清理自身失败不把异常带出（ENAMETOOLONG 时 copy2 未写字节，本就无可清）
        sys.exit(
            f"交付写入失败（已清理 {part.name}）: {e}\n  源 {src_mp4} → 目的 {dest}"
        )
    print(f">> 已交付 {dest}（v{nxt}；copy2 保留源 mtime）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
