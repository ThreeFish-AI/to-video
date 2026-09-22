# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- 顶部分段式章节进度条（frozen `ChapterProgress.tsx`）：新集开箱自带全片顶部 overlay——段宽∝幕时长、已播 `text@0.9` 填充、播放头 Ø14 亮点（bg 描边 + 辉光）随帧推进、**章节名内嵌段内居中**（sans 18，标题缺失回退 mono 幕码），段内文字**双色随播放头揭示**（已填侧深字 `bg` 压亮填充、未填侧亮字：当前章 `text`/未播章 `dim`，左右两层同显式 px 宽裁切保 ellipsis 逐像素一致）；段高 36（y14–50，圆角 4），整带仍收在 y<56 零碰撞带（各幕内容 y≥56 起、SceneTag top:64 不动），开场 12 帧淡入、片尾 tail ≤30 帧淡出（均从 props 推导零写死帧数）。数据面两条链：段边界/占比走 `computeTimeline` 的 `scenes`（TTS 重跑自动重定时）；标题走 `build_narration.py` 新派生的 `video/src/chapters.json`（`## Pn 幕标题` 此前被 SCENE_RE 丢弃，占位 `[]` 时组件自渲染 null）。档位登记：组件 frozen（同 Subtitle 性质）、chapters.json seeded（机器生成同 pnpm-lock 先例）；Main.tsx 挂载属 regioned 承重区改动，9 个已发布集按 Subtitle 分代先例登记 drift 指纹 `179be60ed605`（保持发布态，下次重渲时同步撤销）。配套规格：skills/03「幕标题即章节标签」、skills/05 顶部安全带、skills/06「顶部章节进度条」节 + 红线 2b + HarnessBadge 共存定案项（EP2–5 同步窗口）、skills/08 目检五判据；测试新增 test_skeleton 2 条（档位归属 + 挂载承重）与 test_build_narration 2 条（chapters 派生黄金 + 分隔符形态）。
- `deliver` 子命令（⑨ 交付归档）：`out/final.mp4` → `<根>/<系列id>/<集标题> vN.mp4` 统一归档。根路径两渠道——`--root`（一次性/prompt 指定）与 env `TO_VIDEO_DELIVER_ROOT`（持久统一配置；机器属性不进受版本控制 toml，同 tts.server / tts-store 立场）；系列子目录与集标题取自 series.json，版本号扫目录自增（同字节重投跳过不升版、`.part` 原子落位、绝不覆写既有版本）；显式子命令，不串联进 `render --final`（完成行信号契约），亦不可 `--series` 扇出。

## [1.0.0] - 2026-09-21

### Added

- 自 [ThreeFish-AI/negentropy](https://github.com/ThreeFish-AI/negentropy) `apps/negentropy-influence/pipeline/` 抽取为独立可安装技能：九阶段科普视频流水线（信源取证→策划→逐字稿→双重校验→分镜→TTS 声音克隆→Remotion 场景→草渲抽帧 QA→终渲交付）。
- 双锚点架构：skill 根（SKILL.md 哨兵，随安装位置）与内容工作区根（`.to-video-root` 哨兵，兼容 `.influence-root`）物理分离；`scaffold.py --init-workspace` 初始化任意目录为工作区。
- 分集/工作区薄包装器改为 skill 解析器（`TO_VIDEO_HOME` → `~/.claude/skills/to-video` → `~/.agents/skills/to-video`，未命中大声失败）。
- tts-store 默认目录迁至 `to-video`（旧目录自动回退兼容，内容寻址零缓存失效）。
  存量用户彻底搬走旧缓存（可选，一次性）：

  ```bash
  mv ~/Library/Application\ Support/negentropy-influence/tts-store \
     ~/Library/Application\ Support/to-video/tts-store
  ```

  （若新目录已被创建，先用 `rsync -a` 合并内容再删除旧目录，勿直接 `mv` 套娃。）
- `check_series` 工程级受检面与课程/下期卡系列 id 集配置化（工作区 `to-video.toml`）。
