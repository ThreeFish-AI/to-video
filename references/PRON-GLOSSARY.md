# 易错字台账（发音标注复用表）

> **用途**：把「这一集试听时听出来的读错字」沉淀成跨集可复用的标注，让发音修正从
> 逐集 O(n) 重听变成写稿时 O(1) 查表。语法与校验规则见
> [scripts/pron_marks.py](../scripts/pron_marks.py)；写稿纪律见
> [references/03-narration.md](./03-narration.md)。

## 怎么用

1. **写稿时**：新稿定稿前，对照下表把命中的词按「标注写法」列改写进 `narration.md`；
2. **试听时**：听出新的读错字，先用单句小样确认标注有效，再回填本表；
3. **校验**：`build_narration.py` 会硬失败拦非法标注（格式/通道/`^[JQX]U` 等），
   `pinyin.vocab` 存在时还会告警「音节不在表内」。

## 台账

首条来自 2026-09-21 成片句尾缺陷定稿（ISSUE-192）；三集成片尚未做过系统性读音复听，
下一集配音的试听关卡（[references/07-tts-voice.md](./07-tts-voice.md) 第 3 闸）请边听边往下表记。

| 词 | 正确读音 | 标注写法 | 出处 | 记录日期 |
|---|---|---|---|---|
| Context | K AA1 N T EH2 K S T | `<Context\|K AA1 N T EH2 K S T>` | horizon-context-video p0-10 | 2026-09-21 |
| 行（表格/量词语境） | háng | `<行\|HANG2>` | jev-decision-model-video v1 人耳证实（negentropy 37692b45d，26 处）→ 修复 8974c2f3f（经 negentropy#1176 合入，27 处） | 2026-09-27 |

## 语义规则速查（高危多音字，写稿阶段就标注）

语义规则 = 字典级确定的读音 + **已证实会错的方向**（RSI-014）。jev 集 v1 全片 26 处（negentropy 37692b45d）
「行(háng)」被 TTS 读成 xíng、终渲后才靠人耳发现——TTS 对 行 的默认倾向是 xíng，
表格/量词语境（每行/单选行/行尾）系统性读错，而 运行/执行 等 xíng 向语境实测读对。
规则只挂高危方向（宁缺勿错：错规则会把可能读对强推成必然读错）；某字经试听证实
系统性读错后，其高危方向规则入 [pron_marks.POLYPHONE_CANDIDATES](../scripts/pron_marks.py)
（本表与代码同源，由 tests 钉住不漂移）；首条规则的证据锚点见上方台账「行（表格/量词语境）」行。命中处的纪律：**写稿即标注，不等试听**
（[references/03-narration.md](./03-narration.md) 发音标注节）。

| 字 | 语境正则（命中即推荐） | 推荐读音 | 标注写法 |
|---|---|---|---|
| 行 | `(?:银行\|行列\|内行\|外行\|行业\|行话\|行尾\|行首\|行间\|行内\|行里\|行号\|行上\|行样张?\|整行\|同行(?=的)\|类行(?![为动]))` | HANG2 | `<行\|HANG2>` |
| 行 | `(?:单选\|多选\|等级\|是否\|别的\|另一?\|同一\|下一?\|上一?\|某\|这\|那\|每\|各\|几\|两\|二\|三\|四\|五\|六\|七\|八\|九\|十\|百\|一\|\d+) ?行(?![人为其为程事文踪李星进政])` | HANG2 | `<行\|HANG2>` |
| 行 | `的行(?![为程动业政走人事文踪李星进驶使医善贿])` | HANG2 | `<行\|HANG2>` |

逐句扫描（报告 + 建议标注清单）；`--pron-gate` 把「规则命中而句中该 occurrence
无任何标注」升为 FAIL 门（已标注视为作者显式接管，不拦）：

```bash
uv run --no-project $T/scripts/check_script.py --project $P --pron-candidates
uv run --no-project $T/scripts/check_script.py --project $P --pron-gate
```

## 候选清单（尚未验证，供复听时重点关注）

科普题材的高频多音字，**未经实测确认模型是否读错**，仅作复听时的注意力清单——
语义规则未覆盖的字确认读错才写进上面的台账并标注：无规则依据的预防性标注反而
引入风险（标注错 = 必然读错）。

候选表已收敛为代码内单一事实源：[pron_marks.POLYPHONE_CANDIDATES](../scripts/pron_marks.py)
（文档里的表没有消费者，只会与扫描器漂移）。逐句扫描报告：

```bash
uv run --no-project $T/scripts/check_script.py --project $P --pron-candidates
```

## 边界

- **英文专名默认不进本表**：内容层沿用「进角标不口播」。CMU 音素通道（`<Claude|K L AO1 D>`）
  已实战定稿（2026-09-21，ISSUE-192：horizon-context-video 成片句尾 *Context* 修复）——按
  [INDEXTTS-2.5-ADVANCED.md §2.3](./INDEXTTS-2.5-ADVANCED.md) 的定稿配方处理（标注 +
  重掷 + 无偏验证），操作协议见 [VOICE-CLONING.md §5.4](./VOICE-CLONING.md)；**句尾英文词
  读法一律标注兜底、不赌采样**。确需口播的专名可记入本表并注明「CMU」。
- **数字/百分号/量词不进本表**：那是文本归一化的职责，禁写清单见
  [references/03-narration.md](./03-narration.md) 的读法纪律表。
