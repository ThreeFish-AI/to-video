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
    assert payload == {"fails": [], "warns": []}


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
