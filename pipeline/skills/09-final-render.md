# Stage ⑨ 终渲与交付（skill 规格 · 09）

> 前置：Stage ⑧ 的自动体检零 FAIL 且人工目检通过；文稿与音频已冻结（B 遍完成）。

## 终渲

```bash
cd $P/video
# 终渲（codec/crf/pixel-format/audio 已固化在 remotion.config.ts）
./node_modules/.bin/remotion render Main ../out/final.mp4
```

**关于并发**：并发度是机器属性、不进共享配置（见 §渲染硬化）。但 `remotion benchmark`
**对本类长片不实用**——它要按不同并发把整片渲多轮，25000 帧规模下 20 分钟不出结果
（2026-08-20 实测放弃）。实践口径：直接用 Remotion 默认并发（它已按 CPU 核数自适应）；
仅当终渲耗时明显异常时，才对**单幕**做 `--frames=<区间>` 的小样对比来选 `--concurrency=N`。

**⚠️ 渲染分两段，`Rendered N/N` 不等于完成**：先「渲帧」再「编码」，日志分别打
`Rendered i/N` 与 `Encoded i/N`。只盯 `Rendered` 会在编码进行到 ~20% 时误判完成，此时
`out/*.mp4` 是不完整产物（体积远小于最终值），拿去抽帧 QA 会得到假结论。判完成一律以
编排层的 `>> render 完成` 标记（或进程退出）为准，勿以帧计数为准。

**耗时口径**（2026-08-21 实测，M4 / 25642 帧 / 14:14 成片 / 170 句配音）：

| 阶段 | 墙钟 | 产物 |
|---|---|---|
| 草渲 0.5x + jpeg60 | **6.0 分钟** | 960×540，31.2 MB |
| 终渲 1080p + jpeg90 | **8.2 分钟** | 1920×1080，42.1 MB，视频 196 kb/s + 音频 189 kb/s |

即整片渲染是**分钟级**，远快于配音（同集 TTS 2.1 小时）。排期上「渲染慢」是错觉——
真正的长尾在配音；渲染可以放心多轮迭代（改一处场景重渲全片只要 8 分钟）。

渲染主机约束：**macOS + PingFang SC/Songti SC/SF Mono 系统字体**（三集未内嵌 CJK 字体，Linux/CI 渲染不在支持范围；重启触发器见 pipeline/README「字体可复现性」——渲染迁 Linux/CI，或 Remotion 5.0 将 validateFontIsLoaded 默认翻 true 时必须内嵌子集字体）。

## 交付件清单

```bash
# 字幕（B 站/YouTube 上传件；cue 终点不含句间停顿——外挂字幕静默期不留字）
uv run --no-project $T/pipeline/scripts/captions.py --project $P

# 交付归档（根路径 = --root 一次性 或 env TO_VIDEO_DELIVER_ROOT 持久；机器属性不进 toml）
uv run --no-project $T/pipeline/scripts/pipeline.py --project $P deliver
```

- [ ] `out/final.mp4`（1080p30，h264/aac192K；`remotion ffmpeg -i` 核流摘要）
- [ ] `out/captions.srt` + `out/captions.vtt`
- [ ] 封面帧（可从 `qa_frames.py` 挑一张标题卡帧，或 `remotion still` 单渲）
- [ ] 全片逐幕抽帧复检 + `--last-n 6 --check`（时长在 B 遍后又位移过，勿复用 A 遍结论）
- [ ] 交付时长以 `total_duration_in_frames`（timeline.py 纯函数）**现算**，登记时连复算式一起写（`= 23820 帧 @30fps = 794.00s` 形态）——勿抄上次输出/README/series.json 里的旧数字：四集曾统一短 2.19s（登记值取了音轨末点而非含 `tailSec` 的片尾），有复算式的那一集才对（ISSUE-171）
- [ ] `pipeline.py check` 实测口径在预算窗内
- [ ] deliver 归档副本（根路径已配置时）：`<根>/<系列id>/<集标题> vN.mp4`
- [ ] RSI 台账复查（非阻断）：制作中发现的 Skill 缺陷/改进已按 [RSI.md](../../RSI.md) 登记台账（无则跳过）

## 交付归档（deliver）

`out/final.mp4` 是**新鲜渲槽位**（重渲即覆盖、gitignored）；`deliver` 把成片复制进统一归档根 `<根>/<系列id>/<集标题> v<N>.mp4`——系列子目录与集标题取自 `$W/series.json`（发布顺序 SSOT），版本号扫目录自增：首投 v1，**内容变化才升版**，同字节重投打印跳过不产生重复副本；改题后新题另起 v1、旧版本原样保留。

- **配置渠道**：`--root ~/Documents/video`（一次性 / prompt 指定）或 `export TO_VIDEO_DELIVER_ROOT=~/Documents/video`（持久统一配置，可写 shell profile / Claude Code settings env）。根路径是机器属性，不写进受版本控制的 toml（同 tts.server / tts-store 立场）；两渠道皆无时 deliver 大声退出并列出用法。
- **agent 契约**：用户在 prompt 中给出目标路径时，`render --final` 成功后**显式**执行 `pipeline.py --project $P deliver --root <路径>`，并建议用户以 env 固化。`render --final` 刻意不自动串联 deliver——本规格把编排层 `>> render 完成` 标记钉为判完成唯一信号，串联外部写操作会在失败时产生「标记已打 + 退出码非零」的混合信号。
- 先 `deliver --dry-run` 预览目的地与下一版本号，确认后再实投。

## 平台合规（发布前自查）

- 合成语音标注：B 站/YouTube 对 AI 合成语音有披露要求，按平台当期规则标注；
- 许可：Remotion（>3 人公司需商业授权）；IndexTTS-2.5（bilibili 模型许可，个人/研究可用，商用联系 indexspeech@bilibili.com）——详见 [pipeline/README §八](../README.md)；
- 声音克隆仅为本人自愿克隆；克隆他人声音须书面同意（[VOICE-CLONING.md §八](../VOICE-CLONING.md)）。

## 换机 / 换 worktree 重建 runbook

git 只带走入库字节——`out/` 渲染产物、archify 的 mp4/末帧 PNG（派生产物）、分集 mp3、
`voices/`（生物特征）与 `node_modules` 都不随 clone 走。因此**换一个 worktree/机器就要重建一次，
这是常规操作而非异常路径**。按依赖序六步（TTS 可恢复时总量级 ≈ 1 小时，对比整集重合成 2 小时）：

1. **装 skill**：clone 本仓并软链或设 `TO_VIDEO_HOME`（见 [README §路径变量约定](../README.md)）——
   工作区/分集薄包装靠它解析机制，缺席是大声失败而非静默跳过。
2. **`cd video && pnpm install`（裸 install，勿加 `--ignore-workspace`；必须先于 archify 录制）**：
   录制器要起 Remotion 打包浏览器，`node_modules` 半残会在录制中途裸 traceback。构建许可配在
   `video/pnpm-workspace.yaml` 的 `allowBuilds`——加 `--ignore-workspace` 会把它一并忽略，
   直接以 `ERR_PNPM_IGNORED_BUILDS` 中断安装留下半残。
3. **TTS 恢复（分钟级，服务须在线）**：先起 IndexTTS 服务（[VOICE-CLONING §二](../VOICE-CLONING.md)），
   原参数重跑 `pipeline.py tts`——机器级 tts-store 按 digest 逐句回收、整集零重合成（缓存口径见
   [VOICE-CLONING §六](../VOICE-CLONING.md)）。换 worktree 须先从旧工作区/私有录音恢复 `voices/`
   并过 `refs.py verify`（参考音频不随 git 走）；换机则随行拷贝 tts-store 目录（或以
   `TO_VIDEO_TTS_STORE` 指位），否则此步退化为 2 小时量级整集重合成。
4. **archify 全量重录（~45 分钟）**：`uv run --with playwright python
   $T/pipeline/scripts/record_archify_all.py --project $P`（串行是刻意的：多实例互抢前台焦点会掉帧、
   静默污染产物）。驱动录后自动对录前 sidecar 的 `capture_fps` 基线逐章比对，**退化超 10%
   即 WARN 点名**，按点名 `--only <slug> --force` 补录——`--min-fps` 与该 WARN 都只告警不失败，
   不处理的降质素材会绿着门进片。录完跑 `$T/pipeline/scripts/archify_lead.py --project $P`
   （漏跑 = 白闪进片；覆盖门会按图点名 lead 全 0 的图，但只是 WARN）与
   `$T/pipeline/scripts/archify_manifest.py --project $P`。
5. **build / check**：`pipeline.py build` 重建 narration.json 派生物 → `pipeline.py check`
   （含 archify 覆盖门）→ `video/` 内 `tsc --noEmit`。
6. **render**：草渲 + 抽帧 QA（[skills/08](./08-render-qa.md)）→ 终渲（本文件上文）。
