// Quickstart 第二幕场景组件（根 README「快速上手」的 cp 源，与 P0.tsx 配套）。
// 画面与口播互补：口播说「顶部进度条」，画面把它放大解剖——中央大条与顶部
// ChapterProgress 逐帧同步（段界/填充全部由真实时间轴派生，零演示常数；
// 全片总长按两幕 quickstart 的末幕恒等式推导，见组件体注释）。
// 动效仍来自 frozen cards 原语（FadeUp 错峰）；单句幕用 w('p1-01')——解析器
// 契约见 P0.tsx 头注（check_script.py 的 SCENE_CALL_RE 第二参可选）。内容垂直
// 居中 y≥56 起（顶部 y<56 安全带归章节进度条，references/06 红线 2b）。
import React from 'react';
import {AbsoluteFill, Sequence, useCurrentFrame} from 'remotion';
import {FadeUp, Pill} from '../components/cards';
import {theme} from '../design/theme';
import {beatWindow} from '../timing';
import type {SceneRange} from '../types';
import chaptersJson from '../chapters.json';
import timingJson from '../timing.json';

type Chapter = {scene: string; title: string};
const CHAPTERS = chaptersJson as Chapter[];

/** timing.ts 的 LEAD_IN/ TAIL_SEC 属 A 档 frozen 未导出，就地读同一 timing.json
 *  SSOT 同式派生——改时序常量只改 json，此处自动跟随。 */
const FPS = timingJson.fps;
const LEAD_IN_FRAMES = Math.round(timingJson.leadInSec * FPS); // = scenes[0].from
const TAIL_FRAMES = Math.round(timingJson.tailSec * FPS); // 片尾静默（不在任何幕内）

// 放大档几何：顶部章节条（components/ChapterProgress.tsx，frozen）的讲解版——
// 同一设计语言（panelBorder 轨道 / text@0.9 填充 / 双层同位文字裁切，无播放头），
// 只放大尺寸便于讲解。
const BAR_W = 1180;
const BAR_H = 48;
const SEG_GAP = 12; // 顶部条 8px 的放大档
const TITLE_SIZE = 30;
const TITLE_PAD_X = 24;

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
 *  填充 + bg 深字）——文字色随填充前沿揭示翻转，同顶部条状态机。 */
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
  // 全片进度：Sequence 内 useCurrentFrame 是本幕局部帧，+scene.from 还原全局帧。
  // 全片总长走末幕恒等式（勿用 useVideoConfig().durationInFrames——Sequence
  // 内被覆盖为本幕局部时长，取到 118 而非 522，段宽会溢出画布）。段界 = 本幕
  // 起点（顶部条 segSpans 段 1 恰收 [P0.from, P1.from)、末段吞到 total）；段宽
  // 比与顶部条逐帧同构——顶部条以 scenes 时间轴为基（[P0.from, total)，片头
  // 静默不在 strip 内），分子分母同剔 leadIn。零演示常数。
  const frame = useCurrentFrame();
  const f = scene.from + frame;
  const usable = BAR_W - SEG_GAP;
  const total = scene.from + scene.durationInFrames + TAIL_FRAMES; // 末幕恒等式
  const stripTotal = total - LEAD_IN_FRAMES; // 顶部条归一化基：scenes 时间轴全长
  const seg1W = (usable * (scene.from - LEAD_IN_FRAMES)) / stripTotal;
  const seg2W = usable - seg1W;
  const seg2Fill = clamp01((f - scene.from) / (total - scene.from));
  return (
    <AbsoluteFill>
      <Sequence {...w('p1-01')} name="1-A 收束">
        <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', gap: 44}}>
          <FadeUp>
            <div style={{display: 'flex', gap: SEG_GAP}}>
              <Seg w={seg1W} fill={1} label={titleOf('P0')} />
              <Seg w={seg2W} fill={seg2Fill} label={titleOf('P1')} />
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
