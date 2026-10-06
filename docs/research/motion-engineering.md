# Motion Engineering 吸收方案

## 结论

`vibe-video` 应吸收「视觉约束可执行化」与「过渡质量可验收」两类能力，而不应把音乐 BPM、人物生成链路或新的渲染后端引入现有生产主线。既有 frame-driven 时间轴、纯函数运动模型和 30fps 默认值保持不变。

本次方案把新增能力分成三个边界：

1. **分镜契约**：在现有四列分镜表末尾增加可选 `Visual Lock` 列，按「参考 / 保持 / 禁止」表达逐镜约束；旧分镜不需要迁移。
2. **抽帧验收**：Stage ⑨ 增加显式 `--transition` 与 `--loop` 采样入口，复用 manifest 与 timing 的单一事实源；不改变默认 beat 抽帧行为。
3. **渲染策略**：Motion Blur 只作为镜头级 opt-in 规范，运动主体与可读叠加层分离，不对整帧默认施加 `tmix`，也不把默认帧率提高到 60fps。

## 方案比选

| 方案 | 做法 | 取舍 | 决策 |
|---|---|---|---|
| A | 新增独立 JSON 视觉规格与渲染器 | 约束可计算，但引入第二事实源与迁移成本 | 否决 |
| B | 分镜可选列 + 既有抽帧 CLI 扩展 | 复用现有解析、manifest、timing 与 QA 输出，改动半径最小 | **采纳** |
| C | 全面引入图生视频或 Motion Blur 后端 | 适合实拍/广告链路，但削弱可追溯性并增加依赖 | 否决 |

## 建模与验收规则

`Morph Continuity` 只适用于同一视觉主体的状态演进，至少声明起始态、终止态、身份线索和禁止项。过渡采样应覆盖过渡前一帧、起始帧、中间帧、结束帧和后一帧；验收对象是主体连续性、文字交接和语义边界，不是要求整帧像素相等。

`Loop Continuity` 只适用于显式标记的循环镜头。除首尾位置外，还要检查首尾速度方向与幅度连续；字幕、章节条等非循环叠加层不参与主体速度判定。时间区间按 manifest 的分镜顺序解析，拒绝缺失、倒置、跨幕或越界请求。

## 依据

- Remotion 官方文档将动画属性建模为随 frame 变化的值，并提供 `interpolate`、`spring` 等确定性工具；这支持沿用现有 frame-driven 运动层，而不是引入 timer 或 CSS transition。[1]
- FFmpeg 官方 filter 文档定义 `tmix` 为多帧混合滤镜；它适合成为显式后处理选项，但整帧混合会同时模糊字幕和公式，因此不能作为默认 QA 或默认渲染路径。[2]
- 文章《从写代码到做视频，Claude Opus 5.5 被玩出了新花样》提供了 Morph、视觉锁定、边界帧和 loop 速度连续性的实践启发；本文只吸收其可迁移的工程约束，不把文章中的模型或生产链路视为本仓依赖。[3]

## References

[1] Remotion, “Animating properties,” *Remotion Documentation*, accessed Oct. 5, 2026. [Online]. Available: https://www.remotion.dev/docs/animating-properties

[2] FFmpeg Developers, “tmix,” *FFmpeg Filters Documentation*, accessed Oct. 5, 2026. [Online]. Available: https://ffmpeg.org/ffmpeg-filters.html#tmix

[3] K 姐研究社, “从写代码到做视频，Claude Opus 5.5 被玩出了新花样,” *微信公众号*, Oct. 5, 2026. [Online]. Available: https://mp.weixin.qq.com/s/H6sKRbURDgRrp_6P4-qapw
