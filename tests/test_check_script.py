"""check_script 的覆盖性 / 预算 / 淡入不变式判定。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_script.py"


def run_check(root: Path, *extra: str) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--project", str(root), *extra],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.returncode, r.stdout + r.stderr


def write_board(root: Path, table: str) -> None:
    (root / "script" / "storyboard.md").write_text(table, encoding="utf-8")


def write_config(root: Path, toml: str) -> None:
    (root / "pipeline.toml").write_text(toml, encoding="utf-8")


BOARD_OK = """# 分镜
## P0
| 镜 | 句区间 | 画面 | 动效 |
|---|---|---|---|
| 0-A | p0-01..02 | x | y |
## P1
| 镜 | 句区间 | 画面 | 动效 |
|---|---|---|---|
| 1-A | p1-01..02 | x | y |
"""

CFG_OK = """[narration]
target_minutes = [0.0, 99.0]
chars_per_min = 280
"""


def test_all_green(project):
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 0, out
    assert not [line for line in out.splitlines() if line.strip().startswith("FAIL")]


def test_missing_sentence_fails(project):
    board = BOARD_OK.replace("| 1-A | p1-01..02 |", "| 1-A | p1-01..01 |")
    write_board(project, board)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 1
    assert "p1-02" in out and "未覆盖" in out


def test_unknown_id_fails(project):
    board = BOARD_OK.replace("p1-01..02", "p1-01..p9-99")
    write_board(project, board)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 1
    assert "p9-99" in out


def test_overlap_warns_but_passes(project):
    board = BOARD_OK.replace(
        "| 0-A | p0-01..02 | x | y |",
        "| 0-A | p0-01..02 | x | y |\n| 0-B | p0-02 | 标题卡 | 压尾 |",
    )
    write_board(project, board)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 0  # WARN 不判死
    assert "重叠" in out


def test_annotated_overlap_silent(project):
    board = BOARD_OK.replace(
        "| 0-A | p0-01..02 | x | y |",
        "| 0-A | p0-01..02 | x | y |\n| 0-B | p0-02 尾 | 标题卡 | 压尾 |",
    )
    write_board(project, board)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 0
    assert "重叠" not in out  # 「尾」标注 = 刻意惯例，静默


def test_budget_window_fails(project):
    write_board(project, BOARD_OK)
    write_config(
        project, "[narration]\ntarget_minutes = [0.0, 0.01]\nchars_per_min = 280\n"
    )
    rc, out = run_check(project)
    assert rc == 1
    assert "超预算" in out


def test_malformed_budget_warns_and_skips_instead_of_crashing(project):
    """单元素 target_minutes：形状 FAIL 由 config.validate 报，此处点名 WARN 跳过
    预算门——此前 lo, hi = budget 无条件解包直接 traceback，FAIL 清单一条也打不出。
    """
    write_board(project, BOARD_OK)
    write_config(project, "[narration]\ntarget_minutes = [13.0]\n")
    rc, out = run_check(project)
    assert "Traceback" not in out, out
    assert "跳过时长预算门" in out, out
    assert "应为 [下限, 上限]" in out, out  # 配置校验的 FAIL 仍须报出
    assert rc == 1


def test_measured_budget_uses_manifest(project):
    write_board(project, BOARD_OK)
    # fixture manifest 实测 ≈ (3.10+0.32)+(2.05+1.22)+(4.77+0.32)+(1.02)+tail 2.0 ≈ 14.8s
    write_config(
        project, "[narration]\ntarget_minutes = [0.0, 0.5]\nchars_per_min = 280\n"
    )
    rc, out = run_check(project)
    assert rc == 0, out
    assert "实测口径" in out


# -------- RSI-034：实测门只对「属于当前生效引擎」的 manifest 执法 --------


def test_draft_voice_anchor_skips_measured_budget(project):
    """engine=edge + 终声档锚点：草声实测墙钟不对终声窗执法（跳过须点名），
    估算口径照常执法——本窗口下若无跳过，实测 ≈0.2 分必超 [0, 0.1]。"""
    write_board(project, BOARD_OK)
    write_config(
        project,
        "[narration]\ntarget_minutes = [0.0, 0.1]\nchars_per_min = 10000\n"
        '[tts]\nengine = "edge"\nstyle = "story"\n',
    )
    rc, out = run_check(project)
    assert rc == 0, out
    assert "草声期跳过" in out


def test_edge_final_without_anchor_enforces_measured_budget(project):
    """以 edge 为终声（无锚点）的集：实测门照常执法——锚点跳过不是免死金牌。"""
    write_board(project, BOARD_OK)
    write_config(
        project,
        "[narration]\ntarget_minutes = [0.0, 0.1]\nchars_per_min = 10000\n"
        '[tts]\nengine = "edge"\n',
    )
    rc, out = run_check(project)
    assert rc == 1
    assert "实测时长" in out


def test_upgrade_midstate_marker_mismatch_skips_measured_budget(project):
    """升档中间态（RSI-034 核心钉子）：toml 已翻 indextts、.engine 标记还是
    edge 草声——--pre-tts 前置门不得拿旧引擎墙钟对新档窗口假红拦死重配。"""
    write_board(project, BOARD_OK)
    write_config(
        project,
        "[narration]\ntarget_minutes = [0.0, 0.1]\nchars_per_min = 10000\n"
        '[tts]\nengine = "indextts"\nref = "voices/me-bright.wav"\n'
        'ref_sha1 = "54b699cce97f"\nstyle = "story"\n',
    )
    (project / "video/public/audio/.engine").write_text(
        "edge|zh-CN-YunxiNeural|+4%\n", encoding="utf-8"
    )
    rc, out = run_check(project)
    assert rc == 0, out
    assert "升档重配未完成" in out


def test_marker_matching_engine_enforces_measured_budget(project):
    """标记与当前引擎一致（重配已完成或纯 indextts 集）：实测门恢复执法。"""
    write_board(project, BOARD_OK)
    write_config(
        project,
        "[narration]\ntarget_minutes = [0.0, 0.1]\nchars_per_min = 10000\n"
        '[tts]\nengine = "indextts"\nref = "voices/me-bright.wav"\n'
        'ref_sha1 = "54b699cce97f"\nstyle = "story"\n',
    )
    (project / "video/public/audio/.engine").write_text(
        "indextts|indextts|story|54b699cce97f\n", encoding="utf-8"
    )
    rc, out = run_check(project)
    assert rc == 1
    assert "实测时长" in out


def test_fade_invariant(project):
    (project / "video/src/timing.json").write_text(
        '{"fps":30,"sentenceGapSec":0.32,"sceneGapSec":0.9,"leadInSec":0.6,"tailSec":2.0,"sceneCrossFadeSec":0.9}',
        encoding="utf-8",
    )
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 1
    assert "淡入淡出" in out or "sceneCrossFadeSec" in out


# ---------------- 读法陷阱（上游中文归一化的实测错读写法）----------------
#
# 每条断言对应一次在本机 index-tts venv 上直接跑 TextNormalizer.normalize() 的实测
# （2026-08-20）。反例组同样重要：`0.5~1.0 秒`→`零点五到一点零秒`、`9:30`→`九点三十分`
# 实测**正确**，故不得报错——加规则前先跑探针，别凭直觉扩大清单。


def write_narration(root: Path, texts: list[str]) -> None:
    """按 BOARD_OK 的 4 句骨架（p0-01/02 + p1-01/02）写 narration.json。"""
    import json as _json

    ids = ["p0-01", "p0-02", "p1-01", "p1-02"]
    items = [
        {"id": i, "scene": "P0" if i.startswith("p0") else "P1", "text": t}
        for i, t in zip(ids, texts, strict=True)
    ]
    (root / "script" / "narration.json").write_text(
        _json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )


BENIGN = "这是一句普通的中文口播。"


@pytest.mark.parametrize(
    ("bad", "frag"),
    [
        ("论文发表于 2026 年六月。", "两千零二十六"),  # 4 位年份 + 空格
        ("升级到版本 2.5.1 之后。", "三段版本号"),
        ("速度快了 3-5 倍。", "三减五"),
        ("测量误差是 ±3 个点。", "正负"),
        ("整体提速 10x 左右。", "十x"),
    ],
)
def test_reading_trap_fails(project, bad, frag):
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, [bad, BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project)
    assert rc == 1, out
    assert "读法陷阱" in out and frag in out


def test_sentence_without_han_fails(project):
    """整句无汉字会被上游 use_chinese() 路由到英文归一化（2.5 → two point five）。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, ["IndexTTS 2.5", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project)
    assert rc == 1, out
    assert "整句无汉字" in out


@pytest.mark.parametrize(
    "ok",
    [
        "论文发表于 2026年六月。",  # 无空格才读「二零二六年」
        "耗时 0.5~1.0 秒。",  # 实测 → 零点五到一点零秒（正确）
        "上午 9:30 开始录制。",  # 实测 → 九点三十分（正确）
        "提升 16.2 个百分点。",  # 实测正确
        "6 月 20 日发布。",  # 实测正确
        "第 3 章第 1.2 节。",  # 实测正确
        "AI 与 LLM 都能做到。",  # 纯缩写原样透传
    ],
)
def test_reading_trap_no_false_positive(project, ok):
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, [ok, BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project)
    assert rc == 0, out
    assert "命中 0 处" in out


def test_model_designator_warns_not_fails(project):
    """`1080P` 读成「一千零八十P」——是缺陷但不阻断（型号写法多样，避免误伤）。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, ["输出 1080P 视频。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project)
    assert rc == 0, out
    assert "WARN" in out and "一千零八十" in out


# ---------------- zh 字幕单行宽度门（RSI-024：物理上限 50 全角当量） ----------------


def _write_current_gen_subtitle(root: Path) -> None:
    """字幕宽度门的代际标记：当前模板特征行 `twoLine = !isZh && …`（zh 恒单行）。"""
    f = root / "video" / "src" / "components" / "Subtitle.tsx"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("const twoLine = !isZh && fitted < MIN_FONT_SIZE;\n", encoding="utf-8")


def test_subtitle_width_overflow_fails(project):
    """52 个全角字符（51 字 + 句号）= 52.0 当量 > 50（30px×1528px 物理预算）——E3 事故形态。"""
    _write_current_gen_subtitle(project)
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, ["务" * 51 + "。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project)
    assert rc == 1, out
    assert "字幕宽度" in out and "超字幕单行上限" in out and "p0-01" in out


def test_subtitle_width_at_limit_passes(project):
    """恰 50 个全角字符（49 字 + 句号）= 50.0 当量，在物理预算内放行。"""
    _write_current_gen_subtitle(project)
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, ["务" * 49 + "。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project)
    assert rc == 0, out
    assert "字幕宽度" in out and "超限 0 处" in out


def test_subtitle_width_mixed_halfwidth_fails(project):
    """混排按半角 ~0.55 折算：40 全角 + 20 半角字母 = 40 + 11 = 51.0 > 50。"""
    _write_current_gen_subtitle(project)
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(
        project, ["字" * 40 + "abcdefghij" + "klmnopqrst", BENIGN, BENIGN, BENIGN]
    )
    rc, out = run_check(project)
    assert rc == 1, out
    assert "超字幕单行上限" in out


def test_subtitle_width_runs_in_pre_tts(project):
    """分镜未写时门照跑（句级检查不依赖 storyboard）——两遍法草稿遍即拦截。"""
    _write_current_gen_subtitle(project)
    (project / "script" / "storyboard.md").unlink()
    write_config(project, CFG_OK)
    write_narration(project, ["务" * 51 + "。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project, "--pre-tts")
    assert rc == 1, out
    assert "超字幕单行上限" in out


# ---------------- p0-01 开篇钩子句式 WARN（RSI-039；执法主体=④ 评审门） ----------------


def test_opening_hook_plain_opener_warns(project):
    """寒暄/平铺开场（「今天我们来聊聊」）→ WARN 点名 p0-01，不影响退出码。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, ["今天我们来聊聊一个新东西。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project)
    assert rc == 0, out
    assert any(
        "WARN" in ln and "p0-01" in ln and "开篇钩子" in ln for ln in out.splitlines()
    )


def test_opening_hook_negation_prefix_passes(project):
    """「这不是」起头零 WARN——否定式悬念钩合法（RSI-039 判定口径）。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, ["这不是一支普通的科普视频。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project)
    assert rc == 0, out
    assert not [ln for ln in out.splitlines() if "开篇钩子" in ln and "WARN" in ln], out


def test_opening_hook_runs_in_pre_tts(project):
    """两遍法草稿遍（无分镜）即拦——句式是文本自身可判面。"""
    (project / "script" / "storyboard.md").unlink()
    write_config(project, CFG_OK)
    write_narration(project, ["大家好，欢迎收看本期节目。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project, "--pre-tts")
    assert rc == 0, out
    assert any(
        "WARN" in ln and "p0-01" in ln and "开篇钩子" in ln for ln in out.splitlines()
    )


def test_opening_hook_en_warns_without_this_is(project):
    """en 门：p0-01 不以 "This is" 起头 → WARN；对齐起头零 WARN（语义判定在 ④C）。"""
    setup_en(project)
    rc, out = run_check(project, "--lang", "en")
    assert rc == 0, out
    assert any("WARN" in ln and "p0-01" in ln for ln in out.splitlines()), out
    items = [
        dict(EN_ITEMS_OK[0], text="This is a video made entirely by code.")
    ] + EN_ITEMS_OK[1:]
    setup_en(project, items)
    rc, out = run_check(project, "--lang", "en")
    assert rc == 0, out
    assert not [ln for ln in out.splitlines() if "WARN" in ln and "开篇钩子" in ln], out


# ---------------- --pre-tts：TTS 前置门（两遍法草稿遍，分镜未写） ----------------


def test_pre_tts_completes_without_storyboard(project):
    """两遍法草稿遍形态：storyboard.md 缺失时照常完成、退出 0——前置门只跑
    不需要分镜的检查，缺分镜在它这里是**预期**而非错误。"""
    (project / "script" / "storyboard.md").unlink()
    write_config(project, CFG_OK)
    rc, out = run_check(project, "--pre-tts")
    assert rc == 0, out
    assert "pre-TTS" in out
    # 分镜相关门须**点名跳过**（静默跳过的门比没有门更糟）
    assert "跳过覆盖性" in out


def test_pre_tts_fails_on_over_budget(project):
    """分镜缺席不影响预算门：超窗必须拦（否则草稿遍带着超长稿进 2 小时长跑）。"""
    (project / "script" / "storyboard.md").unlink()
    write_config(
        project, "[narration]\ntarget_minutes = [0.0, 0.01]\nchars_per_min = 280\n"
    )
    rc, out = run_check(project, "--pre-tts")
    assert rc == 1
    assert "超预算" in out


def test_pre_tts_fails_on_reading_trap(project):
    """读法陷阱在前置门内同样成门（ISSUE-164：8 句年份空格错误进了三集成片）。"""
    (project / "script" / "storyboard.md").unlink()
    write_config(project, CFG_OK)
    write_narration(project, ["论文发表于 2026 年六月。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project, "--pre-tts")
    assert rc == 1, out
    assert "读法陷阱" in out and "两千零二十六" in out


def test_pre_tts_fails_on_illegal_pron_mark(project):
    """非法发音标注必须在前置门内红（标注错 = 必然读错，长跑前拦最便宜）。"""
    (project / "script" / "storyboard.md").unlink()
    write_config(project, CFG_OK)
    write_narration(project, ["他在银<行|HANG>里走。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project, "--pre-tts")
    assert rc == 1, out
    assert "发音标注非法" in out


def test_pre_tts_json_output_without_storyboard(project):
    """pipeline.py cmd_tts 以 --json 消费前置门：JSON 输出路径同样不依赖分镜。"""
    (project / "script" / "storyboard.md").unlink()
    write_config(project, CFG_OK)
    rc, out = run_check(project, "--pre-tts", "--json")
    assert rc == 0, out
    import json as _j

    # 输出 = 前置门头部行（人读）+ 多行 JSON（indent=1）；从第一个 "{" 起解析
    payload = _j.loads(out[out.index("{") :])
    assert payload["fails"] == []
    # 夹具 p0-01 是平铺开场，触发已知的开篇钩子 WARN（RSI-039，WARN 不判死）——
    # JSON 面关心 fails 清零与 warns 可消费，不锁定 WARN 明细。
    assert all(w.startswith("WARN") for w in payload["warns"]), payload["warns"]
    assert any("p0-01" in w and "开篇钩子" in w for w in payload["warns"])


# ---------------- --pron-candidates：多音字候选报告（非门） ----------------


def test_pron_candidates_lists_planted_polyphone(project):
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, ["先写一行代码试试。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project, "--pron-candidates")
    assert rc == 0, out
    assert "p0-01" in out and "行" in out
    assert "候选命中" in out and "非门" in out  # 非门声明不打诳语


def test_pron_candidates_silent_on_clean_text(project):
    """无候选字命中时零行输出（只打头部与汇总行）——报告的静默即干净。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, [BENIGN, BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project, "--pron-candidates")
    assert rc == 0, out
    assert "候选命中 0 处" in out


# ---------------- --term-density：④B 密度预算的机器面（RSI-015，WARN 级）----------------
#
# 病理（jev 集）：三个名词系统（集中度/门槛/计费单位）全部先用后讲，④B 五条
# 全检通过而普通观众一脸懵。中文术语机器分不出来——由评审员经 --terms 声明
# （声明优于猜测），拉丁字母词自动计入；beat 边界读 beatStart。WARN 级不改退出码。


def write_items(root: Path, items: list[dict]) -> None:
    (root / "script" / "narration.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )


def _item(sid: str, text: str, *, beat: bool = False) -> dict:
    it = {"id": sid, "scene": f"P{sid[1]}", "text": text}
    if beat:
        it["beatStart"] = True
    return it


def test_term_density_beat_budget_warns(project):
    """jev 病理正控：一个 beat 里 3 个首现中文术语（预算 ≤2）→ WARN，退出码不变。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_items(
        project,
        [
            _item("p0-01", "集中度、门槛、计费单位一起讲。", beat=True),
            _item("p0-02", "普通句。"),
            _item("p1-01", "新幕开讲。", beat=True),
            _item("p1-02", "普通收尾。"),
        ],
    )
    rc, out = run_check(project, "--term-density", "--terms", "集中度,门槛,计费单位")
    assert rc == 0, out  # WARN 级
    warned = [ln for ln in out.splitlines() if "术语密度" in ln]
    assert any("p0-01" in ln and "3 个" in ln for ln in warned), out
    assert any("集中度" in ln and "门槛" in ln for ln in warned), out


def test_term_density_scene_budget_warns(project):
    """幕级预算 ≤8：五个 beat 各 2 个首现术语（beat 全过）而幕合计 9 → 幕级 WARN。
    幕级与 beat 级是两条独立判据——beat 合规不豁免幕超载。"""
    board = """# 分镜
## P0
| 镜 | 句区间 | 画面 | 动效 |
|---|---|---|---|
| 0-A | p0-01 | x | y |
| 0-B | p0-02 | x | y |
| 0-C | p0-03 | x | y |
| 0-D | p0-04 | x | y |
| 0-E | p0-05 | x | y |
## P1
| 镜 | 句区间 | 画面 | 动效 |
|---|---|---|---|
| 1-A | p1-01 | x | y |
"""
    write_board(project, board)
    write_config(project, CFG_OK)
    # 夹具 manifest 是 4 句旧集，与 6 句新稿 id 集不一致会另报 FAIL——删掉走
    # 「manifest 未生成」路径，本用例只看密度门
    (project / "video" / "public" / "audio" / "manifest.json").unlink()
    terms = "甲,乙,丙,丁,戊,己,庚,辛,壬"
    write_items(
        project,
        [
            _item("p0-01", "甲乙讲解。", beat=True),
            _item("p0-02", "丙丁讲解。", beat=True),
            _item("p0-03", "戊己讲解。", beat=True),
            _item("p0-04", "庚辛讲解。", beat=True),
            _item("p0-05", "壬讲解。", beat=True),
            _item("p1-01", "普通收尾。", beat=True),
        ],
    )
    rc, out = run_check(project, "--term-density", "--terms", terms)
    assert rc == 0, out
    warned = [ln for ln in out.splitlines() if "术语密度" in ln and "WARN" in ln]
    assert len(warned) == 1 and "幕 P0" in warned[0] and "9 个" in warned[0], out


def test_term_density_within_budget_silent(project):
    """预算内零 WARN（静默即合规）；拉丁字母词自动计入首现（无需声明）。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_items(
        project,
        [
            _item("p0-01", "Jev 提出了 workflow 的新方法。", beat=True),
            _item("p0-02", "Hume 是另一个门派。", beat=True),
            _item("p1-01", "Jev 又出现了不算首现。", beat=True),
            _item("p1-02", "普通收尾。"),
        ],
    )
    rc, out = run_check(project, "--term-density")
    assert rc == 0, out
    assert not [ln for ln in out.splitlines() if "术语密度" in ln and "WARN" in ln], out
    assert "首现 3 个术语" in out  # jev / workflow / hume（去大小写合并）


def test_term_density_without_beatstart_degrades_to_scene_level(project):
    """旧版 build 产物（无 beatStart）：beat 级点名跳过（静默跳过的门比没有门
    更糟），幕级照跑——两个 beat 各 2 个首现术语若无 beatStart 视为一个 beat，
    点名跳过后不得误报 beat 超载。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_items(
        project,
        [
            _item("p0-01", "甲乙讲解。"),
            _item("p0-02", "丙丁讲解。"),
            _item("p1-01", "普通。"),
            _item("p1-02", "收尾。"),
        ],
    )
    rc, out = run_check(project, "--term-density", "--terms", "甲,乙,丙,丁")
    assert rc == 0, out
    assert "beat 级术语密度跳过" in out and "重跑 build" in out
    assert not [ln for ln in out.splitlines() if "幕 " in ln and "WARN" in ln], out


def test_terms_flag_requires_term_density(project):
    """--terms 只与 --term-density 同用：单独出现即大声退出（拼错 flag 不静默）。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, [BENIGN, BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project, "--terms", "集中度")
    assert rc != 0
    assert "--term-density" in out


def test_term_density_declared_latin_needs_whole_token(project):
    """声明面拉丁词整 token 匹配（评审回归 D3-1）：声明 AI 不得命中 OpenAI 的
    内嵌子串——「OpenAI 发布了 GPT-4o」真实新概念只有 2 个，双计会虚报 3。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_items(
        project,
        [
            _item("p0-01", "OpenAI 发布了 GPT-4o。", beat=True),
            _item("p0-02", "普通句。"),
            _item("p1-01", "新幕开讲。", beat=True),
            _item("p1-02", "普通收尾。"),
        ],
    )
    rc, out = run_check(project, "--term-density", "--terms", "AI")
    assert rc == 0, out
    assert "首现 2 个术语" in out, out  # openai / gpt-4o，无内嵌 ai


def test_term_density_overlapping_declarations_longest_wins(project):
    """中文声明词重叠时长者优先（评审回归 D3-1）：门槛/高门槛 同时声明，
    「高门槛」一处只计 1 个首现术语；且 门槛 被占位命中不算「全片未命中」
    失配（二次评审：改前会误报『声明术语「门槛」全片未命中』）。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_items(
        project,
        [
            _item("p0-01", "这是个高门槛任务。", beat=True),
            _item("p0-02", "普通句。"),
            _item("p1-01", "新幕开讲。", beat=True),
            _item("p1-02", "普通收尾。"),
        ],
    )
    rc, out = run_check(project, "--term-density", "--terms", "门槛,高门槛")
    assert rc == 0, out
    assert "首现 1 个术语" in out, out
    assert "全片未命中" not in out, out


def test_term_density_declared_zero_hit_warns(project):
    """声明词全片零命中点名 WARN（评审回归 D3-2）：圈词与稿子措辞失配时，
    静默消失会让评审员误以为该术语系统密度合规。"""
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_items(
        project,
        [
            _item("p0-01", "普通句子没有术语。", beat=True),
            _item("p0-02", "普通句。"),
            _item("p1-01", "新幕开讲。", beat=True),
            _item("p1-02", "普通收尾。"),
        ],
    )
    rc, out = run_check(project, "--term-density", "--terms", "计费单位")
    assert rc == 0, out  # WARN 级
    assert any("计费单位" in ln and "全片未命中" in ln for ln in out.splitlines()), out


def test_term_density_scene_boundary_at_budget_silent(project):
    """幕级预算边界（评审回归 D6-2）：恰 8 个首现术语（beat 全 ≤2）须静默——
    与 beat 侧 within_budget_silent 对称，防 > 回归成 >= 的变异假绿。"""
    board = """# 分镜
## P0
| 镜 | 句区间 | 画面 | 动效 |
|---|---|---|---|
| 0-A | p0-01 | x | y |
| 0-B | p0-02 | x | y |
| 0-C | p0-03 | x | y |
| 0-D | p0-04 | x | y |
## P1
| 镜 | 句区间 | 画面 | 动效 |
|---|---|---|---|
| 1-A | p1-01 | x | y |
"""
    write_board(project, board)
    write_config(project, CFG_OK)
    (project / "video" / "public" / "audio" / "manifest.json").unlink()
    write_items(
        project,
        [
            _item("p0-01", "甲乙讲解。", beat=True),
            _item("p0-02", "丙丁讲解。", beat=True),
            _item("p0-03", "戊己讲解。", beat=True),
            _item("p0-04", "庚辛讲解。", beat=True),
            _item("p1-01", "普通收尾。", beat=True),
        ],
    )
    rc, out = run_check(project, "--term-density", "--terms", "甲,乙,丙,丁,戊,己,庚,辛")
    assert rc == 0, out
    assert not [ln for ln in out.splitlines() if "术语密度" in ln and "WARN" in ln], out


def test_term_density_pre_tts_mode_also_runs(project):
    """--pre-tts（分镜未写）也要能跑密度门——④B 评审时 storyboard 尚不存在。"""
    (project / "script" / "storyboard.md").unlink()
    write_config(project, CFG_OK)
    write_items(
        project,
        [
            _item("p0-01", "甲乙丙一起讲。", beat=True),
            _item("p0-02", "普通句。"),
            _item("p1-01", "新幕。", beat=True),
            _item("p1-02", "收尾。"),
        ],
    )
    rc, out = run_check(project, "--pre-tts", "--term-density", "--terms", "甲,乙,丙")
    assert rc == 0, out
    assert "术语密度" in out
    assert any("p0-01" in ln and "3 个" in ln for ln in out.splitlines()), out


# ---------------- --check-motion：动效列 @动词 ↔ 场景代码互比 ----------------


BOARD_MOTION = """# 分镜
## P0
| 镜 | 句区间 | 画面 | 动效 |
|---|---|---|---|
| 0-A | p0-01..02 | x | `@enter:fall` 自上落下 `@draw` 描线 |
## P1
| 镜 | 句区间 | 画面 | 动效 |
|---|---|---|---|
| 1-A | p1-01..02 | x | `@stagger` 依次点亮 |
"""


def write_motion_hooks(root: Path) -> None:
    m = root / "video" / "src" / "motion"
    m.mkdir(parents=True, exist_ok=True)
    (m / "hooks.ts").write_text(
        "export function useEnter() {}\nexport function useStagger() {}\n",
        encoding="utf-8",
    )


def write_scene(root: Path, name: str, src: str) -> None:
    d = root / "video" / "src" / "scenes"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(src, encoding="utf-8")


def test_check_motion_warns_on_unimplemented_verb(project):
    """镜内声明 @动词 而该幕场景未调用 → WARN（FadeUp 散文失约的机械化）。"""
    write_board(project, BOARD_MOTION)
    write_config(project, CFG_OK)
    write_narration(project, [BENIGN, BENIGN, BENIGN, BENIGN])
    write_motion_hooks(project)
    write_scene(
        project,
        "P0Hook.tsx",
        "import {useEnter} from '../motion';\nconst e = useEnter('fall');\n",
    )
    write_scene(project, "P1Loop.tsx", "export const P1Loop = () => null;\n")
    rc, out = run_check(project, "--check-motion")
    assert rc == 0, out  # WARN-only 不改退出码
    warned = [line for line in out.splitlines() if "未调用" in line]
    assert any("1-A" in line and "@stagger" in line for line in warned), out
    assert not any("0-A" in line for line in warned), out  # @enter 已实现不告警


def test_check_motion_unknown_verb_and_missing_layer(project):
    """@teleport 不在词表 → WARN；运动层未铺设（无 hooks.ts）→ 门静默不适用。"""
    board = BOARD_MOTION.replace("@stagger", "@teleport")
    write_board(project, board)
    write_config(project, CFG_OK)
    write_narration(project, [BENIGN, BENIGN, BENIGN, BENIGN])
    write_motion_hooks(project)
    write_scene(project, "P0Hook.tsx", "import {useEnter} from '../motion';\n")
    write_scene(project, "P1Loop.tsx", "export const P1Loop = () => null;\n")
    rc, out = run_check(project, "--check-motion")
    assert "@teleport" in out and "词表" in out

    # 无运动层的集（已冻结旧集形态）：不因缺 hooks.ts 而炸或误报
    import shutil

    shutil.rmtree(project / "video" / "src" / "motion")
    rc, out = run_check(project, "--check-motion")
    assert rc == 0 and "未调用" not in out, out


def test_scene_anchor_unknown_id_fails(project):
    """ISSUE-190 防 5：场景代码 at()/dur() 引用不存在的句 id → FAIL（渲染期才抛的跳号句前移拦截）。"""
    board = "| 镜 | 句区间 | 画面 | 动效 |\n|---|---|---|---|\n| 0-A | p0-01..02 | 卡 | ；`@stagger` |\n"
    write_board(project, board)
    write_config(project, CFG_OK)
    write_narration(project, [BENIGN, BENIGN, BENIGN, BENIGN])
    write_scene(
        project,
        "P0Card.tsx",
        "const t1 = at('p0-01');\nconst d9 = dur('p0-99');\n",
    )
    rc, out = run_check(project, "--check-scenes")
    assert rc == 1 and "p0-99" in out and "at()/dur()" in out, out

    # 合法锚（两句都存在）不报
    write_scene(
        project,
        "P0Card.tsx",
        "const t1 = at('p0-01');\nconst d2 = dur('p0-02');\n",
    )
    rc, out = run_check(project, "--check-scenes")
    assert "at()/dur()" not in out, out


DUP_BOARD = (
    "| 镜 | 句区间 | 画面 | 动效 |\n|---|---|---|---|\n| 0-A | p0-01..02 | 卡 | y |\n"
)


def dup_lines(out: str) -> list[str]:
    return [line for line in out.splitlines() if "逐字复述口播" in line]


def test_caption_duplication_fails(project):
    """RSI-007：画面文字逐字复述口播 → FAIL（烧录字幕已逐句上屏，同屏两层重复）。

    钉实测形态：整句照抄、去掉句首连接词的复述（覆盖率判据）、带发音标注的
    口播句（比对字幕面 text——build 期已剥标注，ttsText 不参与）、短于覆盖率
    长度门的短句整句照抄；非幕文件（无 Pn 前缀）回落全片句子比对。缺省执法：
    不带 --check-scenes 也跑（忘带 flag = 检查面静默缩小，all / check 同此）。"""
    write_board(project, DUP_BOARD)
    write_config(project, CFG_OK)
    write_narration(
        project,
        [
            "所以打分不是每个选项各算各的，选项之间会互相影响。",
            "名字叫Jev，官方管这类模型叫系统一模型。",
            "你会拿它，去量什么？",
            BENIGN,
        ],
    )
    nj = project / "script" / "narration.json"
    items = json.loads(nj.read_text(encoding="utf-8"))
    items[1]["ttsText"] = "名字叫<Jev|JH EH1 V>，官方管这类模型叫系统一模型。"
    nj.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    write_scene(
        project,
        "P0Card.tsx",
        "const a = at('p0-01');\n"
        "<div>{'打分不是每个选项各算各的 —— 选项之间会互相影响'}</div>\n"
        "<div>{'名字叫Jev，官方管这类模型叫系统一模型'}</div>\n",
    )
    write_scene(project, "P1Card.tsx", "<div>{'你会拿它，去量什么？'}</div>\n")
    write_scene(
        project, "Callouts.tsx", "<b>{'名字叫Jev，官方管这类模型叫系统一模型'}</b>\n"
    )
    rc, out = run_check(project)
    dup = dup_lines(out)
    assert rc == 1, out
    # 截去句首「所以」照样拦
    assert any("P0Card.tsx:2 " in line and "p0-01" in line for line in dup), out
    # 标注句按字幕面比对
    assert any("P0Card.tsx:3 " in line and "p0-02" in line for line in dup), out
    # 短句整句照抄不受长度门豁免
    assert any("P1Card.tsx:1 " in line and "p1-01" in line for line in dup), out
    # 非幕文件回落全片
    assert any("Callouts.tsx:1 " in line and "p0-02" in line for line in dup), out


@pytest.mark.parametrize(
    ("sentence", "scene_src"),
    [
        pytest.param(
            "当每一次判断都便宜到可以随手来一次——",
            "{show(at('p1-01')) && <Quote text='当每一次判断都便宜到可以随手来一次——' />}",
            id="同行先有短句id-引号不错配",
        ),
        pytest.param(
            "当每一次判断都便宜到可以随手来一次——",
            "<Quote text={`当每一次判断都便宜到可以随手来一次`} />",
            id="模板字符串",
        ),
        pytest.param(
            "当每一次判断都便宜到可以随手来一次——",
            "<div style={{fontSize: 33}}>\n  当每一次判断都便宜到可以随手来一次——\n</div>",
            id="JSX文本独占一行",
        ),
        pytest.param(
            "当每一次判断都便宜到可以随手来一次——",
            '<L zh="结论：当每一次判断都便宜到可以随手来一次" en="x" />',
            id="整句被包含-加前缀标签",
        ),
        pytest.param("就这么简单。", "<b>{'就这么简单'}</b>", id="4到5字短句整句照抄"),
        pytest.param(
            "当每一次判断都便宜到可以随手来一次——",
            "<div>\n  当每一次判断都便宜到\n  可以随手来一次——\n</div>",
            id="同一文本节点跨行续写",
        ),
        pytest.param(
            "当每一次判断都便宜到可以随手来一次——",
            "<div>\n  当每一次判断，\n  <br />\n  都便宜到可以随手来一次\n</div>",
            id="br换行不断段",
        ),
    ],
)
def test_caption_duplication_literal_shapes(project, sentence, scene_src):
    """RSI-007 评审回归：场景代码的常见上屏写法都须被提取——此前多行 JSX 文本
    全漏，已合入的 jev 集因此残留 9 处复述而门报 0。"""
    write_board(project, DUP_BOARD)
    write_config(project, CFG_OK)
    write_narration(project, [BENIGN, BENIGN, BENIGN, sentence])
    write_scene(project, "P1Quote.tsx", "const a = at('p1-01');\n" + scene_src + "\n")
    _rc, out = run_check(project)
    assert any("P1Quote.tsx" in line and "p1-02" in line for line in dup_lines(out)), (
        out
    )


def test_caption_duplication_spares_keyword_anchors(project):
    """RSI-007：关键词 / 数字 / 标签锚点、注释、跨幕回扣均不误伤——字幕只在该句
    播出时上屏，别幕引用同句不构成同屏两层。"""
    write_board(project, DUP_BOARD)
    write_config(project, CFG_OK)
    s = "所以打分不是每个选项各算各的，选项之间会互相影响。"
    write_narration(project, [s, BENIGN, BENIGN, BENIGN])
    write_scene(
        project,
        "P0Card.tsx",
        "const a = at('p0-01');\n"
        "<div>{'选项之间 ⇄ 互相牵动'}</div>\n"  # 关键词锚点（< DUP_MIN_CHARS）
        "<div>{'13% 的答案跟着翻面 · 第三方实测'}</div>\n"  # 补充信息，非口播句
        f"// 对应口播 '{s}'\n"
        f'{{/* "{s}" */}}\n'
        f' * 0-A："{s}"\n',
    )
    write_scene(project, "P1Ending.tsx", f"<div>{{'{s}'}}</div>\n")  # 片尾回扣 P0 句
    _rc, out = run_check(project)
    assert not dup_lines(out), out


def test_caption_duplication_opt_out_needs_reason(project):
    """RSI-007：刻意复述（章节标题卡、同幕跨镜回扣）以 `caption-dup-ok: <理由>`
    逐处豁免——命中行或上一行注明，降为 WARN 留痕；无理由的标记不算豁免。"""
    write_board(project, DUP_BOARD)
    write_config(project, CFG_OK)
    s = "所以打分不是每个选项各算各的，选项之间会互相影响。"
    write_narration(project, [s, BENIGN, BENIGN, BENIGN])
    write_scene(
        project,
        "P0Card.tsx",
        "{/* caption-dup-ok: 章节标题卡，口播即标题 */}\n"
        f"<ChapterCard title='{s}' />\n"
        f"<Recap text='{s}' /> // caption-dup-ok: 幕尾回扣\n"
        "{/* caption-dup-ok: */}\n"
        f"<Quote text='{s}' />\n",
    )
    _rc, out = run_check(project)
    assert "P0Card.tsx:2 画面文字复述口播 p0-01（caption-dup-ok 豁免：章节标题卡" in out
    assert "P0Card.tsx:3 画面文字复述口播 p0-01（caption-dup-ok 豁免：幕尾回扣" in out
    assert [line for line in dup_lines(out) if "P0Card.tsx:5 " in line], out
    assert len(dup_lines(out)) == 1, out


# ---------------- --lang en：译稿门集（RSI-004）----------------
#
# fixture 的 zh narration.json 有 4 句（p0-01/02 · P0，p1-01/02 · P1），en 侧
# 镜像同 id 集。锁期望值按 zh fixture 文本现算（与 build_narration.zh_digest
# 同口径），不复制 digest 字面——口径唯一。

EN_ITEMS_OK = [
    {"id": "p0-01", "scene": "P0", "text": "First sentence of the opening scene."},
    {"id": "p0-02", "scene": "P0", "text": "Second sentence, still opening."},
    {"id": "p1-01", "scene": "P1", "text": "Now the development scene begins."},
    {"id": "p1-02", "scene": "P1", "text": "A slightly longer closing line."},
]

CFG_EN = """[narration]
target_minutes = [0.0, 99.0]
chars_per_min = 280
langs = ["zh", "en"]
words_per_min = 150

[narration.en]
target_minutes = [0.0, 99.0]
"""


def _zh_digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def fresh_lock(project: Path) -> dict[str, dict[str, str]]:
    """锁形态 {句id: {zh: 主稿 digest, en: 译句 digest}}（与 build_narration 同构）。"""
    zh = json.loads((project / "script" / "narration.json").read_text(encoding="utf-8"))
    en = {i["id"]: i["text"] for i in EN_ITEMS_OK}
    return {
        i["id"]: {"zh": _zh_digest(i["text"]), "en": _zh_digest(en[i["id"]])}
        for i in zh
    }


def setup_en(
    project: Path,
    items: list[dict] | None = None,
    *,
    lock: dict[str, dict[str, str]] | None = None,
    toml: str = CFG_EN,
    with_lock: bool = True,
) -> None:
    write_config(project, toml)
    (project / "script" / "narration.en.json").write_text(
        json.dumps(items if items is not None else EN_ITEMS_OK, ensure_ascii=False),
        encoding="utf-8",
    )
    if with_lock:
        (project / "script" / "narration.en.lock.json").write_text(
            json.dumps(
                lock if lock is not None else fresh_lock(project), ensure_ascii=False
            ),
            encoding="utf-8",
        )


def test_en_all_green_and_skips_language_agnostic_gates(project):
    """en 全绿：语言无关门点名跳过（覆盖/淡入/场景互比只在主稿执法）。"""
    setup_en(project)
    rc, out = run_check(project, "--lang", "en")
    assert rc == 0, out
    assert "语言无关门" in out and "主稿执法" in out
    assert "译稿文本门" in out


def test_en_han_residue_fails(project):
    setup_en(project, [dict(EN_ITEMS_OK[0], text="这是一句中文。")] + EN_ITEMS_OK[1:])
    rc, out = run_check(project, "--lang", "en")
    assert rc == 1
    assert "p0-01" in out and "含汉字" in out and "中文归一化" in out


def test_en_no_latin_fails(project):
    """纯数字/符号句与含汉字句同病：上游 use_chinese() 按整句嗅探路由。"""
    setup_en(project, [dict(EN_ITEMS_OK[0], text="2.5 42")] + EN_ITEMS_OK[1:])
    rc, out = run_check(project, "--lang", "en")
    assert rc == 1
    assert "无拉丁字母" in out


def test_en_fullwidth_punct_fails(project):
    setup_en(
        project,
        [dict(EN_ITEMS_OK[0], text="Full-width，pause。")] + EN_ITEMS_OK[1:],
    )
    rc, out = run_check(project, "--lang", "en")
    assert rc == 1
    assert "全角标点" in out and "，" in out and "。" in out


def test_en_subtitle_overflow_fails(project):
    setup_en(
        project,
        [dict(EN_ITEMS_OK[0], text="word " * 40)] + EN_ITEMS_OK[1:],
    )
    rc, out = run_check(project, "--lang", "en")
    assert rc == 1
    assert "字幕两行容量" in out and "p0-01" in out


def test_en_word_budget_over_window_fails(project):
    """en 预算按词数 ÷ words_per_min 对 narration.en.target_minutes 窗口执法
    （zh 窗口不受牵连——两窗独立）。"""
    setup_en(
        project,
        toml=CFG_EN.replace(
            "[narration.en]\ntarget_minutes = [0.0, 99.0]",
            "[narration.en]\ntarget_minutes = [0.0, 0.01]",
        ),
    )
    rc, out = run_check(project, "--lang", "en")
    assert rc == 1
    assert "超预算" in out and "词/分" in out


def test_en_missing_window_warns_and_skips(project):
    """narration.en.target_minutes 未声明：点名 WARN 跳过，不继承 zh 窗口。"""
    setup_en(
        project,
        toml=CFG_EN.replace("\n[narration.en]\ntarget_minutes = [0.0, 99.0]\n", "\n"),
    )
    rc, out = run_check(project, "--lang", "en")
    assert rc == 0, out
    assert "跳过 en 时长预算门" in out and "不继承" in out


def test_en_bad_window_fails_in_config_layer(project):
    """en 窗口形状非法：config 层 FAIL（rc=1）——不再只剩一条跳门 WARN。"""
    setup_en(
        project,
        toml=CFG_EN.replace(
            "[narration.en]\ntarget_minutes = [0.0, 99.0]",
            "[narration.en]\ntarget_minutes = 8",
        ),
    )
    rc, out = run_check(project, "--lang", "en")
    assert rc == 1
    assert "narration.en.target_minutes 应为" in out
    assert "narration.en.target_minutes 缺失或形状非法" in out  # 跳门 WARN 点对键名


def test_en_lock_missing_warns(project):
    setup_en(project, with_lock=False)
    rc, out = run_check(project, "--lang", "en")
    assert rc == 0, out  # 锁缺失是 WARN：译稿还没 build 过是常态时序
    assert "未锁定翻译基线" in out and "build --lang en" in out


def test_en_lock_stale_fails(project):
    """锁与当前主稿 digest 不一致：点名改动句，提示重译后刷新锁。"""
    stale = fresh_lock(project)
    stale["p1-02"]["zh"] = "0" * 12
    setup_en(project, lock=stale)
    rc, out = run_check(project, "--lang", "en")
    assert rc == 1
    assert "基线锁失配" in out and "p1-02" in out and "刷新锁" in out


def test_en_alignment_gates(project):
    """对齐门：缺句 / 多句 / 乱序 / 幕归属错挂，各自点名（幕归属经手改 json 构造——
    md 解析的幕前缀规则使然，json 层才是该门的真实执法面）。"""
    for frag, items in (
        ("缺句", EN_ITEMS_OK[:3]),
        ("多句", EN_ITEMS_OK + [{"id": "p1-03", "scene": "P1", "text": "Extra."}]),
        (
            "句序",
            [EN_ITEMS_OK[1], EN_ITEMS_OK[0], EN_ITEMS_OK[2], EN_ITEMS_OK[3]],
        ),
        (
            "幕归属",
            [dict(EN_ITEMS_OK[0], scene="P1")] + EN_ITEMS_OK[1:],
        ),
    ):
        setup_en(project, items)
        rc, out = run_check(project, "--lang", "en")
        assert rc == 1, (frag, out)
        assert (
            "对齐" not in out
        )  # check 侧消息以「译稿…」点名（build 侧才有「对齐」措辞）
        assert frag in out, (frag, out)


def test_en_missing_zh_master_fails(project):
    lock = fresh_lock(project)  # 先取锁快照，再抽走主稿
    (project / "script" / "narration.json").unlink()
    setup_en(project, lock=lock)
    rc, out = run_check(project, "--lang", "en")
    assert rc == 1
    assert "主稿" in out and "先 build 主稿" in out


def test_pre_tts_en_runs_text_gates_and_blocks_on_stale_lock(project):
    """--pre-tts --lang en：对齐/锁/文本门/词数预算 + 发音标注合法性；锁失配即拦
    （长跑前拦最便宜）。"""
    setup_en(project)
    rc, out = run_check(project, "--pre-tts", "--lang", "en")
    assert rc == 0, out
    assert "pre-TTS" in out and "跳过覆盖性" in out

    stale = fresh_lock(project)
    stale["p0-01"]["zh"] = "f" * 12
    setup_en(project, lock=stale)
    rc, out = run_check(project, "--pre-tts", "--lang", "en")
    assert rc == 1
    assert "基线锁失配" in out


def test_caption_duplication_en_checks_english_subtitle_face(project):
    """RSI-007 双语：en 版字幕是英文，`<L en>` 与英文字幕逐字相同同样叠层——en 门
    缺省执法、对英文字幕面比对；中文画面文字不与英文字幕互判。"""
    setup_en(project)
    write_scene(
        project,
        "P1Quote.tsx",
        '<L zh="结尾金句" en="A slightly longer closing line" />\n'
        "<div>{'这是一句普通的中文口播'}</div>\n",
    )
    rc, out = run_check(project, "--lang", "en")
    assert rc == 1, out
    assert any("P1Quote.tsx:1 " in line and "p1-02" in line for line in dup_lines(out))
    assert not [line for line in dup_lines(out) if "P1Quote.tsx:2 " in line], out


def test_check_scenes_en_reports_untranslated_literals(project):
    """--check-scenes --lang en：未翻译画面文字报告（WARN-only）。已翻译片段
    （带 en 的 <L>、references/08 的 t({zh, en}) 字面对）剥除后不报；缺 en 的 <L>
    （回落中文）与 <Label> 之类同前缀标签照报。"""
    setup_en(project)
    write_scene(
        project,
        "P0Card.tsx",
        "const title = '未翻译的标题';\n"
        'const L1 = <L zh="已翻译" en="Translated"/>;\n'
        "const t = useL();\n"
        "const s = t({zh: '已走通道', en: 'Via hook'});\n"
        'const L2 = <L zh="缺译回落" />;\n'
        'const lb = <Label text="未翻译标签"/>;\n'
        "const mix = t({zh: '甲', en: 'A'}) + '漏译';\n",
    )
    rc, out = run_check(project, "--check-scenes", "--lang", "en")
    assert rc == 0, out  # WARN-only 不改退出码
    assert "英文版画面将显示中文" in out
    for n in (1, 5, 6, 7):
        assert f"P0Card.tsx:{n} " in out, (n, out)
    for n in (2, 3, 4):
        assert f"P0Card.tsx:{n} " not in out, (n, out)
    # en 模式下不再跑主稿的场景互比门（语言无关，主稿执法）
    assert "beatWindow" not in out


def test_subtitle_width_skips_old_gen_subtitle(project):
    """旧代 Subtitle（无 `twoLine = !isZh` 守卫，zh 可折行）——门点名跳过不误报。"""
    f = project / "video" / "src" / "components" / "Subtitle.tsx"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("const twoLine = fitted < MIN_FONT_SIZE;\n", encoding="utf-8")
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    write_narration(project, ["务" * 60 + "。", BENIGN, BENIGN, BENIGN])
    rc, out = run_check(project)
    assert rc == 0, out
    assert "门不适用，点名跳过" in out


# ---------- theme 死字符串门（RSI-043） ----------


def test_quoted_theme_literal_fails(project):
    """`background: 'theme.bgDeep'` 保留引号 = 字符串字面量非常量引用 → FAIL。

    事故行取自 ep1 提交 b542a2ae5 的原样形态（hex→theme 批量替换保留引号，
    12 处死字符串、8 轮门全绿，直到 git show 逐行对账才揭穿）。"""
    write_scene(
        project,
        "P1Card.tsx",
        "const card = {\n"
        "  width: 380,\n"
        "  background: 'theme.bgDeep',\n"
        "  border: `2px solid ${theme.panelBorder}`,\n"
        "};\n",
    )
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 1, out
    assert "P1Card.tsx:3 带引号的 theme 死字符串 'theme.bgDeep'" in out, out
    assert "去引号改读常量" in out


def test_quoted_theme_unquoted_reference_passes(project):
    """去引号后是常量引用（R9 修复形态）——不命中。"""
    write_scene(
        project,
        "P1Card.tsx",
        "const card = {\n  background: theme.bgDeep,\n  color: theme.text,\n};\n",
    )
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 0, out
    assert "死字符串" not in out


def test_quoted_theme_comments_skipped(project):
    """注释行（//、JSX {/* */}、JSDoc * 续行）里的形态不报——说明文字提到
    theme 常量是评审留痕常态，不是缺陷。"""
    write_scene(
        project,
        "P1Card.tsx",
        "// 原 '#0B0E13' 已收敛为 'theme.bgDeep'（RSI-043 判例）\n"
        "const card = {\n"
        "  background: theme.bgDeep,\n"
        "};\n"
        "{/* 上一版写的是 'theme.bgDeep' 被门拦下 */}\n"
        "/**\n"
        " * 历史上 'theme.bgDeep' 曾是死字符串\n"
        " */\n"
        "export default card;\n",
    )
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 0, out
    assert "死字符串" not in out


def test_quoted_theme_filename_literal_exempt(project):
    """`theme.ts` 文件名字面引用是合法上屏形态（agent-skills 集图表配色
    code 标注先例）——词表豁免不报。"""
    write_scene(
        project,
        "P5Note.tsx",
        "const NOTES = [\n  {zh: '图表配色沿用', code: 'theme.ts'},\n];\n",
    )
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 0, out
    assert "死字符串" not in out


def test_quoted_theme_inside_longer_string_not_hit(project):
    """引号内**整串**恰为 theme 成员路径才算——长文案含该子串（说明文字）
    不命中，这是零误报的判据核心。"""
    write_scene(
        project,
        "P5Note.tsx",
        "const label = 'theme.bgDeep 是画框内衬色，见 theme.ts';\n"
        "const tip = `use theme.bgDeep via import`;\n",
    )
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 0, out
    assert "死字符串" not in out


def test_quoted_theme_ok_annotation_downgrades_to_warn(project):
    """命中行注 `quoted-theme-ok: <理由>` 豁免 → WARN 留痕，退出码 0。"""
    write_scene(
        project,
        "P1Card.tsx",
        "const card = {\n"
        "  // quoted-theme-ok: 教学演示死字符串形态本尊\n"
        "  background: 'theme.bgDeep',\n"
        "};\n",
    )
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 0, out
    assert "quoted-theme-ok 豁免" in out


def test_quoted_theme_double_quotes_in_components(project):
    """components/ 同在扫面；双引号形态同罪。"""
    d = project / "video" / "src" / "components"
    d.mkdir(parents=True, exist_ok=True)
    (d / "Banner.tsx").write_text(
        'const style = {background: "theme.bg"};\n', encoding="utf-8"
    )
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 1, out
    assert "components/Banner.tsx:1 带引号的 theme 死字符串 'theme.bg'" in out, out


def test_quoted_theme_same_line_dedup(project):
    """同行同串多命中只报一条（行尾注释复述同一串不双报）。"""
    write_scene(
        project,
        "P1Card.tsx",
        "const card = {\n"
        "  background: 'theme.bgDeep', // 原 '#0B0E13' → 'theme.bgDeep'\n"
        "  color: 'theme.text', color2: 'theme.text',\n"
        "};\n",
    )
    write_board(project, BOARD_OK)
    write_config(project, CFG_OK)
    rc, out = run_check(project)
    assert rc == 1, out
    assert out.count("'theme.bgDeep'") == 1, out
    assert out.count("'theme.text'") == 1, out
