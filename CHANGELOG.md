# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

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
