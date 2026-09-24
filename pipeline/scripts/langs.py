#!/usr/bin/env python3
"""语言注册表与双语产物路径派生——「语言」维度的唯一机制事实源。

## 为什么需要它

此前全链路是「单语言单槽位」：narration.json / audio/{id}.mp3 / captions.srt /
final.mp4 各只有一个路径，语言相关常数（tts lang 码、edge 音色、长度单位）散落
在各消费者里硬编码。双语化把语言建模为与九阶段正交的独立维度，分三层（RSI-004）：

  机制（本模块）  语言注册表 + 路径派生规则 + 长度单位——纯函数、零 IO
  策略（config）  pipeline.toml 的 narration.langs / [narration.en] / [tts.en]
  执行（pipeline）--lang 运行期选择

## 路径约定（主语言恒等，防既有集回归）

主语言（zh）**不加后缀、路径逐字节等于改造前**；非主语言在文件名主干后加
`.<lang>` 后缀、配音落同名子目录（`movie.en.srt` 业界惯例）：

  script/narration{sfx}.md / .json / .lock.json
  video/public/audio/            （zh）
  video/public/audio/<lang>/     （非主语言，含独立 .engine 签名与 manifest）
  out/captions{sfx}.{srt,vtt} · out/{draft,final}{sfx}.mp4 · out/frames{sfx}/

## 导入边界（承重，勿破）

本模块**不得** import paths / config（保持零工作区锚、可被任何脚本含 check 族
直接 import）。反向红线：**tts.py / tts_server.py 不得 import 本模块**——它们会被
拷进 ~/tools/index-tts 的 venv 单独运行（见 paths.py 导入边界），同目录依赖会断掉
那条拷出路径；tts.py 持内联最小镜像表，与 LANGS 的一致性由
tests/test_langs.py 钉住（timing.json「TS/Python 双语共读」的同构纪律）。TS 侧
镜像为模板 video/src/i18n.tsx 的 audioDir()，同受测试执法。

用法示例：
  from langs import PRIMARY, LANGS, suffix, narration_json, parse_selection
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple


class LangSpec(NamedTuple):
    """一种语言的机制常数（策略偏离走 config 的 per-lang 覆写表）。"""

    #: IndexTTS infer(lang=...) 取值（合法集 ZH/EN/JA/AR/ES，见 INDEXTTS-2.5-ADVANCED §2.1）
    tts_code: str
    #: edge-tts 预置音色（engine=edge 时的该语言缺省）
    edge_voice: str
    #: 长度单位名（预算门打印口径）：zh 数字符、en 数词
    unit: str
    #: 未合成句的外推语速起步值（单位随 unit：zh 字/秒为首集实测 300 字/分；
    #: en 词/秒 2.5 仅量级参考，首集英文长跑实测后校准）。消费者：qa_frames
    #: --stills-plan 未显式给 --chars-per-sec 时取此缺省（语言相关常数内联在
    #: 消费者属 RSI-004 后续防范明令禁止的形态）。
    stills_rate: float


#: 语言注册表。新增语言 = 加一行 + config.SCHEMA 补对应覆写键 + i18n.tsx 扩类型，
#: 三处一致性由 tests/test_langs.py 与 test_skeleton 执法。
LANGS: dict[str, LangSpec] = {
    "zh": LangSpec("ZH", "zh-CN-YunxiNeural", "字", 5.0),
    "en": LangSpec("EN", "en-US-AndrewNeural", "词", 2.5),
}

#: 主语言 = 中文主稿（SSOT）。英文等译稿与之句 id 1:1 对齐（check_script 执法）。
PRIMARY = "zh"

#: 英文词计数：字母数字串，允许撇号/连字符内连（don't / state-of-the-art 各计 1 词）。
_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’‐-―-][A-Za-z0-9]+)*")


def validate(lang: str) -> str:
    """→ lang（原样）。未知语言大声失败——静默回落会产出错版视频。"""
    if lang not in LANGS:
        raise ValueError(
            f"未知语言 {lang!r}：注册表只有 {sorted(LANGS)}（langs.py 是唯一事实源）"
        )
    return lang


def suffix(lang: str) -> str:
    """→ 路径后缀：主语言空串（既有路径逐字节不变），其余 `.<lang>`。"""
    validate(lang)
    return "" if lang == PRIMARY else f".{lang}"


# ---------------- 路径派生（root = 分集工程根 $P） ----------------


def narration_md(root: Path, lang: str) -> Path:
    return root / "script" / f"narration{suffix(lang)}.md"


def narration_json(root: Path, lang: str) -> Path:
    return root / "script" / f"narration{suffix(lang)}.json"


def lock(root: Path, lang: str) -> Path:
    """译稿基线锁：翻译时主稿句文本的 digest 快照（gettext msgid 同构）。
    仅非主语言有意义——主稿自身没有「对齐对象」。"""
    return root / "script" / f"narration{suffix(lang)}.lock.json"


def audio_dir(root: Path, lang: str) -> Path:
    """逐句 mp3 / manifest.json / .engine 签名所在目录（签名护栏按目录独立）。"""
    d = root / "video" / "public" / "audio"
    return d if lang == PRIMARY else d / lang


def manifest(root: Path, lang: str) -> Path:
    return audio_dir(root, lang) / "manifest.json"


def captions(root: Path, lang: str, fmt: str) -> Path:
    return root / "out" / f"captions{suffix(lang)}.{fmt}"


def render_out(root: Path, kind: str, lang: str) -> Path:
    """kind ∈ {'draft', 'final'} → out/<kind><sfx>.mp4（终渲槽位语义不变）。"""
    if kind not in ("draft", "final"):
        raise ValueError(f"kind 应为 'draft' | 'final'，实际 {kind!r}")
    return root / "out" / f"{kind}{suffix(lang)}.mp4"


def frames_dir(root: Path, lang: str) -> Path:
    return root / "out" / f"frames{suffix(lang)}"


# ---------------- 长度单位（预算门 / 语速外推共用口径） ----------------


def length(text: str, lang: str) -> int:
    """→ 该语言口径的「长度」：zh 数码点（与既有 len(text) 口径一致，防黄金漂移）、
    en 数词。语速常数按语言各配（chars_per_min / words_per_min），互不换算。"""
    validate(lang)
    return len(text) if lang == PRIMARY else len(_WORD_RE.findall(text))


# ---------------- 运行期选择解析（--lang 的唯一解析处） ----------------


def parse_selection(arg: str | None, declared: list[str]) -> list[str] | None:
    """→ 选中的语言列表；arg 为 None 时返回 None（缺省策略归调用方——昂贵命令
    显式化：tts/render/deliver 缺省只跑主语言，build/check/captions/status 缺省
    跑全部声明语言，两种缺省语义不同，不能在本处一刀切）。

    取值：'all' = 全部声明语言；否则逗号分隔的语言码。逐项须已在本集
    narration.langs 声明（防 `--lang en` 在未声明 en 的集上静默跑半套）；
    去重保序；空串/空白项报错。
    """
    if arg is None:
        return None
    picked = (
        list(declared) if arg.strip() == "all" else [x.strip() for x in arg.split(",")]
    )
    if not picked or any(not x for x in picked):
        raise ValueError(f"--lang 取值非法：{arg!r}（可选 'all' 或逗号分隔语言码）")
    out: list[str] = []
    for x in picked:
        validate(x)
        if x not in declared:
            raise ValueError(
                f"语言 {x!r} 未在本集 narration.langs 声明（已声明 {declared}；"
                "先在 pipeline.toml 声明再产出该语言版本）"
            )
        if x not in out:
            out.append(x)
    return out
