#!/usr/bin/env python3
"""④⑥ 内容门：分镜覆盖性、时长预算、淡入不变式——公共管线版本。

机械化清单（此前靠人眼/散文守着的事）：
  1. storyboard 的 beat 句 id 区间必须**覆盖**本幕每一句（无缺句），重叠仅允许
     「标题卡/章头压前句尾」的刻意惯例（该 beat 的句区间单元格以「尾」结尾标注）；
  2. 时长预算：narration.json 字数估算与 manifest 实测（若已合成）两个口径都对
     pipeline.toml 的 target_minutes 负责——首次把「策划宣称/估算/实测」三处接上；
  3. 幕间呼吸淡入淡出的不变式：2×sceneCrossFadeSec ≤ sentenceGap+sceneGap
    （淡入淡出必须花在既有静默里，时间轴零位移的前提）；
  4. 读法陷阱：上游中文归一化实测会读错的写法（4 位年份带空格、三段版本号、
     数字区间连字符、±、10x、整句无汉字…）——见 READING_TRAPS，每条都附实测输出。
  5. zh 字幕单行宽度（RSI-024）：frozen 模板对 zh 恒单行 + 字号下限 30px +
     nowrap，全角当量超 floor(1528/30)=50 即物理溢出画布——上限钉进门里
     而不是钉在稿风里（旧代可折行模板点名跳过）。

**双语（--lang en，RSI-004）**：语言无关门（分镜覆盖/淡入/场景互比/动效互比）
只在主稿执法——分镜与场景代码是 zh 主稿的派生物，en 按句 id 复用，重复执法
只会双报同源错。en 门集见 check_translation：对齐（与主稿句 id 1:1）、基线锁
（译稿失鲜）、文本形态（禁汉字 / 必含拉丁字母 / 禁全角标点——防上游
use_chinese() 的整句嗅探把英文句路由进中文归一化）、字幕溢出；预算按词数 /
words_per_min 对 narration.en.target_minutes 窗口（缺省点名跳过，不继承 zh）。
--check-scenes --lang en 附未翻译画面文字报告（scenes/*.tsx 中未走 <L zh en> /
t({zh, en}) 双语对的含汉字字面量，WARN-only）。

画面文字复述口播门（RSI-007，FAIL，**缺省执法、无需 flag**——忘带 flag = 检查面
静默缩小，同 ISSUE-168）：场景代码里与口播逐字相同的画面文字，与烧录字幕叠成
同屏两层。语言相关门，zh / en 各自对本语言字幕面执法；--pre-tts 不跑（场景未写）。

可选 --check-scenes：从 video/src/scenes/*.tsx 提取 beatWindow/w('id','id')
调用，与分镜表互比（WARN，TSX 正则本质近似）；at()/dur() 引用的句 id 须真实
存在（FAIL，ISSUE-190）。

可选 --check-motion：分镜「动效」列的 @动词 标注 ↔ 场景代码运动模型调用互比
（WARN-only）。动效列可写 `@enter:fall`、`@stagger`、`@draw` 等（动词表从本集
video/src/motion/hooks.ts 的 use* 导出**派生**，单一事实源不复制）；镜内声明了
@动词 而该幕场景文件未调用对应 use 模型 → WARN——「FadeUp 写在分镜里却没进代码」
（实测发生过 3 处）这一缺陷类的机械化。反向（代码用了模型而分镜没写）不报：
动效列是意图摘要而非全量清单。

可选 --pre-tts（TTS 前置门）：只跑**不需要分镜**的检查——时长预算（估算口径；
manifest 若在则含实测口径）+ 读法陷阱 + 发音标注合法性（build_narration 已在
生成期拦非法标注，此处对 narration.json 再收口一遍）+ zh 字幕单行宽度。
两遍法草稿遍（A 遍）写完
稿就要排配音、storyboard.md 尚未写——本模式在 storyboard.md 缺失时照常完成并
以 0 退出；storyboard 相关的覆盖性/淡入/场景互比在此模式下一律跳过。

可选 --pron-candidates（报告，非门）：逐句列出命中多音字候选表的句子
（候选表见 pron_marks.POLYPHONE_CANDIDATES；与 --pre-tts / --lang en 互斥——
与门混跑会让退出码语义含混，多音字表只针对中文）。退出码恒 0；句中带非法
标注时点名但不判死（标注合法性的执法在 --pre-tts 面）。

可选 --pron-gate（RSI-014，门）：在候选报告之上，把「语义规则命中而句中该
occurrence **无任何标注**」升为 FAIL。字典级确定的语境（每行/单选行/银行）
不该等复听——jev 集全片 26 处「行(háng)」被读成 xíng（v1＝negentropy 37692b45d；
修复 8974c2f3f 标 27 处），候选报告全程零拦截、
终渲后才靠人耳发现。已标注的 occurrence（无论读音是否同推荐）视为作者显式
接管，不拦——语义规则是建议不是权威；「接管」的前提是标注本身合法：非法
标注（必然读错，比漏标更严重）在本面直接 FAIL（评审回归 D2-1）。缺省（不带
本 flag）仍为报告。与 --pre-tts / --term-density / --lang en 互斥（规则表
只针对中文）；--json/--check-scenes/--check-motion 属内容门面，同样互斥。

可选 --term-density（RSI-015，WARN 级）：④B 密度预算的机器面——逐 beat 统计
**首现术语**个数（>2 报 WARN）、逐幕汇总（>8 报 WARN），超出须拆 beat 或用
白话替代消术语。术语两面：`--terms 逗号清单` 显式声明（中文术语系统由 ④B
评审员圈定后喂入——机器分不出「集中度」是不是术语，声明优于猜测）＋拉丁
字母词自动面（Jev、top-p 这类英文专名）。beat 边界读 narration.json 的
beatStart（build 派生，幕内空行 = 一个 beat）；旧版产物缺失该键时 beat 级
点名跳过、幕级照跑。与 --lang en 互斥（英文稿整句拉丁字母，密度口径无意义）。

用法：uv run --no-project $T/scripts/check_script.py --project $P [--lang zh|en]
退出码：0 = 通过；1 = 有 FAIL。WARN 不影响退出码但会列明。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # noqa: E402
import config  # noqa: E402 - 同目录模块，须在 sys.path 注入之后
import langs  # noqa: E402
from build_narration import read_lock, stale_ids  # noqa: E402
from pron_marks import scan_candidates, semantic_missing, strip_marks, validate  # noqa: E402
from timeline import load_constants, total_duration_in_frames  # noqa: E402

#: 分镜表行：| 镜号 | 句区间 | 画面 | 动效 |。镜号形如 `0-A`/`2-B2`。
ROW_RE = re.compile(r"^\|\s*(\d+-[A-Z]\d*)[^|]*\|([^|]*)\|([^|]*)\|")
#: 句区间单元格：`p0-01..03`（右端可为裸编号，须补幕前缀）、`p6-06a..06d`、单句 `p6-07`。
SPAN_RE = re.compile(r"^\s*(p\d+-[0-9a-z-]+(?:\.\.[0-9a-z-]+)?)\s*([^|]*)$")
#: 场景组件里的 beat 调用。实际形如 `w('p0-01', 'p0-04')`（各场景统一先定义
#: `const w = (fromId, toId?) => beatWindow(scene.sentences, scene.from, …)` 再使用），
#: 故匹配任意 `\w(...)` 调用并要求参数为 1–2 个单引号句 id。
SCENE_CALL_RE = re.compile(r"\bw\(\s*'([a-z0-9-]+)'(?:\s*,\s*'([a-z0-9-]+)')?\s*\)")
#: 场景代码里的时点/时长锚：`at('id')` / `dur('id')`（archify cue 与杂项引用）。
#: ISSUE-190 病理：分镜 beat 句 id 有存在性检查，但 scene 代码里**非 beat 的**
#: at()/dur() 引用不在任何形态断言内——p1-23 跳号句嵌套窗 tsc 与覆盖门全放行、
#: 渲染期才抛。此正则把那类引用拉进同一存在性门。
SCENE_ANCHOR_RE = re.compile(r"\b(?:at|dur)\(\s*'([a-z0-9-]+)'\s*\)")
#: 幕名（P0/P1/…）从句 id 前缀还原
SCENE_OF_RE = re.compile(r"^(p\d+)-")


def fail(msgs: list[str], text: str) -> None:
    msgs.append(f"FAIL {text}")


def warn(msgs: list[str], text: str) -> None:
    msgs.append(f"WARN {text}")


def _rows(path: Path) -> list[tuple[str, str, str]]:
    """→ [(镜号, 句区间单元格, 画面单元格)]。行集 = 镜号/句区间/画面三列齐全的行。

    画面列在此一并取出：覆盖门（check_archify_coverage）的分镜声明对账要读它，
    单独再写一个行正则就是第二解析器——分叉即 split-brain。"""
    out: list[tuple[str, str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if m := ROW_RE.match(raw):
            out.append((m.group(1), m.group(2), m.group(3)))
    return out


def parse_storyboard(path: Path) -> list[tuple[str, str, str, str]]:
    """返回 [(镜号, 起句id, 止句id, 区间单元格原文)]。单元格原文含「尾」= 刻意压尾标注。"""
    beats: list[tuple[str, str, str, str]] = []
    for beat_id, span_cell, _visual in _rows(path):
        sm = SPAN_RE.match(span_cell)
        if not sm:
            continue
        span, cell = sm.group(1), (sm.group(1) + sm.group(2))
        if ".." in span:
            left, _, right = span.partition("..")
            # 右端可为裸编号（p0-01..03）——须补幕前缀，否则永远匹配不到句子
            if not right.startswith("p"):
                scene = SCENE_OF_RE.match(left).group(1)  # type: ignore[union-attr]
                right = f"{scene}-{right}"
        else:
            left = right = span
        beats.append((beat_id, left, right, cell))
    return beats


def parse_storyboard_visual(path: Path) -> list[tuple[str, str]]:
    """→ [(镜号, 画面列原文)]。行集与 parse_storyboard 完全一致（同一 _rows + SPAN_RE
    过滤，索引按序对齐）——覆盖门从画面列抽 `·**archify …**` 声明。"""
    out: list[tuple[str, str]] = []
    for beat_id, span_cell, visual in _rows(path):
        if SPAN_RE.match(span_cell):
            out.append((beat_id, visual))
    return out


def check_coverage(
    items: list[dict], beats: list[tuple[str, str, str, str]], msgs: list[str]
) -> None:
    ids = [i["id"] for i in items]
    pos = {sid: k for k, sid in enumerate(ids)}
    covered = [False] * len(ids)
    for beat_id, left, right, cell in beats:
        if left not in pos or right not in pos:
            bad = left if left not in pos else right
            fail(
                msgs,
                f"镜 {beat_id}：句 id {bad!r} 不在 narration.json（分镜陈旧或笔误）",
            )
            continue
        a, b = pos[left], pos[right]
        if b < a:
            fail(msgs, f"镜 {beat_id}：区间 {cell} 起止倒置")
            continue
        overlap = any(covered[a : b + 1])
        deliberate = "尾" in cell  # 区间单元格原文含「尾」= 标题卡压前句尾的刻意惯例
        for k in range(a, b + 1):
            covered[k] = True
        if overlap and not deliberate:
            warn(
                msgs,
                f"镜 {beat_id}：区间 {cell} 与前镜重叠（若为标题卡压前句尾的刻意设计，请在句区间后标注「尾」）",
            )
    missing = [sid for sid, c in zip(ids, covered, strict=False) if not c]
    if missing:
        fail(msgs, f"分镜未覆盖 {len(missing)} 句: {' '.join(missing)}")
    # 分镜表与代码的镜号互比（按幕：分镜镜号前缀数字 == 幕序号）
    scene_nums = sorted({int(SCENE_OF_RE.match(i["id"]).group(1)[1:]) for i in items})  # type: ignore[union-attr]
    beat_nums = sorted({int(b[0].split("-")[0]) for b in beats})
    if beat_nums and beat_nums != scene_nums:
        warn(msgs, f"分镜覆盖的幕 {beat_nums} 与 narration 的幕 {scene_nums} 不一致")


def check_budget(
    root: Path, items: list[dict], cfg: dict, msgs: list[str], lang: str = langs.PRIMARY
) -> None:
    """时长预算门（估算 + 实测），窗口与语速单位经 config.for_lang 视图取。

    zh：target_minutes 窗口 + chars_per_min 字数口径（行为与单语时代逐字节一致）。
    en：窗口只认 narration.en.target_minutes——缺省点名 WARN 跳过、**不继承 zh
    窗口**（英文稿的合理窗与中文不同，静默继承等于造出一个没人声明过的门）；
    估算 = 词数 ÷ words_per_min；实测读 audio/en/manifest.json。

    实测口径只对「属于当前生效引擎」的 manifest 执法（RSI-034），两条件跳过并
    点名：① 草声期——engine=edge 且挂终声档锚点（tts.style），edge 语速≠终声
    档口径，草声实测对终声窗执法必然系统性偏短；② 升档中间态——.engine 标记
    首 token 与当前 engine 不符（toml 已翻 indextts、音频还是 edge），照窗执法
    会把重配拦死在 --pre-tts 前置门。重配完成（标记重写）后本门自动恢复。"""
    view = config.for_lang(cfg, lang)
    narr = view.get("narration", {})
    budget = narr.get("target_minutes")
    # 形状校验归 config.validate（FAIL 已在那里报过）；此处只管「能否作为预算窗使用」。
    # 缺失与形状非法同路处理：解包前崩溃会让 FAIL 清单一条也打不出来。
    usable = (
        isinstance(budget, list)
        and len(budget) == 2
        and all(isinstance(x, (int, float)) for x in budget)
    )
    if not usable:
        # 此前缺失时静默退化为 [0, 999]——一个「你以为开着其实关着的门」。
        # 点名 WARN 是本次改动的要点：门被跳过必须说出来。
        if lang != langs.PRIMARY and budget is None:
            warn(
                msgs,
                "narration.en.target_minutes 未声明：**跳过 en 时长预算门**"
                "（英文窗口独立声明，不继承 zh 窗口）",
            )
        else:
            key = (
                "narration.target_minutes"
                if lang == langs.PRIMARY
                else f"narration.{lang}.target_minutes"
            )
            warn(
                msgs,
                f"{key} 缺失或形状非法（{budget!r}）："
                "**跳过时长预算门**（无 pipeline.toml？）",
            )
        lo, hi = 0, 999
    else:
        lo, hi = budget
    # 默认值取自 config.SCHEMA：本函数在 `required=False` 且缺 pipeline.toml 时
    # 拿到的 cfg 是 `{}`（load 不走 resolve），内联一份就是第二事实源。
    if lang == langs.PRIMARY:
        cpm = narr.get("chars_per_min", config.default("narration.chars_per_min"))
        chars = sum(len(i["text"]) for i in items)
        est_min = chars / cpm
        print(
            f"  估算口径：{chars} 字 ÷ {cpm} 字/分 = {est_min:.1f} 分钟（目标 {lo}–{hi}）"
        )
    else:
        wpm = narr.get("words_per_min", config.default("narration.words_per_min"))
        words = sum(langs.length(i["text"], lang) for i in items)
        est_min = words / wpm
        print(
            f"  估算口径：{words} 词 ÷ {wpm} 词/分 = {est_min:.1f} 分钟（目标 {lo}–{hi}）"
        )
    if not lo <= est_min <= hi:
        fail(msgs, f"估算时长 {est_min:.1f} 分超预算 [{lo}, {hi}]")
    manifest = langs.manifest(root, lang)
    if manifest.is_file():
        m_items = json.loads(manifest.read_text(encoding="utf-8"))
        tts_view = view.get("tts", {})
        engine = tts_view.get("engine", config.default("tts.engine"))
        anchor = tts_view.get("style")
        marker = langs.audio_dir(root, lang) / ".engine"
        marker_engine = (
            marker.read_text(encoding="utf-8").split("|", 1)[0].strip()
            if marker.is_file()
            else None
        )
        if engine == "edge" and isinstance(anchor, str) and anchor:
            print(
                "  实测口径：草声期跳过（engine=edge 且挂终声档锚点）——"
                "预算按终声档估算口径执法，重配完成后以终声实测复核；"
                "以 edge 为终声交付的集应删除 tts.style 锚点恢复本门"
            )
        elif marker_engine is not None and marker_engine != engine:
            print(
                f"  实测口径：跳过——manifest 属 {marker_engine} 引擎、当前生效 "
                f"{engine}（升档重配未完成）；重配完成后本门自动恢复"
            )
        else:
            c = load_constants(root)
            real_min = total_duration_in_frames(m_items, c) / c["fps"] / 60
            print(
                f"  实测口径：manifest {len(m_items)} 句，含时距总长 = {real_min:.1f} 分钟"
            )
            if not lo <= real_min <= hi:
                fail(msgs, f"实测时长 {real_min:.1f} 分超预算 [{lo}, {hi}]")
        # 句 id 集一致性是文本层事实（与引擎无关），跳过实测窗时照常执法
        if {i["id"] for i in m_items} != {i["id"] for i in items}:
            fail(msgs, "manifest 与 narration.json 的句 id 集不一致——改稿后未重跑 tts")
    else:
        print("  实测口径：manifest 未生成（跳过；合成后复跑本门）")


#: 读法陷阱：上游中文文本归一化（macOS 上是 wetext，`indextts/utils/front.py:116-142`）
#: 会把数字展开成口语读法，绝大多数写法都正确，但下列写法**实测读错**。
#:
#: 每条都标注了 2026-08-20 在本机 index-tts venv 上直接跑 `TextNormalizer.normalize()`
#: 得到的真实输出——加规则前先跑探针拿证据，不要凭直觉列清单（本轮就有两条「疑似错误」
#: 实测其实是对的：`0.5~1.0 秒`→`零点五到一点零秒`、`9:30`→`九点三十分`，故未列入）。
#:
#: 归一化是**幂等**的：把读法预写成汉字后再过一遍结果不变，所以修复可逐句增量做。
READING_TRAPS: tuple[tuple[str, str, str], ...] = (
    (
        r"\d{4}\s+年",
        "FAIL",
        "4 位年份与「年」之间有空格：`2026 年` 读成「两千零二十六年」（写成 `2026年` 才读「二零二六年」）",
        # ⚠️ 空格位置敏感（2026-08-21 探针复核）：错读只发生在空格**夹在年份与「年」之间**；
        # 空格在年份**前**（`这篇 2026年的`）读法正确（「二零二六年」），门也不触发——不要
        # 把这类句子「顺手规范化」成年份前无空格以外的别的形态。
    ),
    (
        r"\d+\.\d+\.\d+",
        "FAIL",
        "三段版本号：`2.5.1` 读成「二.五点一」（残留字面小数点）——改写为「二点五点一」",
    ),
    (
        r"\d\s*[-–—]\s*\d",
        "FAIL",
        "数字区间用连字符：`3-5 倍` 读成「三减五倍」——改写为「三到五倍」",
    ),
    (
        r"±",
        "FAIL",
        "正负号：`±3%` 读成「百分之正负三」（顺序颠倒）——改写为「正负百分之三」",
    ),
    (
        r"\d\s*[xX](?![A-Za-z])",
        "FAIL",
        "倍数用 x：`10x` 读成「十x」（裸字母）——改写为「十倍」",
    ),
    (
        r"\d{3,}\s*[A-Za-z]",
        "WARN",
        (
            "数字串+字母型号：`1080P` 读成「一千零八十P」（按基数读且裸字母）——"
            "若要逐位读需改写为「一零八零 P」"
        ),
    ),
    (
        r"≈",
        "WARN",
        "约等于号未被归一化展开（原样透传），大概率不发音——改写为「大约」",
    ),
)
READING_TRAPS_COMPILED = tuple(
    (re.compile(p), level, msg) for p, level, msg, *_ in READING_TRAPS
)

#: 汉字。整句无汉字时上游按 `use_chinese()`（front.py:106-114）逐句嗅探路由到**英文**
#: normalizer：实测 `IndexTTS 2.5`→`IndexTTS two point five`、`RTF 0.2065`→
#: `RTF oh point two oh six five`。逐字稿为字幕可读性把句子拆到 ≤43 字，反而**提高**了
#: 出现纯 ASCII 短句的概率——两个既有约束的隐性冲突，故必须成门。
HAN_RE = re.compile(r"[一-鿿]")


def check_reading_traps(items: list[dict], msgs: list[str]) -> None:
    """逐句扫描已知会被读错的写法（上游归一化的实测行为）。

    扫两个面：字幕面 `text` 与合成面（去标注后的 `ttsText`）。二者只在台本 `[say]` 改了
    标点时不同——换标点本身就能踩陷阱（`2020、2026` → `2020—2026` 读成「减」），只扫
    `text` 会漏；同一条陷阱两面都中时只报字幕面一次。
    """
    hits = 0
    for it in items:
        text = it["text"]
        synth = strip_marks(it.get("ttsText") or text)
        faces = [(text, "")] + (
            [(synth, "的合成文本（台本 [say]）")] if synth != text else []
        )
        seen: set[int] = set()
        for face, where in faces:
            for k, (pattern, level, why) in enumerate(READING_TRAPS_COMPILED):
                if k in seen or not (m := pattern.search(face)):
                    continue
                seen.add(k)
                hits += 1
                (fail if level == "FAIL" else warn)(
                    msgs, f"句 {it['id']}{where} 命中读法陷阱 {m.group(0)!r}：{why}"
                )
        if not HAN_RE.search(text):
            hits += 1
            fail(
                msgs,
                f"句 {it['id']} 整句无汉字（{text!r}）：上游按整句嗅探路由到英文归一化，"
                "数字会读成英文（`2.5`→`two point five`）——请并入相邻句或补中文",
            )
    print(f"  读法陷阱：{len(items)} 句扫描，命中 {hits} 处")


# ---------------- en 译稿门集（--lang en）----------------

#: en 译稿禁用的全角标点（逐字符判定）。只列英文确无用途的 CJK 全角形；
#: `—`（em dash）与 `…`（ellipsis）是标准英文排版字符，**刻意不禁**——zh 的
#: `——`/`……` 映射只作用于 ZH（tts_text 对非 ZH 原样透传），无混入路径；
#: 若上游实测发现新读法风险再按「先探针后成门」补录。
EN_FULLWIDTH = "（）。？！，、：；"

#: en 字幕单句字符上限。推导锚 Subtitle.tsx 两行 30px 几何：安全区行宽约
#: 1528px ÷ 平均字符宽约 15.6px ≈ 98 字符/行，两行 ≈ 196；留 fitText 收缩与
#: textWrap 平衡排版的余量取 170（实施后用 fitText 实测复核标定）。
EN_SUBTITLE_MAX_CHARS = 170

LATIN_RE = re.compile(r"[A-Za-z]")
#: 引号内夹汉字的字符串字面量（近似正则：一行内引号对之间含汉字即命中）
HAN_LITERAL_RE = re.compile(r"['\"][^'\"]*[一-鿿][^'\"]*['\"]")
#: zh 字幕单行宽度物理上限（渲染侧 SSOT = frozen 模板 Subtitle.tsx，骨架指纹把守漂移）：
#: 内容预算 CONTENT_WIDTH = 1528px（MAX_WIDTH 1600 − PADDING_X 36×2），字号下限
#: MIN_FONT_SIZE = 30px 且 zh 恒单行（twoLine 仅 en 开启）+ nowrap 不折行——CJK
#: 全角字符 advance ≈ 1.0em，故「不溢出 1920 画布」⇔ 全角当量 ≤ floor(1528/30)=50；
#: 半角按 ~0.55em 折算（模板注释记载的历史估宽口径）。en 有两行回退不受此限。
SUBTITLE_CJK_UNITS_MAX = 50
_HALFWIDTH_UNIT = 0.55


def _cjk_units(text: str) -> float:
    """全角当量：宽/全角字符计 1.0，其余（含半角与合并符）计 ~0.55。"""
    return sum(
        1.0 if unicodedata.east_asian_width(ch) in "WF" else _HALFWIDTH_UNIT
        for ch in text
    )


def check_subtitle_width(root: Path, items: list[dict], msgs: list[str]) -> None:
    """zh 字幕单行宽度门：句全角当量超渲染物理上限即 FAIL。

    历史事故两起（E3 81 字散文句两侧各溢出画布 ~255px；E2 重制评审确认构造仍在、
    当时最长 39 字不触发，复活门槛 ≈51 全角字）——frozen 模板对 zh 没有两行回退，
    稿风纪律（超宽句压短）不执法，把物理上限钉进门里而不是钉在稿风里。

    代际感知：单行前提 = 当前模板的 `twoLine = !isZh && …` 守卫。旧代 Subtitle
    的 zh 可折行（无守卫），本门对其是假阳——点名跳过，拷齐当前模板即自动生效
    （15 集实测校准：25cf 代 2 集 4 句真溢出；cacb/7faa 旧代跳过后零误报）。"""
    sub = root / "video" / "src" / "components" / "Subtitle.tsx"
    if not (sub.is_file() and "twoLine = !isZh" in sub.read_text(encoding="utf-8")):
        print(
            "  字幕宽度：本集 Subtitle 为旧代（zh 可折行）——门不适用，点名跳过（拷齐当前模板后自动生效）"
        )
        return
    hits = 0
    for it in items:
        units = _cjk_units(it["text"])
        # round 消半角 0.55 的浮点累积噪声（实测恰 50.0 当量句被 1e-14 顶过界）
        if round(units, 2) > SUBTITLE_CJK_UNITS_MAX:
            hits += 1
            fail(
                msgs,
                f"句 {it['id']} 全角当量 {units:.1f} 超字幕单行上限 "
                f"{SUBTITLE_CJK_UNITS_MAX}（zh 恒单行，30px×1528px 物理预算）"
                "——拆句或压缩该句，勿赌字号缩放",
            )
    print(f"  字幕宽度：{len(items)} 句扫描，超限 {hits} 处")


#: 已走 i18n 通道的片段（扫描前剥除，其余字面量照常判定）：带 en 属性的 <L …>
#: 标签（`<L zh=… />` 缺 en 会回落中文，不剥）；同行含 en 键时 `zh: '…'` 的值
#: （`t({zh: '…', en: '…'})` 字面对）。`<Label`/`<Loop` 等不以 `<L\s` 开头，不剥。
I18N_TAG_RE = re.compile(r"<L\s(?=[^>]*\ben\s*=)[^>]*>")
I18N_ZH_VALUE_RE = re.compile(r"""\bzh\s*:\s*(['"`])(?:\\.|(?!\1).)*\1""")
I18N_EN_KEY_RE = re.compile(r"\ben\s*:")


def strip_translated(line: str) -> str:
    """→ 剥除已翻译片段后的行（report_untranslated_scene_text 的判定面）。"""
    line = I18N_TAG_RE.sub("", line)
    return I18N_ZH_VALUE_RE.sub("", line) if I18N_EN_KEY_RE.search(line) else line


def check_translation(
    root: Path, lang: str, items: list[dict], msgs: list[str]
) -> None:
    """en 译稿门集：对齐 / 基线锁 / 文本形态 / 字幕溢出（zh 主稿为基准 SSOT）。

    文本形态三门的共同病因是上游 use_chinese() 的整句嗅探：含汉字或纯数字/符号
    的「英文句」都会被路由进中文归一化（数字读中文、标点映射错乱）。"""
    zh_json = langs.narration_json(root, langs.PRIMARY)
    if not zh_json.is_file():
        fail(
            msgs,
            f"主稿 {zh_json.name} 不存在——译稿门以主稿为对齐基准，先 build 主稿（zh）",
        )
    else:
        zh_items = json.loads(zh_json.read_text(encoding="utf-8"))
        # 对齐门：句 id 序列与幕归属逐一相等（beatWindow 按句 id 取窗的前提）
        zh_ids = [i["id"] for i in zh_items]
        en_ids = [i["id"] for i in items]
        if en_ids != zh_ids:
            zh_set, en_set = set(zh_ids), set(en_ids)
            if missing := [x for x in zh_ids if x not in en_set]:
                fail(msgs, f"译稿缺句（主稿有而译稿无）: {' '.join(missing)}")
            if extra := [x for x in en_ids if x not in zh_set]:
                fail(msgs, f"译稿多句（译稿有而主稿无）: {' '.join(extra)}")
            if set(en_ids) == zh_set:  # 集合相等而序列不同 → 纯乱序
                for k, (z, e) in enumerate(zip(zh_ids, en_ids)):
                    if z != e:
                        fail(
                            msgs,
                            f"译稿句序不一致：第 {k + 1} 句主稿为 {z}，译稿为 {e}",
                        )
                        break
        zh_scene = {i["id"]: i["scene"] for i in zh_items}
        if wrong := [
            i["id"]
            for i in items
            if i["id"] in zh_scene and i["scene"] != zh_scene[i["id"]]
        ]:
            fail(msgs, f"译稿句幕归属与主稿不一致: {' '.join(wrong)}")
        # 基线锁门：锁 = 翻译时主稿句 digest 快照，主稿改稿 ⇒ 失鲜可测
        lock_path = langs.lock(root, lang)
        if not lock_path.is_file():
            warn(
                msgs,
                f"未锁定翻译基线（缺 {lock_path.name}）——先 build --lang en 生成锁",
            )
        else:
            try:
                stale = stale_ids(read_lock(lock_path), zh_items)
            except ValueError as e:
                fail(
                    msgs,
                    f"基线锁损坏：{e}——复核译稿后 build --lang {lang} --accept all 重建",
                )
            else:
                if stale:
                    fail(
                        msgs,
                        f"基线锁失配：主稿句 {' '.join(stale)} 在锁定后被改动——"
                        f"重译这些句后重跑 build --lang {lang} 刷新锁（译文确实无需"
                        f"改动时加 --accept {','.join(stale)}）",
                    )
    # 文本形态 + 字幕溢出（不依赖主稿，逐句自判）
    n_han = n_latin = n_fw = n_over = 0
    for it in items:
        text = it["text"]
        if m := HAN_RE.search(text):
            n_han += 1
            fail(
                msgs,
                f"句 {it['id']} 含汉字 {m.group(0)!r}："
                "en 译稿不得残留中文——上游 use_chinese() 会把该句路由中文归一化",
            )
        if not LATIN_RE.search(text):
            n_latin += 1
            fail(
                msgs,
                f"句 {it['id']} 无拉丁字母（{text!r}）：纯数字/符号句同样被路由"
                "中文归一化——改写为含字母的英文句",
            )
        if hits := "".join(sorted({ch for ch in EN_FULLWIDTH if ch in text})):
            n_fw += 1
            fail(
                msgs,
                f"句 {it['id']} 含全角标点 {hits!r}：英文版用半角标点"
                "（兼防 tts_text 的全角映射混入英文）",
            )
        if len(text) > EN_SUBTITLE_MAX_CHARS:
            n_over += 1
            fail(
                msgs,
                f"句 {it['id']} 长 {len(text)} 超过 en 字幕两行容量 "
                f"{EN_SUBTITLE_MAX_CHARS}——拆句或精简",
            )
    print(
        f"  译稿文本门：{len(items)} 句扫描（汉字 {n_han} · 无拉丁 {n_latin} · "
        f"全角 {n_fw} · 超长 {n_over}）"
    )


def report_untranslated_scene_text(root: Path, msgs: list[str]) -> None:
    """en 版未翻译画面文字报告（WARN-only）：scenes/*.tsx 中未走 i18n 通道的
    含汉字字符串字面量——英文版渲染时这些字会原样显示中文。

    近似扫描（TSX 正则本质近似，同 check_scenes 的既定口径），只提醒不拦：
    逐行判定，先剥除已翻译片段（见 strip_translated）再找含汉字字面量；跨行
    书写的双语对按行各自判定。"""
    scenes_dir = root / "video" / "src" / "scenes"
    if not scenes_dir.is_dir():
        return
    hits = 0
    for tsx in sorted(scenes_dir.glob("*.tsx")):
        for lineno, line in enumerate(tsx.read_text(encoding="utf-8").splitlines(), 1):
            if HAN_LITERAL_RE.search(strip_translated(line)):
                hits += 1
                warn(
                    msgs,
                    f"{tsx.name}:{lineno} 含汉字字符串字面量——英文版画面将显示中文"
                    "（改用 <L zh=… en=…> / t({zh, en})）",
                )
    print(f"  画面 i18n 扫描：{hits} 处未翻译汉字字面量（WARN-only）")


def check_pron_marks(items: list[dict], msgs: list[str]) -> None:
    """发音标注合法性收口（build 生成期已拦，此处对 narration.json 再收口一遍；
    pron_marks.validate 的 CMU 通道对 en 标注天然可用，两语言复用同一循环）。"""
    for it in items:
        errs, _warns = validate(it.get("ttsText") or it["text"])
        if errs:
            fail(msgs, f"句 {it['id']} 发音标注非法：{errs[0]}")


#: 术语密度预算（RSI-015 ④B「密度预算」的机器面，WARN 级）：jev 集三个名词系统
#: （集中度/门槛/计费单位）全部「先用后讲」，④B 五条全检通过而普通观众仍一脸懵
#: ——每 beat 首现术语 ≤2、每幕 ≤8 是 04 规格 B 节的判据，此处做可机判的那半。
TERM_BUDGET_BEAT = 2
TERM_BUDGET_SCENE = 8
#: 拉丁字母术语 token（自动面）：英文专名/方法名（Jev、top-p、IndexTTS）。
#: 单字母（变量名 a、倍数 x）不构成术语，长度门 ≥2。近似边界（评审回归 D3-3，
#: 接受为已知近似）：数字开头的词（3D、802.11）与斜杠对（A/B）漏计；「e.g.」
#: 这类缩写按术语计入——自动面只做注意力预算，不追求词法完备。
TERM_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.-]*[A-Za-z0-9+#]|[A-Za-z]")


def check_term_density(items: list[dict], declared: list[str], msgs: list[str]) -> None:
    """首现术语密度（WARN 级）：逐 beat ≤TERM_BUDGET_BEAT、逐幕 ≤TERM_BUDGET_SCENE。

    术语 = `--terms` 显式清单（中文术语系统由 ④B 评审员圈定后声明——机器分不出
    「集中度」是不是术语，声明优于猜测）∪ 拉丁字母词自动面。声明面语义（评审
    回归 D3-1）：拉丁声明词只按**整 token** 命中（声明 AI 不得命中 OpenAI 的
    内嵌子串）；中文声明词按子串命中、与其它声明词重叠时最长优先（门槛/高门槛
    同处只计 1）——同一处文本只贡献一个首现术语。声明词全片零命中时点名 WARN
    （评审回归 D3-2）：圈词与稿子措辞失配会让该术语系统的密度门静默失效。
    「首现」按全片顺序首次出现计；beat 边界读 narration.json 的 beatStart
    （build 派生），旧版产物缺该键时 beat 级点名跳过（静默跳过的门比没有门
    更糟）、幕级照跑。
    """
    # 声明清单归一：casefold 为匹配键、保留原样显示（Jev≠jev 只在显示层）
    decl: dict[str, str] = {}
    for t in declared:
        t = t.strip()
        if t:
            decl.setdefault(t.casefold(), t)
    seen: set[str] = set()
    display: dict[str, str] = {}
    first_at: dict[str, tuple[str, str]] = {}  # 术语 → (首现句id, 幕)
    for it in items:
        cf = it["text"].casefold()
        toks = [m.group(0).casefold() for m in TERM_TOKEN_RE.finditer(it["text"])]
        found: set[str] = set()
        # 声明面：拉丁词整 token 匹配；中文词子串匹配、按位置最长优先占位
        claimed: list[tuple[int, int]] = []
        for k in sorted(decl, key=len, reverse=True):
            if TERM_TOKEN_RE.fullmatch(k):
                if k in toks:
                    found.add(k)
                continue
            start = cf.find(k)
            while start != -1:
                span = (start, start + len(k))
                if not any(s < span[1] and span[0] < e for s, e in claimed):
                    claimed.append(span)
                    found.add(k)
                    break
                start = cf.find(k, start + 1)
        # 拉丁自动面：≥2 字符整 token
        found.update(t for t in toks if len(t) >= 2)
        for t in found - seen:
            first_at[t] = (it["id"], it["scene"])
            display[t] = decl.get(t, t)
        seen |= found
    for k, shown in decl.items():
        if k in seen:
            continue
        # 被更长声明词占位命中（门槛 ⊂ 高门槛 且 高门槛 已命中）不是失配——
        # 该处文本已按最长声明计，再报「未命中」会把评审员引向错误结论
        if any(k in d for d in decl if d != k and d in seen):
            continue
        warn(
            msgs,
            f"术语密度：声明术语「{shown}」全片未命中——圈词与稿子措辞失配？"
            "（该术语系统的密度门没有测到）",
        )
    # beat 分组：幕切换或 beatStart=True 开新 beat；无 beatStart 时每个幕并为
    # 一个 beat，但该形态下 beat 级预算与幕级同源（≤2 对 ≤8 必然先红），故点名跳过
    has_beats = any(i.get("beatStart") for i in items)
    if not has_beats:
        warn(
            msgs,
            "narration.json 无 beatStart（旧版 build 产物，重跑 build 即得）——"
            "beat 级术语密度跳过，仅幕级执法",
        )
    beat_head: list[str] = []
    sid_beat: dict[str, int] = {}
    prev_scene = None
    for it in items:
        if (
            not beat_head
            or it["scene"] != prev_scene
            or (has_beats and it.get("beatStart"))
        ):
            beat_head.append(it["id"])
        sid_beat[it["id"]] = len(beat_head) - 1
        prev_scene = it["scene"]
    beat_terms: dict[int, list[str]] = {}
    scene_terms: dict[str, list[str]] = {}
    for t, (sid, scene) in first_at.items():
        if (b := sid_beat.get(sid)) is not None:
            beat_terms.setdefault(b, []).append(t)
        scene_terms.setdefault(scene, []).append(t)
    if has_beats:
        for b, terms in sorted(beat_terms.items()):
            if len(terms) > TERM_BUDGET_BEAT:
                warn(
                    msgs,
                    f"术语密度：beat {beat_head[b]} 首现术语 {len(terms)} 个"
                    f"（预算 ≤{TERM_BUDGET_BEAT}）：{'、'.join(sorted(display[t] for t in terms))}"
                    "——拆 beat 或用白话替代消术语",
                )
    for scene, terms in sorted(scene_terms.items()):
        if len(terms) > TERM_BUDGET_SCENE:
            warn(
                msgs,
                f"术语密度：幕 {scene} 首现术语 {len(terms)} 个"
                f"（预算 ≤{TERM_BUDGET_SCENE}）：{'、'.join(sorted(display[t] for t in terms))}",
            )
    print(
        f"  术语密度：首现 {len(first_at)} 个术语 · beat {len(beat_head)} 段 · "
        f"幕 {len(scene_terms)} 处（beat ≤{TERM_BUDGET_BEAT} · 幕 ≤{TERM_BUDGET_SCENE}）"
    )


def check_fade_invariant(root: Path, msgs: list[str]) -> None:
    c = load_constants(root)
    budget = c["sentenceGapSec"] + c["sceneGapSec"]
    if 2 * c["sceneCrossFadeSec"] > budget:
        fail(
            msgs,
            f"2×sceneCrossFadeSec({c['sceneCrossFadeSec']}) > 幕间静默预算({budget:.2f}s)"
            " —— 淡入淡出会吃进句子音频，SceneFade 时间轴零位移前提被破坏",
        )


#: 画面文字 ↔ 口播逐字重合判定的归一化：NFKC 折叠全角后只留字母数字与汉字
#: （Unicode \w 去下划线）——「选项之间会互相影响」与「选项之间，会互相影响。」同源。
_DUP_DROP_RE = re.compile(r"[\W_]+")
#: TSX 里可能上屏的字面量：引号 / 反引号字符串与同行 JSX 标签间文本。引号左起
#: 成对、不设长度下限——设下限会让 `at('p0-01')` 的闭引号与正文开引号错配而吞掉
#: 同行正文；长度门在归一化后判。
_SCENE_TEXT_RE = re.compile(
    r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`((?:[^`\\\n]|\\.)*)`"
    r"|>([^<>{}\n]+)<"
)
#: 整行裸文本：JSX 文本独占一行（标签各占一行）是场景代码的主流写法，逐行扫描
#: 时它不带任何定界符；相邻的裸文本行是同一文本节点的续写，拼接后另判一次。
_SCENE_BARE_LINE_RE = re.compile(r"^\s*([^<>{}'\"`=;()\n]+?)\s*$")
#: 独占一行的 `<br />`：段内换行，不打断续写段。
_SCENE_BR_RE = re.compile(r"^\s*<br\s*/?>\s*$")
#: 注释行不上屏（场景作者常在注释里引口播标注镜头）。
_SCENE_COMMENT_RE = re.compile(r"^\s*(?://|/\*|\*|\{/\*)")
#: 场景文件名的幕前缀：P0Cost.tsx → P0。
_SCENE_FILE_RE = re.compile(r"^(P\d+)")
#: 逐处豁免：命中行或其上一行注 `caption-dup-ok: <理由>`（理由必填）→ 降为 WARN
#: 留痕。逃逸口必须存在且必须被记录（同骨架漂移登记 [[skeleton.drift]] 立场）。
_DUP_OK_RE = re.compile(r"caption-dup-ok[:：](.*)$")
#: 「部分覆盖 / 整句包含」判据的最短长度——短字面量作为子串天然会撞进长句（标签、
#: 单词级锚点），短句也天然会落进长字面量，不设门会误伤。
DUP_MIN_CHARS = 10
#: 「整句相等」判据的最短长度，远低于上者（短句照抄同样是两层重复）；只防单字/
#: 双字字面量（「是」「对」）与极短口播句误配。
DUP_EXACT_MIN_CHARS = 4
#: 字面量覆盖口播句的比例达到此值即视为「整句复述」（截掉句首连接词的复述照样拦）。
DUP_MIN_COVERAGE = 0.7


def _dup_norm(s: str) -> str:
    return _DUP_DROP_RE.sub("", unicodedata.normalize("NFKC", s)).casefold()


def _scene_candidates(lines: list[str]) -> list[tuple[tuple[int, ...], str]]:
    """→ [(所跨行号, 候选文字)]：逐行字面量，外加相邻裸文本行的拼接段。"""
    out: list[tuple[tuple[int, ...], str]] = []
    run: list[tuple[int, str]] = []

    def flush() -> None:
        if len(run) > 1:
            out.append((tuple(n for n, _ in run), "".join(t for _, t in run)))
        run.clear()

    for lineno, line in enumerate(lines, 1):
        if _SCENE_COMMENT_RE.match(line):
            flush()
            continue
        if _SCENE_BR_RE.match(line):
            continue
        for gs in _SCENE_TEXT_RE.findall(line):
            out.append(((lineno,), next((g for g in gs if g), "")))
        if m := _SCENE_BARE_LINE_RE.match(line):
            out.append(((lineno,), m.group(1)))
            run.append((lineno, m.group(1)))
        else:
            flush()
    flush()
    return out


def _dup_ok_reason(line: str) -> str:
    """→ 该行 `caption-dup-ok:` 标记的理由（剥注释闭合符）；无标记或理由为空 → ""。"""
    m = _DUP_OK_RE.search(line)
    return re.sub(r"\*/\}?\s*$", "", m.group(1)).strip() if m else ""


def _dup_hit(n: str, pool: list[tuple[str, str]]) -> str | None:
    """→ 被复述的句 id；None = 未命中。判据见 check_caption_duplication。"""
    if len(n) < DUP_EXACT_MIN_CHARS:
        return None
    for sid, s in pool:
        if (
            n == s
            or (
                len(n) >= DUP_MIN_CHARS
                and n in s
                and len(n) >= DUP_MIN_COVERAGE * len(s)
            )
            or (len(s) >= DUP_MIN_CHARS and s in n)
        ):
            return sid
    return None


def check_caption_duplication(root: Path, items: list[dict], msgs: list[str]) -> None:
    """画面文字逐字复述口播 → FAIL（烧录字幕已逐句上屏，同屏两层相同文字）。

    Subtitle 是 frozen 全片 overlay，每句口播必然出现在底部字幕带；场景里再放
    一张与该句逐字相同的文字卡（金句卡 / 清单条 / 判词条），观众看到的就是上下
    两层同一句话。画面文字的职责是补充字幕给不了的信息（数字、标签、关键词、
    结构），不是复述。

    判据（归一化后任一即 FAIL）：整句相等（≥DUP_EXACT_MIN_CHARS 字，短句照抄同样
    拦）；字面量 ≥DUP_MIN_CHARS 字且是覆盖该句 ≥DUP_MIN_COVERAGE 的子串（截掉句首
    「所以」的复述照样拦，「选项之间 ⇄ 互相牵动」这类关键词锚点不误伤）；该句
    ≥DUP_MIN_CHARS 字且整句落在字面量内（加前缀标签、两句并一卡）。口播侧取
    items 的 text——即本语言字幕所显示的文本，发音标注 build 期已剥；zh / en
    各查各的字幕面（en 版画面上的 `<L en>` 同样会与英文字幕叠层）。

    近似扫描（TSX 正则本质近似，同 check_scenes 的既定口径）：逐行判定，相邻
    裸文本行（JSX 同一文本节点的续写，`<br />` 不断段）拼接后另判；注释行跳过；
    Pn 前缀的场景文件只比本幕句子（字幕只在该句播出时上屏，别幕回扣同句不构成
    同屏两层），其余文件比全片。同幕跨镜回扣、章节标题卡等刻意复述，在命中行或
    上一行注 `caption-dup-ok: <理由>` 豁免，降为 WARN 留痕。
    """
    scenes_dir = root / "video" / "src" / "scenes"
    if not scenes_dir.is_dir():
        return
    sents = [(it["id"], it["scene"], _dup_norm(it["text"])) for it in items]
    for tsx in sorted(scenes_dir.glob("*.tsx")):
        m = _SCENE_FILE_RE.match(tsx.name)
        pool = [(i, s) for i, sc, s in sents if s and m and sc == m.group(1)] or [
            (i, s) for i, _sc, s in sents if s
        ]
        lines = tsx.read_text(encoding="utf-8").splitlines()
        seen: dict[str, list[set[int]]] = {}  # 句 id → 已报命中所跨行（拼接段去重）
        for span, lit in _scene_candidates(lines):
            sid = _dup_hit(_dup_norm(lit), pool)
            if sid is None or any(prev & set(span) for prev in seen.get(sid, [])):
                continue
            seen.setdefault(sid, []).append(set(span))
            head = span[0]
            ok = next(
                (
                    r
                    for ln in (head, head - 1)
                    if ln >= 1 and (r := _dup_ok_reason(lines[ln - 1]))
                ),
                "",
            )
            where = f"{tsx.name}:{head} "
            if ok:
                warn(
                    msgs, f"{where}画面文字复述口播 {sid}（caption-dup-ok 豁免：{ok}）"
                )
                continue
            fail(
                msgs,
                f"{where}画面文字逐字复述口播 {sid}「{lit.strip()[:24]}」——字幕已烧录"
                "同句，同屏两层重复；画面文字改为关键词/数字/标签锚点（刻意为之则注 "
                "caption-dup-ok: <理由>）",
            )


def check_scenes(
    root: Path,
    beats: list[tuple[str, str, str, str]],
    msgs: list[str],
    known_ids: set[str] | None = None,
) -> None:
    scenes_dir = root / "video" / "src" / "scenes"
    if not scenes_dir.is_dir():
        return
    code_pairs: set[tuple[str, str]] = set()
    anchor_ids: set[str] = set()
    for tsx in sorted(scenes_dir.glob("*.tsx")):
        src = tsx.read_text(encoding="utf-8")
        for m in SCENE_CALL_RE.finditer(src):
            left, right = m.group(1), m.group(2) or m.group(1)
            code_pairs.add((left, right))
        anchor_ids.update(m.group(1) for m in SCENE_ANCHOR_RE.finditer(src))
    # ISSUE-190 防 5：at()/dur() 引用的句 id 必须真实存在（known_ids 来自
    # narration.json；缺 narration 时跳过——build 先于场景撰写是常态时序）。
    if known_ids:
        for sid in sorted(anchor_ids - known_ids):
            fail(
                msgs,
                f"场景代码 at()/dur() 引用了不存在的句 id {sid}"
                "（跳号/改名残留，渲染期才抛——ISSUE-190）",
            )
    board_pairs = {(left, right) for _, left, right, _ in beats}
    for pair in sorted(board_pairs - code_pairs):
        warn(
            msgs,
            f"分镜区间 {pair[0]}..{pair[1]} 未在场景代码中找到对应 beatWindow/w 调用",
        )
    for pair in sorted(code_pairs - board_pairs):
        warn(msgs, f"场景代码区间 {pair[0]}..{pair[1]} 未在分镜表中登记（分镜陈旧）")


#: 动效列的结构化标注：`@enter:fall` / `@stagger` / `@accelTravel` …
MOTION_TAG_RE = re.compile(r"@([A-Za-z][A-Za-z0-9]*)")


def parse_motion_tags(board: Path) -> list[tuple[str, str]]:
    """返回 [(镜号, 动词)]。动效列 = 表格行第 4 单元格（| 镜 | 句区间 | 画面 | 动效 |）。"""
    tags: list[tuple[str, str]] = []
    for raw in board.read_text(encoding="utf-8").splitlines():
        if not raw.startswith("|") or "---" in raw:
            continue
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        if len(cells) < 4 or not re.match(r"^\d+-[A-Z]\d*$", cells[0]):
            continue
        for m in MOTION_TAG_RE.finditer(cells[3]):
            tags.append((cells[0], m.group(1)))
    return tags


def check_motion(root: Path, msgs: list[str]) -> None:
    """@动词 标注 ↔ 场景代码运动模型调用互比（WARN-only）。

    动词表从本集 video/src/motion/hooks.ts 派生（use 词首字母小写化），
    不在本文件复制第二份——hooks.ts 加模型，这里自动跟随。
    """
    board = root / "script" / "storyboard.md"
    hooks_ts = root / "video" / "src" / "motion" / "hooks.ts"
    if not hooks_ts.is_file():
        return  # 运动层未铺设的集（如已冻结的旧集）——此门静默不适用
    verbs = {
        m.group(1)[0].lower() + m.group(1)[1:]
        for m in re.finditer(
            r"export (?:async )?function use(\w+)", hooks_ts.read_text(encoding="utf-8")
        )
    }
    # 场景文件 → 该文件调用的运动模型（import 来源限定 ../motion，防同名误配）
    scenes_dir = root / "video" / "src" / "scenes"
    per_file: dict[str, set[str]] = {}
    for tsx in sorted(scenes_dir.glob("*.tsx")):
        src = tsx.read_text(encoding="utf-8")
        used = set()
        if re.search(r"from ['\"]\.\./motion['\"]", src):
            for m in re.finditer(r"\buse([A-Z][A-Za-z0-9]*)\s*\(", src):
                v = m.group(1)[0].lower() + m.group(1)[1:]
                if v in verbs:
                    used.add(v)
        per_file[tsx.name] = used
    # beat 镜号数字前缀 → 幕场景文件（0-A → P0*.tsx）
    for beat, verb in parse_motion_tags(board):
        if verb not in verbs:
            warn(msgs, f"镜 {beat}：@{verb} 不在运动模型词表（hooks.ts 派生；拼写？）")
            continue
        scene_pref = f"P{beat.split('-')[0]}"
        owners = [n for n in per_file if n.startswith(scene_pref)]
        if not owners or not any(verb in per_file[n] for n in owners):
            warn(msgs, f"镜 {beat}：分镜声明 @{verb}，但 {scene_pref} 场景代码未调用")


def main() -> None:
    ap = argparse.ArgumentParser(description="④⑥ 内容门：覆盖性/预算/淡入不变式")
    ap.add_argument("--project", default=".", help="视频工程根目录")
    ap.add_argument(
        "--lang",
        default=langs.PRIMARY,
        help="受检语言：zh 主稿（缺省）| en 译稿（门集见 check_translation）",
    )
    ap.add_argument(
        "--check-scenes",
        action="store_true",
        help="附:分镜↔场景代码 beat 互比（WARN）+ at()/dur() 句 id 存在性（FAIL）；"
        "--lang en 时改为未翻译画面文字报告（复述口播门缺省执法，不依赖本 flag）",
    )
    ap.add_argument(
        "--check-motion",
        action="store_true",
        help="附:分镜动效列 @动词 标注 ↔ 场景代码运动模型互比（WARN-only）",
    )
    ap.add_argument(
        "--pre-tts",
        action="store_true",
        help="TTS 前置门：只跑不需要分镜的检查（预算/读法陷阱/标注合法性/zh 字幕宽度），"
        "storyboard.md 缺失时照常完成（两遍法草稿遍场景）",
    )
    ap.add_argument(
        "--pron-candidates",
        action="store_true",
        help="报告（非门）：列出命中多音字候选表的句子，供复听时重点关注；退出码恒 0",
    )
    ap.add_argument(
        "--pron-gate",
        action="store_true",
        help="门（RSI-014）：候选报告之上，语义规则命中（字典级确定读音，如 每行→HANG2）"
        "而句中该 occurrence 无任何标注时 FAIL；已标注视为作者显式接管不拦",
    )
    ap.add_argument(
        "--term-density",
        action="store_true",
        help="附（WARN，RSI-015）：逐 beat 首现术语 ≤2、逐幕 ≤8 的密度预算；"
        "中文术语经 --terms 声明，拉丁字母词自动计入",
    )
    ap.add_argument(
        "--terms",
        default="",
        help="--term-density 的显式术语清单（逗号分隔，如「集中度,门槛,计费单位」）；"
        "由 ④B 评审员圈定后喂入",
    )
    ap.add_argument(
        "--json", action="store_true", help="以 JSON 输出结果（供 pipeline.py 汇总）"
    )
    args = ap.parse_args()
    try:
        lang = langs.validate(args.lang)
    except ValueError as e:
        ap.error(str(e))
    pron_face = args.pron_candidates or args.pron_gate
    if args.pre_tts and pron_face:
        ap.error(
            "--pre-tts 是内容门、--pron-candidates/--pron-gate 是发音候选面，两者互斥"
        )
    if pron_face and args.term_density:
        ap.error("--term-density 与 --pron-candidates/--pron-gate 互斥")
    if args.terms and not args.term_density:
        ap.error("--terms 只与 --term-density 同用")
    # 报错按实际触发的 flag 点名——用户只传 --pron-candidates 时报
    # --pron-gate/--term-density 是指向不存在的误用（评审回归 D5-4）
    zh_only = [
        name
        for name, on in (
            ("--pron-candidates", args.pron_candidates),
            ("--pron-gate", args.pron_gate),
            ("--term-density", args.term_density),
        )
        if on
    ]
    if zh_only and lang != langs.PRIMARY:
        ap.error(f"{'/'.join(zh_only)} 仅对主稿（zh）有意义")
    if pron_face and (args.json or args.check_scenes or args.check_motion):
        # 静默丢弃比报错更糟：CI 传了 --check-scenes 却以为两项都跑了（评审
        # 回归 D2-2）；--json 的机读面只存在于内容门路径
        ap.error(
            "--json/--check-scenes/--check-motion 属内容门面，"
            "与 --pron-candidates/--pron-gate 互斥"
        )

    root = Path(args.project).resolve()
    # required=False：内容门在没有 pipeline.toml 时仍应能跑（如新集脚手架期）。
    # 但受影响的门必须点名 WARN（见 check_budget）——静默跳过的门是 config.py
    # 存在的首要原因。schema/默认值与 pipeline.py 共用同一事实源。
    cfg, _origin, cfg_fails, cfg_warns = config.load(
        root, required=False, scope={"narration"}
    )
    items = json.loads(langs.narration_json(root, lang).read_text(encoding="utf-8"))

    if pron_face:
        # 「已标注 = 作者显式接管」只对合法标注成立：非法标注（拼音无声调/
        # 未成对尖括号）是必然读错，比门要拦的漏标更严重，先于语义判定收口
        # （评审回归 D2-1）。报告面按「退出码恒 0」契约只点名不判死。
        illegal = []
        for it in items:
            errs, _warns = validate(it.get("ttsText") or it["text"])
            if errs:
                illegal.append((it["id"], errs[0]))
        hits = scan_candidates(items)
        print(f">> 多音字候选 · {root.name} · {len(items)} 句（候选 ≠ 台账，非门）")
        for sid, char, risk, advice in hits:
            print(f"  {sid}  {char}  {risk}  → 若听出错读：{advice}")
        missing = semantic_missing(items)
        if missing:
            print(
                f">> 语义规则命中而未标注 {len(missing)} 处"
                "（字典级确定读音，写稿阶段就该标注——RSI-014）"
            )
            for sid, char, reading, mark, ctx in missing:
                print(f"  {sid}  {char} → {reading}（{ctx}）  建议标注 {mark}")
        tail = f">> 候选命中 {len(hits)} 处 · 语义规则未标注 {len(missing)} 处"
        if args.pron_gate:
            for sid, err in illegal:
                print(f"  FAIL 句 {sid} 发音标注非法：{err}")
            for sid, char, reading, mark, ctx in missing:
                print(
                    f"  FAIL 句 {sid} 高危多音字 {char!r} 语境「{ctx}」应读 {reading} "
                    f"而句中无标注：加 {mark}（语义规则命中即建议标注，RSI-014）"
                )
            print(tail + "（--pron-gate 门）")
            sys.exit(1 if (missing or illegal) else 0)
        for sid, err in illegal:
            print(
                f"  ⚠ 句 {sid} 发音标注非法：{err}"
                "（本面退出码恒 0，合法性执法在 --pre-tts 面）"
            )
        print(tail + "（语义规则命中处写稿即标注；其余候选确认读错才写台账）")
        return

    board = root / "script" / "storyboard.md"
    # storyboard 只在主稿完整门被消费；en 门集与 --pre-tts 均不要求分镜存在
    if not args.pre_tts and lang == langs.PRIMARY and not board.is_file():
        sys.exit(f"storyboard.md 不存在: {board}")

    msgs: list[str] = []
    for f in cfg_fails:
        fail(msgs, f"配置：{f}")
    for w in cfg_warns:
        warn(msgs, f"配置：{w}")
    if args.pre_tts:
        # 两遍法草稿遍的形态：稿已定、分镜未写。只跑「文本自身」可判定的门——
        # 分镜覆盖性/淡入不变式/场景互比都依赖 storyboard 或 timing 常数随分镜
        # 联动，此时跳过并**点名**（静默跳过的门比没有门更糟）。
        print(
            f">> pre-TTS 前置门 · {root.name} · {len(items)} 句（分镜未写，跳过覆盖性/淡入/场景互比）"
        )
        if lang != langs.PRIMARY:
            check_translation(root, lang, items, msgs)
        check_budget(root, items, cfg, msgs, lang)
        if lang == langs.PRIMARY:
            check_reading_traps(items, msgs)
            check_subtitle_width(root, items, msgs)
        check_pron_marks(items, msgs)
        if args.term_density:
            check_term_density(items, args.terms.split(","), msgs)
    elif lang != langs.PRIMARY:
        # en 完整门：语言无关门（覆盖/淡入/场景互比/动效互比）只在主稿执法——
        # 分镜与场景代码是 zh 主稿的派生物，en 按句 id 复用，重复执法只会双报
        # 同源错。跳过必须说出来，不能静默。
        print("  语言无关门（覆盖性/淡入/场景互比/动效互比）在主稿执法——en 模式跳过")
        check_translation(root, lang, items, msgs)
        check_budget(root, items, cfg, msgs, lang)
        check_pron_marks(items, msgs)
        check_caption_duplication(root, items, msgs)
        if args.check_scenes:
            report_untranslated_scene_text(root, msgs)
    else:
        beats = parse_storyboard(board)
        if not beats:
            fail(msgs, f"未能从 {board.name} 解析出任何 beat 行（格式变化？）")
        check_coverage(items, beats, msgs)
        check_budget(root, items, cfg, msgs)
        check_reading_traps(items, msgs)
        check_subtitle_width(root, items, msgs)
        check_fade_invariant(root, msgs)
        check_caption_duplication(root, items, msgs)
        if args.term_density:
            check_term_density(items, args.terms.split(","), msgs)
        if args.check_scenes:
            check_scenes(root, beats, msgs, known_ids={i["id"] for i in items})
        if args.check_motion:
            check_motion(root, msgs)

    fails = [m for m in msgs if m.startswith("FAIL")]
    warns = [m for m in msgs if m.startswith("WARN")]
    if args.json:
        print(
            json.dumps({"fails": fails, "warns": warns}, ensure_ascii=False, indent=1)
        )
    else:
        if lang != langs.PRIMARY:
            print(f">> 内容门 · {root.name} · {len(items)} 句 · lang=en")
        else:
            n_beats = "—" if args.pre_tts else len(beats)
            print(f">> 内容门 · {root.name} · {len(items)} 句 / {n_beats} 镜")
        for m in msgs:
            print(f"  {m}")
        print(f">> FAIL {len(fails)} · WARN {len(warns)}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
