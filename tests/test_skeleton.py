"""骨架模板、漂移门与 scaffold 的执法。

模板的存在意义是「给复制源头一个名字」。但一份新目录若无人校验，它就是**第 5 份
副本**，净负。所以这里必须钉住三件事：
  1. skeleton.toml 声明的路径在模板里真实存在（清单不能指空）
  2. 模板与基线系列一致（模板不过期）
  3. 漂移门有方向、逃逸表生效、且**能真的报警**（正控——一个不会红的门等于没门）

另注：模板里的 `.tsx` 不被任何 tsconfig 覆盖，因此没有 tsc 检查。这不是漏洞，
而是漂移门保证的性质：模板与真集字节相同 ⟹ 真集的 `tsc --noEmit` 传递性地
验证了模板。门被关掉时会同时失去这层保障——该耦合已写入 skeleton.toml。

**但这条传递性有一个缺口**：它只覆盖受门档位。`theme.ts` 是 **seeded** 档、
不受门，而 frozen 组件对 `theme.serif` / `theme.sans` 有硬依赖——真集的 theme.ts
恰好齐全，模板的 seed 却曾缺这两个键，于是 scaffold 出的新集开箱即 6 个 TS2339
而漂移门照样报 0 处。补口在 `test_template_theme_covers_frozen_component_tokens`：
凡 seeded 档被 frozen 档消费，那个接口必须单独立判据。

## 双锚点下的正控沙箱（承重）

正控必须**注入漂移**才能证明门会红，但注入对象绝不能是受版本控制的模板或
真集（旧教训：注入一度落在已发布分集文件上，还原只靠 try/finally）。双锚点
架构（skill 根 / 内容工作区物理分离）下，沙箱由两半拼成：

  - **假 skill 根**（`mirror_skill`）：SKILL.md 哨兵 + 从真 `scripts/`
    原样拷来的脚本 + 模板全量拷贝。`paths.SKILL` 自 `__file__` 向上找
    SKILL.md——裸拷脚本进 tmp 会在**导入期**就大声退出（旧嵌套镜像因此在
    机制抽取后整体失效），假哨兵必须随行。模板升代注入落在副本上，
    真仓文件分毫不动。
  - **平铺工作区**（`flat_ws`）：哨兵 + series.json + episodes/。工作区锚由
    CWD 哨兵搜索提供（subprocess 传 `cwd=工作区根`）。drift/generation 登记
    写进它的 to-video.toml `[skeleton]`（登记面住工作区，RSI-010）。

沙箱里的分集不再从真树复制：由（副本里的真）scaffold 实例化——scaffold 产物
与模板字节相同正是 scaffold 自身的执法对象（见
test_scaffold_produces_gate_clean_episode），恰好也是漂移门正控需要的干净基线。
真树判据（baselineOf 在册、逃逸表指向实存文件）改为 env 门控的集成模式
（TO_VIDEO_TEST_WORKSPACE，见 conftest 文件头）：本仓是 skill 仓，没有 episodes/。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

#: 本仓根 = 真 skill 根（含 SKILL.md）。scaffold 行为用例经绝对路径调真脚本。
SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
TEMPLATE = SKILL_ROOT / "assets" / "video-skeleton"
VERIFY = SCRIPTS / "verify_skeleton.py"
SCAFFOLD = SCRIPTS / "scaffold.py"

GATED_CLASSES = ("frozen", "overridable", "regioned", "structured")

#: 集成模式真树：env 指向的内容工作区（含哨兵与 episodes/ 真集）；离线为 None。
#: 真树判据只在集成模式下运行——本仓（skill 仓）没有 episodes/，离线无从对账。
INTEGRATION_WS = os.environ.get("TO_VIDEO_TEST_WORKSPACE")
needs_real_tree = pytest.mark.skipif(
    not INTEGRATION_WS,
    reason="真树判据：skill 仓离线无 episodes/，集成模式（TO_VIDEO_TEST_WORKSPACE）下运行",
)


def skeleton() -> dict:
    return tomllib.loads((TEMPLATE / "skeleton.toml").read_text(encoding="utf-8"))


def _clean_env() -> dict[str, str]:
    """剥掉 TO_VIDEO_*：锚点 env（TO_VIDEO_WORKSPACE）优先级高于 CWD 搜索，
    外部残留会让用例静默锚去别处；集成模式的 env 尤其必须挡在门外。"""
    return {k: v for k, v in os.environ.items() if not k.startswith("TO_VIDEO_")}


def run(
    script: Path, *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=cwd,
        env=_clean_env(),
    )


# ── 正控沙箱：假 skill 根 + 平铺工作区，绝不改真文件 ────────────────────────


def mirror_skill(tmp_path: Path) -> Path:
    """在 tmp 下搭一个**自包含的假 skill 根** → 返回它。

    只镜像门与脚手架真正读的东西：SKILL.md 哨兵 + 真 scripts/ 的
    verify_skeleton.py / scaffold.py（含同目录依赖 paths.py）+ 模板全量。
    模板升代注入（advance_template）发生在副本上；登记写工作区（register_drift）。
    """
    skill = tmp_path / "skill"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# 假 skill 根哨兵\n", encoding="utf-8")
    for name in ("verify_skeleton.py", "scaffold.py", "paths.py"):
        shutil.copy2(SCRIPTS / name, skill / "scripts" / name)
    shutil.copytree(TEMPLATE, skill / "assets" / "video-skeleton")
    return skill


def flat_ws(tmp_path: Path, sentinel: str = ".to-video-root") -> Path:
    """平铺假工作区：哨兵 + 空 seriesList + episodes/（两脚本的最小消费面）。"""
    ws = tmp_path / "ws"
    (ws / "episodes").mkdir(parents=True)
    (ws / sentinel).write_text("# 假工作区哨兵\n", encoding="utf-8")
    (ws / "series.json").write_text('{"seriesList": []}\n', encoding="utf-8")
    return ws


def write_series(ws: Path, series: list[tuple[str, list[str]]]) -> None:
    (ws / "series.json").write_text(
        json.dumps(
            {
                "seriesList": [
                    {
                        "id": sid,
                        "title": sid,
                        "rule": "",
                        "episodes": [
                            {"episode": i, "slug": s, "path": f"episodes/{s}"}
                            for i, s in enumerate(slugs, 1)
                        ],
                    }
                    for sid, slugs in series
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


#: 沙箱探针集：scaffold 实例化 ⇒ 字节即模板 ⇒ 天然无登记豁免、天然与模板一致。
#: 旧版须从真树挑「当前恰好干净」的两集（CLEAN_A/CLEAN_B），那是对真树状态的
#: 间接依赖；scaffold 产物把这层依赖消掉了。
PROBE_A = "probe-a-video"
PROBE_B = "probe-b-video"


def scaffold_into(
    skill: Path, ws: Path, slug: str, title: str = "自检"
) -> subprocess.CompletedProcess:
    """在平铺工作区上经（副本里的真）scaffold 实例化一集。

    cwd=工作区根 ⇒ 哨兵搜索锚定工作区——scaffold 建集模式要求 CWD 在工作区内
    或 TO_VIDEO_WORKSPACE 指派，二者都是双锚点的工作区锚来源。
    """
    return run(skill / "scripts" / "scaffold.py", slug, "--title", title, cwd=ws)


def register_drift(ws: Path, episode: str, rel: str, fingerprint: str | None) -> None:
    """往沙箱工作区 to-video.toml 追加一条 `[[skeleton.drift]]`。"""
    pin = f'fingerprint = "{fingerprint}"\n' if fingerprint else ""
    with (ws / "to-video.toml").open("a", encoding="utf-8") as fh:
        fh.write(
            f'\n[[skeleton.drift]]\nepisode = "{episode}"\npath = "{rel}"\n{pin}'
            'reason = "正控用条目"\n'
        )


def ws_registry(ws: Path) -> dict:
    """工作区 to-video.toml 的 [skeleton] 登记表（真树用例的读取面）。"""
    toml = ws / "to-video.toml"
    if not toml.is_file():
        return {}
    return tomllib.loads(toml.read_text(encoding="utf-8")).get("skeleton", {})


def test_declared_paths_exist_in_template():
    """清单不能指空——一条指向不存在文件的 frozen 记录是静默失效的门。"""
    skel = skeleton()
    missing = []
    for cls in GATED_CLASSES:
        for rel in skel["classes"].get(cls, []):
            # .tmpl 后缀的模板文件对应生成物同名去后缀
            if (
                not (TEMPLATE / rel).is_file()
                and not (TEMPLATE / f"{rel}.tmpl").is_file()
            ):
                missing.append(f"{cls}:{rel}")
    assert not missing, f"skeleton.toml 声明了模板中不存在的路径：{missing}"


def test_every_template_file_is_classified():
    """反向：模板里的每个文件都该有档位归属，否则新增文件会悄悄不受门。"""
    skel = skeleton()
    classified = {
        rel
        for cls in (*GATED_CLASSES, "seeded")
        for rel in skel["classes"].get(cls, [])
    }
    template_only = {"skeleton.toml", "scenes-EXAMPLE.tsx.txt"}
    unclassified = []
    for p in TEMPLATE.rglob("*"):
        if not p.is_file() or p.name in template_only or p.name == ".gitkeep":
            continue
        rel = str(p.relative_to(TEMPLATE))
        if rel.endswith(".tmpl"):
            rel = rel[: -len(".tmpl")]
        if rel not in classified:
            unclassified.append(rel)
    assert not unclassified, f"模板文件未归档位（不受任何门约束）：{unclassified}"


@needs_real_tree
def test_drift_entries_reference_real_episodes_and_paths():
    """逃逸表不能指向不存在的集或路径——陈旧豁免会静默放行真实漂移。"""
    influence = Path(INTEGRATION_WS).resolve()
    slugs = {p.name for p in (influence / "episodes").iterdir() if p.is_dir()}
    for d in ws_registry(influence).get("drift", []):
        assert d["episode"] in slugs, f"drift 指向不存在的集：{d['episode']}"
        # 「缺失」哨兵 = 登记一次合法退役（整文件删除、模板保留给其他集）；
        # 哈希指纹的条目仍必须指向实存文件，否则就是陈旧豁免
        is_absent = d.get("fingerprint") == "缺失"
        assert (
            is_absent or (influence / "episodes" / d["episode"] / d["path"]).is_file()
        ), (
            f"drift 指向不存在的文件：{d['episode']}/{d['path']}"
            '（若为合法退役，fingerprint 须钉 "缺失" 哨兵）'
        )
        assert d.get("reason", "").strip(), (
            f"{d['episode']}/{d['path']} 缺 reason —— 逃逸口必须被记录，"
            "无理由的豁免下一个人无法判断能否撤销"
        )
        # 机制上允许缺 fingerprint（向前兼容），但策略上不允许：不钉指纹的豁免
        # 等于「该文件从此永久免检」，包括与 reason 无关的后续改动。
        assert len(d.get("fingerprint", "")) == 12 or is_absent, (
            f"{d['episode']}/{d['path']} 缺 12 位 fingerprint —— 未钉指纹的豁免"
            "会把该文件此后的任何漂移一并放行；当前值可从 verify_skeleton.py 报告里取"
        )


@needs_real_tree
def test_baseline_series_exists():
    skel = skeleton()
    ids = {
        s["id"]
        for s in json.loads(
            (Path(INTEGRATION_WS).resolve() / "series.json").read_text(encoding="utf-8")
        )["seriesList"]
    }
    baseline = skel.get("baselineOf")
    if baseline is not None:
        assert baseline in ids, f"baselineOf={baseline!r} 不在 series.json"


def test_gate_actually_detects_drift(tmp_path):
    """**正控**：制造一处未登记漂移，门必须报出来并在 --strict 下失败。

    一个不会红的门等于没门。本条是这套机制的合法性来源。注入发生在沙箱副本上。
    """
    skill = mirror_skill(tmp_path)
    ws = flat_ws(tmp_path)
    assert scaffold_into(skill, ws, PROBE_A).returncode == 0
    write_series(ws, [("solo", [PROBE_A])])
    verify = skill / "scripts" / "verify_skeleton.py"
    assert run(verify, "--strict", cwd=ws).returncode == 0, "沙箱基线本身就不干净"

    victim = ws / "episodes" / PROBE_A / "video" / "src" / "types.ts"
    victim.write_bytes(victim.read_bytes() + b"\n// positive-control: injected drift\n")
    r = run(verify, "--strict", cwd=ws)
    assert r.returncode == 1, f"门未能失败：\n{r.stdout}"
    assert "types.ts" in r.stdout, r.stdout


def test_gate_catches_structured_drift_via_tmpl_fallback(tmp_path):
    """**正控（structured 档）**：模板侧只有 `package.json.tmpl`，fingerprint 曾因此
    返回 None、I2 整段跳过——单集系列连 I1 也无比较对象，package.json 于是完全
    不受门。注入依赖漂移必须被 STALE 抓到（回退读 .tmpl 后模板指纹可得）。
    """
    skill = mirror_skill(tmp_path)
    ws = flat_ws(tmp_path)
    assert scaffold_into(skill, ws, PROBE_A).returncode == 0
    write_series(ws, [("solo", [PROBE_A])])
    verify = skill / "scripts" / "verify_skeleton.py"

    victim = ws / "episodes" / PROBE_A / "video" / "package.json"
    d = json.loads(victim.read_text(encoding="utf-8"))
    d["dependencies"]["react"] = "^18.0.0"  # 依赖漂移 = structured 档的执法对象
    victim.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    r = run(verify, "--strict", cwd=ws)
    assert r.returncode == 1, f"structured 漂移未被抓住：\n{r.stdout}"
    assert "package.json" in r.stdout, r.stdout


def test_registered_drift_is_pinned_to_its_fingerprint(tmp_path):
    """**正控（豁免失效）**：登记表以 (episode, path) 为键，若不钉指纹，该文件此后
    对任何改动都永久免检——而 Main.tsx 恰是每集都要动的文件。指纹相符才放行，
    偏离内容一变必须报 DRIFT-CHANGED 并使 --strict 失败。
    """
    import verify_skeleton as vs

    rel = "video/src/types.ts"
    skill = mirror_skill(tmp_path)
    ws = flat_ws(tmp_path)
    assert scaffold_into(skill, ws, PROBE_A).returncode == 0
    assert scaffold_into(skill, ws, PROBE_B).returncode == 0
    write_series(ws, [("pair", [PROBE_A, PROBE_B])])
    verify = skill / "scripts" / "verify_skeleton.py"

    # B 集偏离（A 集仍等于模板，故 I1 有方向、能走到 DRIFT-CHANGED 分支）
    victim = ws / "episodes" / PROBE_B / rel
    victim.write_bytes(victim.read_bytes() + b"\n// drift v1\n")
    fp_v1 = vs.fingerprint(victim, rel, "frozen")

    register_drift(ws, PROBE_B, rel, fp_v1)
    assert run(verify, "--strict", cwd=ws).returncode == 0, "指纹相符却未放行"

    # 偏离内容再变一次：同一条登记不得继续兜住它
    victim.write_bytes(victim.read_bytes() + b"\n// drift v2\n")
    r = run(verify, "--strict", cwd=ws)
    assert r.returncode == 1, f"豁免未随偏离改变而失效：\n{r.stdout}"
    assert "DRIFT-CHANGED" in r.stdout, r.stdout


def test_i2_honours_the_drift_registry(tmp_path):
    """I2 必须与 I1 共用逃逸口：单集系列的 I1 是空条件，若 I2 不查登记表，
    给单集系列登记一条合法偏离后 `--strict` 永远红、登记者无路可走。
    """
    import verify_skeleton as vs

    rel = "video/src/types.ts"
    skill = mirror_skill(tmp_path)
    ws = flat_ws(tmp_path)
    assert scaffold_into(skill, ws, PROBE_A).returncode == 0
    write_series(ws, [("solo", [PROBE_A])])
    verify = skill / "scripts" / "verify_skeleton.py"

    victim = ws / "episodes" / PROBE_A / rel
    victim.write_bytes(victim.read_bytes() + b"\n// legit episode-local deviation\n")
    assert run(verify, "--strict", cwd=ws).returncode == 1, "未登记的偏离竟然放行"

    register_drift(ws, PROBE_A, rel, vs.fingerprint(victim, rel, "frozen"))
    r = run(verify, "--strict", cwd=ws)
    assert r.returncode == 0, f"已登记的偏离仍被 STALE 判红：\n{r.stdout}"


def test_i2_honours_the_overridable_class(tmp_path):
    """`overridable` 的覆写许可对 I1 与 I2 必须**同时**有效。

    I2 若不认档位，「全系列都行使许可」就会报 STALE —— 而**单集系列行使一次即是
    全系列**。于是档位声明的「只报 INFO，不 FAIL」变成只在多集系列成立，等于
    把许可撤回一半，并逼人为一次合法覆写去登记 [[drift]]。
    """
    rel = "video/src/timing.json"
    assert rel in skeleton()["classes"]["overridable"], "档位前提变了，本用例该更新"
    skill = mirror_skill(tmp_path)
    ws = flat_ws(tmp_path)
    assert scaffold_into(skill, ws, PROBE_A).returncode == 0
    write_series(ws, [("solo", [PROBE_A])])
    verify = skill / "scripts" / "verify_skeleton.py"
    assert run(verify, "--strict", cwd=ws).returncode == 0, "沙箱基线本身就不干净"

    victim = ws / "episodes" / PROBE_A / rel
    timing = json.loads(victim.read_text(encoding="utf-8"))
    timing["sceneGapSec"] = timing["sceneGapSec"] + 0.3  # 行使覆写许可
    victim.write_text(json.dumps(timing), encoding="utf-8")

    r = run(verify, "--strict", cwd=ws)
    assert r.returncode == 0, f"行使 overridable 许可却被判红：\n{r.stdout}"
    assert "STALE" not in r.stdout, r.stdout


# ── 登记面住工作区（RSI-010）：登记指向具体集 = 内容，不随模板分发 ──────────


def test_template_carries_no_workspace_registry():
    """模板零登记出厂：skill 侧出现 drift/generation 即集名泄入机制侧。"""
    import verify_skeleton as vs

    leaked = [k for k in vs.REGISTRY_KEYS if k in skeleton()]
    assert not leaked, (
        f"skill 模板含登记表 {leaked}——应写进工作区 $W/to-video.toml 的 [skeleton]"
    )


def test_skill_side_registry_is_refused(tmp_path):
    """**正控**：skill 侧写登记 ⇒ 大声退出并指路工作区。静默忽略会让登记者
    误以为已豁免；与工作区合并读取则是两处登记的 split-brain。"""
    skill = mirror_skill(tmp_path)
    ws = flat_ws(tmp_path)
    toml = skill / "assets" / "video-skeleton" / "skeleton.toml"
    with toml.open("a", encoding="utf-8") as fh:
        fh.write(
            '\n[[drift]]\nepisode = "x-video"\npath = "video/src/types.ts"\n'
            'reason = "旧版 skill 侧写法"\n'
        )
    r = run(skill / "scripts" / "verify_skeleton.py", cwd=ws)
    assert r.returncode != 0, f"skill 侧登记被静默接受：\n{r.stdout}"
    assert "to-video.toml" in r.stderr and "skeleton.drift" in r.stderr, r.stderr


def test_stale_registry_entry_is_flagged(tmp_path):
    """登记指向 series.json 未知集 ⇒ 报告点名「陈旧登记」，不计入未登记漂移。"""
    skill = mirror_skill(tmp_path)
    ws = flat_ws(tmp_path)
    assert scaffold_into(skill, ws, PROBE_A).returncode == 0
    write_series(ws, [("solo", [PROBE_A])])
    register_drift(ws, "gone-video", "video/src/types.ts", "000000000000")

    r = run(skill / "scripts" / "verify_skeleton.py", "--strict", cwd=ws)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "gone-video" in r.stdout and "陈旧登记" in r.stdout, r.stdout


def test_scaffold_produces_gate_clean_episode(tmp_path):
    """scaffold 出来的新集必须立刻通过冻结档比对（模板即真理）。

    真脚本绝对路径调用 + cwd=平铺工作区根（scaffold 的工作区锚来自 CWD 哨兵
    搜索）；真 episodes/ 下不留探针目录，也不怕并行跑测试互踩。
    """
    import hashlib

    slug = "pytest-probe-video"
    ws = flat_ws(tmp_path)
    r = run(SCAFFOLD, slug, "--title", "自检", cwd=ws)
    assert r.returncode == 0, r.stdout + r.stderr

    dest = ws / "episodes" / slug
    skel = skeleton()
    for rel in skel["classes"]["frozen"]:
        a = hashlib.md5((TEMPLATE / rel).read_bytes()).hexdigest()
        b = hashlib.md5((dest / rel).read_bytes()).hexdigest()
        assert a == b, f"scaffold 产物与模板不一致：{rel}"
    # seeded 档同样经 rglob 整树复制（scaffold 无显式文件清单）——chrome 层
    # motifs.tsx 若被未来改动漏掉，新集将连 Panel 都没有。钉住它。
    # （theme.ts 是 .tmpl 渲染产物，非字节直拷，故不在此列。）
    rel = "video/src/components/motifs.tsx"
    assert (dest / rel).read_bytes() == (TEMPLATE / rel).read_bytes(), (
        f"scaffold 未原样复制 seeded 文件：{rel}"
    )
    # scenes/ 刻意留空；样例只留在模板
    assert not (dest / "scenes-EXAMPLE.tsx.txt").exists()
    assert not any((dest / "video/src/scenes").glob("*.tsx"))
    # Main.tsx 不得带来别集的场景 import —— 否则新集开箱即 module-not-found
    main = (dest / "video/src/Main.tsx").read_text(encoding="utf-8")
    assert "./scenes/" not in main, "模板 Main.tsx 残留了某一集的场景 import"
    # 占位符必须全部渲染
    for rel in ("pipeline.toml", "README.md", "video/package.json"):
        assert "{{" not in (dest / rel).read_text(encoding="utf-8"), rel
    # 未登记到 series.json 的工程会被门点名（真 verify + 真模板 + 假工作区）
    out = run(VERIFY, cwd=ws).stdout
    assert slug in out and "未登记到 series.json" in out, out


def test_scaffolded_config_does_not_block_authoring_stages(tmp_path):
    """scaffold 产出的 pipeline.toml 必须通过 config 校验：占位符自身不合规会让
    新集连 `pipeline.py build`（Stage ③，与 TTS 无关）都跑不起来。
    """
    import config

    slug = "pytest-probe-video"
    ws = flat_ws(tmp_path)
    assert run(SCAFFOLD, slug, "--title", "自检", cwd=ws).returncode == 0
    dest = ws / "episodes" / slug
    _cfg, _origin, fails, _warns = config.load(dest, required=True)
    assert not fails, f"scaffold 产物未通过配置校验：{fails}"


def test_scaffold_rejects_bad_slug_and_existing_dir(tmp_path):
    ws = flat_ws(tmp_path)
    r = run(SCAFFOLD, "no-suffix", "--title", "x", cwd=ws)
    assert r.returncode != 0 and "-video" in (r.stdout + r.stderr)
    (ws / "episodes" / "claude-code-explained-video").mkdir()
    r = run(SCAFFOLD, "claude-code-explained-video", "--title", "x", cwd=ws)
    assert r.returncode != 0 and "已存在" in (r.stdout + r.stderr)


def test_init_workspace_is_idempotent(tmp_path):
    """`--init-workspace` 落盘全部工作区工件，且幂等：既有文件 skip-if-exists
    （--force 才覆盖）——用户已写的 series.json 不会被二跑抹回模板。
    """
    ws = tmp_path / "inited"
    r = run(SCAFFOLD, "--init-workspace", str(ws))
    assert r.returncode == 0, r.stdout + r.stderr
    for rel in (
        ".to-video-root",
        "series.json",
        "series.md",
        "to-video.toml",
        ".gitignore",
        "README.md",
        "scripts/pipeline.py",
        "scripts/check_series.py",
        "voices/README.md",
        "voices/refs.toml",
        "episodes/.gitkeep",
        "source-map/.gitkeep",
    ):
        assert (ws / rel).is_file(), f"init 未落盘 {rel}"
    # 幂等：改写 series.json 后二跑必须保留用户内容
    (ws / "series.json").write_text(
        '{"seriesList": [{"id": "user-authored"}]}\n', encoding="utf-8"
    )
    r2 = run(SCAFFOLD, "--init-workspace", str(ws))
    assert r2.returncode == 0 and "保留既有" in r2.stdout, r2.stdout + r2.stderr
    assert '"user-authored"' in (ws / "series.json").read_text(encoding="utf-8")


def test_workspace_wrapper_resolves_skill_via_env(tmp_path):
    """init 落盘的工作区薄包装：TO_VIDEO_HOME → 本仓真 check_series，且从
    **任意 CWD** 都锚回该工作区（包装器以自身位置写 TO_VIDEO_WORKSPACE，
    双锚点的工作区锚经 env 移交）。

    断言锚定真脚本的退出语：空 seriesList 是 load_series 的大声退出——只有
    链路真打通（包装器 → 真 paths.py → 真检查器）才会出现这句话。
    """
    ws = tmp_path / "inited"
    assert run(SCAFFOLD, "--init-workspace", str(ws)).returncode == 0
    r = subprocess.run(
        [sys.executable, str(ws / "scripts" / "check_series.py")],
        capture_output=True,
        text=True,
        check=False,
        cwd=tmp_path,  # 刻意不在工作区内：锚不得依赖调用现场
        env={**_clean_env(), "TO_VIDEO_HOME": str(SKILL_ROOT)},
    )
    assert r.returncode != 0
    assert "无 seriesList" in r.stdout + r.stderr, r.stdout + r.stderr


def test_template_readme_qa_commands_are_runnable():
    """模板 README 是每个新集经 scaffold 继承的「复现流水线」正典，qa 命令必须
    与 pipeline.py 的真实参数契约一致——曾整段缺 --video，照抄即 parser.error。
    """
    text = (TEMPLATE / "README.md.tmpl").read_text(encoding="utf-8")
    qa_cmds = re.findall(r"^\s*uv run.*pipeline\.py.*\bqa\b.*$", text, re.MULTILINE)
    assert qa_cmds, "模板 README 里没找到 qa 命令（检测器失效？）"
    for cmd in qa_cmds:
        assert "--video" in cmd, f"qa 命令缺 --video：{cmd}"
        # pipeline.py 以 cwd=<分集工程> 启动 qa_frames，后者 Path(video).resolve()
        # ⇒ 产物路径必须**工程相对**。`$P/out/…` 会被解析成 <工程>/$P/out/… 而落空。
        assert "--video out/" in cmd, f"qa 产物路径应为工程相对（out/…）：{cmd}"
        assert "$P/out/" not in cmd, (
            f"qa 产物路径不可用 $P 锚定（那是直调 qa_frames.py 才对的写法）：{cmd}"
        )


def test_paths_docstring_lists_all_real_importers():
    """paths.py 的「导入边界（承重，勿破）」须与实际导入方一致——契约在落地时
    就与代码矛盾的话，下一位读者会误判新增脚本违规。
    """
    doc = (SCRIPTS / "paths.py").read_text(encoding="utf-8")
    m = re.search(r"## 导入边界.*?`(.*?)`.*?可以 `import paths`", doc, re.DOTALL)
    assert m, "paths.py 导入边界小节形态变化，检测器该更新了"

    r = subprocess.run(
        ["grep", "-l", r"from paths import", "-r", str(SCRIPTS)],
        capture_output=True,
        text=True,
        check=True,
    )
    # 只认 .py：grep -r 会扫进 __pycache__ 的 paths.cpython-*.pyc（本测试自身的
    # 导入副作用），把缓存文件当「导入方」报假红
    real = {Path(p).name for p in r.stdout.split() if p.endswith(".py")} - {"paths.py"}
    allowed = set(re.findall(r"`(\w+\.py)`", doc))
    assert real <= allowed, f"实际导入方超出清单：{real - allowed}"
    assert "tts.py" not in real, "红线：tts.py 不可 import paths（拷出路径会断）"


#: 模板组件里读的 theme token。`theme.ts` 属 **seeded** 档、不受漂移门执法，
#: 而 frozen 组件对它有硬依赖——这个 seeded↔frozen 接口是本文件文件头那条
#: 「模板≡真集 ⟹ 真集 tsc 传递性验证模板」推理的**唯一缺口**：真集的 theme.ts
#: 是人写的、恰好齐全，模板的 seed 却可以缺键而无人发现。实测代价是 scaffold
#: 出的新集开箱即 6 个 TS2339（`theme.serif` / `theme.sans` 不存在）。
THEME_TOKEN_RE = re.compile(r"\btheme\.([A-Za-z][A-Za-z0-9]*)")
#: **必须先切出 `theme` 对象字面量再取键**：整文件扫会把同缩进的兄弟导出
#: （曾存在的 `export const font = { serif: … }`）一并算作已定义，于是把这条
#: 判据变成永真——注入正控时实测过一次假通过。
THEME_LITERAL_RE = re.compile(r"export const theme = \{(.*?)\n\} as const;", re.DOTALL)
#: seed 里以注释形式留给本集填的占位（concept/conceptDeep/deny 之类）不算已定义，
#: 但组件也不该引用它们——故只需比对「未注释的键」。
THEME_KEY_RE = re.compile(r"^ {2}([A-Za-z][A-Za-z0-9]*)\s*:", re.MULTILINE)
#: 受检面含 regioned：Main.tsx 同样由 scaffold 原样复制，它读 `theme.bg`。
THEME_CONSUMER_CLASSES = ("frozen", "regioned")


def seed_theme_keys() -> set[str]:
    """→ 模板 theme seed 中**未注释**的键（占位注释不算已定义）。

    供 frozen 消费面与 chrome 层 motifs 两条判据共用：键集合从 tmpl 动态解析，
    seed 将来增删底座键（如并入 danger）时判据零改动跟上。
    """
    seed = (TEMPLATE / "video/src/design/theme.ts.tmpl").read_text(encoding="utf-8")
    body = THEME_LITERAL_RE.search(seed)
    assert body, "seed 里找不到 `export const theme = {…} as const;`（形态变了？）"
    defined = set(THEME_KEY_RE.findall(body.group(1)))
    assert "bg" in defined, "seed 解析失效（键的缩进形态变了？检测器该更新了）"
    return defined


def test_template_theme_covers_frozen_component_tokens():
    """模板 theme.ts 必须覆盖 frozen 组件读到的每个 token（零依赖静态判据）。

    不拉 tsc：这套测试的定位是零基建依赖 / 5 秒跑完。判据贴着真实失效模式——
    「组件读了 seed 里没有的键」——而非贴着类型系统。
    """
    defined = seed_theme_keys()

    skel = skeleton()
    missing: list[str] = []
    gated = [
        rel for cls in THEME_CONSUMER_CLASSES for rel in skel["classes"].get(cls, [])
    ]
    for rel in gated:
        if not rel.endswith((".tsx", ".ts")):
            continue
        text = (TEMPLATE / rel).read_text(encoding="utf-8")
        for token in sorted(set(THEME_TOKEN_RE.findall(text))):
            if token not in defined:
                missing.append(f"{rel} 读了 theme.{token}")
    assert not missing, (
        "frozen 组件依赖的 token 不在模板 theme seed 里 —— scaffold 出的新集会"
        "直接 tsc 失败：\n  " + "\n  ".join(missing)
    )


# ── chrome 层 motifs 播种（seeded 档）──────────────────────────────────────
#
# motifs.tsx 的正交切分：chrome（机械排版/标注，模板播种）vs 母题（创作性，
# 各集复制 ep1 后裁剪）。seeded 档不受漂移门执法，但「模板 seed 只读底座
# token」这条接口性质必须有自己的判据——否则 chrome 层一次「顺手」引用了
# 某集概念色（core/mech/…），scaffold 出的新集就会开箱即 TS2339，且漂移门
# 照样报 0 处（theme.ts 属 seeded、无门）。这是上面那条 seeded↔frozen 缺口
# 的姊妹缺口：seeded↔seeded 同样无门。

#: chrome 层应播种的导出（含一个值导出与一个纯函数）。ep1 的调用面证明了
#: 这七个是跨集机械；清单变动 = 显式决策，须同步 references/07 母题节首段。
CHROME_EXPORTS = frozenset(
    {"Panel", "Footnote", "SceneTag", "Counter", "CodeCard", "NumberedCard", "ease"}
)
#: 刻意不进模板的创作性母题（ep1 拥有；借用方式=复制后裁剪，见 references/07 表）。
MOTIF_EXPORTS = frozenset(
    {"Terminal", "LoopRing", "DispatchTable", "GateRouter", "SlotRing", "useRingDot"}
)
MOTIFS_REL = "video/src/components/motifs.tsx"


def motifs_source(*, strip_comments: bool = False) -> str:
    text = (TEMPLATE / MOTIFS_REL).read_text(encoding="utf-8")
    if not strip_comments:
        return text
    #: 文件头注释里合法地写着「theme.ts」「Terminal」等字样——不剥注释的话
    #: token/导出提取会把散文当代码，判据直接误报。剥 `/* */` 与 `//` 两形态。
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


def export_names(text: str) -> set[str]:
    """→ 文件里的具名导出（`export const/type X` 与文件尾 `export {X};` 一并计，
    小写导出如 `ease` 同样要抓——ep1 的惯用形态就是文件尾 re-export）。"""
    names = re.findall(
        r"^export (?:const|type) ([A-Za-z][A-Za-z0-9]*)", text, re.MULTILINE
    )
    names += re.findall(r"^export \{([A-Za-z][A-Za-z0-9]*)\};", text, re.MULTILINE)
    return set(names)


def test_seed_class_lists_motifs_and_file_exists():
    """seeded 档登记了 motifs.tsx 且模板侧真实存在（清单不能指空，同上）。"""
    skel = skeleton()
    assert MOTIFS_REL in skel["classes"]["seeded"], (
        f"{MOTIFS_REL} 应在 [classes].seeded（chrome 层由模板播种）"
    )
    assert (TEMPLATE / MOTIFS_REL).is_file(), f"模板缺 {MOTIFS_REL}"


def test_chrome_motifs_split_is_enforced():
    """模板 motifs.tsx 导出的恰是 chrome 集：七个机械导出在、五个母题不在。

    「多导出」比「少导出」更危险：多出来的若带了概念色依赖（如 ep1 的
    DispatchTable 读 theme.mech），它随 scaffold 复制进新集即 TS2339；少导出
    只是新集少个便利，无破坏。故两侧都钉死，清单变化须改这里的常量。
    """
    exports = export_names(motifs_source(strip_comments=True))
    leaked = exports & MOTIF_EXPORTS
    assert not leaked, f"母题不得进模板（复制 ep1 后裁剪才是正道）：{sorted(leaked)}"
    missing = CHROME_EXPORTS - exports
    assert not missing, f"chrome 层缺导出（调用面见 ep1 各 scenes）：{sorted(missing)}"


def test_chrome_motifs_only_read_base_theme_tokens():
    """chrome 层只读**未注释的**底座 token——概念色经 accent prop 注入。

    判据复用 test_template_theme_covers_frozen_component_tokens 的解析形态
    （seed_theme_keys），但受检面是 seeded↔seeded 接口（motifs ↔ theme.ts.tmpl）。
    """
    defined = seed_theme_keys()
    used = set(THEME_TOKEN_RE.findall(motifs_source(strip_comments=True)))
    missing = sorted(used - defined)
    assert not missing, (
        f"模板 motifs.tsx 读了 seed 未定义的 theme.{missing} —— 概念色须经 "
        "accent prop 注入，否则 scaffold 出的新集开箱即 TS2339"
    )


# ── 运动层（motion）───────────────────────────────────────────────────────

#: frozen 运动层的全部文件（skeleton.toml frozen 清单的 motion 子集）
MOTION_FILES = (
    "video/src/motion/tokens.ts",
    "video/src/motion/window.ts",
    "video/src/motion/schedule.ts",
    "video/src/motion/hooks.ts",
    "video/src/motion/index.ts",
    "video/src/motion/gallery.tsx",
    "video/scripts/motion.test.ts",
)


def test_motion_layer_is_frozen_and_complete():
    """运动层文件面齐全且全部归 frozen 档——「共享的是运动机制」这一边界的机器化。

    反向判据（缺文件不受门）由 test_every_template_file_is_classified 承担；
    此处钉住「在 frozen 而非 seeded」：错放 seeded 会重蹈 motifs.tsx 裂成 5 份的覆辙。
    """
    skel = skeleton()
    frozen = set(skel["classes"].get("frozen", []))
    missing = [f for f in MOTION_FILES if f not in frozen]
    assert not missing, f"运动层文件未归 frozen：{missing}"
    for rel in MOTION_FILES:
        assert (TEMPLATE / rel).is_file(), f"模板缺 {rel}"


def test_motion_layer_reads_no_theme_tokens():
    """frozen 运动层不得读 theme——两系列 theme token 名已分叉（core/mech/deny vs
    danger），读 concept 色会当场破坏跨系列可冻结性。颜色只许经参数注入。

    判据同 test_chrome_motifs_only_read_base_theme_tokens 的口径：先剥注释，
    再查 `theme.` 引用与 theme import——注释里的散文会假阳/假阴。
    """
    import re

    for rel in MOTION_FILES:
        src = (TEMPLATE / rel).read_text(encoding="utf-8")
        stripped = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
        stripped = re.sub(r"^\s*//.*$", "", stripped, flags=re.MULTILINE)
        assert not re.search(r"\bfrom\s+'(?:\.\./)+design/theme'", stripped), (
            f"{rel} import 了 theme——运动层颜色只许经参数注入"
        )
        assert "theme." not in stripped, f"{rel} 读 theme.*——concept 色会破坏跨系列冻结"


def test_motion_test_imports_only_pure_modules():
    """motion.test.ts 只许 import 纯模块（tokens/window/schedule）与 node 内建——
    import hooks（remotion/react）会让 node --test 在无渲染环境里炸。"""
    src = (TEMPLATE / "video/scripts/motion.test.ts").read_text(encoding="utf-8")
    for m in re.finditer(r"from\s+'(\.\./src/motion/[a-z]+)\.ts'", src):
        assert m.group(1).endswith(("tokens", "window", "schedule")), (
            f"motion.test.ts import 了非纯模块：{m.group(1)}"
        )


def test_motion_test_lives_outside_tsc_include():
    """单测文件须在 video/ 而非 video/src/：其 import 带 .ts 后缀（Node ESM 解析
    规则），落进 tsconfig include 会因 allowImportingTsExtensions 未开而报 TS5097。"""
    tsconfig = json.loads(
        (TEMPLATE / "video/tsconfig.json").read_text(encoding="utf-8")
    )
    include = tsconfig.get("include", [])
    assert "src" in include and "video/scripts/motion.test.ts" not in include
    assert not (TEMPLATE / "video/src/motion/motion.test.ts").exists()


def test_chapter_progress_frozen_and_placeholder_classified():
    """顶部分段进度条：组件归 frozen（全片机械 chrome，同 Subtitle 性质——跨集
    一致即产品意图）；chapters.json 归 seeded（build_narration 每次 build 全量重写
    的派生数据）。占位必须是合法空数组——占位损坏 = 新集首次 tsc 当场红。"""
    skel = skeleton()
    assert "video/src/components/ChapterProgress.tsx" in skel["classes"]["frozen"]
    assert "video/src/chapters.json" in skel["classes"]["seeded"]
    assert (
        json.loads((TEMPLATE / "video/src/chapters.json").read_text(encoding="utf-8"))
        == []
    )


def test_chapter_progress_mount_is_load_bearing():
    """挂载行必须落在 regioned 归一化的保留区（不被 SCENE_IMPORT_RE/REGISTRY 剥
    掉）——否则某集删除挂载行后漂移门会静默放行，「统一配备」失去执法。"""
    import verify_skeleton as vs

    text = (TEMPLATE / "video/src/Main.tsx").read_text(encoding="utf-8")
    assert "ChapterProgress" in vs.normalize_main(text)


# ── 骨架分代（generation）：旧代原子组豁免的表合法性 + 正控 ─────────────────
#
# 「一次模板升级 = 一代」：分代文件是原子组（半同步 tsc 必红），故豁免只对
# 「整组停在旧代」放行。与 [[drift]] 的分工：drift 钉该集**特有**偏离（一集
# 一文件一指纹），generation 钉**模板升级遗留**的整组旧态（一组文件一组指纹，
# 按显式花名册退役）。正控沿双锚点沙箱形态（mirror_skill + flat_ws），注入的
# 分代登记落在镜像 skeleton.toml 上——真实 legacy 指纹指向真实旧代文件，镜像
# 里无从复现，故正控自登记「镜像当代」为旧代再升模板，复现整组旧态。

#: bilingual-i18n 分代组的文件面（含档位），正控与表合法性测试共用。
GEN_GROUP: tuple[tuple[str, str], ...] = (
    ("video/src/Root.tsx", "frozen"),
    ("video/src/components/NarrationAudio.tsx", "frozen"),
    ("video/src/components/Subtitle.tsx", "frozen"),
    ("video/src/components/ChapterProgress.tsx", "frozen"),
    ("video/src/Main.tsx", "regioned"),
    ("video/src/i18n.tsx", "frozen"),
)


@needs_real_tree
def test_generation_registry_is_well_formed():
    """分代表条目合法性：legacy 指纹 12 位 hex 或「缺失」；≠ 当前模板指纹
    （登记成当代值 = 永真豁免，门对该文件失明——同 drift 不钉指纹的教训）；
    声明的文件都在受门档位里（不在档内的文件无从按档位口径比对指纹）。
    Main 的 regioned 归一化口径无法在测试内对旧内容复现，由「≠ 当前模板指纹」
    与真树正控（各集停在登记旧代时门全绿）共同担保。"""
    import verify_skeleton as vs

    skel = skeleton()
    gens = ws_registry(Path(INTEGRATION_WS).resolve()).get("generation", [])
    gated_of = {
        rel: cls for cls in GATED_CLASSES for rel in skel["classes"].get(cls, [])
    }
    for g in gens:
        assert g["id"].strip() and g.get("reason", "").strip(), (
            f"generation {g.get('id')!r} 缺 id/reason —— 分代必须被记录"
        )
        assert g.get("episodes"), f"generation {g['id']} 花名册为空"
        legacy = g.get("legacy", {})
        assert legacy, f"generation {g['id']} 缺 legacy 指纹表"
        for rel, fp in legacy.items():
            assert rel in gated_of, (
                f"generation {g['id']} 声明了不受门的文件：{rel}"
                "（分代豁免按档位口径比对指纹）"
            )
            assert fp == "缺失" or re.fullmatch(r"[0-9a-f]{12}", fp), (
                f"generation {g['id']} 的 {rel} 指纹非法：{fp!r}"
                "（应 12 位 hex 或「缺失」哨兵）"
            )
            tmpl_fp = vs.fingerprint(vs.template_source(rel), rel, gated_of[rel])
            assert fp != tmpl_fp, (
                f"generation {g['id']} 的 {rel} legacy 指纹 == 当前模板 —— "
                "登记成当代值会把该文件永久豁免"
            )


@needs_real_tree
def test_generation_roster_references_real_episodes():
    """花名册不能指向不存在的集（同 drift 引用测试先例）——陈旧 roster 会让
    豁免指向幻影集、汇总行的「停旧代 N」失真。"""
    influence = Path(INTEGRATION_WS).resolve()
    slugs = {p.name for p in (influence / "episodes").iterdir() if p.is_dir()}
    for g in ws_registry(influence).get("generation", []):
        for slug in g["episodes"]:
            assert slug in slugs, f"generation {g['id']} 花名册指向不存在的集：{slug}"


def inject_generation(
    ws: Path, gid: str, episodes: list[str], legacy: dict[str, str]
) -> None:
    """往沙箱工作区 to-video.toml 追加一个 [[skeleton.generation]]（正控用）。"""
    eps = ", ".join(f'"{e}"' for e in episodes)
    lines = [
        "\n[[skeleton.generation]]",
        f'id = "{gid}"',
        'reason = "正控用分代"',
        f"episodes = [{eps}]",
        "",
        "[skeleton.generation.legacy]",
    ]
    lines += [f'"{rel}" = "{fp}"' for rel, fp in legacy.items()]
    with (ws / "to-video.toml").open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def advance_template(skill: Path, rels: list[tuple[str, str]]) -> None:
    """把镜像模板的给定文件「升一代」：追加一行注释——字节与归一化指纹都变、
    语义零变化（regioned 的 Main.tsx 追加普通注释行同样改变归一化指纹）。"""
    for rel, _cls in rels:
        p = skill / "assets" / "video-skeleton" / rel
        p.write_bytes(p.read_bytes() + b"\n// positive-control: generation bump\n")


def _gen_sandbox(tmp_path: Path, slug: str = PROBE_A):
    """正控公共脚手架：镜像 skill + scaffold 一集 + 该集当前指纹表（= 即将
    登记的「旧代」）。返回 (skill, ws, legacy)。"""
    import verify_skeleton as vs

    skill = mirror_skill(tmp_path)
    ws = flat_ws(tmp_path)
    assert scaffold_into(skill, ws, slug).returncode == 0
    write_series(ws, [("solo", [slug])])
    legacy = {
        rel: vs.fingerprint(ws / "episodes" / slug / rel, rel, cls)
        for rel, cls in GEN_GROUP
    }
    assert all(legacy.values()), "指纹表含缺失（scaffold 应复制全部分代文件）"
    return skill, ws, legacy


def test_generation_old_generation_is_exempt(tmp_path):
    """**正控 (a)**：花名册集全部文件停旧代 ⇒ 0 未登记 + INFO 可见 + 汇总行。

    scaffold 产物 == 模板（即「上一代」），登记该代后把模板升一代——集未动 =
    整组停旧代。--strict 必须放行：generation 是合法过渡态而非漂移。"""
    skill, ws, legacy = _gen_sandbox(tmp_path)
    inject_generation(ws, "gen-a", [PROBE_A], legacy)
    advance_template(skill, GEN_GROUP)

    r = run(skill / "scripts" / "verify_skeleton.py", "--strict", cwd=ws)
    assert r.returncode == 0, f"整组停旧代被判红：\n{r.stdout}"
    assert "停在旧代 gen-a" in r.stdout, f"旧代集缺 INFO 可见性：\n{r.stdout}"
    assert "GENERATION-MIXED" not in r.stdout, r.stdout
    assert "代 gen-a" in r.stdout and "停旧代 1" in r.stdout, (
        f"每代汇总行缺失：\n{r.stdout}"
    )


def test_generation_mixed_half_sync_fails(tmp_path):
    """**正控 (b)**：半同步（部分文件到新代、部分停旧代）⇒ GENERATION-MIXED
    计入未登记、--strict 失败。单集系列里这种形态对 I1/I2 **都静默**（新代指纹
    恰是唯一参照、模板在 seen），MIXED 判定是唯一的网——半同步集 tsc 必红。"""
    skill, ws, legacy = _gen_sandbox(tmp_path)
    inject_generation(ws, "gen-b", [PROBE_A], legacy)
    advance_template(skill, GEN_GROUP)
    # 只把 Root.tsx 同步到新代（模拟「拷了部分文件就停手」）
    shutil.copy2(
        skill / "assets" / "video-skeleton" / "video/src/Root.tsx",
        ws / "episodes" / PROBE_A / "video/src/Root.tsx",
    )

    r = run(skill / "scripts" / "verify_skeleton.py", "--strict", cwd=ws)
    assert r.returncode == 1, f"半同步未被判红：\n{r.stdout}"
    assert "GENERATION-MIXED gen-b" in r.stdout, r.stdout
    assert "Root.tsx" in r.stdout, f"MIXED 组摘要缺文件点名：\n{r.stdout}"


def test_generation_exempt_does_not_leak_beyond_roster(tmp_path):
    """**正控 (c)**：非花名册集停在旧代指纹 ⇒ 仍报 STALE/DRIFT——豁免按显式
    roster 生效，cp -r 复制集与新集不继承（否则「从旧代集复制」会把豁免带进
    新集，等于给未登记漂移开了传播通道）。"""
    skill = mirror_skill(tmp_path)
    ws = flat_ws(tmp_path)
    assert scaffold_into(skill, ws, PROBE_A).returncode == 0
    assert scaffold_into(skill, ws, PROBE_B).returncode == 0
    write_series(ws, [("pair", [PROBE_A, PROBE_B])])
    import verify_skeleton as vs

    legacy = {
        rel: vs.fingerprint(ws / "episodes" / PROBE_A / rel, rel, cls)
        for rel, cls in GEN_GROUP
    }
    inject_generation(ws, "gen-c", [PROBE_A], legacy)  # 花名册只含 A
    advance_template(skill, GEN_GROUP)

    r = run(skill / "scripts" / "verify_skeleton.py", "--strict", cwd=ws)
    assert r.returncode == 1, f"非花名册集继承了旧代豁免：\n{r.stdout}"
    assert PROBE_B in r.stdout and "STALE" in r.stdout, r.stdout


def test_generation_mismatched_legacy_still_fails(tmp_path):
    """**正控 (d)**：旧代指纹 ≠ 登记值 ⇒ 仍红——分代豁免同样钉指纹，登记值与
    实际不符即失效（同 [[drift]] 纪律：防「登记一次、永久免检」）。"""
    skill, ws, _legacy = _gen_sandbox(tmp_path)
    inject_generation(
        ws,
        "gen-d",
        [PROBE_A],
        {rel: "000000000000" for rel, _cls in GEN_GROUP},
    )
    advance_template(skill, GEN_GROUP)

    r = run(skill / "scripts" / "verify_skeleton.py", "--strict", cwd=ws)
    assert r.returncode == 1, f"假登记值兜住了真偏离：\n{r.stdout}"
    assert "DRIFT" in r.stdout or "STALE" in r.stdout, r.stdout


def test_generation_mixed_sees_drift_held_files(tmp_path):
    """**正控 (e)**：drift 放行的旧文件同样是原子组成员——真树形态是花名册集的
    Main/Subtitle/ChapterProgress 由 [[drift]] 钉住。整组未动 ⇒ 放行（停旧代）；
    除 drift 文件外全部同步 ⇒ GENERATION-MIXED 点名 drift 文件（此前 drift 文件
    不入表，组内只剩 new，--strict 全绿且汇总误计「已同步」，而此形态 tsc 已红）。"""
    import verify_skeleton as vs

    rel = "video/src/components/Subtitle.tsx"
    skill, ws, legacy = _gen_sandbox(tmp_path)
    sub = ws / "episodes" / PROBE_A / rel
    sub.write_bytes(sub.read_bytes() + b"\n// probe: episode-specific drift\n")
    register_drift(ws, PROBE_A, rel, vs.fingerprint(sub, rel, "frozen"))
    inject_generation(ws, "gen-f", [PROBE_A], legacy)
    advance_template(skill, GEN_GROUP)

    script = skill / "scripts" / "verify_skeleton.py"
    r = run(script, "--strict", cwd=ws)
    assert r.returncode == 0, f"整组停旧代（含 drift 文件）被判红：\n{r.stdout}"
    assert "GENERATION-MIXED" not in r.stdout, r.stdout
    assert f"INFO  {rel} · {PROBE_A} 停在旧代" not in r.stdout, r.stdout

    tmpl = skill / "assets" / "video-skeleton"
    for other, _cls in GEN_GROUP:
        if other != rel:
            shutil.copy2(tmpl / other, ws / "episodes" / PROBE_A / other)
    r = run(script, "--strict", cwd=ws)
    assert r.returncode == 1, f"drift 集半同步未被判红：\n{r.stdout}"
    assert "GENERATION-MIXED gen-f" in r.stdout and "Subtitle.tsx" in r.stdout, r.stdout
    assert "已同步 0" in r.stdout, f"半同步集被计为已同步：\n{r.stdout}"


def test_generation_does_not_override_drift_registry(tmp_path):
    """drift 优先于 generation：文件被 [[drift]] 钉住其它指纹的集，即使当前
    指纹 == 旧代登记值也按 drift 语义报 DRIFT-CHANGED，旧代豁免不兜底——特有
    偏离比代际滞后更需要盯。真树稳定形态：9 集 Subtitle 停剥句号前代，由
    [[drift]] 61df1a5e08e2 钉住而非 generation legacy。A 同步到新代（I1 参照
    稳定取模板指纹）+ B 纯旧代，才能确定性走到 DRIFT-CHANGED 分支。"""
    rel = "video/src/components/Subtitle.tsx"
    skill = mirror_skill(tmp_path)
    ws = flat_ws(tmp_path)
    assert scaffold_into(skill, ws, PROBE_A).returncode == 0
    assert scaffold_into(skill, ws, PROBE_B).returncode == 0
    write_series(ws, [("pair", [PROBE_A, PROBE_B])])
    import verify_skeleton as vs

    legacy = {
        r: vs.fingerprint(ws / "episodes" / PROBE_A / r, r, c) for r, c in GEN_GROUP
    }
    advance_template(skill, GEN_GROUP)
    # A 整组同步到新代（拷新模板）；B 不动 = 纯旧代集，但其 Subtitle 被 drift
    # 钉了一个 ≠ 旧代值的指纹（模拟「登记未随集推进复核」的形态）
    tmpl = skill / "assets" / "video-skeleton"
    for r, _cls in GEN_GROUP:
        shutil.copy2(tmpl / r, ws / "episodes" / PROBE_A / r)
    register_drift(ws, PROBE_B, rel, "111111111111")
    inject_generation(ws, "gen-e", [PROBE_A, PROBE_B], legacy)

    r = run(skill / "scripts" / "verify_skeleton.py", "--strict", cwd=ws)
    assert r.returncode == 1, f"drift 指纹失效被 generation 旧代值兜底：\n{r.stdout}"
    assert "DRIFT-CHANGED" in r.stdout and PROBE_B in r.stdout, r.stdout
    assert f"INFO  {rel} · {PROBE_B} 停在旧代" not in r.stdout, (
        f"drift 管辖的文件不应打旧代 INFO（优先级语义）：\n{r.stdout}"
    )


# ── 双语骨架（bilingual-i18n 分代内容侧）──────────────────────────────────


def test_i18n_frozen_and_audiodir_mirrors_python():
    """i18n.tsx 归 frozen（test_every_template_file_is_classified 的反向覆盖
    之外，此处钉「在 frozen 而非 seeded」——错放 seeded 会重蹈 motifs 裂成多份
    的覆辙）；audioDir/PRIMARY_LANG 与 langs.py 同构——TS/Python 双侧路径契约
    的文本形态执法（zh 无后缀是既有集零回归的根）。"""
    import langs

    skel = skeleton()
    assert "video/src/i18n.tsx" in skel["classes"]["frozen"]
    src = (TEMPLATE / "video/src/i18n.tsx").read_text(encoding="utf-8")
    assert "export const PRIMARY_LANG: Lang = 'zh';" in src, "主语言须恒 'zh'"
    assert re.search(r"lang === PRIMARY_LANG \? 'audio' : `audio/\$\{lang\}`", src), (
        "audioDir 形态漂移：与 langs.audio_dir 的同构契约破了（zh 无后缀/子目录）"
    )
    # Python 侧行为对照：两侧注册表口径一致
    assert langs.PRIMARY == "zh" and set(langs.LANGS) == {"zh", "en"}


def test_lang_provider_mount_is_load_bearing():
    """LangProvider 挂载行必须落在 regioned 归一化保留区（同 ChapterProgress
    mount 先例）——否则某集删除挂载后语言 context 消失、useLang 全部回落 zh，
    英文版静默渲成中文而漂移门放行。"""
    import verify_skeleton as vs

    text = (TEMPLATE / "video/src/Main.tsx").read_text(encoding="utf-8")
    assert "LangProvider" in vs.normalize_main(text)


def test_subtitle_en_two_line_geometry_is_pinned():
    """en 双行几何守恒：marginBottom 35 + padding 24 + 2×30×1.3 = 137 ≤ 137.4
    （zh 单行满字号包络）——不越过 qa_frames SUBTITLE_BOX_H_PX=132 检查线的
    padding 缓冲带，侵入检测两语言照常执法。三常数互锁，动任何一个须连同
    检查线重标定；zh 分支锚（54 / nowrap）同时钉住逐像素不变。"""
    src = (TEMPLATE / "video/src/components/Subtitle.tsx").read_text(encoding="utf-8")
    for pin in (
        "EN_MARGIN_BOTTOM = 35",
        "EN_TWO_LINE_SIZE = 30",
        "EN_LINE_HEIGHT = 1.3",
        "isZh ? 54 : EN_MARGIN_BOTTOM",
        "whiteSpace: twoLine ? 'normal' : 'nowrap'",
    ):
        assert pin in src, f"字幕几何/zh 分支锚被动：{pin}"
