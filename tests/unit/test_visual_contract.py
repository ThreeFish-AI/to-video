"""Visual Lock 扩展的解析兼容性回归。"""

from pathlib import Path

from check_archify_coverage import parse_storyboard_visual
from check_script import parse_motion_tags, parse_storyboard


def write_storyboard(path: Path, extra_column: bool) -> None:
    header = (
        "| 镜 | 句区间 | 画面 | 动效 | Visual Lock |\n"
        if extra_column
        else "| 镜 | 句区间 | 画面 | 动效 |\n"
    )
    separator = "|---|---|---|---|---|\n" if extra_column else "|---|---|---|---|\n"
    row = (
        "| 0-A | p0-01..02 | **装置** | @stagger | 参考: `ref.png`; "
        "保持: 轮廓与青色节点; 禁止: 新增人物 |\n"
        if extra_column
        else "| 0-A | p0-01..02 | **装置** | @stagger |\n"
    )
    path.write_text("# 分镜\n\n" + header + separator + row, encoding="utf-8")


def test_visual_lock_column_preserves_existing_parsers(tmp_path: Path):
    legacy = tmp_path / "legacy.md"
    locked = tmp_path / "locked.md"
    write_storyboard(legacy, extra_column=False)
    write_storyboard(locked, extra_column=True)

    assert parse_storyboard(locked) == parse_storyboard(legacy)
    assert parse_storyboard_visual(locked) == parse_storyboard_visual(legacy)
    assert parse_motion_tags(locked) == parse_motion_tags(legacy)


def test_visual_lock_is_optional_and_keeps_visual_text_in_the_same_column(
    tmp_path: Path,
):
    board = tmp_path / "locked.md"
    write_storyboard(board, extra_column=True)

    assert parse_storyboard_visual(board) == [("0-A", " **装置** ")]
    assert parse_motion_tags(board) == [("0-A", "stagger")]
