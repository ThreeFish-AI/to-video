"""中文长字幕单行契约的文档级锚定执法（RSI-049）。

三层契约各归其层（写法同 test_directing_craft / test_voice_tiers 的文案锚定先例）：
  1. ⑥ 内容层：zh 恒单行，长句按语义边界拆连续字幕窗口、淡入淡出前后切换；
  2. ⑧ 渲染层：zh 必须 whiteSpace: 'nowrap'，禁自动换行/压字距/缩字号/外溢；
     拆句触发绑定单行内容门上限（全角当量 ≤50，RSI-024），fitText 不替代内容门；
  3. ⑨ QA 层：字幕单行验收——逼近门上限的长句及其前后切换帧必抽查；
  4. en 非泛化：「两行回落」是 en 专属回落术语，06/08 跨层同词（zh 单行约束不得外溢）；
  5. 负例锚：06 不得回退到旧版一句话字幕规范（无长句切换语义，RSI-047 负例先例）；
  6. 渲染层几何不变量（zh nowrap / 54 底距 / en 两行盒几何）已由
     test_skeleton.test_subtitle_en_two_line_geometry_is_pinned 钉住，本文件不重复执法。
"""

from __future__ import annotations

from paths import skill_root  # noqa: E402

REFERENCES = skill_root() / "references"

#: 各文档的契约指纹串（doc → 必须命中的 needle 元组）。串取「本句独有指纹」：
#: 独有到规格漂移即红，又不钉死标点级细节（取舍准则同 test_voice_tiers 锚串先例）。
NEEDLES: dict[str, tuple[str, ...]] = {
    # 06 内容层：结果态锚（恒单行）+ 拆点机制锚（语义边界）+ 切换机制锚（淡入淡出）
    "06-storyboard.md": ("zh 字幕底部恒单行", "语义边界", "淡入淡出前后切换"),
    # 08 渲染层：渲染态锚（nowrap）+ 门数值联动锚（≤50）+ fitText≠内容门锚
    "08-remotion-implementation.md": (
        "whiteSpace: 'nowrap'",
        "全角当量 ≤50",
        "不能替代内容长度门",
    ),
    # 09 QA 层：验收条目锚 + 门数值锚 + 切换帧锚
    "09-render-qa.md": ("字幕单行验收", "全角当量趋近 50", "前后切换帧"),
}


def _read(name: str) -> str:
    return (REFERENCES / name).read_text(encoding="utf-8")


def test_subtitle_single_line_contract_anchors():
    """三层契约 needle 就位：文档缺任一指纹串即红（防规格回退/漂移）。"""
    assert NEEDLES, "NEEDLES 未配置（见 TODO(human)）——空映射会让本测试平凡通过"
    for name, needles in NEEDLES.items():
        text = _read(name)
        for needle in needles:
            assert needle in text, (
                f"{name} 缺「{needle}」（RSI-049 单行契约锚——三层契约任一回退即红）"
            )


def test_en_two_line_fallback_term_not_generalized():
    """「两行回落」是 en 专属回落术语：06/08 跨层同词，zh 单行约束不得泛化到 en 实现。"""
    for name in ("06-storyboard.md", "08-remotion-implementation.md"):
        assert "两行回落" in _read(name), (
            f"{name} 缺「两行回落」——en 冻结回落规则的跨层术语断裂"
            "（zh 单行契约与 en 两行回落是两条并行规则，不得互相吞并）"
        )


def test_storyboard_old_vague_subtitle_spec_gone():
    """负例锚：06 不得回退到旧版模糊字幕规范（只声明结果形态、无长句切换语义）。"""
    old_spec = "底部单行、一句一条、字号、与配音同步"
    assert old_spec not in _read("06-storyboard.md"), (
        "06 回退到旧版一句话字幕规范——正是 RSI-049 表因"
        "「只声明结果形态，没有规定长句如何前后切换」"
    )
