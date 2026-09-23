"""建模手册有界门（RSI-003）——经验沉淀面不得单调膨胀。

手册每集回流、天然只增不减；没有机器执法的上限等于没有上限。本文件钉住三件事：
计数口径确定（同一文本永远同一字数）、水位分级（HIGH 预警 / CAP 阻断）、条目
原子化规则（编号/权重/字段/锚点），以及真实手册本身过门。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_playbook as cp  # noqa: E402

HEAD = "# 手册\n\n> 导言\n\n"
M1 = (
    "- **[M-001] 恒定锚**〔试行·w2〕当：某物不变。故：锁死线宽。"
    "验：抽帧线宽恒等。证：ep-a#1-A（2026-08）"
)
X1 = "- **[X-001] 逆旁白**〔w2〕忌：方向相反。证：ep-a（2026-08）"
C1 = "- 〔+用户〕ep-b#2-C：以静写闷再次被认可（投 M-001）"


def doc(methods=(M1,), anti=(X1,), cands=()) -> str:
    return (
        HEAD
        + "## 建模方法\n\n"
        + "\n".join(methods)
        + "\n\n## 反模式\n\n"
        + "\n".join(anti)
        + "\n\n## 候选区\n\n"
        + "\n".join(cands)
        + "\n"
    )


def errors_of(text: str) -> list[str]:
    return cp.check(text)[1]


# ---------------- 计数口径：确定性 ----------------


@pytest.mark.parametrize(
    ("text", "units"),
    [
        ("恒定视觉锚", 5),
        ("用 Remotion 渲染", 4),  # 3 汉字 + 1 词
        ("strokeWidth 与 LoopRing", 3),
        ("「引号」，标点。！", 4),  # 标点计 0
        ("[手册](./pipeline/MODELING-PLAYBOOK.md)", 2),  # 链接目标不计
        ("见 https://example.com/a-b 说明", 3),  # 裸 URL 不计
        ("claude-code-explained-video#1-A（2026-08）", 3),  # 连字词各算 1
        ("见https://a.com，后面还有十个汉字啊啊啊", 12),  # URL 不得吞掉后随中文
        ("据：https://x.io/p。证：五个汉字", 6),
        ("かな한글", 4),
        ("", 0),
    ],
)
def test_count_units_golden(text, units):
    assert cp.count_units(text) == units


def test_watermarks_are_ordered_hysteresis():
    """滞回的前提：TARGET < HIGH < CAP，且余量足以容纳数条新条目（否则压完即再触发）。"""
    assert cp.TARGET < cp.HIGH < cp.CAP
    assert cp.HIGH - cp.TARGET >= 3 * cp.M_MAX


# ---------------- 真实手册 ----------------


def test_real_playbook_passes_and_stays_below_high():
    """提交态须零 WARN：候选区策展后清空，越过 HIGH 就该在同一 PR 内压到 TARGET。"""
    units, errors, warnings, counts = cp.check(cp.PLAYBOOK.read_text(encoding="utf-8"))
    assert (errors, warnings) == ([], [])
    assert units < cp.HIGH
    assert counts["建模方法"] >= 1


def test_cli_exit_codes(tmp_path, capsys):
    assert cp.main([]) == 0
    bad = tmp_path / "bad.md"
    bad.write_text(doc(methods=(M1, M1)), encoding="utf-8")
    assert cp.main([str(bad)]) == 1
    assert cp.main([str(tmp_path / "missing.md")]) == 1
    assert "ERROR" in capsys.readouterr().out


# ---------------- 水位分级 ----------------


def _padded(units: int) -> str:
    """构造总字数恰为 units 的合规文档（导言区填充，不影响条目规则）。"""
    base = doc()
    pad = units - cp.count_units(base)
    assert pad >= 0
    return base.replace("> 导言", "> 导言" + "字" * pad)


def test_below_high_is_silent():
    units, errors, warnings, _ = cp.check(_padded(cp.HIGH - 1))
    assert (units, errors, warnings) == (cp.HIGH - 1, [], [])


def test_at_high_warns_to_compress():
    _, errors, warnings, _ = cp.check(_padded(cp.HIGH))
    assert errors == []
    assert len(warnings) == 1 and str(cp.TARGET) in warnings[0]


def test_over_cap_is_error():
    _, errors, _, _ = cp.check(_padded(cp.CAP + 1))
    assert any("CAP" in e for e in errors)


# ---------------- 条目规则 ----------------


def test_minimal_valid_doc_passes():
    assert errors_of(doc(cands=(C1,))) == []


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        (doc(methods=(M1, M1.replace("恒定锚", "别名"))), "编号"),
        (doc(methods=(M1, M1.replace("M-001", "M-002"))), "名称"),
        (doc(methods=(M1.replace("w2", "w0"),)), "≤0"),
        (doc(methods=(M1.replace("w2", "w-1"),)), "≤0"),
        (
            doc(
                methods=(
                    M1.replace("w2", "w1"),
                    M1.replace("M-001", "M-002").replace("恒定锚", "乙"),
                )
            ),
            "非增",
        ),
        (doc(methods=(M1.replace("试行·w2", "定式·w3"),)), "定式"),
        (doc(methods=(M1.replace("验：抽帧线宽恒等。", ""),)), "缺必填"),
        (doc(methods=(M1.replace("证：ep-a#1-A（2026-08）", "证：第一集"),)), "锚点"),
        (
            doc(
                methods=(
                    M1.replace(
                        "（2026-08）", "（2026-08）、ep-b（2026-09）、ep-c（2026-09）"
                    ),
                )
            ),
            "至多 2",
        ),
        (
            doc(
                methods=(M1.replace("故：锁死线宽。验", "验：抽帧。故：锁死线宽。验"),)
            ),
            "重复",
        ),
        (
            doc(
                methods=(
                    M1.replace(
                        "当：某物不变。故：锁死线宽。", "故：锁死线宽。当：某物不变。"
                    ),
                )
            ),
            "顺序",
        ),
        (doc(methods=(M1.replace("锁死线宽", "锁" * cp.M_MAX),)), "单条上限"),
        (doc(anti=(X1.replace("方向相反", "反" * cp.X_MAX),)), "单条上限"),
        (doc(cands=("- 随手记一条",)), "候选格式"),
        (doc(cands=("- 〔+用户〕随便写：以静写闷",)), "候选格式"),  # 锚点须指向镜
        (doc(cands=("- 〔-主〕ep-b#2-C：主 Agent 不单独否决",)), "候选格式"),
        (
            doc(
                methods=(
                    M1.replace("w2", "w4"),
                    M1.replace("M-001", "M-002")
                    .replace("恒定锚", "乙")
                    .replace("试行·w2", "定式·w3")
                    .replace("（2026-08）", "（2026-08）、ep-b（2026-09）"),
                )
            ),
            "定式在前",
        ),
        (doc(anti=(X1.replace("忌：方向相反。", ""),)), "缺必填"),
        (
            doc(anti=("- **[X-001] 逆旁白**〔w2〕证：ep-a（2026-08）。忌：方向相反",)),
            "顺序",
        ),
        (doc(methods=("随手散文",)), "非条目行"),
        (doc() + "\n## 附录\n", "二级标题"),
        (doc().replace("## 候选区", "## 候选区\n\n```\ncode\n```"), "围栏"),
    ],
)
def test_violations_are_reported(text, needle):
    assert any(needle in e for e in errors_of(text)), errors_of(text)


@pytest.mark.parametrize("sign", ["+用户", "-用户", "−用户", "－用户", "＋用户", "+主"])
def test_candidate_signs_accept_typed_variants(sign):
    """协议写 U+2212，键盘打出的是 ASCII/全角——三种都必须过，免得门误拒真信号。"""
    assert errors_of(doc(cands=(f"- 〔{sign}〕ep-b#2-C：以静写闷再次被认可",))) == []


def test_quoted_period_inside_field_is_not_split():
    """「当」常引旁白原句，引号里的句号不是字段分隔。"""
    quoted = M1.replace("当：某物不变。", "当：旁白说「够了。」时。")
    assert errors_of(doc(methods=(quoted,))) == []


def test_promotion_rejects_two_anchors_from_same_episode():
    same = M1.replace("试行·w2", "定式·w3").replace(
        "（2026-08）", "（2026-08）、ep-a#2-B（2026-09）"
    )
    assert any("定式" in e for e in errors_of(doc(methods=(same,))))


def test_promotion_requires_two_episodes_and_w3():
    """定式晋升的正例：w≥3 且证锚点分属 2 集。"""
    promoted = M1.replace("试行·w2", "定式·w3").replace(
        "（2026-08）", "（2026-08）、ep-b#3-D（2026-09）"
    )
    assert errors_of(doc(methods=(promoted,))) == []
