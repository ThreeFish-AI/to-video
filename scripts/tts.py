#!/usr/bin/env python3
"""逐句合成配音并产出时长 manifest——公共管线版本（双引擎）。

- 输入：<工程>/script/narration.json（单一事实源派生）
- 输出：<工程>/video/public/audio/{id}.mp3 + <工程>/video/public/audio/manifest.json
- 引擎：
  - edge（默认）：edge-tts 预置音色，免密钥，行为与历史版本完全一致；
  - indextts：声音克隆（IndexTTS-2.5 本地服务），需先启动 tts_server.py，
    通过 --ref 提供参考音色样本、--style 选择风格（sunny 明快阳光为推荐位，
    sunny-steady 为其定稿档＝同参数 + 束宽 3；另有激情/轻快/自信/正能量）。
- 幂等：参数与文本未变则跳过（SHA1 摘要 sidecar 缓存）。
- 版本库（indextts）：合成成功的句子按 digest 存入机器级持久库（默认
  ~/Library/Application Support/to-video/tts-store，环境变量 TO_VIDEO_TTS_STORE
  覆盖，--no-store 禁用）；集内缓存未命中时先按 digest 回收——换 worktree / 清盘不再
  丢整集合成成果，改稿只重配变更句。历史版本按 digest 文件名并存，不互相覆盖。

用法：
  edge：    uv run --no-project --with edge-tts --with mutagen $T/scripts/tts.py \
                --project $P [--narration-lang zh] [--voice zh-CN-YunxiNeural] [--rate +4%] [--force]
  indextts：uv run --no-project --with mutagen $T/scripts/tts.py \
                --project $P --engine indextts --ref <参考样本.wav> \
                [--style passionate] [--server http://127.0.0.1:8766] [--force]
  情感三来源（互斥）：--style/--emo-vector 向量注入 · --emo-ref <另一段录音> 语调迁移
                （更自然）· --emo-text "轻快爽朗、自信阳光" 自然语言（需服务端 --use-qwen-emo）
  （工程内薄包装等价于在工程目录下运行 scripts/tts.py）

声音克隆完整手册（部署/风格/排障/许可）见 references/VOICE-CLONING.md。
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

# edge_tts / mutagen 均惰性导入：克隆模式（indextts）无需 edge_tts；`--list-styles` 等本地操作零依赖。

DEFAULT_VOICE = "zh-CN-YunxiNeural"
DEFAULT_RATE = "+4%"

#: 语言镜像表：narration-lang → (IndexTTS infer lang 码, edge 缺省音色)。
#: ⚠️ 内联而非 import langs——本文件会被拷进 ~/tools/index-tts 的 venv 单独运行
#: （paths.py「导入边界」），同目录依赖会断掉那条拷出路径；与 scripts/langs.py
#: 的 LANGS 注册表的一致性由 tests/test_tts_lang_mirror.py 钉住（timing.json
#: 「TS/Python 双语共读」的同构纪律）。路径后缀规则（zh 无后缀 / en 加 .en）
#: 同理内联，与 langs.narration_json / langs.audio_dir 同构。
LANG_MIRROR: dict[str, tuple[str, str]] = {
    "zh": ("ZH", DEFAULT_VOICE),
    "en": ("EN", "en-US-AndrewNeural"),
}
CONCURRENCY_EDGE = 6
CONCURRENCY_INDEXTTS = 1  # 服务端串行锁推理；>1 会在锁后排队，排队时长计入客户端超时
RETRIES = 4
HTTP_TIMEOUT = 600  # MPS fp32 长句可达数分钟；须覆盖队列等待
MANUAL = str(
    Path(__file__).resolve().parents[1] / "references" / "VOICE-CLONING.md"
)  # skill 根 references/

# --plan 排期估算用的实测常数（MPS fp32，长跑折算口径：含降频、机器争用与逐句开销）。
# RTF_1BEAM 来自三集 596 句连续跑 8.5 小时 / 40.2 分钟纯语音；RTF_MULTIBEAM 由同句
# 1↔3 束 A/B 实测的约 3.2 倍推得（与早期 3 束直测的 RTF 40–58 区间一致）。
#
# ⚠️ 2026-08-20 实测偏差（EP1 v3 两遍法，187 句）：
#   A 遍 sunny(beams=1)：墙钟 ~1.9 h、纯语音 12.98 分 → 实测 RTF ≈ 8.8（常量 13 偏保守 1.5×）
#   B 遍 sunny-steady(beams=3)：墙钟 1.98 h、纯语音 12.89 分 → 实测 RTF ≈ 9.2（常量 45 偏保守 4.9×）
# 即机器空闲时 3 束的实际代价远低于「+241%」的旧口径（本次 B/A ≈ 1.04），旧数据应是
# 在机器被占用/热节流时测得。**常量刻意不下调**：--plan 的用途是排期决策，宁可高估
# 让人留出窗口，也不要低估导致长跑撞上其他任务；但看到估算与实测差 3–5 倍属正常。
RTF_1BEAM = 13.0
RTF_MULTIBEAM = 45.0
AVG_SEC_PER_LINE = 4.2  # 三集每句音频均值

# IndexTTS 8 维情感向量顺序（indextts/infer_v2_5.py 固定）：happy, angry, sad, afraid,
# disgusted, melancholic, surprised, calm。
#
# 有效和护栏 Σ分量×emo_alpha ≤ 0.8 是**本管线自定的口径**，不是上游行为（2026-08-20 核验）：
# 上游 infer() 从不归一化，normalize_emo_vec 全仓唯一调用点是 webui.py:665 的「自定义向量」
# 分支，且那条的 0.8 作用在**已乘 emo_bias 的和**上、且在 alpha 之前。
# emo_bias（infer_v2_5.py:493 硬编码）8 维严重不等权：
#   sad/afraid=1.0 > happy/disgusted/melancholic=0.9375 > angry=0.875 > surprised=0.6875 > calm=0.5625
# 后果：从社区/WebUI 抄来的 (vec, alpha) 经本管线复现实际**强 16%–33%**（含 calm 越重偏差越大，
# confident 档最失真），跨来源参数迁移必须重新试听定档。详见 INDEXTTS-2.5-ADVANCED.md §3.2。
#
# 另注：alpha 恰好等于「替换掉本人语调的百分比」**仅当名义向量和 = 1.0** ——
# sunny/passionate 刚好是 1.00，而 lively(0.85)/confident(0.90)/positive(0.95) 不是，
# 其 alpha 跨预设不可直接比较。
EMO_KEYS = [
    "happy",
    "angry",
    "sad",
    "afraid",
    "disgusted",
    "melancholic",
    "surprised",
    "calm",
]

# 风格预设 —— 数值为初值，可实测试听后微调。
# 可选键 "beams"：预设自带的束搜索宽度（缺省 1）。束宽会改变韵律稳定度，属风格的一部分，
# 故允许写进预设；命令行 --num-beams 显式给值时优先。束宽代价见下方 sunny-steady 注释
# （MPS 上近乎免费，CUDA 上近线性）；机器忙时想只让关键句更稳，用 --steady 混合档。
# 可选键 "sampling"：预设自带的采样参数覆盖（见 SAMPLING_DEFAULTS）。当前所有预设都不带 ——
# 任何写进预设的值都会改缓存摘要 ⇒ 整集重录，故须先 A/B 拿到证据再定档。
STYLE_PRESETS: dict[str, dict] = {
    "neutral": {"label": "中性", "vec": None, "alpha": 1.0, "df": 1.0},
    "passionate": {
        "label": "激情",
        # 高唤醒正价（happy 主载）+ 跳跃感（surprised）+ 少量 calm 锚定咬字；
        # 有效和 1.00×0.7=0.70 ≤0.8。
        # ⚠️ 校准（2026-08-20）：此处原注「df 0.97 护密集技术句清晰度」**方向写反了**。
        # duration_factor 作用于 S2M 的时间轴重采样（infer_v2_5.py:832 target_lengths），
        # df<1 → 梅尔帧更少 → 语速更快 → 每个音素分到的时间更短、咬字更紧，密集技术句
        # 应当**更糊**而非更清。护清晰度的正确方向是 df>1。0.97 的实际效果是「略快」，
        # 与本档「激情」的定位自洽，故数值保留、只更正因果表述。
        "vec": [0.70, 0, 0, 0, 0, 0, 0.20, 0.10],
        "alpha": 0.7,
        "df": 0.97,
    },
    # 以下三档的名义向量已归一到 Σvec=1.0（2026-08-20）：只有 Σvec=1.0 时 alpha 才等于
    # 「替换掉本人语调的百分比」，否则它被稀释成 α·Σvec、**跨预设不可比**。
    # alpha 同步反向缩放（α_new = α_old × Σvec_old），故有效注入 w=vec×alpha 在数学上不变。
    # **精确说法**：上游把 w 截断到 4 位小数（infer_v2_5.py:608 用 int() 截断而非四舍五入），
    # 而 0.33/0.455 一类值恰落在截断边界上，故 21 个分量里有 3 个出现 1e-4 的差异
    # （0.33→0.3299、0.455→0.4549、0.5249→0.525）。相对幅度 0.03%，远低于任何听感阈；
    # 且这三档**未被任何已上线剧集使用**（三集用 sunny-steady / passionate），即便真有
    # 差异也无影响。不要把它写成「逐项完全一致」——那是过度断言。
    # 由 tests/test_digest.py::test_preset_normalization_preserves_injection 钉死 1e-4 界。
    "lively": {
        "label": "轻快",
        "vec": [
            0.6470588,
            0,
            0,
            0,
            0,
            0,
            0.1764706,
            0.1764706,
        ],  # 原 .55/.15/.15 ÷ 0.85
        "alpha": 0.51,  # 原 0.6 × 0.85
        "df": 0.95,
    },
    "confident": {
        "label": "自信",
        "vec": [0.2777778, 0, 0, 0, 0, 0, 0, 0.7222222],  # 原 .25/.65 ÷ 0.90
        "alpha": 0.63,  # 原 0.7 × 0.90
        "df": 1.05,
    },
    "positive": {
        "label": "正能量",
        "vec": [0.7894737, 0, 0, 0, 0, 0, 0, 0.2105263],  # 原 .75/.20 ÷ 0.95
        "alpha": 0.665,  # 原 0.7 × 0.95
        "df": 1.0,
    },
    "sunny": {
        "label": "明快阳光",
        # 2026-08-19 试听定档（科普长视频推荐位）。方向由 QwenEmotion 对「轻快、爽朗、
        # 自信、阳光」推出（happy 近乎独载），强度则**人工压到 0.35**——Qwen 原始输出会顶到
        # Σ=0.8 上限，实测把克隆音高推到 199–223 Hz（说话人自然区间仅 142–163 Hz）而显假；
        # 0.35 留 65% 给本人真实语调，配 df 0.95 取「明快但不飘」。
        # 配套样本很关键：本档在 voices/me-bright.wav（me-1.mp3 --start 0.36 --duration 12）
        # 上定档，换回更闷的样本会失去明快感——见 VOICE-CLONING.md §3.3。
        "vec": [0.95, 0, 0, 0, 0, 0, 0.02, 0.03],
        "alpha": 0.35,
        "df": 0.95,
    },
    "sunny-steady": {
        "label": "明快稳健",
        # = sunny 同方向同强度同语速，只把束宽提到 3：GPT 段搜索更宽 → 韵律更收敛。
        # 实测（同文本同样本）：语调起伏 48.4 → 43.5、音节率 4.10 → 4.55，亮度基本不掉
        # （质心 1245 → 1223）——是唯一「不牺牲明快度就让语气更稳」的旋钮。
        # 代价高度依赖硬件，**不是无条件的「线性放大」**：束宽只作用于 T2S（S2M 入口的
        # codes 形状与束宽无关），而 MPS 上 T2S 只占三段耗时的 18–46%（2026-08-20 本机
        # 13 样本分段 profile：s2mel 反而占 45–73%）。整集实测 1→3 束仅 +4%
        # （EP1 v3 两遍法 1.9h → 1.98h）。故：CUDA 上近线性放大，MPS 上近乎免费。
        # 机器忙/热节流时仍可能出现数倍差，此时用 `--steady` 混合档只升关键句。
        "vec": [0.95, 0, 0, 0, 0, 0, 0.02, 0.03],
        "alpha": 0.35,
        "df": 0.95,
        "beams": 3,
    },
    # ── 以下两档是**候选**，尚未定档：新增而非改动生产档，故对三集缓存零影响。
    #    定档前必须按 INDEXTTS-2.5-ADVANCED.md §6.5 的测量协议做 A/B + 人工试听定档。
    "sunny-pure": {
        "label": "明快纯载",
        # 候选（路线图 #10）：砍掉 sunny 里的配料维度，使 Σvec=1.0 与「happy 单载」
        # 同时成立 ⇒ alpha 语义最干净（它就是被替换掉的本人语调比例）。
        # ⚠️ 立论勘误（2026-09-02）：本档原注以 emo_bias「surprised 只兑付 69%、
        # calm 56%」为依据——该折扣**在本管线不生效**。施加 bias 的 normalize_emo_vec
        # （infer_v2_5.py:488）全仓唯一调用点是 webui.py:665；infer() 内对 emo_vector
        # 的唯一变换是 :605-607 的 int(x*alpha*10000)/10000，无 bias 相乘。故本管线
        # 名义权重即实际权重，「配料维度不划算」这条理由作废，本档退回纯 alpha 语义论证。
        # 顺带：surprised 的原型数是 10（happy 只有 3，emo_num=[3,17,2,8,4,5,10,24]），
        # 表达基底并不贫乏——砍它的代价可能比原注设想的大，定档须以试听为准。
        "vec": [1.0, 0, 0, 0, 0, 0, 0, 0],
        "alpha": 0.35,
        "df": 0.95,
    },
    "sunny-clear": {
        "label": "明快清晰",
        # 候选（路线图 #11）：= sunny-steady 但 df 1.05。依据是 df 方向的勘误——
        # df<1 = 更快 = 每音素分到的时间更短 = 咬字更紧更糊，护术语密集句的清晰度
        # 正确方向是 df>1（§3.4）。明快感仍由 happy/alpha 承担，与语速正交。
        # 代价：拉长时长 ⇒ 牵动 beat 与片尾渐黑窗口，定档后须重渲。
        "vec": [0.95, 0, 0, 0, 0, 0, 0.02, 0.03],
        "alpha": 0.35,
        "df": 1.05,
        "beams": 3,
    },
    "story": {
        "label": "段落演绎",
        # 2026-09-25 第三轮试听定档（#07，试听页 .context/voice-audition/v3/）：合成单位从
        # 「句」升为「故事块」——同幕连续句拼一次请求，上游 front.py 合并短句为单段 ⇒
        # 句间韵律连续 + 自然停顿，替代逐句合成的「朗读感」（逐句/单一情绪/恒定句距
        # 三者叠加是根因，见 issue.md RSI-011）。
        # - vec/alpha 取 #07 g2 方向（surprised 主载 + happy）×0.28 有效注入；无台本块/
        #   未覆盖块用它，块情绪可被 script/narration.cues.toml 逐块覆盖（§4.5）。
        # - seed 固定 4242：试听定档 take 可复现；单块换 take 用台本 [take]（--seed-offset 是整集口径）。
        # - block: 块上限与切分参数；perform_punct 开表演标点（……→…，tts_text）。
        "vec": [1 / 3, 0, 0, 0, 0, 0, 2 / 3, 0],
        "alpha": 0.28,
        "df": 1.0,
        "beams": 1,
        "seed": 4242,
        "block": {
            "max_sentences": 3,
            "max_chars": 90,
            "tail_pad_sec": 0.18,
            "perform_punct": True,
        },
    },
}


# 上游自回归采样参数的默认值 —— 已知副本，锚点 indextts/infer_v2_5.py:731-739（HEAD 4f8792f）；
# 与 infer_v2.py:536-544 完全一致，两版共享同一组默认。
#
# **分层 SSOT**：`SAMPLING_PASSTHROUGH_DEFAULTS`（7 个经 **generation_kwargs 透传给 HF
# generate 的参数）是唯一的数据副本，服务端 tts_server.py 运行时从本模块导入它（那个进程
# 不受本 skill 版本控制之外的依赖影响——导入是纯常量读取）；本字典在其上追加两个
# **非透传**键：text_normalization（v2.5 infer() 的独立形参）与 seed（本服务自己 set_seed），
# 它们不进 SAMPLING_RANGES/SAMPLING_CLI 的透传校验路径。
#
# 本副本只有一个用途：判定「这一项是否被显式改过」，从而决定**要不要进缓存摘要**。
# 摘要沿用「未使用即省略」规则（同 |beams=N），故全部取默认时摘要与历史逐字节相同 ——
# 这是已上线三集近 600 句缓存零失效的前提，由 tests/test_digest.py 黄金哈希钉死。
SAMPLING_PASSTHROUGH_DEFAULTS: dict[str, float | int] = {
    "temperature": 0.8,
    "top_p": 0.8,
    "top_k": 30,
    "length_penalty": 0.0,
    "repetition_penalty": 10.0,
    "max_mel_tokens": 1500,
    "interval_silence": 200,
}
SAMPLING_DEFAULTS: dict[str, float | int | bool | None] = {
    **SAMPLING_PASSTHROUGH_DEFAULTS,
    "text_normalization": True,
    "seed": None,
}

#: 采样参数的合法区间（对齐上游 webui.py:901-910 的滑杆），用于长跑前提前失败。
#: max_mel_tokens 上限 1815 = config.yaml 的 gpt.max_mel_tokens（mel 位置嵌入容量 ≈36.2 s）。
SAMPLING_RANGES: dict[str, tuple[float, float]] = {
    "temperature": (0.1, 2.0),
    "top_p": (0.0, 1.0),
    "top_k": (0, 100),
    "length_penalty": (-2.0, 2.0),
    "repetition_penalty": (0.1, 20.0),
    "max_mel_tokens": (50, 1815),
    "interval_silence": (0, 2000),
}


def tts_text(text: str, lang: str = "ZH", perform: bool = False) -> str:
    """口播文本微调：破折号换为逗号停顿，避免 TTS 念成怪音。

    全角映射仅对主语言（ZH）生效：en 稿经 check_script 禁全角标点门，此处原样
    透传是纵深防御——`——` 会被换成全角逗号混进英文文本。

    perform=True（段落演绎档）：`……` 保留为单个 `…` 而非压成 `。`——上游把 `…`
    当独立 token 并给拖长停顿（front.py 标点表），是「表演标点」的一部分；默认
    映射不动（存量 2 集含 `……`，改全局会令其重合成出不同音频而摘要不变）。

    注意这是**唯一**的程序化文本预处理：数字/百分号/量词的读法由上游中文归一化
    （wetext）承担，多音字与英文专名读音由逐字稿里的发音标注 `<字|读音>` 承担。
    归一化的已知陷阱（4 位年份与「年」之间不能有空格）由 check_script.py 的写稿 lint 拦。
    """
    if lang != "ZH":
        return text
    text = text.replace("——", "，")
    return text.replace("……", "…") if perform else text.replace("……", "。")


def synth_source_text(item: dict) -> str:
    """取该句真正送去合成的文本：优先 `ttsText`（含发音标注），否则 `text`。

    `narration.json` 的 `text` 是**人读文本**，同时被字幕（captions.py）与字数预算
    （check_script.py）消费；发音标注只能进 `ttsText`，否则会泄漏到 SRT/VTT 并污染预算。
    未标注的句子没有 `ttsText` 字段 ⇒ 取值与历史完全一致 ⇒ 存量缓存不失效。
    """
    return item.get("ttsText") or item["text"]


def mp3_duration(path: Path) -> float:
    """mutagen 实测 MP3 时长（两引擎共用）。"""
    from mutagen.mp3 import MP3

    return MP3(str(path)).info.length


# ---------------- 风格解析 ----------------


def parse_emo_vector(spec: str) -> list[float]:
    """`happy:0.6,calm:0.2` → 8 维向量；未知键/负值/空集报错。"""
    vec = [0.0] * 8
    seen: set[str] = set()
    for part in spec.split(","):
        key, _, val = part.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key not in EMO_KEYS:
            raise ValueError(f"未知情感键 {key!r}（可用：{','.join(EMO_KEYS)}）")
        if key in seen:
            raise ValueError(f"情感键重复：{key}")
        if not val:
            raise ValueError(f"情感权重缺失：{key}（格式如 happy:0.6）")
        weight = float(val)
        if not math.isfinite(weight) or weight < 0:  # isfinite 显式拦 NaN/Inf
            raise ValueError(f"情感权重必须为非负有限数值：{key}")
        vec[EMO_KEYS.index(key)] = weight
        seen.add(key)
    if not seen:
        raise ValueError("--emo-vector 不能为空")
    return vec


def resolve_style(
    args: argparse.Namespace,
) -> tuple[str, list[float] | None, float, float, int]:
    """返回 (风格名, 情感向量|None, emo_alpha, duration_factor, num_beams)。

    三个可覆盖参数（alpha / df / beams）一律「命令行显式给值优先，否则取预设」——
    故 --num-beams 的 argparse 默认值必须是 None 而非 1，否则无法区分「没给」与「给了 1」。
    """
    beams = args.num_beams if args.num_beams is not None else 1
    if args.emo_vector:
        vec = parse_emo_vector(args.emo_vector)
        alpha = args.emo_alpha if args.emo_alpha is not None else 0.6
        df = args.duration_factor if args.duration_factor is not None else 1.0
        return "raw", vec, alpha, df, beams
    preset = STYLE_PRESETS[args.style]
    alpha = args.emo_alpha if args.emo_alpha is not None else preset["alpha"]
    df = args.duration_factor if args.duration_factor is not None else preset["df"]
    if args.num_beams is None:  # 预设可自带束宽（如 sunny-steady=3），缺省为 1
        beams = preset.get("beams", 1)
    return args.style, preset["vec"], alpha, df, beams


#: 采样参数的 CLI 名 → 属性名（argparse 把连字符转下划线）。text_normalization / seed 单独处理。
SAMPLING_CLI = (
    "temperature",
    "top_p",
    "top_k",
    "length_penalty",
    "repetition_penalty",
    "max_mel_tokens",
    "interval_silence",
)


def resolve_sampling(args: argparse.Namespace) -> dict[str, float | int | bool]:
    """收集所有**被显式改动过**的采样参数；全默认时返回空 dict（摘要因此不变）。

    优先级同 alpha/df/beams：命令行显式给值 > 风格预设的 `sampling` 键 > 上游默认。
    预设自带采样参数是刻意留的扩展位——束宽已证明「属于风格的一部分」，length_penalty
    这类同样影响韵律的旋钮理应能随风格走；但**任何写进预设的值都会改摘要 ⇒ 整集重录**，
    故当前所有预设都不带 sampling，待 A/B 拿到证据后再定档。
    """
    preset: dict = STYLE_PRESETS.get(args.style, {}) if args.style else {}
    preset_sampling: dict = preset.get("sampling", {})
    out: dict[str, float | int | bool] = {}
    for key in SAMPLING_CLI:
        cli_val = getattr(args, key, None)
        val = cli_val if cli_val is not None else preset_sampling.get(key)
        if val is None:
            continue
        lo, hi = SAMPLING_RANGES[key]
        if not lo <= val <= hi:  # NaN 比较恒 False，一并被拦
            raise ValueError(f"--{key.replace('_', '-')} 必须在 [{lo:g}, {hi:g}]")
        if key == "top_k" and val == 1:
            raise ValueError(
                "--top-k 1 在束搜索下不安全（每束需保底 2 个候选）：用 0 关闭或 ≥2"
            )
        if val != SAMPLING_DEFAULTS[key]:
            out[key] = val
    if getattr(args, "no_text_normalization", False):
        out["text_normalization"] = False
    if getattr(args, "seed", None) is not None:
        # --seed-offset 是「换一条 take」的逃生口：固定种子会把某句锁死在一条可能不佳的
        # 采样结果上，偏移一位即可换一条而仍然可复现。
        out["seed"] = int(args.seed) + int(getattr(args, "seed_offset", 0) or 0)
    elif preset.get("seed") is not None:
        # 预设自带种子（story：定档 take 可复现）。CLI --seed 优先；--seed-offset 叠加（整集换 take）。
        # 经 |seed= 后缀进摘要（同 CLI 路径），故存量无种子口径零波及。
        out["seed"] = int(preset["seed"]) + int(getattr(args, "seed_offset", 0) or 0)
    return out


def sampling_suffix(sampling: dict | None) -> str:
    """采样参数 → 缓存摘要后缀。空 dict 返回空串（存量缓存零失效的关键）。

    键按字母序，值用 repr()（防 0.7 → 0.70 之类的表示漂移，与 alpha/df 同口径）。
    """
    if not sampling:
        return ""
    return "".join(f"|{k}={sampling[k]!r}" for k in sorted(sampling))


# ---------------- 混合档：整集低束宽 + 指定句高束宽 ----------------
#
# 动机（实测）：3 束把语调起伏收窄约 10–20%、听感更「稳/可信」，但短句 RTF 从 6–7 涨到
# 20–31（数字密集句可达 31.5），整集从 2.5–3.5 小时涨到 8–15 小时。而真正决定第一印象的
# 只是冷开场与各幕金句——把这几句单独升到 3 束即可。代价按句线性：189 句一集里每升 1 句
# 约 +2.2 分钟（+1.3%），升 5 句 2.9→3.1 小时、升 20 句 →3.6 小时，而整集升档要 9.9 小时。
# 缓存 sidecar 按句独立（摘要含 |beams=N），故同一集内混用两种束宽完全安全、可分批补跑。


def parse_steady_selector(spec: str) -> tuple[set[str], set[str], list[str]]:
    """`P0,p3-25b,p5-*` → (精确句 id, 幕名, 前缀)。

    判定规则（可预测、无歧义）：以 `*` 结尾→前缀通配；含 `-`→精确句 id；其余→幕名。
    全部大小写不敏感。
    """
    ids: set[str] = set()
    scenes: set[str] = set()
    prefixes: list[str] = []
    for raw in spec.split(","):
        tok = raw.strip().lower()
        if not tok:
            continue
        if tok.endswith("*"):
            prefixes.append(tok[:-1])
        elif "-" in tok:
            ids.add(tok)
        else:
            scenes.add(tok)
    if not (ids or scenes or prefixes):
        raise ValueError("--steady 不能为空")
    return ids, scenes, prefixes


def steady_match(
    item: dict, ids: set[str], scenes: set[str], prefixes: list[str]
) -> bool:
    sid = str(item["id"]).lower()
    if sid in ids or str(item.get("scene", "")).lower() in scenes:
        return True
    return any(sid.startswith(p) for p in prefixes)


# ---------------- 音色签名护栏（防整集静默改写） ----------------

#: 音频目录下的音色签名标记。逐句 `{id}.sha` 只能发现「这一句该重合成」，
#: 发现不了「整集正被换成另一种声音」——因为换音色时每一句的摘要都合法地变了。
#: 本标记补的正是这个缺口：它记录上次成功合成的引擎/音色/风格，
#: 与本次不一致时硬失败，要求显式 --allow-voice-switch。不参与逐句摘要，故零缓存影响。
ENGINE_MARKER = ".engine"

#: tts_server.py 的启动命令此前有三份副本（本文件、tts_sample.py、VOICE-CLONING.md），
#: 其中一份还留着 `<仓库路径>` 占位符——粘贴即错。收敛为唯一生成处。
SERVER_SCRIPT = Path(__file__).resolve().parent / "tts_server.py"


def server_launch_hint(port: int = 8766) -> str:
    """返回可直接粘贴的 IndexTTS 服务启动命令（服务须运行在 index-tts 自己的环境里）。"""
    return (
        "  cd ~/tools/index-tts && uv run --frozen --with fastapi --with uvicorn \\\n"
        "      --with soundfile --with numpy --with lameenc \\\n"
        f"      python {SERVER_SCRIPT} --model-dir checkpoints --port {port}"
    )


def check_voice_marker(out_dir: Path, signature: str, allow_switch: bool) -> None:
    """比对音色签名；不一致且未显式放行时硬失败。"""
    marker = out_dir / ENGINE_MARKER
    if not marker.exists():
        return
    previous = marker.read_text(encoding="utf-8").strip()
    if previous == signature or allow_switch:
        return
    sys.exit(
        f"音色签名与上次合成不一致，将整集改写（{len(list(out_dir.glob('*.mp3')))} 个 mp3 单槽位覆盖）：\n"
        f"  上次: {previous}\n"
        f"  本次: {signature}\n"
        f"若确为有意重录，请显式加 --allow-voice-switch；否则请检查 --engine/--ref/--style 是否写错。\n"
        f"详见 {MANUAL} §六"
    )


def write_voice_marker(out_dir: Path, signature: str) -> None:
    (out_dir / ENGINE_MARKER).write_text(signature + "\n", encoding="utf-8")


# ---------------- 引擎一：edge-tts（历史路径，保持字节级一致） ----------------


def digest_edge(voice: str, rate: str, text: str) -> str:
    return hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()


async def synth_edge(
    sem: asyncio.Semaphore,
    item: dict,
    force: bool,
    voice: str,
    rate: str,
    out_dir: Path,
    lang: str = "ZH",
) -> dict:
    import edge_tts  # 惰性导入：仅 edge 引擎需要

    sid, text = item["id"], item["text"]
    mp3 = out_dir / f"{sid}.mp3"
    meta = out_dir / f"{sid}.sha"
    digest = digest_edge(voice, rate, text)

    if (
        not force
        and mp3.exists()
        and mp3.stat().st_size > 0
        and meta.exists()
        and meta.read_text() == digest
    ):
        pass
    else:
        async with sem:
            last_err: Exception | None = None
            for attempt in range(RETRIES):
                try:
                    communicate = edge_tts.Communicate(
                        tts_text(text, lang), voice, rate=rate
                    )
                    await communicate.save(str(mp3))
                    if mp3.stat().st_size == 0:
                        raise RuntimeError("空音频文件")
                    meta.write_text(digest)
                    break
                except Exception as e:  # noqa: BLE001 - 网络服务需要整体重试
                    last_err = e
                    await asyncio.sleep(1.5 * (attempt + 1))
            else:
                raise RuntimeError(f"{sid} 合成失败: {last_err}")

    duration = mp3_duration(mp3)
    return {**item, "durationSec": round(duration, 3)}


# ---------------- 引擎二：IndexTTS 声音克隆（本地 HTTP 服务） ----------------


class NonRetryableError(Exception):
    """4xx 类错误：重试无意义，直接失败并携带服务端错误详情。"""


def _http_error_detail(e: urllib.error.HTTPError) -> str:
    try:
        parsed = json.loads(e.read())
        if isinstance(parsed, dict):
            return str(parsed.get("detail", parsed))
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            return str(parsed[0].get("msg", parsed[0]))  # FastAPI 422 校验数组
        return str(parsed)
    except Exception:  # noqa: BLE001 - 详情解析失败退化为字符串
        return str(e)


def http_json(
    method: str, url: str, payload: dict | None = None, timeout: int = HTTP_TIMEOUT
) -> dict:
    """同步 urllib 调用（调用方需置于 asyncio.to_thread）；4xx → NonRetryableError。"""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        detail = _http_error_detail(e)
        if 400 <= e.code < 500:
            raise NonRetryableError(f"HTTP {e.code}: {detail}") from e
        raise RuntimeError(f"HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"连接失败: {e.reason}") from e
    if "application/json" not in ctype:
        raise NonRetryableError(f"响应 Content-Type 异常: {ctype}")
    return json.loads(body)


def http_synthesize(
    server: str,
    text: str,
    ref: str,
    vec: list[float] | None,
    alpha: float,
    df: float,
    lang: str,
    num_beams: int = 1,
    emo_ref: str | None = None,
    emo_text: str | None = None,
    headers_out: dict | None = None,
    sampling: dict | None = None,
) -> tuple[bytes, str]:
    """POST /synthesize → (mp3 bytes, X-Audio-Format)。4xx 不可重试。

    headers_out：可选出参，传入 dict 时回填全部响应头（如 emo_text 模式的 X-Emo-Vector），
    供试听工具回显；管线主路径不需要，故保持返回值签名不变。
    **键统一小写**——urllib 的 HTTPMessage 查找不分大小写，但拷进普通 dict 后会变成
    大小写敏感，而 Starlette 下发的响应头名是小写的，故此处归一避免调用方取不到值。
    """
    payload: dict = {
        "text": text,
        "ref_path": ref,
        "emo_alpha": alpha,
        "duration_factor": df,
        "lang": lang,
        "num_beams": num_beams,
    }
    if vec is not None:
        payload["emo_vector"] = vec
    if emo_ref:  # 情感参考音频：音色仍取 ref，语调迁移自 emo_ref（服务端与向量互斥）
        payload["emo_ref_path"] = emo_ref
    if emo_text:  # 自然语言情感描述（服务端 QwenEmotion 转向量）
        payload["emo_text"] = emo_text
    if sampling:  # 只发被显式改过的采样参数，其余由服务端取上游默认
        payload.update(sampling)
    req = urllib.request.Request(
        f"{server}/synthesize",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            if headers_out is not None:
                headers_out.update({k.lower(): v for k, v in resp.headers.items()})
            return resp.read(), resp.headers.get("X-Audio-Format", "unknown")
    except urllib.error.HTTPError as e:
        detail = _http_error_detail(e)
        if 400 <= e.code < 500:
            raise NonRetryableError(f"HTTP {e.code}: {detail}") from e
        raise RuntimeError(f"HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"连接失败: {e.reason}") from e


def digest_indextts(
    ref_sha1: str,
    style: str,
    vec: list[float] | None,
    alpha: float,
    df: float,
    lang: str,
    engine_tag: str,
    text: str,
    num_beams: int = 1,
    emo_ref_sha1: str | None = None,
    emo_text: str | None = None,
    sampling: dict | None = None,
    block: str | None = None,
    pos: str | None = None,
) -> str:
    vec_str = ",".join(repr(x) for x in vec) if vec else "none"
    # 束宽/情感来源/采样参数改变合成结果，须入键；未使用时省略字段——沿用历史摘要格式，
    # 存量缓存不失效。新增字段一律追加在**末尾**且默认省略，故摘要格式可持续扩展。
    beams_part = "" if num_beams == 1 else f"|beams={num_beams}"
    emo_part = f"|emoref={emo_ref_sha1}" if emo_ref_sha1 else ""
    emo_part += f"|emotext={emo_text}" if emo_text else ""
    # 块模式（story 档）：块=缓存单位——block 后缀由成员文本+切分参数派生，改任一句
    # 即整块换摘要；pos 区分块内句位。仅块模式追加，逐句口径逐字节不变。
    block_part = f"|block={block}|{pos}" if block else ""
    return hashlib.sha1(
        f"indextts|{engine_tag}|{ref_sha1}|{lang}|{style}|{vec_str}|{alpha!r}|{df!r}|{text}"
        f"{beams_part}{emo_part}{sampling_suffix(sampling)}{block_part}".encode()
    ).hexdigest()


# ---------------- 音频版本库（内容寻址持久库，仅 indextts） ----------------
#
# 集内 audio/ 是 gitignored 本地产物 ⇒ 换 worktree / 清盘即丢整集合成成果
# （Claude Code 系列的 mp3 曾在任何工作区都不剩一份，实测教训）。版本库按
# 「句 id + digest 前 12 位」命名放在机器级持久目录，与任何 worktree 解耦：
#   - 合成成功 → store_deposit 入库（同 digest 刷新为最新音频；不同 digest 并存=保留历史版本）；
#   - 集内缓存未命中 → store_restore 按 digest 回收，命中即等价集内缓存命中；
#   - 改稿/换风格 ⇒ 新 digest 自然 miss 重配，旧版本文件保留可回退。
# 路径是机器属性：默认值在此 + TO_VIDEO_TTS_STORE 环境变量覆盖，永不写进
# 受版本控制的 toml（与
# config.py 对 tts.server 的立场一致；tts.py 不 import paths.py 的边界也不变
# ——默认值是纯字面量）。仅接 indextts：edge 预置音色免密钥秒级重合成，
# 无 2 小时级资产可丢。
#
# 条目按内容寻址（<slug>/<sid>.<digest12>.mp3），库根整体搬迁零失效（mv 即迁移）。
#
# ⚠️ 继承是中性的：坏 take 同样按 digest 逐代继承（187/187 句恢复零重合成 =
# 缺陷一并回来；换 worktree 重建继续继承，ISSUE-192）。撤销发音标注会使 digest
# 回退旧值、静默复活历史坏 take——死 digest 下的已知坏 take 一律改名隔离
# （<sid>.<digest12>.mp3 → *.bad-<tag>，.sha 邻档同步），留档不删，恢复后抽检。

DEFAULT_STORE = "~/Library/Application Support/to-video/tts-store"


def store_root(disabled: bool) -> Path | None:
    """版本库根目录；--no-store 或 env 置空串时返回 None（全程直通不落盘）。

    解析顺序：TO_VIDEO_TTS_STORE → 默认目录（不存在则原样返回，首存即建）。"""
    if disabled:
        return None
    env = os.environ.get("TO_VIDEO_TTS_STORE")
    if env == "":
        return None
    if env:
        return Path(env).expanduser()
    return Path(DEFAULT_STORE).expanduser()


def store_entry(store: Path | None, slug: str, sid: str, digest: str) -> Path | None:
    """库内条目路径：<root>/<集 slug>/<sid>.<digest12>.mp3（同名 .sha 邻档存全量 digest）。"""
    if store is None:
        return None
    return store / slug / f"{sid}.{digest[:12]}.mp3"


def store_has(store: Path | None, slug: str, sid: str, digest: str) -> bool:
    """--plan 用：库内是否存在该 digest 的句子（校验 .sha 邻档，防 12 位前缀巧合）。"""
    if store is None:
        return False
    mp3 = store_entry(store, slug, sid, digest)
    assert mp3 is not None
    sha = mp3.with_suffix(".sha")
    try:
        return (
            mp3.is_file()
            and mp3.stat().st_size > 0
            and sha.is_file()
            and sha.read_text(encoding="utf-8") == digest
        )
    except (OSError, UnicodeError) as e:
        print(f"WARN 版本库读取失败（{sid}）：{e}", file=sys.stderr)
        return False


def store_deposit(
    mp3: Path, sid: str, digest: str, store: Path | None, slug: str
) -> None:
    """合成成功后入库。失败只 WARN 不断长跑——库是加速器，不是门。"""
    if store is None:
        return
    dst = store_entry(store, slug, sid, digest)
    assert dst is not None
    sha = dst.with_suffix(".sha")
    tmp_mp3: Path | None = None
    tmp_sha: Path | None = None
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=dst.parent, prefix=f".{dst.name}.", suffix=".tmp", delete=False
        ) as f:
            tmp_mp3 = Path(f.name)
        shutil.copyfile(mp3, tmp_mp3)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=dst.parent,
            prefix=f".{sha.name}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            tmp_sha = Path(f.name)
            f.write(digest)
        os.replace(tmp_mp3, dst)
        tmp_mp3 = None
        os.replace(tmp_sha, sha)
        tmp_sha = None
    except (OSError, UnicodeError) as e:
        print(f"WARN 版本库入库失败（{sid}）：{e}", file=sys.stderr)
    finally:
        for tmp in (tmp_mp3, tmp_sha):
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass


def store_restore(
    sid: str, digest: str, out_dir: Path, store: Path | None, slug: str
) -> bool:
    """集内缓存 miss 时先向库回收；命中则 mp3 + .sha 落位，等价集内缓存命中。"""
    if not store_has(store, slug, sid, digest):
        return False
    src = store_entry(store, slug, sid, digest)
    assert src is not None
    try:
        shutil.copyfile(src, out_dir / f"{sid}.mp3")
        (out_dir / f"{sid}.sha").write_text(digest, encoding="utf-8")
        return True
    except (OSError, UnicodeError) as e:
        print(f"WARN 版本库回收失败（{sid}）：{e}", file=sys.stderr)
        return False


async def synth_indextts(
    sem: asyncio.Semaphore,
    item: dict,
    force: bool,
    ref: str,
    ref_sha1: str,
    style: str,
    vec: list[float] | None,
    alpha: float,
    df: float,
    lang: str,
    engine_tag: str,
    server: str,
    out_dir: Path,
    num_beams: int = 1,
    emo_ref: str | None = None,
    emo_ref_sha1: str | None = None,
    emo_text: str | None = None,
    sampling: dict | None = None,
    store: Path | None = None,
    slug: str = "",
) -> dict:
    sid, text = item["id"], synth_source_text(item)
    mp3 = out_dir / f"{sid}.mp3"
    meta = out_dir / f"{sid}.sha"
    digest = digest_indextts(
        ref_sha1,
        style,
        vec,
        alpha,
        df,
        lang,
        engine_tag,
        text,
        num_beams,
        emo_ref_sha1,
        emo_text,
        sampling,
    )

    local_hit = (
        not force
        and mp3.exists()
        and mp3.stat().st_size > 0
        and meta.exists()
        and meta.read_text() == digest
    )
    if local_hit:
        pass
    elif not force and store_restore(sid, digest, out_dir, store, slug):
        pass  # 版本库回收命中：mp3 + .sha 已落位，等价集内缓存命中（--force 不走库）
    else:
        async with sem:
            last_err: Exception | None = None
            for attempt in range(RETRIES):
                try:
                    audio, fmt = await asyncio.to_thread(
                        http_synthesize,
                        server,
                        tts_text(text, lang),
                        ref,
                        vec,
                        alpha,
                        df,
                        lang,
                        num_beams,
                        emo_ref,
                        emo_text,
                        None,  # headers_out：管线主路径不需要回填响应头
                        sampling,
                    )
                    if fmt != "mp3":
                        raise NonRetryableError(
                            f"服务端编码器不可用（X-Audio-Format={fmt}）—— 按 {MANUAL} §七 检查 soundfile/lameenc"
                        )
                    if not audio:
                        raise RuntimeError("空音频响应")
                    mp3.write_bytes(audio)
                    if mp3.stat().st_size == 0:
                        raise RuntimeError("空音频文件")
                    meta.write_text(digest)
                    store_deposit(mp3, sid, digest, store, slug)
                    break
                except NonRetryableError:
                    raise
                except Exception as e:  # noqa: BLE001 - 推理服务需要整体重试
                    last_err = e
                    await asyncio.sleep(1.5 * (attempt + 1))
            else:
                raise RuntimeError(f"{sid} 合成失败: {last_err}")

    duration = mp3_duration(mp3)
    if local_hit and not store_has(store, slug, sid, digest):
        store_deposit(mp3, sid, digest, store, slug)
    return {**item, "durationSec": round(duration, 3)}


# ---------------- 段落演绎（story 档）：块请求与块合成 ----------------


def http_synthesize_block(
    server: str,
    text: str,
    ref: str,
    vec: list[float],
    alpha: float,
    df: float,
    lang: str,
    num_beams: int,
    weights: list[float],
    discard_sec: float,
    tail_pad_sec: float,
    sampling: dict | None = None,
) -> dict:
    """块模式 POST /synthesize → JSON {clips:[{audio,durationSec,format}], cuts, seams, split}。

    块音频在服务端按句界切回 N 个 mp3（b64）。超时 1800 s：块 ≈3 句音频 12–18 s，
    忙时热节流可把单块推理推过逐句口径的 600 s。
    """
    payload: dict = {
        "text": text,
        "ref_path": ref,
        "emo_vector": vec,
        "emo_alpha": alpha,
        "duration_factor": df,
        "lang": lang,
        "num_beams": num_beams,
        "block": {
            "weights": weights,
            "discard_sec": discard_sec,
            "tail_pad_sec": tail_pad_sec,
        },
    }
    if sampling:
        payload.update(sampling)
    req = urllib.request.Request(
        f"{server}/synthesize",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = _http_error_detail(e)
        if 400 <= e.code < 500:
            raise NonRetryableError(f"HTTP {e.code}: {detail}") from e
        raise RuntimeError(f"HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"连接失败: {e.reason}") from e


def resolve_block_vec(
    block_items: list[dict], preset_vec: list[float], preset_alpha: float
) -> tuple[list[float], float, str | None]:
    """块情感：台本 cue（块首句 item["cue"]）优先，否则预设向量。

    cue 方向归一到 Σ=1、强度取 cue.alpha 或预设 α——与 #07 的「名义 Σ0.35×α0.8」
    在上游 4 位截断后逐位等价（0.35×0.8 = 1×0.28），故可复现定档 take。
    返回 (vec, alpha, 出错的句 id|None)；α>0.8（方向已归一，有效和即 α）时返回错误 id 由调用方报错。
    """
    cue = block_items[0].get("cue")
    if not cue:
        return list(preset_vec), preset_alpha, None
    vec = parse_emo_vector(cue["emo"])
    total = sum(vec)
    if total <= 0:
        return list(preset_vec), preset_alpha, block_items[0]["id"]
    vec = [x / total for x in vec]
    alpha = float(cue.get("alpha", preset_alpha))
    if alpha > 0.8:
        return vec, alpha, block_items[0]["id"]
    # 归一后 Σ 浮点可能是 1.0000000000000002：α=0.8 时 Σ×α 以 1 ulp 之差撞本地与服务端的
    # ≤0.8 护栏（build 已放行同一台本）。仅此情形把最大分量逐 ulp 下调（≤2 步），上游 4 位
    # 截断下无可听差异；未超界的块向量与摘要逐位不变
    top = max(range(len(vec)), key=vec.__getitem__)
    while sum(vec) * alpha > 0.8:
        vec[top] = math.nextafter(vec[top], 0.0)
    return vec, alpha, None


def block_sampling(block_items: list[dict], sampling: dict) -> dict:
    """块采样口径：台本 `[take]`（成员句 item["take"]）把该块种子 +N，其余块原样。

    块模式的重掷单位是块：--seed-offset 作用于全局种子 ⇒ 全部块换摘要、整集重录；
    take 只改本块 |seed= 后缀 ⇒ 只重录这一块，定稿值留在台本即可复现。
    同块多句带 take 时歧义（加和还是择一），报错由调用方收口。
    """
    takes = [(i["id"], i["take"]) for i in block_items if i.get("take")]
    if not takes:
        return sampling
    if len(takes) > 1:
        raise ValueError(
            f"台本 [take] 在同一块内出现多次（{'、'.join(s for s, _ in takes)}）："
            "块是重掷单位，只保留一条"
        )
    if "seed" not in sampling:
        raise ValueError(f"台本 [take] 需要种子口径（{takes[0][0]}）")
    return {**sampling, "seed": sampling["seed"] + takes[0][1]}


async def synth_block_indextts(
    sem: asyncio.Semaphore,
    block_items: list[dict],
    force: bool,
    ref: str,
    ref_sha1: str,
    style: str,
    preset_vec: list[float],
    preset_alpha: float,
    df: float,
    lang: str,
    engine_tag: str,
    server: str,
    out_dir: Path,
    num_beams: int = 1,
    sampling: dict | None = None,
    store: Path | None = None,
    slug: str = "",
    discard_sec: float = 0.32,
    tail_pad_sec: float = 0.18,
    perform_punct: bool = False,
) -> list[dict]:
    """一个故事块 → N 句 mp3（块=缓存单位；切分失败逐句兜底，仍按块成员摘要落盘）。"""
    vec, alpha, bad_id = resolve_block_vec(block_items, preset_vec, preset_alpha)
    if bad_id is not None:
        raise NonRetryableError(
            f"{bad_id} 的台本情绪有效和 Σvec×alpha 超过 0.8 上限（见 {MANUAL} §4.2）"
        )
    try:
        sampling = block_sampling(block_items, sampling or {})
    except ValueError as e:
        raise NonRetryableError(str(e)) from e
    member_texts = [synth_source_text(i) for i in block_items]
    block_text = block_synth_text(block_items)
    suffix = block_digest_suffix(member_texts, discard_sec, tail_pad_sec)
    n = len(block_items)
    digests = [
        digest_indextts(
            ref_sha1,
            style,
            vec,
            alpha,
            df,
            lang,
            engine_tag,
            member_texts[k],
            num_beams,
            None,
            None,
            sampling,
            suffix,
            f"{k + 1}/{n}",
        )
        for k in range(n)
    ]
    weights = [sentence_weight(i["text"]) for i in block_items]

    # 块=缓存单位：全部成员命中（集内或版本库回收）才跳过合成，否则整块重录
    all_hit = True
    if not force:
        for k, item in enumerate(block_items):
            mp3 = out_dir / f"{item['id']}.mp3"
            meta = out_dir / f"{item['id']}.sha"
            if not (
                mp3.exists()
                and mp3.stat().st_size > 0
                and meta.exists()
                and meta.read_text() == digests[k]
            ):
                if not store_restore(item["id"], digests[k], out_dir, store, slug):
                    all_hit = False
    else:
        all_hit = False

    async def request(text: str, w: list[float], label: str, pad: float) -> dict:
        # 锁只罩单次请求（含重试）：兜底要再发请求，锁内递归会与 Semaphore(1) 自锁
        last_err: Exception | None = None
        async with sem:
            for attempt in range(RETRIES):
                try:
                    return await asyncio.to_thread(
                        http_synthesize_block,
                        server,
                        tts_text(text, lang, perform=perform_punct),
                        ref,
                        vec,
                        alpha,
                        df,
                        lang,
                        num_beams,
                        w,
                        discard_sec,
                        pad,
                        sampling,
                    )
                except NonRetryableError:
                    raise
                except Exception as e:  # noqa: BLE001 - 推理服务需要整体重试
                    last_err = e
                    await asyncio.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"块合成失败（{label}）: {last_err}")

    split_note: str | None = None
    if not all_hit:
        resp = await request(
            block_text, weights, f"{block_items[0]['id']}…{n} 句", tail_pad_sec
        )
        clips = resp.get("clips") if resp.get("split") == "ok" else None
        if clips:
            if resp.get("seams"):
                print(
                    f"WARN 块内出现上游分段缝 {resp['seams']}（>118 token 被迫分段，段间为"
                    f" 200ms 定长静音）——请缩短该块：{block_items[0]['id']}",
                    file=sys.stderr,
                )
            if len(clips) != n:
                raise NonRetryableError(
                    f"块切分数 {len(clips)} != 句数 {n}（{block_items[0]['id']}）"
                )
        else:
            # 切分失败：逐句兜底（单句块无句界，服务端必 split ok），同块情绪。产物仍按块
            # 成员摘要落盘——同输入+定种子下切分失败可复现，复跑直接命中而非每次重试整块。
            # 尾垫只给末句（同块合成口径）：服务端单句路径无条件补垫，非末句须传 0
            print(
                f"WARN 块切分失败（{resp.get('reason', '未知')}），退回逐句合成："
                f"{block_items[0]['id']}…共 {n} 句",
                file=sys.stderr,
            )
            split_note = "fallback"
            clips = []
            for k, item in enumerate(block_items):
                one = await request(
                    block_synth_text([item]),
                    [weights[k]],
                    item["id"],
                    tail_pad_sec if k == n - 1 else 0.0,
                )
                got = one.get("clips") if one.get("split") == "ok" else None
                if not got or len(got) != 1:
                    raise NonRetryableError(
                        f"逐句兜底仍切分失败（{item['id']}）: {one.get('reason', '未知')}"
                    )
                clips.append(got[0])
        fmts = {c.get("format") for c in clips}
        if fmts != {"mp3"}:  # 同逐句路径的编码器守卫：WAV 字节不得落成 .mp3
            raise NonRetryableError(
                f"服务端编码器不可用（format={','.join(sorted(map(str, fmts)))}）"
                f"—— 按 {MANUAL} §七 检查 soundfile/lameenc，或用当前 tts_server.py 重启服务"
            )
        for k, clip in enumerate(clips):
            item = block_items[k]
            mp3 = out_dir / f"{item['id']}.mp3"
            meta = out_dir / f"{item['id']}.sha"
            audio = base64.b64decode(clip["audio"])
            if not audio:
                raise RuntimeError(f"空音频响应（{item['id']}）")
            mp3.write_bytes(audio)
            meta.write_text(digests[k])
            store_deposit(mp3, item["id"], digests[k], store, slug)
    else:
        # 同逐句路径：整块命中但库中缺档（曾 --no-store 或入库失败）⇒ 回填
        for k, item in enumerate(block_items):
            if not store_has(store, slug, item["id"], digests[k]):
                store_deposit(
                    out_dir / f"{item['id']}.mp3", item["id"], digests[k], store, slug
                )

    results = []
    for item in block_items:
        # 合成与命中同口径实测 mp3 时长（同逐句路径）：否则复跑时 manifest 随缓存状态漂移
        dur = mp3_duration(out_dir / f"{item['id']}.mp3")
        r = {**item, "durationSec": round(dur, 3)}
        if split_note:
            r["blockSplit"] = split_note
        results.append(r)
    return results


# ---------------- 段落演绎（story 档）：故事块划分 + 块音频切分 ----------------
#
# 机制：同幕连续句拼成一次 /synthesize（块文本 ≤118 token 时上游单段连续生成，
# 句间是模型自带的自然停顿）；响应在服务端按句界切回 N 个 mp3。切分/划块的本体
# 是下面的纯函数——numpy 惰性 import，唯一执行者是 tts_server.py（它本就从本模块
# 导入常量，且持有 mp3 编码前的 float32 PCM）；客户端 tts.py 只有 mutagen、
# 不 import 兄弟模块（test_tts_lang_mirror 钉死），永不触碰这些函数。
#
# 实测定档依据（2026-09-25，dream-rsi P0）：
# - 句界自然停顿 0.31–0.55 s 与句内逗号停顿 0.14–0.42 s 区间重叠 ⇒ 不能「取最长
#   N−1 个静音」，按字符占比期望位置就近选（DP），4/4 块选对且最近错误候选 ≥0.5 s；
# - 停顿保留在音频内：句界静音正中丢弃恰好 sentenceGapSec，时间轴又加回同值
#   ⇒ 听感＝自然停顿原值，frozen 模板与 14 集零波及。


def sentence_weight(text: str) -> float:
    """句「发音量」权重：期望切点按各句权重占比内插。

    口径：CJK/数字=1、拉丁字母=0.35（约 1 个音节）、句中标点=1.5（拖停顿），
    其余字符（空格/引号）不计。够粗——DP 容差 ±max(1.0, 0.15T) 秒吸收估计误差。
    """
    import unicodedata

    w = 0.0
    for ch in text:
        if ch in "，、；：？！…—":
            w += 1.5
            continue
        cat = unicodedata.category(ch)
        if ch.isdigit() or cat.startswith("Lo"):  # 中日韩表意文字按 1
            w += 1.0
        elif ch.isalpha():  # 拉丁字母按 0.35
            w += 0.35
    return w


def plan_blocks(items: list[dict], cfg: dict) -> list[list[dict]]:
    """narration items → 故事块（同幕连续句的列表的列表）。

    硬边界：幕界 + 台本 blockStart（item 里的 cue 台本由 build_narration 落成
    blockStart:true）。无台本段自动划分：先按位置切成 2×max_sentences 句的定长窗
    （1 句尾窗并入前窗），窗内块数取 ≥max(⌈n/3⌉,⌈ΣL/90⌉) 的首个可行值，DP 最小化
    块长方差，块 ≤max_sentences 句、≤max_chars 字（合成文本口径，超限单句自成一块）。
    台本段超限被拆开时，后续子块继承段首 cue（块首句浅拷贝注入，不改原件）。
    """
    ms, mc = cfg.get("max_sentences", 3), cfg.get("max_chars", 90)

    def synth_len(i: dict) -> int:
        return len(synth_source_text(i))

    blocks: list[list[dict]] = []
    run: list[dict] = []

    def window_cuts(seg: list[dict]) -> list[int]:
        n = len(seg)
        total = sum(synth_len(i) for i in seg)
        k_min = min(n, max(1, -(-n // ms), -(-total // mc)))
        # DP：best[end][j]＝前 end 句切成 j 块（块句数 ≤ms、多句块长 ≤mc）的最小块长方差。
        # k_min 只是下界：装箱约束下恰好 k_min 块常切不出，逐层放宽到首个可行块数
        # （j=n 即逐句，必可行）——否则整窗会整体退化为逐句
        INF = float("inf")
        best: list[list[tuple[float, int]]] = [
            [(INF, -1)] * (n + 1) for _ in range(n + 1)
        ]
        best[0][0] = (0.0, -1)
        lens = [0]
        for i in seg:
            lens.append(lens[-1] + synth_len(i))
        k = n
        for j in range(1, n + 1):
            for end in range(1, n + 1):
                for start in range(max(0, end - ms), end):
                    seglen = lens[end] - lens[start]
                    if seglen > mc and start + 1 < end:
                        continue  # 多句块不许超字数；单句超长只能自成一块放行
                    prev = best[start][j - 1][0]
                    if prev == INF:
                        continue
                    # 方差代理：Σlen²（固定块数与总量下最小化它＝最小化方差）
                    cand = prev + seglen * seglen
                    if cand < best[end][j][0]:
                        best[end][j] = (cand, start)
            if j >= k_min and best[n][j][0] < INF:
                k = j
                break
        cuts, end = [], n
        for j in range(k, 0, -1):
            cuts.append(end)
            end = best[end][j][1]
        cuts.append(0)
        cuts.reverse()
        return cuts

    def flush_auto(seg: list[dict]) -> None:
        # 定长窗：块界只依赖窗内句长 ⇒ 改一句至多重排所在窗（≤2×ms+1 句）。整段全局 DP
        # 下块界依赖段内全部句长，改一个字即可整段平移、整幕重录（14 集对拍：改字爆炸
        # 半径 max 34→7 句，块数 +2.6%）。窗界按位置而非内容，插/删句仍重排同段其后各窗
        starts = list(range(0, len(seg), 2 * ms))
        if len(starts) > 1 and len(seg) - starts[-1] == 1:
            starts.pop()  # 1 句尾窗并入前窗：幕末收束句不孤立成逐句合成
        cuts = [0]
        for a, b in zip(starts, [*starts[1:], len(seg)]):
            cuts += [a + c for c in window_cuts(seg[a:b])[1:]]
        cue = seg[0].get("cue")
        for a, b in zip(cuts, cuts[1:]):
            blk = seg[a:b]
            if a and cue:  # 台本段被上限拆开：子块沿用段首情绪，不在段中途换档
                blk = [{**blk[0], "cue": cue}, *blk[1:]]
            blocks.append(blk)

    for i in items:
        hard = i.get("blockStart") or (run and run[-1]["scene"] != i["scene"])
        if hard and run:
            flush_auto(run)
            run = []
        run.append(i)
    if run:
        flush_auto(run)
    return blocks


def block_synth_text(items: list[dict]) -> str:
    """块的合成文本＝成员句拼接；句末无停顿标点者补 `。`（上游按标点断句合并段）。

    `，：、——` 结尾是原稿有意的续接（本身即停顿、可作切点候选），原样保留——追加 `。`
    会拼出 `，。`（上游映射为 `,.` 双标点）并把续接改成句末降调。收引号/括号不算末字：
    `不可能！”` 按 `！` 判定，否则会拼出 `！”。` 同类双标点。
    """
    PAUSE = "。！？…；，：、—"
    CLOSERS = "”’」』）)》】\"'"
    parts = []
    for i in items:
        t = synth_source_text(i).strip()
        body = t.rstrip(CLOSERS)
        if body and body[-1] not in PAUSE:
            t += "。"
        parts.append(t)
    return "".join(parts)


def block_digest_suffix(
    member_texts: list[str], discard: float, tail_pad: float
) -> str:
    """块缓存后缀（仅块模式追加）：改任一句/切分参数 ⇒ 整块换 digest 重录。

    `split=vN` 版本化块文本拼接与切分算法（v2：软停顿结尾不再补 `。`；v3：收引号前
    的标点计入末字、逐句兜底仅末句补尾垫）——算法改变合成结果而成员文本不变时，靠它换键。
    换键口径：改了送合成文本或切段时长（⇒ 时间轴）才递增；静音内的样本级淡变（如末段
    补 5ms 淡入）时长不变、听感不可辨，不换键——否则存量音频会为不可听差异整块重录。
    """
    payload = "\x1f".join(member_texts) + f"\x1f{discard!r}\x1f{tail_pad!r}\x1fsplit=v3"
    return hashlib.sha1(payload.encode()).hexdigest()[:12]


def frame_db(pcm, sr: int, hop_sec: float = 0.01, win_sec: float = 0.025):
    """帧 RMS → dB（10 ms hop / 25 ms win，与实测标定一致）。pcm: float32 1-D。"""
    import numpy as np

    hop, win = int(sr * hop_sec), int(sr * win_sec)
    n = 1 + max(0, (len(pcm) - win) // hop)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    frames = pcm[idx]
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    return 20 * np.log10(np.maximum(rms, 1e-9))


def silence_runs(
    db, sr: int, hop_sec: float = 0.01, min_sec: float = 0.12, below_db: float = 35.0
):
    """低于 p95−below_db 的连续帧 → (内部静音段列表, 语音起, 语音止)。

    只保留首尾语音之间的内部段（块首/块尾静音不是切点候选）；返回三元组，
    语音起止供 plan_block_cuts 内插期望位置。
    """
    import numpy as np

    thr = np.percentile(db, 95) - below_db
    quiet = db < thr
    idx = np.flatnonzero(np.diff(quiet.astype(int)) != 0) + 1
    bounds = np.concatenate(([0], idx, [len(quiet)]))
    runs = [
        (bounds[k] * hop_sec, bounds[k + 1] * hop_sec)
        for k in range(len(bounds) - 1)
        if quiet[bounds[k]] and bounds[k + 1] - bounds[k] >= min_sec / hop_sec
    ]
    speech = np.flatnonzero(~quiet)
    if not len(speech):
        return [], 0.0, len(db) * hop_sec
    on, off = speech[0] * hop_sec, (speech[-1] + 1) * hop_sec
    return [(s, e) for s, e in runs if s > on and e < off], float(on), float(off)


def plan_block_cuts(
    runs, weights: list[float], total_sec: float, speech_on: float, speech_off: float
):
    """在候选静音里为 N−1 个句界各选一个切点。

    期望位置 exp_k 按累计权重占比内插；DP 选严格递增候选最小化
    Σ((mid−exp)/σ)² − 0.3·ln(段长/0.1)（长静音略优先）；门：|mid−exp| ≤ max(1.0, 0.15T)
    且各句语音占比 ∈[0.5,1.8]×期望。返回 (mid_1..mid_{N-1}, cut_runs) 或 None。
    """
    import math

    n = len(weights)
    if n < 2:
        return None
    total_w = sum(weights)
    cum = [sum(weights[:k]) / total_w for k in range(1, n)]
    exp = [speech_on + (speech_off - speech_on) * c for c in cum]
    sigma = max(0.35, 0.06 * total_sec)
    tol = max(1.0, 0.15 * total_sec)

    INF = float("inf")
    m = len(runs)
    # dp[j][k]：第 k 个界用候选 j 的最小代价
    dp = [[INF] * (n - 1) for _ in range(m)]
    par = [[-1] * (n - 1) for _ in range(m)]
    for j, (s, e) in enumerate(runs):
        mid = (s + e) / 2
        cost = ((mid - exp[0]) / sigma) ** 2 - 0.3 * math.log((e - s) / 0.1)
        if abs(mid - exp[0]) <= tol:
            dp[j][0] = cost
    for k in range(1, n - 1):
        best = INF
        best_j = -1
        for j, (s, e) in enumerate(runs):
            if best_j >= 0:
                mid = (s + e) / 2
                if abs(mid - exp[k]) <= tol:
                    cost = (
                        best
                        + ((mid - exp[k]) / sigma) ** 2
                        - 0.3 * math.log((e - s) / 0.1)
                    )
                    if cost < dp[j][k]:
                        dp[j][k] = cost
                        par[j][k] = best_j
            if dp[j][k - 1] < best:
                best, best_j = dp[j][k - 1], j
    end_j = min(range(m), key=lambda j: dp[j][n - 2]) if m else -1
    if m == 0 or dp[end_j][n - 2] == INF:
        return None
    chosen = [0] * (n - 1)
    j = end_j
    for k in range(n - 2, -1, -1):
        chosen[k] = j
        j = par[j][k]
    picked = [runs[j] for j in chosen]
    # 语音占比门：切后各段语音时长与期望占比偏离 ∈[0.5,1.8]
    spans = []
    prev = speech_on
    for s, e in picked + [(speech_off, speech_off)]:
        spans.append((prev, s))
        prev = e
    for k, (a, b) in enumerate(spans):
        share = (b - a) / (speech_off - speech_on)
        want = weights[k] / total_w
        if not 0.5 <= share / want <= 1.8:
            return None
    return picked


def split_block_pcm(pcm, sr: int, runs, discard_sec: float, tail_pad_sec: float = 0.0):
    """按切点把块 PCM 切成 N 段：每界从静音正中丢弃 discard_sec，每段两端 5ms 淡入淡出。

    discard 的语义：时间轴随后会加回 sentenceGapSec ⇒ 听感＝自然停顿原值；
    静音不足 gap+2m 时退化为丢 S−2m（下限 0.06 s 余量）。末段统一补尾垫。
    返回 [(clip_pcm, 自然停顿 S_k)]。
    """
    import numpy as np

    margin = 0.03
    fade = int(sr * 0.005)
    out = []
    cursor = 0
    for s, e in runs:
        nat = e - s
        d = min(discard_sec, max(0.0, nat - 2 * margin))
        cut_start = s + (nat - d) / 2
        clip = pcm[int(cursor * sr) : int(cut_start * sr)].copy()
        if len(clip) > 2 * fade:
            clip[:fade] *= np.linspace(0, 1, fade)
            clip[-fade:] *= np.linspace(1, 0, fade)
        out.append((clip, nat))
        cursor = cut_start + d
    clip = pcm[int(cursor * sr) :].copy()
    if len(clip) > 2 * fade:  # 末段起点即末个切点（静音≠零值）：与中间段同口径两端淡变
        clip[:fade] *= np.linspace(0, 1, fade)
        clip[-fade:] *= np.linspace(1, 0, fade)
    if tail_pad_sec > 0:
        clip = np.concatenate([clip, np.zeros(int(tail_pad_sec * sr), np.float32)])
    out.append((clip, 0.0))
    return out


# ---------------- 主流程 ----------------


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="逐句 TTS 合成 + 时长 manifest（双引擎）"
    )
    parser.add_argument(
        "--engine",
        choices=["edge", "indextts"],
        default="edge",
        help="edge=预置音色（默认）；indextts=声音克隆（需本地服务）",
    )
    parser.add_argument(
        "--project", default=".", help="视频工程根目录（含 script/ 与 video/）"
    )
    parser.add_argument(
        "--narration-lang",
        default="zh",
        choices=list(LANG_MIRROR),
        help="逐字稿语言：选输入 json（zh=script/narration.json、en=script/narration.en.json）"
        "与输出目录（zh=video/public/audio/、en=…/audio/en/，含独立 manifest 与 .engine 签名）",
    )
    parser.add_argument(
        "--voice",
        default=None,
        help="[edge] 语音（缺省按 --narration-lang 解析：zh→zh-CN-YunxiNeural、"
        "en→en-US-AndrewNeural）",
    )
    parser.add_argument("--rate", default=DEFAULT_RATE, help="[edge] 语速（默认 +4%%）")
    parser.add_argument("--force", action="store_true", help="忽略缓存强制重合成")
    parser.add_argument(
        "--no-store",
        action="store_true",
        help="[indextts] 禁用音频版本库（默认启用；库根目录可用环境变量 TO_VIDEO_TTS_STORE 覆盖）",
    )
    parser.add_argument(
        "--allow-voice-switch",
        action="store_true",
        help="放行音色签名变更（引擎/音色/风格换档＝整集重录，须显式确认）",
    )
    parser.add_argument("--list-styles", action="store_true", help="列出风格预设并退出")

    idx = parser.add_argument_group("indextts 声音克隆")
    idx.add_argument(
        "--ref",
        default=None,
        help="[indextts] 参考音色样本路径（建议 10–14s 干净人声；硬上限 15s，上游超出即静默前截）",
    )
    idx.add_argument(
        "--expect-ref-sha1",
        default=None,
        metavar="12HEX",
        help="[indextts] 期望的参考样本 sha1 前 12 位，不符即硬失败——pipeline.py 从"
        "各集 pipeline.toml 自动带上，防「换样本静默重录整集」（指纹清单见 voices/refs.toml）",
    )
    idx.add_argument(
        "--server", default="http://127.0.0.1:8766", help="[indextts] 服务地址"
    )
    idx.add_argument(
        "--style",
        default="neutral",
        choices=list(STYLE_PRESETS),
        help="[indextts] 风格预设（默认 neutral）",
    )
    idx.add_argument(
        "--emo-vector",
        default=None,
        help="[indextts] 原始情感向量，如 happy:0.6,calm:0.2（与 --style 非默认值互斥）",
    )
    idx.add_argument(
        "--emo-ref",
        default=None,
        help="[indextts] 情感参考音频：音色仍取 --ref，语调/情绪迁移自这段录音（比向量注入更自然；"
        "与 --style 非默认值/--emo-vector/--emo-text 互斥）",
    )
    idx.add_argument(
        "--emo-text",
        default=None,
        help="[indextts] 自然语言情感描述，如「轻快爽朗、自信阳光」（需服务端 --use-qwen-emo；"
        "与 --style 非默认值/--emo-vector/--emo-ref 互斥）",
    )
    idx.add_argument(
        "--emo-alpha",
        default=None,
        type=float,
        help="[indextts] 情感强度 0–1（默认随风格）",
    )
    idx.add_argument(
        "--duration-factor",
        default=None,
        type=float,
        help="[indextts] 语速 0.5–2.0（默认随风格）",
    )
    idx.add_argument(
        "--lang",
        default=None,
        help="[indextts] 语言（缺省按 --narration-lang 解析：zh→ZH、en→EN；"
        "显式给值须与之一致，冲突即报错退出）",
    )
    idx.add_argument(
        "--num-beams",
        default=None,
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="[indextts] GPT 束搜索宽度（缺省随风格，多数预设为 1、sunny-steady 为 3；"
        "束宽越大韵律越稳但 GPT 段耗时约按束宽线性放大——长篇批量跑 1，定稿可试 3）",
    )
    idx.add_argument(
        "--steady",
        default=None,
        metavar="P0,p3-25b,p5-*",
        help="[indextts] 混合档：仅这些句子改用高束宽（默认 3），其余仍按风格的束宽。"
        "支持幕名（P0）/精确句 id（p3-25b）/前缀通配（p5-*），逗号分隔、大小写不敏感。"
        "用于把冷开场与金句升到更稳的档而不拖长整集耗时",
    )
    idx.add_argument(
        "--steady-beams",
        default=3,
        type=int,
        choices=[2, 3, 4, 5],
        help="[indextts] --steady 命中句所用束宽（默认 3）",
    )
    idx.add_argument(
        "--plan",
        action="store_true",
        help="[indextts] 只打印合成计划（各束宽句数、缓存命中/待合成、耗时估算）并退出，不连服务",
    )
    idx.add_argument(
        "--engine-tag",
        default="indextts",
        help="[indextts] 缓存标记；模型升级后自定义以失效旧缓存",
    )

    # 采样参数族：上游经 **generation_kwargs 透传给 HF generate，此前全部隐式继承上游默认，
    # 任何调优都得改服务源码。显式化后它们会**进缓存摘要**（仅在 ≠ 上游默认时），故改参必然
    # 重合成，不会出现「改了参数却命中旧缓存 ⇒ 误判无效果」这类假验证。
    # 缺省一律 None = 取风格预设的 sampling，再退到上游默认（见 resolve_sampling）。
    smp = parser.add_argument_group(
        "indextts 采样参数（专家级，缺省即上游默认；改任一项都会失效该句缓存）"
    )
    smp.add_argument(
        "--temperature",
        default=None,
        type=float,
        help="[indextts] 采样温度 0.1–2.0（上游默认 0.8）。收紧可降低长视频的句间韵律漂移，"
        "过紧会滑向单调播报",
    )
    smp.add_argument(
        "--top-p",
        default=None,
        type=float,
        help="[indextts] 核采样 0–1（上游默认 0.8）",
    )
    smp.add_argument(
        "--top-k",
        default=None,
        type=int,
        help="[indextts] top-k 0–100（上游默认 30；0=关闭，1 在束搜索下不安全故禁用）",
    )
    smp.add_argument(
        "--length-penalty",
        default=None,
        type=float,
        help="[indextts] 束打分长度惩罚 -2–2（上游默认 0.0）。**0.0 不是中性**：打分不做长度"
        "归一化而对数概率恒负，故系统性偏好更短假设，是 --num-beams>1 时吞尾/漏字的机制来源。"
        "抬到 0.3–1.0 可缓解；仅束搜索打分时生效，--num-beams 1 下改它无效",
    )
    smp.add_argument(
        "--repetition-penalty",
        default=None,
        type=float,
        help="[indextts] 重复惩罚 0.1–20（上游默认 10.0，自 v1 沿用且无测试支撑）。"
        "作用在语义码头上、是对 logit 的符号相关缩放；有效强度依赖 logit 绝对尺度，"
        "故**与音色/情感向量耦合**，跨音色不可迁移调参结论",
    )
    smp.add_argument(
        "--max-mel-tokens",
        default=None,
        type=int,
        help="[indextts] 生成上限 50–1815（上游默认 1500 ≈30 s；1815 为架构上限 ≈36.2 s）。"
        "溢出后果不是音频被裁短，而是文本尾部根本没被念出。本管线单句远未触顶，通常不需要动",
    )
    smp.add_argument(
        "--interval-silence",
        default=None,
        type=int,
        help="[indextts] 单请求内**分段之间**的静音毫秒（上游默认 200）。本管线逐句合成、"
        "单句远低于分段预算，故默认不生效；句间停顿由 video/src/timing.json 的 sentenceGapSec 决定",
    )
    smp.add_argument(
        "--no-text-normalization",
        action="store_true",
        help="[indextts] 关闭上游中文文本归一化（v2.5 专属）。**通常不要用**：实测 %% / 小数 /"
        "量词 / 月日 / 章节的读法本来就正确，关掉等于把全部读法责任推给逐字稿；"
        "发音标注 <字|读音> 本身免疫归一化，不需要为保标记而关它",
    )
    smp.add_argument(
        "--seed",
        default=None,
        type=int,
        help="[indextts] 随机种子。上游 do_sample 恒 True 且全链路无种子，同句每次合成都是"
        "不同的 take；给定种子后逐句可复现——这是任何参数 A/B 可信的前提",
    )
    smp.add_argument(
        "--seed-offset",
        default=0,
        type=int,
        help="[indextts] 与 --seed 相加（默认 0）。固定种子会把某句锁死在一条可能不佳的"
        "采样结果上，偏移一位即可换一条 take 而仍然可复现",
    )
    args = parser.parse_args()
    args.server = args.server.rstrip(
        "/"
    )  # 尾斜杠归一：health/synthesize 两处拼 URL 前收口

    # 语言解析：--lang/--voice 未显式给出时按 --narration-lang 从镜像表取缺省——
    # `--narration-lang en` 下绝不能静默回落 ZH/中文音色（digest 与音色都会错槽位）。
    want_lang, want_voice = LANG_MIRROR[args.narration_lang]
    # 显式 --lang 与镜像解析值冲突即拦（两引擎统一）：错语言 take 的 digest 自洽，
    # 后续会当缓存命中，事后只能靠听发现。
    if args.lang is not None and args.lang != want_lang:
        parser.error(
            f"--lang {args.lang} 与 --narration-lang {args.narration_lang}"
            f"（应为 {want_lang}）冲突——省略 --lang 即按逐字稿语言自动解析"
        )
    tts_lang = want_lang  # 冲突已拦：显式值若给出必与镜像解析值相等
    voice = args.voice if args.voice is not None else want_voice

    if args.list_styles:
        print(
            "风格            说明      情感向量（happy,angry,sad,afraid,disgusted,melancholic,surprised,calm）"
            "  alpha  有效注入  语速  束宽"
        )
        for name, p in STYLE_PRESETS.items():
            vec = (
                ",".join(f"{x:g}" for x in p["vec"]) if p["vec"] else "—（不注入情感）"
            )
            eff = (sum(p["vec"]) * p["alpha"]) if p["vec"] else 0.0
            smp_note = (
                ""
                if not p.get("sampling")
                else "  采样 "
                + ",".join(f"{k}={v!r}" for k, v in sorted(p["sampling"].items()))
            )
            print(
                f"{name:<14}  {p['label']:<6}  {vec:<62}  {p['alpha']:<5}  "
                f"{eff:<8.3g}  {p['df']:<4}  {p.get('beams', 1)}{smp_note}"
            )
        print(
            "\n采样参数（temperature/top_p/top_k/length_penalty/repetition_penalty/"
            "max_mel_tokens/interval_silence）未在任何预设中覆盖，"
            "均取上游默认："
            + ", ".join(f"{k}={v!r}" for k, v in SAMPLING_DEFAULTS.items())
        )
        return

    if args.engine == "edge":
        # --plan 语义是「只看不跑」，而 edge 无束宽/无估时口径。若沿用「提示后照跑」的处理，
        # 漏写 --engine indextts 时会静默全量合成，把整集克隆音频改写成 edge 预置音色
        # （两引擎摘要必然不同，且 {id}.mp3 单槽位），故此处硬失败而非忽略。
        if args.plan:
            parser.error(
                "--plan 仅对 --engine indextts 生效（是否漏写 --engine indextts？）"
            )
        # 克隆专属参数分两类处置。**带值参数硬失败**：漏写 --engine indextts 的典型手型
        # 就是「照抄文档打了 --ref/--style 却丢了 --engine」，而 {id}.mp3 是单槽位、
        # 两引擎摘要必然不同 ⇒ 照跑就会把整集克隆音频静默改写成 edge 预置音色。
        # 上面 --plan 已按此论证硬化，合成路径同理（否则只硬化了「看」、没硬化「跑」）。
        clone_only = [
            flag
            for flag, val in {
                "--ref": args.ref,
                "--emo-vector": args.emo_vector,
                "--emo-ref": args.emo_ref,
                "--emo-text": args.emo_text,
                "--emo-alpha": args.emo_alpha is not None,
                "--duration-factor": args.duration_factor is not None,
                "--num-beams": args.num_beams is not None,
                "--steady": args.steady,
                "--style": args.style != "neutral",
                # 采样参数族同属克隆专属：edge 不认这些旋钮，且两引擎摘要必然不同，
                # 照跑同样会把整集克隆音频改写成 edge 预置音色 ⇒ 与上面同口径硬失败。
                "--temperature": args.temperature is not None,
                "--top-p": args.top_p is not None,
                "--top-k": args.top_k is not None,
                "--length-penalty": args.length_penalty is not None,
                "--repetition-penalty": args.repetition_penalty is not None,
                "--max-mel-tokens": args.max_mel_tokens is not None,
                "--interval-silence": args.interval_silence is not None,
                "--no-text-normalization": args.no_text_normalization,
                "--seed": args.seed is not None,
            }.items()
            if val
        ]
        if clone_only:
            parser.error(
                f"以下参数仅对 --engine indextts 生效: {' '.join(clone_only)}"
                "（是否漏写 --engine indextts？若确实要用 edge 预置音色，请去掉这些参数）"
            )
        # 无副作用的旁路参数：给不到默认值也不会改变输出，只提示不失败
        benign = [
            flag
            for flag, val in {
                "--steady-beams": args.steady_beams != 3,
                "--server": args.server != "http://127.0.0.1:8766",
                "--engine-tag": args.engine_tag != "indextts",
                # --seed-offset 单独给值而没给 --seed 时无任何效果（见 resolve_sampling）
                "--seed-offset": args.seed_offset != 0 and args.seed is None,
            }.items()
            if val
        ]
        if benign:
            print(
                f"提示：以下参数仅对 --engine indextts 生效，已忽略: {' '.join(benign)}",
                file=sys.stderr,
            )

    root = Path(args.project).resolve()
    # 后缀规则内联（与 langs.narration_json / langs.audio_dir 同构，见 LANG_MIRROR 注）：
    # 主语言 zh 路径逐字节等于旧版，非主语言加 .<lang> 后缀 / 子目录。
    sfx = "" if args.narration_lang == "zh" else f".{args.narration_lang}"
    src = root / "script" / f"narration{sfx}.json"
    if not src.is_file():
        sys.exit(
            f"narration{sfx}.json 不存在: {src}"
            f" —— 先运行 build_narration.py --lang {args.narration_lang} 生成"
        )
    audio_base = root / "video" / "public" / "audio"
    out_dir = (
        audio_base if args.narration_lang == "zh" else audio_base / args.narration_lang
    )
    items = json.loads(src.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    store = store_root(args.no_store)
    slug = root.name

    if args.engine == "edge":
        signature = f"edge|{voice}|{args.rate}"
        check_voice_marker(out_dir, signature, args.allow_voice_switch)
        sem = asyncio.Semaphore(CONCURRENCY_EDGE)
        results = await asyncio.gather(
            *(
                synth_edge(sem, i, args.force, voice, args.rate, out_dir, tts_lang)
                for i in items
            )
        )
    else:
        # 情感三来源互斥：显式向量 / 情感参考音频 / 自然语言描述（服务端亦校验，此处提前失败）
        emo_sources = [
            f
            for f, v in (
                ("--emo-vector", args.emo_vector),
                ("--emo-ref", args.emo_ref),
                ("--emo-text", args.emo_text),
            )
            if v
        ]
        if len(emo_sources) > 1:
            parser.error(f"情感来源互斥，只能给一个：{' '.join(emo_sources)}")
        if args.style != "neutral" and emo_sources:
            parser.error(f"--style 非默认值与 {emo_sources[0]} 互斥")
        if args.emo_ref or args.emo_text:
            # 音频/文本驱动情感时不注入向量；alpha 默认 1.0（完全采用该情感来源）
            style_name = "emoref" if args.emo_ref else "emotext"
            vec = None
            alpha = args.emo_alpha if args.emo_alpha is not None else 1.0
            df = args.duration_factor if args.duration_factor is not None else 1.0
            beams = args.num_beams if args.num_beams is not None else 1
        else:
            try:
                style_name, vec, alpha, df, beams = resolve_style(args)
            except ValueError as e:
                parser.error(str(e))
        try:
            sampling = resolve_sampling(args)
        except ValueError as e:
            parser.error(str(e))
        if not args.ref:
            parser.error(
                "--engine indextts 需要 --ref 参考音色样本（见 " + MANUAL + " §三）"
            )
        ref_path = Path(args.ref).expanduser().resolve()
        if not ref_path.is_file():
            parser.error(f"参考样本不存在: {ref_path}")
        if args.emo_alpha is not None and not 0.0 <= args.emo_alpha <= 1.0:
            parser.error("--emo-alpha 必须在 [0, 1]")
        if (
            vec is not None and sum(vec) * alpha > 0.8
        ):  # infer 内部以 alpha 缩放，校验有效和
            parser.error(
                f"情感向量有效和 {sum(vec) * alpha:.3f}（Σvec×alpha）超过 0.8 上限"
            )
        if args.duration_factor is not None and not 0.5 <= args.duration_factor <= 2.0:
            parser.error("--duration-factor 必须在 [0.5, 2.0]")

        emo_ref_path = emo_ref_sha1 = None
        if args.emo_ref:
            p = Path(args.emo_ref).expanduser().resolve()
            if not p.is_file():
                parser.error(f"情感参考音频不存在: {p}")
            emo_ref_path = str(p)
            # 情感样本按内容入摘要：换情感录音必须失效缓存（与 ref 同口径）
            emo_ref_sha1 = hashlib.sha1(p.read_bytes()).hexdigest()[:12]
        ref_sha1 = hashlib.sha1(ref_path.read_bytes()).hexdigest()[:12]
        # 指纹硬校验：样本即音色。换样本 = 整集换音色，必须在长跑开始前失败
        if args.expect_ref_sha1 and args.expect_ref_sha1 != ref_sha1:
            parser.error(
                f"参考样本指纹不符：期望 {args.expect_ref_sha1}，实得 {ref_sha1}"
                f"（{ref_path}）——源录音或裁剪参数已变。"
                f"勿在未核验音色上跑长合成；指纹清单见 $V/refs.toml（$W/voices/）"
            )

        # 混合档：解析选择器并逐句定束宽（此处即失败，避免典型的「id 拼错→静默全按低束宽跑完」）
        beams_of: dict[str, int] = dict.fromkeys((i["id"] for i in items), beams)
        if args.steady:
            if args.steady_beams <= beams:
                parser.error(
                    f"--steady-beams {args.steady_beams} 不高于基础束宽 {beams}，混合档无意义"
                )
            try:
                sids, scenes, prefixes = parse_steady_selector(args.steady)
            except ValueError as e:
                parser.error(str(e))
            for tok in sorted(sids | scenes) + [p + "*" for p in prefixes]:
                one_id, one_scene, one_pre = parse_steady_selector(tok)
                if not any(steady_match(i, one_id, one_scene, one_pre) for i in items):
                    parser.error(
                        f"--steady 的 {tok!r} 未命中任何句子（幕名/句 id 拼错？）"
                    )
            for i in items:
                if steady_match(i, sids, scenes, prefixes):
                    beams_of[i["id"]] = args.steady_beams

        signature = f"indextts|{args.engine_tag}|{style_name}|{ref_sha1}"
        # 在 --plan 之前检查：排期正是发现「这次长跑将整集换音色」的最佳时机
        check_voice_marker(out_dir, signature, args.allow_voice_switch)

        # ── 段落演绎（story 档）：块模式解析 ─────────────────────────────
        # 块=同幕连续句一次合成（句间自然停顿），服务端切回逐句 mp3。仅预设声明 block
        # 时启用；EN 未验证（06-tts-voice 跨语种须试听）回退逐句；--steady 的逐句升束
        # 与「块=一个请求」冲突，硬拒。
        block_cfg = (STYLE_PRESETS.get(style_name) or {}).get("block")
        if block_cfg and tts_lang != "ZH":
            print(
                "提示：story 档块合成未在 EN 验证（跨语种须试听，见 references/06-tts-voice.md），"
                "EN 本次回退逐句合成",
                file=sys.stderr,
            )
            block_cfg = None
        # 须排在 EN 回退之后：回退逐句的 EN 版与 --steady 并不冲突
        if block_cfg and args.steady:
            parser.error("--steady 的逐句升束与块合成（story 档）冲突：整块同一束宽")
        perform_punct = bool(block_cfg and block_cfg.get("perform_punct"))
        # 句界丢弃量＝时间轴句距（时间轴随后加回 ⇒ 听感＝自然停顿原值）。
        # 直读 timing.json（不 import 兄弟模块），缺文件/缺键回退机制常数 0.32。
        discard_sec = 0.32
        if block_cfg:
            timing_json = root / "video" / "src" / "timing.json"
            if timing_json.is_file():
                try:
                    discard_sec = float(
                        json.loads(timing_json.read_text(encoding="utf-8"))[
                            "sentenceGapSec"
                        ]
                    )
                except (ValueError, KeyError, TypeError):
                    pass
        blocks: list[list[dict]] = plan_blocks(items, block_cfg) if block_cfg else []
        # 台本护栏提前到 --plan：长跑前发现 Σvec×alpha 超界、同块多条 [take]
        if block_cfg:
            for b in blocks:
                _, _, bad_id = resolve_block_vec(b, vec, alpha)
                if bad_id is not None:
                    parser.error(
                        f"{bad_id} 的台本情绪有效和超过 0.8 上限（见 {MANUAL} §4.2）"
                    )
                try:
                    block_sampling(b, sampling)
                except ValueError as e:
                    parser.error(str(e))

        if args.plan:  # 计划模式：纯本地计算，不连服务
            print(
                f">> 计划：{root.name} · 风格 {style_name} · alpha {alpha:g} · 语速 {df:g}"
                + (
                    ""
                    if not sampling
                    else " · 采样 "
                    + ",".join(f"{k}={sampling[k]!r}" for k in sorted(sampling))
                )
            )
            todo = {b: 0 for b in sorted(set(beams_of.values()))}
            cached = dict(todo)
            store_hits = dict(todo)
            if block_cfg:
                # 块=缓存单位：整块成员全部命中才算命中；改一句 ⇒ 整块重录
                cached_blocks = recoverable_blocks = todo_blocks = todo_members = 0
                recoverable_members = 0
                for b in blocks:
                    b_vec, b_alpha, _ = resolve_block_vec(b, vec, alpha)
                    b_sampling = block_sampling(b, sampling)
                    suffix = block_digest_suffix(
                        [synth_source_text(i) for i in b],
                        discard_sec,
                        block_cfg.get("tail_pad_sec", 0.18),
                    )
                    n = len(b)
                    all_local, all_recoverable = True, True
                    for k, i in enumerate(b):
                        d = digest_indextts(
                            ref_sha1,
                            style_name,
                            b_vec,
                            b_alpha,
                            df,
                            tts_lang,
                            args.engine_tag,
                            synth_source_text(i),
                            beams,
                            None,
                            None,
                            b_sampling,
                            suffix,
                            f"{k + 1}/{n}",
                        )
                        meta, mp3 = (
                            out_dir / f"{i['id']}.sha",
                            out_dir / f"{i['id']}.mp3",
                        )
                        local_ok = (
                            not args.force
                            and mp3.exists()
                            and mp3.stat().st_size > 0
                            and meta.exists()
                            and meta.read_text() == d
                        )
                        if not local_ok:
                            all_local = False
                            if args.force or not store_has(store, slug, i["id"], d):
                                all_recoverable = False
                    if all_local:
                        cached_blocks += 1
                    elif all_recoverable:
                        recoverable_blocks += 1
                        recoverable_members += n
                        todo_blocks += 1
                        todo_members += n
                    else:
                        todo_blocks += 1
                        todo_members += n
                # 同逐句口径：版本库整块直收不占合成时间，不进估时
                est = (
                    (todo_members - recoverable_members)
                    * AVG_SEC_PER_LINE
                    * (RTF_1BEAM if beams == 1 else RTF_MULTIBEAM)
                )
                print(
                    f"   块模式：{len(blocks)} 块 · 待合成 {todo_blocks} 块 / {todo_members} 句"
                    f" · 已整块缓存 {cached_blocks} 块"
                    + (
                        f" · 版本库可整块回收 {recoverable_blocks} 块"
                        if recoverable_blocks
                        else ""
                    )
                    + "（块=缓存单位，改一句重录整块）"
                )
                print(
                    f">> 待合成合计 {todo_members} 句（块口径）"
                    + (
                        f"（其中 {recoverable_blocks} 块 / {recoverable_members} 句由版本库整块直收，"
                        "不占合成时间）"
                        if recoverable_members
                        else ""
                    )
                    + f"，估算墙钟约 {est / 3600:.1f} 小时"
                    f"（长跑折算口径 RTF 1 束≈{RTF_1BEAM:g} / 高束宽≈{RTF_MULTIBEAM:g}，"
                    f"机器负载会显著影响，仅作排期参考）"
                )
                return
            for i in items:
                b = beams_of[i["id"]]
                d = digest_indextts(
                    ref_sha1,
                    style_name,
                    vec,
                    alpha,
                    df,
                    tts_lang,
                    args.engine_tag,
                    synth_source_text(i),
                    b,
                    emo_ref_sha1,
                    args.emo_text,
                    sampling,
                )
                meta, mp3 = out_dir / f"{i['id']}.sha", out_dir / f"{i['id']}.mp3"
                hit = (
                    not args.force
                    and mp3.exists()
                    and mp3.stat().st_size > 0
                    and meta.exists()
                    and meta.read_text() == d
                )
                (cached if hit else todo)[b] += 1
                if not hit and not args.force and store_has(store, slug, i["id"], d):
                    store_hits[b] += 1
            # 估时用**整集长跑折算口径**（含降频、机器争用与逐句开销），不是单句空闲口径：
            # 1 束 RTF≈13（三集 596 句实测 8.5 h 折算）、≥2 束≈45（短句 A/B 实测约 3.2 倍）；
            # 每句音频按 4.2s（三集均值）。单句空闲时可快到 RTF 6–7，故本估算偏保守。
            est = sum(
                (n - store_hits[b])
                * AVG_SEC_PER_LINE
                * (RTF_1BEAM if b == 1 else RTF_MULTIBEAM)
                for b, n in todo.items()
            )
            for b in sorted(todo):
                print(
                    f"   束宽 {b}：待合成 {todo[b]:>3} 句 · 已缓存 {cached[b]:>3} 句"
                    + (
                        f" · 版本库可回收 {store_hits[b]:>3} 句"
                        if store_hits[b]
                        else ""
                    )
                    + ("" if b == 1 else "（高束宽档）")
                )
            print(
                f">> 待合成合计 {sum(todo.values())} 句"
                + (
                    f"（其中 {sum(store_hits.values())} 句由版本库直收，不占合成时间）"
                    if sum(store_hits.values())
                    else ""
                )
                + f"，估算墙钟约 {est / 3600:.1f} 小时"
                f"（长跑折算口径 RTF 1 束≈{RTF_1BEAM:g} / 高束宽≈{RTF_MULTIBEAM:g}，"
                f"机器负载会显著影响，仅作排期参考）"
            )
            return

        try:
            health = await asyncio.to_thread(
                http_json, "GET", f"{args.server}/health", None, 10
            )
            if not health.get("ok"):
                raise RuntimeError(f"health.ok=false: {health}")
        except Exception as e:  # noqa: BLE001 - 服务未启动给出可操作指引
            print(
                f"IndexTTS 服务不可用（{e}）。请先启动：\n{server_launch_hint()}\n详见 {MANUAL} §二",
                file=sys.stderr,
            )
            sys.exit(1)
        if df != 1.0 and not health.get("supports_duration_factor"):
            parser.error(
                "当前服务为 IndexTTS-2（无语速控制）：去掉 --duration-factor，或风格选 neutral，见 "
                + MANUAL
            )
        if args.emo_text and not health.get("supports_emo_text"):
            parser.error(
                "当前服务未加载 QwenEmotion：重启服务加 --use-qwen-emo，或改用 --emo-vector/--emo-ref，见 "
                + MANUAL
            )
        # 采样参数/种子对旧服务是**静默丢弃**（Pydantic 默认忽略未声明字段），而摘要这边已经
        # 按新参数变了 ⇒ 会产出「摘要说改过、音频其实没改」的假验证。故显式硬失败。
        sampling_only = {k: v for k, v in sampling.items() if k != "seed"}
        if sampling_only and not health.get("supports_sampling_params"):
            parser.error(
                f"当前服务不支持采样参数（{','.join(sorted(sampling_only))}）：服务端代码过旧，"
                f"请用本 skill 当前 tts_server.py 重启服务，见 {MANUAL} §二"
            )
        if "seed" in sampling and not health.get("supports_seed"):
            parser.error(
                f"当前服务不支持 --seed：服务端代码过旧，请用本 skill 当前 tts_server.py 重启服务，见 {MANUAL} §二"
            )
        if sampling.get("text_normalization") is False and not health.get(
            "supports_text_normalization"
        ):
            parser.error(
                "当前服务为 IndexTTS-2（infer() 无 text_normalization 形参）："
                "去掉 --no-text-normalization，或改用 v2.5 服务"
            )
        if block_cfg and not health.get("supports_blocks"):
            parser.error(
                "当前服务不支持块合成（story 档需要）：服务端代码过旧，请用本 skill"
                f" 当前 tts_server.py 重启服务，见 {MANUAL} §二"
            )

        sem = asyncio.Semaphore(CONCURRENCY_INDEXTTS)
        if block_cfg:
            # 段落演绎：块=合成与缓存单位；逐块并发=1（服务端串行锁），结果按原顺序展平
            block_results = await asyncio.gather(
                *(
                    synth_block_indextts(
                        sem,
                        b,
                        args.force,
                        str(ref_path),
                        ref_sha1,
                        style_name,
                        vec,
                        alpha,
                        df,
                        tts_lang,
                        args.engine_tag,
                        args.server,
                        out_dir,
                        num_beams=beams,
                        sampling=sampling,
                        store=store,
                        slug=slug,
                        discard_sec=discard_sec,
                        tail_pad_sec=block_cfg.get("tail_pad_sec", 0.18),
                        perform_punct=perform_punct,
                    )
                    for b in blocks
                )
            )
            results = [r for br in block_results for r in br]
        else:
            results = await asyncio.gather(
                *(
                    synth_indextts(
                        sem,
                        i,
                        args.force,
                        str(ref_path),
                        ref_sha1,
                        style_name,
                        vec,
                        alpha,
                        df,
                        tts_lang,
                        args.engine_tag,
                        args.server,
                        out_dir,
                        # 逐句束宽：基础值来自「命令行优先、否则取预设」，--steady 命中句再提高
                        num_beams=beams_of[i["id"]],
                        emo_ref=emo_ref_path,
                        emo_ref_sha1=emo_ref_sha1,
                        emo_text=args.emo_text,
                        sampling=sampling,
                        store=store,
                        slug=slug,
                    )
                    for i in items
                )
            )

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    write_voice_marker(out_dir, signature)  # 成功收尾才落签名，中途失败不改变基线
    total = sum(r["durationSec"] for r in results)
    print(f"合成 {len(results)} 句，纯语音总时长 {total / 60:.2f} 分钟")
    if args.engine == "indextts" and args.steady:  # 混合档：回执两档各多少句，便于对账
        hi = sum(1 for i in items if beams_of[i["id"]] != beams)
        print(
            f"混合档：{len(items) - hi} 句按束宽 {beams}（{style_name}）+ "
            f"{hi} 句按束宽 {args.steady_beams}（--steady {args.steady}）"
        )
    print(f"manifest: {manifest_path}")


if __name__ == "__main__":
    asyncio.run(main())
