"""check_series 八条规则的判定（tmp 平铺工作区，不依赖真实剧集状态）。

双锚点自证：脚本在 skill 仓**真位置**原地运行（SKILL 锚自 `__file__` 向上找
SKILL.md 解析），工作区锚由 CWD 哨兵搜索提供——旧「把脚本链路拷进假仓再跑」
的镜像法在新 paths.py 下会在导入期就大声退出（tmp 里没有 SKILL.md），拷不动
恰是双锚点架构的行为签名。多系列语义（2026-08 起 series.json 顶层为
seriesList[]）也在此固定：规则 1 跨系列全局，规则 2/3/4 按系列内判定。

PROJECT 锚（工作区所在 git 仓库根）的两种形态各有专门用例：tmp 树无 .git 时
回退工作区自身；宿主层 .git 为**文件**（git worktree 指针，内容 `gitdir: …`）
时锚到宿主层——FAIL 消息里的 `relative_to(PROJECT)` 路径形态即锚点的可观测
证据。工程级受检面（project_globs）与规则 7/8 的系列 id 集都住工作区
to-video.toml（内容策略随内容走），空默认的「不激活」态同样被钉住。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
SCRIPT = SCRIPTS_DIR / "check_series.py"

EP1 = {
    "episode": 1,
    "slug": "ep-a",
    "path": "episodes/ep-a",
    "title": "甲集标题",
    "accents": ["#F5C542"],
    "paper": {},
}
EP2 = {
    "episode": 2,
    "slug": "ep-b",
    "path": "episodes/ep-b",
    "title": "乙集标题",
    "accents": ["#4A9EFF"],
    "paper": {},
}
#: 另一个系列的第 1 集——用于验证「各系列各自都有第 1 集」不误报
OTHER1 = {
    "episode": 1,
    "slug": "ep-x",
    "path": "episodes/ep-x",
    "title": "丙集标题",
    "accents": ["#D97757"],
    "paper": {},
}


def S(sid: str, *eps: dict) -> dict:
    return {"id": sid, "title": sid, "rule": "", "episodes": list(eps)}


def ep_root(ws: Path, ep: dict) -> Path:
    """分集工程根。ep["path"] 是**工作区根相对**（与真 series.json 同义）。"""
    return ws / ep["path"]


def main_tsx(*scenes: str) -> str:
    """按真 Main.tsx（regioned 档）的两处可变区域生成镜像。

    形状锚定真实的 `Record<string, React.FC<{scene: SceneRange}>>` 注解——
    泛型注解自带花括号，是规则 6 注册表解析的已知锚点坑（见其
    SCENE_REGISTRY_BODY_RE 注释），此处必须如实复刻，否则测不到那条路径。
    """
    imports = "\n".join(f"import {{{s}}} from './scenes/{s}';" for s in scenes)
    entries = "\n".join(f"  P{i}: {s}," for i, s in enumerate(scenes))
    return (
        f"{imports}\n"
        "const SCENE_COMPONENTS: Record<string, React.FC<{scene: SceneRange}>> = {\n"
        f"{entries}\n"
        "};\n"
    )


def scene_file(name: str) -> str:
    """最小场景组件——规则 6 只看存在性与注册对齐，不读内容。"""
    return f"export const {name} = () => null;\n"


#: 规则 7「去站点化」的课程型系列 id 集（「站点」一词只对课程系执法）。
#: 内容策略随工作区 to-video.toml 走，skill 不携带具体系列身份。
COURSE_TOML = '[check_series]\ncourse_series_ids = ["claude-code-explained"]\n'
#: 规则 8「下期卡同步」的系列 id 集（配了统一收尾装置的系列才进门）。
NEXT_CARD_TOML = '[check_series]\nnext_card_series_ids = ["claude-code-explained"]\n'


def build_workspace(
    tmp_path: Path,
    series_list: list[dict],
    files: dict[str, str],
    scene_names: dict[str, tuple[str, ...]] | None = None,
    *,
    sentinel: str = ".to-video-root",
    git_host: bool = False,
    toml: str | None = None,
) -> Path:
    """搭建平铺假工作区 → 返回工作区根。

    - sentinel：两种哨兵都要覆盖（`.to-video-root` 新工作区 / `.influence-root`
      negentropy 兼容名），find_upward 对二者等价取先命中。
    - git_host：True 时把工作区嵌进一个上层放 **.git 文件**（git worktree 指针
      形态，内容 `gitdir: …`）的宿主目录——PROJECT 锚到宿主层（negentropy 式
      嵌套工作区同款）；False 时 tmp 树内无任何 .git，PROJECT 回退工作区自身。
      两种都是 project_root 文档化的真实路径，须各自走到。
    - files：键为**工作区相对**。宿主仓库层文件（project_globs 受检面）由调用方
      自行落到 `ws.parent`——那层在工作区之外，正是工程级受检面存在的意义。
    - toml：工作区 to-video.toml 内容；None = 不落盘 = 全空默认（新独立工作区
      的初始态，规则 7/8 与工程级受检面均不激活）。

    scene_names：slug → 场景组件名元组；值 `None` 表示该集**完全无场景层**
    （连 storyboard 也不落——脚手架期形态），`()` 表示落 storyboard 但场景为空。
    缺省对每集落 P0Hook/P1Ending 并配齐 storyboard / Main.tsx / scenes/——
    与真树的「已上线集」同构，规则 6 静默。负例用例覆盖个别 slug 构造违规形态。
    """
    if git_host:
        host = tmp_path / "host"
        host.mkdir()
        # git worktree 指针：.git 是文件不是目录，project_root 对二者皆认
        # （内容无须指向真实仓库——锚点判据只看存在性）
        (host / ".git").write_text(
            "gitdir: /nonexistent/worktree.git\n", encoding="utf-8"
        )
        ws = host / "ws"
    else:
        ws = tmp_path / "ws"
    (ws / "episodes").mkdir(parents=True)
    (ws / sentinel).write_text("# 假工作区哨兵\n", encoding="utf-8")
    for series in series_list:
        for ep in series["episodes"]:
            # path 是工作区根相对（与真 series.json 同义）
            root = ws / ep["path"]
            # exist_ok：重复 slug/path 的负例用例会两次落到同一目录
            (root / "script").mkdir(parents=True, exist_ok=True)
            (root / "script" / "narration.md").write_text(
                "## P0\n\n- [p0-01] 独立成片。\n", encoding="utf-8"
            )
            (root / "README.md").write_text(f"# {ep['title']}\n", encoding="utf-8")
            theme = root / "video/src/design/theme.ts"
            theme.parent.mkdir(parents=True, exist_ok=True)
            # 只落第一个 accent：让「清单多出的色」可被规则 4 抓到
            theme.write_text(
                f"export const theme = {{\n  x0: '{ep['accents'][0]}',\n}} as const;\n",
                encoding="utf-8",
            )
            scenes = (scene_names or {}).get(ep["slug"], ("P0Hook", "P1Ending"))
            if scenes is not None:
                # storyboard + Main.tsx + scenes/ 三件齐 = 规则 6 的执法前提
                (root / "script" / "storyboard.md").write_text(
                    "## P0\n\n- 开场\n", encoding="utf-8"
                )
                src = root / "video/src"
                (src / "scenes").mkdir(parents=True, exist_ok=True)
                (src / "Main.tsx").write_text(main_tsx(*scenes), encoding="utf-8")
                for s in scenes:
                    (src / "scenes" / f"{s}.tsx").write_text(
                        scene_file(s), encoding="utf-8"
                    )
    (ws / "series.json").write_text(
        json.dumps({"seriesList": series_list}, ensure_ascii=False),
        encoding="utf-8",
    )
    if toml is not None:
        (ws / "to-video.toml").write_text(toml, encoding="utf-8")
    for rel, content in files.items():
        dest = ws / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    return ws


def run_check(ws: Path) -> tuple[int, str]:
    """真脚本原地运行：SKILL 锚自脚本真实位置解析，CWD 落工作区内 → 哨兵搜索锚定。

    env 刻意剥掉 TO_VIDEO_*：workspace_root 的 env 优先级高于 CWD 搜索，外部
    环境残留（如集成模式的 TO_VIDEO_WORKSPACE）会让所有用例静默锚去别处。
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("TO_VIDEO_")}
    r = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ws,
        env=env,
    )
    return r.returncode, r.stdout + r.stderr


@pytest.mark.parametrize("sentinel", [".to-video-root", ".influence-root"])
def test_clean_repo_passes(tmp_path, sentinel):
    ws = build_workspace(
        tmp_path,
        [S("t", EP1, EP2)],
        {"docs/other.md": "无关内容\n"},
        sentinel=sentinel,
    )
    rc, out = run_check(ws)
    assert rc == 0, out


def test_spoken_other_title_fails(tmp_path):
    ws = build_workspace(tmp_path, [S("t", EP1, EP2)], {})
    (ep_root(ws, EP1) / "script/narration.md").write_text(
        "## P0\n\n- [p0-02] 上期我们讲过《乙集标题》。\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则1" in out and "乙集标题" in out


def test_spoken_own_title_passes(tmp_path):
    ws = build_workspace(tmp_path, [S("t", EP1, EP2)], {})
    (ep_root(ws, EP1) / "script/narration.md").write_text(
        f"## P0\n\n- [p0-02] 欢迎来到《{EP1['title']}》。\n- [p0-03] 我们下期再见。\n",
        encoding="utf-8",
    )
    rc, out = run_check(ws)
    assert rc == 0, out  # 自身标题 + 「下期」白名单


def test_title_order_inverted_fails(tmp_path):
    # 中性位置（非本集工程内）出现 ≥2 集标题时按首现位置判序——knowledge-map/CHANGELOG 场景
    files = {"notes.md": "先提《乙集标题》再提《甲集标题》，顺序倒置。\n"}
    ws = build_workspace(tmp_path, [S("t", EP1, EP2)], files)
    rc, out = run_check(ws)
    assert rc == 1 and "规则2" in out


def test_ordinal_binding_fails(tmp_path):
    files = {"notes.md": "第一集是《乙集标题》。\n"}
    ws = build_workspace(tmp_path, [S("t", EP1, EP2)], files)
    rc, out = run_check(ws)
    assert rc == 1 and "规则3" in out


def test_dead_link_fails(tmp_path):
    files = {
        "episodes/ep-a/README.md": "# 甲集标题\n[已删除](../../video-package/README.md)\n"
    }
    ws = build_workspace(tmp_path, [S("t", EP1, EP2)], files)
    rc, out = run_check(ws)
    assert rc == 1 and "规则5" in out and "video-package" in out


def test_accent_not_in_theme_fails(tmp_path):
    bad = {**EP1, "accents": ["#F5C542", "#123456"]}
    ws = build_workspace(tmp_path, [S("t", bad, EP2)], {})
    rc, out = run_check(ws)
    assert rc == 1 and "#123456" in out


# ---------------------------------------------------------------- 多系列语义


def test_two_series_each_numbered_from_one_passes(tmp_path):
    """规则 4 的 1..N 连续性按系列内判定——两个系列各自都有第 1 集是合法的。"""
    ws = build_workspace(tmp_path, [S("alpha", EP1, EP2), S("beta", OTHER1)], {})
    rc, out = run_check(ws)
    assert rc == 0, out


def test_cross_series_title_order_not_compared(tmp_path):
    """规则 2 只在系列内比顺序：先提 beta 首集再提 alpha 首集不构成倒置。"""
    files = {"notes.md": "先提《丙集标题》，再提《甲集标题》。\n"}
    ws = build_workspace(tmp_path, [S("alpha", EP1, EP2), S("beta", OTHER1)], files)
    rc, out = run_check(ws)
    assert rc == 0, out


def test_cross_series_spoken_title_fails(tmp_path):
    """规则 1 跨系列全局：beta 的口播提到 alpha 的片名仍然 FAIL。"""
    ws = build_workspace(tmp_path, [S("alpha", EP1, EP2), S("beta", OTHER1)], {})
    (ep_root(ws, OTHER1) / "script/narration.md").write_text(
        "## P0\n\n- [p0-02] 这和《甲集标题》讲的是一回事。\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则1" in out and "甲集标题" in out


def test_ordinal_binding_matches_own_series_episode(tmp_path):
    """规则 3 判据是「标题 → 它自己的序号」：beta 首集旁写第一集合法。"""
    files = {"notes.md": "第一集是《丙集标题》。\n"}
    ws = build_workspace(tmp_path, [S("alpha", EP1, EP2), S("beta", OTHER1)], files)
    rc, out = run_check(ws)
    assert rc == 0, out


def test_duplicate_slug_across_series_fails(tmp_path):
    """slug 是工程目录名，跨系列也必须唯一（否则两系列指向同一工程）。"""
    dup = {**OTHER1, "slug": EP1["slug"], "path": EP1["path"], "title": "丁集标题"}
    ws = build_workspace(tmp_path, [S("alpha", EP1), S("beta", dup)], {})
    rc, out = run_check(ws)
    assert rc == 1 and "规则4" in out and "重复" in out


def test_series_without_episodes_exits(tmp_path):
    ws = build_workspace(tmp_path, [S("alpha", EP1)], {})
    (ws / "series.json").write_text(
        json.dumps({"seriesList": [{"id": "empty", "episodes": []}]}),
        encoding="utf-8",
    )
    rc, out = run_check(ws)
    assert rc != 0 and "无 episodes" in out


# ---------------------------------------------------------------- 反向登记（规则 4 反向）
#
# scaffold 刻意不写 series.json（登记是内容决策），漏登因此是高概率人祸——
# 旧门只遍历 series.json 对孤儿目录**结构性失明**。判据按 narration.md 是否
# 落盘分级（死锁分析见 check_series.rule_manifest_integrity）。


def test_orphan_with_narration_fails(tmp_path):
    """narration.md 已落盘的未登记目录必须 FAIL：规则 1 的反串线扫描看不见它。"""
    ws = build_workspace(tmp_path, [S("t", EP1)], {})
    orphan = ws / "episodes" / "orphan-video"
    (orphan / "script").mkdir(parents=True)
    (orphan / "script" / "narration.md").write_text(
        "## P0\n\n- [p0-01] 独立成片。\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则4" in out and "orphan-video" in out
    assert "已有 narration.md" in out


def test_orphan_scaffold_warns_not_fails(tmp_path):
    """脚手架期（无 narration.md）只 WARN：一概 FAIL 会与规则 4 的 accents
    校验前后夹死 scaffold→登记窗口（死锁注释的机器化复述）。"""
    ws = build_workspace(tmp_path, [S("t", EP1)], {})
    orphan = ws / "episodes" / "orphan-video"
    (orphan / "script").mkdir(parents=True)  # 只有空 script/，narration 未落盘
    rc, out = run_check(ws)
    assert rc == 0 and "WARN 规则4" in out and "orphan-video" in out
    assert "转 FAIL" in out


def test_registered_episode_no_orphan_message(tmp_path):
    """已登记集不触发反向登记消息（默认 fixture 即此形态，显式锁死）。"""
    ws = build_workspace(tmp_path, [S("t", EP1, EP2)], {})
    rc, out = run_check(ws)
    assert rc == 0 and "未登记到 series.json" not in out


# ---------------------------------------------------------------- 撞色（规则 4 系列内）


def test_same_hex_within_series_fails(tmp_path):
    """系列内两集共用同一 accent 是视觉契约违规（skills/06「已用色错开」）。"""
    clash = {**EP2, "accents": [EP1["accents"][0]]}
    ws = build_workspace(tmp_path, [S("t", EP1, clash)], {})
    rc, out = run_check(ws)
    assert rc == 1 and "规则4" in out and "撞色" in out and EP1["accents"][0] in out
    assert "ep-a" in out and "ep-b" in out


def test_same_hex_across_series_passes(tmp_path):
    """跨系列撞色是接受态：两系列发布顺序与视觉契约各自独立（docstring 已固定）。"""
    clash = {**OTHER1, "accents": [EP1["accents"][0]]}
    ws = build_workspace(tmp_path, [S("alpha", EP1), S("beta", clash)], {})
    rc, out = run_check(ws)
    assert rc == 0 and "撞色" not in out


def test_occupied_hex_info_line_present(tmp_path):
    """每系列刷一行已用色登记（skills/06 登记表的机器化输出）。"""
    ws = build_workspace(tmp_path, [S("t", EP1, EP2)], {})
    rc, out = run_check(ws)
    assert rc == 0 and "INFO 规则4：t 已用色" in out
    assert EP1["accents"][0] in out and EP2["accents"][0] in out


# ---------------------------------------------------------------- 可渲染性（规则 6）


def test_storyboard_with_empty_scenes_fails(tmp_path):
    """storyboard 定稿后 scenes/ 仍空：口播已定、画面未写，规则 6 第一判据。"""
    ws = build_workspace(tmp_path, [S("t", EP1)], {}, scene_names={EP1["slug"]: ()})
    rc, out = run_check(ws)
    assert rc == 1 and "规则6" in out and EP1["slug"] in out and "为空" in out


def test_registry_entry_without_scene_file_fails(tmp_path):
    """注册表条目指向不存在的场景文件——tsc/build 必炸的形态。

    必须保留一个在档场景文件（P1Ending）使「scenes/ 为空」判据先行放行，
    才能测到「注册 → import → 文件」这条链路本身。"""
    ws = build_workspace(tmp_path, [S("t", EP1)], {})
    # 删掉注册表里的 P0Hook 的实体文件：注册与 import 都在，文件没了
    (ep_root(ws, EP1) / "video/src/scenes/P0Hook.tsx").unlink()
    rc, out = run_check(ws)
    assert rc == 1 and "规则6" in out and "P0Hook" in out


def test_registry_entry_without_import_fails(tmp_path):
    """注册表值无对应 import（标识符未定义）——与文件缺失同为渲染必炸形态。"""
    ws = build_workspace(tmp_path, [S("t", EP1)], {})
    src = ep_root(ws, EP1) / "video/src"
    # 注册表保留 P0: P0Hook，但抹掉它的 import 行
    main = (src / "Main.tsx").read_text(encoding="utf-8")
    (src / "Main.tsx").write_text(
        main.replace("import {P0Hook} from './scenes/P0Hook';\n", ""),
        encoding="utf-8",
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则6" in out and "P0Hook" in out and "import" in out


def test_scene_file_not_registered_warns(tmp_path):
    """场景文件未进注册表只 WARN：可能是被其他场景 import 的合法辅助组件。"""
    ws = build_workspace(
        tmp_path, [S("t", EP1)], {}, scene_names={EP1["slug"]: ("P0Hook",)}
    )
    (ep_root(ws, EP1) / "video/src/scenes/HelperCard.tsx").write_text(
        scene_file("HelperCard"), encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 0 and "WARN 规则6" in out and "HelperCard" in out


def test_no_storyboard_rule6_silent(tmp_path):
    """storyboard 未落盘（阶段②完成前）是合法脚手架期，规则 6 整体不执法。"""
    ws = build_workspace(tmp_path, [S("t", EP1)], {}, scene_names={EP1["slug"]: None})
    rc, out = run_check(ws)
    assert rc == 0 and "规则6" not in out


# ---------------------------------------------------------------- PROJECT 锚（双锚点）


def test_project_falls_back_to_workspace_without_git(tmp_path):
    """tmp 树内无任何 .git：PROJECT 回退**工作区自身**——此路径必须真实走到。

    证据是 FAIL 消息的 `relative_to(PROJECT)` 形态：锚在工作区 ⇒ 路径无
    「ws/」前缀（若误锚到 tmp_path 层则会带前缀）。"""
    ws = build_workspace(tmp_path, [S("t", EP1)], {})
    (ep_root(ws, EP1) / "README.md").write_text(
        "# 甲集标题\n[死链](../../video-package/README.md)\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 1 and "FAIL 规则5：episodes/ep-a/README.md 死链" in out


def test_project_anchors_to_git_file_pointer_above_workspace(tmp_path):
    """宿主层 .git 是**文件**（git worktree 指针，内容 `gitdir: …`）：PROJECT
    锚到宿主层——`(p/".git").is_dir()` 式判据会在此形态失效，文件/目录皆认
    是 paths.project_root 的承重契约（negentropy 式嵌套工作区即此形态）。"""
    ws = build_workspace(
        tmp_path, [S("t", EP1)], {}, sentinel=".influence-root", git_host=True
    )
    (ep_root(ws, EP1) / "README.md").write_text(
        "# 甲集标题\n[死链](../../video-package/README.md)\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    # 「ws/」前缀 = PROJECT 锚在宿主层（工作区相对路径拼上了工作区目录名）
    assert rc == 1 and "FAIL 规则5：ws/episodes/ep-a/README.md 死链" in out


def test_project_globs_cover_host_repo_files(tmp_path):
    """工程级受检面：to-video.toml 声明 project_globs 后，**宿主仓库层**文件
    （工作区之外）进门受检——knowledge-map/CHANGELOG 整目录迁移断链的执法点。"""
    ws = build_workspace(
        tmp_path,
        [S("t", EP1, EP2)],
        {},
        git_host=True,
        toml='[check_series]\nproject_globs = ["docs/knowledge-map.md"]\n',
    )
    host = ws.parent
    (host / "docs").mkdir()
    (host / "docs" / "knowledge-map.md").write_text(
        "第一集是《乙集标题》。\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    # 消息路径相对 PROJECT（宿主层）：无「ws/」前缀
    assert rc == 1 and "规则3" in out and "docs/knowledge-map.md" in out


def test_project_globs_default_empty_host_files_uncovered(tmp_path):
    """空默认（to-video.toml 缺席）：宿主层文件不进门——独立工作区没有宿主
    文档层，刻意的空默认而非全收（连带执法宿主既存债只会促使有人删配置）。"""
    ws = build_workspace(tmp_path, [S("t", EP1, EP2)], {}, git_host=True)
    host = ws.parent
    (host / "docs").mkdir()
    (host / "docs" / "knowledge-map.md").write_text(
        "第一集是《乙集标题》。\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 0 and "规则3" not in out


# ── 规则 7 · 去站点化（2026-08-23 系列改造引入）──────────────────────────────
#: 强标识（learn.shareai / Learn Claude Code / shareAI / 课程 / 章号 s01–s20）
#: 全系列执法（**不随配置**）；「站点」一词只对 course_series_ids 中的课程系
#: 执法（论文系用它指论文配套网站）。COURSE_S 走 COURSE_TOML 配置后的形态，
#: 「不配置不执法」的空默认负测见 test_rules_7_8_inactive_without_workspace_config。
COURSE_S = {
    "episode": 1,
    "slug": "ep-course",
    "path": "episodes/ep-course",
    "title": "课程系首集",
    "accents": ["#F5C542"],
    "paper": {},
}


def test_rule7_course_word_in_narration_fails(tmp_path):
    ws = build_workspace(
        tmp_path, [S("claude-code-explained", COURSE_S)], {}, toml=COURSE_TOML
    )
    (ep_root(ws, COURSE_S) / "script/narration.md").write_text(
        "## P0\n\n- [p0-02] 课程作者拆过源码，他说……\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则7" in out and "课程" in out


def test_rule7_chapter_id_in_storyboard_fails(tmp_path):
    ws = build_workspace(
        tmp_path, [S("claude-code-explained", COURSE_S)], {}, toml=COURSE_TOML
    )
    (ep_root(ws, COURSE_S) / "script/storyboard.md").write_text(
        "## P0\n\n- 0-A 开场（对应 s01）\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则7" in out and "s01" in out


def test_rule7_site_url_in_scene_fails(tmp_path):
    ws = build_workspace(
        tmp_path, [S("claude-code-explained", COURSE_S)], {}, toml=COURSE_TOML
    )
    scene = ep_root(ws, COURSE_S) / "video/src/scenes/P0Hook.tsx"
    scene.write_text(
        "export const P0Hook = () => null;\n// 信源：learn.shareai.run/zh/s01/\n",
        encoding="utf-8",
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则7" in out and "learn.shareai" in out


def test_rule7_anonymized_attribution_passes(tmp_path):
    """三级证据归属匿名化后的合法形态：有人拆过它的源码。"""
    ws = build_workspace(
        tmp_path, [S("claude-code-explained", COURSE_S)], {}, toml=COURSE_TOML
    )
    (ep_root(ws, COURSE_S) / "script/narration.md").write_text(
        "## P0\n\n- [p0-02] 有人拆过它的源码，他说……\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 0, out


def test_rule7_research_layer_not_policed(tmp_path):
    """内部取证层保留具名归属（research/ 不进门）——两层口径的执法边界。"""
    ws = build_workspace(
        tmp_path, [S("claude-code-explained", COURSE_S)], {}, toml=COURSE_TOML
    )
    (ep_root(ws, COURSE_S) / "research").mkdir(parents=True)
    (ep_root(ws, COURSE_S) / "research/source-notes.md").write_text(
        "课程作者拆过源码（具名归属，仓内义务）。\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 0, out


def test_rule7_zhandian_word_course_series_fails(tmp_path):
    """「站点」在课程系（course_series_ids 已配置）是站点指称——FAIL。"""
    ws = build_workspace(
        tmp_path, [S("claude-code-explained", COURSE_S)], {}, toml=COURSE_TOML
    )
    (ep_root(ws, COURSE_S) / "script/narration.md").write_text(
        "## P0\n\n- [p0-02] 配套站点上还有一张图。\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则7" in out and "站点" in out


def test_rule7_zhandian_word_paper_series_passes(tmp_path):
    """「站点」在论文系指论文配套网站——正常用法，静默（课程 id 集不含它）。"""
    ws = build_workspace(tmp_path, [S("self-evolution", EP1)], {}, toml=COURSE_TOML)
    (ep_root(ws, EP1) / "script/narration.md").write_text(
        "## P0\n\n- [p0-02] 官方工程站点统计出的三张活地图。\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 0, out


def test_rule7_strong_marker_in_paper_series_fails(tmp_path):
    """强标识全系列执法（**不随 to-video.toml 配置**）：论文系出现课程章号
    同样异常——不落 toml 即钉住「无配置也执法」的强标识口径。"""
    ws = build_workspace(tmp_path, [S("self-evolution", EP1)], {})
    (ep_root(ws, EP1) / "script/storyboard.md").write_text(
        "## P0\n\n- 0-A 开场（对应 s13 后台任务）\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则7" in out and "s13" in out


def test_rule7_chapter_id_cjk_adjacent_fails(tmp_path):
    """章号贴邻汉字（无空格）同样命中——`\b` 在 CJK 邻接下不成立（评审修复），
    改用 ASCII 侧环视后「对应s01」这类中文最自然的笔误形态不再逃过执法。"""
    ws = build_workspace(
        tmp_path, [S("claude-code-explained", COURSE_S)], {}, toml=COURSE_TOML
    )
    (ep_root(ws, COURSE_S) / "script/storyboard.md").write_text(
        "## P0\n\n- 0-A 开场（对应s01的循环）\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则7" in out and "s01" in out


def test_rule7_chapter_id_cjk_adjacent_trailing_fails(tmp_path):
    """章号后紧跟汉字（「看s13的后台」）同样命中。"""
    ws = build_workspace(
        tmp_path, [S("claude-code-explained", COURSE_S)], {}, toml=COURSE_TOML
    )
    (ep_root(ws, COURSE_S) / "script/narration.md").write_text(
        "## P0\n\n- [p0-02] 看s13的后台任务。\n", encoding="utf-8"
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则7" in out and "s13" in out


def test_rule7_chapter_id_prefix_suffix_ascii_still_exempt(tmp_path):
    """ASCII 词符贴邻（`s01e02` / `as01` / `s01_agent_loop` 目录名）仍豁免——
    环视排除集与原 `\b` 行为对齐，仅补上 CJK 贴邻盲区。"""
    ws = build_workspace(
        tmp_path, [S("claude-code-explained", COURSE_S)], {}, toml=COURSE_TOML
    )
    (ep_root(ws, COURSE_S) / "script/storyboard.md").write_text(
        "## P0\n\n- 0-A 开场（对比 as01 / s01e02 / s01_agent_loop 三种写法）\n",
        encoding="utf-8",
    )
    rc, out = run_check(ws)
    assert rc == 0, out


# ── 规则 8 · 下期卡与 series.json 同步（2026-08-23 评审修复引入）──────────────
#: P6 文本须含本集标题与下集标题的主段（「：」后半）；标题带主副结构时画面卡
#: 只放副题。系列 id 须在 next_card_series_ids（配了统一收尾装置的系列）。
#: accent 与 COURSE_S 错开（规则 4 系列内禁撞色）。
NEXT_EP2 = {
    "episode": 2,
    "slug": "ep-next2",
    "path": "episodes/ep-next2",
    "title": "规划层：视野是安排出来的",
    "accents": ["#9C90EE"],
    "paper": {},
}


def _write_p6(ws: Path, ep: dict, body: str) -> None:
    p6 = ep_root(ws, ep) / "video/src/scenes"
    p6.mkdir(parents=True, exist_ok=True)
    (p6 / "P6Ending.tsx").write_text(
        "export const P6Ending = () => null;\n" + body, encoding="utf-8"
    )


def test_rule8_next_card_stale_title_fails(tmp_path):
    """下期卡硬编码的旧标题与 series.json 不符——系列更名时的陈旧预告，FAIL。"""
    ws = build_workspace(
        tmp_path,
        [
            S(
                "claude-code-explained",
                {**COURSE_S, "title": "执行层：一个循环"},
                NEXT_EP2,
            )
        ],
        {},
        toml=NEXT_CARD_TOML,
    )
    # 用 series.json 的最新标题替换画面卡的旧串 → 陈旧
    _write_p6(
        ws,
        COURSE_S,
        "// {'下期 · 规划层'} {'旧标题占位'}",
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则8" in out and "视野是安排出来的" in out


def test_rule8_own_identity_card_missing_fails(tmp_path):
    """身份卡缺本集标题（更名后只改了下期卡）——FAIL。"""
    ws = build_workspace(
        tmp_path,
        [S("claude-code-explained", COURSE_S, NEXT_EP2)],
        {},
        toml=NEXT_CARD_TOML,
    )
    _write_p6(
        ws,
        COURSE_S,
        "// 只有下期卡：{'视野是安排出来的'}，身份卡标题没更新",
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则8" in out and "身份卡缺本集标题" in out


def test_rule8_synced_cards_pass(tmp_path):
    """身份卡 + 下期卡都与 series.json 主段一致——静默。"""
    ws = build_workspace(
        tmp_path,
        [
            S(
                "claude-code-explained",
                {**COURSE_S, "title": "执行层：一个循环"},
                NEXT_EP2,
            )
        ],
        {},
        toml=NEXT_CARD_TOML,
    )
    _write_p6(
        ws,
        COURSE_S,
        "// {'执行层：一个循环'} {'下期 · 规划层'} {'视野是安排出来的'}",
    )
    _write_p6(
        ws,
        NEXT_EP2,
        "// {'视野是安排出来的'}（末集，无下期断言）",
    )
    rc, out = run_check(ws)
    assert rc == 0, out


def test_rule8_paper_series_not_policed(tmp_path):
    """self-evolution 系无身份卡装置（旧版论文型收尾）——规则 8 不进门。"""
    ws = build_workspace(
        tmp_path, [S("self-evolution", EP1, EP2)], {}, toml=NEXT_CARD_TOML
    )
    # EP1 的 P6 只有「我们下期再见」，无任何标题卡
    _write_p6(ws, EP1, "// {'我们下期再见'}")
    rc, out = run_check(ws)
    assert rc == 0, out


def test_rules_7_8_inactive_without_workspace_config(tmp_path):
    """空默认（to-video.toml 缺席）：系列 id 集为空 → 规则 7 的「站点」判据与
    规则 8 整体不激活——独立新工作区在声明内容策略前不被误伤。

    与 test_rule7_zhandian_word_course_series_fails / 规则 8 各 FAIL 用例
    构成「同一违规、配置前后」的对拍；强标识（课程/章号）不在此列——它不随
    配置，全系列执法（见 test_rule7_strong_marker_in_paper_series_fails）。"""
    ws = build_workspace(tmp_path, [S("claude-code-explained", COURSE_S, NEXT_EP2)], {})
    (ep_root(ws, COURSE_S) / "script/narration.md").write_text(
        "## P0\n\n- [p0-02] 配套站点上还有一张图。\n", encoding="utf-8"
    )
    _write_p6(ws, COURSE_S, "// {'下期 · 规划层'} {'旧标题占位'}")
    rc, out = run_check(ws)
    assert rc == 0 and "规则7" not in out and "规则8" not in out


# ── en 译稿：规则 1 英文顺序词 + 规则 7 受检面（RSI-004）──────────────────────


def test_rule1_en_ordinal_word_fails(tmp_path):
    """en 译稿口播出现英文顺序词（previous episode 等）——序号只允许存在于
    视觉层与 series.json，en 侧同理执法。"""
    ws = build_workspace(tmp_path, [S("t", EP1, EP2)], {})
    (ep_root(ws, EP1) / "script/narration.en.md").write_text(
        "## P0\n\n- [p0-01] In the previous episode we covered the loop.\n",
        encoding="utf-8",
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则1" in out and "previous episode" in out


def test_rule1_en_next_time_closing_passes(tmp_path):
    """白名单：`see you next time` 收尾语放行——顺序无关的告别语（与 zh「下期」
    同一先例），正则只收 next episode 而不收裸 next。"""
    ws = build_workspace(tmp_path, [S("t", EP1, EP2)], {})
    (ep_root(ws, EP1) / "script/narration.en.md").write_text(
        "## P0\n\n- [p0-01] That is the whole picture. See you next time!\n",
        encoding="utf-8",
    )
    rc, out = run_check(ws)
    assert rc == 0, out


def test_rule1_en_ordinal_word_boundaries(tmp_path):
    """词边界 + 惯用法：`this series of …`（「这一连串」）放行；zh「上一集」最常见
    的英文说法 last episode 命中。"""
    ws = build_workspace(tmp_path, [S("t", EP1, EP2)], {})
    en_md = ep_root(ws, EP1) / "script/narration.en.md"
    en_md.write_text(
        "## P0\n\n- [p0-01] This series of commands builds the index.\n",
        encoding="utf-8",
    )
    rc, out = run_check(ws)
    assert rc == 0, out
    en_md.write_text(
        "## P0\n\n- [p0-01] In the last episode we built the index.\n",
        encoding="utf-8",
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则1" in out and "last episode" in out


def test_rule7_en_narration_in_audience_globs(tmp_path):
    """AUDIENCE_GLOBS 增 narration.en.md：英文稿里的站点标识同样进门（ASCII
    章号在英文稿更易顺手写出）；他集标题互查对 en 跳过（标题仅 zh，已知边界）。"""
    ws = build_workspace(
        tmp_path, [S("claude-code-explained", COURSE_S)], {}, toml=COURSE_TOML
    )
    (ep_root(ws, COURSE_S) / "script/narration.en.md").write_text(
        "## P0\n\n- [p0-01] See the course site for details (s01).\n",
        encoding="utf-8",
    )
    rc, out = run_check(ws)
    assert rc == 1 and "规则7" in out and "s01" in out and "narration.en.md" in out
