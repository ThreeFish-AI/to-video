#!/usr/bin/env python3
"""④⑤ 内容门：分镜覆盖性、时长预算、淡入不变式——公共管线版本。

机械化三件此前靠人眼/散文守着的事：
  1. storyboard 的 beat 句 id 区间必须**覆盖**本幕每一句（无缺句），重叠仅允许
     「标题卡/章头压前句尾」的刻意惯例（该 beat 的句区间单元格以「尾」结尾标注）；
  2. 时长预算：narration.json 字数估算与 manifest 实测（若已合成）两个口径都对
     pipeline.toml 的 target_minutes 负责——首次把「策划宣称/估算/实测」三处接上；
  3. 幕间呼吸淡入淡出的不变式：2×sceneCrossFadeSec ≤ sentenceGap+sceneGap
    （淡入淡出必须花在既有静默里，时间轴零位移的前提）；
  4. 读法陷阱：上游中文归一化实测会读错的写法（4 位年份带空格、三段版本号、
     数字区间连字符、±、10x、整句无汉字…）——见 READING_TRAPS，每条都附实测输出。

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
生成期拦非法标注，此处对 narration.json 再收口一遍）。两遍法草稿遍（A 遍）写完
稿就要排配音、storyboard.md 尚未写——本模式在 storyboard.md 缺失时照常完成并
以 0 退出；storyboard 相关的覆盖性/淡入/场景互比在此模式下一律跳过。

可选 --pron-candidates（报告，非门）：逐句列出命中多音字候选表的句子
（候选表见 pron_marks.POLYPHONE_CANDIDATES；与 --pre-tts 互斥——一个是门、
一个是注意力清单，混跑会让退出码语义含混）。退出码恒 0。

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
from pron_marks import scan_candidates, validate  # noqa: E402
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
    估算 = 词数 ÷ words_per_min；实测读 audio/en/manifest.json。"""
    narr = config.for_lang(cfg, lang).get("narration", {})
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
        c = load_constants(root)
        m_items = json.loads(manifest.read_text(encoding="utf-8"))
        real_min = total_duration_in_frames(m_items, c) / c["fps"] / 60
        print(
            f"  实测口径：manifest {len(m_items)} 句，含时距总长 = {real_min:.1f} 分钟"
        )
        if not lo <= real_min <= hi:
            fail(msgs, f"实测时长 {real_min:.1f} 分超预算 [{lo}, {hi}]")
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
    """逐句扫描已知会被读错的写法（上游归一化的实测行为）。"""
    hits = 0
    for it in items:
        text = it["text"]
        for pattern, level, why in READING_TRAPS_COMPILED:
            if m := pattern.search(text):
                hits += 1
                (fail if level == "FAIL" else warn)(
                    msgs, f"句 {it['id']} 命中读法陷阱 {m.group(0)!r}：{why}"
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
    ap = argparse.ArgumentParser(description="④⑤ 内容门：覆盖性/预算/淡入不变式")
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
        help="TTS 前置门：只跑不需要分镜的检查（预算/读法陷阱/标注合法性），"
        "storyboard.md 缺失时照常完成（两遍法草稿遍场景）",
    )
    ap.add_argument(
        "--pron-candidates",
        action="store_true",
        help="报告（非门）：列出命中多音字候选表的句子，供复听时重点关注；退出码恒 0",
    )
    ap.add_argument(
        "--json", action="store_true", help="以 JSON 输出结果（供 pipeline.py 汇总）"
    )
    args = ap.parse_args()
    if args.pre_tts and args.pron_candidates:
        ap.error("--pre-tts 是门、--pron-candidates 是报告，两者互斥")
    try:
        lang = langs.validate(args.lang)
    except ValueError as e:
        ap.error(str(e))

    root = Path(args.project).resolve()
    # required=False：内容门在没有 pipeline.toml 时仍应能跑（如新集脚手架期）。
    # 但受影响的门必须点名 WARN（见 check_budget）——静默跳过的门是 config.py
    # 存在的首要原因。schema/默认值与 pipeline.py 共用同一事实源。
    cfg, _origin, cfg_fails, cfg_warns = config.load(
        root, required=False, scope={"narration"}
    )
    items = json.loads(langs.narration_json(root, lang).read_text(encoding="utf-8"))

    if args.pron_candidates:
        hits = scan_candidates(items)
        print(f">> 多音字候选 · {root.name} · {len(items)} 句（候选 ≠ 台账，非门）")
        for sid, char, risk, advice in hits:
            print(f"  {sid}  {char}  {risk}  → 若听出错读：{advice}")
        print(f">> 候选命中 {len(hits)} 处（确认读错才写台账，不要预防性标注）")
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
        check_pron_marks(items, msgs)
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
        check_fade_invariant(root, msgs)
        check_caption_duplication(root, items, msgs)
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
