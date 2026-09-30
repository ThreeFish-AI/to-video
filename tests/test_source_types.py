"""Stage ① 三型信源（A paper-notes / B source-notes / C gl-notes）的锚定执法（RSI-030）。

C 型（guided-learn 精读产物）落地后的纪律：**文件名清单只在 01 顶部分流表一处枚举**，
下游规格一律三型泛引（指针指向 01），防第四型出现时再复制十余处。本文件钉四个字符串
锚点（写法同 test_docs_paths 的文案锚定测试）；刻意不做「02–05 全文禁裸 paper-notes」
类脆断言——01 的 A 型正文与各规格对 A 型的具名使用（如「A 型即 paper-notes」括注）是
合法形态，一刀切禁词会把它们误判成漂移。
"""

from __future__ import annotations

import re

from paths import skill_root

REFERENCES = skill_root() / "references"


def _type_table_rows(text: str) -> dict[str, str]:
    """→ {型别字母: 该行全文}：01 顶部块引用分流表里的 A/B/C 数据行。"""
    out: dict[str, str] = {}
    for ln in text.splitlines():
        m = re.match(r">\s*\|\s*\*\*([ABC])\*\*\s*\|", ln)
        if m:
            out[m.group(1)] = ln
    return out


def test_source_type_table_lists_three_types():
    """01 顶部分流表须含 A/B/C 三行，C 行指向 research/gl-notes.md（型别判定 SSOT）。"""
    rows = _type_table_rows(
        (REFERENCES / "01-source-extraction.md").read_text(encoding="utf-8")
    )
    assert set(rows) == {"A", "B", "C"}, (
        f"01 顶部分流表应含 A/B/C 三行，实际 {sorted(rows)}——"
        "新增信源形态先挂分流表，挂不进 = 规格缺口而非绕路理由"
    )
    assert "research/gl-notes.md" in rows["C"], (
        "C 行事实源文件应为 research/gl-notes.md"
    )
    assert "guided-learn" in rows["C"], "C 行信源形态应点名 guided-learn 精读产物"


def test_narration_fact_source_line_covers_three_types():
    """03 头部模板行的事实源指引覆盖三型文件名，或含指向 01 的判定指针。"""
    text = (REFERENCES / "03-narration.md").read_text(encoding="utf-8")
    src_lines = [ln for ln in text.splitlines() if "事实源：" in ln]
    assert src_lines, "03 头部模板行丢了「事实源：」指引（检测器失效？）"
    line = src_lines[0]
    has_all_names = all(
        name in line for name in ("paper-notes", "source-notes", "gl-notes")
    )
    points_to_spec = "01" in line
    assert has_all_names or points_to_spec, (
        f"03 事实源指引未泛化到三型：{line.strip()!r}——文件名清单的 SSOT 在 01 顶部表，"
        "此处要么三型并列、要么指针指向 01"
    )


def test_verification_checklist_column_generalized():
    """04 核查表列名须为「事实源锚点」；旧「paper-notes 锚点」是 B/C 型失配形态（反控红面）。"""
    text = (REFERENCES / "04-verification.md").read_text(encoding="utf-8")
    assert "事实源锚点" in text, "04 核查表列名应为「事实源锚点」（三型泛引）"
    assert "paper-notes 锚点" not in text, (
        "04 核查表列名仍写「paper-notes 锚点」——B/C 型集按此列名找不到锚点落法"
    )


def test_skill_router_has_c_type_entry():
    """SKILL.md 任务分流表须含 C 型入口（GL 精读产物成片）。"""
    text = (skill_root() / "SKILL.md").read_text(encoding="utf-8")
    assert "GL 精读产物" in text, (
        "SKILL.md 任务表缺「GL 精读产物成片」入口——上游 guided-learn 产物无路由，"
        "Stage ① 会被迫重复精读（RSI-030 表因）"
    )
