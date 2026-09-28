"""--pron-gate（RSI-014）：多音字读音候选门升级的 CLI 回归。

病理（jev-decision-model-video v1，negentropy 37692b45d）：全片 26 处「行(háng)」
被 TTS 读成 xíng（修复 8974c2f3f 标 27 处），
`--pron-candidates` 是非门报告（exit 恒 0）、POLYPHONE_CANDIDATES 纯字符匹配
无语义消歧——全片零拦截，终渲后才靠人耳发现。本文件钉住升级后的门语义：

  1. 报告面（缺省）不变：候选清单 + 「语义规则命中而未标注」建议清单，exit 恒 0；
  2. 门面（--pron-gate）：规则命中而该 occurrence 无任何标注 → FAIL、exit 1；
  3. 加标注后 → 通过（这是「门拦得住且放得过」的双向证据，单测拦不住不算门）；
  4. 已标注 occurrence 是作者显式接管，不拦（防规则表错误反噬正确稿）。

夹具复用 test_check_script（同一 minimal 工程骨架），不另建第二套。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_check_script import (  # noqa: E402
    BENIGN,
    BOARD_OK,
    CFG_OK,
    run_check,
    write_board,
    write_config,
    write_narration,
)


def write_marked_narration(root: Path, texts: list[str], tts: dict[str, str]) -> None:
    """写带 ttsText 的 narration.json（text 与 ttsText 的双面形态）。"""
    ids = ["p0-01", "p0-02", "p1-01", "p1-02"]
    items = [
        {
            "id": i,
            "scene": "P0" if i.startswith("p0") else "P1",
            "text": t,
            **({"ttsText": tts[i]} if i in tts else {}),
        }
        for i, t in zip(ids, texts, strict=True)
    ]
    (root / "script" / "narration.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )


def test_gate_fails_on_unmarked_table_context(project):
    """门病理正控：每行的 行 未标注 → FAIL、exit 1——v1 的候选报告对同一输入
    exit 0（下方报告面用例钉住），门与报告的行为差就是本 RSI 的全部收益。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, ["报单上每一行都要核对。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project, "--pron-gate")
    assert rc == 1, out
    assert "FAIL" in out and "p0-01" in out and "HANG2" in out
    assert "加 <行|HANG2>" in out


def test_gate_passes_once_marked(project):
    """加标注后门放行：`<行|HANG2>` 使该 occurrence 已被接管。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_marked_narration(
        project,
        ["报单上每一行都要核对。", BENIGN, BENIGN, BENIGN],
        {"p0-01": "报单上每一<行|HANG2>都要核对。"},
    )
    rc, out = run_check(project, "--pron-gate")
    assert rc == 0, out
    assert "语义规则未标注 0 处" in out


def test_gate_respects_author_override(project):
    """作者标注了不同读音（显式异议）→ 不 FAIL——规则表可能错，作者的标注优先。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_marked_narration(
        project,
        ["报单上每一行都要核对。", BENIGN, BENIGN, BENIGN],
        {"p0-01": "报单上每一<行|XING2>都要核对。"},
    )
    rc, out = run_check(project, "--pron-gate")
    assert rc == 0, out


def test_report_mode_stays_nongating(project):
    """报告面（缺省 --pron-candidates）保持非门：同样的未标注输入 exit 0，
    但「语义规则命中而未标注」建议清单必须在场（报告 ≥ 候选注意力的升级点）。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, ["报单上每一行都要核对。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project, "--pron-candidates")
    assert rc == 0, out
    assert "非门" in out and "候选命中" in out
    assert "语义规则命中而未标注 1 处" in out
    assert "建议标注 <行|HANG2>" in out and "FAIL" not in out


def test_gate_silent_on_xing_default_direction(project):
    """xíng 向语境（TTS 默认倾向、实测读对）零误报——门只挂已证实会错的方向；
    误报会逼人给默认读对的词批量加标注，门退化成噪声然后被绕开。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, ["系统运行得很稳定。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project, "--pron-gate")
    assert rc == 0, out
    assert "语义规则未标注 0 处" in out


def test_gate_mutually_exclusive_with_pre_tts(project):
    """--pre-tts 是内容门、--pron-gate 是发音候选面：混跑会让退出码语义含混。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project, "--pron-gate", "--pre-tts")
    assert rc != 0
    assert "互斥" in out


def test_gate_refuses_lang_en(project):
    """规则表只针对中文多音字；en 模式下跑门只会静默空转（0 命中假绿）。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project, "--pron-gate", "--lang", "en")
    assert rc != 0
    assert "zh" in out


def test_gate_fails_on_illegal_mark(project):
    """非法标注（必然读错）比漏标更严重：门面直接 FAIL，不得当作有效作者
    接管放行（评审回归 D2-1——改前 rc=0 假绿）。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_marked_narration(
        project,
        ["每一行都要重新算。", BENIGN, BENIGN, BENIGN],
        {"p0-01": "每一<行|háng>都要重新算。"},  # 小写拼音 = 非法标注
    )
    rc, out = run_check(project, "--pron-gate")
    assert rc == 1, out
    assert "发音标注非法" in out and "FAIL" in out


def test_report_mode_names_illegal_mark_but_stays_nongating(project):
    """报告面维持「退出码恒 0」契约，但非法标注要点名——静默比非门更糟。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_marked_narration(
        project,
        ["每一行都要重新算。", BENIGN, BENIGN, BENIGN],
        {"p0-01": "报单上每一<行|>都要核对。"},  # 空读音 = 非法标注
    )
    rc, out = run_check(project, "--pron-candidates")
    assert rc == 0, out
    assert "发音标注非法" in out and "FAIL" not in out


def test_gate_refuses_content_face_flags(project):
    """--json/--check-scenes/--check-motion 属内容门面：pron 面静默丢弃会让人
    以为两项检查都跑了（评审回归 D2-2）。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    for flag in ("--json", "--check-scenes", "--check-motion"):
        rc, out = run_check(project, "--pron-gate", flag)
        assert rc != 0, (flag, out)
        assert "互斥" in out, (flag, out)


def test_candidates_lang_en_error_names_actual_flag(project):
    """报错按实际触发的 flag 点名：只传 --pron-candidates 却报 --pron-gate
    是指向不存在的误用（评审回归 D5-4）。断言锚在报错行上——usage 行天然
    列出全部 flag，锚在全文会假绿。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project, "--pron-candidates", "--lang", "en")
    assert rc != 0
    assert any(
        "仅对主稿" in ln and "--pron-candidates" in ln for ln in out.splitlines()
    ), out
