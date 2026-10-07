"""导演手艺知识库的文档级锚定执法（RSI-048）。

执法五类纪律（同 test_voice_tiers 的跨文档行锚先例——防规格漂移的最低成本形态）：
  1. 存在性与预算：DIRECTING-CRAFT.md 存在、带目录、行数 ≤500（知识库自身防 context rot）；
  2. 规格注入行锚：②⑥⑧⑨ 四阶段规格与 05 冻结清单各含核心规范 + 指针（指针断裂即红）；
  3. SSOT 边界：@shot 五档枚举完整枚举只在 DIRECTING-CRAFT——06 只许指针 + ≤2 档样例
     （防第二事实源，同 archify 覆盖门「docstring SSOT、分镜侧摘要同构」纪律）；
  4. 免费护栏钉：@shot 在动效列得「不在词表」WARN 是预期行为（在 test_check_script）；
  5. 路由可达：SKILL.md 按需加载表含 DIRECTING-CRAFT 行（②⑥⑧⑨ 设计时读）。
"""

from __future__ import annotations

from paths import skill_root  # noqa: E402

REFERENCES = skill_root() / "references"
CRAFT = REFERENCES / "DIRECTING-CRAFT.md"

#: 行数上限（完整详解版 ~250 行档位 + 膨胀余量；知识库也要防 context rot）
MAX_LINES = 500

#: 五档景别枚举（SSOT 只在 DIRECTING-CRAFT §1.1 表）
SHOT_TIERS = ("ECU", "CU", "MS", "WS", "EWS")


def _read(path) -> str:
    return path.read_text(encoding="utf-8")


def test_doc_exists_with_toc_and_budget():
    """DIRECTING-CRAFT.md 存在、带目录行、行数 ≤500。"""
    assert CRAFT.exists(), (
        "references/DIRECTING-CRAFT.md 不存在（RSI-048 知识 SSOT 缺失）"
    )
    text = _read(CRAFT)
    assert "**目录**" in text, "DIRECTING-CRAFT 缺目录行（按节查阅的导航面）"
    assert text.count("\n") + 1 <= MAX_LINES, (
        f"DIRECTING-CRAFT {text.count(chr(10)) + 1} 行 > {MAX_LINES}"
        "——知识库膨胀会吃查阅 context，按节压缩或下沉研究文档"
    )


def test_stage_specs_inject_pointer_and_core_rule():
    """四阶段规格 + 05 冻结清单各含核心规范与 DIRECTING-CRAFT 指针（指针断裂即红）。"""
    checks = {
        "02-planning.md": ("镜头语言基调与节奏蓝图", "DIRECTING-CRAFT"),
        "06-storyboard.md": ("@shot:", "DIRECTING-CRAFT"),
        "08-remotion-implementation.md": ("Land on the Word", "DIRECTING-CRAFT"),
        "09-render-qa.md": ("导演级四维", "DIRECTING-CRAFT"),
        "05-prose-refinement.md": ("`@shot`", None),  # 冻结清单只须含记号本身
    }
    for name, (needle, pointer) in checks.items():
        text = _read(REFERENCES / name)
        assert needle in text, f"{name} 缺「{needle}」（RSI-048 核心规范注入）"
        if pointer:
            assert "](./DIRECTING-CRAFT.md)" in text, (
                f"{name} 缺 DIRECTING-CRAFT 可跳转链接（AGENTS.md 死文本禁令；"
                "规格只带指针+核心规范，知识本体不复制）"
            )


def test_shot_enum_ssot_boundary():
    """五档景别完整枚举只在 DIRECTING-CRAFT；06 不得枚举 >2 档（防第二事实源）。"""
    craft = _read(CRAFT)
    for tier in SHOT_TIERS:
        assert f"@shot:{tier}" in craft, (
            f"DIRECTING-CRAFT 缺 @shot:{tier} 档定义（词表 SSOT）"
        )

    # 按裸名独立词统计档数（@shot:WS 与裸枚举 ECU/CU/MS/WS/EWS 都算——第二事实源的两种形态）
    import re

    storyboard = _read(REFERENCES / "06-storyboard.md")
    present = [t for t in SHOT_TIERS if re.search(rf"\b{t}\b", storyboard)]
    assert len(present) <= 2, (
        f"06 出现了 {len(present)} 档景别名（{present}）——枚举 SSOT 在 DIRECTING-CRAFT §1.1，"
        "06 只许指针 + ≤2 档样例（同 archify docstring/分镜摘要同构纪律）"
    )


def test_prose_refinement_freeze_list_covers_shot_tag():
    """05 §七.4 成文优化不动清单须含 @shot（防改写 pass 顺手改坏镜头标注）。"""
    text = _read(REFERENCES / "05-prose-refinement.md")
    assert "`@shot`" in text, (
        "05 冻结清单缺 `@shot`——成文优化会把画面列镜头标注当散文改写"
    )


def test_skill_md_load_on_demand_row():
    """SKILL.md 按需加载表含 DIRECTING-CRAFT 行（②⑥⑧⑨ 设计时读）。"""
    text = _read(skill_root() / "SKILL.md")
    assert "[DIRECTING-CRAFT.md](references/DIRECTING-CRAFT.md)" in text, (
        "SKILL.md 按需加载表缺 DIRECTING-CRAFT 行——Agent 无发现通道，知识库成孤岛（RSI-048）"
    )
