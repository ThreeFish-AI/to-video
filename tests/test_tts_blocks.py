"""story 档（段落演绎）：块划分 / 切分规划 / 摘要后缀 / 台本解析 / 表演标点。"""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import tts  # noqa: E402

# dream-rsi P0 前 11 句（test_tts_blocks 的回归语料，与 .temp 试听集同源）
P0 = [
    {"id": f"p0-{n:02d}", "scene": "P0", "text": t}
    for n, t in enumerate(
        [
            "想让 AI 自己改进自己，先得让它大量试错。",
            "一轮试错，就是一次「提出方案、交给评审打分」。",
            "这样一轮轮跑下去，动辄几千次调用，每一次都要花钱。",
            "账单滚得飞快，问题也来了：能不能换个更聪明的试错法？",
            "最实在的办法，是把整套流程再跑一遍，换个打法看结果。",
            "可这一试，又是几千次真金白银的调用。",
            "2026年9月，一篇论文押了一个大胆的赌注。",
            "AI 已经走过的每一步路，其实都留在了台账里。",
            "与其再进一次山，不如把旧台账变成一座免费的沙盘。",
            "在沙盘上推演新打法，一分钱不用花。",
            "这套方法，说白了就是：在做梦里改进自己。",
        ],
        1,
    )
]
BLOCK_CFG = tts.STYLE_PRESETS["story"]["block"]


# ---------------- 块划分 ----------------


def ids(blocks):
    return [[i["id"] for i in b] for b in blocks]


def test_plan_blocks_never_crosses_scene():
    items = [dict(i) for i in P0] + [
        {"id": "p1-01", "scene": "P1", "text": "新幕第一句。"},
        {"id": "p1-02", "scene": "P1", "text": "新幕第二句。"},
    ]
    blocks = tts.plan_blocks(items, BLOCK_CFG)
    assert all(len({i["scene"] for i in b}) == 1 for b in blocks)
    assert {i["id"] for b in blocks for i in b} == {i["id"] for i in items}


def test_plan_blocks_cue_starts_reproduce_p0_audition():
    """台本块起点（#07 的 [1-3][4-6][7-8][9-11]）不被自动划分改写。"""
    items = [dict(i) for i in P0]
    for sid in ("p0-01", "p0-04", "p0-07", "p0-09"):
        next(i for i in items if i["id"] == sid)["blockStart"] = True
    assert ids(tts.plan_blocks(items, BLOCK_CFG)) == [
        [f"p0-{n:02d}" for n in rng]
        for rng in ((1, 2, 3), (4, 5, 6), (7, 8), (9, 10, 11))
    ]


def test_plan_blocks_auto_respects_limits():
    blocks = tts.plan_blocks([dict(i) for i in P0], BLOCK_CFG)
    for b in blocks:
        assert len(b) <= BLOCK_CFG["max_sentences"]
        assert (
            sum(len(tts.synth_source_text(i)) for i in b) <= BLOCK_CFG["max_chars"]
            or len(b) == 1
        )


def test_plan_blocks_oversized_single_sentence_own_block():
    items = [
        {"id": "p0-01", "scene": "P0", "text": "短句。"},
        {"id": "p0-02", "scene": "P0", "text": "长" * 120},
    ]
    blocks = tts.plan_blocks(items, BLOCK_CFG)
    assert len(blocks) == 2  # 超长句无法与邻句成块（>max_chars），各自成块


def test_plan_blocks_widens_past_infeasible_lower_bound():
    """下界切不出时逐层放宽块数，而非整段退化逐句（9×35 字：下界 4 块不可行，5 块可行）。"""
    items = [
        {"id": f"p0-{n:02d}", "scene": "P0", "text": "字" * 35} for n in range(1, 10)
    ]
    blocks = tts.plan_blocks(items, BLOCK_CFG)
    assert sorted(len(b) for b in blocks) == [1, 2, 2, 2, 2]
    assert [sid for b in ids(blocks) for sid in b] == [i["id"] for i in items]


def test_plan_blocks_split_cue_run_inherits_emotion():
    """台本段超限被拆开：后续子块沿用段首情绪（不在段中途退回预设），且不改写原件。"""
    items = [
        {"id": f"p0-{n:02d}", "scene": "P0", "text": "字" * 20} for n in range(1, 6)
    ]
    items[0]["blockStart"] = True
    items[0]["cue"] = {"emo": "afraid:1"}
    blocks = tts.plan_blocks(items, BLOCK_CFG)
    assert len(blocks) == 2
    preset = tts.STYLE_PRESETS["story"]["vec"]
    vecs = [tts.resolve_block_vec(b, preset, 0.28)[0] for b in blocks]
    assert vecs[0] == vecs[1] == tts.parse_emo_vector("afraid:1")
    assert all("cue" not in i for i in items[1:])


def test_plan_blocks_cue_does_not_leak_past_next_boundary():
    """继承止于下一个硬边界：新幕 / 无台本的新 run 仍用预设情绪。"""
    items = [
        {"id": f"p0-{n:02d}", "scene": "P0", "text": "字" * 20} for n in range(1, 6)
    ] + [{"id": "p1-01", "scene": "P1", "text": "新幕第一句。"}]
    items[0]["blockStart"] = True
    items[0]["cue"] = {"emo": "afraid:1"}
    blocks = tts.plan_blocks(items, BLOCK_CFG)
    preset = tts.STYLE_PRESETS["story"]["vec"]
    assert tts.resolve_block_vec(blocks[-1], preset, 0.28)[0] == preset


def test_plan_blocks_edit_only_repartitions_its_window():
    """改一句只重排其所在划分窗：9×31 字末句 +1 字，前 6 句的块原样不动（全局 DP 下 5 块全平移）。"""
    items = [
        {"id": f"p0-{n:02d}", "scene": "P0", "text": "字" * 31} for n in range(1, 10)
    ]

    def head(blocks):  # 完全落在首窗（前 6 句）的块
        return [b for b in ids(blocks) if all(int(s[-2:]) <= 6 for s in b)]

    before = tts.plan_blocks(items, BLOCK_CFG)
    items[-1] = {**items[-1], "text": "字" * 32}
    after = tts.plan_blocks(items, BLOCK_CFG)
    assert head(before) == head(after) and len(head(before)) == 3


def test_plan_blocks_edit_blast_radius_is_bounded():
    """任一句改字长，需重录的句数 ≤ 所在窗（2×max_sentences，1 句尾窗并入 ⇒ 至多 +1）。"""
    import random

    rng = random.Random(20260926)
    bound = 2 * BLOCK_CFG["max_sentences"] + 1
    for _ in range(40):
        n = rng.randint(4, 20)
        lens = [rng.randint(8, 50) for _ in range(n)]
        mk = lambda ls: [  # noqa: E731
            {"id": f"p0-{k:02d}", "scene": "P0", "text": "字" * L}
            for k, L in enumerate(ls, 1)
        ]
        base = {tuple(b) for b in ids(tts.plan_blocks(mk(lens), BLOCK_CFG))}
        for i in range(n):
            for d in (-6, 3, 12):
                edited = list(lens)
                edited[i] = max(1, edited[i] + d)
                new = ids(tts.plan_blocks(mk(edited), BLOCK_CFG))
                sid = f"p0-{i + 1:02d}"
                redo = sum(len(b) for b in new if tuple(b) not in base or sid in b)
                assert redo <= bound, (lens, i, d, new)


def test_plan_blocks_lone_tail_joins_previous_window():
    """7 句的段：末句不因定长窗被孤立成单句块（1 句尾窗并入前窗）。"""
    items = [
        {"id": f"p0-{n:02d}", "scene": "P0", "text": "字" * 20} for n in range(1, 8)
    ]
    assert all(len(b) > 1 for b in tts.plan_blocks(items, BLOCK_CFG))


# ---------------- 切分规划与切分算术 ----------------


def test_plan_block_cuts_prefers_expected_positions():
    """3 句块：句界期望位 1/3、2/3 处各放长静音；逗号短静音落在别处干扰。"""
    runs = [
        (1.2, 1.5),  # 逗号停顿（离期望远）
        (2.0, 2.4),  # 期望 ~2.1：句界 1
        (3.1, 3.2),  # 逗号停顿
        (4.1, 4.5),  # 期望 ~4.2：句界 2
    ]
    picked = tts.plan_block_cuts(
        runs, [1.0, 1.0, 1.0], total_sec=6.0, speech_on=0.0, speech_off=6.0
    )
    assert picked == [(2.0, 2.4), (4.1, 4.5)]


def test_plan_block_cuts_fails_when_no_feasible_match():
    runs = [(0.1, 0.2)]  # 唯一候选远离子数所需
    assert (
        tts.plan_block_cuts(
            runs, [1.0] * 3, total_sec=6.0, speech_on=0.0, speech_off=6.0
        )
        is None
    )


def test_split_block_pcm_discard_from_middle():
    import numpy as np

    sr = 1000
    pcm = np.concatenate(
        [
            np.ones(1000, np.float32),
            np.zeros(500, np.float32),
            np.ones(1000, np.float32),
        ]
    )
    clips = tts.split_block_pcm(pcm, sr, [(1.0, 1.5)], discard_sec=0.32)
    assert len(clips) == 2
    # 前段保留静音前半 (500-320)/2=90ms；总停顿 = 90 + 320(时间轴补) + 90 = 自然停顿 500ms
    assert clips[0][0].shape[0] == 1090  # 1000 语音 + 90 静音前半（淡出只缩幅不改长度）
    assert abs(clips[0][1] - 0.5) < 1e-6  # 自然停顿回填值


def test_split_block_pcm_floor_when_silence_short():
    import numpy as np

    sr = 1000
    pcm = np.concatenate(
        [
            np.ones(1000, np.float32),
            np.zeros(200, np.float32),
            np.ones(1000, np.float32),
        ]
    )
    clips = tts.split_block_pcm(pcm, sr, [(1.0, 1.2)], discard_sec=0.32)
    # 静音 0.2 < 0.32+2×0.03 → 退化为丢 S−0.06=0.14，各留 30ms
    assert clips[0][0].shape[0] == 1030


def test_split_block_pcm_last_clip_fades_in_at_cut():
    """末段起点即末个切点：静音只是低于阈值（非零底噪），须与中间段同样淡入，否则起播阶跃。"""
    import numpy as np

    sr = 1000
    pcm = np.full(2500, 0.01, np.float32)  # 全程底噪：切点处样本非零
    clips = tts.split_block_pcm(pcm, sr, [(1.0, 1.5)], discard_sec=0.32)
    fade = int(sr * 0.005)
    for clip, _ in clips:
        assert clip[0] == 0.0 and clip[-1] == 0.0
        assert clip[fade] == np.float32(0.01)  # 淡变只罩 5ms，不改长度与正文幅度


def test_split_block_pcm_tail_pad():
    import numpy as np

    sr = 1000
    pcm = np.ones(1000, np.float32)
    clips = tts.split_block_pcm(pcm, sr, [], discard_sec=0.32, tail_pad_sec=0.18)
    assert clips[0][0].shape[0] == 1000 + 180


# ---------------- 摘要与预设 ----------------


def test_digest_block_none_is_byte_identical_to_legacy():
    base = tts.digest_indextts(
        "aa" * 6, "sunny", [1.0] + [0] * 7, 0.35, 0.95, "ZH", "indextts", "x"
    )
    again = tts.digest_indextts(
        "aa" * 6,
        "sunny",
        [1.0] + [0] * 7,
        0.35,
        0.95,
        "ZH",
        "indextts",
        "x",
        block=None,
        pos=None,
    )
    assert base == again


def test_digest_block_suffix_changes_and_is_deterministic():
    a = tts.digest_indextts(
        "aa" * 6,
        "story",
        [0.5] + [0] * 7,
        0.28,
        1.0,
        "ZH",
        "indextts",
        "x",
        block="ab12cd34ef56",
        pos="1/3",
    )
    b = tts.digest_indextts(
        "aa" * 6,
        "story",
        [0.5] + [0] * 7,
        0.28,
        1.0,
        "ZH",
        "indextts",
        "x",
        block="ab12cd34ef56",
        pos="1/3",
    )
    c = tts.digest_indextts(
        "aa" * 6,
        "story",
        [0.5] + [0] * 7,
        0.28,
        1.0,
        "ZH",
        "indextts",
        "x",
        block="ab12cd34ef56",
        pos="2/3",
    )
    assert a == b and a != c


def test_block_digest_suffix_tracks_member_text():
    s1 = tts.block_digest_suffix(["a", "b"], 0.32, 0.18)
    s2 = tts.block_digest_suffix(["a", "c"], 0.32, 0.18)
    s3 = tts.block_digest_suffix(["a", "b"], 0.4, 0.18)
    assert len(s1) == 12 and s1 != s2 and s1 != s3


def test_story_preset_invariants():
    p = tts.STYLE_PRESETS["story"]
    assert abs(sum(p["vec"]) - 1.0) < 1e-6  # nominal-sum 门（test_digest 同口径）
    assert p["alpha"] * sum(p["vec"]) <= 0.8
    assert isinstance(p["seed"], int)
    for k in ("max_sentences", "max_chars", "tail_pad_sec", "perform_punct"):
        assert k in p["block"]


def test_tts_text_perform_keeps_ellipsis():
    assert tts.tts_text("可这一试……", "ZH") == "可这一试。"
    assert tts.tts_text("可这一试……", "ZH", perform=True) == "可这一试…"
    assert tts.tts_text("破折——号", "ZH", perform=True) == "破折，号"
    assert tts.tts_text("x……", "EN", perform=True) == "x……"  # en 不做映射


def test_resolve_sampling_preset_seed():
    import argparse

    ns = argparse.Namespace(
        style="story",
        emo_vector=None,
        seed=None,
        seed_offset=0,
        no_text_normalization=False,
        temperature=None,
        top_p=None,
        top_k=None,
        length_penalty=None,
        repetition_penalty=None,
        max_mel_tokens=None,
        interval_silence=None,
    )
    assert tts.resolve_sampling(ns)["seed"] == tts.STYLE_PRESETS["story"]["seed"]
    ns.seed_offset = 3
    assert tts.resolve_sampling(ns)["seed"] == tts.STYLE_PRESETS["story"]["seed"] + 3
    ns.seed, ns.seed_offset = 7, 0
    assert tts.resolve_sampling(ns)["seed"] == 7  # CLI 优先


def test_block_synth_text_adds_terminal_punct():
    items = [
        {"id": "a", "scene": "P0", "text": "没有句号"},
        {"id": "b", "scene": "P0", "text": "有句号。"},
        {"id": "c", "scene": "P0", "text": "感叹！"},
    ]
    assert tts.block_synth_text(items) == "没有句号。有句号。感叹！"


def test_block_synth_text_keeps_soft_pause_endings():
    """`，：、——` 结尾是原稿续接：原样保留，不拼出 `，。` 双标点。"""
    items = [
        {"id": "a", "scene": "P0", "text": "逗号续接，"},
        {"id": "b", "scene": "P0", "text": "冒号引出："},
        {"id": "c", "scene": "P0", "text": "破折号——"},
        {"id": "d", "scene": "P0", "text": "收尾。"},
    ]
    text = tts.block_synth_text(items)
    assert text == "逗号续接，冒号引出：破折号——收尾。"
    assert "，。" not in tts.tts_text(text, "ZH", perform=True)


def test_block_synth_text_sees_through_closing_quotes():
    """收引号/括号不算末字：`！”` 不再拼出 `！”。`；引号前无标点才补 `。`。"""
    items = [
        {"id": "a", "scene": "P0", "text": "他说：“不可能！”"},
        {"id": "b", "scene": "P0", "text": "你确定真的不要这些了？」"},
        {"id": "c", "scene": "P0", "text": '忽略你之前的所有规则。"'},
        {"id": "d", "scene": "P0", "text": "他称之为“负熵”"},
    ]
    assert tts.block_synth_text(items) == (
        '他说：“不可能！”你确定真的不要这些了？」忽略你之前的所有规则。"他称之为“负熵”。'
    )


def test_block_suffix_versioned_past_v2():
    """v3 改了块文本拼接与兜底尾垫：同成员文本也必须换键（旧 v2 产物不得命中）。"""
    import hashlib

    v2 = hashlib.sha1(("a\x1fb\x1f0.32\x1f0.18\x1fsplit=v2").encode()).hexdigest()[:12]
    assert tts.block_digest_suffix(["a", "b"], 0.32, 0.18) != v2


# ---------------- 块情感（cue）解析 ----------------


def test_resolve_block_vec_normalizes_cue_direction():
    b = [dict(P0[0])]
    b[0]["cue"] = {"emo": "afraid:0.18,surprised:0.12,melancholic:0.05"}
    vec, alpha, bad = tts.resolve_block_vec(b, tts.STYLE_PRESETS["story"]["vec"], 0.28)
    assert bad is None and alpha == 0.28
    assert abs(sum(vec) - 1.0) < 1e-9
    assert sum(vec) * alpha <= 0.8


def test_resolve_block_vec_rejects_over_strength():
    b = [dict(P0[0])]
    b[0]["cue"] = {"emo": "happy:1.0", "alpha": 0.9}
    _, _, bad = tts.resolve_block_vec(b, tts.STYLE_PRESETS["story"]["vec"], 0.28)
    assert bad == "p0-01"


def test_resolve_block_vec_accepts_full_strength_despite_float_sum():
    """归一后 Σ 浮点可为 1+1ulp：build 放行的 alpha=0.8 不得被 Σ×α≤0.8 护栏误拒（服务端同口径）。"""
    emo = "afraid:0.01,surprised:0.04,calm:0.13"
    raw = tts.parse_emo_vector(emo)
    naive = [x / sum(raw) for x in raw]
    assert sum(naive) * 0.8 > 0.8  # 前提：该方向确实踩到浮点边界
    b = [dict(P0[0])]
    b[0]["cue"] = {"emo": emo, "alpha": 0.8}
    vec, alpha, bad = tts.resolve_block_vec(b, tts.STYLE_PRESETS["story"]["vec"], 0.28)
    assert bad is None and alpha == 0.8
    assert sum(vec) * alpha <= 0.8
    assert max(abs(a - c) for a, c in zip(vec, naive)) < 1e-15
    # 未踩边界的档（α<0.8）向量逐位不变 ⇒ 摘要不漂移
    b[0]["cue"] = {"emo": emo}
    assert tts.resolve_block_vec(b, tts.STYLE_PRESETS["story"]["vec"], 0.28)[0] == naive


def test_resolve_block_vec_falls_back_to_preset():
    vec, alpha, bad = tts.resolve_block_vec(
        [dict(P0[0])], tts.STYLE_PRESETS["story"]["vec"], 0.28
    )
    assert bad is None and vec == tts.STYLE_PRESETS["story"]["vec"] and alpha == 0.28


# ---------------- 服务端切分入口（不启 FastAPI，直接调函数） ----------------


def test_frame_db_and_silence_runs_roundtrip():
    import numpy as np

    sr = 22050
    pcm = np.concatenate(
        [
            np.random.default_rng(0).normal(0, 0.3, int(sr * 1.0)).astype(np.float32),
            np.zeros(int(sr * 0.4), np.float32),
            np.random.default_rng(1).normal(0, 0.3, int(sr * 1.0)).astype(np.float32),
        ]
    )
    db = tts.frame_db(pcm, sr)
    runs, on, off = tts.silence_runs(db, sr)
    assert (
        len(runs) == 1
        and abs(runs[0][0] - 1.0) < 0.05
        and abs((runs[0][1] - runs[0][0]) - 0.4) < 0.05
    )
    assert abs(on) < 0.05


# ---------------- 台本（build_narration.apply_cues） ----------------


def _write_md(root: Path):
    (root / "script").mkdir(parents=True, exist_ok=True)
    lines = ["## P0 开场", "", "- [p0-01] 想让 AI 自己改进自己，先得让它大量试错。", ""]
    (root / "narration.md").write_text("\n".join(lines), encoding="utf-8")


def test_apply_cues_absent_file_is_noop():
    import build_narration as bn

    items = [
        {
            "id": "p0-01",
            "scene": "P0",
            "text": "想让 AI 自己改进自己，先得让它大量试错。",
        }
    ]
    before = [dict(i) for i in items]
    assert bn.apply_cues(Path("/nonexistent"), items) == (0, 0, [])
    assert items == before


def test_apply_cues_emits_block_and_say(tmp_path):
    import build_narration as bn

    _write_md(tmp_path)
    items = [
        {
            "id": "p0-01",
            "scene": "P0",
            "text": "想让 AI 自己改进自己，先得让它大量试错。",
        }
    ]
    (tmp_path / "script" / "narration.cues.toml").write_text(
        '[block.p0-01]\nemo = "surprised:0.6,happy:0.4"\n\n[say]\n'
        'p0-01 = "想让 AI 自己改进自己？先得让它，大量试错！"\n',
        encoding="utf-8",
    )
    n_block, n_say, errs = bn.apply_cues(tmp_path, items)
    assert errs == [] and (n_block, n_say) == (1, 1)
    assert (
        items[0]["blockStart"] is True
        and items[0]["cue"]["emo"] == "surprised:0.6,happy:0.4"
    )
    assert items[0]["ttsText"] == "想让 AI 自己改进自己？先得让它，大量试错！"
    assert items[0]["text"] == "想让 AI 自己改进自己，先得让它大量试错。"  # 字幕不动


def test_apply_cues_rejects_word_changes(tmp_path):
    import build_narration as bn

    _write_md(tmp_path)
    items = [
        {
            "id": "p0-01",
            "scene": "P0",
            "text": "想让 AI 自己改进自己，先得让它大量试错。",
        }
    ]
    (tmp_path / "script" / "narration.cues.toml").write_text(
        '[say]\np0-01 = "想让 AI 自己进化自己？先得让它大量试错！"\n', encoding="utf-8"
    )
    _, _, errs = bn.apply_cues(tmp_path, items)
    assert any("只许改标点" in e for e in errs)


def test_apply_cues_pins_every_pron_mark(tmp_path):
    """say 须逐个原样携带标注：删一个、改读音都拒；只动标点放行。"""
    import build_narration as bn

    _write_md(tmp_path)
    tts_text = "<重|CHONG2>新定义<行|HANG2>业。"
    cues = tmp_path / "script" / "narration.cues.toml"
    for say, ok in (
        ("<重|CHONG2>新定义，行业。", False),  # 丢 <行|HANG2>
        ("<重|ZHONG4>新定义，<行|HANG2>业！", False),  # 改读音
        (
            "<重|CHONG2>新定义，<行|HANG，2>业！",
            False,
        ),  # 读音内插标点（去标点比对会剥掉）
        ("<重|CHONG2>新定义，<行|HANG2。>业！", False),
        ("<重|CHONG2>新定义，<行|HANG2>业！", True),
    ):
        items = [{"id": "p0-01", "scene": "P0", "text": "重新定义行业。"}]
        items[0]["ttsText"] = tts_text
        cues.write_text(f'[say]\np0-01 = "{say}"\n', encoding="utf-8")
        _, n_say, errs = bn.apply_cues(tmp_path, items)
        if ok:
            assert errs == [] and n_say == 1 and items[0]["ttsText"] == say
        else:
            assert any("发音标注" in e for e in errs), say
            assert items[0]["ttsText"] == tts_text  # 拒绝时不落盘


def test_apply_cues_keeps_digit_separators(tmp_path):
    """数字里的半角 . , : 是正文字符：say 删掉它等于改数（3.5%→35%），须拒；句读标点照常可改。"""
    import build_narration as bn

    _write_md(tmp_path)
    cues = tmp_path / "script" / "narration.cues.toml"
    for say, ok in (
        ("增长了35%，用时10:30，共1,200次。", False),
        ("增长了3.5%，用时1030，共1,200次。", False),
        ("增长了3.5%，用时10:30，共1200次。", False),
        ("增长了3.5%……用时10:30！共1,200次！", True),
    ):
        items = [
            {"id": "p0-01", "scene": "P0", "text": "增长了3.5%，用时10:30，共1,200次。"}
        ]
        cues.write_text(f'[say]\np0-01 = "{say}"\n', encoding="utf-8")
        _, n_say, errs = bn.apply_cues(tmp_path, items)
        if ok:
            assert errs == [] and n_say == 1, say
        else:
            assert any("只许改标点" in e for e in errs), say


def test_apply_cues_rejects_punct_inserted_into_numbers(tmp_path):
    """往数字串里插标点（含多字符 `……`）或删掉两数之间的标点都改了读数，须拒；
    两数之间已有的标点换成别的表演标点照常放行。"""
    import build_narration as bn

    _write_md(tmp_path)
    cues = tmp_path / "script" / "narration.cues.toml"
    for text, say, ok in (
        ("一共1200台。", "一共12，00台。", False),
        ("一共1200台。", "一共12……00台。", False),
        ("写于2026年。", "写于20，26年。", False),
        ("从2020，2026两年。", "从20202026两年。", False),
        ("从2020，2026两年。", "从2020……2026两年！", True),
        ("一共1200台。", "一共，1200台！", True),
    ):
        items = [{"id": "p0-01", "scene": "P0", "text": text}]
        cues.write_text(f'[say]\np0-01 = "{say}"\n', encoding="utf-8")
        _, n_say, errs = bn.apply_cues(tmp_path, items)
        if ok:
            assert errs == [] and n_say == 1, say
        else:
            assert any("只许改标点" in e for e in errs), say


def test_apply_cues_malformed_tables_are_reported_not_raised(tmp_path):
    """台本写错形态：汇入错误清单（build 统一 FAIL 退出），不得抛 traceback。"""
    import build_narration as bn

    _write_md(tmp_path)
    cues = tmp_path / "script" / "narration.cues.toml"
    for body, needle in (
        ('[block]\np0-01 = "happy:1"\n', "block.p0-01 须为表"),
        ('[block.p0-01]\nemo = "happy:1"\nalpha = "x"\n', "alpha"),
        ('[block.p0-01]\nemo = "happy:1"\nalpha = true\n', "alpha"),
        ("[block.p0-01]\nemo = 1\n", "emo"),
        ('block = "x"\n', "[block] 须为表"),
        ('say = "x"\n', "[say] 须为表"),
    ):
        items = [{"id": "p0-01", "scene": "P0", "text": "想让 AI 自己改进自己。"}]
        cues.write_text(body, encoding="utf-8")
        n_block, _, errs = bn.apply_cues(tmp_path, items)
        assert n_block == 0 and any(needle in e for e in errs), (body, errs)
        assert "cue" not in items[0]


def test_status_tracks_cues_sidecar(tmp_path, capsys):
    """只改台本不改正文：status 须报 narration.json 失鲜（否则 tts 拿旧 cue 合成）。"""
    import os

    import pipeline

    script = tmp_path / "script"
    script.mkdir()
    (script / "narration.md").write_text("x", encoding="utf-8")
    (script / "narration.json").write_text("[]", encoding="utf-8")
    cues = script / "narration.cues.toml"
    cues.write_text("[say]\n", encoding="utf-8")
    for p, t in ((script / "narration.md", 100), (script / "narration.json", 200)):
        os.utime(p, (t, t))
    os.utime(cues, (300, 300))
    pipeline._status_lang(tmp_path, "zh", multi=False)
    assert "输入已更新（narration.cues.toml）" in capsys.readouterr().out
    os.utime(cues, (150, 150))
    pipeline._status_lang(tmp_path, "zh", multi=False)
    assert "narration.json    ✅ 新鲜" in capsys.readouterr().out


def test_apply_cues_rejects_unknown_ids(tmp_path):
    import build_narration as bn

    _write_md(tmp_path)
    items = [{"id": "p0-01", "scene": "P0", "text": "想让 AI 自己改进自己。"}]
    (tmp_path / "script" / "narration.cues.toml").write_text(
        '[block.p0-99]\nemo = "happy:1.0"\n', encoding="utf-8"
    )
    _, _, errs = bn.apply_cues(tmp_path, items)
    assert any("不是本稿句 id" in e for e in errs)


def test_apply_cues_take_is_validated_int(tmp_path):
    """[take] 落 item["take"]；非 1–999 整数（含 bool/浮点/字符串）与未知 id 汇入错误清单。"""
    import build_narration as bn

    _write_md(tmp_path)
    cues = tmp_path / "script" / "narration.cues.toml"

    def run(body: str):
        items = [{"id": "p0-01", "scene": "P0", "text": "想让 AI 自己改进自己。"}]
        cues.write_text(body, encoding="utf-8")
        return items, bn.apply_cues(tmp_path, items)[2]

    items, errs = run("[take]\np0-01 = 2\n")
    assert errs == [] and items[0]["take"] == 2
    for bad in ("0", "1000", "-1", "true", "1.5", '"1"'):
        items, errs = run(f"[take]\np0-01 = {bad}\n")
        assert "take" not in items[0] and any("1–999" in e for e in errs), bad
    _, errs = run("[take]\np0-99 = 1\n")
    assert any("take.p0-99 不是本稿句 id" in e for e in errs)
    _, errs = run('take = "x"\n')
    assert any("[take] 须为表" in e for e in errs)


def _story_steady_plan(tmp_path, lang: str = "zh"):
    """--style story --steady p0-01 --plan 的子进程结果（纯本地，不连服务）。"""
    import subprocess

    script = Path(__file__).resolve().parents[1] / "scripts" / "tts.py"
    proj = tmp_path / "proj"
    (proj / "script").mkdir(parents=True)
    sfx, text = (
        ("", "想让 AI 自己改进自己。") if lang == "zh" else (".en", "Hello there.")
    )
    (proj / "script" / f"narration{sfx}.json").write_text(
        f'[{{"id": "p0-01", "scene": "P0", "text": "{text}"}}]',
        encoding="utf-8",
    )
    (proj / "video" / "src").mkdir(parents=True)
    (proj / "video" / "src" / "timing.json").write_text(
        '{"fps": 30, "sentenceGapSec": 0.32, "sceneGapSec": 0.9, "leadInSec": 0.6, "tailSec": 2.0, "sceneCrossFadeSec": 0.4}',
        encoding="utf-8",
    )
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"x" * 16)
    return subprocess.run(
        [
            sys.executable,
            str(script),
            "--project",
            str(proj),
            "--engine",
            "indextts",
            "--ref",
            str(ref),
            "--narration-lang",
            lang,
            "--style",
            "story",
            "--steady",
            "p0-01",
            "--plan",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
    )


def test_steady_with_block_style_is_rejected(tmp_path):
    """--steady 逐句升束与块合成冲突：进程级退出非零并点名冲突。"""
    r = _story_steady_plan(tmp_path)
    assert r.returncode != 0
    assert "冲突" in (r.stderr + r.stdout)


def test_steady_allowed_when_en_falls_back_to_sentences(tmp_path):
    """EN 版 story 档回退逐句合成，与 --steady 不冲突：须照常按混合档排期。"""
    r = _story_steady_plan(tmp_path, lang="en")
    assert r.returncode == 0, r.stderr
    assert "回退逐句" in r.stderr
    assert "束宽 3" in r.stdout  # --steady 命中句按 --steady-beams 3 排期


# ---------------- 块合成主流程（stub 服务端）----------------


def _clip(fmt: str = "mp3") -> dict:
    """占位 clip：客户端只落字节不解码（时长由 mp3_duration 实测，测试里 stub）。"""
    import base64

    return {
        "audio": base64.b64encode(b"ID3fake").decode(),
        "durationSec": 9.99,
        "format": fmt,
    }


def _run_block(block, audio_dir, timeout: float = 5.0, **kw):
    import asyncio

    return asyncio.run(
        asyncio.wait_for(
            tts.synth_block_indextts(
                asyncio.Semaphore(tts.CONCURRENCY_INDEXTTS),
                block,
                False,
                "ref.wav",
                "r" * 12,
                "story",
                tts.STYLE_PRESETS["story"]["vec"],
                tts.STYLE_PRESETS["story"]["alpha"],
                1.0,
                "ZH",
                "indextts",
                "http://unused",
                audio_dir,
                **kw,
            ),
            timeout,
        )
    )


def test_split_failure_falls_back_without_deadlock_and_caches(monkeypatch, tmp_path):
    """切分失败 → 锁外逐句兜底（旧实现锁内递归，Semaphore(1) 自锁挂死）；兜底产物按块
    成员摘要落盘，复跑整块命中、零请求；兜底沿用块情绪（台本 cue 覆盖全部成员）。"""
    block = [dict(i) for i in P0[:2]]
    block[0]["cue"] = {"emo": "afraid:0.6,surprised:0.4"}
    calls: list[tuple[int, list[float]]] = []

    def fake(server, text, ref, vec, alpha, df, lang, beams, weights, *rest):
        calls.append((len(weights), vec))
        if len(weights) > 1:
            return {"split": "failed", "reason": "stub", "clips": None}
        return {"split": "ok", "clips": [_clip()], "cuts": [], "seams": []}

    monkeypatch.setattr(tts, "http_synthesize_block", fake)
    monkeypatch.setattr(tts, "mp3_duration", lambda _p: 2.0)
    out = _run_block(block, tmp_path)
    assert [n for n, _ in calls] == [2, 1, 1]
    assert calls[1][1] == calls[2][1] == calls[0][1]  # 兜底同块情绪
    assert [r["blockSplit"] for r in out] == ["fallback", "fallback"]

    def unexpected(*_a, **_k):
        raise AssertionError("兜底产物复跑应整块命中")

    monkeypatch.setattr(tts, "http_synthesize_block", unexpected)
    again = _run_block(block, tmp_path)
    assert [r["durationSec"] for r in again] == [2.0, 2.0]


def test_split_failure_fallback_pads_only_last_sentence(monkeypatch, tmp_path):
    """兜底尾垫同块合成口径：只有末句补垫（服务端单句路径无条件补，非末句须传 0）。"""
    pads: list[float] = []

    def fake(server, text, ref, vec, alpha, df, lang, beams, weights, discard, pad, *_):
        pads.append(pad)
        if len(weights) > 1:
            return {"split": "failed", "reason": "stub", "clips": None}
        return {"split": "ok", "clips": [_clip()], "cuts": [], "seams": []}

    monkeypatch.setattr(tts, "http_synthesize_block", fake)
    monkeypatch.setattr(tts, "mp3_duration", lambda _p: 2.0)
    _run_block([dict(i) for i in P0[:3]], tmp_path, tail_pad_sec=0.18)
    assert pads == [0.18, 0.0, 0.0, 0.18]  # 整块请求 + 3 句兜底


def test_block_duration_is_cache_state_independent(monkeypatch, tmp_path):
    """合成与命中同取 mp3 实测时长：服务端 PCM 口径（durationSec）不进 manifest。"""
    block = [dict(i) for i in P0[:2]]
    monkeypatch.setattr(
        tts,
        "http_synthesize_block",
        lambda *_a, **_k: {
            "split": "ok",
            "clips": [_clip(), _clip()],
            "cuts": [],
            "seams": [],
        },
    )
    monkeypatch.setattr(tts, "mp3_duration", lambda _p: 2.0)
    fresh = _run_block(block, tmp_path)
    cached = _run_block(block, tmp_path)
    assert (
        [r["durationSec"] for r in fresh]
        == [r["durationSec"] for r in cached]
        == [2.0, 2.0]
    )


def test_block_rejects_non_mp3_clips(monkeypatch, tmp_path):
    """服务端无 MP3 编码器回退 wav：硬拒且不落盘（同逐句路径 X-Audio-Format 守卫）。"""
    import pytest

    block = [dict(i) for i in P0[:2]]
    monkeypatch.setattr(
        tts,
        "http_synthesize_block",
        lambda *_a, **_k: {
            "split": "ok",
            "clips": [_clip("wav"), _clip("wav")],
            "cuts": [],
            "seams": [],
        },
    )
    with pytest.raises(tts.NonRetryableError, match="编码器不可用"):
        _run_block(block, tmp_path)
    assert not list(tmp_path.glob("*.mp3"))


def test_block_local_hit_backfills_store(monkeypatch, tmp_path):
    """整块本地命中而库中缺档（首跑 --no-store）⇒ 回填入库，同逐句路径。"""
    block = [dict(i) for i in P0[:2]]
    audio, store = tmp_path / "audio", tmp_path / "store"
    audio.mkdir()
    monkeypatch.setattr(
        tts,
        "http_synthesize_block",
        lambda *_a, **_k: {
            "split": "ok",
            "clips": [_clip(), _clip()],
            "cuts": [],
            "seams": [],
        },
    )
    monkeypatch.setattr(tts, "mp3_duration", lambda _p: 2.0)
    _run_block(block, audio)  # store=None：不入库

    def unexpected(*_a, **_k):
        raise AssertionError("整块本地命中不应再请求")

    monkeypatch.setattr(tts, "http_synthesize_block", unexpected)
    _run_block(block, audio, store=store, slug="ep")
    for i in block:
        digest = (audio / f"{i['id']}.sha").read_text()
        assert tts.store_has(store, "ep", i["id"], digest)


def test_plan_eta_excludes_store_recoverable_blocks(tmp_path):
    """--plan 块口径：版本库可整块回收的块不占合成时间（同逐句 n − store_hits 口径）。"""
    import hashlib
    import json
    import os
    import subprocess

    script = Path(__file__).resolve().parents[1] / "scripts" / "tts.py"
    proj = tmp_path / "ep"
    (proj / "script").mkdir(parents=True)
    items = [dict(i) for i in P0[:3]]
    (proj / "script" / "narration.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"x" * 16)
    ref_sha1 = hashlib.sha1(ref.read_bytes()).hexdigest()[:12]
    p = tts.STYLE_PRESETS["story"]
    store = tmp_path / "store"
    src = tmp_path / "src.mp3"
    src.write_bytes(b"ID3fake")
    # 无 timing.json ⇒ discard 回退 0.32（与 main 同口径）
    for b in tts.plan_blocks(items, p["block"]):
        texts = [tts.synth_source_text(i) for i in b]
        suffix = tts.block_digest_suffix(texts, 0.32, p["block"]["tail_pad_sec"])
        for k, i in enumerate(b):
            d = tts.digest_indextts(
                ref_sha1,
                "story",
                p["vec"],
                p["alpha"],
                p["df"],
                "ZH",
                "indextts",
                texts[k],
                1,
                None,
                None,
                {"seed": p["seed"]},
                suffix,
                f"{k + 1}/{len(b)}",
            )
            tts.store_deposit(src, i["id"], d, store, proj.name)
    r = subprocess.run(
        [
            sys.executable,
            str(script),
            "--project",
            str(proj),
            "--engine",
            "indextts",
            "--ref",
            str(ref),
            "--style",
            "story",
            "--plan",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        env={**os.environ, "TO_VIDEO_TTS_STORE": str(store)},
    )
    assert r.returncode == 0, r.stderr
    assert "版本库整块直收" in r.stdout
    assert "估算墙钟约 0.0 小时" in r.stdout


# ---------------- 台本 [take]：块级重掷 ----------------


def test_block_sampling_offsets_only_its_block():
    """take 只改所在块的种子（整集 --seed-offset 会改全部块）；无 take 的块口径原样。"""
    base = {"seed": 4242}
    plain = [dict(i) for i in P0[:2]]
    taken = [dict(i) for i in P0[2:4]]
    taken[1]["take"] = 3
    assert tts.block_sampling(plain, base) == base
    assert tts.block_sampling(taken, base) == {"seed": 4245}
    assert base == {"seed": 4242}  # 不改入参


def test_block_sampling_rejects_ambiguous_takes():
    """同块两条 take（加和还是择一）歧义 ⇒ 报错；无种子口径时 take 无从生效 ⇒ 报错。"""
    import pytest

    block = [dict(i) for i in P0[:2]]
    block[0]["take"], block[1]["take"] = 1, 2
    with pytest.raises(ValueError, match="同一块内出现多次"):
        tts.block_sampling(block, {"seed": 4242})
    with pytest.raises(ValueError, match="需要种子"):
        tts.block_sampling(block[1:], {})


def test_block_take_reaches_request_and_digest(monkeypatch, tmp_path):
    """take 进请求种子与成员摘要：同块加 take 即缓存失配、按新种子重录。"""
    seeds: list[int] = []

    def fake(server, text, ref, vec, alpha, df, lang, beams, weights, d, p, sampling):
        seeds.append(sampling["seed"])
        clips = [_clip() for _ in weights]
        return {"split": "ok", "clips": clips, "cuts": [], "seams": []}

    monkeypatch.setattr(tts, "http_synthesize_block", fake)
    monkeypatch.setattr(tts, "mp3_duration", lambda _p: 2.0)
    block = [dict(i) for i in P0[:2]]
    _run_block(block, tmp_path, sampling={"seed": 4242})
    before = (tmp_path / "p0-01.sha").read_text()
    block[1]["take"] = 2
    _run_block(block, tmp_path, sampling={"seed": 4242})
    assert seeds == [4242, 4244]
    assert (tmp_path / "p0-01.sha").read_text() != before


def _story_plan(proj: Path, ref: Path):
    import subprocess

    return subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts" / "tts.py"),
            "--project",
            str(proj),
            "--engine",
            "indextts",
            "--ref",
            str(ref),
            "--style",
            "story",
            "--no-store",
            "--plan",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=proj.parent,
    )


def test_plan_matches_synth_digest_with_take(monkeypatch, tmp_path):
    """--plan 与合成同一 take 口径：带 take 合成后排期整块命中（两处各算摘要，防漂移）。"""
    import asyncio
    import hashlib
    import json

    proj = tmp_path / "ep"
    (proj / "script").mkdir(parents=True)
    items = [dict(i) for i in P0[:3]]
    items[1]["take"] = 1
    (proj / "script" / "narration.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"x" * 16)
    audio = proj / "video" / "public" / "audio"
    audio.mkdir(parents=True)
    p = tts.STYLE_PRESETS["story"]
    monkeypatch.setattr(
        tts,
        "http_synthesize_block",
        lambda *a: {"split": "ok", "clips": [_clip() for _ in a[8]], "seams": []},
    )
    monkeypatch.setattr(tts, "mp3_duration", lambda _p: 2.0)
    for b in tts.plan_blocks(items, p["block"]):
        asyncio.run(
            tts.synth_block_indextts(
                asyncio.Semaphore(1),
                b,
                False,
                str(ref),
                hashlib.sha1(ref.read_bytes()).hexdigest()[:12],
                "story",
                p["vec"],
                p["alpha"],
                p["df"],
                "ZH",
                "indextts",
                "http://unused",
                audio,
                sampling={"seed": p["seed"]},
            )
        )
    r = _story_plan(proj, ref)
    assert r.returncode == 0, r.stderr
    assert "待合成 0 块" in r.stdout


def test_plan_rejects_two_takes_in_one_block(tmp_path):
    """同块多条 take 在 --plan（长跑前）即报错退出。"""
    import json

    proj = tmp_path / "ep"
    (proj / "script").mkdir(parents=True)
    items = [dict(i) for i in P0[:2]]
    items[0]["take"], items[1]["take"] = 1, 2
    (proj / "script" / "narration.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"x" * 16)
    r = _story_plan(proj, ref)
    assert r.returncode != 0 and "同一块内出现多次" in r.stderr


def test_sample_all_styles_applies_preset_seed(tmp_path):
    """--all-styles 逐档解析采样口径：story 档带预设 seed，其余档不被波及。"""
    import os
    import subprocess

    script = Path(__file__).resolve().parents[1] / "scripts" / "tts_sample.py"
    (tmp_path / ".to-video-root").write_text("", encoding="utf-8")
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"x" * 16)
    r = subprocess.run(
        [sys.executable, str(script), "--ref", str(ref), "--all-styles", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,
        env={**os.environ, "TO_VIDEO_WORKSPACE": str(tmp_path)},
    )
    assert r.returncode == 0, r.stderr
    lines = {ln.split()[0]: ln for ln in r.stdout.splitlines() if ln.startswith("   ")}
    assert f"seed={tts.STYLE_PRESETS['story']['seed']}" in lines["story"]
    assert "seed=" not in lines["sunny"]


# ---------------- 进度监视：mtime 聚簇 ----------------


def _progress(tmp_path, texts: list[str], mtimes: list[float]) -> str:
    """造工程：前 len(mtimes) 句已产出（mp3 mtime 按给定序列），跑 tts_progress 取 stdout。"""
    import json
    import os
    import subprocess

    items = [
        {"id": f"p0-{k:02d}", "scene": "P0", "text": t} for k, t in enumerate(texts)
    ]
    (tmp_path / "script").mkdir()
    (tmp_path / "script" / "narration.json").write_text(
        json.dumps(items, ensure_ascii=False), encoding="utf-8"
    )
    audio = tmp_path / "video" / "public" / "audio"
    audio.mkdir(parents=True)
    base = 1_700_000_000.0
    for item, t in zip(items, mtimes):
        p = audio / f"{item['id']}.mp3"
        p.write_bytes(b"x")
        os.utime(p, (base + t, base + t))
    script = Path(__file__).resolve().parents[1] / "scripts" / "tts_progress.py"
    r = subprocess.run(
        [sys.executable, str(script), "--project", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return r.stdout


def test_progress_wall_pairs_with_its_own_sentence(tmp_path):
    """逐句口径：墙钟 t(k+1)−t(k) 是第 k+1 句的合成耗时，除以第 k+1 句字数；末句计入。"""
    # 10 字 / 2 字 / 20 字 已产出，末句待合成：秒/字 = [10/2, 20/20] → 中位 3.0
    out = _progress(tmp_path, ["一" * 10, "二" * 2, "三" * 20, "四" * 5], [0, 10, 30])
    assert "中位 3.000" in out


def test_progress_clusters_block_writes(tmp_path):
    """块口径：<1s 内落盘的 N 句聚成一次合成，墙钟除以下一簇总字数。"""
    # 簇 A（10+10 字 @0/0.2s）→ 簇 B（15+5 字 @40/40.3s）：40s / 20 字 = 2.0
    out = _progress(
        tmp_path,
        ["甲" * 10, "乙" * 10, "丙" * 15, "丁" * 5, "戊" * 3],
        [0, 0.2, 40, 40.3],
    )
    assert "中位 2.000" in out


def test_progress_single_cluster_reports_insufficient_samples(tmp_path):
    """单簇但跨度 ≥1s（连续 <1s 间隔串起）：无墙钟样本，报不足而非 StatisticsError。"""
    out = _progress(tmp_path, ["甲" * 5] * 4, [0, 0.6, 1.2])
    assert "样本不足" in out
