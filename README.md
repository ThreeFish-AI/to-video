# to-video

> 读透一份信源，交付一支 1080p30 的科普视频——由 AI Agent 执行、人做评审决策的九阶段流水线。

**to-video** 是一个可安装的 agent skill（Claude Code 等）加 Python / Remotion 工具链：把「信源精读 → 逐字稿 → 配音 → 代码动画 → 终渲」固化为九个带通过门的阶段。内容层四个写作阶段产出**可回溯的逐字稿**（每句口播都能落到信源证据），生产层五个工具阶段完成声音克隆配音、React 场景动画、抽帧质检与终渲交付。全片派生自文本单一事实源——改稿后 `build → tts → render` 一条链重跑，全程不打开任何剪辑软件。

## 一、九阶段流水线

![九阶段双层流水线：内容层（文档驱动）① 信源精读取证 → ② 策划案 → ③ 逐字稿单一事实源 → ④ 双重校验 → ⑤ 分镜表；生产层（工具驱动）由 ③ 下行 ⑥ TTS 合成、由 ⑤ 下行 ⑦ Remotion 场景实现，二者汇合经 ⑧ 草渲 + 抽帧 QA 迭代修正，最终 ⑨ 终渲交付 1080p30](docs/assets/architecture/influence--pipeline-layers-dark.png)

①–⑤ 为**内容层**（写作产物，由人/代理撰写），⑥–⑨ 为**生产层**（由工具执行）：

| 阶段 | 产出 · 通过门 |
| --- | --- |
| ① 信源精读取证 | 取证笔记——全部口播断言可回溯，RISKY=0（A 型论文 / B 型文档·代码·站点） |
| ② 策划案生成 | `planning.md` 六节齐，含本集视觉契约 |
| ③ 逐字稿写作 | `narration.md`（全片单一事实源），`build` 派生 narration.json |
| ④ 双重校验 | 真实性 + 易懂性双门（`check`），RISKY=0 且 REWRITE=0 |
| ⑤ 分镜表生成 | 镜号 ↔ 句区间 ↔ 画面 ↔ 动效，beat 覆盖无缺句（`check`） |
| ⑥ TTS 配音 | 逐句 mp3 + 时长 manifest（`tts`，幂等续跑），`captions` 导出 srt/vtt |
| ⑦ Remotion 场景实现 | React 场景组件、全代码动画，tsc 零错误 + 七条渲染红线 |
| ⑧ 草渲 + 抽帧 QA | 半分辨率 draft.mp4 + 抽帧自动体检（`render` / `qa`），零 FAIL |
| ⑨ 终渲与交付 | 1080p30 final.mp4（`render --final`），实测时长落在预算窗内 |

九阶段的声明源是 [`pipeline/stages.toml`](pipeline/stages.toml)，本表是它的人读视图。

## 二、它能做出什么

- **IndexTTS-2.5 声音克隆配音**：用 10–14 秒干净样本克隆你自己的音色，风格档控制语气；样本先经勘探（F0 / 起伏 / 音节率）与保真度验收（削波 / 底噪 / 动态）再上台。逐句内容寻址缓存，断点续跑零重复合成。无本地模型时可用 edge 预置音色兜底。
- **Remotion 全代码动画**：每个画面是一个 React 场景组件——可 review、可 diff、可编程复渲；frozen 运动层提供跨集一致的时序语汇（时长令牌 / 缓动 / 弹簧 / 错峰），主题与构图每集独立设计。
- **抽帧 QA 门**：草渲后按幕 / 句 / 末 N 句抽帧，自动体检黑帧、重复帧、安全区侵入与字幕 WCAG 对比度，零 FAIL 才放行终渲——把「渲染缺陷靠肉眼全程盯」压缩为「机器点名 + 定点目检」。
- **archify 动效图例**：架构图（archify 技能产物，见「相邻技能」）逐章录制为视频动效；覆盖门按句级锚定率执法「图与口播互证」，整幕零锚定即 FAIL。
- **字幕导出**：srt / vtt 双格式，cue 终点不含句间停顿——外挂字幕的静默期不留残字。
- **1080p30 终渲交付**：音频 manifest 驱动全片时间轴，零手工对轨；时序常数单一事实源（timing.json），TS 与 Python 两侧共读，双语言镜像漂移结构性不存在。

## 三、前置条件

| 依赖 | 说明 |
| --- | --- |
| macOS 渲染主机 | 场景字体走系统 CJK 字体栈（PingFang SC / Songti SC / SF Mono），未内嵌字体文件，渲染与抽帧 QA 仅支持 macOS |
| [uv](https://docs.astral.sh/uv/) | 运行全部 Python 脚本（`uv run --no-project --with …` 按需取依赖，无需预装环境） |
| pnpm ≥ 12 | 分集 Remotion 工程的依赖安装（workspace 隔离与构建脚本许可已按 pnpm 12 行为配好） |
| Node ≥ 23.6 | 运动层单测用 `node --test` 原生跑 TS |
| （可选）IndexTTS-2.5 本地服务 | 声音克隆后端（默认 `127.0.0.1:8766`），部署见 [pipeline/VOICE-CLONING.md](pipeline/VOICE-CLONING.md) §二 |

## 四、安装

```bash
git clone https://github.com/ThreeFish-AI/to-video ~/projects/to-video
ln -s ~/projects/to-video ~/.claude/skills/to-video
```

- **多宿主共享**：把同一 clone 再链到 `~/.agents/skills/to-video`——包装器脚本的解析序为 `TO_VIDEO_HOME` → `~/.claude/skills/to-video` → `~/.agents/skills/to-video`。
- **任意安装位置**：设 `TO_VIDEO_HOME=<clone 根>` 覆盖默认解析。
- 装完**重启 Claude Code 会话**（技能在会话启动时扫描装载）。
- 也可用 [vercel-labs/skills](https://github.com/vercel-labs/skills) CLI 安装：`npx skills add ThreeFish-AI/to-video`。

## 五、Quickstart

变量约定（完整定义见 [pipeline/README.md](pipeline/README.md) 路径变量一节）：`$T` = skill 根（安装位置），`$W` = 内容工作区根，`$P` = 分集工程，`$V` = 音色样本目录（本例用 edge 引擎，用不到）。

```bash
T=~/.claude/skills/to-video
W=~/my-videos
P=$W/episodes/hello-video
V=$W/voices

# 1) 初始化内容工作区（幂等：哨兵 + series.json + voices/ + 工作区包装器）
uv run --no-project $T/pipeline/scripts/scaffold.py --init-workspace $W

# 2) 建集脚手架（在 $W 内执行，脚本靠哨兵 .to-video-root 定位工作区）
cd $W
uv run --no-project $T/pipeline/scripts/scaffold.py hello-video --title "你好 to-video"

# 3) mini 篇幅调整：改用 edge 预置音色（免本地模型与声音样本，需联网）
#    + 把时长预算窗缩到两句话的量级（用自己的声音克隆见 pipeline/VOICE-CLONING.md）
sed -i '' -e 's/^engine = "indextts"/engine = "edge"/' \
          -e 's/^target_minutes = .*/target_minutes = [0.1, 2.0]/' "$P/pipeline.toml"

# 4) 写 mini 逐字稿（narration.md 是全片单一事实源；`## P0 幕名` + 一句一行）
cat > "$P/script/narration.md" <<'EOF'
## P0 开场

- [p0-01] 你好，这是用 to-video 流水线做出的第一支视频。
- [p0-02] 画面、配音、字幕，全部由代码生成。
EOF

# 5) 写 mini 分镜表（check 门要求每个 beat 的句区间覆盖本幕全部句子）
cat > "$P/script/storyboard.md" <<'EOF'
| 镜号 | 句区间 | 画面 | 动效 |
| --- | --- | --- | --- |
| 0-A | p0-01..p0-02 | 居中标题卡 | FadeUp |
EOF

# 6) 写一个最小场景组件（真实制作中场景是创作主体，规格见 pipeline/skills/06）
cat > "$P/video/src/scenes/P0.tsx" <<'EOF'
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
EOF
#    再在 $P/video/src/Main.tsx 注册：顶部加 `import {P0} from './scenes/P0';`，
#    并给刻意留空的 SCENE_COMPONENTS 表填一行 `P0: P0,`（键 = 幕名）。

# 7) ③④⑤ 内容流水线：逐字稿派生 + 内容门（时长预算 / 分镜覆盖 / 读法陷阱）
uv run --no-project $W/scripts/pipeline.py --project $P build
uv run --no-project $W/scripts/pipeline.py --project $P check

# 8) ⑥ 配音（edge 引擎按分集包装器契约直调，两句秒级；声音克隆走
#    `pipeline.py tts`——参数取自 pipeline.toml，长跑前先 `tts --plan` 对账 ETA，
#    见 pipeline/VOICE-CLONING.md §五）
cd "$P" && uv run --no-project --with edge-tts --with mutagen scripts/tts.py

# 9) ⑧ 草渲 + 抽帧体检（先装分集依赖：video/ 自带 pnpm-workspace.yaml 自锚 + 构建脚本
#    许可，裸 pnpm install 即可，勿加 --ignore-workspace——那会连本工程自己的
#    pnpm-workspace.yaml 一并忽略，esbuild 许可失效；产物在 $P/out/draft.mp4）
cd "$P/video" && pnpm install
cd "$W"
uv run --no-project $W/scripts/pipeline.py --project $P render
uv run --no-project $W/scripts/pipeline.py --project $P qa --video out/draft.mp4 --last-n 2 --check
```

全绿后交付：`captions` 导出 srt/vtt，`render --final` 出 `out/final.mp4`。随时可用 `status`（阶段新鲜度）与 `doctor`（环境自检）定位问题。真实制作的完整清单（信源取证、series.json 登记、概念色设计）见 [pipeline/README.md](pipeline/README.md)。

## 六、文档地图

| 文档 | 内容 |
| --- | --- |
| [pipeline/README.md](pipeline/README.md) | 机制 SSOT：脚本清单、pipeline.toml 字段表、路径变量约定、复用边界 |
| [pipeline/skills/](pipeline/skills/) | 九阶段规格（`01`–`09` 每阶段一份，可直接作为子代理 prompt） |
| [pipeline/VOICE-CLONING.md](pipeline/VOICE-CLONING.md) | 声音克隆操作与参数：部署、样本、风格档、合成、缓存、排障 |
| [pipeline/INDEXTTS-2.5-ADVANCED.md](pipeline/INDEXTTS-2.5-ADVANCED.md) | 上游能力面与进阶：机制循证、配音质量提升路线图 |
| [pipeline/PRON-GLOSSARY.md](pipeline/PRON-GLOSSARY.md) | 易错字台账：发音标注（`<原文|读音>`）跨集复用表 |

## 七、相邻技能

同一作者的配套技能，与本流水线互补：

- **/guided-learn** —— 信源精读方法论（Stage ① 的上游能力：前置体检、先梳理后总结、费曼考评闭环）
- **/archify** —— 架构 / 流程图绘制与动效录制（Stage ⑦ 的图例资产来源，覆盖门的消费对象）

## 八、许可与合规

- **本仓代码**：[MIT](LICENSE)。
- **Remotion**：免费限于个人与不超过 3 人的公司；超过 3 人的公司需购买 [Remotion 公司许可证](https://www.remotion.com/license)。
- **IndexTTS-2.5**：按 [bilibili 模型使用许可](https://github.com/index-tts/index-tts/blob/main/LICENSE)发布——个人 / 研究用途可用，商用需联系 indexspeech@bilibili.com（详见 [pipeline/VOICE-CLONING.md](pipeline/VOICE-CLONING.md) §八）。
- **edge-tts**：微软在线语音接口；发布前请确认目标平台对合成语音的标注要求。
- **声音权利**：克隆他人声音必须取得本人书面授权。声音样本是生物特征：样本目录整目录 gitignored，仓库只存指纹（refs.toml）。

## 九、致谢

本仓自 [ThreeFish-AI/negentropy](https://github.com/ThreeFish-AI/negentropy)（Apache-2.0）的 `apps/negentropy-influence/pipeline/` 抽取为独立技能，并沿用其 2026-08–2026-09 的流水线演化成果：单文件 Canvas 制作包 → Remotion 工程模式 → 九阶段门禁化 → 双锚点独立技能。

**tts-store 迁移提示**：合成缓存默认目录已迁至 `~/Library/Application Support/to-video/tts-store`；旧目录（`~/Library/Application Support/negentropy-influence/tts-store`）存在时自动回退使用，零配置、零缓存失效。想彻底搬走旧缓存可：

```bash
mv ~/Library/Application\ Support/negentropy-influence/tts-store \
   ~/Library/Application\ Support/to-video/tts-store
```

（若新目录已被创建，先用 `rsync -a` 合并内容再删除旧目录，勿直接 `mv` 套娃。）
