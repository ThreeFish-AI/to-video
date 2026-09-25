#!/usr/bin/env python3
"""骨架漂移门——把 references/07 的纸面义务变成秒级机器判据。

此前「A 档改任何一处须同步并验 md5 唯一」是散文规范，**从未被执行过一次**：
实测 Main.tsx 有注释/换行漂移（两旧集落后于两新集）、cards.tsx 裂成 3-vs-1，
都是在无人察觉中发生的。

两条不变量（依据 references/07 的「义务限于同一系列内」）：
  I1 系列内一致：同一 series 的各集，frozen 文件哈希必须唯一
  I2 模板不过期：baselineOf 指定的系列必须与 assets/video-skeleton 一致
      —— 单集系列的 I1 是空条件（无比较对象），故 I2 不可省

两者**共用同一个逃逸口**（skeleton.toml 的 `[[drift]]`，见 exempt()）：语义不一致
会让单集系列拿不到文档承诺的豁免（I1 放行、I2 仍红，登记者无路可走）。豁免按
指纹钉住，偏离内容一变即报 DRIFT-CHANGED——否则「登记一次、永久免检」。

第二个逃逸口是 `[[generation]]`（骨架分代，见 skeleton.toml 分代节）：一次模板
升级 = 一代，花名册集「整组停在旧代」是合法态（I1/I2 免报、打 INFO），但组内
新旧混杂（半同步）计入未登记（GENERATION-MIXED）——只换部分文件 tsc 必红。
drift 与 generation 重叠时 drift 优先：特有偏离比代际滞后更需要盯。

本档**只报告不阻塞**（退出码恒 0，除非 --strict）：转阻塞前须先把既有漂移登记
或收敛，否则第一次运行就红，而一个「一上线就红」的门只会被立刻关掉。

用法：
  uv run --no-project $T/scripts/verify_skeleton.py            # 报告
  uv run --no-project $T/scripts/verify_skeleton.py --strict    # 有未登记漂移即退出码 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402 - SKILL 模块级、WORKSPACE 惰性解析

TEMPLATE = paths.SKILL / "assets" / "video-skeleton"
SKELETON_TOML = TEMPLATE / "skeleton.toml"

#: Main.tsx 的每集内容：场景 import 行 + SCENE_COMPONENTS 注册表条目。
#: 用归一化而非插入标记注释——后者要改动 4 个已发布集的 A 档邻近文件。
SCENE_IMPORT_RE = re.compile(r"^\s*import\s*\{[^}]*\}\s*from\s*'\./scenes/[^']+';\s*$")
REGISTRY_ENTRY_RE = re.compile(r"^\s*P\d+:\s*\w+,\s*$")


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()[:12]


def normalize_main(text: str) -> str:
    """剥掉 Main.tsx 的每集内容，留下承重 boilerplate。"""
    keep = [
        ln
        for ln in text.split("\n")
        if not SCENE_IMPORT_RE.match(ln) and not REGISTRY_ENTRY_RE.match(ln)
    ]
    return "\n".join(keep)


def structured_package(text: str) -> str:
    """package.json 的受门子集：忽略 name/description，门住依赖与脚本。"""
    d = json.loads(text)
    return json.dumps(
        {k: d.get(k) for k in ("dependencies", "devDependencies", "scripts", "pnpm")},
        ensure_ascii=False,
        sort_keys=True,
    )


def template_source(rel: str) -> Path:
    """模板侧路径：`.tmpl` 是唯一例外——scaffold 渲染前后的同构性由 scaffold.py
    保证（frozen 档字节直拷、structured 档只比结构键），故比对时读渲染前原文。
    structured 的占位符 {{SLUG}}/{{TITLE}} 恰在被忽略的 name/description 里，
    json 解析不受影响；frozen 档无 .tmpl 文件，此回退对它不生效。"""
    plain = TEMPLATE / rel
    if plain.is_file() or not (TEMPLATE / f"{rel}.tmpl").is_file():
        return plain
    return TEMPLATE / f"{rel}.tmpl"


def fingerprint(path: Path, rel: str, cls: str) -> str | None:
    if not path.is_file():
        return None
    if cls == "regioned":
        return hashlib.md5(
            normalize_main(path.read_text(encoding="utf-8")).encode()
        ).hexdigest()[:12]
    if cls == "structured":
        return hashlib.md5(
            structured_package(path.read_text(encoding="utf-8")).encode()
        ).hexdigest()[:12]
    return md5(path)


#: 登记表类型：(episode, path) → (reason, fingerprint|None)
Registry = dict[tuple[str, str], tuple[str, str | None]]


class Generation(NamedTuple):
    """skeleton.toml 的 [[generation]]（原子组旧代豁免，见该文件「骨架分代」节）。

    legacy 键为受门相对路径、值为上一代指纹（12 位 hex 或「缺失」哨兵，口径与
    档位一致：frozen/structured 取原指纹、regioned 取归一化后指纹）。"""

    id: str
    reason: str
    episodes: frozenset[str]
    legacy: dict[str, str]


def gen_owner(generations: list[Generation], slug: str, rel: str) -> Generation | None:
    """→ 该集该文件所属的分代；None = 非分代管辖。

    多代并存时取首个声明代（现存各代文件面互不相交，按文件即可唯一归属；同一
    文件跨代叠加时最旧的代先退役）。episodes 是显式花名册——不在册的集（新集、cp -r 复制集）天然
    不命中，豁免不随复制传播。
    """
    for g in generations:
        if slug in g.episodes and rel in g.legacy:
            return g
    return None


def generation_hit(generations: list[Generation], slug: str, rel: str, fp: str) -> bool:
    """旧代豁免：花名册集的文件指纹 == 该代登记值（含「缺失」哨兵）⇒ 合法旧代。

    调用方须先过 drift 登记（exempt / DRIFT-CHANGED）——drift 钉的是该集特有
    偏离，优先级高于代豁免：某文件被 [[drift]] 钉住其它指纹时按 drift 语义处理，
    代豁免不兜底。
    """
    g = gen_owner(generations, slug, rel)
    return g is not None and g.legacy[rel] == fp


def exempt(registry: Registry, slug: str, rel: str, fp: str) -> bool:
    """该集该文件的**当前**指纹是否被登记表放行。

    登记了但指纹已变 → 不放行，由调用方报 DRIFT-CHANGED：这正是「豁免随偏离
    内容改变而自动失效」的落点。未写 fingerprint 的旧条目仍无条件放行（向前
    兼容），但 tests/test_skeleton.py 要求每条 `[[drift]]` 都带指纹。
    """
    hit = registry.get((slug, rel))
    return hit is not None and (hit[1] is None or hit[1] == fp)


def main() -> int:
    ap = argparse.ArgumentParser(description="骨架漂移门（默认只报告）")
    ap.add_argument("--strict", action="store_true", help="有未登记漂移即退出码 1")
    args = ap.parse_args()

    skel = tomllib.loads(SKELETON_TOML.read_text(encoding="utf-8"))
    classes: dict[str, list[str]] = skel["classes"]
    baseline_series = skel.get("baselineOf")
    #: 登记表 → (reason, fingerprint|None)。**指纹钉住的是「已知的那处偏离」**：
    #: 不带指纹的豁免以 (episode, path) 为键无条件放行，于是该文件此后对任何改动
    #: 都永久免检——而 Main.tsx 恰是每集都要动的文件，等于把最该看的地方蒙上。
    #: 带指纹后豁免会在偏离内容改变时自动失效（同 `# type: ignore[code]` 只豁免
    #: 指定错误码，而非整行）；skeleton.toml 里写的「撤销条件」也随之成为机器判据。
    registered: Registry = {
        (d["episode"], d["path"]): (d.get("reason", ""), d.get("fingerprint"))
        for d in skel.get("drift", [])
    }
    #: 分代登记（[[generation]]）：花名册集「整组停在旧代」的合法态。与 [[drift]]
    #: 的分工——drift 钉**该集特有**偏离（一集一文件一指纹），generation 钉**模板
    #: 升级遗留**的整组旧代（一次升级一代、一组文件一组指纹）；两者重叠时 drift
    #: 优先（特有偏离比代际滞后更需要盯）。
    generations: list[Generation] = [
        Generation(
            id=str(g["id"]),
            reason=str(g.get("reason", "")),
            episodes=frozenset(g.get("episodes", [])),
            legacy=dict(g.get("legacy", {})),
        )
        for g in skel.get("generation", [])
    ]
    series_list = json.loads(
        (paths.WORKSPACE / "series.json").read_text(encoding="utf-8")
    )["seriesList"]

    known_ids = {s["id"] for s in series_list}
    if baseline_series and baseline_series not in known_ids:
        # 新工作区首集自建基线是合法形态（README §骨架纪律），但模板时新性
        # （I2）此刻无人担保——点名而非静默，首集登记后该 WARN 自然消失。
        print(
            f"  ⚠️  baselineOf 系列 {baseline_series!r} 不在本工作区 series.json："
            "模板时新性暂无担保（新工作区首个系列落成后自愈）"
        )

    # 受门档位（seeded 不设门）
    gated = [
        (rel, cls)
        for cls in ("frozen", "overridable", "regioned", "structured")
        for rel in classes.get(cls, [])
    ]

    unregistered = 0
    #: (代 id, slug) → {rel: 'new' | 'old'}：分代状态收集——GENERATION-MIXED
    #: 判定与每代汇总的数据面。drift 放行的非模板文件同样计 'old'（它仍是本代
    #: 原子组的成员，漏计则半同步对 drift 集隐身），但不打旧代 INFO（特有偏离
    #: 优先，报告归 drift 语义）；既非当代模板、亦非登记旧代或 drift 放行的文件
    #: 走普通 DRIFT 路径，不入表。
    gen_states: dict[tuple[str, str], dict[str, str]] = {}
    print(f">> 骨架漂移门 · 模板 {TEMPLATE} · 受门 {len(gated)} 文件\n")

    for series in series_list:
        eps = [e["slug"] for e in series["episodes"]]
        is_baseline = series["id"] == baseline_series
        tag = " [模板基线]" if is_baseline else ""
        print(f"  系列 {series['id']}（{len(eps)} 集）{tag}")
        for rel, cls in gated:
            tmpl_path = template_source(rel)
            tmpl_fp = fingerprint(tmpl_path, rel, cls)
            fps = {
                slug: fingerprint(paths.WORKSPACE / "episodes" / slug / rel, rel, cls)
                or "缺失"
                for slug in eps
            }

            # 分代状态收集 + 旧代可见性：独立于 I1 参照系——纯旧代系列里旧代指纹
            # 恰是系列多数（I1 对它无话可说），旧代集仍须在报告里点名（INFO），
            # 否则「13 集都停在旧代」会静默得像一切如常。旧代集在 I2 参照系选择
            # 中同样静默（见下），这份 INFO 是唯一的逐集可见性。
            for slug in eps:
                g = gen_owner(generations, slug, rel)
                if g is None:
                    continue
                if fps[slug] == tmpl_fp:
                    gen_states.setdefault((g.id, slug), {})[rel] = "new"
                elif (slug, rel) in registered:
                    if exempt(registered, slug, rel, fps[slug]):
                        gen_states.setdefault((g.id, slug), {})[rel] = "old"
                elif fps[slug] == g.legacy[rel]:
                    gen_states.setdefault((g.id, slug), {})[rel] = "old"
                    print(f"    INFO  {rel} · {slug} 停在旧代 {g.id}（重渲时整组同步）")

            seen: dict[str, list[str]] = {}
            for slug, fp in fps.items():
                seen.setdefault(fp, []).append(slug)

            # 参照系：优先取模板指纹，其次取系列内多数——否则「与某人不一致」
            # 会把符合模板的多数集反过来报成偏离方（判据必须有方向）。
            if tmpl_fp and tmpl_fp in seen:
                ref = tmpl_fp
            else:
                ref = max(seen, key=lambda k: (len(seen[k]), k))

            # I1：系列内一致（相对参照系）
            for fp, slugs in sorted(seen.items()):
                if fp == ref:
                    continue
                for slug in slugs:
                    if exempt(registered, slug, rel, fp):
                        continue
                    if (slug, rel) in registered:  # 登记在册但指纹已变
                        unregistered += 1
                        print(
                            f"    DRIFT-CHANGED {rel} · {slug} 现为 {fp}，"
                            f"登记的是 {registered[(slug, rel)][1]}"
                            f" —— 偏离内容已变，豁免失效：请复核后更新 skeleton.toml"
                        )
                        continue
                    if generation_hit(generations, slug, rel, fp):
                        # 整组停在旧代：合法态（逐文件 INFO 已在上方状态收集中
                        # 打过）；半同步的原子性执法在主循环后的 GENERATION-MIXED。
                        continue
                    if cls == "overridable":
                        print(f"    INFO  {rel} · {slug} 行使了覆写许可（{fp}）")
                        continue
                    unregistered += 1
                    print(f"    DRIFT {rel} · {slug}（{fp}）≠ 参照（{ref}）")

            # I2：模板不过期 / 不被绕过。**当前只有一份模板**，故对全部系列执法：
            # 每集的 frozen 指纹必须等于模板，除非登记为漂移。只对基线系列执法的
            # 初版被自己的正控击穿——单集系列的 I1 是空条件（无同侪可比较），
            # 非基线的单集系列就完全落进了盲区。待将来出现第二份模板
            # （跨系列基线分叉），才回退为「仅基线系列」的窄语义。
            # I2 同样尊重逃逸口：全部偏离集都已登记时不报 STALE。否则**单集系列**
            # 拿不到文档承诺的豁免——I1 放行、I2 仍红，登记者无路可走（I1 的
            # 空条件性质正是 I2 存在的理由，两者对逃逸口的语义必须一致）。
            # 同理 I2 必须**尊重档位**：`overridable` 的覆写许可在 I1 只换来 INFO，
            # 若 I2 仍判 STALE，则「全系列都行使许可」——而**单集系列行使一次即是**
            # ——会让 --strict 变红，逼人为一次合法覆写去登记 [[drift]]，等于把
            # 档位声明的许可撤回一半（timing.json 恰是文档鼓励「改节奏只动 JSON」
            # 的那个文件，claude-code-explained 今天恰是单集系列）。
            unreg = [
                s
                for s in eps
                if not exempt(registered, s, rel, fps[s])
                and not generation_hit(generations, s, rel, fps[s])
            ]
            if cls != "overridable" and tmpl_fp and tmpl_fp not in seen and unreg:
                unregistered += 1
                scope = "基线系列" if is_baseline else "系列"
                print(
                    f"    STALE {rel} · {scope} {series['id']} 无一集匹配模板"
                    f"（模板 {tmpl_fp}，实际 {sorted(seen)}；未登记 {unreg}）"
                )

    # 孤儿工程：scaffold 出来但忘了登记 series.json 的目录。这类目录对
    # check_series（只遍历 series.json）与本门（同）**双向不可见**——脚手架
    # 让新建变便宜之后，这个缺口才真正需要堵。阻塞执法在 check_series.py
    # 规则 4（未登记且 narration.md 已落盘即 FAIL，且分级触发以免死锁，判据
    # 与死锁分析见其 rule_manifest_integrity）；本门保持 WARN——漂移门的
    # 职责是骨架一致性，登记是清单问题，只在报告里点名即可。
    registered_slugs = {e["slug"] for s in series_list for e in s["episodes"]}
    orphans = sorted(
        p.name
        for p in (paths.WORKSPACE / "episodes").iterdir()
        if p.is_dir() and p.name not in registered_slugs
    )
    if orphans:
        print(
            f"\n  ⚠️  未登记到 series.json 的工程目录（阻塞门在 check_series.py 规则4；"
            f"narration.md 落盘后该处 FAIL）：{orphans}"
        )

    # GENERATION-MIXED（原子性执法）：花名册集的分代文件**新旧混杂**——半同步集
    # tsc 必红（只拷新 Main 不拷 i18n.tsx，import 当场断），且这种形态对 I1/I2 都
    # 可能静默（单集系列里新代指纹恰是唯一参照）。整组同步或整组回退二选一，
    # 半同步计入未登记。
    for (gid, slug), states in sorted(gen_states.items()):
        if "new" in states.values() and "old" in states.values():
            unregistered += 1
            news = sorted(r for r, v in states.items() if v == "new")
            olds = sorted(r for r, v in states.items() if v == "old")
            print(
                f"    GENERATION-MIXED {gid} · {slug}：分代文件新旧混杂"
                f"（新代 {news} / 旧代 {olds}）"
                "——只换部分文件 tsc 必红，须整组同步或整组回退"
            )

    # 每代一行汇总：旧代集在 I1 参照系选择与 I2 判定中均为静默（合法态不报警），
    # 但「还有几集停在上一代」是重渲排期要读的信号，须可见（roster 总数含不在
    # 本工作区的集；状态只统计 series.json 可见集）。
    if generations:
        print()
        for g in generations:
            states_of = {
                slug: st for (gid, slug), st in gen_states.items() if gid == g.id
            }
            synced = sum(1 for st in states_of.values() if set(st.values()) == {"new"})
            lagging = sum(
                1
                for st in states_of.values()
                if "old" in st.values() and "new" not in st.values()
            )
            print(
                f"  代 {g.id}：roster {len(g.episodes)} 集 · 已同步 {synced} · "
                f"停旧代 {lagging}（重渲时整组同步）"
            )

    #: 漂移登记表随模板分发（skill 仓 skeleton.toml），但登记指向的是**具体工作区
    #: 的具体集**——只显示本工作区 series.json 已知的 slug，他工作区的历史登记
    #: 在此是纯噪音（exempt() 同样以 slug 为键，未知 slug 天然不命中，行为不变）。
    known_slugs = {e["slug"] for s in series_list for e in s["episodes"]}
    visible = {k: v for k, v in registered.items() if k[0] in known_slugs}
    if visible:
        print("\n  已登记的合法偏离（逃逸口必须存在，但必须被记录）：")
        for (slug, rel), (why, pin) in sorted(visible.items()):
            print(f"    · {slug} / {rel}  [指纹 {pin or '未钉'}]\n        {why}")

    print(
        f"\n>> 未登记漂移 {unregistered} 处"
        + ("（--strict 下会失败）" if unregistered and not args.strict else "")
    )
    return 1 if (args.strict and unregistered) else 0


if __name__ == "__main__":
    sys.exit(main())
