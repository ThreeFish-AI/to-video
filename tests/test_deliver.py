"""deliver 子命令契约：根路径两渠道、series.json 身份锚、标题 vN 版本管理。

形态沿 test_check_series.run_check 先例：subprocess + cwd=ws + 剥 TO_VIDEO_* env
（防集成模式 env 残留锚走别的树）。纯函数（清洗/计号）in-process 直测；
deliver.py 的 WORKSPACE 消费全在函数内（paths 惰性解析），subprocess 形态
天然走真解析路径。交付根一律落 tmp_path——conftest 的真树守卫只盯
episodes/，不掩护工作区外写入。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
DELIVER = SCRIPTS / "deliver.py"
sys.path.insert(0, str(SCRIPTS))

import deliver  # noqa: E402 - sys.path 注入后导入；纯函数 in-process 直测

SLUG = "blueprint-video"
TITLE = "Context Layer Blueprint"
SID = "context-layer"


def build_ws(
    tmp_path: Path,
    *,
    title: str = TITLE,
    slug: str = SLUG,
    sid: str = SID,
    series_json: dict | None = None,
) -> Path:
    """最小可交付工作区：哨兵 + series.json（一集已登记）+ out/final.mp4。"""
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / ".to-video-root").write_text("# sentinel\n", encoding="utf-8")
    data = series_json or {
        "seriesList": [
            {
                "id": sid,
                "title": "Context Layer 系列",
                "episodes": [
                    {
                        "episode": 1,
                        "slug": slug,
                        "title": title,
                        "path": f"episodes/{slug}",
                    }
                ],
            }
        ]
    }
    (ws / "series.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (ws / "episodes" / slug / "out").mkdir(parents=True)
    (ws / "episodes" / slug / "out" / "final.mp4").write_bytes(b"fake-final-A")
    return ws


def run_deliver(
    ws: Path,
    *extra: str,
    project: str | None = None,
    env_extra: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """按真实调用形态驱动 deliver.py；剥 TO_VIDEO_* 防外层 env 改变锚走向。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("TO_VIDEO_")}
    env.update(env_extra or {})
    return subprocess.run(
        [
            sys.executable,
            str(DELIVER),
            "--project",
            project or str(ws / "episodes" / SLUG),
            *extra,
        ],
        cwd=cwd or ws,
        env=env,
        capture_output=True,
        text=True,
    )


def tree_snapshot(root: Path) -> set[str]:
    """文件与目录全收——dry-run 的「连目录都不建」声明需要目录级可见性。"""
    return {str(p.relative_to(root)) for p in root.rglob("*")}


def out_text(r: subprocess.CompletedProcess[str]) -> str:
    return r.stdout + r.stderr


# ---------------- 纯函数 ----------------


@pytest.mark.parametrize(
    "raw,want",
    [
        ("a/b", "a-b"),
        ("a:b", "a-b"),
        ("a\\b", "a-b"),
        ("a?b", "a-b"),
        ("a*b", "a-b"),
        ('a"b', "a-b"),
        ("a<b", "a-b"),
        ("a>b", "a-b"),
        ("a|b", "a-b"),
        ("a\nb", "a-b"),
        ("  padded  ", "padded"),
        ("AI 如何自己变强？", "AI 如何自己变强？"),  # 全角标点保留
        ("Context Layer Blueprint", "Context Layer Blueprint"),  # 空格保留
        ("///", "---"),  # 纯非法字符逐个替换，不折叠为空（空值守卫只管纯空白）
    ],
)
def test_sanitize_deterministic_and_idempotent(raw, want):
    assert deliver.sanitize(raw) == want
    assert deliver.sanitize(deliver.sanitize(raw)) == want  # 幂等


def test_scan_versions_semantics():
    """计号判据：全名 fullmatch + int 比较；洞不回填、尾巴/前缀重叠/杂文件不抬号。"""
    assert deliver.scan_versions([], "T") == []
    names = ["T v1.mp4", "T v2.mp4"]
    assert deliver.scan_versions(names, "T") == [(1, "T v1.mp4"), (2, "T v2.mp4")]
    # v10 与 v2 并存按 int 排最大（字典序会把 v2 抬到 v10 之上）
    assert deliver.scan_versions(["T v2.mp4", "T v10.mp4"], "T")[-1][0] == 10
    # 标题自带「 v2」尾巴：计入的是文件名尾部的真版本号，不是标题的一部分
    assert deliver.scan_versions(["X v2 时代的 Y v1.mp4"], "X v2 时代的 Y") == [
        (1, "X v2 时代的 Y v1.mp4")
    ]
    # 前缀重叠标题互不抬号："X Y v3" 不是 "Y" 的版本
    assert deliver.scan_versions(["X Y v3.mp4"], "Y") == []
    # 非匹配文件不抬号
    assert deliver.scan_versions([".DS_Store", "T.mp4", "T v1 (副本).mp4"], "T") == []


# ---------------- 版本落盘（subprocess） ----------------


def test_first_delivery_creates_v1(tmp_path: Path):
    ws = build_ws(tmp_path)
    root = tmp_path / "dv"
    r = run_deliver(ws, "--root", str(root))
    assert r.returncode == 0, out_text(r)
    f = root / SID / f"{TITLE} v1.mp4"
    assert f.is_file() and f.read_bytes() == b"fake-final-A"
    assert (ws / "episodes" / SLUG / "out" / "final.mp4").is_file()  # 源保留


def test_changed_bytes_increment_to_v2(tmp_path: Path):
    ws = build_ws(tmp_path)
    root = tmp_path / "dv"
    run_deliver(ws, "--root", str(root))
    (ws / "episodes" / SLUG / "out" / "final.mp4").write_bytes(b"fake-final-B")
    r = run_deliver(ws, "--root", str(root))
    assert r.returncode == 0, out_text(r)
    assert (root / SID / f"{TITLE} v1.mp4").read_bytes() == b"fake-final-A"
    assert (root / SID / f"{TITLE} v2.mp4").read_bytes() == b"fake-final-B"


def test_identical_bytes_skip_not_new_version(tmp_path: Path):
    """同字节重投：跳过不升版——重跑命令/隔日补投不产生 GB 级重复副本。"""
    ws = build_ws(tmp_path)
    root = tmp_path / "dv"
    run_deliver(ws, "--root", str(root))
    r = run_deliver(ws, "--root", str(root))
    assert r.returncode == 0, out_text(r)
    assert "跳过" in r.stdout and "v1" in r.stdout
    assert not (root / SID / f"{TITLE} v2.mp4").exists()


def test_version_gap_not_backfilled(tmp_path: Path):
    """v1/v2 被手删只剩 v3 → 下一号 v4：防覆写优先于号连续。"""
    ws = build_ws(tmp_path)
    root = tmp_path / "dv" / SID
    root.mkdir(parents=True)
    (root / f"{TITLE} v3.mp4").write_bytes(b"old")
    (ws / "episodes" / SLUG / "out" / "final.mp4").write_bytes(b"new-bytes")
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode == 0, out_text(r)
    assert (root / f"{TITLE} v4.mp4").is_file()


def test_copy_preserves_bytes_and_mtime(tmp_path: Path):
    ws = build_ws(tmp_path)
    src = ws / "episodes" / SLUG / "out" / "final.mp4"
    t = time.time() - 3600
    os.utime(src, (t, t))
    root = tmp_path / "dv"
    assert run_deliver(ws, "--root", str(root)).returncode == 0
    dest = root / SID / f"{TITLE} v1.mp4"
    assert dest.read_bytes() == src.read_bytes()
    assert abs(dest.stat().st_mtime - t) < 2  # copy2 保 mtime（版本快照可追溯）


def test_copy_failure_leaves_no_debris(tmp_path, monkeypatch):
    """os.replace 阶段失败（.part 已真实落盘）：清理守卫承重——无 .part 残留、
    无残缺版本文件、大声退出。（变异锚点：删除 unlink 行本测试必红。）"""
    ws = build_ws(tmp_path)
    root = tmp_path / "dv"
    monkeypatch.setenv("TO_VIDEO_WORKSPACE", str(ws))

    def boom(*_a, **_k):
        raise OSError("replace failed (simulated)")

    monkeypatch.setattr(deliver.os, "replace", boom)
    monkeypatch.setattr(
        deliver.sys,
        "argv",
        ["deliver.py", "--project", str(ws / "episodes" / SLUG), "--root", str(root)],
    )
    with pytest.raises(SystemExit) as ei:
        deliver.main()
    assert ei.value.code
    assert not list(root.rglob("*.part"))
    assert not list(root.rglob("*.mp4"))


def test_dest_collision_refuses_overwrite(tmp_path: Path):
    """大小写不敏感 FS 上扫描漏网（标题仅大小写变化）→ dest.exists() 复查兜底，
    绝不静默覆写已交付版本。"""
    probe = tmp_path / ".ci-probe"
    probe.mkdir()
    (probe / "A").write_text("x", encoding="utf-8")
    ci = (probe / "a").exists()
    shutil.rmtree(probe)
    if not ci:
        pytest.skip("文件系统大小写敏感，覆写兜底不可达（macOS 默认 APFS 不敏感）")
    ws = build_ws(tmp_path)
    root = tmp_path / "dv" / SID
    root.mkdir(parents=True)
    (root / f"{TITLE.lower()} v1.mp4").write_bytes(b"delivered-old")
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "拒绝覆写" in out_text(r)
    assert (root / f"{TITLE.lower()} v1.mp4").read_bytes() == b"delivered-old"


# ---------------- 根路径渠道 ----------------


def test_root_flag_beats_env(tmp_path: Path):
    ws = build_ws(tmp_path)
    flag_root, env_root = tmp_path / "flag-dv", tmp_path / "env-dv"
    r = run_deliver(
        ws,
        "--root",
        str(flag_root),
        env_extra={deliver.ENV_ROOT: str(env_root)},
    )
    assert r.returncode == 0, out_text(r)
    assert (flag_root / SID / f"{TITLE} v1.mp4").is_file()
    assert "--root" in r.stdout.split("根来源")[1]  # 来源标记点名 flag 渠道
    assert not env_root.exists()


def test_env_root_used_when_no_flag(tmp_path: Path):
    ws = build_ws(tmp_path)
    env_root = tmp_path / "env-dv"
    r = run_deliver(ws, env_extra={deliver.ENV_ROOT: str(env_root)})
    assert r.returncode == 0, out_text(r)
    assert "env:" in r.stdout.split("根来源")[1]  # 来源标记点名 env 渠道
    assert (env_root / SID / f"{TITLE} v1.mp4").is_file()


def test_env_empty_string_means_unconfigured(tmp_path: Path):
    ws = build_ws(tmp_path)
    r = run_deliver(ws, env_extra={deliver.ENV_ROOT: ""})
    assert r.returncode != 0
    assert "未配置" in out_text(r)


def test_no_root_loud_exit_lists_channels(tmp_path: Path):
    ws = build_ws(tmp_path)
    r = run_deliver(ws)
    assert r.returncode != 0
    assert "--root" in out_text(r) and deliver.ENV_ROOT in out_text(r)


def test_root_expanduser(tmp_path: Path):
    ws = build_ws(tmp_path)
    r = run_deliver(
        ws,
        "--root",
        "~/dv",
        env_extra={"HOME": str(tmp_path), "TO_VIDEO_WORKSPACE": str(ws)},
        cwd=tmp_path,
    )
    assert r.returncode == 0, out_text(r)
    assert (tmp_path / "dv" / SID / f"{TITLE} v1.mp4").is_file()


def test_relative_root_anchors_to_workspace_not_cwd(tmp_path: Path):
    """相对根锚 $W（env 指派的工作区），绝不锚 CWD——本例 CWD 在工作区之外。"""
    ws = build_ws(tmp_path)
    r = run_deliver(
        ws,
        "--root",
        "dv",
        cwd=tmp_path,  # 工作区之外：若锚 CWD，产物会落在 tmp_path/dv 之外
        env_extra={"TO_VIDEO_WORKSPACE": str(ws)},
    )
    assert r.returncode == 0, out_text(r)
    assert (ws / "dv" / SID / f"{TITLE} v1.mp4").is_file()
    assert not (tmp_path / "dv").exists()


def test_root_is_file_exits(tmp_path: Path):
    ws = build_ws(tmp_path)
    f = tmp_path / "not-a-dir"
    f.write_text("x", encoding="utf-8")
    r = run_deliver(ws, "--root", str(f))
    assert r.returncode != 0
    assert "文件而非目录" in out_text(r)


def test_missing_root_dirs_created(tmp_path: Path):
    """root 与系列子目录一并 mkdir -p（首投无需手工建目录）。"""
    ws = build_ws(tmp_path)
    root = tmp_path / "deep" / "dv"
    assert run_deliver(ws, "--root", str(root)).returncode == 0
    assert (root / SID / f"{TITLE} v1.mp4").is_file()


@pytest.mark.skipif(os.geteuid() == 0, reason="root 不受写权限位约束")
def test_root_without_write_permission_exits(tmp_path: Path):
    ws = build_ws(tmp_path)
    root = tmp_path / "dv"
    root.mkdir()
    root.chmod(0o555)
    try:
        r = run_deliver(ws, "--root", str(root))
        assert r.returncode != 0
        assert "写入失败" in out_text(r)
        assert not list(root.rglob("*.part"))
    finally:
        root.chmod(0o755)


def test_root_inside_workspace_outside_episodes_warns(tmp_path: Path):
    """$W 内非 episodes 落点不被 .gitignore 覆盖——必须点名（静默污染 git status）。"""
    ws = build_ws(tmp_path)
    r = run_deliver(ws, "--root", "dv", env_extra={"TO_VIDEO_WORKSPACE": str(ws)})
    assert r.returncode == 0, out_text(r)
    assert "git status" in r.stdout
    assert (ws / "dv" / SID / f"{TITLE} v1.mp4").is_file()


# ---------------- 身份锚（series.json） ----------------


def test_unregistered_episode_exits_with_context(tmp_path: Path):
    ws = build_ws(tmp_path)
    other = ws / "episodes" / "other-video"
    (other / "out").mkdir(parents=True)
    (other / "out" / "final.mp4").write_bytes(b"x")
    r = run_deliver(ws, "--root", str(tmp_path / "dv"), project=str(other))
    assert r.returncode != 0
    assert "未登记" in out_text(r) and SID in out_text(r)  # 系列 id 可见（可诊断）


def test_slug_mismatch_warns_but_delivers(tmp_path: Path):
    data = {
        "seriesList": [
            {
                "id": SID,
                "title": "s",
                "episodes": [
                    {
                        "episode": 1,
                        "slug": "wrong-slug",
                        "title": TITLE,
                        "path": f"episodes/{SLUG}",
                    }
                ],
            }
        ]
    }
    ws = build_ws(tmp_path, series_json=data)
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode == 0, out_text(r)
    assert "不一致" in r.stdout  # WARN 交叉校验
    assert (tmp_path / "dv" / SID / f"{TITLE} v1.mp4").is_file()


def test_two_series_same_path_exits(tmp_path: Path):
    ep = {"episode": 1, "slug": SLUG, "title": TITLE, "path": f"episodes/{SLUG}"}
    data = {
        "seriesList": [
            {"id": "series-a", "title": "a", "episodes": [ep]},
            {"id": "series-b", "title": "b", "episodes": [dict(ep)]},
        ]
    }
    ws = build_ws(tmp_path, series_json=data)
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "命中多条" in out_text(r)


def test_missing_series_json_exits(tmp_path: Path):
    ws = build_ws(tmp_path)
    (ws / "series.json").unlink()
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "series.json" in out_text(r) and "Traceback" not in out_text(r)


def test_bad_series_json_exits_clean(tmp_path: Path):
    ws = build_ws(tmp_path)
    (ws / "series.json").write_text("{not json", encoding="utf-8")
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "合法 JSON" in out_text(r) and "Traceback" not in out_text(r)


def test_empty_title_after_sanitize_exits(tmp_path: Path):
    ws = build_ws(tmp_path, title="   ")
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "清洗后为空" in out_text(r)


def test_series_id_sanitized_for_subdir(tmp_path: Path):
    ws = build_ws(tmp_path, sid="a/b")  # 防御非 kebab-case id
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode == 0, out_text(r)
    assert (tmp_path / "dv" / "a-b" / f"{TITLE} v1.mp4").is_file()


# ---------------- 产物与 dry-run ----------------


def test_missing_final_mp4_exits(tmp_path: Path):
    ws = build_ws(tmp_path)
    (ws / "episodes" / SLUG / "out" / "final.mp4").unlink()
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "final.mp4" in out_text(r)


def test_dry_run_prints_plan_and_writes_nothing(tmp_path: Path):
    ws = build_ws(tmp_path)
    root = tmp_path / "dv"
    before = tree_snapshot(tmp_path)
    r = run_deliver(ws, "--root", str(root), "--dry-run")
    assert r.returncode == 0, out_text(r)
    assert f"{TITLE} v1.mp4" in r.stdout and SID in r.stdout
    assert tree_snapshot(tmp_path) == before  # 零写入（连目录都不建）


def test_dry_run_still_exits_without_root(tmp_path: Path):
    """dry-run 不豁免配置错误（否则排期成功态掩盖未配置事实）。"""
    ws = build_ws(tmp_path)
    r = run_deliver(ws, "--dry-run")
    assert r.returncode != 0
    assert "未配置" in out_text(r)


# ---------------- 评审补钉（对抗式评审 13 项确认发现） ----------------


@pytest.mark.parametrize(
    "raw",
    [
        "[1, 2]",  # 顶层是数组
        '{"seriesList": "oops"}',  # seriesList 是字符串
        '{"seriesList": ["not-an-object"]}',  # 元素是字符串
    ],
)
def test_structurally_malformed_series_json_exits_clean(tmp_path, raw):
    """合法 JSON 但结构畸形：结构门大声退出，不裸 traceback。"""
    ws = build_ws(tmp_path)
    (ws / "series.json").write_text(raw, encoding="utf-8")
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "Traceback" not in out_text(r)


def test_empty_series_list_exits(tmp_path: Path):
    ws = build_ws(tmp_path, series_json={"seriesList": []})
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "无 seriesList" in out_text(r)
    assert "Traceback" not in out_text(r)


def test_null_path_entry_does_not_crash(tmp_path: Path):
    """path 为 null（键在值非字符串）：按无锚处理 → 未登记路径退出，不 TypeError。"""
    data = {
        "seriesList": [
            {
                "id": SID,
                "title": "s",
                "episodes": [
                    {"episode": 1, "slug": SLUG, "title": TITLE, "path": None}
                ],
            }
        ]
    }
    ws = build_ws(tmp_path, series_json=data)
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "Traceback" not in out_text(r)


def test_missing_title_key_exits(tmp_path: Path):
    """条目缺 title 键（与「title 为空白」不同分支）：点名条目大声退出。"""
    data = {
        "seriesList": [
            {
                "id": SID,
                "title": "s",
                "episodes": [{"episode": 1, "slug": SLUG, "path": f"episodes/{SLUG}"}],
            }
        ]
    }
    ws = build_ws(tmp_path, series_json=data)
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "缺 title" in out_text(r)
    assert "Traceback" not in out_text(r)


def test_overlong_title_exits_before_any_write(tmp_path: Path):
    """长度门以组合名为准（含 " vN.mp4.part" 中转段）：82 汉字（246B）组合后
    258B → 大声退出，且在任何 mkdir 之前（归档根零创建）。"""
    ws = build_ws(tmp_path, title="汉" * 82)
    root = tmp_path / "dv"
    r = run_deliver(ws, "--root", str(root))
    assert r.returncode != 0
    assert "超长" in out_text(r)
    assert "Traceback" not in out_text(r)
    assert not root.exists()


def test_title_at_composed_boundary_delivers(tmp_path: Path):
    """81 汉字 = 243B，组合后恰 255B：边界内可交付（钉住「严格大于」语义）。"""
    ws = build_ws(tmp_path, title="汉" * 81)
    root = tmp_path / "dv"
    r = run_deliver(ws, "--root", str(root))
    assert r.returncode == 0, out_text(r)
    assert (root / SID / f"{'汉' * 81} v1.mp4").is_file()


def test_version_like_directory_refused_cleanly(tmp_path: Path):
    """归档目录里存在命中版本模式的**目录**：不抬号、不进 sha1，由 dest.exists()
    复查以「拒绝覆写」干净退出（回归：此前 IsADirectoryError 裸栈）。"""
    ws = build_ws(tmp_path)
    root = tmp_path / "dv" / SID
    root.mkdir(parents=True)
    (root / f"{TITLE} v1.mp4").mkdir()  # 目录占名，任何文件系统形态皆可构造
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "拒绝覆写" in out_text(r)
    assert "Traceback" not in out_text(r)


def test_dry_run_does_not_bypass_read_guards(tmp_path: Path):
    """dry-run 打印的计划必须真实可落地：文件型 root / 占名冲突在 dry-run 即退出
    （与「dry-run 不豁免配置错误」同一原则）。"""
    ws = build_ws(tmp_path)
    f = tmp_path / "not-a-dir"
    f.write_text("x", encoding="utf-8")
    r = run_deliver(ws, "--root", str(f), "--dry-run")
    assert r.returncode != 0
    assert "文件而非目录" in out_text(r)
    root = tmp_path / "dv" / SID
    root.mkdir(parents=True)
    (root / f"{TITLE} v1.mp4").mkdir()
    r = run_deliver(ws, "--root", str(tmp_path / "dv"), "--dry-run")
    assert r.returncode != 0
    assert "拒绝覆写" in out_text(r)


def test_toml_deliver_root_is_not_a_channel(tmp_path: Path):
    """机器属性立法：[deliver] root 写进 toml（曾拟议后否决的渠道）不生效——
    deliver 只认 --root / env TO_VIDEO_DELIVER_ROOT 两渠道。"""
    ws = build_ws(tmp_path)
    (ws / "to-video.toml").write_text(
        '[deliver]\nroot = "elsewhere"\n', encoding="utf-8"
    )
    r = run_deliver(ws)
    assert r.returncode != 0
    assert "未配置" in out_text(r)


# ---------------- 双语：en 槽位与版本号独立 ----------------


def test_scan_versions_suffix_isolates_language_slots():
    """sfx 进 fullmatch：zh/en 版本号互不抬号（"T v1.en.mp4" 不是 "T" 的版本）。"""
    assert deliver.scan_versions(["T v1.en.mp4", "T v2.en.mp4"], "T", ".en") == [
        (1, "T v1.en.mp4"),
        (2, "T v2.en.mp4"),
    ]
    assert deliver.scan_versions(["T v3.mp4"], "T", ".en") == []  # zh 版本不抬 en 号
    assert deliver.scan_versions(["T v3.en.mp4"], "T", "") == []  # en 版本不抬 zh 号
    # sfx 空串与旧口径同构（既有黄金零漂移）
    assert deliver.scan_versions(["T v1.mp4"], "T", "") == [(1, "T v1.mp4")]


def test_en_delivery_names_and_versions_independent(tmp_path: Path):
    """en 命名 `<标题> vN.en.mp4`；先投 en v1 再投 zh v1 共存、zh 升 v2 不动 en。"""
    ws = build_ws(tmp_path)
    out = ws / "episodes" / SLUG / "out"
    root = tmp_path / "dv"
    (out / "final.en.mp4").write_bytes(b"en-A")
    assert run_deliver(ws, "--root", str(root), "--lang", "en").returncode == 0
    assert (root / SID / f"{TITLE} v1.en.mp4").read_bytes() == b"en-A"

    assert run_deliver(ws, "--root", str(root)).returncode == 0  # zh v1
    assert (root / SID / f"{TITLE} v1.mp4").is_file()
    (out / "final.mp4").write_bytes(b"zh-B")
    assert run_deliver(ws, "--root", str(root)).returncode == 0  # zh v2
    assert (root / SID / f"{TITLE} v2.mp4").read_bytes() == b"zh-B"
    # en 侧不受 zh 两次投递影响（版本号独立计号）
    assert (root / SID / f"{TITLE} v1.en.mp4").read_bytes() == b"en-A"
    assert not (root / SID / f"{TITLE} v2.en.mp4").exists()


def test_en_missing_source_hints_render_lang(tmp_path: Path):
    """en 源缺失：报错点名 final.en.mp4 与 `render --final --lang en` 修复路径。"""
    ws = build_ws(tmp_path)
    r = run_deliver(ws, "--root", str(tmp_path / "dv"), "--lang", "en")
    assert r.returncode != 0
    assert "final.en.mp4" in out_text(r)
    assert "render --final --lang en" in out_text(r)


# ---------------- 评审补钉二轮（3 项确认发现） ----------------


@pytest.mark.parametrize("raw", ['"oops"', '{"a": 1}', "null", "3"])
def test_episodes_not_a_list_exits_clean(tmp_path: Path, raw: str):
    """episodes 键非列表（字符串/dict/null/int）：结构门大声退出，不裸 traceback
    （load_series 原只把关 seriesList 形态，episodes 是同族剩下的缺口）。"""
    ws = build_ws(tmp_path)
    (ws / "series.json").write_text(
        f'{{"seriesList": [{{"id": "{SID}", "title": "s", "episodes": {raw}}}]}}',
        encoding="utf-8",
    )
    r = run_deliver(ws, "--root", str(tmp_path / "dv"))
    assert r.returncode != 0
    assert "episodes 应为对象数组" in out_text(r)
    assert "Traceback" not in out_text(r)


@pytest.mark.skipif(os.geteuid() == 0, reason="root 不受读权限位约束")
def test_series_dir_without_read_permission_exits(tmp_path: Path):
    """系列子目录可写不可读（drop-box 型 0300）：版本扫描的 iterdir 即失败——
    与 sha1 读同一环境条件，同样大声退出不裸栈。"""
    ws = build_ws(tmp_path)
    sdir = tmp_path / "dv" / SID
    sdir.mkdir(parents=True)
    sdir.chmod(0o300)
    try:
        r = run_deliver(ws, "--root", str(tmp_path / "dv"))
        assert r.returncode != 0
        assert "列举失败" in out_text(r)
        assert "Traceback" not in out_text(r)
    finally:
        sdir.chmod(0o755)


def test_series_subdir_is_file_exits_including_dry_run(tmp_path: Path):
    """<root>/<系列id> 被文件占名：dry-run 即退出——计划必须真实可落地
    （root-是-文件已有同款守卫，此相邻形态原漏网：dry-run rc=0、实投才炸）。"""
    ws = build_ws(tmp_path)
    root = tmp_path / "dv"
    root.mkdir()
    (root / SID).write_text("x", encoding="utf-8")
    r = run_deliver(ws, "--root", str(root), "--dry-run")
    assert r.returncode != 0
    assert "被文件占名" in out_text(r)
    r = run_deliver(ws, "--root", str(root))
    assert r.returncode != 0
    assert "被文件占名" in out_text(r)
