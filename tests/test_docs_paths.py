"""文档命令的路径锚定执法（双锚点架构：skill 根与工作区根物理分离）。

抽取为独立技能后，机制（skill 仓）与内容（工作区）不再同址，文档里的命令
一律用四变量组合，定义 SSOT 在 references/PIPELINE.md 的路径变量约定节：

  - ``$T`` = skill 根（机制所在，随安装位置变化：``~/.claude/skills/to-video``
    软链 / ``TO_VIDEO_HOME`` / 任意 clone 路径）
  - ``$W`` / ``$P`` / ``$V`` = 工作区根 / 分集工程 / 音色样本目录（内容所在，
    随用户把工作区放在哪变化）

本文件执法三类纪律（方向各不相同）：
  1. 变量定义 SSOT：$T/$W/$P/$V 各自在 references/PIPELINE.md 定义且仅定义一次；
     skills 与 SKILL.md 只引用不定义——重复定义意味着搬迁/改名时要同步 N 处。
  2. 命令锚定：$T 锚定的命令行里不得混入工作区相对字面量（voices/、episodes/
     裸前缀）——$T 是 skill 根，配上工作区相对路径在任何安装位置都不成立
     （混锚）。$W/$P/$V 引用合法。注意 `to-video.toml` 的 tts.ref 与
     series.json 的 path 是工作区根相对的**配置契约**，不是命令，不在受检面。
  3. 散文里的 Markdown 相对链接必须落到 skill 仓内真实文件——AGENTS.md 强制
     可跳转链接；把链接变量化会一次性造出十几条死链。

受检面：references/PIPELINE.md + references/NN-*.md（九篇阶段规格）+ SKILL.md + 根 RSI.md
（自改进协议，散文链接最密集的文档，纳入即受围栏/链接/变量/混锚四类执法）
+ references/MODELING-PLAYBOOK.md（RSI 建模经验沉淀面，条目指针须可跳转）。
references/ 下的手册（VOICE-CLONING.md 等，非 NN- 阶段规格）与根 README（门面）暂不在面内
——根 README 快速上手中的 T=/W=/P= 赋值块是 quickstart 实例化而非第二
定义处；若未来扩面把它纳入，须先为该块设豁免。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from paths import skill_root  # noqa: E402

REFERENCES = skill_root() / "references"
#: 九篇阶段规格（显式 NN- glob：同目录的手册不进变量/混锚规则的受检面）
STAGE_SPECS = "[0-9][0-9]-*.md"
README = REFERENCES / "PIPELINE.md"
SKILL_MD = skill_root() / "SKILL.md"
RSI_MD = skill_root() / "RSI.md"
PLAYBOOK_MD = REFERENCES / "MODELING-PLAYBOOK.md"

FENCE_RE = re.compile(r"^```")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
#: 行内代码跨算「命令」的判据：经典命令调用形态，或直接引用了任何路径变量——
#: 把 $ 变量写进行内跨就意味着它在充当命令（references/06 的命令历史上就写成
#: 行内跨而非围栏块，只扫围栏会漏）。
COMMAND_SPAN_RE = re.compile(r"uv run|\.venv/bin/python|\$[TWPV]\b")

#: 工作区相对字面量的**裸前缀**形态：前一字符是字母/数字/_/$/./-// 时，视为
#: 更长路径的一部分（`$W/voices/…` 合法）；前是空白或引号才是从任何锚点都
#: 拼不上的裸前缀。
WORKSPACE_LITERAL_RE = re.compile(r"(?<![\w$./~-])(?:voices|episodes)/")
#: $T 锚定的命令行：引用了 $T（含 `$T/` 前缀路径）即视为以 skill 根为锚。
T_ANCHORED_RE = re.compile(r"\$T\b")

#: 路径变量定义形态：行首 `X=`（bash 块内赋值；容忍缩进与 = 两侧空格）。
VAR_DEF_RE = re.compile(r"^[ \t]*([TWPV])[ \t]*=", re.MULTILINE)

#: Markdown 链接目标；非 scheme / 纯锚点的都按 skill 仓内相对路径校验。
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
EXTERNAL_LINK_RE = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|#)")


def scanned_docs() -> list[Path]:
    """受检面：README（变量 SSOT）+ 根 RSI.md + 建模手册 + 全部阶段文档 + SKILL.md。"""
    return [
        p
        for p in (
            README,
            SKILL_MD,
            RSI_MD,
            PLAYBOOK_MD,
            *sorted(REFERENCES.glob(STAGE_SPECS)),
        )
        if p.is_file()
    ]


def command_lines(text: str) -> list[tuple[int, str]]:
    """→ [(行号, 命令文本)]：围栏块内行（反斜杠续行并成一条）+ 行内命令跨。

    续行拼接承自旧版判据：`--ref voices/x.wav` 这类尾巴常被换行切开，按单行
    判定会漏混锚；拼接后按整条命令检查，行号锚定首行。
    """
    lines = text.split("\n")
    out: list[tuple[int, str]] = []
    inside = False
    i = 0
    while i < len(lines):
        first = i + 1
        line = lines[i]
        if FENCE_RE.match(line):
            inside = not inside
            i += 1
            continue
        if inside:
            joined = line
            while (
                joined.rstrip().endswith("\\")
                and i + 1 < len(lines)
                and not FENCE_RE.match(lines[i + 1])
            ):
                i += 1
                joined = joined.rstrip().rstrip("\\") + " " + lines[i]
            out.append((first, joined))
        else:
            for m in INLINE_CODE_RE.finditer(line):
                if COMMAND_SPAN_RE.search(m.group(1)):
                    out.append((first, m.group(1)))
        i += 1
    return out


def prose_links(text: str) -> list[tuple[int, str]]:
    """→ [(行号, 链接目标)]：围栏块**外**的 Markdown 链接（块内是示例非链接）。"""
    out: list[tuple[int, str]] = []
    inside = False
    for i, line in enumerate(text.split("\n"), 1):
        if FENCE_RE.match(line):
            inside = not inside
            continue
        if not inside:
            out += [(i, m.group(1)) for m in MD_LINK_RE.finditer(line)]
    return out


def test_fences_are_balanced():
    """悬空围栏会把正文困进代码块、吞掉后续命令行——本仓系有过同类事故
    （Perceives 切片相位错位）；它同时会腐蚀本文件的两类提取器。"""
    for p in scanned_docs():
        n = sum(
            1
            for line in p.read_text(encoding="utf-8").split("\n")
            if FENCE_RE.match(line)
        )
        assert n % 2 == 0, f"{p.name}: 围栏数 {n} 为奇数（悬空围栏）"


def test_path_variables_defined_exactly_once_in_readme():
    """判据 1（SSOT 正向）：$T/$W/$P/$V 在 references/PIPELINE.md 各定义恰好一次。

    「机制在哪、内容在哪」两个事实只在 README 落一次，其余文档全部引用；
    重复定义意味着搬迁/改名时要同步 N 处——上次迁移正是靠 N 处未同步暴露的。
    """
    readme = README.read_text(encoding="utf-8")
    defined = [m.group(1) for m in VAR_DEF_RE.finditer(readme)]
    for var in "TWPV":
        n = defined.count(var)
        assert n == 1, (
            f"references/PIPELINE.md 里 `${var}=` 定义出现 {n} 次（应恰好 1 次）——"
            "路径变量约定是文档 SSOT，缺失请补定义，重复请去重"
        )


def test_only_readme_defines_path_variables():
    """判据 1（SSOT 反向）：skills 与 SKILL.md 只引用不定义。"""
    for p in scanned_docs():
        if p == README:
            continue
        hits = [m.group(1) for m in VAR_DEF_RE.finditer(p.read_text(encoding="utf-8"))]
        assert not hits, (
            f"{p.name}: 自行定义路径变量 {hits} —— 定义 SSOT 在"
            " references/PIPELINE.md，消费者只引用"
        )


def test_t_anchored_commands_carry_no_workspace_literals():
    """判据 2b（混锚禁令·反向）：$T 锚定的命令不得带工作区相对字面量。

    $T 是 skill 根（机制），voices/、episodes/ 是工作区根相对（内容）——组合
    出的路径在任何安装位置都不成立；样本/分集路径一律 $V/$P/$W。裸前缀判定
    放行 `$W/voices/…` 这类作为 $W 路径组成部分的写法。
    """
    offenders: list[str] = []
    for p in scanned_docs():
        for lineno, cmd in command_lines(p.read_text(encoding="utf-8")):
            if not T_ANCHORED_RE.search(cmd):
                continue
            for m in WORKSPACE_LITERAL_RE.finditer(cmd):
                offenders.append(f"{p.name}:{lineno}  `{m.group(0)}…` ← {cmd.strip()}")
    assert not offenders, (
        "$T 锚定的命令混入工作区相对字面量（样本/分集路径改用 $V/$P/$W）：\n  "
        + "\n  ".join(offenders)
    )


def test_relative_links_resolve():
    """判据 3：散文相对链接必须落到 skill 仓内真实文件（可跳转性）。"""
    offenders: list[str] = []
    for p in scanned_docs():
        for lineno, target in prose_links(p.read_text(encoding="utf-8")):
            if EXTERNAL_LINK_RE.match(target):
                continue
            rel = target.split("#", 1)[0]
            if rel and not (p.parent / rel).exists():
                offenders.append(f"{p.name}:{lineno}  {target}")
    assert not offenders, (
        "相对链接目标不存在（skill 内链接须可跳转）：\n  " + "\n  ".join(offenders)
    )


# ---- 用户可见文案 ↔ 工具面一致性（RSI-005 / RSI-006）----
#
# 门的报错指引与脚手架的「下一步」提示是用户照做的命令——它们与机制面漂移时，
# 使用者先在错误路径上找工具。两类实测漂移：指引点名的脚本根本不存在
# （RSI-006：scripts/archify_types.py），以及提示教人加一个会弄坏安装的参数
# （RSI-005：--ignore-workspace，ISSUE-175 后已作废但 scaffold 结尾仍在打印）。

SCRIPTS = skill_root() / "scripts"
TEMPLATES = skill_root() / "assets"
_TEMPLATE_TEXT = {".md", ".tmpl", ".toml", ".txt", ".py", ".yaml", ".ts", ".tsx"}
#: `scripts/xxx.py` 指名（注释与字符串都算——都是给人看的指引）。前缀不限：
#: `$T/scripts/x.py` 是文案里的主流写法，排除 `/` 前缀会漏掉绝大多数。
_SCRIPT_REF_RE = re.compile(r"(?<!\w)scripts/([a-z_][a-z0-9_]*\.py)")
#: 把 `--ignore-workspace` 当命令参数给出的形态；`[\s#]` 跨过换行与注释续行符
#: （skeleton.toml 注释曾把这条命令断在两行，逐行扫描因此漏检）。
_IGNORE_WS_CMD_RE = re.compile(r"pnpm install[\s#]+--ignore-workspace")
#: 同一 flag 的 .npmrc 配置形态：pnpm ≥11 不从 .npmrc 读它（实测 11.25.0 / 12.2.1
#: `pnpm config get ignore-workspace` 恒 undefined），写了只会误导隔离机制的归属。
_IGNORE_WS_NPMRC_RE = re.compile(r"^\s*ignore-workspace\s*=", re.M)


#: Remotion 工具经 npx 调用（07 规格：一律 ./node_modules/.bin/ 直调，防 workspace 污染）。
_NPX_TOOL_RE = re.compile(r"\bnpx\s+(?:tsc|remotion)\b")
#: 已不存在的旧布局路径（RSI-009 起 pipeline/ 目录整体移除，任何指回都是死路径；
#: docs/quickstart 已迁 assets/）；前一字符不许是词字符或 -，但**不排除 /**
#: （`$T/…` 命令与本仓 blob 外链都以 / 起头），只放过上游
#: apps/negentropy-influence/pipeline/… 的历史外链。另拦省略 pipeline/ 前缀的
#: `templates/<子目录>` 与 `skills/NN` 简写（脚本注释的惯用写法）。
_LEGACY_PATH_RE = re.compile(
    r"(?<![\w-])(?<!negentropy-influence/)"
    r"(?:pipeline/[A-Za-z0-9_.-]+|docs/quickstart)"
    r"|(?<![\w-])(?<!pipeline/)(?:templates/(?:video-skeleton|workspace)|skills/\d\d)"
)


def _rel(f: Path) -> Path:
    root = skill_root()
    return f.relative_to(root) if f.is_relative_to(root) else f


def user_facing_files() -> list[Path]:
    """用户照做的文案面：机制脚本（门报错 / 脚手架提示）、规格与门面文档、模板
    （含注释——scaffold 原样复制，新集作者会读）。"""
    templates = sorted(
        p
        for p in TEMPLATES.rglob("*")
        if p.is_file() and p.suffix in _TEMPLATE_TEXT and "node_modules" not in p.parts
    )
    return (
        sorted(SCRIPTS.glob("*.py"))
        + sorted(REFERENCES.glob(STAGE_SPECS))
        + [README, SKILL_MD, RSI_MD, PLAYBOOK_MD]
        + templates
    )


def test_script_references_resolve():
    """文案里点名的 scripts/*.py 必须真实存在（RSI-006 幽灵脚本回归）。

    分集侧薄包装（build_narration/tts/qa_frames）与 skill 同名，同样落在
    scripts/ 下，故判据统一为「该名在 skill 的 scripts 目录存在」。"""
    have = {p.name for p in SCRIPTS.glob("*.py")}
    missing = []
    for f in user_facing_files():
        for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for name in _SCRIPT_REF_RE.findall(line):
                if name not in have:
                    missing.append(f"{_rel(f)}:{lineno} → scripts/{name}")
    assert not missing, "点名了不存在的脚本（用户会照着找）：\n  " + "\n  ".join(
        missing
    )


def test_no_instruction_to_add_ignore_workspace():
    """用户可见文案不得教人加 `--ignore-workspace`（RSI-005）。

    分集 video/ 已入库 pnpm-workspace.yaml 自锚；pnpm ≥12 加该参数会把工程自身
    workspace 一并忽略 → ERR_PNPM_IGNORED_BUILDS。允许「勿加 / 不要加」式的
    警示说明，只拦把它当命令参数给出的形态（含跨行断开的注释），以及模板
    .npmrc 里的同名死配置。"""
    offenders = []
    for f in user_facing_files():
        text = f.read_text(encoding="utf-8")
        for m in _IGNORE_WS_CMD_RE.finditer(text):
            lineno = text.count("\n", 0, m.start()) + 1
            offenders.append(f"{_rel(f)}:{lineno}")
    for f in sorted(TEMPLATES.rglob(".npmrc")):
        text = f.read_text(encoding="utf-8")
        for m in _IGNORE_WS_NPMRC_RE.finditer(text):
            offenders.append(f"{_rel(f)}:{text.count(chr(10), 0, m.start()) + 1}")
    assert not offenders, "文案仍在教人加 --ignore-workspace：\n  " + "\n  ".join(
        offenders
    )


def current_docs_and_code() -> list[Path]:
    """现行文案面 = 用户照做面 + references/ 全部手册 + 根 README + mermaid 图源
    （首行 `%% source:` 指回文档章节）+ docs/research（设计依据文档，编号对齐后
    `skills/NN` 简写会被误读为同号新规格）。frozen 档不再豁免：2.0.0 起模板即唯一
    事实源（RSI-009），陈旧注释一律清到现行路径。issue 台账与 CHANGELOG 是历史
    记录，不在面内。"""
    docs = skill_root() / "docs"
    files = {
        *user_facing_files(),
        *REFERENCES.glob("*.md"),
        skill_root() / "README.md",
        *(docs / "assets" / "mermaid").glob("*.mmd"),
        *(docs / "research").glob("*.md"),
    }
    return sorted(files)


def test_no_npx_for_remotion_tools():
    """RSI-008：SKILL.md 快速通道曾教 `npx tsc --noEmit`，与 07 命令闭环矛盾。"""
    offenders = [
        f"{_rel(f)}:{no}"
        for f in current_docs_and_code()
        for no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
        if _NPX_TOOL_RE.search(line)
    ]
    assert not offenders, "文案教人用 npx 调 tsc/remotion：\n  " + "\n  ".join(
        offenders
    )


@pytest.mark.parametrize(
    ("line", "legacy"),
    [
        ("见 pipeline/skills/06", True),
        ("`$T/pipeline/VOICE-CLONING.md` §3.3", True),
        ("[x](https://github.com/o/to-video/blob/main/pipeline/templates/x)", True),
        ("cp $T/docs/quickstart/P0.tsx", True),
        ("[x](../pipeline/stages.toml)", True),
        ("%% source: pipeline/VOICE-CLONING.md — §一", True),
        ("必须与 templates/video-skeleton 一致", True),
        ("skill 只带 templates/workspace/voices/", True),
        ("见 skills/06 清单", True),
        ("apps/negentropy-influence/pipeline/skills/06-x.md", False),
        ("apps/negentropy-influence/pipeline/templates/workspace/x", False),
        ("$T/pipeline/scripts/tts.py", True),
        ("映射见 pipeline/README.md", True),
        ("assets/video-skeleton/skeleton.toml", False),
        ("ln -s <目录> ~/.claude/skills/to-video", False),
    ],
)
def test_legacy_path_detector_forms(line, legacy):
    """检测器自检：`/` 起头的 `$T` 命令与本仓 blob 外链、省略 pipeline/ 前缀的
    简写曾被漏检（RSI-008 复核；RSI-009 起 pipeline/ 整体入拦）。"""
    assert bool(_LEGACY_PATH_RE.search(line)) is legacy


def test_no_legacy_layout_paths():
    """pipeline/ 布局已整体移除（RSI-009），现行文案不得再指向它（含简写）。"""
    offenders = [
        f"{_rel(f)}:{no} → {m.group(0)}"
        for f in current_docs_and_code()
        for no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
        for m in _LEGACY_PATH_RE.finditer(line)
    ]
    assert not offenders, "文案仍指向已删除的旧布局路径 pipeline/：\n  " + (
        "\n  ".join(offenders)
    )


#: 指向 PIPELINE.md 具名章节的指针（如 `§五「双语渲染」`、`「环境变量」`）；
#: 窗口不跨句读，免得把同句后文的引号误当节名。
_PIPELINE_SECTION_REF_RE = re.compile(
    r"PIPELINE\.md[^「」，。；\n]{0,12}「([^」\n]+)」"
)


def test_pipeline_section_refs_resolve():
    """具名章节指针须落到 PIPELINE.md 真实标题（RSI-009 评审：09 规格曾指向不存在的
    「字体可复现性」节——该事实条在 07；链接可达门只验文件，不验节名）。"""
    headings = [
        ln
        for ln in README.read_text(encoding="utf-8").splitlines()
        if ln.startswith("#")
    ]
    checked, dangling = 0, []
    for f in current_docs_and_code():
        for no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in _PIPELINE_SECTION_REF_RE.finditer(line):
                checked += 1
                if not any(m.group(1) in h for h in headings):
                    dangling.append(f"{_rel(f)}:{no} → 「{m.group(1)}」")
    assert checked, "未扫到任何 PIPELINE.md 具名章节指针（检测器失效？本门不得空转）"
    assert not dangling, "指向 PIPELINE.md 不存在的章节：\n  " + "\n  ".join(dangling)
