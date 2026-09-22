// Quickstart 最小场景组件（根 README「快速上手」的 cp 源）。
// 真实制作中场景是创作主体，规格见 pipeline/skills/06-remotion-implementation.md。
import React from 'react';
import {AbsoluteFill, Sequence} from 'remotion';
import {theme} from '../design/theme';
import {beatWindow} from '../timing';
import type {SceneRange} from '../types';

export const P0: React.FC<{scene: SceneRange}> = ({scene}) => {
  const w = (fromId: string, toId?: string) => beatWindow(scene.sentences, scene.from, fromId, toId);
  const bA = w('p0-01', 'p0-02');
  return (
    <AbsoluteFill style={{justifyContent: 'center', alignItems: 'center'}}>
      <Sequence {...bA} name="0-A 开场">
        <div style={{color: theme.text, fontSize: 72, fontFamily: theme.sans}}>
          你好，to-video
        </div>
      </Sequence>
    </AbsoluteFill>
  );
};
