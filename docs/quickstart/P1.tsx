// Quickstart 第二幕场景组件（根 README「快速上手」的 cp 源，与 P0.tsx 配套）。
// 画面与口播互补：口播说「顶部进度条」，画面把它放大解剖——中央大条与顶部
// ChapterProgress 逐帧同步（段界/填充/播放头全部由真实时间轴派生，零演示常数）。
// 动效仍来自 frozen cards 原语（FadeUp 错峰）；单句幕用 w('p1-01')——解析器
// 契约见 P0.tsx 头注（check_script.py 的 SCENE_CALL_RE 第二参可选）。内容垂直
// 居中 y≥56 起（顶部 y<56 安全带归章节进度条，skills/06 红线 2b）。
import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {FadeUp, Pill} from '../components/cards';
import {theme} from '../design/theme';
import {beatWindow} from '../timing';
import type {SceneRange} from '../types';
import chaptersJson from '../chapters.json';

type Chapter = {scene: string; title: string};
const CHAPTERS = chaptersJson as Chapter[];

// 放大档几何：顶部章节条（components/ChapterProgress.tsx，frozen）的讲解版——
// 同一设计语言（panelBorder 轨道 / text@0.9 填充 / 双层同位文字裁切 / bg 描边
// 播放头），只放大尺寸便于讲解。
const BAR_W = 1180;
const BAR_H = 48;
const SEG_GAP = 12; // 顶部条 8px 的放大档
const TITLE_SIZE = 30;
const TITLE_PAD_X = 24;
const HEAD_R = 12; // 顶部条 Ø14 的放大档（border 计入 border-box）

const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const titleOf = (scene: string) => CHAPTERS.find((c) => c.scene === scene)?.title ?? scene;

/** 段内居中文字。显式 px 宽（段宽−左右 pad）：轨道/填充两层共用同值，ellipsis
 *  截断才逐像素一致（双色裁切不错位——同 ChapterProgress 的 SegLabel）。 */
const SegText: React.FC<{label: string; color: string; width: number}> = ({label, color, width}) => (
  <div
    style={{
      position: 'absolute',
      left: TITLE_PAD_X,
      top: 0,
      width,
      height: BAR_H,
      lineHeight: `${BAR_H}px`,
      textAlign: 'center',
      fontFamily: theme.sans,
      fontSize: TITLE_SIZE,
      fontWeight: 500,
      letterSpacing: 2,
      color,
      whiteSpace: 'nowrap',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
    }}
  >
    {label}
  </div>
);

/** 单段：panelBorder 轨道 + 未填侧文字（dim）+ 宽 w*fill 的裁切层（text@0.9 亮
 *  填充 + bg 深字）——文字色随播放头揭示翻转，同顶部条状态机。 */
const Seg: React.FC<{w: number; fill: number; label: string}> = ({w, fill, label}) => (
  <div
    style={{
      position: 'relative',
      width: w,
      height: BAR_H,
      borderRadius: 8,
      overflow: 'hidden',
      background: theme.panelBorder,
    }}
  >
    <SegText label={label} color={theme.dim} width={w - TITLE_PAD_X * 2} />
    <div style={{position: 'absolute', left: 0, top: 0, width: w * clamp01(fill), height: BAR_H, overflow: 'hidden'}}>
      <div style={{position: 'absolute', left: 0, top: 0, width: w, height: BAR_H, background: theme.text, opacity: 0.9}} />
      <SegText label={label} color={theme.bg} width={w - TITLE_PAD_X * 2} />
    </div>
  </div>
);

export const P1: React.FC<{scene: SceneRange}> = ({scene}) => {
  const w = (fromId: string, toId?: string) => beatWindow(scene.sentences, scene.from, fromId, toId);
  // 全片进度：Sequence 内 useCurrentFrame 是本幕局部帧，+scene.from 还原全局帧；
  // durationInFrames 是全片总帧数（Root calculateMetadata 事实源）。段界 = 本幕
  // 起点（顶部条 segSpans 的段 1 恰收在 [P0.from, P1.from)、末段吞到 total），
  // 故大条几何完全派生——段宽∝幕时长，与顶部条逐帧同构、零演示常数。
  const frame = useCurrentFrame();
  const {durationInFrames: total} = useVideoConfig();
  const f = scene.from + frame;
  const usable = BAR_W - SEG_GAP;
  const seg1W = (usable * scene.from) / total;
  const seg2W = usable - seg1W;
  const seg2Fill = clamp01((f - scene.from) / (total - scene.from));
  const headX = seg1W + SEG_GAP + seg2W * seg2Fill; // 播放头贴段 2 填充前沿
  return (
    <AbsoluteFill>
      <Sequence {...w('p1-01')} name="1-A 收束">
        <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', gap: 44}}>
          <FadeUp>
            <div style={{position: 'relative', width: BAR_W, height: BAR_H}}>
              <div style={{position: 'absolute', left: 0, top: 0, display: 'flex', gap: SEG_GAP}}>
                <Seg w={seg1W} fill={1} label={titleOf('P0')} />
                <Seg w={seg2W} fill={seg2Fill} label={titleOf('P1')} />
              </div>
              {/* 播放头：亮圆点 + bg 描边 + 辉光（绝对定位绕开 FadeUp 的 flex 布局） */}
              <div
                style={{
                  position: 'absolute',
                  left: headX - HEAD_R,
                  top: BAR_H / 2 - HEAD_R,
                  width: HEAD_R * 2,
                  height: HEAD_R * 2,
                  borderRadius: HEAD_R,
                  background: theme.text,
                  border: `3px solid ${theme.bg}`,
                  boxShadow: '0 0 18px rgba(242,245,250,0.5)',
                }}
              />
            </div>
          </FadeUp>
          <FadeUp delay={24}>
            <Pill color={theme.dim}>{'段宽 ∝ 幕时长'}</Pill>
          </FadeUp>
        </AbsoluteFill>
      </Sequence>
    </AbsoluteFill>
  );
};
