#!/usr/bin/env python3
"""从 narration.md 解析生成 narration.json（逐句：id/scene/text[/ttsText]）——公共管线版本。

narration.md 是单一事实源；本脚本是纯派生转换，不做任何内容改写。
适用于任何 `episodes/*-video/` 科普视频工程（目录约定见 references/PIPELINE.md）。

派生产物两件：narration.json（逐句）与 video/src/chapters.json（逐幕标题——
`## Pn 标题` 的标题文字此前被丢弃，现为顶部分段进度条的数据面）。

**双语构建（--lang，RSI-004）**：主语言 zh 解析 narration.md；en 解析
narration.en.md（同一套 LINE_RE/SCENE_RE，字段同构）并过**硬对齐门**——句 id
序列 / 幕归属 / 幕集合与主稿逐一相等（缺句 / 多句 / 乱序 / 换幕分别点名），
1:1 对齐是复用分镜与场景代码的前提。en 构建成功即写**基线锁**
narration.en.lock.json（`{句id: {"zh": 主稿句 digest, "en": 译句 digest}}`）：记录
「翻译时主稿长什么样」，主稿事后改稿 ⇒ check_script --lang en 可测出译稿失鲜。
锁合并取 gettext msgmerge 的 fuzzy 语义（见 merge_lock）：重建**不会**自动接受
改过的主稿——只有译句改过（重译）或 `--accept` 点名的句才刷新，否则缺省
`build` 先 zh 后 en 的顺序会在 check 之前把失鲜信号抹掉。
chapters.json 只有一份：zh / en 两种构建产出同一文件，en 幕标题在本集声明
narration.langs 后附进条目 i18n 键（en 文件缺失/解析失败降级 WARN，zh 构建
永不为 en 文件失败）。

**发音标注的正交拆分**：逐字稿里可内联 `<原文|读音>` 标注（多音字/英文专名，语法见
[pron_marks.py](./pron_marks.py)）。本脚本据此派生两个字段：

  text     剥离标注后的**人读文本** —— 同时被字幕（captions.py）与时长预算
           （check_script.py）消费，因此绝不能含标注，否则标注会漏进 SRT/VTT
           并污染字数口径；
  ttsText  原始带标注文本，**仅当该句含标注时才写入** —— tts.py 优先取它送合成。

未标注的句子不产生 ttsText 字段，取值与历史完全一致 ⇒ 存量缓存摘要不失效。
标注本身携带原字，故一处书写即可派生两者，不存在两份副本漂移。

用法：uv run --no-project $T/scripts/build_narration.py --project $P [--lang zh|en]
     工程内薄包装等价于：uv run --no-project scripts/build_narration.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config  # noqa: E402 - 同目录模块，须在 sys.path 注入之后
import langs  # noqa: E402
from pron_marks import (  # noqa: E402
    PRON_MARK_RE,
    has_marks,
    load_vocab,
    strip_marks,
    validate,
)

LINE_RE = re.compile(r"^- \[(?P<id>[a-z0-9-]+)\]\s+(?P<text>.+)$")
#: 幕标题文字此前被丢弃；现为顶部分段进度条（ChapterProgress）的数据面，
#: 经 emit_chapters 落盘 video/src/chapters.json。分隔符类兼容 `## P2 标题` /
#: `## P2：标题` / `## P2`（空标题）三种写法。
SCENE_RE = re.compile(r"^## (?P<scene>P\d+)\b[\s:：—\-·]*(?P<title>.*)$")
FORMAT_DOC = "references/PIPELINE.md 第二节格式契约"

#: pinyin.vocab 在 index-tts checkout 内（不在 skill）。根目录可经
#: TO_VIDEO_INDEX_TTS_ROOT 覆盖（默认 ~/tools/index-tts）。存在则用于 WARN 级「音节是否在表内」，
#: 缺失时格式类 ERROR 仍然生效（规则内联在 pron_marks.py，不依赖该文件）。
PINYIN_VOCAB = (
    Path(os.environ.get("TO_VIDEO_INDEX_TTS_ROOT", "~/tools/index-tts")).expanduser()
    / "checkpoints"
    / "pinyin.vocab"
)


def parse_md(
    src: Path, vocab: frozenset[str] | None
) -> tuple[
    list[dict[str, str]],
    dict[str, str],
    list[str],
    list[str],
    list[str],
    int,
]:
    """解析一份逐字稿（zh 主稿与 en 译稿共用同一套 LINE_RE/SCENE_RE）。

    → (items, scene_titles, 结构错, 标注错, 标注WARN, 带标注句数)。本函数不退出：
    错误分类交还调用方决定语义——构建目标（主稿或译稿本体）硬失败，chapters 的
    i18n 容错收集（collect_scene_i18n）降级 WARN。en 译稿文件的结构规则与 zh
    完全同构（句 id 幕前缀等），对齐差异归 check_alignment 点名。
    """
    scene = ""
    scene_titles: dict[str, str] = {}
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    struct_errors: list[str] = []
    mark_errors: list[str] = []
    mark_warnings: list[str] = []
    marked = 0
    for lineno, raw in enumerate(src.read_text(encoding="utf-8").splitlines(), 1):
        if m := SCENE_RE.match(raw):
            scene = m.group("scene")
            # 插入序即章节序；重号幕保留首个（与句子归属的首次生效口径一致）
            scene_titles.setdefault(scene, m.group("title").strip())
            continue
        if m := LINE_RE.match(raw):
            sid, text = m.group("id"), m.group("text").strip()
            if not scene:
                # 幕名为空时下一条校验会报出「与所在幕  不一致」这种令人困惑的信息，
                # 故先明确指出真正的原因：首句之前缺 `## Pn` 标题。
                struct_errors.append(
                    f"{src}:{lineno} 句 {sid} 出现在任何 `## Pn` 分幕标题之前 —— 每句必须归属于某一幕，见 {FORMAT_DOC}"
                )
                continue
            if sid in seen:
                struct_errors.append(f"{src}:{lineno} 重复句 id: {sid}")
                continue
            if not sid.startswith(scene.lower() + "-"):
                struct_errors.append(
                    f"{src}:{lineno} 句 id {sid} 与所在幕 {scene} 不一致 —— "
                    f"句 id 必须以幕名小写为前缀（应为 {scene.lower()}-…）"
                )
                continue
            seen.add(sid)
            # 发音标注：先校验（标注错 = 必然读错，上游丢弃原字、无字形兜底），
            # 再派生「人读 text」与「送合成 ttsText」
            errs, warns = validate(text, vocab)
            mark_errors += [f"{src}:{lineno} 句 {sid} {e}" for e in errs]
            mark_warnings += [f"{src}:{lineno} 句 {sid} {w}" for w in warns]
            item: dict = {
                "id": sid,
                "scene": scene,
                "text": strip_marks(text),
            }
            if has_marks(text):
                item["ttsText"] = text
                marked += 1
            items.append(item)
    return items, scene_titles, struct_errors, mark_errors, mark_warnings, marked


# ---------------- 配音台本（story 档）：script/narration.cues.toml ----------------
#
# 可选 sidecar，写稿阶段与 narration.md 一同产出（references/03 规约）：
#   [block.<句id>] emo = "afraid:0.18,surprised:0.12"（可选 alpha=0.35）
#       —— 该 id 是一个故事块的起点；块内情绪由 tts.py 归一后使用（§4.5）。
#   [say] <句id> = "…表演标点版…" —— 仅合成文本（ttsText），字幕取 text 不变；
#       校验「去标点后与 text 全等、发音标注逐个原样」，改字必须回 narration.md 改。
#   [take] <句id> = N —— take 验收的重掷：该句所在块种子 +N（1–999），只重录这一块；
#       定稿值留在台本即 canonical（块模式的 §5.4 口径）。
# 无该文件 ⇒ narration.json 与今日逐字节一致（存量集零波及）；en 构建不消费台本
# （story 档 EN 回退逐句）。
#: 「只许改标点」的比较口径，按标点**串**整体判定（逐字符判定会被 `3……5` 绕过）：
#: 不夹在两数字之间 ⇒ 剥掉；夹在两数字之间且恰为单个半角 `.,:` ⇒ 数值/时刻的一部分
#: （3.5%、1,200、10:30），原样保留；夹在两数字之间的其余标点 ⇒ 归一为分隔符（「2020，2026」
#: 改「2020…2026」仍放行）。后两条保证 say 删小数点、往数字串里插 `，` 或删掉两数之间的
#: 标点都比对不上——否则合成念成另一个数
CUES_PUNCT_RE = re.compile(r"[，。！？…、；：;!?.,:]+")


def _strip_punct(s: str) -> str:
    def repl(m: re.Match[str]) -> str:
        a, b = m.start(), m.end()
        if not (a and s[a - 1].isdecimal() and b < len(s) and s[b].isdecimal()):
            return ""
        return m.group() if m.group() in (".", ",", ":") else "\x1f"

    return CUES_PUNCT_RE.sub(repl, s)


def apply_cues(root: Path, items: list[dict]) -> tuple[int, int, list[str]]:
    """读 cues.toml 并落进 items → (块数, say 句数, 错误列表)。无文件 → (0,0,[])。"""
    cues_path = root / "script" / "narration.cues.toml"
    if not cues_path.is_file():
        return 0, 0, []
    import tomllib

    from tts import parse_emo_vector  # noqa: E402 - 兄弟模块 SSOT 复用（语法校验单一口径）

    try:
        cues = tomllib.loads(cues_path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeError) as e:
        return 0, 0, [f"{cues_path.name} 解析失败: {e}"]
    errors: list[str] = []
    # 形态写错（值不是表）一律汇入错误清单，由 build 统一 FAIL 退出，不抛 traceback
    tables: dict[str, dict] = {}
    for name in ("block", "say", "take"):
        tbl = cues.get(name, {})
        if not isinstance(tbl, dict):
            errors.append(f"{cues_path.name}: [{name}] 须为表")
            tbl = {}
        tables[name] = tbl
    by_id = {i["id"]: i for i in items}
    n_block = n_say = 0
    for sid, spec in tables["block"].items():
        if sid not in by_id:
            errors.append(f"{cues_path.name}: block.{sid} 不是本稿句 id")
            continue
        if not isinstance(spec, dict):
            errors.append(
                f'{cues_path.name}: block.{sid} 须为表（[block.{sid}] emo = "…"）'
            )
            continue
        emo = spec.get("emo")
        if not isinstance(emo, str) or not emo.strip():
            errors.append(f"{cues_path.name}: block.{sid} 缺 emo（须为非空字符串）")
            continue
        try:
            vec = parse_emo_vector(emo)
            if sum(vec) <= 0:
                raise ValueError("方向全零")
        except ValueError as e:
            errors.append(f"{cues_path.name}: block.{sid} emo 无效（{e}）")
            continue
        cue: dict = {"emo": emo}
        a = spec.get("alpha")
        if a is not None:
            # 方向由 tts.py 归一到 Σ=1 ⇒ 有效和 Σ×α 即 α；bool 是 int 子类，须单独排除
            if (
                isinstance(a, bool)
                or not isinstance(a, int | float)
                or not 0 < a <= 0.8
            ):
                errors.append(
                    f"{cues_path.name}: block.{sid} alpha 须为 (0, 0.8] 内的数值（Σ×α ≤ 0.8）"
                )
                continue
            cue["alpha"] = float(a)
        by_id[sid]["blockStart"] = True
        by_id[sid]["cue"] = cue
        n_block += 1
    for sid, say in tables["say"].items():
        if sid not in by_id:
            errors.append(f"{cues_path.name}: say.{sid} 不是本稿句 id")
            continue
        if not isinstance(say, str) or not say.strip():
            errors.append(f"{cues_path.name}: say.{sid} 必须是非空字符串")
            continue
        base = by_id[sid]
        src = base.get("ttsText", base["text"])
        if _strip_punct(strip_marks(say)) != _strip_punct(strip_marks(src)):
            errors.append(
                f"{cues_path.name}: say.{sid} 与正文不一致（只许改标点，改字请回 narration.md）"
            )
            continue
        # 保留标注再比：标注的集合/位置/读音须与正文逐个一致（只查「有无」会放过删改）；
        # 去标点会连标注内部一起剥（`<行|HANG，2>` ≡ `<行|HANG2>`），故标注本体另行逐字全等
        same_marks = PRON_MARK_RE.findall(say) == PRON_MARK_RE.findall(src)
        if not same_marks or _strip_punct(say) != _strip_punct(src):
            errors.append(
                f"{cues_path.name}: say.{sid} 发音标注与正文不一致（须原样携带 <字|读音>）"
            )
            continue
        base["ttsText"] = say
        n_say += 1
    for sid, n in tables["take"].items():
        if sid not in by_id:
            errors.append(f"{cues_path.name}: take.{sid} 不是本稿句 id")
            continue
        # take 序号（块种子偏移）；bool 是 int 子类，须单独排除
        if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 999:
            errors.append(
                f"{cues_path.name}: take.{sid} 须为 1–999 的整数（take 序号）"
            )
            continue
        by_id[sid]["take"] = n
    return n_block, n_say, errors


def sentence_digest(text: str) -> str:
    """基线锁的句 digest：pron 剥离后 text 字段口径的 sha1 前 12 位（zh / en 同口径）。

    build（写锁）、check_script 与 pipeline status（读锁比对）共用此函数——译稿
    失鲜判定的单一口径，勿在他处内联同形计算。
    """
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def read_lock(path: Path) -> dict[str, dict[str, str]]:
    """→ {句id: {"zh": 锁定时主稿 digest, "en": 该句译文 digest}}；形状非法 → ValueError
    （含非法 JSON），由调用方决定大声失败或降级提示。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not all(
        isinstance(v, dict) and all(isinstance(v.get(k), str) for k in ("zh", "en"))
        for v in raw.values()
    ):
        raise ValueError(f"{path.name} 形状非法：应为 {{句id: {{zh, en}}}}")
    return raw


def stale_ids(lock: dict[str, dict[str, str]], zh_items: list[dict]) -> list[str]:
    """→ 锁定后主稿被改动、译文尚待复核的句 id（按主稿句序）。"""
    return [
        i["id"]
        for i in zh_items
        if i["id"] in lock and lock[i["id"]]["zh"] != sentence_digest(i["text"])
    ]


def merge_lock(
    old: dict[str, dict[str, str]],
    zh_items: list[dict],
    en_items: list[dict],
    accept: set[str] | None,
) -> dict[str, dict[str, str]]:
    """重建锁（gettext msgmerge 的 fuzzy 语义）：主稿改了而译句没动的句**保留旧主稿
    digest**——失鲜持续可测，直到译句被改写（视为已重译）或被 accept 点名确认
    （accept=None 表示全部接受）。新增句 / 无旧锁时以当前主稿为基线。"""
    en_now = {i["id"]: sentence_digest(i["text"]) for i in en_items}
    out: dict[str, dict[str, str]] = {}
    for i in zh_items:
        sid, prev = i["id"], old.get(i["id"])
        take = (
            prev is None
            or prev.get("en") != en_now[sid]
            or accept is None
            or sid in accept
        )
        zh = sentence_digest(i["text"]) if take else prev["zh"]
        out[sid] = {"zh": zh, "en": en_now[sid]}
    return out


def check_alignment(
    zh_items: list[dict],
    en_items: list[dict],
    zh_titles: dict[str, str],
    en_titles: dict[str, str],
) -> None:
    """硬对齐门：译稿与主稿句 id 序列 / 幕归属 / 幕集合逐一相等，失配大声退出。

    幕标题是译写对象、允许不同；其余任何失配都会让「en 复用 zh 分镜与场景
    代码」的前提静默失效（beatWindow 按句 id 取窗），故在生成期拦死。"""
    zh_ids = [i["id"] for i in zh_items]
    en_ids = [i["id"] for i in en_items]
    problems: list[str] = []
    if en_ids != zh_ids:
        zh_set, en_set = set(zh_ids), set(en_ids)
        missing = [x for x in zh_ids if x not in en_set]
        extra = [x for x in en_ids if x not in zh_set]
        if missing:
            problems.append(f"缺句（主稿有而译稿无）: {' '.join(missing)}")
        if extra:
            problems.append(f"多句（译稿有而主稿无）: {' '.join(extra)}")
        if not missing and not extra:
            for k, (z, e) in enumerate(zip(zh_ids, en_ids)):
                if z != e:
                    problems.append(f"句序不一致：第 {k + 1} 句主稿为 {z}，译稿为 {e}")
                    break
    zh_scene = {i["id"]: i["scene"] for i in zh_items}
    if wrong := [
        i["id"]
        for i in en_items
        if i["id"] in zh_scene and i["scene"] != zh_scene[i["id"]]
    ]:
        problems.append(f"句幕归属不一致: {' '.join(wrong)}")
    if set(en_titles) != set(zh_titles):
        problems.append(
            f"幕集合不一致：主稿独有 {sorted(set(zh_titles) - set(en_titles))}"
            f"，译稿独有 {sorted(set(en_titles) - set(zh_titles))}"
        )
    if problems:
        for p in problems:
            print(f"FAIL  对齐: {p}", file=sys.stderr)
        sys.exit(
            f"译稿与主稿未对齐（{len(problems)} 类失配）—— 1:1 句 id 对齐是复用分镜/时间轴的前提"
        )


def collect_scene_i18n(root: Path, declared: list[str]) -> dict[str, str] | None:
    """→ {幕: en 标题}；未声明 en 或 narration.en.md 缺失/解析失败 → None（WARN 降级）。

    语言激活只认 narration.langs 声明（文件存在与否不作依据——二源归一）；
    只读幕标题，坏文件不炸 zh build（译稿自身的门在 build --lang en 里执法）。"""
    if "en" not in declared:
        return None
    src = langs.narration_md(root, "en")
    if not src.is_file():
        print(
            f"WARN  narration.langs 已声明 en 但缺 {src.name}——chapters.json 暂不带 i18n（zh 构建不为 en 文件失败）",
            file=sys.stderr,
        )
        return None
    _items, titles, struct_errors, mark_errors, _w, _m = parse_md(src, None)
    if struct_errors or mark_errors:
        print(
            f"WARN  {src.name} 解析失败（{len(struct_errors) + len(mark_errors)} 处）——chapters.json 暂不带 i18n（build --lang en 会点名）",
            file=sys.stderr,
        )
        return None
    return titles


def _old_lock(path: Path, accept: str | None) -> dict[str, dict[str, str]]:
    """→ 既有基线锁（无锁 = 空表）。坏锁不静默重置为「全部已复核」：须显式
    --accept all 才以当前主稿重建基线。"""
    if not path.is_file():
        return {}
    try:
        return read_lock(path)
    except ValueError as e:
        if accept is not None and accept.strip() == "all":
            return {}
        sys.exit(f"{e} —— 确认译稿全部复核后加 --accept all 重建基线锁")


def _parse_accept(arg: str | None, zh_items: list[dict]) -> set[str] | None:
    """--accept 取值 → merge_lock 的 accept（None = 全部接受；空集 = 不接受任何句）。"""
    if arg is None:
        return set()
    if arg.strip() == "all":
        return None
    ids = {x.strip() for x in arg.split(",") if x.strip()}
    if not ids:
        sys.exit(f"--accept 取值非法：{arg!r}（可选 'all' 或逗号分隔句 id）")
    if unknown := sorted(ids - {i["id"] for i in zh_items}):
        sys.exit(f"--accept 含主稿不存在的句 id: {' '.join(unknown)}")
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description="narration.md → narration.json")
    parser.add_argument("--project", default=".", help="视频工程根目录（含 script/）")
    parser.add_argument(
        "--lang", default=langs.PRIMARY, help="构建语言：zh 主稿（缺省）| en 译稿"
    )
    parser.add_argument(
        "--accept",
        metavar="all|ID[,ID…]",
        help="译稿构建：确认这些句的译文在主稿改稿后无需改动，按当前主稿刷新基线锁"
        "（重译过的句无需点名，自动刷新）",
    )
    args = parser.parse_args()
    try:
        lang = langs.validate(args.lang)
    except ValueError as e:
        parser.error(str(e))
    if args.accept is not None and lang == langs.PRIMARY:
        parser.error("--accept 只作用于译稿构建（--lang en）：主稿没有对齐对象")

    root = Path(args.project).resolve()
    src = langs.narration_md(root, lang)
    dst = langs.narration_json(root, lang)

    # 与 tts.py 同口径的可操作退出（而非裸 FileNotFoundError 栈）
    if not src.is_file():
        sys.exit(f"narration{langs.suffix(lang)}.md 不存在: {src} —— 见 {FORMAT_DOC}")

    vocab = load_vocab(PINYIN_VOCAB)
    items, scene_titles, struct_errors, mark_errors, mark_warnings, marked = parse_md(
        src, vocab
    )
    if struct_errors:
        for e in struct_errors:
            print(f"FAIL  {e}", file=sys.stderr)
        sys.exit(
            f"{src.name} 结构解析失败（{len(struct_errors)} 处）—— 见 {FORMAT_DOC}"
        )
    for w in mark_warnings:
        print(f"WARN  {w}", file=sys.stderr)
    if mark_errors:
        # 与结构病同口径硬失败：绝不产出一份带坏标注的 narration.json，
        # 否则会静默合成出读错音的整集（单槽位 mp3，事后只能靠听发现）
        for e in mark_errors:
            print(f"FAIL  {e}", file=sys.stderr)
        sys.exit(
            f"发音标注校验失败（{len(mark_errors)} 处）—— 语法见 $T/scripts/pron_marks.py"
        )

    # 配音台本（story 档，主稿专属）：块起点/块情绪/表演标点落进 items；无文件零波及
    n_block = n_say = 0
    if lang == langs.PRIMARY:
        n_block, n_say, cue_errors = apply_cues(root, items)
        for e in cue_errors:
            print(f"FAIL  {e}", file=sys.stderr)
        if cue_errors:
            sys.exit(
                f"配音台本校验失败（{len(cue_errors)} 处）—— 语法见 $T/references/VOICE-CLONING.md §4.5"
            )

    # 译稿构建以主稿为基准：对齐门 + 基线锁 + chapters 的 zh 标题底稿
    zh_titles = scene_titles
    if lang != langs.PRIMARY:
        zh_src = langs.narration_md(root, langs.PRIMARY)
        if not zh_src.is_file():
            sys.exit(f"主稿不存在: {zh_src} —— 译稿构建以主稿为对齐基准，先构建主稿")
        zh_items, zh_titles, z_struct, z_marks, _zw, _zm = parse_md(zh_src, vocab)
        if z_struct or z_marks:
            for e in (*z_struct, *z_marks):
                print(f"FAIL  {e}", file=sys.stderr)
            sys.exit(f"主稿 {zh_src.name} 解析失败——先修复主稿再构建译稿")
        check_alignment(zh_items, items, zh_titles, scene_titles)
        # 锁合并在任何写盘之前完成：坏锁 / 非法 --accept 大声退出时不留半套产物
        new_lock = merge_lock(
            _old_lock(langs.lock(root, lang), args.accept),
            zh_items,
            items,
            _parse_accept(args.accept, zh_items),
        )

    dst.write_text(
        json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 时长估算：语速常数按语言各配（zh 字/分、en 词/分），默认值只经 config.default
    cfg, *_rest = config.load(root, required=False, scope={"narration"})
    narr = cfg.get("narration", {})
    declared = narr.get("langs", config.default("narration.langs"))
    per_scene: dict[str, int] = {}
    for i in items:
        per_scene[i["scene"]] = per_scene.get(i["scene"], 0) + 1
    if lang == langs.PRIMARY:
        total = sum(len(i["text"]) for i in items)
        cpm = narr.get("chars_per_min", config.default("narration.chars_per_min"))
        print(f"句数: {len(items)}  总字数: {total}")
        print(f"各幕句数: {per_scene}")
        print(f"估算时长({cpm}字/分): {total / cpm:.1f} 分钟")
    else:
        unit = langs.LANGS[lang].unit
        total = sum(langs.length(i["text"], lang) for i in items)
        wpm = narr.get("words_per_min", config.default("narration.words_per_min"))
        print(f"句数: {len(items)}  总{unit}数: {total}")
        print(f"各幕句数: {per_scene}")
        print(f"估算时长({wpm}{unit}/分): {total / wpm:.1f} 分钟")
    if marked:
        print(
            f"发音标注: {marked} 句带 ttsText（字数与字幕仍取剥离后的 text）"
            + ("" if vocab else "；未找到 pinyin.vocab，已跳过「音节是否在表内」告警")
        )
    n_take = sum(1 for i in items if "take" in i)
    if n_block or n_say or n_take:
        print(
            f"配音台本: {n_block} 个块起点/情绪 · {n_say} 句表演标点"
            + (f" · {n_take} 处块重掷" if n_take else "")
            + "（story 档消费，见 VOICE-CLONING §4.5）"
        )
    if lang != langs.PRIMARY:
        # 基线锁：记录「翻译时主稿长什么样」——主稿事后改稿 ⇒ 译稿失鲜可测
        lock_path = langs.lock(root, lang)
        lock_path.write_text(
            json.dumps(new_lock, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        print(f"基线锁: {len(zh_items)} 句主稿 digest → {lock_path.name}")
        if pending := stale_ids(new_lock, zh_items):
            print(
                f"WARN  译稿待复核 {len(pending)} 句（主稿在锁定后改动、译句未动）:"
                f" {' '.join(pending)} —— 重译这些句；译文确实无需改动时加"
                f" --accept {','.join(pending)}（check --lang {lang} 在复核前保持 FAIL）",
                file=sys.stderr,
            )
    # chapters 以主稿标题为底（en 构建同样）：幕数对齐门已保证两稿同幕集
    print(f"章节标签: {len(zh_titles)} 幕 → video/src/chapters.json（顶部进度条）")
    emit_chapters(root, zh_titles, declared)
    emit_series_layers(root)


def emit_chapters(
    root: Path, scene_titles: dict[str, str], declared: list[str]
) -> None:
    """幕标题 → video/src/chapters.json（顶部分段进度条 ChapterProgress 的数据面）。

    scene_titles 恒为主稿（zh）标题；本集声明产出 en 且 narration.en.md 可容错
    解析时，条目附 `i18n: {en: 译标题}`（ChapterProgress 按渲染语言取用）。
    zh 与 en 两种构建产出同一文件；未声明 en 的集不带 i18n 键（字节与改造前
    一致）。无条件写（series-layers 依赖 series.json，本文件只依赖 narration
    本身）；标题缺失写空串，组件侧回退只显 PART n。空集也照写（脚手架期形态）。
    """
    i18n = collect_scene_i18n(root, declared)
    entries: list[dict] = []
    for s, t in scene_titles.items():
        entry: dict = {"scene": s, "title": t}
        if i18n and s in i18n:
            entry["i18n"] = {"en": i18n[s]}
        entries.append(entry)
    out = root / "video" / "src" / "chapters.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(entries, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )


def emit_series_layers(root: Path) -> None:
    """series.json → video/src/series-layers.json（系列身份装置的数据面）。

    references/07 五层 Harness 栈的层序/层名**必须**从 series.json 派生（硬编码即漂移）；
    Remotion 的打包根是 video/，读不到工程外文件，故由本脚本每次 build 重派生落盘。
    仅取本集所属系列；集不在任何系列（脚手架期）则跳过不写。层短名取 cardSub
    首段（「执行层 · 循环」→「执行层」）。next 为下一集标题（P6 呼吸预告用）。
    集条目与 next 的可选 `i18n: {"en": …}` 透传为 titleI18n / nextI18n（P6 身份
    卡/下期卡按渲染语言取用；无则不加键，zh-only 集字节不变）。
    """
    series_json = root.parent.parent / "series.json"
    if not series_json.is_file():
        return
    series_list = json.loads(series_json.read_text(encoding="utf-8"))["seriesList"]
    for series in series_list:
        eps = series["episodes"]
        for k, ep in enumerate(eps):
            if ep["path"] != f"episodes/{root.name}":
                continue
            layers = [
                {
                    "index": i + 1,
                    "layer": e["cardSub"].split(" · ")[0],
                    "title": e["title"],
                    **({"titleI18n": e["i18n"]} if e.get("i18n") else {}),
                    "published": e.get("status") == "ready"
                    and "已上线" in e.get("voice", ""),
                }
                for i, e in enumerate(eps)
            ]
            payload: dict = {
                "seriesId": series["id"],
                "layers": layers,
                "activeIndex": k + 1,
            }
            if k + 1 < len(eps):
                payload["next"] = eps[k + 1]["title"]
                if eps[k + 1].get("i18n"):
                    payload["nextI18n"] = eps[k + 1]["i18n"]
            else:
                payload["next"] = None
            out = root / "video" / "src" / "series-layers.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                json.dumps(payload, ensure_ascii=False, indent=1) + "\n",
                encoding="utf-8",
            )
            print(f"系列层: {series['id']} 第 {k + 1}/{len(eps)} 集 · layers 已派生")
            return


if __name__ == "__main__":
    main()
