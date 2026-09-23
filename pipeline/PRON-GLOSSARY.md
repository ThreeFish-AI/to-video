# 易错字台账（发音标注复用表）

> **用途**：把「这一集试听时听出来的读错字」沉淀成跨集可复用的标注，让发音修正从
> 逐集 O(n) 重听变成写稿时 O(1) 查表。语法与校验规则见
> [scripts/pron_marks.py](./scripts/pron_marks.py)；写稿纪律见
> [skills/03-narration.md](./skills/03-narration.md)。

## 怎么用

1. **写稿时**：新稿定稿前，对照下表把命中的词按「标注写法」列改写进 `narration.md`；
2. **试听时**：听出新的读错字，先用单句小样确认标注有效，再回填本表；
3. **校验**：`build_narration.py` 会硬失败拦非法标注（格式/通道/`^[JQX]U` 等），
   `pinyin.vocab` 存在时还会告警「音节不在表内」。

## 台账

首条来自 2026-09-21 成片句尾缺陷定稿（ISSUE-192）；三集成片尚未做过系统性读音复听，
下一集配音的试听关卡（[skills/07-tts-voice.md](./skills/07-tts-voice.md) 第 3 闸）请边听边往下表记。

| 词 | 正确读音 | 标注写法 | 出处 | 记录日期 |
|---|---|---|---|---|
| Context | K AA1 N T EH2 K S T | `<Context\|K AA1 N T EH2 K S T>` | horizon-context-video p0-10 | 2026-09-21 |

## 候选清单（尚未验证，供复听时重点关注）

科普题材的高频多音字，**未经实测确认模型是否读错**，仅作复听时的注意力清单——
确认读错才写进上面的台账，不要预防性标注（标注错 = 必然读错，反而引入风险）。

候选表已收敛为代码内单一事实源：[pron_marks.POLYPHONE_CANDIDATES](./scripts/pron_marks.py)
（文档里的表没有消费者，只会与扫描器漂移）。逐句扫描报告：

```bash
uv run --no-project $T/pipeline/scripts/check_script.py --project $P --pron-candidates
```

## 边界

- **英文专名默认不进本表**：内容层沿用「进角标不口播」。CMU 音素通道（`<Claude|K L AO1 D>`）
  已实战定稿（2026-09-21，ISSUE-192：horizon-context-video 成片句尾 *Context* 修复）——按
  [INDEXTTS-2.5-ADVANCED.md §2.3](./INDEXTTS-2.5-ADVANCED.md) 的定稿配方处理（标注 +
  重掷 + 无偏验证），操作协议见 [VOICE-CLONING.md §5.4](./VOICE-CLONING.md)；**句尾英文词
  读法一律标注兜底、不赌采样**。确需口播的专名可记入本表并注明「CMU」。
- **数字/百分号/量词不进本表**：那是文本归一化的职责，禁写清单见
  [skills/03-narration.md](./skills/03-narration.md) 的读法纪律表。
