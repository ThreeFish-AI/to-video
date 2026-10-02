"""⑦ 配音两档生命周期（edge 草声默认 + 评审后 IndexTTS 克隆重配）的锚定执法（RSI-034）。

路由与规格是本改动的行为面：SKILL.md 任务表入口、07 的重配/追配章节、模板引擎默认、
stages.toml ⑦ 门的引擎分支——四处任一回退都会让「草声→评审→重配」流程失去入口或
被克隆前置错拦。钉字符串锚点（写法同 test_source_types / test_docs_paths 的文案锚定）。
"""

from __future__ import annotations

import tomllib

from paths import skill_root

REFERENCES = skill_root() / "references"
ASSETS = skill_root() / "assets"


def test_skill_router_has_revoice_entry():
    """SKILL.md 任务表须含「评审后重配音」入口（本人声音克隆重配/追配的显式触发面）。"""
    text = (skill_root() / "SKILL.md").read_text(encoding="utf-8")
    assert "评审后重配音" in text, (
        "SKILL.md 任务表缺「评审后重配音」入口——用户显式触发重配/追配时无路由，"
        "只能重走全流程或手改 toml（RSI-034 表因）"
    )


def test_stage7_spec_has_revoice_section_and_triggers():
    """07 须含「两档生命周期」节、「重配（评审后升档）」节与两条触发话术（zh 重配 / en 追配）。"""
    text = (REFERENCES / "07-tts-voice.md").read_text(encoding="utf-8")
    assert "两档生命周期" in text, "07 缺「两档生命周期」节（草声/终声分档语义）"
    assert "重配（评审后升档" in text, "07 缺「重配（评审后升档）」节"
    assert "重配本集视频" in text, "07 缺 zh 重配触发话术"
    assert "额外为本集视频配置英文配音" in text, "07 缺 en 追配触发话术"


def test_scaffold_template_defaults_to_edge_draft():
    """建集模板引擎默认须为 edge 草声（重配才升 indextts，ref 以注释预置）。"""
    text = (ASSETS / "video-skeleton" / "pipeline.toml.tmpl").read_text(
        encoding="utf-8"
    )
    assert 'engine = "edge"' in text, "模板 tts.engine 应默认 edge（草声档）"
    assert "#ref = " in text, "模板 ref 应以注释预置（重配前才需要，非建集前置）"


def test_stage7_gate_is_engine_branched():
    """stages.toml ⑦ 门须引擎分支化：edge 草声直行、indextts 另过克隆三闸。"""
    data = tomllib.loads((REFERENCES / "stages.toml").read_text(encoding="utf-8"))
    stage = next(s for s in data["stage"] if s["id"] == "tts-voice")
    assert "edge" in stage["gate"] and "indextts" in stage["gate"], (
        "⑦ 门未按引擎分支——edge 草声会被克隆前置（refs/试听/排期）错拦"
    )
    assert "草声" in stage["name"], "⑦ 阶段名应体现草声与克隆档位"
