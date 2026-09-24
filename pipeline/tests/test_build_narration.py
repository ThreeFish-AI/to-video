"""build_narration 解析/校验分支（经 subprocess 走真实 CLI 入口）。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_narration.py"


def run_build(root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--project", str(root), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def make_project(tmp_path: Path, md: str) -> Path:
    root = tmp_path / "ep"
    (root / "script").mkdir(parents=True)
    (root / "script" / "narration.md").write_text(md, encoding="utf-8")
    return root


def test_happy_path_and_golden_json(tmp_path):
    root = make_project(
        tmp_path,
        "## P0 开场\n\n- [p0-01] 甲句。\n> 备注不入稿\n- [p0-02] 乙句。\n\n## 不相关标题\n",
    )
    r = run_build(root)
    assert r.returncode == 0, r.stderr
    data = json.loads((root / "script" / "narration.json").read_text(encoding="utf-8"))
    assert data == [
        {"id": "p0-01", "scene": "P0", "text": "甲句。"},
        {"id": "p0-02", "scene": "P0", "text": "乙句。"},
    ]
    assert "不相关标题" not in json.dumps(data, ensure_ascii=False)


def test_missing_file_actionable_exit(tmp_path):
    root = tmp_path / "empty"
    (root / "script").mkdir(parents=True)
    r = run_build(root)
    assert r.returncode != 0
    assert "narration.md 不存在" in r.stderr or "narration.md 不存在" in r.stdout


def test_duplicate_id(tmp_path):
    root = make_project(tmp_path, "## P0\n- [p0-01] 甲。\n- [p0-01] 乙。\n")
    r = run_build(root)
    assert r.returncode != 0
    assert "重复句 id" in (r.stderr + r.stdout)


def test_scene_prefix_mismatch_names_scene(tmp_path):
    root = make_project(tmp_path, "## P1\n- [p1-01] 对。\n- [p0-09] 错。\n")
    r = run_build(root)
    assert r.returncode != 0
    assert "p0-09" in (r.stderr + r.stdout) and "P1" in (r.stderr + r.stdout)


def test_sentence_before_any_scene_heading(tmp_path):
    root = make_project(tmp_path, "- [p0-01] 无幕句。\n\n## P0\n- [p0-02] 有幕句。\n")
    r = run_build(root)
    assert r.returncode != 0
    assert "## Pn" in (r.stderr + r.stdout)  # 报真正原因而非「与所在幕  不一致」


def test_series_layer_published_requires_ready_and_online_marker(tmp_path):
    influence = tmp_path / "influence"
    root = influence / "episodes" / "episode-one"
    (root / "script").mkdir(parents=True)
    (root / "script" / "narration.md").write_text(
        "## P0\n- [p0-01] 测试。\n", encoding="utf-8"
    )
    (influence / "series.json").write_text(
        json.dumps(
            {
                "seriesList": [
                    {
                        "id": "series-one",
                        "episodes": [
                            {
                                "path": "episodes/episode-one",
                                "cardSub": "第一层 · 循环",
                                "title": "未上线",
                                "status": "ready",
                                "voice": "配音已完成",
                            },
                            {
                                "path": "episodes/episode-two",
                                "cardSub": "第二层 · 循环",
                                "title": "已上线",
                                "status": "ready",
                                "voice": "已上线 · 定稿",
                            },
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    r = run_build(root)

    assert r.returncode == 0, r.stderr
    layers = json.loads(
        (root / "video" / "src" / "series-layers.json").read_text(encoding="utf-8")
    )["layers"]
    assert [layer["published"] for layer in layers] == [False, True]


def test_chapters_json_emitted_from_scene_titles(tmp_path):
    """`## Pn 标题` 的标题文字此前被 SCENE_RE 丢弃；现须落盘 chapters.json（顶部
    进度条数据面），按 narration.md 出现序；重跑 build 字节不变（纯派生幂等）。"""
    root = make_project(
        tmp_path, "## P0 冷开场\n- [p0-01] 甲。\n\n## P1 展开\n- [p1-01] 乙。\n"
    )
    r = run_build(root)
    assert r.returncode == 0, r.stderr
    path = root / "video" / "src" / "chapters.json"
    assert json.loads(path.read_text(encoding="utf-8")) == [
        {"scene": "P0", "title": "冷开场"},
        {"scene": "P1", "title": "展开"},
    ]
    first = path.read_text(encoding="utf-8")
    assert run_build(root).returncode == 0
    assert path.read_text(encoding="utf-8") == first


def test_chapters_title_fallback_and_separator_forms(tmp_path):
    """无标题幕写空串（组件回退只显 PART n）；全角冒号分隔合法；非 Pn 标题不入。"""
    root = make_project(
        tmp_path,
        "## P0\n- [p0-01] 甲。\n\n## P1：冒号标题\n- [p1-01] 乙。\n\n## 不相关标题\n",
    )
    r = run_build(root)
    assert r.returncode == 0, r.stderr
    assert json.loads(
        (root / "video" / "src" / "chapters.json").read_text(encoding="utf-8")
    ) == [
        {"scene": "P0", "title": ""},
        {"scene": "P1", "title": "冒号标题"},
    ]


# ---------------- 双语构建：--lang en / 硬对齐门 / 基线锁 / chapters i18n ----------------

ZH_MD = "## P0 开场\n- [p0-01] 第一句。\n- [p0-02] 第二句。\n"
EN_MD_OK = "## P0 Opening\n- [p0-01] First sentence.\n- [p0-02] Second sentence.\n"
TOML_BI = (
    '[episode]\nslug = "ep-bi"\n[narration]\ntarget_minutes = [1.0, 2.0]\n'
    'langs = ["zh", "en"]\n'
)


def make_bi_project(
    tmp_path: Path, zh_md: str, en_md: str | None, toml: str | None = None
) -> Path:
    root = tmp_path / "ep-bi"
    (root / "script").mkdir(parents=True)
    (root / "script" / "narration.md").write_text(zh_md, encoding="utf-8")
    if en_md is not None:
        (root / "script" / "narration.en.md").write_text(en_md, encoding="utf-8")
    if toml is not None:
        (root / "pipeline.toml").write_text(toml, encoding="utf-8")
    return root


def _zh_digest(text: str) -> str:
    """与 build_narration.zh_digest 同口径（sha1 前 12 位）——锁内容的期望值。"""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def test_en_build_happy_path_json_and_lock(tmp_path):
    root = make_bi_project(tmp_path, ZH_MD, EN_MD_OK)
    r = run_build(root, "--lang", "en")
    assert r.returncode == 0, r.stderr
    data = json.loads(
        (root / "script" / "narration.en.json").read_text(encoding="utf-8")
    )
    assert data == [
        {"id": "p0-01", "scene": "P0", "text": "First sentence."},
        {"id": "p0-02", "scene": "P0", "text": "Second sentence."},
    ]
    # 各语言各槽位：en build 不改写主稿产物
    assert not (root / "script" / "narration.json").exists()
    # 基线锁内容黄金：{句id: {zh: 主稿句 digest, en: 译句 digest}}（pron 剥离口径）
    want = {
        "p0-01": {"zh": _zh_digest("第一句。"), "en": _zh_digest("First sentence.")},
        "p0-02": {"zh": _zh_digest("第二句。"), "en": _zh_digest("Second sentence.")},
    }
    lock_raw = (root / "script" / "narration.en.lock.json").read_text(encoding="utf-8")
    assert json.loads(lock_raw) == want
    assert lock_raw == json.dumps(want, ensure_ascii=False, indent=1) + "\n"
    # 词数口径的时长估算（words_per_min 默认 150，缺 toml 经 config.default 兜底）
    assert "总词数" in r.stdout and "词/分" in r.stdout


@pytest.mark.parametrize(
    ("en_md", "frag"),
    [
        ("## P0 Opening\n- [p0-01] Only first.\n", "缺句"),
        (
            "## P0 Opening\n- [p0-01] A.\n- [p0-02] B.\n- [p0-03] C.\n",
            "多句",
        ),
        ("## P0 Opening\n- [p0-02] B.\n- [p0-01] A.\n", "句序"),
        (
            "## P0 Opening\n- [p0-01] A.\n- [p0-02] B.\n\n## P9 Tail\n",
            "幕集合",
        ),
    ],
)
def test_en_alignment_mismatches_fail(tmp_path, en_md, frag):
    """硬对齐门四类失配各自点名（缺句 / 多句 / 乱序 / 换幕），FAIL 大声退出。"""
    root = make_bi_project(tmp_path, ZH_MD, en_md)
    r = run_build(root, "--lang", "en")
    assert r.returncode != 0
    out = r.stderr + r.stdout
    assert "对齐" in out and frag in out, out
    # 对齐失败不产出译稿 json 与锁
    assert not (root / "script" / "narration.en.json").exists()
    assert not (root / "script" / "narration.en.lock.json").exists()


def test_en_build_requires_zh_master(tmp_path):
    """主稿缺失 / 主稿自身带结构病：译稿构建以主稿为基准，先修主稿。"""
    root = tmp_path / "ep-bi"
    (root / "script").mkdir(parents=True)
    (root / "script" / "narration.en.md").write_text(EN_MD_OK, encoding="utf-8")
    r = run_build(root, "--lang", "en")
    assert r.returncode != 0
    assert "主稿" in (r.stderr + r.stdout)

    root2 = make_bi_project(tmp_path / "case2", ZH_MD, EN_MD_OK)
    (root2 / "script" / "narration.md").write_text(
        "## P0\n- [p0-01] 甲。\n- [p0-01] 乙。\n", encoding="utf-8"
    )
    r2 = run_build(root2, "--lang", "en")
    assert r2.returncode != 0
    assert "主稿" in (r2.stderr + r2.stdout) and "重复句 id" in (r2.stderr + r2.stdout)


ZH_MD_EDITED = "## P0 开场\n- [p0-01] 第一句改。\n- [p0-02] 第二句。\n"
CHECK = Path(__file__).resolve().parents[1] / "scripts" / "check_script.py"


def _lock(root: Path) -> dict:
    return json.loads(
        (root / "script" / "narration.en.lock.json").read_text(encoding="utf-8")
    )


def test_lock_keeps_zh_baseline_until_retranslated(tmp_path):
    """fuzzy 语义：主稿改稿后重建 en、译句未动 ⇒ 锁保留旧主稿 digest（失鲜持续
    可测）并点名待复核；译句改写（重译）后自动刷新。缺省 build 先 zh 后 en，
    若重建即刷新，check 之前失鲜信号就被抹掉。"""
    root = make_bi_project(tmp_path, ZH_MD, EN_MD_OK)
    assert run_build(root, "--lang", "en").returncode == 0
    lock1 = _lock(root)
    (root / "script" / "narration.md").write_text(ZH_MD_EDITED, encoding="utf-8")

    r = run_build(root, "--lang", "en")
    assert r.returncode == 0, r.stderr
    assert _lock(root) == lock1  # 译句未动：主稿基线不前移
    assert "待复核 1 句" in r.stderr and "p0-01" in r.stderr and "--accept" in r.stderr

    (root / "script" / "narration.en.md").write_text(
        EN_MD_OK.replace("First sentence.", "First sentence, revised."),
        encoding="utf-8",
    )
    r = run_build(root, "--lang", "en")
    assert r.returncode == 0, r.stderr
    lock3 = _lock(root)
    assert lock3["p0-01"] == {
        "zh": _zh_digest("第一句改。"),
        "en": _zh_digest("First sentence, revised."),
    }
    assert lock3["p0-02"] == lock1["p0-02"]
    assert "待复核" not in r.stderr


def test_lock_accept_confirms_without_retranslation(tmp_path):
    """--accept <ids> / all：确认译文无需改动，按当前主稿刷新基线；未知 id 与主稿
    构建带 --accept 大声失败（parse 了却不生效的 flag 等于静默缩小操作面）。"""
    root = make_bi_project(tmp_path, ZH_MD, EN_MD_OK)
    assert run_build(root, "--lang", "en").returncode == 0
    (root / "script" / "narration.md").write_text(ZH_MD_EDITED, encoding="utf-8")

    bad = run_build(root, "--lang", "en", "--accept", "p9-99")
    assert bad.returncode != 0 and "p9-99" in (bad.stderr + bad.stdout)
    zh_bad = run_build(root, "--accept", "all")
    assert zh_bad.returncode != 0 and "--accept" in zh_bad.stderr

    r = run_build(root, "--lang", "en", "--accept", "p0-01")
    assert r.returncode == 0, r.stderr
    assert _lock(root)["p0-01"]["zh"] == _zh_digest("第一句改。")
    assert "待复核" not in r.stderr


def test_lock_corrupt_requires_explicit_accept_all(tmp_path):
    """坏锁不静默重置为「全部已复核」：无 --accept all 即大声退出且不写任何产物。"""
    root = make_bi_project(tmp_path, ZH_MD, EN_MD_OK)
    lock_path = root / "script" / "narration.en.lock.json"
    lock_path.write_text('{"p0-01": "legacy-flat"}\n', encoding="utf-8")

    r = run_build(root, "--lang", "en")
    assert r.returncode != 0 and "--accept all" in (r.stderr + r.stdout)
    assert not (root / "script" / "narration.en.json").exists()

    assert run_build(root, "--lang", "en", "--accept", "all").returncode == 0
    assert _lock(root)["p0-01"]["zh"] == _zh_digest("第一句。")


def test_stale_translation_survives_default_build_order(tmp_path):
    """端到端回归：文档流程「改主稿 → build（先 zh 后 en）→ check --lang en」必须
    FAIL 点名失配句——此前重建即刷新锁，check 永远放行旧译文。"""
    root = make_bi_project(tmp_path, ZH_MD, EN_MD_OK, TOML_BI)
    for lang in ("zh", "en"):
        assert run_build(root, "--lang", lang).returncode == 0
    (root / "script" / "narration.md").write_text(ZH_MD_EDITED, encoding="utf-8")
    for lang in ("zh", "en"):
        assert run_build(root, "--lang", lang).returncode == 0

    r = subprocess.run(
        [sys.executable, str(CHECK), "--project", str(root)]
        + ["--pre-tts", "--lang", "en"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 1, r.stdout + r.stderr
    assert "基线锁失配" in r.stdout and "p0-01" in r.stdout


def test_chapters_i18n_emitted_when_declared_and_present(tmp_path):
    """声明 en 且 narration.en.md 在：条目附 i18n（en 幕标题）；zh / en 两种
    build 产出同一 chapters.json（确定性）。"""
    root = make_bi_project(tmp_path, ZH_MD, EN_MD_OK, TOML_BI)
    r = run_build(root)
    assert r.returncode == 0, r.stderr
    path = root / "video" / "src" / "chapters.json"
    assert json.loads(path.read_text(encoding="utf-8")) == [
        {"scene": "P0", "title": "开场", "i18n": {"en": "Opening"}}
    ]
    first = path.read_text(encoding="utf-8")
    assert run_build(root, "--lang", "en").returncode == 0
    assert path.read_text(encoding="utf-8") == first


def test_chapters_zh_only_stay_byte_identical(tmp_path):
    """langs 未声明 en：即使 narration.en.md 碰巧存在也不带 i18n（语言激活的
    唯一来源是声明，不看文件存在与否），输出与改造前字节一致。"""
    root = make_bi_project(tmp_path, ZH_MD, EN_MD_OK)  # 无 pipeline.toml
    r = run_build(root)
    assert r.returncode == 0, r.stderr
    assert (root / "video" / "src" / "chapters.json").read_text(encoding="utf-8") == (
        json.dumps([{"scene": "P0", "title": "开场"}], ensure_ascii=False, indent=1)
        + "\n"
    )


def test_chapters_i18n_degrades_when_en_md_missing(tmp_path):
    """声明 en 但文件缺失：WARN 降级、不带 i18n——zh build 永不为 en 文件失败。"""
    root = make_bi_project(tmp_path, ZH_MD, None, TOML_BI)
    r = run_build(root)
    assert r.returncode == 0, r.stderr
    assert "WARN" in r.stderr and "narration.en.md" in r.stderr
    assert json.loads(
        (root / "video" / "src" / "chapters.json").read_text(encoding="utf-8")
    ) == [{"scene": "P0", "title": "开场"}]


def test_chapters_i18n_degrades_when_en_md_broken(tmp_path):
    """en 文件解析失败（重复句 id）：zh build 降级 WARN；en build 自己硬失败。"""
    broken = "## P0 Opening\n- [p0-01] Fine.\n- [p0-01] Dup.\n"
    root = make_bi_project(tmp_path, ZH_MD, broken, TOML_BI)
    r = run_build(root)
    assert r.returncode == 0, r.stderr
    assert "WARN" in r.stderr and "narration.en.md" in r.stderr
    assert json.loads(
        (root / "video" / "src" / "chapters.json").read_text(encoding="utf-8")
    ) == [{"scene": "P0", "title": "开场"}]
    r2 = run_build(root, "--lang", "en")
    assert r2.returncode != 0
    assert "重复句 id" in (r2.stderr + r2.stdout)


def test_series_layers_i18n_passthrough(tmp_path):
    """series.json 集条目 / next 的可选 i18n 透传为 titleI18n / nextI18n；
    无 i18n 的条目不加键（zh-only 字节不变由既有 series-layers 用例守）。"""
    influence = tmp_path / "influence"
    root = influence / "episodes" / "episode-one"
    (root / "script").mkdir(parents=True)
    (root / "script" / "narration.md").write_text(
        "## P0\n- [p0-01] 测试。\n", encoding="utf-8"
    )
    (influence / "series.json").write_text(
        json.dumps(
            {
                "seriesList": [
                    {
                        "id": "series-one",
                        "episodes": [
                            {
                                "path": "episodes/episode-one",
                                "cardSub": "第一层 · 循环",
                                "title": "循环",
                                "i18n": {"en": "The Loop"},
                                "status": "ready",
                                "voice": "配音已完成",
                            },
                            {
                                "path": "episodes/episode-two",
                                "cardSub": "第二层 · 视野",
                                "title": "视野",
                                "status": "ready",
                                "voice": "已上线 · 定稿",
                            },
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    r = run_build(root)
    assert r.returncode == 0, r.stderr
    payload = json.loads(
        (root / "video" / "src" / "series-layers.json").read_text(encoding="utf-8")
    )
    assert payload["layers"][0]["titleI18n"] == {"en": "The Loop"}  # 有则透传
    assert "titleI18n" not in payload["layers"][1]  # 无则不加键
    assert "nextI18n" not in payload  # next 无 i18n 同样不加键
