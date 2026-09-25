"""stages.toml 的执法。

**这个文件是 stages.toml 的存在许可证。** 一份没有消费者的声明是第四个事实源，
严格劣于「散文 + 子命令 + mermaid + 路由表」四处漂移的现状——因为它多了一处
可漂移的地方却没有换来任何约束。砍范围时宁可砍 `pipeline.py stages` 子命令
（那只是便利），也不能砍这里。

覆盖五条：
  1. skill 指针全部真实存在（**skill 根相对**——stages.toml 与阶段规格同住
     skill 仓，双锚点架构下不再有「子项目」这个锚）
  2. commands 每一项都是 pipeline.py 真实注册的子命令
  3. ordinal 恰好是 ①..⑨、无重无缺
  4. 每篇 skill 文档的 H1 与声明（ordinal / name / 文件号）逐字相符
  5. skill 根 SKILL.md（路由壳）的九阶段速查表覆盖全部九个 skill 文档，
     且声明「关键不变量」节（**校验而非生成**：生成物会被手改，那是更隐蔽的
     第二事实源）

另覆盖 pipeline.py 的语言维度（--lang 注册/转发/缺省语义/完成行/qa 推断/
render 旧骨架预检）。
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
import tomllib

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PIPELINE_PY = SCRIPTS / "pipeline.py"

sys.path.insert(0, str(SCRIPTS))

import paths  # noqa: E402 - sys.path 注入后导入

#: skill 根（paths.SKILL 的存在理由就是「不数层数」；此处若改回 parents[N]，
#: SKILL.md 被软链/换安装位时这些断言会静默锚错树）
SKILL_ROOT = paths.SKILL

#: 路由壳 = skill 根的 SKILL.md 本体（旧 .agent/skills/science-video-pipeline/
#: SKILL.md 随抽取退役，路由职责由技能装载单位自己承担）
ROUTER = SKILL_ROOT / paths.SKILL_MARKER
STAGES_TOML = SKILL_ROOT / "references" / "stages.toml"
#: 机制契约文档（路径变量 SSOT + 子命令穷举抄件）
PIPELINE_MD = SKILL_ROOT / "references" / "PIPELINE.md"

ORDINALS = "①②③④⑤⑥⑦⑧⑨"


def stages() -> list[dict]:
    return tomllib.loads(STAGES_TOML.read_text(encoding="utf-8"))["stage"]


def test_skill_pointers_exist():
    """skill 是**skill 根相对**的轻量指针，全部须落到真实文件。"""
    for st in stages():
        target = SKILL_ROOT / st["skill"]
        assert target.is_file(), f"{st['id']}: skill 指针失效 {st['skill']}"


def test_commands_are_registered_subcommands():
    """commands 不得声明 pipeline.py 里不存在的子命令（防声明与实现漂移）。"""
    src = PIPELINE_PY.read_text(encoding="utf-8")
    registered = set(re.findall(r'add_parser\(\s*"([a-z-]+)"', src))
    assert registered, "未能从 pipeline.py 解析出任何子命令——解析器该更新了"
    for st in stages():
        for c in st["commands"]:
            assert c in registered, (
                f"{st['id']}: 声明了子命令 {c!r}，但 pipeline.py 未注册"
                f"（已注册：{sorted(registered)}）"
            )


#: 子命令声明被抄进多处：pipeline.py 文件头与 references/PIPELINE.md 是**穷举抄件**
#: （{a|b|c} 清单），SKILL.md（路由壳——使用者从这里抄命令）刻意不复制穷举清单、
#: 只在与 pipeline.py 同现的命令行里提及子命令。抄件无执法就会漂——`stages` 上线
#: 时各处**全部**漏更，而当时的守卫只查 stages.toml→parser 一个方向（声明多于
#: 实现），看不见反向缺口。（旧第四处「子项目 README」随双锚点抽取退役。）
BRACE_LIST_RE = re.compile(r"\{([a-z|-]{20,})\}")
DOCSTRING_LIST_RE = re.compile(r"^子命令：(.+)$", re.MULTILINE)

#: SKILL.md 的提及形态：`…pipeline.py [--project $P] <cmd> …`——捕获入口脚本名
#: （可带 --project 取值）之后的裸 token；`<cmd>` 占位与 flag（-- 开头）不匹配。
SKILL_MD_CMD_RE = re.compile(r"pipeline\.py(?:\s+--project\s+\S+)?\s+([a-z][a-z-]*)")


def documented_subcommand_lists() -> list[tuple[str, set[str], bool]]:
    """→ [(出处, 该处声明的子命令集合, 是否穷举)]。找不到清单即视为检测器失效并报错。

    穷举源断言 == 注册表（两个方向的漂移都拦）；SKILL.md 是指针式路由壳，
    穷举不是它的职责——对它执法「提及即真实」（⊆）：它教出的每条命令都必须
    argparse 认识，反向缺口（新增子命令未写进路由壳）由穷举源兜底。
    """
    out: list[tuple[str, set[str], bool]] = []
    m = DOCSTRING_LIST_RE.search(PIPELINE_PY.read_text(encoding="utf-8"))
    assert m, "pipeline.py 文件头的「子命令：」行形态变了，检测器该更新了"
    out.append(("pipeline.py 文件头", {s.strip() for s in m.group(1).split("/")}, True))
    hits = BRACE_LIST_RE.findall(PIPELINE_MD.read_text(encoding="utf-8"))
    assert hits, "README.md: 未找到 {a|b|c} 形态的子命令清单（检测器失效？）"
    out += [("references/PIPELINE.md", set(h.split("|")), True) for h in hits]
    mentioned = SKILL_MD_CMD_RE.findall(ROUTER.read_text(encoding="utf-8"))
    assert mentioned, "SKILL.md: 未找到任何 pipeline.py 调用行（检测器失效？）"
    out.append(("SKILL.md", set(mentioned), False))
    return out


def test_documented_subcommand_lists_match_the_parser():
    """散文声明与 argparse 注册表对齐：穷举源逐项相等，路由壳提及即须真实。"""
    registered = set(
        re.findall(
            r'add_parser\(\s*"([a-z-]+)"', PIPELINE_PY.read_text(encoding="utf-8")
        )
    )
    assert registered, "未能从 pipeline.py 解析出任何子命令——解析器该更新了"
    for where, listed, exhaustive in documented_subcommand_lists():
        if exhaustive:
            assert listed == registered, (
                f"{where} 的子命令清单与 argparse 注册表不符："
                f"缺 {sorted(registered - listed)} / 多 {sorted(listed - registered)}"
            )
        else:
            assert listed <= registered, (
                f"{where} 教出了 argparse 未注册的子命令：{sorted(listed - registered)}"
            )


# ---------------- 系列扇出白名单 ----------------


def registered_subcommands() -> set[str]:
    src = PIPELINE_PY.read_text(encoding="utf-8")
    return set(re.findall(r'add_parser\(\s*"([a-z-]+)"', src))


def fanout_ok() -> set[str]:
    """从 pipeline.py 源码取 FANOUT_OK 字面量（import 会执行 paths 哨兵搜索，
    在 tmp_path 布局的测试里语义不明；AST 取值与 registered 同族、同样会被
    「找不到 FANOUT_OK 赋值」式的断言兜底）。"""
    import ast

    tree = ast.parse(PIPELINE_PY.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            t.id == "FANOUT_OK" for t in node.targets if isinstance(t, ast.Name)
        ):
            # 形态为 frozenset({...})/set({...})/{...}，取第一个 set 字面量求值
            inner = node.value
            if isinstance(inner, ast.Call):
                inner = inner.args[0]
            return set(ast.literal_eval(inner))
    raise AssertionError("pipeline.py 里找不到 FANOUT_OK 赋值——检测器该更新了")


def test_fanout_whitelist_is_subset_of_registered_subcommands():
    """白名单不得声明未注册的子命令（否则 --series 白名单项跑起来即 argparse 报错）。"""
    assert fanout_ok() <= registered_subcommands(), (
        f"FANOUT_OK 含未注册子命令：{sorted(fanout_ok() - registered_subcommands())}"
    )


def test_fanout_forwards_subcommand_flags_verbatim():
    """扇出必须**逐字转发**子命令自己的 flag。

    回归：此前子进程只拼 `--project <root> <cmd>`，于是
    `--series X check --check-scenes` 里 argparse 正常解析了 flag、五集却全按
    窄检查跑完，而扇出汇总照样逐集打 ✅——输出与「全集全项通过」不可区分。
    与 ISSUE-168 的 `--scene` 单值 store 同一失效形态，只是搬到了编排器这层。

    `sub_argv` 是纯切片函数（无路径依赖），故此处直接 import pipeline；
    FANOUT_OK 那两条判据仍走 AST，因为它们要读源码字面量。
    """
    from pipeline import sub_argv

    base = ["pipeline.py", "--series", "claude-code-explained"]
    assert sub_argv("check", [*base, "check", "--check-scenes"]) == ["--check-scenes"]
    assert sub_argv("status", [*base, "status"]) == []
    # `--opt=value` 单 token 形态自然跳过，无需登记进 GLOBAL_OPTS_WITH_VALUE
    assert sub_argv("check", ["pipeline.py", "--series=x", "check", "-v"]) == ["-v"]
    # 与 --project 共存（仅默认值 "." 时合法，见 main 的互斥判定）也须切对
    assert sub_argv(
        "check", ["pipeline.py", "--project", ".", "--series", "x", "check", "--a"]
    ) == ["--a"]


def test_fanout_slice_skips_global_option_values():
    """系列 id 恰与子命令同名时不得切错位置。

    `--series check check --check-scenes`：朴素的「从左找第一个等于 cmd 的
    token」会命中 `--series` 的**取值**，于是把真正的子命令当成 flag 转发过去，
    每集都收到一条 `check --check-scenes` 的错位命令行。带取值的顶层选项必须
    连值一起跳（GLOBAL_OPTS_WITH_VALUE 的存在理由）。
    """
    from pipeline import GLOBAL_OPTS_WITH_VALUE, sub_argv

    argv = ["pipeline.py", "--series", "check", "check", "--check-scenes"]
    assert sub_argv("check", argv) == ["--check-scenes"]
    # 顶层带取值的选项全部在册——漏一个就会在「取值恰等于子命令名」时切错
    assert set(GLOBAL_OPTS_WITH_VALUE) == {"--series", "--project"}


def test_check_forwards_motion_flag(monkeypatch, tmp_path):
    import pipeline

    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )

    assert pipeline.cmd_check(tmp_path, {}, motion=True) == 0
    assert "--check-motion" in commands[0]


def test_tts_forwards_no_store_flag(monkeypatch, tmp_path):
    import pipeline

    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )

    assert (
        pipeline.cmd_tts(
            tmp_path,
            {"tts": {"engine": "edge"}},
            plan=False,
            force=False,
            steady=None,
            style=None,
            skip_pre_tts=True,
            no_store=True,
        )
        == 0
    )
    assert "--no-store" in commands[0]


def test_pipeline_cli_registers_forwarded_flags():
    for subcommand, flag in (("check", "--check-motion"), ("tts", "--no-store")):
        result = subprocess.run(
            [sys.executable, str(PIPELINE_PY), subcommand, "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert flag in result.stdout


# ---------------- deliver（⑨ 交付归档） ----------------


def test_deliver_stays_outside_fanout_whitelist():
    """deliver 写 $P 之外的用户目录且累积版本文件：必须显式逐集执行，
    不得被收编进扇出白名单（complement 测试只钉五个既有破坏性命令，
    新增子命令的误收编由此条拦住）。"""
    assert "deliver" in registered_subcommands() - fanout_ok()


def test_final_render_stage_declares_deliver():
    """⑨ 命令声明完整性：test_commands_are_registered_subcommands 只查 ⊆ 注册表，
    反向缺口（⑨ 删漏 deliver）由此条拦住。"""
    by_id = {st["id"]: st for st in stages()}
    assert "deliver" in by_id["final-render"]["commands"]


def test_deliver_forwards_root_and_dry_run_flags(monkeypatch, tmp_path):
    import pipeline

    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    assert pipeline.cmd_deliver(tmp_path, {}, out_root="/tmp/dv", dry_run=True) == 0
    cmd = commands[0]
    # --root 等号单 token 转发：'-' 开头的取值经分离 token 会被子进程 argparse 拒收
    assert "--root=/tmp/dv" in cmd
    assert "--dry-run" in cmd
    assert cmd[cmd.index("--project") + 1] == str(tmp_path)


def test_deliver_cli_registers_forwarded_flags():
    result = subprocess.run(
        [sys.executable, str(PIPELINE_PY), "deliver", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--root" in result.stdout and "--dry-run" in result.stdout


def test_fanout_complement_is_nonempty_and_keeps_destructive_out():
    """反向：**未列入白名单**的子命令必须非空，且 tts/render/qa/all/clean-samples
    恰在其中——这是白名单（而非黑名单）的意义：未来新增子命令默认不可扇出，
    不会静默继承「一条命令跑遍全系列」的破坏半径（4 集 × tts = 8 小时不可逆）。
    """
    outside = registered_subcommands() - fanout_ok()
    assert outside, "FANOUT_OK 收编了全部子命令——扇出默认不再安全"
    for destructive in ("tts", "render", "qa", "all", "clean-samples"):
        assert destructive in outside, (
            f"{destructive} 必须留在扇出白名单之外（昂贵/破坏性命令须显式逐集执行）"
        )


def test_ordinals_are_exactly_one_through_nine():
    got = [st["ordinal"] for st in stages()]
    assert got == list(ORDINALS), f"ordinal 应恰为 ①..⑨ 且按序声明，实际 {got}"


def test_kind_is_known_and_authored_stages_own_no_generation():
    """kind 只有两个取值；tooled 阶段必须至少有一个子命令（否则「工具生成」无从发生）。"""
    for st in stages():
        assert st["kind"] in {"authored", "tooled"}, (
            f"{st['id']}: 未知 kind {st['kind']!r}"
        )
        if st["kind"] == "tooled":
            assert st["commands"], f"{st['id']}: 声明为 tooled 却没有任何子命令"


def test_skill_h1_matches_declaration():
    """H1 形态统一为 `# Stage <序号> <名字>（skill 规格 · <NN>）`。

    这一条把「文件 06 是第 ⑦ 阶段」从读者要自己撞见的陷阱，变成文件第一行就说、
    且改错就红的事实。
    """
    for st in stages():
        p = SKILL_ROOT / st["skill"]
        nn = p.name[:2]
        want = f"# Stage {st['ordinal']} {st['name']}（skill 规格 · {nn}）"
        first = p.read_text(encoding="utf-8").split("\n", 1)[0]
        assert first == want, f"{p.name} H1 不符：\n  实际 {first!r}\n  期望 {want!r}"


def test_declared_misalignment_is_real():
    """守住那个反直觉事实本身：⑥↔07、⑦↔06。

    若将来真去重命名文件，本条会红——那正是提醒：入链 ≥5 处需同步。
    """
    by_ord = {st["ordinal"]: Path(st["skill"]).name for st in stages()}
    assert by_ord["⑥"].startswith("07-"), "⑥ 不再对应 07-*，请同步所有入链"
    assert by_ord["⑦"].startswith("06-"), "⑦ 不再对应 06-*，请同步所有入链"


def _router_text() -> str:
    assert ROUTER.is_file(), f"路由壳不存在：{ROUTER}"
    return ROUTER.read_text(encoding="utf-8")


def _quick_reference_section(text: str) -> str:
    """→ 「九阶段速查」节正文（该标题起，至下一个同级或更高级标题止）。

    找不到该节即报错——它和「关键不变量」节都是 SKILL.md 完整版的契约结构，
    缺席说明占位版尚未被完整版替换，而非本检测器失效。
    """
    m = re.search(r"^(#{1,6})[^\n]*九阶段速查[^\n]*$", text, re.MULTILINE)
    assert m, "SKILL.md 缺「九阶段速查」节——占位版尚未落地为完整版"
    rest = text[m.end() :]
    stop = re.search(rf"^#{{1,{len(m.group(1))}}}\s", rest, re.MULTILINE)
    return rest[: stop.start()] if stop else rest


#: 速查表规格链接列的形态：references/NN-name.md（skill 根相对）
SKILL_LINK_RE = re.compile(r"references/(\d{2}-[a-z-]+\.md)")


def test_router_table_covers_every_skill():
    """路由壳（skill 根 SKILL.md）的九阶段速查表必须链到全部九篇规格，一一对应。

    判据三层：表内含规格链接的行恰 9 行（一阶段一行）；链接文件名无重复；
    链接集合与 stages.toml 声明的 9 篇 skill 文件逐一相等——多链（指向已删文档）、
    漏链（新阶段未入表）、重复（一链两用）三类漂移都会红。
    """
    section = _quick_reference_section(_router_text())
    rows = [ln for ln in section.split("\n") if ln.lstrip().startswith("|")]
    linked_rows = [ln for ln in rows if SKILL_LINK_RE.search(ln)]
    assert len(linked_rows) == 9, (
        f"速查表应 9 行（一阶段一行），实际 {len(linked_rows)} 行含规格链接"
    )
    names = SKILL_LINK_RE.findall(section)
    assert len(names) == len(set(names)), f"速查表规格链接重复：{sorted(names)}"
    want = {Path(st["skill"]).name for st in stages()}
    assert set(names) == want, (
        f"速查表链接与九篇规格不一一对应：缺 {sorted(want - set(names))} / "
        f"多 {sorted(set(names) - want)}"
    )


def test_router_gates_match_stages():
    """速查表「通过门」列与 stages.toml 的 gate 逐字相同（RSI-008：手抄件曾 6/9 行漂移）。

    比末列整格而非「包含」：漂移当初就是从在门后追加注释、截短括注开始的。门列须
    写纯文本（加反引号即不相等）。
    """
    section = _quick_reference_section(_router_text())
    by_file = {Path(st["skill"]).name: st for st in stages()}
    drift, checked = [], 0
    for ln in section.split("\n"):
        m = SKILL_LINK_RE.search(ln)
        if not (m and ln.lstrip().startswith("|")):
            continue
        checked += 1
        cell = ln.strip().strip("|").split("|")[-1].strip()
        st = by_file[m.group(1)]
        if cell != st["gate"]:
            drift.append(
                f"{st['ordinal']}: 速查表 {cell!r} ≠ stages.toml {st['gate']!r}"
            )
    assert checked == len(by_file), (
        f"只核到 {checked} 行（链接列形态变了？本门不得空转）"
    )
    assert not drift, "速查表门列与 stages.toml 漂移：\n  " + "\n  ".join(drift)


#: SKILL.md 的 qa 调用行：取子命令后的实参（止于行尾注释）。
ROUTER_QA_RE = re.compile(r"pipeline\.py\s+--project\s+\S+\s+qa\b([^#`\n]*)")


def test_router_qa_commands_pass_both_parsers(monkeypatch, tmp_path):
    """SKILL.md 的 qa 命令须过 pipeline.py 与 qa_frames.py 两层 argparse 且带 --check
    （RSI-008 评审：裸 `qa` 在 qa_frames 处 parser.error，⑧ 修复循环到不了零 FAIL）。

    用真解析器判定而非文本启发式：「有 --video 却缺选择器」同样会红。
    """
    import pipeline
    import qa_frames

    tails = ROUTER_QA_RE.findall(_router_text())
    assert tails, "SKILL.md 里没找到 qa 命令（检测器失效？）"
    monkeypatch.setattr(pipeline, "load_config", lambda root: ({}, {}))
    for tail in tails:
        forwarded: list[list[str]] = []
        monkeypatch.setattr(
            pipeline, "run", lambda cmd, cwd=None: forwarded.append(cmd) or 0
        )
        argv = ["pipeline.py", "--project", str(tmp_path), "qa", *shlex.split(tail)]
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit) as outer:
            pipeline.main()
        assert outer.value.code == 0, f"pipeline.py 拒收参数：qa{tail}"
        (cmd,) = forwarded
        inner = cmd[next(i for i, a in enumerate(cmd) if a.endswith("qa_frames.py")) :]
        monkeypatch.setattr(sys, "argv", inner)
        with pytest.raises(SystemExit) as ei:
            qa_frames.main()
        # 过了参数校验即去读 manifest（tmp 工程没有）；parser.error 的退出码是 2
        assert "manifest.json 不存在" in str(ei.value.code), (
            f"qa_frames 拒收参数：qa{tail}"
        )
        assert "--check" in inner, f"qa 未带 --check，过不了 ⑧ 门：qa{tail}"


def test_router_declares_key_invariants_section():
    """路由壳须含「关键不变量」节——速查表答「做什么」，不变量答「什么不能破」。"""
    text = _router_text()
    assert re.search(r"^#{1,6}[^\n]*关键不变量", text, re.MULTILINE), (
        "SKILL.md 缺「关键不变量」节——占位版尚未落地为完整版"
    )


def test_router_declares_subproject_ssot_paths():
    """路由壳自称「内容 SSOT 在 references/、工具 SSOT 在 scripts/」，
    这两条路径须真实。

    双锚点抽取会一次性打断它的全部相对链接，而搬迁前**没有任何检查**覆盖它。
    """
    text = _router_text()
    for rel in ("references/", "scripts/"):
        assert rel in text, f"路由壳未声明 SSOT 路径 {rel}"
        assert (SKILL_ROOT / rel).is_dir(), f"SSOT 路径不存在：{rel}"


def test_render_and_all_never_chain_deliver(monkeypatch, tmp_path):
    """「刻意不串联」是有测试钉住的设计决策——完成行 `>> render 完成` 是 references/09
    钉死的判完成信号，串联外部写操作会在失败时产生混合信号（见 cmd_deliver 注释）。"""
    import pipeline

    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    pipeline.cmd_render(tmp_path, {}, final=True)
    # engine=edge：cmd_tts 的 indextts 分支会触 paths.WORKSPACE（pytest CWD 无
    # 哨兵即大声退出），本测试只关心链条里有没有 deliver，不锚工作区。
    pipeline.cmd_all(tmp_path, {"tts": {"engine": "edge"}})
    assert not any("deliver.py" in " ".join(c) for c in commands)


def test_doctor_reports_deliver_root_presence(monkeypatch, tmp_path, capsys):
    """doctor 的 deliver root ℹ️ 行两分支：已配置显示生效值，未配置显示两渠道提示。"""
    import pipeline

    monkeypatch.setenv("TO_VIDEO_DELIVER_ROOT", "/tmp/some-dv")
    pipeline.cmd_doctor(tmp_path, {}, None)
    assert "交付归档根: /tmp/some-dv" in capsys.readouterr().out
    monkeypatch.delenv("TO_VIDEO_DELIVER_ROOT")
    pipeline.cmd_doctor(tmp_path, {}, None)
    assert "交付归档未配置" in capsys.readouterr().out


def test_doctor_offline_tts_server_is_warning_not_failure(
    monkeypatch, tmp_path, capsys
):
    """服务按需启停（references/07「服务生命周期」）：离线是常态，doctor 报 ⚠️ 不置失败。

    其余检查全绿时退出码必须为 0——离线计入失败会让 doctor 在正常关停态恒红，
    反过来诱导 Agent 预启动服务。
    """
    import hashlib
    import json
    import urllib.error

    import pipeline

    (tmp_path / "video" / "src").mkdir(parents=True)
    (tmp_path / "video" / "src" / "timing.json").write_text(
        json.dumps(
            {
                "fps": 30,
                "sentenceGapSec": 0.32,
                "sceneGapSec": 0.9,
                "leadInSec": 0.6,
                "tailSec": 2.0,
                "sceneCrossFadeSec": 0.4,
            }
        ),
        encoding="utf-8",
    )
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"RIFF-fixture")
    (tmp_path / ".to-video-root").touch()  # 工作区哨兵：tts.ref 相对工作区根解析
    monkeypatch.setenv("TO_VIDEO_WORKSPACE", str(tmp_path))

    def offline(*_a, **_k):
        raise urllib.error.URLError("Connection refused")

    monkeypatch.setattr(pipeline.urllib.request, "urlopen", offline)
    cfg = {
        "tts": {
            "engine": "indextts",
            "ref": "ref.wav",
            "ref_sha1": hashlib.sha1(ref.read_bytes()).hexdigest()[:12],
        }
    }
    rc = pipeline.cmd_doctor(tmp_path, cfg, None)
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "⚠️  IndexTTS 服务未在线" in out and "按需拉起" in out, out
    assert "❌" not in out, out


# ---------------- 语言维度（--lang：注册 / 转发 / 缺省语义 / 完成行 / 预检） ----------------

#: 挂 --lang 的九个子命令（doctor/stages/clean-samples 刻意不挂）
LANG_CMDS = (
    "build",
    "check",
    "tts",
    "captions",
    "render",
    "qa",
    "deliver",
    "status",
    "all",
)
TMPL = SKILL_ROOT / "assets" / "video-skeleton"


@pytest.mark.parametrize("subcommand", LANG_CMDS)
def test_cli_registers_lang_flag(subcommand):
    result = subprocess.run(
        [sys.executable, str(PIPELINE_PY), subcommand, "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--lang" in result.stdout


def test_cli_doctor_stages_clean_samples_have_no_lang_flag():
    """doctor 打印全部声明语言（无需选择）、stages/clean-samples 与工程语言无关。"""
    for subcommand in ("doctor", "stages", "clean-samples"):
        result = subprocess.run(
            [sys.executable, str(PIPELINE_PY), subcommand, "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "--lang" not in result.stdout


def test_lang_default_policy_split_by_cost():
    """缺省语义按命令代价分类：build/check/captions/status 全部声明语言；
    tts/render/deliver/all 仅主语言，声明多语言而未指定时报错点名 --lang。"""
    import pipeline

    multi = {"narration": {"langs": ["zh", "en"]}}
    single = {"narration": {"langs": ["zh"]}}
    for cheap in ("build", "check", "captions", "status"):
        assert pipeline.resolve_langs(cheap, None, multi) == ["zh", "en"]
    for expensive in ("tts", "render", "deliver", "all"):
        with pytest.raises(ValueError, match="--lang"):
            pipeline.resolve_langs(expensive, None, multi)
        assert pipeline.resolve_langs(expensive, None, single) == ["zh"]
    # 显式给值恒优先（含昂贵命令的多值/all）
    assert pipeline.resolve_langs("tts", "en", multi) == ["en"]
    assert pipeline.resolve_langs("tts", "zh,en", multi) == ["zh", "en"]
    assert pipeline.resolve_langs("tts", "all", multi) == ["zh", "en"]
    with pytest.raises(ValueError, match="未在本集 narration.langs 声明"):
        pipeline.resolve_langs("tts", "en", single)


def test_expensive_multi_lang_errors_at_cli(tmp_path):
    """端到端：声明多语言的集缺省跑 tts ⇒ argparse 报错退出、stderr 指点 --lang。"""
    ep = tmp_path / "ep"
    ep.mkdir()
    (ep / "pipeline.toml").write_text(
        '[episode]\nslug = "ep"\n[narration]\ntarget_minutes = [1.0, 2.0]\n'
        'langs = ["zh", "en"]\n[tts]\nengine = "edge"\n',
        encoding="utf-8",
    )
    r = subprocess.run(
        [sys.executable, str(PIPELINE_PY), "--project", str(ep), "tts"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode != 0
    assert "--lang" in r.stderr


def test_build_check_default_all_declared_langs(monkeypatch, tmp_path):
    """build/check 缺省逐语言顺序执行（cfg mock 双语 ⇒ 两次调用、flag 逐语言）。"""
    import pipeline

    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    cfg = {"narration": {"langs": ["zh", "en"]}}
    pipeline.cmd_build(tmp_path, cfg)
    seen = [c[c.index("--lang") + 1] for c in commands]
    assert seen == ["zh", "en"]
    pipeline.cmd_check(tmp_path, cfg)
    # check_script 每语言一次 + archify 覆盖门一次（语言无关）
    assert len(commands) == 5
    assert all("build_narration.py" not in " ".join(c) for c in commands[2:])


def test_build_accept_forwards_to_translation_langs_only(monkeypatch, tmp_path):
    """build --accept 只转发给译稿语言；选中语言全是主语言时报错而非静默丢弃。"""
    import pipeline

    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    cfg = {"narration": {"langs": ["zh", "en"]}}
    assert pipeline.cmd_build(tmp_path, cfg, accept="p0-01") == 0
    by_lang = {c[c.index("--lang") + 1]: c for c in commands}
    assert "--accept" not in by_lang["zh"]
    assert by_lang["en"][by_lang["en"].index("--accept") + 1] == "p0-01"
    commands.clear()
    assert pipeline.cmd_build(tmp_path, cfg, ["zh"], accept="all") != 0
    assert commands == []


def test_diagnostics_survive_unregistered_declared_lang(tmp_path, capsys):
    """narration.langs 含未注册语言码：config FAIL 已报，status/doctor（配置有病
    也必须能跑）不得在路径派生处以 traceback 结束——未注册码被滤除。"""
    import pipeline

    assert pipeline.declared_langs({"narration": {"langs": ["zh", "EN"]}}) == ["zh"]
    assert pipeline.declared_langs({"narration": {"langs": "zh"}}) == ["zh"]
    (tmp_path / "script").mkdir()
    cfg = {"narration": {"langs": ["zh", "EN"]}, "tts": {"engine": "edge"}}
    assert pipeline.cmd_status(tmp_path, cfg) == 0
    pipeline.cmd_doctor(tmp_path, cfg)
    assert "声明语言：zh（" in capsys.readouterr().out


def test_tts_lang_en_forwards_narration_lang_not_lang(monkeypatch, tmp_path):
    """tts --lang en：薄包装收 --narration-lang en，且**不再传 --lang**
    （tts.py 自解析，zh digest 不变）。"""
    import pipeline

    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    cfg = {"narration": {"langs": ["zh", "en"]}, "tts": {"engine": "edge"}}
    assert (
        pipeline.cmd_tts(
            tmp_path,
            cfg,
            plan=False,
            force=False,
            steady=None,
            style=None,
            skip_pre_tts=True,
            langs=["en"],
        )
        == 0
    )
    cmd = commands[0]
    assert cmd[cmd.index("--narration-lang") + 1] == "en"
    assert "--lang" not in cmd


def test_tts_en_engine_view_overrides(monkeypatch, tmp_path):
    """en 的引擎/音色走 for_lang 覆写视图：edge→indextts 换档、voice 透传；
    zh 无覆写时不传 --voice（命令 token 与现状一致）。"""
    import pipeline

    monkeypatch.setenv("TO_VIDEO_WORKSPACE", str(tmp_path))
    (tmp_path / ".to-video-root").touch()  # 工作区哨兵：tts.ref 相对工作区根解析
    (tmp_path / "voices").mkdir()
    (tmp_path / "voices" / "en.wav").write_bytes(b"ref")
    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    cfg = {
        "narration": {"langs": ["zh", "en"]},
        "tts": {
            "engine": "edge",
            "en": {
                "engine": "indextts",
                "ref": "voices/en.wav",
                "ref_sha1": "abc123def456",
                "style": "sunny",
            },
        },
    }
    assert (
        pipeline.cmd_tts(
            tmp_path,
            cfg,
            plan=False,
            force=False,
            steady=None,
            style=None,
            skip_pre_tts=True,
            langs=["en"],
        )
        == 0
    )
    en_cmd = commands[0]
    assert en_cmd[en_cmd.index("--engine") + 1] == "indextts"
    assert en_cmd[en_cmd.index("--ref") + 1] == str(tmp_path / "voices" / "en.wav")
    assert en_cmd[en_cmd.index("--expect-ref-sha1") + 1] == "abc123def456"
    assert en_cmd[en_cmd.index("--style") + 1] == "sunny"
    assert (
        pipeline.cmd_tts(
            tmp_path,
            cfg,
            plan=False,
            force=False,
            steady=None,
            style=None,
            skip_pre_tts=True,
            langs=["zh"],
        )
        == 0
    )
    zh_cmd = commands[1]
    assert zh_cmd[zh_cmd.index("--engine") + 1] == "edge"
    assert "--voice" not in zh_cmd
    assert "--ref" not in zh_cmd

    cfg2 = {"tts": {"engine": "edge", "en": {"voice": "en-US-GuyNeural"}}}
    assert (
        pipeline.cmd_tts(
            tmp_path,
            cfg2,
            plan=False,
            force=False,
            steady=None,
            style=None,
            skip_pre_tts=True,
            langs=["en"],
        )
        == 0
    )
    voice_cmd = commands[2]
    assert voice_cmd[voice_cmd.index("--voice") + 1] == "en-US-GuyNeural"


def test_render_zh_tokens_unchanged_en_gets_props(monkeypatch, tmp_path):
    """zh 渲染命令 token 序列与单语言时代逐字一致（无 --props、draft.mp4）；
    en 追加 --props '{"lang":"en"}' 且输出名 draft.en.mp4。"""
    import pipeline

    _renderable_lang_project(tmp_path)  # en 侧需过旧骨架预检
    (tmp_path / "video" / "node_modules").mkdir(parents=True)  # 跳过 install 分支
    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    pipeline.cmd_render(tmp_path, {"narration": {"langs": ["zh"]}}, final=False)
    zh = commands[0]
    assert "../out/draft.mp4" in zh
    assert "--props" not in zh
    pipeline.cmd_render(
        tmp_path, {"narration": {"langs": ["zh", "en"]}}, final=True, langs=["en"]
    )
    en = commands[1]
    assert "../out/final.en.mp4" in en
    assert en[en.index("--props") + 1] == '{"lang":"en"}'


def _renderable_lang_project(root: Path) -> None:
    """构造能通过旧骨架预检的 en 渲染面：模板五文件 + i18n.tsx + 对齐句 id。"""
    import json
    import shutil

    import pipeline

    for rel in pipeline._SKELETON_I18N_FILES:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(TMPL / rel, dst)
    (root / "video" / "src" / "i18n.tsx").write_text(
        "// i18n stub（预检只查存在）\n", encoding="utf-8"
    )
    items = [{"id": "p0-01", "scene": "P0", "text": "Hello.", "durationSec": 1.0}]
    (root / "script").mkdir(exist_ok=True)
    (root / "script" / "narration.en.json").write_text(
        json.dumps(items), encoding="utf-8"
    )
    (root / "video" / "public" / "audio" / "en").mkdir(parents=True, exist_ok=True)
    (root / "video" / "public" / "audio" / "en" / "manifest.json").write_text(
        json.dumps(items), encoding="utf-8"
    )


def test_render_en_skeleton_preflight_missing_i18n(monkeypatch, tmp_path, capsys):
    """旧骨架预检三态之一：缺 i18n.tsx ⇒ 大声失败、不启动渲染命令。"""
    import pipeline

    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    rc = pipeline.cmd_render(
        tmp_path, {"narration": {"langs": ["zh", "en"]}}, final=False, langs=["en"]
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "i18n.tsx" in out and "静默产出中文版" in out
    assert not commands  # 预检失败 ⇒ 不进渲染


def test_render_en_skeleton_preflight_fingerprint_mismatch(
    monkeypatch, tmp_path, capsys
):
    """旧骨架预检三态之二：骨架文件与模板指纹不符（旧代集）⇒ 失败并点名文件。"""
    import pipeline

    _renderable_lang_project(tmp_path)
    # 改动一个 frozen 文件的内容 ⇒ 指纹失配（模拟停在旧代的集）
    sub = tmp_path / "video" / "src" / "components" / "Subtitle.tsx"
    sub.write_text(
        sub.read_text(encoding="utf-8") + "\n// local drift\n", encoding="utf-8"
    )
    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    rc = pipeline.cmd_render(
        tmp_path, {"narration": {"langs": ["zh", "en"]}}, final=False, langs=["en"]
    )
    assert rc == 1
    out = capsys.readouterr().out
    assert "Subtitle.tsx" in out and "指纹" in out
    assert not commands


def test_render_en_skeleton_preflight_passes(monkeypatch, tmp_path):
    """旧骨架预检三态之三：新代骨架（模板一致 + 句 id 对齐）⇒ 放行进渲染。"""
    import pipeline

    _renderable_lang_project(tmp_path)
    (tmp_path / "video" / "node_modules").mkdir(parents=True)
    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    assert (
        pipeline.cmd_render(
            tmp_path, {"narration": {"langs": ["zh", "en"]}}, final=False, langs=["en"]
        )
        == 0
    )
    assert commands and "--props" in commands[0]


def test_resolve_qa_lang_infer_and_conflict():
    """qa 恒单语言：显式优先；文件名 .<lang>.mp4 推断、无后缀 = 主语言产物；
    推断与显式冲突即报错（含「--lang en + 无后缀的 zh 槽位」——en 时间轴抽 zh
    视频会句边界静默错位）；推断出的语言同样须已声明。"""
    import pipeline

    multi = {"narration": {"langs": ["zh", "en"]}}
    assert pipeline.resolve_qa_lang(None, "out/draft.mp4", multi) == "zh"
    assert pipeline.resolve_qa_lang(None, "out/draft.en.mp4", multi) == "en"
    assert pipeline.resolve_qa_lang(None, None, multi) == "zh"
    assert pipeline.resolve_qa_lang("en", "out/draft.en.mp4", multi) == "en"
    with pytest.raises(ValueError, match="无语言后缀"):
        pipeline.resolve_qa_lang("en", "out/draft.mp4", multi)
    with pytest.raises(ValueError, match="冲突"):
        pipeline.resolve_qa_lang("zh", "out/draft.en.mp4", multi)
    with pytest.raises(ValueError, match="恒单语言"):
        pipeline.resolve_qa_lang("zh,en", None, multi)
    with pytest.raises(ValueError, match="未在本集 narration.langs 声明"):
        pipeline.resolve_qa_lang(
            None, "out/draft.en.mp4", {"narration": {"langs": ["zh"]}}
        )
    # --compare 两路径同等参与推断：此前只看 --video，en 对拍会静默用 zh 时间轴
    ab_en = ["out/final.en.mp4", "out/draft.en.mp4"]
    assert pipeline.resolve_qa_lang(None, None, multi, ab_en) == "en"
    assert pipeline.resolve_qa_lang("en", None, multi, ab_en) == "en"
    with pytest.raises(ValueError, match="冲突"):
        pipeline.resolve_qa_lang("zh", None, multi, ab_en)
    with pytest.raises(ValueError, match="指向不同语言"):
        pipeline.resolve_qa_lang(None, None, multi, ["out/final.mp4", ab_en[1]])


def test_qa_scale_inference_accepts_draft_en(monkeypatch, tmp_path):
    """--check 的 scale 推断按 draft 前缀（兼容 draft.en.mp4），非全名相等。"""
    import pipeline

    commands: list[list[str]] = []
    monkeypatch.setattr(
        pipeline, "run", lambda cmd, cwd=None: commands.append(cmd) or 0
    )
    cfg = {"narration": {"langs": ["zh", "en"]}, "render": {"draft_scale": 0.5}}
    pipeline.cmd_qa(
        tmp_path, cfg, "out/draft.en.mp4", None, None, [], True, None, lang="en"
    )
    cmd = commands[0]
    assert cmd[cmd.index("--scale") + 1] == "0.5"
    assert cmd[cmd.index("--lang") + 1] == "en"


def test_per_lang_completion_lines(monkeypatch, tmp_path, capsys):
    """完成行按语言分打：多语言逐语言打 `>> <cmd> 完成（<lang>，…s）`；
    单语言不打语言完成行（保持 main 总行的现状形态）。"""
    import pipeline

    monkeypatch.setattr(pipeline, "run", lambda cmd, cwd=None: 0)
    cfg = {"narration": {"langs": ["zh", "en"]}}
    assert pipeline.cmd_build(tmp_path, cfg) == 0
    out = capsys.readouterr().out
    assert ">> build 完成（zh，" in out
    assert ">> build 完成（en，" in out
    assert pipeline.cmd_build(tmp_path, {"narration": {"langs": ["zh"]}}) == 0
    assert "完成（zh，" not in capsys.readouterr().out


def test_per_lang_failure_names_language(monkeypatch, tmp_path, capsys):
    """某语言失败：不打该语言完成行、即断不跑后续语言、点名失败语言与退出码。"""
    import pipeline

    calls: list[list[str]] = []

    def flaky(cmd, cwd=None):
        calls.append(cmd)
        return 1 if len(calls) == 2 else 0  # en（第二次）失败

    monkeypatch.setattr(pipeline, "run", flaky)
    rc = pipeline.cmd_build(tmp_path, {"narration": {"langs": ["zh", "en"]}})
    assert rc == 1
    out = capsys.readouterr().out
    assert "❌ build 语言 en 失败" in out
    assert "完成（en" not in out
    assert pipeline._FAILED_LANGS == ["en"]
    assert len(calls) == 2  # 失败即断


def test_main_summary_line_aggregates_languages(monkeypatch, tmp_path, capsys):
    """main 总行 = 汇总：全部语言成功才 `>> <cmd> 完成`；失败语言点名 `未完成`。"""
    import pipeline

    monkeypatch.setattr(pipeline, "load_config", lambda root: ({}, {}))
    monkeypatch.setattr(pipeline, "run", lambda cmd, cwd=None: 0)
    monkeypatch.setattr(
        sys, "argv", ["pipeline.py", "--project", str(tmp_path), "build"]
    )
    with pytest.raises(SystemExit) as ei:
        pipeline.main()
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert ">> build 完成（" in out and "未完成" not in out

    monkeypatch.setattr(pipeline, "run", lambda cmd, cwd=None: 1)
    monkeypatch.setattr(
        sys, "argv", ["pipeline.py", "--project", str(tmp_path), "build"]
    )
    with pytest.raises(SystemExit) as ei2:
        pipeline.main()
    assert ei2.value.code == 1
    out2 = capsys.readouterr().out
    assert ">> build 未完成（失败语言：zh，" in out2


def test_status_reports_per_language_and_lock(monkeypatch, tmp_path, capsys):
    """status 按声明语言分行；en 加译稿基线锁新鲜度行（失配点名）。"""
    import hashlib
    import json

    import pipeline

    (tmp_path / "video" / "src").mkdir(parents=True)
    (tmp_path / "video" / "src" / "timing.json").write_text(
        json.dumps(
            {
                "fps": 30,
                "sentenceGapSec": 0.32,
                "sceneGapSec": 0.9,
                "leadInSec": 0.6,
                "tailSec": 2.0,
                "sceneCrossFadeSec": 0.4,
            }
        ),
        encoding="utf-8",
    )
    zh_items = [{"id": "p0-01", "scene": "P0", "text": "你好。"}]
    (tmp_path / "script").mkdir()
    (tmp_path / "script" / "narration.json").write_text(
        json.dumps(zh_items), encoding="utf-8"
    )
    digest = hashlib.sha1("你好。".encode()).hexdigest()[:12]
    # 锁与主稿一致 ⇒ ✅（锁形态同 build_narration：{句id: {zh, en}}）
    (tmp_path / "script" / "narration.en.lock.json").write_text(
        json.dumps({"p0-01": {"zh": digest, "en": "0" * 12}}), encoding="utf-8"
    )
    assert pipeline.cmd_status(tmp_path, {"narration": {"langs": ["zh", "en"]}}) == 0
    out = capsys.readouterr().out
    assert "阶段新鲜度（en，" in out  # 多语言标题带语言名
    assert "与主稿一致" in out
    assert "narration.en.json" in out and "audio/en/manifest.json" in out
    # 主稿改稿 ⇒ 锁失配 ⇒ ⚠️ 点名
    (tmp_path / "script" / "narration.json").write_text(
        json.dumps([{"id": "p0-01", "scene": "P0", "text": "你好，改稿。"}]),
        encoding="utf-8",
    )
    assert pipeline.cmd_status(tmp_path, {"narration": {"langs": ["zh", "en"]}}) == 0
    assert "主稿已改" in capsys.readouterr().out
