// Quickstart 最小场景组件（根 README「快速上手」的 cp 源）。
// 动效全部来自 frozen 运动层与 cards 原语：FadeUp = spring 淡入上移，delay 做错峰。
// 开场形态对齐 06「开篇首镜视听合力定式」（RSI-039）：首秒是高反差 accent 视觉锚
// 快速弹簧入场，不是静止文字墙——frozen 词表内无冲击原语，模板级升级须动
// skeleton + 全集同步（另走 RSI），故以 oversized accent Pill 作核心意象；
// 真实制作规格见 references/08-remotion-implementation.md。
// 解析器契约：`const w = (fromId, toId?) => beatWindow(...)` 与 at() 的字面形态勿改
// （check_script.py 的 SCENE_CALL_RE 只认 w('id','id')）。
import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {FadeUp, Pill} from '../components/cards';
import {theme} from '../design/theme';
import {beatWindow} from '../timing';
import type {SceneRange} from '../types';

export const P0: React.FC<{scene: SceneRange}> = ({scene}) => {
  const w = (fromId: string, toId?: string) => beatWindow(scene.sentences, scene.from, fromId, toId);
  const at = (id: string) => w(id).from; // 时点锚：只取某句起始帧
  const bA = w('p0-01', 'p0-02');
  const say02 = at('p0-02') - bA.from; // 第二句起点（Sequence 相对帧），Pills 由此错峰入场
  return (
    <AbsoluteFill>
      <Sequence {...bA} name="0-A 开场">
        <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center', gap: 56}}>
          {/* 首秒核心意象：oversized accent 锚（ok 绿对深底高反差）快速入场，非静止文字卡 */}
          <FadeUp>
            <Pill
              color={theme.ok}
              style={{fontSize: 56, fontWeight: 700, padding: '20px 48px'}}
            >
              to-video
            </Pill>
          </FadeUp>
          <div style={{display: 'flex', gap: 24}}>
            <FadeUp delay={say02}>
              <Pill color={theme.text}>1080p30 终渲</Pill>
            </FadeUp>
            <FadeUp delay={say02 + 12}>
              <Pill color={theme.ok}>声音克隆</Pill>
            </FadeUp>
            <FadeUp delay={say02 + 24}>
              <Pill color={theme.dim}>全代码动画</Pill>
            </FadeUp>
          </div>
        </AbsoluteFill>
      </Sequence>
    </AbsoluteFill>
  );
};
