#!/usr/bin/env python3
"""IndexTTS 长跑自愈编排：健康检查 → 按端口冷重启服务 → 客户端续跑（RSI-022）。

- 定位：tts.py 只管单轮合成（幂等、逐句/逐块缓存续跑）；本脚本补**长跑编排**——
  服务掉线或 MPS 挂死（/health 假绿）时按端口冷重启 tts_server.py，再以**真实
  退出码**判定客户端成败；连续 N 轮失败（--max-restarts，默认 3）放弃并非零退出。
- 退出码纪律：上游自制 .sh 曾踩 `cmd | tail; $?` 陷阱（取的是 tail 的退出码，
  失败检测恒失效）——本脚本用 subprocess.run(...).returncode 结构性消除该类陷阱
  （tests/test_tts_resume.py 钉住负例）。
- 冷重启纪律：只杀 `--server` 解析出的那个端口的 LISTEN 进程（判据面=作用面），
  绝不 `pkill -f tts_server.py`——那会连带 8767 上他人的第二实例
  （references/07「服务生命周期」第 2 步）。
- 纯标准库（RSI 不变量 14）；服务启动命令从 tts.py 的 server_launch_hint 同构
  派生（--with 集合由测试对 hint 钉死防漂移，事实源仍在 tts.py）；长跑所需的
  服务端能力经 --use-qwen-emo 透传（RSI-035：冷重启不得静默降级服务能力——
  缺省不带，story 块情感走台本向量无需 QwenEmotion）；MPS 显存上限经
  --mps-mem-limit-gib 直传（RSI-036：缺省命令路径 env 兜底被服务端缺省 setter
  覆盖、实测无效——env 仅剩 --server-cmd 自定义命令路径）。
- 仅服务 indextts 长跑：edge 无服务端可自愈，直接跑 tts.py。

用法（`--` 之后的参数原样转发 tts.py；须与 tts.py 同解释器依赖面 --with mutagen）：
    uv run --no-project --with mutagen $T/scripts/tts_resume.py \
        -- --engine indextts --final-voice --project $P --ref $V/<样本>.wav \
        --expect-ref-sha1 <指纹> [--seed 4242] …
    （--final-voice＝本人显式点名的具名授权，RSI-040：入口预检缺它即拒、先于任何冷重启）
用法定义见 references/PIPELINE.md §三（脚本表）。
"""

from __future__ import annotations

import argparse
import http.client
import importlib.util
import json
import math
import os
import shlex
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tts  # noqa: E402 - SERVER_SCRIPT/启动 hint 单一事实源；tts.py 顶层纯标准库

DEFAULT_SERVER = "http://127.0.0.1:8766"
KILL_GRACE_SEC = 10.0  # SIGTERM 后等端口释放的上限，逾期 SIGKILL
POLL_SEC = 2.0  # 健康轮询间隔（上游 .sh 实证形态为 5s×60 次）
#: 服务冷启动（模型加载）~1–2 分钟，对齐上游 .sh 的 60×5s 等待预算。
STARTUP_TIMEOUT_SEC = 300.0
#: 放弃前允许的客户端失败轮数（上游 .sh 用 12；缺省取保守 3，可 --max-restarts 调回）。
MAX_RESTARTS = 3


def port_from_server(server: str) -> int:
    """从 --server URL 解析端口（冷重启的判据面=作用面）。"""
    parts = urllib.parse.urlsplit(server)
    if parts.port:
        return parts.port
    if parts.scheme == "https":
        return 443
    if parts.scheme == "http":
        return 80
    sys.exit(f"无法从 --server {server!r} 解析端口（需 http(s)://host:port 形态）")


def default_server_argv(
    port: int, use_qwen_emo: bool = False, mps_mem_limit_gib: float | None = None
) -> list[str]:
    """tts_server 启动命令的可执行形态——与 tts.server_launch_hint 同构。

    刻意不调用 hint 原文（含 cd ~/tools/index-tts 字面量与续行符，面向终端粘贴）；
    --with 集合与脚本路径的一致性由 tests/test_tts_resume.py 对 hint 钉死，事实源
    留在 tts.py（不另立第二事实源，RSI 不变量 10 同款纪律）。

    use_qwen_emo：透传 tts_server.py 同名 flag（RSI-035）——--emo-text 自然语言
    情感的长跑必传（冷重启不带会静默降级服务能力、客户端在健康门硬失败）；
    **缺省不带**：story 档块情感走台本 cue 向量，无需 QwenEmotion，无条件开会
    +1.5 GB 且 qwen 权重未下载的机器直接起不来（VOICE-CLONING §2.4）。
    mps_mem_limit_gib：透传 tts_server.py 同名 flag（RSI-036）——缺省命令路径
    服务端缺省即调 setter 设水位线、进程 env 注入被覆盖（实测无效），长跑调
    上限/禁用（0）只能走 flag 直传；缺省 None 不追加（服务端缺省
    min(0.90×recommended, 16) 即生效）。
    """
    argv = [
        "uv",
        "run",
        "--frozen",
        "--with",
        "fastapi",
        "--with",
        "uvicorn",
        "--with",
        "soundfile",
        "--with",
        "numpy",
        "--with",
        "lameenc",
        "python",
        str(tts.SERVER_SCRIPT),
        "--model-dir",
        "checkpoints",
        "--indextts-version",
        "2.5",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    if use_qwen_emo:
        argv.append("--use-qwen-emo")
    if mps_mem_limit_gib is not None:
        argv += ["--mps-mem-limit-gib", f"{mps_mem_limit_gib:g}"]
    return argv


def index_tts_root(override: str | None = None) -> Path:
    """服务运行环境（uv --frozen 的 cwd）：env VIBE_VIDEO_INDEX_TTS_ROOT 优先。"""
    return Path(
        override or os.environ.get("VIBE_VIDEO_INDEX_TTS_ROOT", "~/tools/index-tts")
    ).expanduser()


def mps_env(high: str | None, low: str | None) -> dict[str, str]:
    """MPS 水位线 env 兜底（可选）——**仅 --server-cmd 自定义命令路径**（调用点
    reconcile_mps 已圈定）：缺省命令路径下 tts_server.py 的 --mps-mem-limit-gib
    缺省即调 setter 设进程水位线（RSI-017），继承的 env 被覆盖、注入无效
    （RSI-036 实测：HIGH=0.0 注入后 /health 仍 15.98）——该路径调上限一律走
    --mps-mem-limit-gib flag 透传。

    配对纪律（RSI-017 评审①⑤，实测）：单设正的 HIGH 而不配 LOW（默认 low=1.4，
    凡 high<1.4 即 low>high）首个 MPS 分配即抛 invalid low watermark ratio——
    规则一刀切免边界推理；HIGH=0.0 是「禁用水位线」特例（上游 .sh 五集实证
    形态），无 LOW 冲突。
    """
    if high is None:
        if low is not None:
            sys.exit("--mps-low-ratio 须与 --mps-high-ratio 成对使用（单独无语义）")
        return {}
    try:
        high_v = float(high)
    except ValueError:
        sys.exit(f"--mps-high-ratio 非数值: {high!r}")
    if not math.isfinite(high_v) or high_v < 0:
        # nan/-inf 比较恒 False 会溜过 `> 0` 分支，负数同例——注入后 torch 首个
        # MPS 分配崩出的错误不含任何可定位信息，防呆须在入口拦。
        sys.exit(
            f"--mps-high-ratio 须为 ≥ 0 的有限数（0.0 = 禁用水位线），实际 {high!r}"
        )
    if high_v > 0 and low is None:
        sys.exit(
            "单设正的 --mps-high-ratio 而不配 --mps-low-ratio：默认 low=1.4，"
            "high<1.4 时首个 MPS 分配即抛 invalid low watermark ratio"
            "（RSI-017 配对纪律，一刀切免边界推理）；high=0.0（禁用水位线）除外"
        )
    env = {"PYTORCH_MPS_HIGH_WATERMARK_RATIO": high}
    if low is not None:
        env["PYTORCH_MPS_LOW_WATERMARK_RATIO"] = low
    return env


def reconcile_mps(args: argparse.Namespace) -> dict[str, str]:
    """MPS 旋钮归位（RSI-036）：缺省命令路径只认 flag 透传，env 兜底圈定
    --server-cmd；返回注入 extra_env。

    - --mps-mem-limit-gib：透传 tts_server.py 同名 flag（0=禁用 high watermark）。
      入口校验 ≥0 有限值——坏值若透传到服务端，冷重启会**先杀掉健康服务**、新
      进程才被服务端 argparse 拦下（起不来），自愈器必须先于杀服拦截。仅缺省
      启动命令可追加（--server-cmd 请把 flag 写进命令串）；与 env 旋钮互斥
      （flag 在场时 env 被服务端 setter 覆盖，两层各说各话）。
    - --mps-high-ratio/--mps-low-ratio：缺省命令路径下大声拒绝——env 注入被
      服务端缺省 setter 覆盖（RSI-036 实测无效），静默放过等于埋同一个坑。
    """
    v = args.mps_mem_limit_gib
    if v is not None:
        if not math.isfinite(v) or v < 0:
            # 与 mps_env 同款防呆：nan/-inf 比较恒 False，负数同例
            sys.exit(
                f"--mps-mem-limit-gib 须为 ≥ 0 的有限数（0=禁用 high watermark），"
                f"实际 {v!r}"
            )
        if args.server_cmd:
            sys.exit(
                "--mps-mem-limit-gib 只追加进缺省启动命令；--server-cmd 自定义命令"
                "请把 flag 写进命令串（编排器不猜用户命令的参数面）"
            )
        if args.mps_high_ratio is not None or args.mps_low_ratio is not None:
            sys.exit(
                "--mps-mem-limit-gib 与 --mps-high-ratio/--mps-low-ratio 互斥："
                "flag 透传路径下 env 被服务端 setter 覆盖（RSI-036），env 旋钮无效"
            )
    elif (
        args.mps_high_ratio is not None or args.mps_low_ratio is not None
    ) and not args.server_cmd:
        # low 单独在场同样拦在圈定门：此前误落 mps_env 的「须成对使用」，照做
        # 补 high 后又被本门驳回——两步矛盾链把用户引上必然被拒的路。
        sys.exit(
            "--mps-high-ratio/--mps-low-ratio 的 env 兜底仅服务 --server-cmd 自定义"
            "命令：缺省命令路径下 tts_server 缺省已调 setter 设水位线、env 注入被"
            "覆盖（RSI-036 实测无效）——调上限改用 --mps-mem-limit-gib 透传"
        )
    return mps_env(args.mps_high_ratio, args.mps_low_ratio)


def server_healthy(
    server: str, health_path: str = "/health", timeout: float = 5.0
) -> bool:
    """GET {server}{health_path}：HTTP 200 且 JSON ok 为真（判据同上游 .sh 的
    grep '"ok": *true'）。/health 假绿场景由「失败后无条件冷重启」兜底，不在此判。"""
    url = server.rstrip("/") + "/" + health_path.lstrip("/")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if getattr(resp, "status", 200) != 200:
                return False
            return bool(json.loads(resp.read()).get("ok"))
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException):
        # URLError/连接拒绝/超时(OSError 族)/坏 JSON(ValueError 族)/非 HTTP 回包
        # 或半截响应（HTTPException 族：BadStatusLine/IncompleteRead——实测不经
        # URLError/OSError 穿透，端口被非 HTTP 进程占用即此形态）一律按不健康
        return False


def port_listeners(port: int) -> list[int]:
    """按端口找 LISTEN 进程 pid（只查这一个端口——判据面=作用面）。"""
    try:
        r = subprocess.run(
            ["lsof", "-tnP", f"-iTCP:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        sys.exit("lsof 不可用——冷重启依赖按端口定位 LISTEN 进程（macOS 自带）")
    return [int(x) for x in r.stdout.split()]


def stop_server(port: int, grace_sec: float = KILL_GRACE_SEC) -> None:
    """按端口停服：SIGTERM → 等端口释放 → 逾期 SIGKILL。"""
    if not port_listeners(port):
        return

    def _signal(sig: int) -> None:
        for pid in port_listeners(port):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:  # 已退
                pass

    def _wait_free(sec: float) -> None:
        deadline = time.monotonic() + sec
        while time.monotonic() < deadline and port_listeners(port):
            time.sleep(0.2)

    _signal(signal.SIGTERM)
    _wait_free(grace_sec)
    _signal(signal.SIGKILL)
    _wait_free(grace_sec / 2)


def start_server(
    argv: list[str],
    cwd: Path,
    log_path: Path,
    extra_env: dict[str, str],
) -> subprocess.Popen:
    """后台拉起服务（新会话，输出追加进日志文件——不与客户端输出混流）。"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, **extra_env}
    try:
        with log_path.open("ab") as log:
            return subprocess.Popen(
                argv,
                cwd=str(cwd),
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except FileNotFoundError as e:
        # 根目录缺失（cwd 不存在）或启动命令不在 PATH（uv 未装）——服务掉线正是
        # 本脚本的靶场景，配置错误不许以裸 traceback 退场（对齐 port_listeners
        # 对 lsof 缺失的可操作退出先例）。
        sys.exit(
            f"服务起不来：{e}\n  检查 --index-tts-root / VIBE_VIDEO_INDEX_TTS_ROOT"
            f"（当前 {cwd}，须为存在的 index-tts checkout）与 --server-cmd"
            " 可执行（缺省经 uv，须在 PATH）"
        )


def wait_healthy(
    server: str,
    health_path: str,
    timeout_sec: float,
    poll_sec: float = POLL_SEC,
    probe_timeout: float = 5.0,
) -> bool:
    """冷启动等待：轮询 /health 直到超时（模型加载 ~1–2 分钟）。"""
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if server_healthy(server, health_path, timeout=probe_timeout):
            return True
        time.sleep(poll_sec)
    return False


def cold_restart(
    port: int,
    server_argv: list[str],
    cwd: Path,
    log_path: Path,
    extra_env: dict[str, str],
    server: str,
    health_path: str,
    startup_timeout: float,
) -> bool:
    """停旧 → 拉新 → 等健康；False = 服务起不来（调用方大声退出）。"""
    stop_server(port)
    start_server(server_argv, cwd, log_path, extra_env)
    return wait_healthy(server, health_path, startup_timeout)


def run_tts(forwarded: list[str]) -> int:
    """跑一轮 tts.py 并返回**真实退出码**（subprocess.run 直取 returncode）。

    禁 `cmd | tail; $?` 形态——那是 tail 的退出码（恒 0），失败检测失效
    （RSI-022 表因③；负例见 tests/test_tts_resume.py）。输出直通终端：
    长跑进度对调用方可见。
    """
    proc = subprocess.run([sys.executable, tts.__file__, *forwarded])
    return proc.returncode


def engine_value(forwarded: list[str]) -> str | None:
    """从转发参数里读 --engine（支持 `--engine X` 与 `--engine=X` 两种形态）。"""
    for i, tok in enumerate(forwarded):
        if tok == "--engine" and i + 1 < len(forwarded):
            return forwarded[i + 1]
        if tok.startswith("--engine="):
            return tok.split("=", 1)[1]
    return None


def require_indextts(forwarded: list[str]) -> None:
    """长跑自愈只对 indextts 有意义：edge 无服务端，直接跑 tts.py。"""
    eng = engine_value(forwarded)
    if eng != "indextts":
        sys.exit(
            "tts_resume 只服务 indextts 长跑（edge 无服务端可自愈，直接跑 tts.py）；"
            f"当前转发参数 --engine={eng or 'edge（tts.py 缺省）'}"
        )


def require_final_voice(forwarded: list[str]) -> None:
    """人为触发原则入口预检（RSI-040）：非 --plan 的 indextts 长跑必须带具名授权
    --final-voice——缺失在此拦，先于健康检查与任何冷重启（同「值校验先于杀服」
    纪律），与 tts.py 主闸同口径；--plan 豁免同主闸。"""
    if "--plan" in forwarded:
        return
    if "--final-voice" not in forwarded:
        sys.exit(
            "❌ 转发参数缺 --final-voice：IndexTTS 声音克隆须本人显式点名才可启用"
            "（每次合成、zh/en 每语言各算一次独立要求），缺省一律 edge 草声。"
            "若本人确已要求，请在 `--` 之后的 tts.py 参数里显式加 --final-voice"
            "（排期用 --plan 无需授权）；纪律见 references/07-tts-voice.md"
        )


def require_client_deps() -> None:
    """入口硬门禁：tts_resume 以当前解释器（sys.executable）跑 tts.py，mutagen
    缺失时不预检会**首句合成成功、写完 mp3 测时长才崩**（RSI-022 表因②，
    uv --no-project 裸调漏 --with 的历史形态）——长跑一轮空转数小时后才暴露。"""
    if importlib.util.find_spec("mutagen") is None:
        sys.exit(
            "❌ 客户端依赖 mutagen 缺失（当前解释器）：tts_resume 用同一解释器运行 "
            "tts.py，缺失会在首句合成成功、测时长时才崩。\n"
            "  修法：uv run --no-project --with mutagen "
            "$T/scripts/tts_resume.py …"
        )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="IndexTTS 长跑自愈编排（RSI-022）：`--` 之后的参数原样转发 tts.py",
    )
    p.add_argument(
        "--server",
        default=DEFAULT_SERVER,
        help=f"服务地址（缺省 {DEFAULT_SERVER}，与 tts.py 同款；冷重启端口从此解析）",
    )
    p.add_argument(
        "--health-path", default="/health", help="健康检查端点路径（缺省 /health）"
    )
    p.add_argument(
        "--health-timeout",
        type=float,
        default=5.0,
        help="单次健康探测超时秒（缺省 5，与 pipeline.py doctor 同款）",
    )
    p.add_argument(
        "--startup-timeout",
        type=float,
        default=STARTUP_TIMEOUT_SEC,
        help=f"冷启动等健康超时秒（缺省 {STARTUP_TIMEOUT_SEC:.0f}；模型加载 ~1–2 分钟）",
    )
    p.add_argument(
        "--max-restarts",
        type=int,
        default=MAX_RESTARTS,
        help=f"放弃前允许的客户端失败轮数（缺省 {MAX_RESTARTS}；上游 .sh 实证用 12）",
    )
    p.add_argument(
        "--server-cmd",
        default=None,
        help="覆写服务启动命令（整条命令字符串；缺省从 tts.py 派生同构命令）",
    )
    p.add_argument(
        "--use-qwen-emo",
        action="store_true",
        help="透传 tts_server.py 同名 flag（加载 QwenEmotion，约 +1.5 GB）：--emo-text "
        "自然语言情感的长跑必传——否则冷重启后服务静默降级、客户端在健康门硬失败"
        "（RSI-035）；story 档块情感走台本向量、无需此 flag；缺省不带，且仅作用于"
        "缺省启动命令（--server-cmd 时请把 flag 写进命令串）",
    )
    p.add_argument(
        "--index-tts-root",
        default=None,
        help="index-tts checkout 根（缺省 env VIBE_VIDEO_INDEX_TTS_ROOT 或 ~/tools/index-tts）",
    )
    p.add_argument(
        "--server-log",
        default=None,
        help="服务日志路径（缺省 .temp/tts-resume/server-<端口>.log，相对 CWD）",
    )
    p.add_argument(
        "--mps-mem-limit-gib",
        type=float,
        default=None,
        help="透传 tts_server.py 同名 flag（GiB；0=禁用 high watermark；缺省"
        " min(0.90×recommended, 16) 即生效）——长跑调显存上限走 flag 直传：缺省命令"
        "路径 env 注入被服务端 setter 覆盖、实测无效（RSI-036）；与 --mps-high-ratio"
        " 互斥，仅缺省启动命令（--server-cmd 时写进命令串）",
    )
    p.add_argument(
        "--mps-high-ratio",
        default=None,
        help="注入 PYTORCH_MPS_HIGH_WATERMARK_RATIO（0<high<1.4 须配 --mps-low-ratio；"
        "0.0=禁用水位线）——**仅 --server-cmd 自定义命令生效**：缺省命令路径被服务端"
        "缺省 setter 覆盖（RSI-036 实测无效），改用 --mps-mem-limit-gib",
    )
    p.add_argument(
        "--mps-low-ratio",
        default=None,
        help="注入 PYTORCH_MPS_LOW_WATERMARK_RATIO（与 --mps-high-ratio 成对；同样"
        "仅 --server-cmd 自定义命令生效——缺省命令路径改用 --mps-mem-limit-gib）",
    )
    return p


def split_forwarded(argv: list[str]) -> tuple[list[str], list[str]]:
    """argv 在首个 `--` 处切开：左侧归 tts_resume，右侧原样转发 tts.py。"""
    if "--" in argv:
        i = argv.index("--")
        return argv[:i], argv[i + 1 :]
    return argv, []


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    own, forwarded = split_forwarded(raw)
    parser = build_parser()
    args = parser.parse_args(own)
    if not forwarded:
        parser.error(
            "缺少转发给 tts.py 的参数（-- 之后，至少须有 --engine indextts --project …）"
        )
    require_indextts(forwarded)
    require_final_voice(forwarded)
    require_client_deps()
    if args.use_qwen_emo and args.server_cmd:
        sys.exit(
            "--use-qwen-emo 只追加进缺省启动命令；--server-cmd 自定义命令请把 flag "
            "写进命令串（编排器不猜用户命令的参数面）"
        )
    extra_env = reconcile_mps(args)

    port = port_from_server(args.server)
    server_argv = (
        shlex.split(args.server_cmd)
        if args.server_cmd
        else default_server_argv(
            port,
            use_qwen_emo=args.use_qwen_emo,
            mps_mem_limit_gib=args.mps_mem_limit_gib,
        )
    )
    root = index_tts_root(args.index_tts_root)
    if not root.is_dir():
        # 冷重启的 Popen cwd：缺目录会在服务掉线时（恰是本脚本靶场景）裸
        # traceback——配置错误在入口就大声退出，不等到半夜长跑掉线才炸。
        sys.exit(
            f"index-tts checkout 不存在: {root}——设 --index-tts-root 或 env"
            " VIBE_VIDEO_INDEX_TTS_ROOT 指向实际 checkout（冷重启的运行目录）"
        )
    log_path = (
        Path(args.server_log)
        if args.server_log
        else Path(f".temp/tts-resume/server-{port}.log")
    )
    restart = dict(
        port=port,
        server_argv=server_argv,
        cwd=root,
        log_path=log_path,
        extra_env=extra_env,
        server=args.server,
        health_path=args.health_path,
        startup_timeout=args.startup_timeout,
    )

    failures = 0
    while True:
        if not server_healthy(args.server, args.health_path, args.health_timeout):
            print(f"[tts_resume] 服务不健康 → 按端口 {port} 冷重启（日志 {log_path}）")
            if not cold_restart(**restart):
                print(
                    f"❌ 服务冷启动超时（{args.startup_timeout:.0f}s 内 /health 未就绪）",
                    file=sys.stderr,
                )
                return 3
            print("[tts_resume] 服务已恢复")
        rc = run_tts(forwarded)
        if rc == 0:
            print("[tts_resume] 客户端退出码 0 —— 长跑完成")
            return 0
        failures += 1
        if failures >= args.max_restarts:
            print(
                f"❌ 客户端连续 {failures} 轮失败（上限 {args.max_restarts}），放弃；"
                f"末轮退出码 {rc}。先人工分因：负载竞争可调大 --max-restarts 续跑，"
                "热节流/MPS 挂死见 references/VOICE-CLONING.md §七",
                file=sys.stderr,
            )
            return rc
        print(
            f"[tts_resume] 客户端退出码 {rc}（第 {failures}/{args.max_restarts} 轮失败）"
            "→ 冷重启服务后续跑（幂等缓存从断点续）"
        )
        if not cold_restart(**restart):
            print(
                f"❌ 服务冷启动超时（{args.startup_timeout:.0f}s 内 /health 未就绪）",
                file=sys.stderr,
            )
            return 3


if __name__ == "__main__":
    sys.exit(main())
