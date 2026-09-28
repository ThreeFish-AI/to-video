"""发音标注 `<原文|读音>` 的解析与校验 —— 「标注错 = 必然读错」的守门人。

上游把标注整体 re.sub 掉、**丢弃原字**（infer_v2_5.py:52-72），且对非法标注既不报错
也不忽略（`pinyin.vocab` 在运行时从未被读取），故错误标注 100% 静默产出错读音频。
一集近 200 句、单槽位 mp3，事后只能靠听发现 —— 校验必须前移到生成阶段。

夹具取自 2026-08-20 对上游源码与 pinyin.vocab（1728 条）的实测。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pron_marks import (  # noqa: E402
    POLYPHONE_CANDIDATES,
    has_marks,
    scan_candidates,
    semantic_missing,
    strip_marks,
    validate,
)

VOCAB = frozenset({"HANG2", "XING2", "YIN2", "JV1", "QV4", "XV1", "ER2", "DE5"})


# ---------------- 剥离：单一书写面派生「人读 text」 ----------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("他在银<行|HANG2>里走。", "他在银行里走。"),
        ("他在银<行|XING2>里<行|HANG2>走。", "他在银行里行走。"),
        ("<Claude|K L AO1 D> 能做到。", "Claude 能做到。"),
        ("<银行|YIN2 HANG2>是机构。", "银行是机构。"),
        ("没有标注的句子。", "没有标注的句子。"),
    ],
)
def test_strip_marks_restores_human_text(raw, expected):
    """标注自带原字 ⇒ 剥离即还原人读文本，无需在逐字稿写两份（不存在副本漂移）。"""
    assert strip_marks(raw) == expected


def test_has_marks():
    assert has_marks("银<行|HANG2>") is True
    assert has_marks("银行") is False
    assert has_marks("延迟 < 10ms") is False  # 孤立 < 不构成标注


# ---------------- ERROR：三个静默失效模式 ----------------


def test_stray_angle_bracket_is_error():
    """上游正则 group(1) 的 `[^|>\\n]+` 允许 `<`：孤立 `<` 会吞掉到下个标记之间的正文。"""
    errs, _ = validate("当 a<b 时，他在银<行|HANG2>里走。")
    assert errs, "孤立 < 与后续标记共存必须报 ERROR"
    assert any("吞掉" in e for e in errs)
    # 只有孤立 < 而无标记时同样报（避免「今天没吞、明天加个标注就吞」）
    errs2, _ = validate("延迟<10ms 就够了。")
    assert errs2


def test_stray_pipe_is_error():
    errs, _ = validate("A|B 两种方案。")
    assert any("孤立 `|`" in e for e in errs)


def test_second_pipe_inside_annotation():
    """`<行|XING2|HANG2>` 的第二个竖线会混进发音串 —— 严格版正则不匹配它，残留即报错。"""
    errs, _ = validate("他在银<行|XING2|HANG2>里走。")
    assert errs


@pytest.mark.parametrize(
    "bad",
    [
        "他在银<行|HANG>里走。",  # 缺声调
        "他在银<行|SHENGDIAO9>里走。",  # 声调越界
        "他在银<行|hang2>里走。",  # 小写
        "他在银<行|HANG2!>里走。",  # 非法字符
        "他在银<行|>里走。",  # 空标注（严格版不匹配 → 残留 <> 报错）
    ],
)
def test_illegal_pinyin_is_error(bad):
    errs, _ = validate(bad)
    assert errs, f"{bad!r} 应报 ERROR"


def test_jqx_u_must_be_written_v():
    """实测 pinyin.vocab 中 `^[JQX]U` 零命中：居/去/须 必须写 JV1/QV4/XV1。"""
    errs, _ = validate("这个<居|JU1>然可以。")
    assert any("必须写 V" in e for e in errs)
    ok, _ = validate("这个<居|JV1>然可以。")
    assert ok == []
    # L/N 声母两种都合法且语义不同（LU=卢、LV=吕），不得误伤
    assert validate("<卢|LU2>先生")[0] == []
    assert validate("<吕|LV3>先生")[0] == []


def test_valid_marks_pass():
    for good in (
        "他在银<行|HANG2>里<行|XING2>走。",
        "<银行|YIN2 HANG2>是机构。",  # 多字词：空格分音节
        "<Claude|K L AO1 D> 能做到。",  # CMU 通道（左侧纯 ASCII）
        "<going|G OW1 . IH0 NG> on.",  # 官方示例的 ` . ` 分音节写法
        "轻声用五声：<的|DE5>。",
    ):
        errs, _ = validate(good)
        assert errs == [], f"{good!r} 应通过，实得 {errs}"


def test_cmu_channel_rejects_non_arpabet():
    errs, _ = validate("<Claude|K L ZZZ1 D> 能做到。")
    assert any("ARPAbet" in e for e in errs)


def test_channel_chosen_by_left_side_not_lang():
    """通道由标记左侧是否含汉字二分（上游 :66），与 lang 无关 —— 写法陷阱的来源。

    `<AI|AI4 AI1>` 左侧纯 ASCII ⇒ 走 CMU 通道，拼音会被当成音素而报错。
    要走拼音通道，左侧必须至少含一个汉字。
    """
    errs, _ = validate("<AI|AI4 AI1> 很强。")
    assert errs, "左侧无汉字却写拼音应被 CMU 校验拦下"
    assert validate("<爱|AI4>很强。")[0] == []


# ---------------- WARN：vocab 缺格只告警不阻断 ----------------


def test_vocab_miss_is_warning_not_error():
    """vocab 存在合法缺格（ANG3/ER1/KEI1 均不在 1728 条内），故只能 WARN。"""
    errs, warns = validate("这<行|ANG3>不通。", VOCAB)
    assert errs == [], "格式合法就不该 ERROR"
    assert any("不在 pinyin.vocab" in w for w in warns)
    # 不传 vocab 时跳过该项（该文件在 index-tts checkout 内，不在本仓）
    assert validate("这<行|ANG3>不通。")[1] == []


def test_in_vocab_no_warning():
    errs, warns = validate("他在银<行|HANG2>里走。", VOCAB)
    assert errs == [] and warns == []


# ---------------- 候选表：每个建议标注都必须本身合法 ----------------
#
# 候选表是「若读错则标注」的复听提示——若表里的建议标注自身非法（如 ü 写 U、
# 缺声调），复听者照抄即产出必然读错的音频（上游丢弃原字无兜底）。故每条建议
# 须先通过 validate() 才有资格出现在表里。


def _marked_forms(advice: str) -> list[str]:
    """`"<行|HANG2>` / `<行|XING2>"` → 取出全部 `<…|…>` 形态并各配一个宿主汉字。

    形态自带原字（`<行|HANG2>`），本身就是可校验的完整标注句。
    """
    import re

    return re.findall(r"<[^>]+>", advice)


def test_every_candidate_advice_passes_validation():
    assert POLYPHONE_CANDIDATES, "候选表为空——检测器失效或表被误删"
    for char, risk, advice, _rules in POLYPHONE_CANDIDATES:
        forms = _marked_forms(advice)
        assert forms, f"候选 {char!r} 的建议列没有任何标注形态：{advice!r}"
        for form in forms:
            errs, _ = validate(f"测试句{form}测试。")
            assert errs == [], f"候选 {char!r} 的建议标注 {form} 非法：{errs}"


def test_candidates_cover_series_vocabulary():
    """claude-code 系列追加的词表必须在场（拆解 Claude Code 口播高频命中）。"""
    chars = {c for c, *_ in POLYPHONE_CANDIDATES}
    for needed in "行重差卷量更":
        assert needed in chars, f"系列词表缺 {needed!r}"


def test_scan_candidates_finds_planted_char_with_id():
    items = [
        {"id": "p0-01", "scene": "P0", "text": "普通句子没有候选字。"},
        {"id": "p1-02", "scene": "P1", "text": "重试一次很重要。"},
    ]
    hits = scan_candidates(items)
    ids = {h[0] for h in hits}
    chars = {h[1] for h in hits}
    assert "p1-02" in ids and "p0-01" not in ids
    assert "重" in chars
    # 四元组形态：(句id, 字, 易错点, 建议标注)
    row = next(h for h in hits if h[1] == "重")
    assert len(row) == 4 and row[2] and row[3]


def test_scan_candidates_empty_on_clean_text():
    items = [{"id": "p0-01", "scene": "P0", "text": "普通句子没有候选字。"}]
    assert scan_candidates(items) == []


def test_glossary_points_to_scanner_not_a_second_table():
    """PRON-GLOSSARY.md 的候选清单已收敛为指针——文档里的表没有消费者，只会
    与扫描器漂移；旧表头若回归（手工补表），split-brain 即复现。
    """
    glossary = (
        Path(__file__).resolve().parents[1] / "references" / "PRON-GLOSSARY.md"
    ).read_text(encoding="utf-8")
    assert "若读错则标注 |" not in glossary, (
        "旧候选表头回归——候选表 SSOT 在 pron_marks.py"
    )
    assert "POLYPHONE_CANDIDATES" in glossary, (
        "指针缺失：文档须指向 pron_marks.py 的候选表"
    )
    assert "--pron-candidates" in glossary, (
        "须给出精确命令（check_script.py --pron-candidates）"
    )
    # 纪律句必须保留（RSI-014 后两段式）：规则命中写稿即标、无规则依据不预防性标注
    assert "写稿即标注" in glossary and "无规则依据的预防性标注" in glossary


# ---------------- 语义规则表（RSI-014）：结构合法性与文档同源 ----------------
#
# 规则是「命中即建议标注」的高危面——错规则会把可能读对强推成必然读错（上游
# 丢弃原字无兜底），故表本身先过三道结构门：正则锚本字、读音是合法拼音、
# 文档速查表与代码同源。


def test_rules_must_anchor_their_char():
    """覆盖判定按「匹配区间盖住本字 occurrence」——正则不含本字则永远盖不住，
    规则静默失效。"""
    for char, _risk, _advice, rules in POLYPHONE_CANDIDATES:
        for pattern, _reading in rules:
            assert char in pattern.pattern, (
                f"{char!r} 的规则 {pattern.pattern!r} 不含本字——覆盖判定失效"
            )


def test_rule_readings_are_legal_pinyin():
    """推荐读音必须能直接写成合法标注（全大写 + 声调；j/q/x+ü 写 V 的约束同校验器）。"""
    n = 0
    for char, _risk, _advice, rules in POLYPHONE_CANDIDATES:
        for _pattern, reading in rules:
            errs, _ = validate(f"测试句<{char}|{reading}>测试。")
            assert errs == [], f"{char!r} 规则推荐读音 {reading} 非法：{errs}"
            n += 1
    assert n > 0, "语义规则表为空——行→HANG2 的实证规则被误删（jev 集全片 ~30 处）"


def test_glossary_quickref_in_sync_with_rules():
    """PRON-GLOSSARY「语义规则速查」节由本测试从 POLYPHONE_CANDIDATES 渲染并
    钉住——文档里的表手动维护必然与代码漂移（候选清单的先例）。表格单元内的
    `|` 按 Markdown 转义为 `\\|`，与文档写法一致。双向钉住：代码行必在文档
    （缺行红）之外，文档表内也不许有代码之外的行（手抄残留/过时正则——单向
    断言拦不住脏行静默留存，评审回归 D5-5）。
    """
    glossary = (
        Path(__file__).resolve().parents[1] / "references" / "PRON-GLOSSARY.md"
    ).read_text(encoding="utf-8")
    assert "语义规则速查" in glossary
    rendered = set()
    for char, _risk, _advice, rules in POLYPHONE_CANDIDATES:
        for pattern, reading in rules:
            esc = "\\"  # Markdown 表格单元内的 | 须转义
            row = (
                f"| {char} | `{pattern.pattern.replace('|', esc + '|')}` "
                f"| {reading} | `<{char}{esc}|{reading}>` |"
            )
            assert row in glossary, (
                f"速查表与 pron_marks 漂移（缺 {char} → {reading} 行）：{row!r}"
            )
            rendered.add(row)
    assert rendered, "语义规则表为空——行→HANG2 的实证规则被误删"
    doc_rows: set[str] = set()
    in_table = False
    for ln in glossary.split("## 语义规则速查", 1)[1].splitlines():
        if not in_table:
            in_table = ln.startswith("| 字 ")
            continue
        if not ln.startswith("|"):
            break  # 表格结束（速查节之后的散文/命令块不属表格）
        if set(ln) <= {"|", "-"}:
            continue  # 表头分隔行
        doc_rows.add(ln)
    assert doc_rows == rendered, (
        f"速查表存在代码之外的行（手抄残留/过时正则）：{sorted(doc_rows - rendered)}"
    )


# ---------------- 语义消歧（semantic_missing，RSI-014 核心）----------------


def test_semantic_missing_recommends_hang_for_table_contexts():
    """jev 病理的正控：表格/量词语境的 行 未标注 → 推荐 HANG2（TTS 默认倾向 xíng，
    全片 ~30 处系统性读错直到终渲才被发现）。"""
    for text in (
        "每一行都要重新算。",
        "单选行记一分。",
        "行尾有个数字。",
        "另起一行。",
    ):
        hits = semantic_missing([{"id": "p0-01", "scene": "P0", "text": text}])
        assert [(h[1], h[2]) for h in hits] == [("行", "HANG2")], (text, hits)


@pytest.mark.parametrize(
    "text",
    [
        "系统运行得很稳定。",  # xíng 向 = TTS 默认倾向，不设规则
        "把任务执行完。",
        "这是他的行为。",
        "分类行动开始。",  # 类行 后跟 动 → 预查排除
        "来了一行人。",  # 一行人 yìxíng → 预查排除
        "另一段行程。",  # 的行 后跟 程 → 预查排除
        "这份报告的行文很流畅。",  # 的行文 xíngwén → 预查排除（评审回归 D1-1）
        "他的行事风格很果断。",  # 的行事 xíngshì
        "警方正在追查他的行踪。",  # 的行踪 xíngzōng
        "他的行李丢了。",  # 的行李 xíngli
        "木星是太阳系的行星。",  # 的行星 xíngxīng——科普天文题材常词
        "队伍的行进速度。",  # 的行进 xíngjìn
        "我们结伴同行。",  # 同行 tóngxíng（走）→ 仅 同行+的 的表格用法入规则
        "我们同行了三年。",
        "继续前行。",  # 前行 qiánxíng 动词 → 前/后 前缀删除
        "这一行为很危险。",  # 一 + 行 + 为 → 预查排除（评审回归 D1-2）
        "各部门各行其是。",  # 各行其是 → 预查排除
        "做事要三思而后行。",  # 后行 → 后一? 前缀删除
        "普通的句子没有候选字。",
    ],
)
def test_semantic_missing_no_false_hit_on_xing_direction(text):
    """规则只挂已证实会错的方向（HANG2 面）——xíng 向语境与干净句零误报。
    误报会逼人绕门：把默认读对的词标成「必须标注」即噪声。"""
    assert semantic_missing([{"id": "p0-01", "scene": "P0", "text": text}]) == []


@pytest.mark.parametrize(
    "text",
    [
        "没有权限查看的行直接扣留。",  # 存量 14 集唯一的 的行 真命中（horizon p3-05）
        "同行的其他格子也要对齐。",  # jev p3-19 同<行|HANG2> 的表格用法
        "上一行和下一行对齐。",  # X一? 前缀 + 裸 一 双路覆盖
        "前一行比后一行长。",
        "同一行代码。",
        "表格的各行都要对齐。",  # 各行 无 其 续字
        "第3行有个数字。",
        "3 行也算。",
        "折叠会把旧的大块头换成一行动字。",  # 一行+动字：行动 歧义取实证方向
    ],
)
def test_semantic_missing_true_hang_survives_tightening(text):
    """收紧后的正控：真 háng 语境（存量语料实证形态）仍须命中——收紧只杀
    误报，不许顺手杀掉 14 集对拍与 jev 27/27 校准赖以成立的真命中。行动
    歧义（一行动字 háng vs 这一行动 xíng）局部不可分，按实证取 háng。"""
    hits = semantic_missing([{"id": "p0-01", "scene": "P0", "text": text}])
    assert hits, text
    assert all(h[1] == "行" and h[2] == "HANG2" for h in hits), (text, hits)


def test_semantic_missing_per_occurrence_precision():
    """occurrence 粒度：同一句里 银行 已标注而 每行 未标注 → 只报后者。
    句级判定（句中有任一标注即过）会放过同句第二个未标注 occurrence。"""
    items = [
        {
            "id": "p0-01",
            "scene": "P0",
            "text": "银行里每一行都要盖章。",
            "ttsText": "银<行|HANG2>里每一行都要盖章。",
        }
    ]
    hits = semantic_missing(items)
    assert len(hits) == 1 and hits[0][2] == "HANG2" and hits[0][4] == "一行"


def test_semantic_missing_respects_author_override():
    """已标注的 occurrence 视为作者显式接管——即便读音与推荐不同也不报
    （语义规则是建议不是权威，规则表本身可能错）。"""
    items = [
        {
            "id": "p0-01",
            "scene": "P0",
            "text": "每一行都要重新算。",
            "ttsText": "每一<行|XING2>都要重新算。",  # 作者异议：标了别的读音
        }
    ]
    assert semantic_missing(items) == []


def test_semantic_missing_multi_char_mark_covers_occurrence():
    """多字词标注 `<银行|YIN2 HANG2>` 内的 行 同样算已标注。"""
    items = [
        {
            "id": "p0-01",
            "scene": "P0",
            "text": "银行是机构，每一行都要对账。",
            "ttsText": "<银行|YIN2 HANG2>是机构，每一行都要对账。",
        }
    ]
    hits = semantic_missing(items)
    assert len(hits) == 1 and hits[0][4] == "一行"
