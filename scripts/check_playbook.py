#!/usr/bin/env python3
"""动效画面建模手册（references/MODELING-PLAYBOOK.md）的体量与结构门。

手册是 RSI「建模经验分支」的沉淀面：制片中被认可/否决的建模方法逐集回流。
回流天然单调增长，而长上下文会稀释模型对中段内容的利用（context rot）——
故本模块是**预算与条目规则的唯一实现**，协议散文（RSI.md）只引用常量名不抄数字。

三道约束：
  1. **总量水位**（滞回，仿 kswapd / Elasticsearch 磁盘水位）：
     字数 ≥ HIGH 出 WARN（须按 RSI.md 压缩阶梯压至 ≤ TARGET），> CAP 为 ERROR。
     触发线与目标线分开，是为了一次压缩换来数集的增长余量，不在每次追加时抖动。
  2. **条目原子化**：单行 bullet、固定字段、单条字数上限——条目化才能增量合并；
     整体重写会让上下文坍缩（ACE 实测 18,282→122 tokens，准确率跌破无适应基线）。
  3. **权重生命周期**（仿 ExpeL）：w 为正整数，w≤0 必须移出；定式须过
     PROMOTE_W / PROMOTE_EPISODES 双门槛——单集孤证只能是试行，防主 Agent 自我强化。

计数口径（确定性，同 UAX #29 对表意字逐字断词的语义）：汉字/假名/谚文每字 1，
拉丁/数字词（含 `-_.'` 连接）每词 1；标点、空白、Markdown 符号计 0；链接目标与
裸 URL 不计——指针鼓励引用而非复制（SSOT）。

用法（任意目录）：uv run --no-project $T/scripts/check_playbook.py [手册路径]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402 - SKILL 模块级解析；本门不触碰 WORKSPACE

PLAYBOOK = paths.SKILL / "references" / "MODELING-PLAYBOOK.md"

#: 硬上限（与 SKILL.md 同量级：一次读入成本可控，约容 30 条方法/反模式）
CAP = 3000
#: 压缩触发线（0.9·CAP）
HIGH = 2700
#: 压缩目标线（0.75·CAP）：HIGH−TARGET 的余量约容 4–5 条新条目
TARGET = 2250
#: 单条上限：方法 / 反模式 / 候选
M_MAX, X_MAX, C_MAX = 120, 60, 80
#: 晋升定式门槛（w 下限 / 证覆盖集数）与每条证锚点上限
PROMOTE_W, PROMOTE_EPISODES, MAX_ANCHORS = 3, 2, 2

SECTIONS = ("建模方法", "反模式", "候选区")

M_ENTRY_RE = re.compile(
    r"^- \*\*\[(M-\d{3})\] ([^*]+)\*\*〔(试行|定式)·w(-?\d+)〕(.+)$"
)
X_ENTRY_RE = re.compile(r"^- \*\*\[(X-\d{3})\] ([^*]+)\*\*〔w(-?\d+)〕(.+)$")
#: 候选：`〔+用户〕`认可 /`〔-用户〕`否决 /`〔+主〕`主 Agent 自评（弱信号只认可、不否决）；
#: 正负号兼收 ASCII、U+2212 与全角，免得手打字符不同被误拒。锚点须指向具体镜。
C_ENTRY_RE = re.compile(
    r"^- 〔(?:[+＋](?:用户|主)|[-−－]用户)〕([a-z0-9][a-z0-9-]*#[^：\s]+)：.+$"
)

#: 字段表（元组序即书写序）与必填集
M_FIELDS, M_REQUIRED = ("当", "故", "非", "验", "据", "证"), {"当", "故", "验", "证"}
X_FIELDS, X_REQUIRED = ("忌", "因", "验", "证"), {"忌", "证"}
FIELD_RE = re.compile(r"^(\S)：(.+)$")
#: 字段只在「。键：」处切分——「当」常引旁白原句，引号内的句号不得误切
FIELD_SPLIT_RE = re.compile(r"。(?=[当故非验据证忌因]：)")
#: 证锚点：`<集目录名>[#镜号]（YYYY-MM）`，以「、」分隔
ANCHOR_RE = re.compile(r"^([a-z0-9][a-z0-9-]*)(?:#[^（）、\s]+)?（\d{4}-\d{2}）$")

_LINK_TARGET_RE = re.compile(r"\]\([^)]*\)")
#: URL 只吃 RFC 3986 字符集——`\S+` 会把紧跟其后的整段中文一并吞掉而漏计
_URL_RE = re.compile(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+")
_CJK_RE = re.compile(
    r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff]"
)
_WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-_.'][A-Za-z0-9]+)*")


def count_units(text: str) -> int:
    """→ 字数（口径见模块文档）。"""
    t = _URL_RE.sub("", _LINK_TARGET_RE.sub("]", text))
    return len(_CJK_RE.findall(t)) + len(_WORD_RE.findall(t))


def _check_fields(
    eid: str, body: str, order: tuple[str, ...], required: set[str], errors: list
) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in (p.strip() for p in FIELD_SPLIT_RE.split(body.rstrip("。"))):
        if not part:
            continue
        m = FIELD_RE.match(part)
        if not m or m.group(1) not in order:
            errors.append(
                f"{eid}：无法识别的字段「{part[:12]}」（合法键 {'/'.join(order)}）"
            )
            continue
        if m.group(1) in fields:
            errors.append(f"{eid}：字段「{m.group(1)}」重复")
        fields[m.group(1)] = m.group(2)
    if missing := required - fields.keys():
        errors.append(f"{eid}：缺必填字段 {'/'.join(k for k in order if k in missing)}")
    keys = [k for k in order if k in fields]
    if list(fields) != keys:
        errors.append(f"{eid}：字段须按 {'→'.join(order)} 顺序书写")
    return fields


def _anchor_slugs(eid: str, evidence: str | None, errors: list) -> set[str]:
    if evidence is None:
        return set()
    anchors = evidence.split("、")
    if len(anchors) > MAX_ANCHORS:
        errors.append(f"{eid}：证锚点至多 {MAX_ANCHORS} 个（保留最新且分属不同集者）")
    slugs = set()
    for a in anchors:
        if m := ANCHOR_RE.match(a.strip()):
            slugs.add(m.group(1))
        else:
            errors.append(f"{eid}：证锚点「{a}」不符 `<集目录名>[#镜号]（YYYY-MM）`")
    return slugs


def check(text: str) -> tuple[int, list[str], list[str], dict[str, int]]:
    """→ (字数, errors, warnings, 各节条目数)。"""
    errors: list[str] = []
    warnings: list[str] = []
    counts = dict.fromkeys(SECTIONS, 0)
    units = count_units(text)

    if any(line.startswith("```") for line in text.splitlines()):
        errors.append(
            "手册禁用围栏代码块（代码归 motifs.tsx / 模板组件，此处只写方法）"
        )

    heads = re.findall(r"^(#{2,}) (.+)$", text, re.MULTILINE)
    if [h for lvl, h in heads if lvl == "##"] != list(SECTIONS) or any(
        lvl != "##" for lvl, _ in heads
    ):
        errors.append(f"二级标题须恰为 {' / '.join(SECTIONS)}（依序、无其他小节）")

    section = None
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    last_rank: dict[str, tuple[bool, int]] = {}
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            continue
        if section not in SECTIONS or not line.strip():
            continue
        if section == "候选区":
            counts[section] += 1
            if not C_ENTRY_RE.match(line):
                errors.append(
                    f"候选格式不符 `- 〔+用户|-用户|+主〕<集目录名>#<镜号>：…`：{line[:24]}"
                )
            elif (n := count_units(line)) > C_MAX:
                errors.append(f"候选超单条上限 {n}>{C_MAX}：{line[:24]}")
            continue

        is_m = section == "建模方法"
        m = (M_ENTRY_RE if is_m else X_ENTRY_RE).match(line)
        if not m:
            errors.append(f"{section}：非条目行（节内只许单行条目）：{line[:24]}")
            continue
        counts[section] += 1
        eid, name = m.group(1), m.group(2).strip()
        status = m.group(3) if is_m else None
        w, body = int(m.group(m.lastindex - 1)), m.group(m.lastindex)
        for key, seen, label in ((eid, seen_ids, "编号"), (name, seen_names, "名称")):
            if key in seen:
                errors.append(f"{eid}：{label}「{key}」重复（同键须合并）")
            seen.add(key)
        if w <= 0:
            errors.append(f"{eid}：w={w}≤0，须移出手册（git 历史即冷档）")
        rank = (status == "定式", w)  # 定式优先，同档按 w 降序
        if section in last_rank and rank > last_rank[section]:
            errors.append(f"{eid}：节内须定式在前、同档按 w 非增排列（高价值置顶）")
        last_rank[section] = rank
        cap = M_MAX if is_m else X_MAX
        if (n := count_units(line)) > cap:
            errors.append(f"{eid}：超单条上限 {n}>{cap}")
        fields = _check_fields(
            eid,
            body,
            M_FIELDS if is_m else X_FIELDS,
            M_REQUIRED if is_m else X_REQUIRED,
            errors,
        )
        slugs = _anchor_slugs(eid, fields.get("证"), errors)
        if status == "定式" and (w < PROMOTE_W or len(slugs) < PROMOTE_EPISODES):
            errors.append(
                f"{eid}：定式须 w≥{PROMOTE_W} 且证覆盖 ≥{PROMOTE_EPISODES} 集"
                f"（现 w={w}、{len(slugs)} 集）"
            )

    if units > CAP:
        errors.append(f"总字数 {units} > CAP {CAP}：先按 RSI.md 压缩阶梯压至 ≤ TARGET")
    elif units >= HIGH:
        warnings.append(
            f"总字数 {units} ≥ HIGH {HIGH}：须按 RSI.md 压缩阶梯压至 ≤ {TARGET}"
        )
    return units, errors, warnings, counts


def main(argv: list[str]) -> int:
    path = Path(argv[0]) if argv else PLAYBOOK
    if not path.is_file():
        print(f"FAIL: 手册不存在 {path}", file=sys.stderr)
        return 1
    units, errors, warnings, counts = check(path.read_text(encoding="utf-8"))
    for m in errors:
        print(f"  ERROR {m}")
    for m in warnings:
        print(f"  WARN  {m}")
    print(
        f">> 建模手册 · {units}/{CAP} 字（HIGH {HIGH} · TARGET {TARGET}）· "
        + " / ".join(f"{k} {v}" for k, v in counts.items())
        + f" · ERROR {len(errors)} · WARN {len(warnings)}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
