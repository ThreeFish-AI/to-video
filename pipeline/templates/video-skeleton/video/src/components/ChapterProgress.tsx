import React from 'react';
import {interpolate, useCurrentFrame} from 'remotion';
import chaptersJson from '../chapters.json';
import {theme} from '../design/theme';
import type {SceneRange} from '../types';

type Chapter = {scene: string; title: string};
/** build_narration.py 从 narration.md `## Pn 幕标题` 派生；scaffold 占位 [] 推断为
 *  never[]，统一断言收窄。空数组（首次 build 前）⇒ 本组件不渲染。 */
const CHAPTERS = chaptersJson as Chapter[];

/* ── 几何带 SSOT：整带收在 y<56 ─────────────────────────────────────────────
 * 依据 skills/06 顶部横条实测：各幕内容最早 y=56 起、SceneTag 在 top:64——
 * y<56 是本设计系统已验证的零碰撞常驻带（底部字幕安全带的顶部对偶）。 */
const MARGIN_X = 72; // 与 SceneTag/Footnote 左锚对齐
const STRIP_W = 1920 - MARGIN_X * 2;
const BAR_Y = 14;
const BAR_H = 8;
const SEG_GAP = 8;
const FADE_IN_FRAMES = 12; // 开场淡入（帧驱动常量，同 Subtitle 先例）
const FADE_OUT_MAX = 30; // 片尾淡出上限 1s，实际取 min(tail, 30)——从 props 推导不写死

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));

/** 段边界：段 i 占 [from_i, from_{i+1})，末段吞到 total——幕间 gap 归前段尾，
 *  段宽比=时长占比，段内填充线性（进度是测量不是动效，无缓动）。 */
const segSpans = (scenes: SceneRange[], total: number) =>
  scenes.map((s, i) => ({
    ...s,
    to: i + 1 < scenes.length ? scenes[i + 1].from : total,
  }));

const titleOf = (scene: string) =>
  CHAPTERS.find((c) => c.scene === scene)?.title ?? '';

/** 顶部分段章节进度条：段宽∝幕时长、已播填充亮色、播放头随帧推进、段下
 *  `PART n : 幕标题` 标签（当前章亮、其余灰）。全片 overlay，与 Subtitle 同范式
 *  （帧驱动 + 只读底座 token，不 import 运动层、零 spring）。 */
export const ChapterProgress: React.FC<{
  scenes: SceneRange[];
  totalDurationInFrames: number;
}> = ({scenes, totalDurationInFrames}) => {
  const frame = useCurrentFrame();
  if (CHAPTERS.length === 0 || scenes.length === 0) {
    return null;
  }
  const segs = segSpans(scenes, totalDurationInFrames);
  const scale = (STRIP_W - SEG_GAP * (segs.length - 1)) / segs.reduce((a, s) => a + s.to - s.from, 0);
  let x = 0;
  const layout = segs.map((s) => {
    const w = (s.to - s.from) * scale;
    const seg = {from: s.from, to: s.to, x, w};
    x += w + SEG_GAP;
    return seg;
  });
  let currentIdx = segs.findIndex((s) => frame < s.to);
  if (currentIdx === -1) {
    currentIdx = segs.length - 1; // tail：钳在末段
  }
  const head = layout[currentIdx];
  const headX = head.x + head.w * clamp01((frame - head.from) / (head.to - head.from));

  const lastSeg = segs[segs.length - 1];
  const fadeOutFrames = Math.max(
    1,
    Math.min(totalDurationInFrames - (lastSeg.from + lastSeg.durationInFrames), FADE_OUT_MAX),
  );
  const opacity =
    interpolate(frame, [0, FADE_IN_FRAMES], [0, 1], {extrapolateRight: 'clamp'}) *
    interpolate(frame, [totalDurationInFrames - fadeOutFrames, totalDurationInFrames], [1, 0], {
      extrapolateLeft: 'clamp',
      extrapolateRight: 'clamp',
    });

  return (
    <div style={{position: 'absolute', left: MARGIN_X, top: BAR_Y, width: STRIP_W, opacity, pointerEvents: 'none'}}>
      {segs.map((s, i) => {
        const {x: segX, w} = layout[i];
        const fill = clamp01((frame - s.from) / (s.to - s.from));
        return (
          <div key={s.scene} style={{position: 'absolute', left: segX, width: w}}>
            {/* 轨道 + 左缘填充（text@0.9：比字幕白稍收，压顶部重量） */}
            <div
              style={{
                height: BAR_H,
                borderRadius: BAR_H / 2,
                background: theme.panelBorder,
                overflow: 'hidden',
              }}
            >
              <div style={{height: '100%', width: `${fill * 100}%`, background: theme.text, opacity: 0.9}} />
            </div>
            {w >= 64 && (
              <div
                style={{
                  marginTop: 6,
                  fontFamily: theme.mono,
                  fontSize: 14,
                  fontWeight: 500,
                  letterSpacing: 1,
                  color: i === currentIdx ? theme.text : theme.dim,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {/* 降级阶梯：w<120 只显序号；标题缺失只显 PART n */}
                {w < 120
                  ? `P${i + 1}`
                  : titleOf(s.scene)
                    ? `PART ${i + 1} : `
                    : `PART ${i + 1}`}
                {w >= 120 && titleOf(s.scene) && (
                  <span style={{fontFamily: theme.sans, fontSize: 20}}>{titleOf(s.scene)}</span>
                )}
              </div>
            )}
          </div>
        );
      })}
      {/* 播放头：与轨同带的亮圆点 + 辉光（rgba 字面值 = theme.text 底座 #F2F5FA） */}
      <div
        style={{
          position: 'absolute',
          left: headX - 6,
          top: BAR_H / 2 - 6,
          width: 12,
          height: 12,
          borderRadius: 6,
          background: theme.text,
          boxShadow: '0 0 10px rgba(242,245,250,0.5)',
        }}
      />
    </div>
  );
};
