# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-09-21

### Added

- 自 [ThreeFish-AI/negentropy](https://github.com/ThreeFish-AI/negentropy) `apps/negentropy-influence/pipeline/` 抽取为独立可安装技能：九阶段科普视频流水线（信源取证→策划→逐字稿→双重校验→分镜→TTS 声音克隆→Remotion 场景→草渲抽帧 QA→终渲交付）。
- 双锚点架构：skill 根（SKILL.md 哨兵，随安装位置）与内容工作区根（`.to-video-root` 哨兵，兼容 `.influence-root`）物理分离；`scaffold.py --init-workspace` 初始化任意目录为工作区。
- 分集/工作区薄包装器改为 skill 解析器（`TO_VIDEO_HOME` → `~/.claude/skills/to-video` → `~/.agents/skills/to-video`，未命中大声失败）。
- tts-store 默认目录迁至 `to-video`（旧目录自动回退兼容，内容寻址零缓存失效）。
- `check_series` 工程级受检面与课程/下期卡系列 id 集配置化（工作区 `to-video.toml`）。
