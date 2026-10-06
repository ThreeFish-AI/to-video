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
    assert "--final-voice" in text, (
        "SKILL.md 须出现 --final-voice（RSI-040 人为触发：重配路由/不变量承载"
        "具名授权，agent 与用户都有可发现的授权面）"
    )


def test_stage7_spec_has_revoice_section_and_triggers():
    """07 须含「两档生命周期」节、「重配（评审后升档）」节与两条触发话术（zh 重配 / en 追配）。"""
    text = (REFERENCES / "07-tts-voice.md").read_text(encoding="utf-8")
    assert "两档生命周期" in text, "07 缺「两档生命周期」节（草声/终声分档语义）"
    assert "重配（评审后升档" in text, "07 缺「重配（评审后升档）」节"
    assert "重配本集视频" in text, "07 缺 zh 重配触发话术"
    assert "额外为本集视频配置英文配音" in text, "07 缺 en 追配触发话术"
    # RSI-040 人为触发原则锚点
    assert "人为触发" in text, "07 缺「人为触发原则」表述（RSI-040）"
    assert "--final-voice" in text, "07 缺具名授权 flag 的机器闸表述（RSI-040）"
    assert "不得主动" in text, "07 缺「agent 不得主动提议 IndexTTS」纪律（RSI-040）"


def test_scaffold_template_defaults_to_edge_draft():
    """建集模板引擎默认须为 edge 草声（重配才升 indextts，ref 以注释预置；头注须含对偶交付路径）。"""
    text = (ASSETS / "video-skeleton" / "pipeline.toml.tmpl").read_text(
        encoding="utf-8"
    )
    assert 'engine = "edge"' in text, "模板 tts.engine 应默认 edge（草声档）"
    assert "#ref = " in text, "模板 ref 应以注释预置（重配前才需要，非建集前置）"
    assert "未点名重配即以 edge 成片交付" in text, (
        "模板 [tts] 头注缺「未点名重配即以 edge 成片交付」对偶路径——"
        "单边升档叙事＝滑动面（RSI-047 后续防范）"
    )


def test_stage7_gate_is_engine_branched():
    """stages.toml ⑦ 门须引擎分支化：edge 草声直行、indextts 另过克隆三闸。"""
    data = tomllib.loads((REFERENCES / "stages.toml").read_text(encoding="utf-8"))
    stage = next(s for s in data["stage"] if s["id"] == "tts-voice")
    assert "edge" in stage["gate"] and "indextts" in stage["gate"], (
        "⑦ 门未按引擎分支——edge 草声会被克隆前置（refs/试听/排期）错拦"
    )
    assert "--final-voice" in stage["gate"], (
        "⑦ 门缺「本人显式授权（--final-voice）」——RSI-040 人为触发原则的机器闸"
        "须在通过门声明（与 SKILL.md 速查双址逐字同步）"
    )
    assert "草声" in stage["name"], "⑦ 阶段名应体现草声与克隆档位"


def test_final_render_consumes_existing_audio_track():
    """⑩ 终渲不触发 TTS：只消费既有音轨，未显式重配即 edge 成片（RSI-047）。

    终渲/交付阶段消费哪档音轨若不显式声明，读者会从「终声=交付音色」的档位
    术语反推出「终渲≈终声≈IndexTTS」——机制上 cmd_render 从不分派 TTS，规格
    却曾是空白。钉住四处：SKILL 速查 ⑩ 行与关键不变量括注、10 终渲节首句与
    前置行中性化（两遍法术语不得作终渲前置）。
    """
    skill = (skill_root() / "SKILL.md").read_text(encoding="utf-8")
    assert "终渲沿用既有音轨" in skill, (
        "SKILL.md 速查 ⑩ 行缺「终渲沿用既有音轨」——终渲阶段配音档位"
        "无声明（RSI-047 表因：可被误读为终渲需先升档 IndexTTS）"
    )
    assert "终渲不自动升档" in skill, (
        "SKILL.md 配音不变量缺「终渲不自动升档」细化括注（RSI-047）——"
        "「其余一律 edge 草声」不点名终渲即留滑动面"
    )
    spec = (REFERENCES / "10-final-render.md").read_text(encoding="utf-8")
    assert "不触发任何 TTS" in spec, "10 终渲节缺「不触发任何 TTS」终渲语义（RSI-047）"
    assert "直接以 edge 成片交付" in spec, (
        "10 缺「直接以 edge 成片交付」edge 成片合法路径表述（RSI-047；"
        "锚串取本句独有指纹——「edge 终声集」系换机 runbook 存量术语可平凡满足）"
    )
    assert "B 遍" not in spec and "A 遍" not in spec, (
        "10 不得出现两遍法术语（B 遍/A 遍）——那是 IndexTTS 存量集概念，"
        "字面把克隆两遍写成终渲相关前置（RSI-047 表因）"
    )


def test_stage7_dual_path_edge_final_delivery():
    """07 两档生命周期须含 edge 直达终渲交付的对偶路径（RSI-047）。"""
    spec = (REFERENCES / "07-tts-voice.md").read_text(encoding="utf-8")
    assert "终渲/交付" in spec, (
        "07 草声时机枚举缺「终渲/交付」——枚举止于试配音会把终渲推向升档叙事（RSI-047）"
    )
    assert "直接终渲交付" in spec, (
        "07 迭代与定稿缺「不点名＝以 edge 草声直接终渲交付」对偶路径——只有"
        "升档单边叙事即暗含交付必升档（RSI-047）"
    )
    assert "末次 TTS 完成后（edge 或克隆皆同）" in spec, (
        "07 完成门须以「末次 TTS」表述——「终声完成后…才算交付」可被读作"
        "交付前须有克隆终声（RSI-047）"
    )
