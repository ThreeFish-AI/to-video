"""tts.py 的内联语言镜像表与导入边界执法。

tts.py 受 paths.py「导入边界」约束（会被拷进 ~/tools/index-tts 的 venv 单独运行），
不得 import 任何同目录模块——语言常数只能在文件内镜像。镜像与 langs.LANGS
注册表的一致性由此钉住（timing.json「TS/Python 双语共读」的同构纪律）：
注册表换音色/加语言而镜像未跟，这里先红。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import langs  # noqa: E402
import tts  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def test_lang_mirror_matches_registry():
    """镜像表逐语言等于 langs.LANGS 的 tts_code/edge_voice。"""
    assert set(tts.LANG_MIRROR) == set(langs.LANGS), (
        f"语言集漂移：tts.py 镜像 {sorted(tts.LANG_MIRROR)} ≠ 注册表 "
        f"{sorted(langs.LANGS)}"
    )
    for lang, spec in langs.LANGS.items():
        tts_code, voice = tts.LANG_MIRROR[lang]
        assert tts_code == spec.tts_code, f"{lang}: tts_code 镜像漂移"
        assert voice == spec.edge_voice, f"{lang}: edge 音色镜像漂移"


def _imported_top_levels(tree: ast.Module) -> set[str]:
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            mods.add(node.module.split(".")[0])
    return mods


def test_tts_does_not_import_sibling_modules():
    """导入边界（承重）：tts.py 不得 import 同目录模块——它会被拷进 index-tts
    的 venv 运行，任何同目录依赖都会断掉那条拷出路径。AST 扫描 import 语句，
    同目录集合从 scripts/*.py 现存文件派生（新增脚本自动进执法面）。"""
    tree = ast.parse((SCRIPTS / "tts.py").read_text(encoding="utf-8"))
    siblings = {p.stem for p in SCRIPTS.glob("*.py")}
    offenders = _imported_top_levels(tree) & siblings
    assert not offenders, (
        f"tts.py 引入了同目录依赖 {sorted(offenders)}——违反 paths.py 导入边界，"
        "拷进 ~/tools/index-tts 后会 ModuleNotFoundError"
    )


def test_tts_text_mappings_are_zh_only():
    """全角破折号/省略号映射仅对 ZH 生效；en 原样透传；缺省参数向后兼容 ZH。"""
    assert tts.tts_text("破折——号。", "ZH") == "破折，号。"
    assert tts.tts_text("省略……结束。", "ZH") == "省略。结束。"
    assert tts.tts_text("wait—— here…", "EN") == "wait—— here…"
    assert tts.tts_text("缺省即 ZH——不变") == "缺省即 ZH，不变"


def _run_tts(*argv: str):
    import subprocess

    return subprocess.run(
        [sys.executable, str(SCRIPTS / "tts.py"), *argv],
        capture_output=True,
        text=True,
        check=False,
        cwd=SCRIPTS,
    )


@pytest.mark.parametrize(
    "argv",
    [
        ("--narration-lang", "en", "--engine", "edge", "--lang", "ZH"),
        # indextts 同样须拦：此前一致性只在 edge 的 clone_only 护栏里校验，
        # indextts 会以 ZH 归一化合成英文稿写进 audio/en/
        ("--narration-lang", "en", "--engine", "indextts", "--lang", "ZH"),
        ("--narration-lang", "zh", "--engine", "indextts", "--lang", "EN"),
    ],
)
def test_explicit_lang_conflict_rejected(argv):
    """显式 --lang 与 --narration-lang 的镜像解析值冲突 ⇒ 两引擎统一 argparse
    报错（exit 2），在读取工程文件之前拦下。"""
    r = _run_tts(*argv, "--ref", "unused.wav")
    assert r.returncode == 2
    assert "冲突" in r.stderr


def test_narration_lang_resolves_not_falls_back():
    """`--narration-lang en` 时未显式给 --lang/--voice ⇒ 解析 EN 与英文音色，
    绝不静默回落 ZH/中文音色（digest 与音色都会错槽位）。

    经 subprocess 走 argparse 真路径：不带 --lang、或显式给出与镜像一致的值
    都不拦（正常路径，因缺工程文件退出，消息不含冲突/克隆参数误用提示）。"""
    for extra in ((), ("--lang", "EN")):
        r = _run_tts("--narration-lang", "en", "--engine", "edge", *extra)
        assert r.returncode != 0  # cwd=SCRIPTS 无 narration.en.json，大声退出
        msg = r.stderr + r.stdout
        assert "仅对 --engine indextts 生效" not in msg  # 不因解析 EN 而误拦
        assert "冲突" not in msg
        assert "narration.en.json 不存在" in msg


def test_tts_inline_path_shapes_mirror_langs():
    """输出槽位路径的内联派生与 langs 同构（源码文本断言，同 test_skeleton 对
    i18n.tsx audioDir 的钉法）：`audio/<lang>` 子目录与 `narration<sfx>.json`
    后缀规则在 tts.py 里是手工镜像，注册表改约定而镜像未跟，这里先红。"""
    src = (SCRIPTS / "tts.py").read_text(encoding="utf-8")
    assert (
        '"audio" / args.narration_lang' in src
        or "audio_base / args.narration_lang" in src.replace("audio", '"audio"')
        or "/ lang" in src
    ), "tts.py 缺 audio/<lang> 输出目录派生（形态变了？检测器该更新）"
    assert 'f".{args.narration_lang}"' in src, "tts.py 缺 .<lang> 后缀派生"
    assert 'f"narration{sfx}.json"' in src, "tts.py 缺 narration<sfx>.json 输入派生"


def test_tts_progress_word_regex_matches_langs():
    """tts_progress 的 _WORD_RE 与 langs._WORD_RE 同一份正则（tts_progress 受
    同款导入边界约束只能内联；两处漂移会让 en 滚动速率口径分叉）。"""
    import re as _re

    tp_src = (SCRIPTS / "tts_progress.py").read_text(encoding="utf-8")
    m = _re.search(r"_WORD_RE = re\.compile\((r\"[^\"]+\")\)", tp_src)
    assert m, "tts_progress._WORD_RE 形态变化，检测器该更新"
    assert _re.compile(eval(m.group(1))).pattern == langs._WORD_RE.pattern, (
        "tts_progress 词计数正则与 langs._WORD_RE 漂移"
    )
