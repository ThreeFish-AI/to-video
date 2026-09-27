#!/usr/bin/env python3
"""发音控制标记 `<原文|读音>` 的解析与校验——公共管线单一事实源。

IndexTTS-2.5 支持在文本里内联标注读音，用于**多音字**与**英文专名**的精确控制：

    他在银<行|HANG2>里<行|XING2>走。      拼音通道（标记左侧含汉字）
    <Claude|K L AO1 D> 能做到。            CMU 音素通道（标记左侧纯 ASCII）

上游实现（`~/tools/index-tts/indextts/infer_v2_5.py`，HEAD 4f8792f）：
  - 正则 `:38` = ``<([^|>\\n]+)\\|([^>\\n]+)>``，替换函数 `:52-72`，唯一调用点 `:714`；
  - 通道由**标记左侧是否含汉字**二分（含汉字→SPECIAL_TOKEN_2 拼音；纯 ASCII→SPECIAL_TOKEN_1
    音素），**与 `lang` 参数无关**；读音内容被强制 `upper()`；
  - 标记天然**免疫**中文文本归一化（`utils/front.py:143-171` 先换成纯字母占位符、`:220` 还原），
    故不需要为保标记而关 `text_normalization`；
  - 切段时作为原子块不可切断（`:410`），单条标记仅 +4~6 token，本管线单句远未触及段预算。

三个**必须由本模块拦住**的失效模式（全部实测确认）：
  1. 上游正则的 group(1) 字符类 `[^|>\\n]+` **允许 `<`**，故正文里孤立的 `<`（如 `延迟<10ms`）
     会与后面的标记粘连、**吞掉两者之间的全部文字**，且吞掉的是正文、事后极难发现；
  2. 替换是整体 `re.sub`，`match.group(1)`（原字）被**完全丢弃** —— 标注错 = 必然读错，
     没有字形兜底；
  3. `checkpoints/pinyin.vocab` 在**运行时从未被任何代码读取**（全仓 grep 仅命中 README/docs），
     非法拼音 100% 静默通过。

拼音拼写规则（对 `checkpoints/pinyin.vocab` 1728 条逐条统计得出，2026-08-20 实测）：
  - 全大写、无分隔符、必须带声调数字 1–5，100% 匹配 ``^[A-Z]+[1-5]$``；
  - 轻声用 5（394 条，是最大的一类）；
  - ü 一律写 **V** 且仅出现在 J/Q/X/L/N 声母后（65 条）。**``^[JQX]U`` 零命中** ——
    居/去/须 必须写 JV1/QV4/XV1，写成 JU1/QU4/XU1 即非法；
    L/N 两种都合法且语义不同（LU=卢、LV=吕；NU=奴、NV=女）；
    Y 声母保持 U 写法（YU/YUAN/YUE/YUN）；
  - 儿化没有独立标记：只有 ER2/ER3/ER4/ER5（无 ER1，无独立 R）；
  - vocab **不是声韵调全叉积**，存在合法音节缺格（ANG3/ER1/KEI1 均不在表内），故
    「不在 vocab」只作 WARN（大概率读错，需试听），不作 ERROR。

用法：本模块只做纯函数，无 IO、无依赖。`build_narration.py` 在生成 narration.json 时调用
`validate()` 硬失败；`check_script.py` 在内容门里复用同一套规则。
"""

from __future__ import annotations

import re

#: **本 skill 的严格版**解析正则：与上游语义一致，但字符类额外禁掉 `<` `>` `|`。
#: 上游那版允许 group(1) 含 `<`，正是「孤立 < 吞正文」的成因；我们用严格版解析，
#: 再把「上游会匹配而严格版不匹配」的残留 `<`/`>` 报成 ERROR，从而把该 bug 前移到 lint。
PRON_MARK_RE = re.compile(r"<([^|<>\n]+)\|([^|<>\n]+)>")

#: 单个拼音音节：全大写字母 + 声调 1–5
PINYIN_SYLLABLE_RE = re.compile(r"^[A-Z]+[1-5]$")

#: jqx + ü 必须写 V（vocab 中 ^[JQX]U 零命中）
PINYIN_JQXU_RE = re.compile(r"^[JQX]U")

#: 汉字（用于判定走哪个通道——与上游 `:66` 的判据一致）
HAN_RE = re.compile(r"[一-鿿]")

#: ARPAbet 音素集（CMU 词典 39 音素），元音可带重音数字 0/1/2
_ARPABET = (
    "AA AE AH AO AW AY B CH D DH EH ER EY F G HH IH IY JH K "
    "L M N NG OW OY P R S SH T TH UH UW V W Y Z ZH"
)
CMU_PHONEMES = frozenset(_ARPABET.split())
CMU_TOKEN_RE = re.compile(r"^([A-Z]{1,2}|NG|CH|DH|HH|JH|SH|TH|ZH)([012])?$")


def has_marks(text: str) -> bool:
    """文本中是否含（严格版可识别的）发音标注。"""
    return bool(PRON_MARK_RE.search(text))


def strip_marks(text: str) -> str:
    """`他在银<行|HANG2>里走。` → `他在银行里走。`

    标记本身携带原字（group(1)），故剥离即可还原**人读文本**——无需在逐字稿里
    重复书写两份，也就不存在两份漂移的风险。这正是 narration.json 里
    `text`（人读/字幕/字数预算）与 `ttsText`（送合成）能共用一个书写面的原因。
    """
    return PRON_MARK_RE.sub(lambda m: m.group(1), text)


def _check_pinyin(reading: str) -> list[str]:
    """拼音通道校验 → ERROR 消息列表（空 = 通过）。"""
    errs: list[str] = []
    syllables = reading.split()
    if not syllables:
        return ["拼音标注为空"]
    for syl in syllables:
        if not PINYIN_SYLLABLE_RE.match(syl):
            errs.append(
                f"拼音音节 {syl!r} 非法：须全大写字母 + 声调 1–5（轻声用 5），如 HANG2"
            )
        elif PINYIN_JQXU_RE.match(syl):
            errs.append(
                f"拼音音节 {syl!r} 非法：j/q/x + ü 必须写 V 而非 U"
                f"（如 居=JV1、去=QV4、须=XV1）"
            )
    return errs


def _check_cmu(reading: str) -> list[str]:
    """CMU 音素通道校验 → ERROR 消息列表（空 = 通过）。"""
    errs: list[str] = []
    # 官方示例用 ` . ` 分音节（`<going|G OW1 . IH0 NG>`），点号在此仅作分隔、不是音素
    tokens = [t for t in reading.replace(".", " ").split() if t]
    if not tokens:
        return ["音素标注为空"]
    for tok in tokens:
        m = CMU_TOKEN_RE.match(tok)
        if not m or m.group(1) not in CMU_PHONEMES:
            errs.append(
                f"音素 {tok!r} 不在 ARPAbet 集合内（元音可带重音 0/1/2），如 K L AO1 D"
            )
    return errs


def validate(
    text: str, vocab: frozenset[str] | None = None
) -> tuple[list[str], list[str]]:
    """校验一句文本里的全部发音标注 → (errors, warnings)。

    vocab：可选的合法拼音音节集合（`checkpoints/pinyin.vocab` 内容）。该文件在
    index-tts checkout 里、**不在本 skill**，故缺失时只跳过「是否在表内」这一项 WARN，
    格式类 ERROR 始终生效（规则已内联在本模块，不依赖外部文件）。
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 先剥掉所有合法标记，残留的 `<` / `>` 即结构风险（含上游「孤立 < 吞正文」那一类）
    residue = PRON_MARK_RE.sub("", text)
    if "<" in residue or ">" in residue:
        errors.append(
            "正文含未成对的 `<` 或 `>`：上游解析正则允许 group(1) 内含 `<`，"
            "孤立的 `<` 会与后面的标记粘连并**吞掉之间的全部正文**"
            "（如 `延迟<10ms` + 同句标记）。请改写为「小于」「大于」等文字"
        )
    if "|" in residue:
        errors.append("正文含孤立 `|`：会与相邻 `<`/`>` 组成意外标记，请去掉")

    for m in PRON_MARK_RE.finditer(text):
        word, reading = m.group(1), m.group(2)
        mark = m.group(0)
        if reading != reading.strip():
            warnings.append(f"{mark}：读音首尾有空格（上游会 upper() 但不 strip）")
        if reading != reading.upper():
            errors.append(
                f"{mark}：读音须全大写（上游 `:65` 会强制 upper()，但小写写法易与"
                f"「裸内联拼音」混淆——后者在 v2.5 会被全局 lower() 打回小写、训练形态不同）"
            )
            continue
        if HAN_RE.search(word):
            errors.extend(f"{mark}：{e}" for e in _check_pinyin(reading))
            if vocab:
                for syl in reading.split():
                    if PINYIN_SYLLABLE_RE.match(syl) and syl not in vocab:
                        warnings.append(
                            f"{mark}：音节 {syl} 不在 pinyin.vocab（1728 条）内 —— "
                            f"vocab 存在合法缺格（如 ANG3/ER1），故仅告警，但请务必试听确认"
                        )
        else:
            errors.extend(f"{mark}：{e}" for e in _check_cmu(reading))

    return errors, warnings


def load_vocab(path) -> frozenset[str] | None:
    """读取 pinyin.vocab（可选）。文件在 index-tts checkout 内，不存在则返回 None。"""
    try:
        with open(path, encoding="utf-8") as fh:
            return frozenset(line.strip() for line in fh if line.strip())
    except OSError:
        return None


#: 多音字候选表：(字, 易错点, 若读错则标注, 语义规则)。**候选 ≠ 台账**——未经语义
#: 规则消歧的字只作复听时的注意力清单（PRON-GLOSSARY.md）；确认读错才回填台账并
#: 在稿中标注。候选表本体收敛在此而非 PRON-GLOSSARY.md：文档里的表没有消费者，
#: 只会与扫描器漂移。
#:
#: **语义规则（RSI-014）**：`(正则, 推荐读音)` 列表，正则**必须包含本字**（覆盖
#: 判定按「匹配区间盖住 occurrence」）。命中即给出字典级确定的读音，命中的
#: occurrence 应在写稿阶段就标注（RSI-014 起 03 规格纪律）；未命中的 occurrence
#: 仍列双候选、等复听确认（歧义语境下预防性标注反而引入风险——标注错 = 必然
#: 读错，上游丢弃原字无兜底）。规则顺序即消歧优先级：同一 occurrence 被多条
#: 规则覆盖时先命中者胜。
#:
#: **入表纪律 = 先探针后成门**（同 READING_TRAPS：加规则前先拿证据，不凭直觉
#: 列清单）。规则面瞄准的是「**偏离 TTS 默认倾向**的高危读音」，不是多音字的
#: 全部读法：jev 集实证 TTS 对 行 的默认倾向是 xíng——表格语境（每行/单选行/
#: 行尾）全片 ~30 处系统性读错（终渲后人耳发现，negentropy#1173 修复标了 27 处
#: HANG2），而 运行/执行 等 xíng 向语境 8 处仅 1 处（放行）需要标注——默认读
#: 对的方向不设规则，规则只挂**已证实会错**的方向。其余 8 个候选字目前没有
#: 系统性读错证据，规则留空（`()`）；某字经试听证实系统性读错后，其高危方向
#: 的规则再入表（台账 PRON-GLOSSARY.md 是证据入口）。错规则会把可能读对强推
#: 成必然读错，宁缺勿错。
POLYPHONE_CANDIDATES: tuple[
    tuple[str, str, str, tuple[tuple[re.Pattern[str], str], ...]], ...
] = (
    (
        "行",
        "银行/一行代码 háng · 行走/运行 xíng",
        "`<行|HANG2>` / `<行|XING2>`",
        (
            # HANG2（高危向）：表格/量词语境。负面预查排除 xíng 向复合词被量词
            # `一?行` 误收（的一行人/类行为/类行动——`的行` 与 `类行` 各自预查）
            (
                re.compile(
                    r"(?:银行|行列|内行|外行|行业|行话|行尾|行首|行间|行内|行里|行号|行上|行样张?|整行|类行(?![为动]))"
                ),
                "HANG2",
            ),
            (
                re.compile(
                    r"(?:单选|多选|等级|是否|别的|另一?|同一?|下一?|上一?|前一?|后一?|某|这|那|每|各|同|几|两|二|三|四|五|六|七|八|九|十|百|一|\d+) ?行(?![人])"
                ),
                "HANG2",
            ),
            (re.compile(r"的行(?![为程动业政走人])"), "HANG2"),
            # XING2 不设规则：xíng 是 TTS 默认倾向（jev 集运行/执行/放行 8+ 处仅
            # 1 处防御性标注、其余实测读对）——默认读对的方向不产生门需求
        ),
    ),
    ("模", "模型 mó · 模具 mú", "`<模|MO2>`", ()),
    ("率", "效率 lǜ · 率领 shuài（ü 一律写 V）", "`<率|LV4>`", ()),
    ("差", "误差/差异 chā · 差不多 chà", "`<差|CHA1>` / `<差|CHA4>`", ()),
    ("重", "重复/重试 chóng · 重要 zhòng", "`<重|CHONG2>` / `<重|ZHONG4>`", ()),
    ("量", "数量/量化 liàng · 测量 liáng", "`<量|LIANG4>`", ()),
    ("卷", "卷积/卷起 juǎn · 试卷/问卷 juàn（j+ü→JV）", "`<卷|JVAN3>`", ()),
    ("系", "系统/关系 xì（口语易读 jì）", "`<系|XI4>`", ()),
    ("更", "更新/变更 gēng · 更加 gèng", "`<更|GENG1>` / `<更|GENG4>`", ()),
)


def scan_candidates(items: list[dict]) -> list[tuple[str, str, str, str]]:
    """逐句扫描候选多音字 → [(句id, 字, 易错点, 建议标注)]。纯函数、不判错。

    消费者：`check_script.py --pron-candidates`（复听注意力报告，非门）。扫描
    `text`（人读面）即可——标注自带原字，`ttsText` 里的候选字在 `text` 中必然
    同样出现，不存在只落在 ttsText 的多音字。语义消歧（命中规则给推荐读音）
    见 `semantic_missing`——本函数保持「字符在场即列双候选」的粗粒度口径，
    与语义命中面互补不替代。
    """
    out: list[tuple[str, str, str, str]] = []
    for it in items:
        for char, risk, advice, _rules in POLYPHONE_CANDIDATES:
            if char in it["text"]:
                out.append((it["id"], char, risk, advice))
    return out


def _char_occurrences(tts: str, char: str) -> list[tuple[int, str | None]]:
    """→ [(stripped 坐标, 该 occurrence 的标注读音或 None)]。

    按 `strip_marks` 的剥离几何逐字符推算：标记本体携带原字（group(1)），标记内
    的字记为「已标注（读音=group(2)）」，标记外的字记为「未标注」。stripped
    坐标即该字在 `strip_marks(tts)` 里的下标——语义规则的上下文匹配在 stripped
    面上做，坐标因此可直接对齐。
    """
    out: list[tuple[int, str | None]] = []
    stripped_pos = 0
    pos = 0
    for m in PRON_MARK_RE.finditer(tts):
        for ch in tts[pos : m.start()]:
            if ch == char:
                out.append((stripped_pos, None))
            stripped_pos += 1
        for ch in m.group(1):
            if ch == char:
                out.append((stripped_pos, m.group(2)))
            stripped_pos += 1
        pos = m.end()
    for ch in tts[pos:]:
        if ch == char:
            out.append((stripped_pos, None))
        stripped_pos += 1
    return out


def semantic_missing(items: list[dict]) -> list[tuple[str, str, str, str, str]]:
    """语义规则命中而该 occurrence 无任何标注 → [(句id, 字, 推荐读音, 建议标注, 命中上下文)]。

    RSI-014 的核心判定：jev 集全片 30 处「行(háng)」被读成 xíng 直到终渲才靠人耳
    发现——字典级确定的语境（每行/单选行/银行）不该等复听。判定按 occurrence
    粒度：规则匹配区间盖住该字且该字**不在任何标注内**才报；已标注（无论读音
    是否同推荐）视为作者已显式接管，不报——语义规则是建议不是权威，规则表
    本身可能错，作者的不同标注是合法异议。

    消费者：`check_script.py --pron-candidates`（建议清单）与 `--pron-gate`
    （升为门）。纯函数、不判错。
    """
    out: list[tuple[str, str, str, str, str]] = []
    for it in items:
        tts = it.get("ttsText") or it["text"]
        stripped = strip_marks(tts)
        for char, _risk, _advice, rules in POLYPHONE_CANDIDATES:
            if not rules or char not in stripped:
                continue
            occ = _char_occurrences(tts, char)
            occ_pos = {p for p, _reading in occ}
            covered: dict[int, tuple[str, str]] = {}
            for pattern, reading in rules:
                for m in pattern.finditer(stripped):
                    for p in range(m.start(), m.end()):
                        if p in occ_pos and p not in covered:
                            covered[p] = (reading, m.group(0))
            for p, marked in occ:
                if p in covered and marked is None:
                    reading, ctx = covered[p]
                    out.append((it["id"], char, reading, f"<{char}|{reading}>", ctx))
    return out
