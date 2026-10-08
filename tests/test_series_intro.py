"""系列片头资产契约的文档级锚定执法（RSI-051）。

执法五类纪律（同 test_directing_craft 的跨文档行锚先例——防规格漂移的最低成本形态）：
  1. 存在性与预算：SERIES-INTRO.md 存在、带目录、行数 ≤500（知识库自身防 context rot）；
  2. 阶段规格指针：07/08/09 三阶段规格各含 SERIES-INTRO 可跳转链接（指针断裂即红）；
  3. SSOT 边界：字幕单行语义切换契约只在 06/08/09（RSI-049）——SERIES-INTRO 只许
     指针，不得出现契约正文锚串（防第二事实源）；
  4. 命名约定声明：NARRATION/SUBS 作为规则1 扩面执法锚的约定须在册（文档—执法互锚，
     RSI-050 的机制契约对应文档面）；
  5. 路由可达：SKILL.md 按需加载表含 SERIES-INTRO 行（做系列片头时读）。
"""

from __future__ import annotations

from paths import skill_root  # noqa: E402

REFERENCES = skill_root() / "references"
INTRO = REFERENCES / "SERIES-INTRO.md"

#: 行数上限（资产契约 ~55 行档位 + 膨胀余量；知识库也要防 context rot）
MAX_LINES = 500

#: RSI-049 单行字幕契约的正文锚串——出现在 SERIES-INTRO 即第二事实源
CONTRACT_BODY_ANCHORS = ("恒单行", "全角当量")


def _read(path) -> str:
    return path.read_text(encoding="utf-8")


def test_doc_exists_with_toc_and_budget():
    """SERIES-INTRO.md 存在、带目录行、行数 ≤500。"""
    assert INTRO.exists(), "references/SERIES-INTRO.md 不存在（RSI-051 资产 SSOT 缺失）"
    text = _read(INTRO)
    assert "**目录**" in text, "SERIES-INTRO 缺目录行（按节查阅的导航面）"
    assert text.count("\n") + 1 <= MAX_LINES, (
        f"SERIES-INTRO {text.count(chr(10)) + 1} 行 > {MAX_LINES}"
        "——知识库膨胀会吃查阅 context，按节压缩或下沉研究文档"
    )


def test_stage_specs_inject_pointer():
    """07/08/09 三阶段规格各含 SERIES-INTRO 可跳转链接（指针断裂即红）。
    兼容两种合法同目录链接形态（07 惯用无 ./ 前缀，08/09 惯用 ./ 前缀）。"""
    for name in (
        "07-tts-voice.md",
        "08-remotion-implementation.md",
        "09-render-qa.md",
    ):
        text = _read(REFERENCES / name)
        assert "](SERIES-INTRO.md)" in text or "](./SERIES-INTRO.md)" in text, (
            f"{name} 缺 SERIES-INTRO 可跳转链接（AGENTS.md 死文本禁令；"
            "规格只带指针，契约本体不复制）"
        )


def test_subtitle_contract_pointer_only():
    """单行语义切换契约 SSOT 在 06/08/09（RSI-049）——SERIES-INTRO 只许指针，
    出现契约正文锚串即第二事实源。"""
    text = _read(INTRO)
    assert "单行语义切换" in text, "SERIES-INTRO §五 须留字幕切换概念的指针面"
    assert "](./06-storyboard.md)" in text and "](./09-render-qa.md)" in text, (
        "SERIES-INTRO 字幕切换指针须指向 06/09（RSI-049 SSOT）"
    )
    for anchor in CONTRACT_BODY_ANCHORS:
        assert anchor not in text, (
            f"SERIES-INTRO 出现契约正文锚串「{anchor}」——单行字幕契约正文"
            "只在 06/08/09，此处只许指针（防第二事实源）"
        )


def test_spoken_container_naming_declared():
    """NARRATION/SUBS 命名约定（规则1 扩面的执法锚）须在册——文档—执法互锚：
    check_series.SPOKEN_CONTAINER_RE 硬编码这两个容器名，约定不立册即无发现通道。"""
    text = _read(INTRO)
    assert "NARRATION" in text and "SUBS" in text, (
        "SERIES-INTRO 须声明 NARRATION/SUBS 口播容器命名约定"
    )
    assert "执法锚" in text, "SERIES-INTRO 须声明容器命名是规则1 扩面的执法锚"


def test_skill_md_load_on_demand_row():
    """SKILL.md 按需加载表含 SERIES-INTRO 行（做系列片头时读）。"""
    text = _read(skill_root() / "SKILL.md")
    assert "[SERIES-INTRO.md](references/SERIES-INTRO.md)" in text, (
        "SKILL.md 按需加载表缺 SERIES-INTRO 行——Agent 无发现通道，资产契约成孤岛（RSI-051）"
    )
