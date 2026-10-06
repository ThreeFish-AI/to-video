"""RSI-022 回归：TTS 长跑自愈编排（tts_resume.py）+ doctor 客户端依赖预检。

覆盖两半：① scripts/tts_resume.py——退出码解析（subprocess 真码 vs 管道尾食
负例）、重启计数状态机（mock subprocess / urlopen，不真起服务）、健康检查
分支、启动命令与 tts.server_launch_hint 的防漂移锚、MPS env 配对纪律；
② scripts/pipeline.py doctor 的 mutagen 预检（⚠️ 可操作提示、不计失败——
同「服务离线不计失败」先例）。全部无网络、无 TTS 服务、秒级。
"""

from __future__ import annotations

import importlib.util
import http.client
import re
import signal
import socket
import subprocess
import urllib.error
from pathlib import Path

import pytest

import pipeline  # noqa: E402
import tts  # noqa: E402
import tts_resume  # noqa: E402

from helpers import offline_doctor_project


# ---------------- 退出码解析（表因③：`cmd | tail; $?` 管道尾食） ----------------


def test_run_tts_returns_real_exit_code(tmp_path, monkeypatch):
    """run_tts 用 subprocess.run(...).returncode 直取真码。

    负例文档化（上游 .sh 踩过的形态）：shell 里 `(exit 7) | cat; echo $?` 取到的
    是管道末端 cat 的退出码 0——失败检测恒失效；正控见本函数前半段。
    """
    probe = tmp_path / "fake_tts.py"
    probe.write_text("import sys; sys.exit(7)\n", encoding="utf-8")
    monkeypatch.setattr(tts_resume.tts, "__file__", str(probe))
    assert tts_resume.run_tts([]) == 7
    piped = subprocess.run(
        ["/bin/sh", "-c", "(exit 7) | cat; echo $?"], capture_output=True, text=True
    )
    assert piped.stdout.strip() == "0", "管道尾食负例漂移：$? 应为 cat 的 0"


# ---------------- 重启计数状态机（mock，不真起服务） ----------------


class _Calls(dict):
    """计数 dict：既有断言用整 dict 相等（calls == {"healthy": …, "restart": …,
    "tts": …}）钉调用序列形状——额外捕获（cold_restart 的 kwargs）以属性附着
    而非键存放，不破坏旧断言。"""

    restart_kw: list[dict]


def _mock_loop(monkeypatch, healthy_seq, rc_seq, restart_ok=True):
    """钉住 main 循环的三个副作用点，返回调用计数。"""
    calls = _Calls({"healthy": 0, "restart": 0, "tts": 0})
    calls.restart_kw = []
    healthy_iter, rc_iter = iter(healthy_seq), iter(rc_seq)

    def fake_healthy(*_a, **_k):
        calls["healthy"] += 1
        return next(healthy_iter, True)

    def fake_restart(**kw):
        calls["restart"] += 1
        calls.restart_kw.append(kw)
        return restart_ok

    def fake_tts(_fwd):
        calls["tts"] += 1
        return next(rc_iter)

    monkeypatch.setattr(tts_resume, "server_healthy", fake_healthy)
    monkeypatch.setattr(tts_resume, "cold_restart", fake_restart)
    monkeypatch.setattr(tts_resume, "run_tts", fake_tts)
    monkeypatch.setattr(tts_resume, "require_client_deps", lambda: None)
    return calls


FWD = ["--engine", "indextts", "--final-voice", "--project", "ep-x"]


@pytest.fixture()
def fake_root(tmp_path):
    """封闭化的 index-tts checkout 目录——main() 入口校验根存在（评审加固），
    不显式指认会让 mock 测试依赖本机 ~/tools/index-tts 真伪。"""
    root = tmp_path / "index-tts"
    root.mkdir()
    return root


def test_main_succeeds_after_transient_failures(monkeypatch, fake_root):
    """两轮瞬时失败（服务态挂死）→ 冷重启两次 → 第三轮成功：退出 0。"""
    calls = _mock_loop(monkeypatch, healthy_seq=[True], rc_seq=[1, 1, 0])
    rc = tts_resume.main(["--index-tts-root", str(fake_root), "--", *FWD])
    assert rc == 0
    assert calls == {"healthy": 3, "restart": 2, "tts": 3}


def test_main_gives_up_after_max_restarts(monkeypatch, fake_root):
    """连续失败达 --max-restarts：返回末轮客户端退出码，不再重启。"""
    calls = _mock_loop(monkeypatch, healthy_seq=[True], rc_seq=[5, 5, 5])
    rc = tts_resume.main(
        ["--max-restarts", "3", "--index-tts-root", str(fake_root), "--", *FWD]
    )
    assert rc == 5
    assert calls["restart"] == 2  # 第 3 轮失败即放弃，未做第 3 次重启


def test_main_restarts_unhealthy_server_before_first_run(monkeypatch, fake_root):
    """服务不健康：先冷重启再跑客户端（不健康的服务不进合成）。"""
    calls = _mock_loop(monkeypatch, healthy_seq=[False], rc_seq=[0])
    assert tts_resume.main(["--index-tts-root", str(fake_root), "--", *FWD]) == 0
    assert calls == {"healthy": 1, "restart": 1, "tts": 1}


def test_main_exit_3_when_server_wont_start(monkeypatch, fake_root):
    """冷启动超时：退出码 3（区别于客户端失败码）。"""
    _mock_loop(monkeypatch, healthy_seq=[False], rc_seq=[0], restart_ok=False)
    assert tts_resume.main(["--index-tts-root", str(fake_root), "--", *FWD]) == 3


def test_main_exits_when_index_tts_root_missing(monkeypatch, tmp_path):
    """评审加固：checkout 缺失在入口大声退出（可操作提示）——配置错误不等到
    服务掉线（本脚本靶场景）才以 Popen 裸 traceback 炸出。"""
    calls = _mock_loop(monkeypatch, healthy_seq=[True], rc_seq=[0])
    with pytest.raises(SystemExit) as e:
        tts_resume.main(["--index-tts-root", str(tmp_path / "nope"), "--", *FWD])
    assert "index-tts" in str(e.value) and "TO_VIDEO_INDEX_TTS_ROOT" in str(e.value)
    assert calls["tts"] == 0  # 未进合成即拦


def test_main_requires_forwarded_args():
    """缺 `--` 之后的转发参数：argparse error（exit 2），不进循环。"""
    with pytest.raises(SystemExit) as e:
        tts_resume.main(["--server", "http://127.0.0.1:8766"])
    assert e.value.code == 2


def test_split_forwarded():
    own, fwd = tts_resume.split_forwarded(
        ["--max-restarts", "5", "--", "--engine", "indextts"]
    )
    assert own == ["--max-restarts", "5"]
    assert fwd == ["--engine", "indextts"]
    assert tts_resume.split_forwarded(["--max-restarts", "5"]) == (
        ["--max-restarts", "5"],
        [],
    )


# ---------------- 健康检查分支（mock urlopen） ----------------


class _FakeResp:
    def __init__(self, payload: bytes, status: int = 200):
        self._payload, self.status = payload, status

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.mark.parametrize(
    ("resp", "expected"),
    [
        (_FakeResp(b'{"ok": true, "version": "2.5"}'), True),
        (_FakeResp(b'{"ok": false}'), False),
        (_FakeResp(b'{"ok": true}', status=500), False),
        (_FakeResp(b"not-json"), False),  # 坏 JSON（ValueError 族）按不健康
    ],
)
def test_server_healthy_payload_branches(monkeypatch, resp, expected):
    monkeypatch.setattr(tts_resume.urllib.request, "urlopen", lambda *a, **k: resp)
    assert tts_resume.server_healthy("http://127.0.0.1:8766") is expected


@pytest.mark.parametrize(
    "exc",
    [
        urllib.error.URLError("Connection refused"),
        socket.timeout("timed out"),
        OSError("reset"),
        # HTTPException 族（评审加固）：端口被非 HTTP 进程占用（BadStatusLine）
        # 或半截响应（IncompleteRead）——MRO 不经 URLError/OSError/ValueError，
        # 实测曾直接穿透 main() 裸 traceback（自愈编排器在自身职责域的病态
        # 服务形态上丧失自愈）。
        http.client.BadStatusLine("REDIS-GARBAGE-NOT-HTTP"),
        http.client.IncompleteRead(b"partial"),
    ],
)
def test_server_healthy_transport_failures_are_unhealthy(monkeypatch, exc):
    """连接拒绝/探测超时/传输错误/非 HTTP 回包一律按不健康（含假绿之外的掉线形态）。"""

    def boom(*_a, **_k):
        raise exc

    monkeypatch.setattr(tts_resume.urllib.request, "urlopen", boom)
    assert tts_resume.server_healthy("http://127.0.0.1:8766") is False


def test_wait_healthy_polls_until_deadline(monkeypatch):
    """冷启动等待：前两次探测失败、第三次成功 → True；全失败 → False。"""
    probe = iter([False, False, True])

    def fake_healthy(*_a, **_k):
        return next(probe)

    monkeypatch.setattr(tts_resume, "server_healthy", fake_healthy)
    monkeypatch.setattr(tts_resume.time, "sleep", lambda _s: None)
    assert tts_resume.wait_healthy("http://s", "/health", timeout_sec=30) is True
    monkeypatch.setattr(tts_resume, "server_healthy", lambda *a, **k: False)
    assert tts_resume.wait_healthy("http://s", "/health", timeout_sec=0.0) is False


# ---------------- 启动命令防漂移（事实源 = tts.server_launch_hint） ----------------


def test_default_server_argv_matches_launch_hint():
    """缺省启动命令与 tts.server_launch_hint 同构：--with 集合、脚本路径、端口。

    hint 是人贴终端的 SSOT（含 cd 与续行符）；本测试钉住派生命令不另立事实源
    （hint 换依赖清单时这里先红）。
    """
    hint = tts.server_launch_hint(8766)
    hint_with = set(re.findall(r"--with (\S+)", hint))
    argv = tts_resume.default_server_argv(8766)
    argv_with = {argv[i + 1] for i, a in enumerate(argv) if a == "--with"}
    assert argv_with == hint_with
    assert argv[:3] == ["uv", "run", "--frozen"]
    assert str(tts.SERVER_SCRIPT) in argv
    assert argv[argv.index("--port") + 1] == "8766"


def test_default_server_argv_flags_pinned_to_manual():
    """RSI-035 快照钉死：缺省 argv 的显式 flag 集对齐 VOICE-CLONING §2.3 权威
    命令（hint 同步携带，四处口径一处红）；可选能力 --use-qwen-emo 缺省不带
    （story 块情感走台本向量；无条件开会 +1.5 GB 且 qwen 权重缺机器起不来）。"""
    hint = tts.server_launch_hint(8766)
    argv = tts_resume.default_server_argv(8766)
    assert argv[argv.index("--indextts-version") + 1] == "2.5"
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert "--use-qwen-emo" not in argv
    # hint 对人可见可选能力（尾注释形态），对机器可 grep——两侧不漂移
    assert "--use-qwen-emo" in hint


def test_use_qwen_emo_passthrough_appends_flag(monkeypatch, fake_root):
    """RSI-035 回归：--emo-text 长跑经 --use-qwen-emo 透传后，冷重启 argv 带上
    同名 flag（此前冷重启静默降级服务能力 → 客户端健康门硬失败循环到放弃）。"""
    argv = tts_resume.default_server_argv(8766, use_qwen_emo=True)
    assert argv.count("--use-qwen-emo") == 1  # store_true 形 flag，无值跟随
    # main() 透传链路：服务不健康触发一次冷重启，捕获编排器实际拉起的 argv
    captured: dict[str, list[str]] = {}

    def fake_restart(**kw):
        captured["argv"] = list(kw["server_argv"])
        return True

    _mock_loop(monkeypatch, [False], [0])
    monkeypatch.setattr(tts_resume, "cold_restart", fake_restart)
    rc = tts_resume.main(
        [
            "--use-qwen-emo",
            "--index-tts-root",
            str(fake_root),
            "--",
            *FWD,
        ]
    )
    assert rc == 0
    assert "--use-qwen-emo" in captured["argv"]


def test_use_qwen_emo_rejected_with_custom_server_cmd(monkeypatch, fake_root):
    """透传 flag 只作用于缺省启动命令；--server-cmd 下静默忽略 = 判据面≠作用面。"""
    _mock_loop(monkeypatch, [True], [0])
    with pytest.raises(SystemExit) as e:
        tts_resume.main(
            [
                "--use-qwen-emo",
                "--server-cmd",
                "uv run x",
                "--index-tts-root",
                str(fake_root),
                "--",
                *FWD,
            ]
        )
    assert "--server-cmd" in str(e.value)


def test_server_launch_hint_flags_anchored_to_manual():
    """RSI-035 核验建议①：hint ↔ VOICE-CLONING §2.3 的 flag 口径此前只靠台账
    纪律「三处同批走」，仿 test_tts_mps_oom_contract 读手册先例升机器锚——
    §2.3 权威命令的显式 flag 必须同时在 hint 与缺省 argv（可选 --use-qwen-emo
    在手册与 hint 以可选/注释形态在场、缺省 argv 不带）。"""
    manual = (
        Path(__file__).resolve().parents[1] / "references" / "VOICE-CLONING.md"
    ).read_text(encoding="utf-8")
    sec = manual.split("### 2.3", 1)[1].split("### 2.4", 1)[0]
    hint = tts.server_launch_hint(8766)
    argv = tts_resume.default_server_argv(8766)
    for token in ("--indextts-version 2.5", "--host 127.0.0.1", "--use-qwen-emo"):
        assert token in sec, (
            f"手册 §2.3 不再含 {token}——口径漂移，请同批更新 hint/argv/测试"
        )
        assert token in hint
    assert "--use-qwen-emo" not in argv  # 可选能力缺省不带（透传参数才追加）


def test_index_tts_root_honors_env_and_flag(monkeypatch):
    monkeypatch.setenv("TO_VIDEO_INDEX_TTS_ROOT", "/opt/idx")
    assert tts_resume.index_tts_root(None) == Path("/opt/idx")
    assert tts_resume.index_tts_root("/else/where") == Path("/else/where")
    monkeypatch.delenv("TO_VIDEO_INDEX_TTS_ROOT")
    assert tts_resume.index_tts_root(None) == Path.home() / "tools/index-tts"


def test_port_from_server():
    assert tts_resume.port_from_server("http://127.0.0.1:8766") == 8766
    assert tts_resume.port_from_server("http://localhost") == 80
    assert tts_resume.port_from_server("https://example.com") == 443


# ---------------- MPS env 配对纪律（RSI-017 回灌） ----------------


def test_mps_env_pairing_rules():
    assert tts_resume.mps_env(None, None) == {}
    # high=0.0（禁用水位线）是唯一免配对的特例——上游 .sh 五集实证形态
    assert tts_resume.mps_env("0.0", None) == {
        "PYTORCH_MPS_HIGH_WATERMARK_RATIO": "0.0"
    }
    assert tts_resume.mps_env("0.9", "0.7") == {
        "PYTORCH_MPS_HIGH_WATERMARK_RATIO": "0.9",
        "PYTORCH_MPS_LOW_WATERMARK_RATIO": "0.7",
    }
    with pytest.raises(SystemExit):
        tts_resume.mps_env("0.9", None)  # 单设正 high：默认 low=1.4 首分配即崩
    with pytest.raises(SystemExit):
        tts_resume.mps_env(None, "0.7")  # 单设 low 无语义
    with pytest.raises(SystemExit):
        tts_resume.mps_env("zero", "0.7")  # 非数值
    # 评审加固：nan/-inf 比较恒 False 会溜过 `> 0` 配对分支、负数同例——注入后
    # torch 首个 MPS 分配崩出的错误不含任何可定位信息，防呆在入口拦。
    with pytest.raises(SystemExit):
        tts_resume.mps_env("nan", None)
    with pytest.raises(SystemExit):
        tts_resume.mps_env("-inf", "0.7")
    with pytest.raises(SystemExit):
        tts_resume.mps_env("-1", "0.7")


# ---------------- MPS 旋钮归位（RSI-036：flag 透传 vs env 兜底） ----------------


def test_mps_mem_limit_gib_passthrough_appended():
    """>0 设限与 0（禁用 high watermark）都原样落进缺省 argv；缺省不追加。"""
    argv = tts_resume.default_server_argv(8766, mps_mem_limit_gib=0.0)
    assert argv[argv.index("--mps-mem-limit-gib") + 1] == "0"
    argv16 = tts_resume.default_server_argv(8766, mps_mem_limit_gib=16.5)
    assert argv16[argv16.index("--mps-mem-limit-gib") + 1] == "16.5"
    assert "--mps-mem-limit-gib" not in tts_resume.default_server_argv(8766)


def test_mps_mem_limit_rejects_bad_values_before_killing_server(monkeypatch, fake_root):
    """入口防呆先于杀服：坏值若透传到服务端，冷重启会先杀掉健康服务、新进程才
    被服务端 argparse 拦下（起不来）——自愈器必须在本入口拦（nan/inf/负数同拦，
    nan/-inf 比较恒 False 是 mps_env 已登记的老陷阱形态）。"""
    calls = _mock_loop(monkeypatch, [True], [0])
    for bad in ("-1", "nan", "inf"):
        with pytest.raises(SystemExit) as e:
            tts_resume.main(
                [
                    "--mps-mem-limit-gib",
                    bad,
                    "--index-tts-root",
                    str(fake_root),
                    "--",
                    *FWD,
                ]
            )
        assert "mps-mem-limit-gib" in str(e.value)
    assert calls["restart"] == 0  # 校验先于杀服：全程未动服务


def test_mps_low_ratio_alone_rejected_on_default_argv(monkeypatch, fake_root):
    """RSI-036 回归：单独传 --mps-low-ratio 在缺省路径同样走「env 兜底仅
    --server-cmd」的指路报错——此前误落 mps_env 的「须成对使用」，照做配对后
    又被同一入口驳回（两步矛盾链，把用户引上必然被拒的路）。"""
    calls = _mock_loop(monkeypatch, [True], [0])
    with pytest.raises(SystemExit) as e:
        tts_resume.main(
            ["--mps-low-ratio", "0.7", "--index-tts-root", str(fake_root), "--", *FWD]
        )
    assert "--mps-mem-limit-gib" in str(e.value)  # 可操作指路
    assert "--server-cmd" in str(e.value)
    assert calls["restart"] == 0  # 入口拦截，未动服务


def test_mps_mem_limit_rejected_with_server_cmd_or_env_knobs(monkeypatch, fake_root):
    """flag 只追加进缺省命令（--server-cmd 请自带）；与 env 旋钮互斥——flag 在场
    时 env 被服务端 setter 覆盖，两层各说各话。"""
    _mock_loop(monkeypatch, [True], [0])
    with pytest.raises(SystemExit) as e1:
        tts_resume.main(
            [
                "--mps-mem-limit-gib",
                "0",
                "--server-cmd",
                "uv run x",
                "--index-tts-root",
                str(fake_root),
                "--",
                *FWD,
            ]
        )
    assert "--server-cmd" in str(e1.value)
    with pytest.raises(SystemExit) as e2:
        tts_resume.main(
            [
                "--mps-mem-limit-gib",
                "0",
                "--mps-high-ratio",
                "0.0",
                "--index-tts-root",
                str(fake_root),
                "--",
                *FWD,
            ]
        )
    assert "互斥" in str(e2.value)


def test_mps_high_ratio_rejected_on_default_argv(monkeypatch, fake_root):
    """RSI-036 回归钉：缺省命令路径 env 兜底被服务端缺省 setter 覆盖（实测
    HIGH=0.0 注入后 /health 仍 15.98）——入口大声拒绝并指路 flag 透传，不再
    静默无效（静默放过 = 埋同一个坑给下一次长跑）。"""
    _mock_loop(monkeypatch, [True], [0])
    with pytest.raises(SystemExit) as e:
        tts_resume.main(
            [
                "--mps-high-ratio",
                "0.0",
                "--index-tts-root",
                str(fake_root),
                "--",
                *FWD,
            ]
        )
    assert "--mps-mem-limit-gib" in str(e.value)  # 可操作指路，不止报错


def test_mps_high_ratio_env_still_works_with_server_cmd(monkeypatch, fake_root):
    """env 兜底是降级圈定不是删除：--server-cmd 自定义命令（无 flag 追加通道）
    仍走 env 注入，配对纪律由 mps_env 纯函数侧执法。服务不健康触发一次冷重启，
    断言编排器拉起进程时 env 真被带上（extra_env→start_server 接线在此前
    零覆盖——只断言放行不证明注入）。"""
    calls = _mock_loop(monkeypatch, [False], [0])
    rc = tts_resume.main(
        [
            "--mps-high-ratio",
            "0.0",
            "--server-cmd",
            "uv run x",
            "--index-tts-root",
            str(fake_root),
            "--",
            *FWD,
        ]
    )
    assert rc == 0
    assert calls["tts"] == 1  # env 路径放行、未被入口拦截
    assert calls["restart"] == 1  # 不健康触发一次冷重启
    assert calls.restart_kw[0]["extra_env"] == {
        "PYTORCH_MPS_HIGH_WATERMARK_RATIO": "0.0"
    }


# ---------------- 入口门禁：引擎面 + 客户端依赖面 ----------------


def test_require_indextts_rejects_non_indextts():
    tts_resume.require_indextts(["--engine", "indextts"])
    tts_resume.require_indextts(["--engine=indextts", "--project", "x"])
    for bad in ([], ["--project", "x"], ["--engine", "edge"]):
        with pytest.raises(SystemExit):
            tts_resume.require_indextts(bad)  # 缺省/edge：无服务端可自愈


def test_require_final_voice_gates_forwarded_args():
    """RSI-040 入口预检：--plan 豁免、含 flag 放行、缺 flag 拒（与 tts.py 主闸同口径）。"""
    tts_resume.require_final_voice(["--engine", "indextts", "--plan"])
    tts_resume.require_final_voice(
        ["--engine", "indextts", "--final-voice", "--project", "x"]
    )
    with pytest.raises(SystemExit) as e:
        tts_resume.require_final_voice(["--engine", "indextts", "--project", "x"])
    assert "--final-voice" in str(e.value)  # 可操作提示而非裸拒


def test_main_missing_final_voice_exits_before_any_restart(monkeypatch):
    """缺授权在入口拦：先于健康检查与任何冷重启（同「值校验先于杀服」纪律）——
    不杀可能健康的服务、不空等模型加载。"""
    calls = _mock_loop(monkeypatch, healthy_seq=[True], rc_seq=[0])
    with pytest.raises(SystemExit) as e:
        tts_resume.main(["--", "--engine", "indextts", "--project", "ep-x"])
    assert "--final-voice" in str(e.value)
    assert calls["restart"] == 0 and calls["tts"] == 0


def test_require_client_deps_hints_with_incantation(monkeypatch):
    monkeypatch.setattr(tts_resume.importlib.util, "find_spec", lambda _name: None)
    with pytest.raises(SystemExit) as e:
        tts_resume.require_client_deps()
    assert "--with mutagen" in str(e.value)  # 可操作提示而非裸 traceback


# ---------------- 冷重启纪律：按端口，判据面=作用面 ----------------


def test_start_server_missing_root_or_exec_exits_with_hint(tmp_path):
    """评审加固：Popen 的 FileNotFoundError（cwd 缺失/uv 不在 PATH）转可操作
    退出——服务掉线正是靶场景，配置错误不裸 traceback（对齐 port_listeners
    对 lsof 缺失的先例）。"""
    with pytest.raises(SystemExit) as e:
        tts_resume.start_server(
            ["uv", "run"], tmp_path / "no-such-dir", tmp_path / "s.log", {}
        )
    assert "--index-tts-root" in str(e.value) and "TO_VIDEO_INDEX_TTS_ROOT" in str(
        e.value
    )


def test_stop_server_kills_by_port_not_pkill(monkeypatch):
    """停服只经 lsof 按端口定位 LISTEN 再 kill——argv 面不得出现 pkill -f
    （会连带 8767 上他人的第二实例，references/07「服务生命周期」第 2 步）。"""
    argv_seen: list[list[str]] = []
    kills: list[tuple[int, int]] = []

    class _R:
        stdout = "4321\n"
        returncode = 0

    def fake_run(argv, **_k):
        argv_seen.append(list(argv))
        return _R()

    monkeypatch.setattr(tts_resume.subprocess, "run", fake_run)
    monkeypatch.setattr(
        tts_resume.os, "kill", lambda pid, sig: kills.append((pid, sig))
    )
    monkeypatch.setattr(tts_resume.time, "sleep", lambda _s: None)
    tts_resume.stop_server(8766, grace_sec=0.0)
    assert ["lsof", "-tnP", "-iTCP:8766", "-sTCP:LISTEN"] in argv_seen
    assert not any("pkill" in " ".join(a) for a in argv_seen)
    assert (4321, signal.SIGTERM) in kills and (4321, signal.SIGKILL) in kills


def test_stop_server_no_listeners_is_noop(monkeypatch):
    class _R:
        stdout = ""
        returncode = 0

    monkeypatch.setattr(tts_resume.subprocess, "run", lambda argv, **_k: _R())
    killed: list[int] = []
    monkeypatch.setattr(tts_resume.os, "kill", lambda pid, sig: killed.append(pid))
    tts_resume.stop_server(8766)
    assert killed == []


# ---------------- doctor 客户端依赖预检（pipeline.py） ----------------


def test_doctor_preflights_missing_mutagen_as_warning_not_failure(
    monkeypatch, tmp_path, capsys
):
    """缺 mutagen：⚠️ 可操作提示（含 --with mutagen 与 tts_resume 指针），
    不计失败——doctor 规范调用本就不带 --with，计入会让正常态恒红。"""
    cfg = offline_doctor_project(tmp_path, monkeypatch)
    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: None if name == "mutagen" else real(name),
    )
    rc = pipeline.cmd_doctor(tmp_path, cfg, None)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "客户端依赖 mutagen 缺失" in out and "--with mutagen" in out
    assert "❌" not in out


def test_doctor_silent_when_client_deps_present(monkeypatch, tmp_path, capsys):
    """依赖在场（pytest 解释器带 --with mutagen）：不出现缺失行。"""
    cfg = offline_doctor_project(tmp_path, monkeypatch)
    rc = pipeline.cmd_doctor(tmp_path, cfg, None)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "客户端依赖 mutagen 缺失" not in out
