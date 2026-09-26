#!/usr/bin/env python3
"""科普视频管线单入口——各阶段中工具化阶段的薄编排。

此前「跑管线」= 人从 README 复制粘贴命令序列，且每集的引擎/风格/样本参数
散落三份 README（已实际漂移：README 仍教 passionate 而VOICE-CLONING 推荐位
已迁移）。本入口从每集 pipeline.toml 装配默认参数，CLI 显式参数仍可覆盖。

设计约束（刻意不做的事）：
  - 不做阶段状态机/状态文件——幂等与续跑已由内容摘要提供（{id}.sha 逐句
    sidecar；narration.json 是 narration.md[+cues.toml] 的纯函数派生），再存一份阶段状态
    就是第二事实源，必然漂移。`status` 实时派生新鲜度，零存储。
  - 不假装能跑写作阶段（①②④⑤⑥中的人/代理部分）——只跑工具与其质量门。

用法（$T/$P 的定义见 references/PIPELINE.md 路径变量约定——那里是唯一定义处，此处不复制
位置字面量，否则搬迁时又多两处要改）：
  uv run --no-project $T/scripts/pipeline.py --project $P <cmd>
子命令：status / doctor / build / check / tts / captions / deliver / render / qa / all / clean-samples / stages
（本行与 references/PIPELINE.md、各集 README 的三份抄件由 tests/test_stages.py 对齐 argparse
真实注册表——`stages` 上线时三处全漏，抄件无执法必漂。）
系列扇出（--series <id>，与 --project 互斥）：
  uv run --no-project $T/scripts/pipeline.py --series <series-id> <cmd> [<cmd 自己的 flag>…]
按 series.json 把该系列各集逐集执行（仅白名单命令，见 FANOUT_OK）；子命令后的
flag 原样转发给每集（见 sub_argv——不转发就是静默缩小检查面）。
语言维度（--lang，声明源 pipeline.toml 的 narration.langs，默认仅 ["zh"]）：
  pipeline.py --project $P <cmd> --lang zh|en|zh,en|all
缺省语义按命令代价分类——build/check/captions/status 跑全部声明语言；
tts/render/deliver/all 只跑主语言（声明多语言而未指定时报错提示 --lang，昂贵命令
显式化）；qa 恒单语言（未给时按视频文件名 .<lang>.mp4 后缀推断）。多语言顺序执行、
完成行按语言分打（某语言失败不打该语言的完成行，总行点名失败语言）。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))  # noqa: E402 - 复用 timeline 的 load_constants

import config  # noqa: E402 - 必须在 sys.path 注入之后导入
import langs  # noqa: E402 - 语言注册表与选择解析的唯一事实源
import paths  # noqa: E402 - WORKSPACE/PROJECT 惰性解析，stages 子命令不依赖工作区

# cmd_* 的语言列表关键字参数名叫 langs（契约签名），会遮蔽上面的模块名——
# 函数体内需要的模块符号走别名引入。
from langs import PRIMARY as LANG_PRIMARY  # noqa: E402
from langs import suffix as lang_suffix  # noqa: E402

MANUAL = str(paths.SKILL / "references" / "VOICE-CLONING.md")  # skill 根哨兵派生


# ---------------- 语言维度（执行层） ----------------
#
# 「语言」是与阶段序列正交的维度：机制在 langs.py、策略在 pipeline.toml 的
# narration.langs、执行在此处（--lang）。缺省语义按命令的代价分类（昂贵命令
# 显式化，ISSUE-163 同族）：便宜命令缺省跑全部声明语言，昂贵命令缺省只跑主语言。


def declared_langs(cfg: dict) -> list[str]:
    """→ 本集声明的语言清单（narration.langs；缺省走 config.default，不内联副本）。

    只保留已注册的语言码：非法声明已由 config.validate 报 FAIL，但 status/doctor
    容忍配置 FAIL 继续跑，原样返回会让它们在路径派生处以 traceback 结束。"""
    got = cfg.get("narration", {}).get("langs")
    ok = [x for x in got if x in langs.LANGS] if isinstance(got, list) else []
    return ok or list(config.default("narration.langs"))


#: 缺省跑**全部声明语言**的子命令（便宜、只读或派生物）。
_ALL_LANGS_DEFAULT = frozenset({"build", "check", "captions", "status"})
#: 缺省只跑**主语言**的子命令——声明多语言而未显式 --lang 时报错，绝不静默
#: 跑半套或全跑（tts/render 是小时级不可逆命令；deliver 写外部归档）。
_PRIMARY_DEFAULT = frozenset({"tts", "render", "deliver", "all"})


def resolve_langs(cmd: str, arg: str | None, cfg: dict) -> list[str]:
    """→ 本次运行的语言列表。取值解析统一走 langs.parse_selection；arg 为 None
    时的缺省策略按上方两组子命令分类实现（qa 恒单语言，另走 resolve_qa_lang）。"""
    declared = declared_langs(cfg)
    if arg is not None:
        return langs.parse_selection(arg, declared)
    if cmd in _PRIMARY_DEFAULT and len(declared) > 1:
        raise ValueError(
            f"本集声明了多语言 {declared}，{cmd} 属昂贵命令、缺省只跑主语言"
            f" {langs.PRIMARY!r}——请显式 --lang（zh|en|zh,en|all）选择本次产出哪些语言版本"
        )
    return list(declared) if cmd in _ALL_LANGS_DEFAULT else [langs.PRIMARY]


def _video_lang(video: str) -> str:
    """视频文件名 → 语言：`.<lang>.mp4` 后缀 → 该语言，无后缀 → 主语言
    （同 langs.render_out 路径约定）。"""
    name = Path(video).name
    return next(
        (
            one
            for one in langs.LANGS
            if one != langs.PRIMARY and name.endswith(f".{one}.mp4")
        ),
        langs.PRIMARY,
    )


def resolve_qa_lang(
    explicit: str | None,
    video: str | None,
    cfg: dict,
    compare: list[str] | None = None,
) -> str:
    """→ qa 的单语言。显式 --lang 优先；未给时从视频文件名推断（--video 与
    --compare 两路径同等参与；推断出的语言同样须已声明）；无视频再退主语言。
    推断与显式冲突、或多个视频互相冲突即报错——两个信号指向两个语言时静默
    取其一，抽帧会抽错语言的时间轴（--compare 同帧号对拍，跨语言本就无意义）。"""
    by_video = {v: _video_lang(v) for v in (video, *(compare or [])) if v}
    if len(set(by_video.values())) > 1:
        raise ValueError(
            "视频文件名指向不同语言（"
            + "、".join(f"{Path(v).name}→{g}" for v, g in by_video.items())
            + "）——qa 恒单语言，同一次运行的视频须同属一个语言版本"
        )
    video, inferred = next(iter(by_video.items()), (None, None))
    if explicit is not None:
        picked = langs.parse_selection(explicit, declared_langs(cfg))
        if len(picked) != 1:
            raise ValueError(
                f"qa 恒单语言：--lang 只接受一个语言码（得到 {explicit!r}）"
            )
        if inferred is not None and inferred != picked[0]:
            slot = (
                "无语言后缀 = 主语言产物"
                if inferred == langs.PRIMARY
                else f"后缀 .{inferred}.mp4"
            )
            raise ValueError(
                f"--lang {picked[0]!r} 与视频文件名冲突（{Path(video).name}：{slot}）"
            )
        return picked[0]
    if inferred is None:
        return langs.PRIMARY
    return langs.parse_selection(inferred, declared_langs(cfg))[0]


#: 最近一次子命令运行的失败语言台账（per_lang 写、main() 汇总读）。cmd_* 的 int
#: 返回签名被直调测试钉住，语言级失败点名走此旁路；单语言路径恒空。
_FAILED_LANGS: list[str] = []


def per_lang(cmd: str, lang_list: list[str], step) -> int:
    """逐语言顺序执行 step(lang)→rc。多语言时逐语言打完成行——「完成行=该语言
    产物成功」（references/10），某语言失败不打该语言完成行、即断不跑后续语言
    （同 cmd_all 短路先例：坏状态下连跑昂贵命令没有意义）。单语言不打语言完成行，
    保持 main() 总行的现状形态。"""
    _FAILED_LANGS.clear()
    for lang in lang_list:
        t0 = time.time()
        rc = step(lang)
        if rc:
            _FAILED_LANGS.append(lang)
            print(
                f"\n❌ {cmd} 语言 {lang} 失败（{time.time() - t0:.1f}s，退出码 {rc}）"
            )
            return rc
        if len(lang_list) > 1:
            print(f"\n>> {cmd} 完成（{lang}，{time.time() - t0:.1f}s）")
    return 0


def tts_view(cfg: dict, lang: str) -> dict:
    """→ 该语言生效的 tts 节（config.for_lang 覆写视图的投影）。zh 恒等是
    for_lang 的契约保证，此处显式短路——主语言路径不依赖 config 的扩展面。"""
    if lang == langs.PRIMARY:
        return cfg.get("tts", {})
    return config.for_lang(cfg, lang).get("tts", {})


#: 可扇出的子命令。白名单而非黑名单：新增子命令默认不可扇出。
#: tts/render/qa/all/clean-samples 刻意在外——4 集扇出 tts 是一条 8 小时不可逆无人值守
#: 命令，昂贵/破坏性默认必须显式逐集执行（ISSUE-163 教训：破坏性默认值必须硬失败
#: 而非提示，静默降级的输出会覆盖唯一产物槽位时尤甚）。
FANOUT_OK = frozenset({"status", "doctor", "build", "check"})


def load_config(root: Path) -> tuple[dict, dict[str, str]]:
    """→ (填过默认值的配置, {键: 来源})。schema/默认值/校验全在 config.py。

    编排器对缺配置是硬失败：没有配置就真的无法装配 TTS 与渲染参数。
    校验 FAIL 同样硬失败——但 `status`/`doctor` 例外（见 main()）：诊断工具
    因为被诊断对象有病而拒绝运行是荒谬的。
    """
    cfg, origin, fails, warns = config.load(root, required=True)
    for w in warns:
        print(f"  ⚠️  {w}")
    if fails:
        sys.exit("配置校验失败：\n  " + "\n  ".join(f"❌ {f}" for f in fails))
    return cfg, origin


def run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"\n$ {' '.join(cmd)}" + (f"   (cwd={cwd})" if cwd else ""))
    return subprocess.run(cmd, cwd=cwd, check=False).returncode


def uv_no_project(
    script: str, with_pkgs: list[str], *extra: str, project: Path
) -> list[str]:
    cmd = ["uv", "run", "--no-project"]
    for p in with_pkgs:
        cmd += ["--with", p]
    cmd += [str(SCRIPTS / script), "--project", str(project), *extra]
    return cmd


# ---------------- 子命令 ----------------


def _lock_freshness(root: Path, lang: str) -> str:
    """非主语言的译稿基线锁新鲜度（锁 = 翻译时主稿句 digest 快照，gettext msgid 同构）。
    主稿事后改稿 ⇒ 锁失配可测，译稿不会沦为无信号的第二事实源。"""
    # 惰性：读锁与失鲜判定口径唯一在 build_narration（同 check_script 的引用）
    from build_narration import read_lock, stale_ids

    lp = langs.lock(root, lang)
    zh_json = langs.narration_json(root, langs.PRIMARY)
    if not lp.is_file():
        return f"⚠️ 无基线锁（build --lang {lang} 成功后生成）"
    if not zh_json.is_file():
        return "⚠️ 主稿缺失，无法比对"
    try:
        recorded = read_lock(lp)
        zh_items = json.loads(zh_json.read_text(encoding="utf-8"))
        moved = sorted(set(recorded) ^ {i["id"] for i in zh_items}) or stale_ids(
            recorded, zh_items
        )
    except (json.JSONDecodeError, KeyError, ValueError):
        return f"⚠️ 基线锁损坏（非法 JSON/缺字段）: {lp.name}"
    if not moved:
        return "✅ 与主稿一致"
    head = "、".join(moved[:3]) + (" 等" if len(moved) > 3 else "")
    return (
        f"⚠️ 主稿已改（{head}）——重译后 build --lang {lang} 刷新锁"
        "（译文无需改动时加 --accept <ids>）"
    )


def _status_lang(root: Path, lang: str, multi: bool) -> None:
    """单语言的新鲜度行（多语言时标题带语言名；zh 单语言语义同旧——⑦ 行
    由「audio/manifest」标签改为显示 manifest 实际相对路径，属显示更明确）。"""
    from timeline import load_constants

    sfx = langs.suffix(lang)
    narr_md = root / "script" / f"narration{sfx}.md"
    narr_json = root / "script" / f"narration{sfx}.json"
    board = root / "script" / "storyboard.md"
    manifest = langs.manifest(root, lang)
    audio_dir = langs.audio_dir(root, lang)
    draft = root / "out" / f"draft{sfx}.mp4"
    final = root / "out" / f"final{sfx}.mp4"

    def fresh(target: Path, *deps: Path) -> str:
        if not target.is_file():
            return "待产出"
        tt = target.stat().st_mtime
        stale = [d.name for d in deps if d.is_file() and d.stat().st_mtime > tt]
        return f"⚠️ 输入已更新（{', '.join(stale)}）" if stale else "✅ 新鲜"

    head = f"（{lang}，实时派生，无状态文件）" if multi else "（实时派生，无状态文件）"
    print(f">> {root.name} 阶段新鲜度{head}")
    # 主稿 narration.json 还派生自配音台本 cues.toml（build_narration.apply_cues；缺文件 fresh 自跳过）
    cues = [root / "script" / "narration.cues.toml"] if lang == langs.PRIMARY else []
    print(f"  ③ narration{sfx}.json    {fresh(narr_json, narr_md, *cues)}")
    print(f"  ⑦ {manifest.relative_to(root)}    {fresh(manifest, narr_json)}")
    if manifest.is_file():
        items = json.loads(manifest.read_text(encoding="utf-8"))
        done = sum(1 for i in items if (audio_dir / f"{i['id']}.mp3").is_file())
        c = load_constants(root)
        from timeline import total_duration_in_frames

        mins = total_duration_in_frames(items, c) / c["fps"] / 60
        print(f"     {done}/{len(items)} 句 mp3 · 预计成片 {mins:.1f} 分钟")
    if lang != langs.PRIMARY:
        print(f"     译稿基线锁       {_lock_freshness(root, lang)}")
    print(f"  ⑨ out/draft{sfx}.mp4     {fresh(draft, manifest, board)}")
    print(
        f"  ⑩ out/final{sfx}.mp4     {final.is_file() and fresh(final, draft) or '待产出'}"
    )


def cmd_status(root: Path, _cfg: dict, langs: list[str] | None = None) -> int:
    """派生式阶段新鲜度表（无状态文件：全部由产物 mtime/摘要实时推断）。"""
    lang_list = langs or declared_langs(_cfg)
    for lang in lang_list:
        _status_lang(root, lang, multi=len(lang_list) > 1)
    return 0


def cmd_doctor(root: Path, cfg: dict, origin: dict[str, str] | None = None) -> int:
    """环境自检：配置、时序 SSOT、参考样本、IndexTTS 服务、node_modules。"""
    ok = True
    tts = cfg.get("tts", {})
    print(">> doctor")
    if origin:
        # 默认值集中进 config.py 后，单看 toml 不再自证全貌——这张带来源标记的
        # 表就是发现性补偿（git config --list --show-origin 的同类做法）。
        print("  ℹ️  生效配置（来源标注）：")
        for line in config.format_table(cfg, origin):
            print(line)
    # 声明语言清单 + 每个非主语言的生效 TTS 配置（for_lang 覆写视图）——双语集
    # 的 en 侧参数（独立 ref/style 覆写）此前不可见，配置错了要到合成才炸。
    declared = declared_langs(cfg)
    print(
        f"  ℹ️  声明语言：{'、'.join(declared)}（主语言 {langs.PRIMARY}；"
        "narration.langs 是语言激活的唯一来源）"
    )
    for lang in declared:
        if lang == langs.PRIMARY:
            continue
        view = config.for_lang(cfg, lang).get("tts", {})
        print(
            f"  ℹ️  [{lang}] 生效 TTS：engine={view.get('engine')}"
            f" style={view.get('style')} ref={view.get('ref')}"
            + (f" voice={view.get('voice')}" if view.get("voice") else "")
        )
        if view.get("engine") == "indextts" and view.get("ref"):
            # 对齐下方主语言块的口径：ref 存在即校验 sha1 与文件实况
            ref = paths.WORKSPACE / view["ref"]
            if ref.is_file():
                import hashlib

                sha1 = hashlib.sha1(ref.read_bytes()).hexdigest()[:12]
                match = "✅" if sha1 == view.get("ref_sha1") else "❌ 指纹不符"
                print(f"     {match} [{lang}] 参考样本 {ref.name} sha1={sha1}")
                ok = ok and sha1 == view.get("ref_sha1")
            else:
                print(f"     ⚠️  [{lang}] 参考样本缺失: {ref}")
    from timeline import load_constants

    try:
        c = load_constants(root)
        print(
            f"  ✅ timing.json: fps={c['fps']} 句间={c['sentenceGapSec']}s 幕间={c['sceneGapSec']}s"
        )
    except SystemExit as e:
        print(f"  ❌ {e}")
        ok = False
    if tts.get("engine") == "indextts":
        # doctor 容忍配置 FAIL 继续跑（见 main()），故 ref 可能真的没配。此时须
        # 明说「未配置」——`WORKSPACE / ""` 会解析成工作区根，把它报成「样本缺失」
        # 是在用一个不存在的路径掩盖配置缺失，两种病因不可混为一谈。
        ref_rel = tts.get("ref")
        if not ref_rel:
            print(
                "  ❌ 未配置 tts.ref（engine=indextts 时必填，字段表见 references/PIPELINE.md）"
            )
            ok = False
        elif (ref := paths.WORKSPACE / ref_rel).is_file():
            import hashlib

            sha1 = hashlib.sha1(ref.read_bytes()).hexdigest()[:12]
            match = "✅" if sha1 == tts.get("ref_sha1") else "❌ 指纹不符"
            print(f"  {match} 参考样本 {ref.name} sha1={sha1}")
            ok = ok and sha1 == tts.get("ref_sha1")
        else:
            print(f"  ⚠️  参考样本缺失: {ref}（音频不入库；用 refs.py rebuild 重建）")
        try:
            server = tts.get("server", config.default("tts.server"))
            with urllib.request.urlopen(f"{server}/health", timeout=5) as resp:
                h = json.loads(resp.read())
            print(
                f"  ✅ IndexTTS 服务: v{h.get('version')} {h.get('device')}/{h.get('dtype')}"
            )
        except (urllib.error.URLError, OSError) as e:
            # 服务按需启停、用完即关（references/07「服务生命周期」）：离线是常态而非故障，
            # 不计入失败——计入则 doctor 在正常关停态恒红，反过来诱导预启动。
            print(
                f"  ⚠️  IndexTTS 服务未在线: {e}"
                f"（按需拉起：合成前启动，命令见 {MANUAL} §二）"
            )
    if not (root / "video" / "node_modules").is_dir():
        print("  ⚠️  video/node_modules 未安装（渲染前: cd video && pnpm install）")
    # 交付归档根是工作区级机器属性（不在 pipeline.toml SCHEMA 内），doctor 只报
    # env 渠道存在性——解析序 SSOT 在 deliver.py，此处不复制。
    if env_root := os.environ.get("TO_VIDEO_DELIVER_ROOT", "").strip():
        print(
            f"  ℹ️  交付归档根: {Path(env_root).expanduser()}"
            "（env:TO_VIDEO_DELIVER_ROOT；deliver 子命令消费）"
        )
    else:
        print(
            "  ℹ️  交付归档未配置（deliver 子命令；渠道 --root 一次性 或 env"
            " TO_VIDEO_DELIVER_ROOT 持久）"
        )
    print(
        "  ℹ️  渲染主机约束：macOS + PingFang SC/Songti SC 系统字体（Linux/CI 渲染不在支持范围）"
    )
    return 0 if ok else 1


def cmd_build(
    root: Path,
    _cfg: dict,
    langs: list[str] | None = None,
    accept: str | None = None,
) -> int:
    """③ 逐语言构建。--accept 只转发给译稿语言（主稿没有对齐对象）；选中语言全是
    主语言时报错而非静默丢弃——parse 了却不生效的 flag 等于静默缩小操作面。"""
    lang_list = langs or declared_langs(_cfg)
    if accept is not None and all(x == LANG_PRIMARY for x in lang_list):
        print(f"❌ --accept 只作用于译稿语言，本次选中 {lang_list}（加 --lang en）")
        return 2
    return per_lang(
        "build",
        lang_list,
        lambda lang: run(
            uv_no_project(
                "build_narration.py",
                [],
                "--lang",
                lang,
                *(
                    ["--accept", accept]
                    if accept is not None and lang != LANG_PRIMARY
                    else []
                ),
                project=root,
            )
        ),
    )


def cmd_check(
    root: Path,
    _cfg: dict,
    scenes: bool = False,
    motion: bool = False,
    langs: list[str] | None = None,
) -> int:
    extra = []
    if scenes:
        extra.append("--check-scenes")
    if motion:
        extra.append("--check-motion")

    def per(lang: str) -> int:
        return run(
            uv_no_project("check_script.py", [], *extra, "--lang", lang, project=root)
        )

    rc = per_lang("check", langs or declared_langs(_cfg), per)
    if rc:
        return rc  # 内容门先红先报（同 cmd_all 短路先例）
    # archify 覆盖门紧随其后串联，不加 flag：忘带 flag = 检查面静默缩小（ISSUE-168
    # 失效形态）。无 archify 资产的集由脚本自身干净跳过。语言无关（按 storyboard
    # 句 id 执法），只跑一次。
    return run(uv_no_project("check_archify_coverage.py", [], project=root))


def cmd_tts(
    root: Path,
    cfg: dict,
    plan: bool,
    force: bool,
    steady: str | None,
    style: str | None,
    allow_voice_switch: bool = False,
    skip_pre_tts: bool = False,
    no_store: bool = False,
    langs: list[str] | None = None,
) -> int:
    def per(lang: str) -> int:
        if not skip_pre_tts:
            # TTS 前置门：预算/读法陷阱/标注合法性都是「合成前可判定的文本门」——
            # 长跑 2 小时量级、mp3 单槽位，读法错误事后只能靠听发现（ISSUE-164 教训：
            # 8 句年份空格错误进了三集成片）。与 cmd_check 同一调用形态（uv 子进程，
            # check_script 的 import 面不被本编排器绑死）。
            rc = run(
                uv_no_project(
                    "check_script.py",
                    [],
                    "--pre-tts",
                    "--json",
                    "--lang",
                    lang,
                    project=root,
                )
            )
            if rc:
                print(
                    "\n❌ pre-TTS 前置门未过——预算超窗/读法陷阱/非法标注任一命中都会在此拦截，"
                    "详情见上方 JSON。修复 narration.md 后重跑 build，或确认无误后加 --skip-pre-tts。"
                )
                return rc
        tts = tts_view(cfg, lang)
        engine = tts.get("engine", config.default("tts.engine"))
        cmd = [
            "uv",
            "run",
            "--no-project",
            # 双依赖并注：edge 引擎需要 edge-tts（在线预置音色），indextts 只需 mutagen。
            # 此前只注 mutagen，engine=edge 时薄包装内 ModuleNotFoundError 退出 1——
            # 单入口对引擎的选择必须连同运行期依赖一起切换。
            *(["--with", "edge-tts"] if engine == "edge" else []),
            "--with",
            "mutagen",
            str(root / "scripts" / "tts.py"),  # 工程内薄包装（注入 --project）
            "--engine",
            engine,
            # 语言由 tts.py 按 --narration-lang 自解析（--lang/--voice 缺省走镜像表，
            # zh 的 digest 与 .engine 签名字节不变），编排器不再传 --lang。
            "--narration-lang",
            lang,
        ]
        if engine == "indextts":
            cmd += ["--ref", str(paths.WORKSPACE / tts["ref"])]
            if tts.get("ref_sha1"):
                cmd += ["--expect-ref-sha1", tts["ref_sha1"]]
            # style 无 SCHEMA 默认值（engine=indextts 时必填、已由 config.validate 拦），
            # 故直取而不编造兜底档名——凭空的 "sunny-steady" 会盖住配置缺失。
            # --style CLI 覆写对两语言同传（现状语义）。
            cmd += ["--style", style or tts["style"]]
        elif tts.get("voice"):
            # edge + 该语言覆写了音色（for_lang 视图带 voice 键）才透传
            cmd += ["--voice", tts["voice"]]
        if plan:
            cmd.append("--plan")
        if force:
            cmd.append("--force")
        if steady:
            cmd += ["--steady", steady]
        if allow_voice_switch:
            # 两遍法经单入口的放行阀：.engine 签名护栏会拦「换风格=整集重录」，
            # 草稿遍(A)/定稿遍(B)任一换档都须显式带上（护栏原理见 tts.py §音色签名）
            cmd.append("--allow-voice-switch")
        if no_store:
            cmd.append("--no-store")
        return run(cmd, cwd=root)

    return per_lang("tts", langs or declared_langs(cfg), per)


def cmd_captions(root: Path, _cfg: dict, langs: list[str] | None = None) -> int:
    return per_lang(
        "captions",
        langs or declared_langs(_cfg),
        lambda lang: run(
            uv_no_project("captions.py", [], "--lang", lang, project=root)
        ),
    )


def cmd_deliver(
    root: Path,
    _cfg: dict,
    out_root: str | None,
    dry_run: bool,
    langs: list[str] | None = None,
) -> int:
    """⑩ 交付归档。显式子命令，刻意不串联进 render --final——完成行
    `>> render 完成` 是 references/10 钉死的判完成信号，串联外部写操作会在失败时
    产生「标记已打 + rc 非零」的混合信号（触发契约见该文档 §终渲）。"""
    extra: list[str] = []
    if out_root:
        # 等号单 token：分离 token 下传时取值以 '-' 开头会被子进程 argparse 拒收，
        # 且用户侧唯一可用的 `--root=-x` 写法经重组也会失效——两级行为必须一致。
        extra.append(f"--root={out_root}")
    if dry_run:
        extra.append("--dry-run")
    return per_lang(
        "deliver",
        langs or declared_langs(_cfg),
        lambda lang: run(
            uv_no_project("deliver.py", [], "--lang", lang, *extra, project=root)
        ),
    )


#: 非主语言渲染前须与模板一致的骨架文件（i18n 承载链：props.lang → Root 读取 →
#: context 下发 → 音频目录/字幕/章节条消费）。档位取 skeleton.toml 的受门表。
_SKELETON_I18N_FILES = (
    "video/src/Root.tsx",
    "video/src/components/NarrationAudio.tsx",
    "video/src/components/Subtitle.tsx",
    "video/src/components/ChapterProgress.tsx",
    "video/src/Main.tsx",
)


def check_skeleton_for_lang(root: Path, lang: str) -> int:
    """非主语言渲染前的旧骨架预检（大声失败）。

    旧代骨架渲英文会**静默产出中文版**：旧 Root.tsx 不读 props.lang（输入 props 被
    丢弃、rc=0），整条昂贵渲染白跑。故渲染前校验 (a) i18n.tsx 存在、(b) 五文件
    指纹与模板一致（复用 verify_skeleton.fingerprint + skeleton.toml 档位；regioned
    取 Main 归一化口径）、(c) 该语言 audio manifest 句 id 集 == narration 句 id 集。"""
    import tomllib

    import verify_skeleton  # 惰性：仅非主语言渲染路径需要（不绑死编排器导入面）

    tmpl = paths.SKILL / "assets" / "video-skeleton"
    classes = tomllib.loads((tmpl / "skeleton.toml").read_text(encoding="utf-8"))[
        "classes"
    ]
    cls_of = {rel: cls for cls, rels in classes.items() for rel in rels}
    problems: list[str] = []
    if not (root / "video" / "src" / "i18n.tsx").is_file():
        problems.append("缺 video/src/i18n.tsx（i18n context 的新代 frozen 文件）")
    for rel in _SKELETON_I18N_FILES:
        cls = cls_of.get(rel)
        if cls is None:
            problems.append(f"{rel} 不在 skeleton.toml 受门档位（登记面漂移？）")
            continue
        want = verify_skeleton.fingerprint(tmpl / rel, rel, cls)
        got = verify_skeleton.fingerprint(root / rel, rel, cls)
        if got != want:
            problems.append(f"{rel} 指纹 {got or '缺失'} ≠ 模板 {want}（{cls} 档）")
    man = langs.manifest(root, lang)
    narr = langs.narration_json(root, lang)
    if not man.is_file():
        problems.append(f"缺 {man.relative_to(root)}（先 tts --lang {lang}）")
    elif not narr.is_file():
        problems.append(f"缺 {narr.relative_to(root)}（先 build --lang {lang}）")
    else:
        m_ids = {i["id"] for i in json.loads(man.read_text(encoding="utf-8"))}
        n_ids = {i["id"] for i in json.loads(narr.read_text(encoding="utf-8"))}
        if m_ids != n_ids:
            problems.append(
                f"{man.relative_to(root)} 句 id 集 ≠ {narr.relative_to(root)}"
                f"（缺 {sorted(n_ids - m_ids)} / 多 {sorted(m_ids - n_ids)}）"
            )
    if problems:
        print(
            "❌ 非主语言渲染前的骨架预检未过——旧代骨架渲染英文会静默产出中文版"
            "（props.lang 被旧 Root 丢弃）："
        )
        for p in problems:
            print(f"   · {p}")
        print(
            "   重渲时按 skeleton.toml 分代说明整组同步"
            "（Main + ChapterProgress + Subtitle + Root + NarrationAudio + i18n.tsx，"
            "拷齐再 tsc），同步后本预检自然放行。"
        )
        return 1
    return 0


def cmd_render(
    root: Path, cfg: dict, final: bool, langs: list[str] | None = None
) -> int:
    def per(lang: str) -> int:
        if lang != LANG_PRIMARY and (rc := check_skeleton_for_lang(root, lang)):
            return rc
        video = root / "video"
        if not (video / "node_modules").is_dir():
            print("先安装依赖（嵌套 workspace 自锚隔离）…")
            # 裸 install：pnpm ≥12 加 --ignore-workspace 会把工程自身 pnpm-workspace.yaml
            # 的 allowBuilds 一并忽略 ⇒ ERR_PNPM_IGNORED_BUILDS 非零退出、node_modules
            # 半残；对根 workspace 的隔离由 video/pnpm-workspace.yaml（packages:[] 自锚）
            # 真正兜住——「能装」≠「装全」，见源仓 ISSUE-175 的结论反转。
            rc = run(["pnpm", "install"], cwd=video)
            if rc:
                return rc
        r = cfg.get("render", {})
        sfx = lang_suffix(lang)
        out = f"../out/{'final' if final else 'draft'}{sfx}.mp4"
        cmd = ["./node_modules/.bin/remotion", "render", "Main", out]
        if not final:
            cmd += [
                "--scale",
                str(r.get("draft_scale", config.default("render.draft_scale"))),
                "--jpeg-quality",
                str(
                    r.get(
                        "draft_jpeg_quality",
                        config.default("render.draft_jpeg_quality"),
                    )
                ),
            ]
        if lang != LANG_PRIMARY:
            # 仅非主语言注入语言 props——zh 命令 token 序列与单语言时代逐字一致
            cmd += ["--props", f'{{"lang":"{lang}"}}']
        return run(cmd, cwd=video)

    return per_lang("render", langs or declared_langs(cfg), per)


def cmd_qa(
    root: Path,
    cfg: dict,
    video: str | None,
    scene: list[str] | None,
    last_n: int | None,
    ids: list[str],
    check: bool,
    scale: float | None,
    beat_heads: int | None = None,
    compare: list[str] | None = None,
    lang: str | None = None,
) -> int:
    cmd = ["uv", "run", "--no-project"]
    if check or compare:
        cmd += ["--with", "pillow", "--with", "numpy"]
    cmd += [
        str(SCRIPTS / "qa_frames.py"),
        "--project",
        str(root),
        "--lang",
        lang or LANG_PRIMARY,
    ]
    for s in scene or []:
        cmd += ["--scene", s]
    if last_n:
        cmd += ["--last-n", str(last_n)]
    if beat_heads:
        cmd += ["--beat-heads", str(beat_heads)]
    if compare:
        cmd += ["--compare", *compare]
    if check:
        cmd += ["--check"]
        # 字幕带/亮块间隔是全分辨率像素常数：草渲（0.5x）不折算则带高×2、间隔×2，
        # 侵入判据双向失真。显式 --scale 优先；未给时按产物名推断（draft → pipeline.toml）
        eff = scale
        if eff is None and video and Path(video).name.startswith("draft"):
            eff = cfg.get("render", {}).get(
                "draft_scale", config.default("render.draft_scale")
            )
        if eff is not None:
            cmd += ["--scale", str(eff)]
        else:
            print("  ⚠️  未指定 --scale 且产物非 draft.mp4：按全分辨率（1.0）体检")
    if video:
        cmd.append(video)
    cmd += ids
    return run(cmd, cwd=root)


def cmd_all(root: Path, cfg: dict, langs: list[str] | None = None) -> int:
    """build → check → tts → captions → render --draft → qa 抽帧（含自动体检）。

    语言语义：all 属昂贵命令，缺省只跑主语言（声明多语言须显式 --lang）；
    显式多值时逐语言跑完整链（每语言一条独立产物链，语言完成行由各步分打）。"""
    lang_list = langs or declared_langs(cfg)
    for lang in lang_list:
        t0 = time.time()
        for step in (
            lambda: cmd_build(root, cfg, langs=[lang]),
            lambda: cmd_check(root, cfg, langs=[lang]),
            lambda: cmd_tts(
                root,
                cfg,
                plan=False,
                force=False,
                steady=None,
                style=None,
                langs=[lang],
            ),
            lambda: cmd_captions(root, cfg, [lang]),
            lambda: cmd_render(root, cfg, final=False, langs=[lang]),
        ):
            if rc := step():
                return rc
        if len(lang_list) > 1:
            print(f"\n>> all 完成（{lang}，{time.time() - t0:.1f}s）")
    print("\n>> 草渲完成。尾幕必查（渐黑过早缺陷的回归点）：")
    # 全部路径用绝对值：脚本/工程/视频各自相对不同 CWD，混用相对路径则任一工作目录照抄必有一端落空
    print(
        f"   uv run --no-project --with pillow --with numpy {SCRIPTS / 'qa_frames.py'} \\"
    )
    draft_scale = cfg.get("render", {}).get(
        "draft_scale", config.default("render.draft_scale")
    )
    for lang in lang_list:
        print(
            f"       --project {root} {root / 'out' / f'draft{lang_suffix(lang)}.mp4'}"
            f" --last-n 6 --check --lang {lang}"
            f" --scale {draft_scale}   # 草渲像素折算，不可省"
        )
    return 0


def cmd_clean_samples(_root: Path, _cfg: dict) -> int:
    d = paths.PROJECT / ".temp" / "voice-samples"
    if d.is_dir():
        import shutil

        shutil.rmtree(d)
        print(f"已删除 {d}（小样含本人音色，属生物特征信息）")
    else:
        print(f"无待清理目录: {d}")
    return 0


def cmd_stages() -> int:
    """打印阶段声明表（替代 README 手维护的阶段表；声明源 references/stages.toml）。

    与工程无关，故不读 pipeline.toml。
    """
    decl = tomllib.loads(
        (paths.SKILL / "references" / "stages.toml").read_text(encoding="utf-8")
    )
    print(
        f">> {len(decl['stage'])} 个阶段（声明源 references/stages.toml；authored=撰写产出 / tooled=工具产出）\n"
    )
    for st in decl["stage"]:
        cmds = " ".join(st["commands"]) or "—"
        print(
            f"  {st['ordinal']} {st['name']:<22} [{st['kind']:<8}] 命令 {cmds:<18} {st['skill']}"
        )
        print(f"      门：{st['gate']}")
    return 0


#: 顶层选项中**带取值**的那些。`sub_argv` 切片时必须连取值一起跳过——否则
#: `--series check check`（系列 id 恰与子命令同名）会把取值误认成子命令，
#: 转发面从错误的位置开始切。`--opt=value` 单 token 形态无需登记（自然跳过）。
GLOBAL_OPTS_WITH_VALUE = ("--series", "--project")


def sub_argv(cmd: str, argv: list[str]) -> list[str]:
    """→ 命令行里**子命令之后**的原样 token（扇出须逐字转发给每集）。

    转发而非按 Namespace 重建：子命令的 flag 声明面只有 argparse 一处，重建就要
    再维护一张 dest→flag 抄件，而抄件漏登记的表现恰是**静默缩小检查面**
    （`--check-scenes` 被丢弃就是这么发生的，同 ISSUE-168 一族）。切片对新增
    flag 零维护，声明面仍只有一处。

    纯切片、不判合法性：argparse 已在调用前解析并校验过整条命令行。
    """
    i = 1
    while i < len(argv):
        tok = argv[i]
        if tok in GLOBAL_OPTS_WITH_VALUE:
            i += 2  # 选项 + 取值两个 token 一起跳
            continue
        if tok == cmd:
            return argv[i + 1 :]
        i += 1
    return []


def fanout(series_id: str, cmd: str, extra: list[str]) -> int:
    """把 <cmd>（连同它自己的 flag）逐集执行在该系列全部集上（--series 入口）。

    每集独立进程跑本脚本自身（而非进程内循环调 cmd_*）：保持各子命令的
    「读配置→跑→打完成行」语义与单集调用逐字相同，扇出只是外层循环。

    `extra` = 子命令之后的原样 token（见 sub_argv）。**必须转发**：此前只拼
    `--project <root> <cmd>`，于是 `--series X check --check-scenes` 里 argparse
    正常解析了 flag、五集却全按窄检查跑完，汇总照样逐集打 ✅——输出与「全集全项
    通过」不可区分，与 ISSUE-168 的 `--scene` 单值 store 同一失效形态。
    """
    if cmd not in FANOUT_OK:
        sys.exit(
            f"❌ `--series` 不支持子命令 {cmd!r}：可扇出的只有 {sorted(FANOUT_OK)}。\n"
            f"   tts/render/qa/all/clean-samples 刻意不可扇出——4 集扇出 tts 即一条"
            f" 8 小时不可逆无人值守命令（mp3 单槽位覆盖），昂贵/破坏性操作必须显式逐集执行。"
        )
    series_list = json.loads(
        (paths.WORKSPACE / "series.json").read_text(encoding="utf-8")
    )["seriesList"]
    hit = next((s for s in series_list if s["id"] == series_id), None)
    if hit is None:
        ids = [s["id"] for s in series_list]
        sys.exit(f"series.json 无此系列 id: {series_id}（现有：{ids}）")
    eps = hit["episodes"]
    print(
        f">> 扇出 {cmd!r} · 系列 {series_id} · {len(eps)} 集"
        # 转发面显式打出来：检查面必须随判定行一起可见（ISSUE-168 防范 2）
        + (f" · 转发 {' '.join(extra)}" if extra else "")
    )
    t0 = time.time()
    results: list[tuple[str, int]] = []
    for ep in eps:
        root = paths.WORKSPACE / ep["path"]
        rc = run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--project",
                str(root),
                cmd,
                *extra,
            ]
        )
        results.append((ep["slug"], rc))
    print(f"\n>> 扇出汇总（{time.time() - t0:.1f}s）")
    failed = 0
    for slug, rc in results:
        mark = "✅" if rc == 0 else f"❌ rc={rc}"
        failed += rc != 0
        print(f"   {mark}  {slug}")
    if failed:
        print(f"   {failed}/{len(results)} 集失败")
    return 1 if failed else 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description="科普视频管线单入口（薄编排，阶段契约见 references/PIPELINE.md）"
    )
    ap.add_argument(
        "--project",
        default=".",
        help="视频工程根目录（含 pipeline.toml）；须置于子命令之前",
    )
    ap.add_argument(
        "--workspace",
        help="内容工作区根目录（含哨兵）；缺省时自 --project 向上推断，再退回 CWD 搜索",
    )
    ap.add_argument(
        "--series",
        help="按 series.json 扇出到该系列各集（与 --project 互斥；仅 "
        f"{sorted(FANOUT_OK)} 可扇出）。子命令自身的 flag 逐字转发给每集",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    # --lang 共享 parent：挂到支持语言的九个子命令（doctor/stages/clean-samples
    # 不挂——doctor 打印全部声明语言，无需选择）。缺省语义见 resolve_langs。
    lang_flag = argparse.ArgumentParser(add_help=False)
    lang_flag.add_argument(
        "--lang",
        metavar="zh|en|zh,en|all",
        help="语言版本：逗号分隔 / all=全部声明语言。缺省——build/check/captions/"
        "status 跑全部声明语言；tts/render/deliver/all 仅主语言（声明多语言时须"
        "显式指定）；qa 恒单语言（未给时按视频文件名 .<lang>.mp4 推断）",
    )
    sub.add_parser(
        "status", parents=[lang_flag], help="阶段新鲜度（实时派生，按声明语言分行）"
    )
    sub.add_parser("doctor", help="环境自检")
    p = sub.add_parser("build", parents=[lang_flag], help="③ narration(.en).md → .json")
    p.add_argument(
        "--accept",
        metavar="all|ID[,ID…]",
        help="译稿基线锁：确认这些句的译文在主稿改稿后无需改动（重译过的句自动刷新，"
        "无需点名）；只转发给译稿语言",
    )
    p = sub.add_parser("check", parents=[lang_flag], help="④⑥ 内容门")
    p.add_argument(
        "--check-scenes",
        action="store_true",
        help="附:分镜↔场景代码 beat 互比（WARN）+ at()/dur() 句 id 存在性（FAIL）；"
        "复述口播门缺省执法，不依赖本 flag",
    )
    p.add_argument(
        "--check-motion",
        action="store_true",
        help="附:分镜动效标注↔场景运动模型互比（WARN-only）",
    )
    sub.add_parser(
        "captions", parents=[lang_flag], help="⑦+ 导出 srt/vtt（按语言分槽位）"
    )
    p = sub.add_parser(
        "deliver", parents=[lang_flag], help="⑩ 交付归档：成片按系列/标题 vN 落统一根"
    )
    p.add_argument(
        "--root",
        help="交付归档根路径（一次性/prompt 指定；持久统一配置用 env"
        " TO_VIDEO_DELIVER_ROOT）",
    )
    p.add_argument(
        "--dry-run", action="store_true", help="只打印目的地与下一版本号，不写入"
    )
    sub.add_parser("clean-samples", help="清理 .temp/voice-samples（生物特征）")
    p = sub.add_parser(
        "tts", parents=[lang_flag], help="⑦ 配音合成（参数来自 pipeline.toml）"
    )
    p.add_argument("--plan", action="store_true", help="只看排期不实跑")
    p.add_argument("--force", action="store_true", help="忽略缓存")
    p.add_argument(
        "--no-store",
        action="store_true",
        help="禁用 IndexTTS 音频版本库",
    )
    p.add_argument("--steady", help="混合档选择器")
    p.add_argument("--style", help="覆写风格（两遍法草稿遍用 --style sunny）")
    p.add_argument(
        "--allow-voice-switch",
        action="store_true",
        help="放行音色签名变更（两遍法换档经单入口时须带上，否则被 .engine 护栏硬拦）",
    )
    p.add_argument(
        "--skip-pre-tts",
        action="store_true",
        help="跳过 pre-TTS 前置门（预算/读法陷阱/标注合法性）。直调 $P/scripts/tts.py"
        " 薄包装不走本入口、天然无此门——那不是绕过的设计，是 tts.py 的导入边界"
        "（不可 import check_script，见 paths.py 文件头）使然；要门就走本入口",
    )
    p = sub.add_parser("render", parents=[lang_flag], help="⑨⑩ 渲染")
    p.add_argument("--final", action="store_true", help="终渲（默认草渲）")
    p = sub.add_parser("qa", parents=[lang_flag], help="⑨ 抽帧 QA（恒单语言）")
    p.add_argument(
        "--video",
        help="渲染产物路径，**按分集工程目录解析**（本入口以 cwd=<工程> 启动 "
        "qa_frames.py）——写 out/draft.mp4，勿写 $P/out/draft.mp4",
    )
    # 与 qa_frames 对齐：可重复传多幕（单值 store 会静默只留末幕，见 qa_frames 注释）
    p.add_argument("--scene", action="append", metavar="Pn")
    p.add_argument("--last-n", type=int)
    p.add_argument(
        "--beat-heads",
        type=int,
        metavar="N",
        help="每 beat 头部连抽 N 帧（入场瞬态补盲，ISSUE-170）",
    )
    p.add_argument(
        "--compare",
        nargs=2,
        metavar=("A.mp4", "B.mp4"),
        help="A/B 对拍（重制/重构回归归因；advisory）",
    )
    p.add_argument("--check", action="store_true", help="自动体检")
    p.add_argument(
        "--scale",
        type=float,
        help="产物缩放系数（草渲不传时按 draft.mp4 自动取 pipeline.toml 的 draft_scale）",
    )
    p.add_argument("ids", nargs="*")
    sub.add_parser(
        "all", parents=[lang_flag], help="build→check→tts→captions→render(草渲) 一键链"
    )
    sub.add_parser("stages", help="打印阶段声明表（与工程无关）")
    args = ap.parse_args()

    if args.series is not None and args.project != ".":
        ap.error("--series 与 --project 互斥（系列扇出按 series.json 定位各集工程）")
    if args.series is not None:
        sys.exit(fanout(args.series, args.cmd, sub_argv(args.cmd, sys.argv)))

    root = Path(args.project).resolve()
    # 工作区锚三级优先：--workspace 显式 > 自 --project 向上推断 > CWD 搜索（env 亦然）。
    # 写回 env 而非模块全局：下游惰性 paths.WORKSPACE / 子进程扇出读同一事实源。
    if args.workspace:
        os.environ["TO_VIDEO_WORKSPACE"] = str(Path(args.workspace).resolve())
    elif (ws := paths.find_upward(root, paths.WORKSPACE_MARKERS)) is not None:
        os.environ.setdefault("TO_VIDEO_WORKSPACE", str(ws))
    # 与具体工程无关的子命令不读 pipeline.toml —— 否则「某集 toml 写坏」会连带
    # 让「清理生物特征小样」和「查阶段表」都无法执行，属荒谬耦合。
    if args.cmd == "stages":
        sys.exit(cmd_stages())
    if args.cmd == "clean-samples":
        sys.exit(cmd_clean_samples(root, {}))
    # status/doctor 是诊断工具：配置有病时它们尤其该运行，故只报不退
    if args.cmd in {"status", "doctor"}:
        cfg, origin, fails, warns = config.load(root, required=True)
        for w in warns:
            print(f"  ⚠️  {w}")
        for f in fails:
            print(f"  ❌ 配置：{f}")
    else:
        cfg, origin = load_config(root)
    # 语言选择：取值解析统一走 langs.parse_selection；None 的缺省策略按命令分类
    # （resolve_langs）。qa 恒单语言、且可从视频文件名推断，另走 resolve_qa_lang。
    lang_arg = getattr(args, "lang", None)
    try:
        lang_list = (
            [resolve_qa_lang(lang_arg, args.video, cfg, args.compare)]
            if args.cmd == "qa"
            else resolve_langs(args.cmd, lang_arg, cfg)
        )
    except ValueError as e:
        ap.error(str(e))
    t0 = time.time()
    rc = {
        "status": lambda: cmd_status(root, cfg, lang_list),
        "doctor": lambda: cmd_doctor(root, cfg, origin),
        "build": lambda: cmd_build(root, cfg, lang_list, args.accept),
        "check": lambda: cmd_check(
            root, cfg, args.check_scenes, args.check_motion, lang_list
        ),
        "tts": lambda: cmd_tts(
            root,
            cfg,
            args.plan,
            args.force,
            args.steady,
            args.style,
            args.allow_voice_switch,
            args.skip_pre_tts,
            args.no_store,
            lang_list,
        ),
        "captions": lambda: cmd_captions(root, cfg, lang_list),
        "deliver": lambda: cmd_deliver(root, cfg, args.root, args.dry_run, lang_list),
        "render": lambda: cmd_render(root, cfg, args.final, lang_list),
        "qa": lambda: cmd_qa(
            root,
            cfg,
            args.video,
            args.scene,
            args.last_n,
            args.ids,
            args.check,
            args.scale,
            getattr(args, "beat_heads", None),
            getattr(args, "compare", None),
            lang_list[0],
        ),
        "all": lambda: cmd_all(root, cfg, lang_list),
        "clean-samples": lambda: cmd_clean_samples(root, cfg),
    }[args.cmd]()
    # 总完成行 = 汇总：全部语言成功才打「完成」，否则点名失败语言（完成行=产物
    # 成功，references/10；语言级完成行已由 per_lang 在各语言成功后分打）。
    if _FAILED_LANGS:
        print(
            f"\n>> {args.cmd} 未完成（失败语言：{'、'.join(_FAILED_LANGS)}，"
            f"{time.time() - t0:.1f}s，退出码 {rc}）"
        )
    else:
        print(f"\n>> {args.cmd} 完成（{time.time() - t0:.1f}s，退出码 {rc}）")
    sys.exit(rc)


if __name__ == "__main__":
    main()
