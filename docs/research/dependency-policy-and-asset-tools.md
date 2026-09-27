# 依赖最新版策略与外部资产工具选型：证据与方案比选

> **结论先行**：① 版本策略取「**模板统一精确钉版 + 使用时对照追新**」——Remotion 官方硬约束全家桶版本严格一致，混排 `^` 与精确钉版会在 `pnpm update` 后分叉（本仓模板正踩此隐患，随本条修复）；「每次使用最新稳定版」以**提醒面 + 追新协议**落地，不以「每集自动漂移」落地（会击穿 structured 门「系列内零依赖漂移」不变量）。② **HyperFrames 复核结论：不替代、不共用**，维持 negentropy 2026-09-04 调研 [1] 既定的「B 轨单集试点」观望；再评估触发器增补两条。③ **text-to-cad 适合以「按集 opt-in 的独立可选工具」引入**（仅装 cad 单 skill，GLB 直通 GLTFLoader 零转换链），不入默认流水线与模板。协议落点：[PIPELINE.md §九「依赖与版本策略」](../../references/PIPELINE.md)，[08「外部 CAD 资产」](../../references/08-remotion-implementation.md)（台账：[RSI-016](../.agents/issue.md)）。数据快照均为 2026-09-27 实测（两轮独立调研 + 对抗性复核，复核修正已并入正文）。

## 一、版本策略比选（G2）

### 1.1 现状与问题

模板 [package.json.tmpl](../../assets/video-skeleton/video/package.json.tmpl) 钉 `remotion`/`@remotion/cli` = `^4.0.0`、`@remotion/layout-utils`/`@remotion/media` = 精确 `4.0.512`（lockfile 实际全族 4.0.512）；SKILL.md/README 无任何「用最新版」指引。两个缺陷：**混排说明符**——Remotion 官方要求全部 `@remotion/*` 与 `remotion` 版本严格一致（`@remotion/three` 的 peerDependencies 对 remotion 是精确锁定 [2]），`pnpm update` 会把 `^4.0.0` 推进而精确钉不动，触发版本不一致错误；**策略缺位**——「优先最新版」从未成文，模板钉版会被读成「停留在旧版的许可」。

### 1.2 候选对比

| 方案 | 做法 | 判定 |
|---|---|---|
| A. 维持混排现状 | `^4.0.0` + 精确 4.0.512 | **否决**：`pnpm update` 后分叉（1.1），且版本态度不可读 |
| B. 全 caret（`^4.0.529`） | 跟随语义化版本自动升 | **否决**：`pnpm update` 静默漂移，击穿 structured 门「版本漂移会让 frozen TS 行为不同」的立论；全家桶四包仍可能被分批更新 |
| **C. 全精确钉版 + 追新协议（采纳）** | 四包统一精确钉撰写时最新稳定版（本次 4.0.529 [2]）；建集/装依赖前 `npm view remotion version` 对照；同 major 整组追新（工作区 `[[skeleton.drift]]` 登记或 RSI 升模板）；跨 major = 重启触发器走 RSI | **采纳**：确定性（同输入同渲染）与「最新版优先」由**协议**而非**说明符语法**承担；追新动作可见（diff + 登记），与 `go mod vendor` 式「物理副本 + 校验门」的既有治理同构（依据见 [skeleton.toml](../../assets/video-skeleton/skeleton.toml) 文件头） |

### 1.3 提醒面与口径

「每次使用时提醒客户端用最新版」落四处（只加指针不复制正文）：SKILL.md 工作流第 5 步注释与「关键不变量」、`scaffold.py` 建集结尾输出（动态打印模板实际钉版）、08 命令闭环、README 前置依赖表。Python 侧 `--with` 刻意不钉版（解析时取最新；uv 缓存命中沿用，强制刷新 `uv cache clean <pkg>`）——与 RSI 不变量 14「pyproject 无 `[project]`」同源。工具链（uv/pnpm/Node）以 README 地板为下限、始终用最新稳定版。

## 二、HyperFrames 复核：不替代、不共用（2026-09-27）

### 2.1 事实快照与三个月增量

HyperFrames（HeyGen，2026-03-10 建仓）："Write HTML. Render video. Built for agents."——纯 HTML/CSS + 可 seek 的 paused timeline（GSAP/Lottie/Three.js/WAAPI，注册到 `window.__timelines`）→ headless Chrome（Puppeteer）逐帧 + FFmpeg 编码，确定性渲染；**Apache-2.0**，无按次渲染费与商用门槛；无 React、无构建步骤（`index.html` 直接可播放）。生态对 agent 全押：21 个官方 agent skills（含 `/faceless-explainer`、`/embedded-captions`、`/media-use`——与本技能 ⑥–⑨ 阶段几乎同型）、MCP、非交互 CLI（init/lint/check/snapshot/preview/render/publish/doctor）、Docker/Lambda/Cloud Run/托管云 [4][5]。

| 指标 | 2026-09-04（negentropy 调研 [1]） | 2026-09-27（本次复核） |
|---|---|---|
| 版本 | 0.8.27 | **0.8.79**（2026-09-26；09-24–09-26 三个日历日连发 11 个 patch，0.8.69–0.8.79） |
| GitHub stars | 43.9k | **53.4k**（+21%） |
| 周下载 | — | 47.9 万（remotion 为 183 万） |
| 定性 | B 轨单集 PoC 候选（四门全过、字形验收留 POC） | **维持**：仍 pre-1.0、API 漂移风险真实 |

### 2.2 决定性论据

- **静默失败模式**：官方 rules-and-anti-patterns 自证——动画「look right in the live preview and still render wrong on a cold, non-linear render worker」（cold seek 隐藏态、GSAP `immediateRender`、SVG draw-on 失效），且两类坑官方明言 "carry no rule code"，须 prompt 层规避 [5]。对照 Remotion 的帧号纯函数模型「更简单、没有需要注册的时间线契约」（HyperFrames 官方对比页自认 [6]）。
- **负向知识清零成本**：本技能在 Remotion 上沉淀的 Sequence 局部时长陷阱、regioned Main 指纹、真实分集回归语料、抽帧 QA 门，构成「设计-实现-验证」闭环；换引擎 = 清零重积累。官方 `/remotion-to-hyperframes` 迁移 skill 自称约 80% 机械翻译、20%（useState/useEffect 状态机等）显式拒绝误译并双版本逐帧比对 [6]——侧面印证不完全兼容。
- **不共用双引擎**：时序 SSOT（timing.json 双语共读）、frozen 骨架 + verify_skeleton 字节门、manifest 驱动时间轴、QA 抽帧门整套体系均以「唯一渲染引擎」为前提；引入第二引擎制造的不是冗余备份而是双份事实源。
- **许可对照**（事实登记，非决策依据）：Remotion 为 source-available 自有许可，>3 人公司须 Company License [3]（[PIPELINE.md §八](../../references/PIPELINE.md) 已登记）；HyperFrames Apache-2.0。官方预告 **Remotion 5.0 将微调 license 条款**（升级窗口须复读 LICENSE）——若收紧，Apache-2.0 的合规吸引力上升，此为再评估触发器之一。

### 2.3 复核修正（对抗性审查产物）

初稿三处表述被复核修正：HyperFrames 诞生动机的「HeyGen 内部 agent 写 Remotion 痛苦」叙事**未核实**（官方原话仅 "inspired by Remotion"，本表以官方口径为准）；输出文件的 `hyperframes_renderer/version` 元数据标签官方自认 "unauthenticated hints"（可伪造可移除）——试点对拍**以抽帧像素为准**，不可当溯源证据；`logo sting` / `avatar-presenter` 等生态条目未逐一核实，不作为论据。

### 2.4 再评估触发器

① HyperFrames 发布 **1.0** 并做出 API 稳定承诺；② **Remotion 5.0 license 条款收紧**；③ B 轨试点（内容侧可选动作，3–5 人日四关验收：中文 TTS 对齐 / 字形 / audio-first 往返 / 与 Remotion 版抽帧对拍 [1]）实投并过四关。触发前主线不动。

## 三、text-to-cad 评估：按集 opt-in（2026-09-27）

### 3.1 事实快照

[earthtojake/text-to-cad](https://github.com/earthtojake/text-to-cad)（2026-04-22 建仓，16.4k★ / 1,380 commits / 2026-09-27 仍在推送，**MIT**）是 13–14 个制造域 agent skills 库（cad / cad-viewer / DXF / 工程图 / URDF / G-code 等，文档站 texttocad.dev）[7][8]。核心 `cad` skill 走**纯本地 Python 内核**：build123d（参数化 CAD 脚本）跑在 OCP（OpenCascade 绑定）之上，自研 CLI `cadgen`（PyPI，0.6.6，2026-09-21；**08-11–09-21 共 41 天 37 版**，churn 快）。`requirements.txt` 全文一行 `cadgen[snapshot]==0.6.6`；**零云 API、零 key**（唯一外联在 step-parts 的 `api.step.parts` 目录检索与制造类 skill——只装 cad 单 skill 即避开）。Windows 的 OCP DLL 拦截问题不影响 macOS。

### 3.2 与 Remotion 的落地面（复核确认可行）

建模侧直接写 **GLB-only 模型**（单 `@glb` 装饰器；官方 supported-exports 明言 mesh-only 是一等公民、面向 render asset，"STEP is one output kind, not the primary"，且 glTF 2.0 **每个零件/面颜色一个材质**——build123d 着色可带入）[9] → `cadgen glb build` 产 GLB → three.js `GLTFLoader` 原生直载，**零转换链**（STL 路线无颜色、STEP 不可直载，均不必走）。`cadgen … snapshot` 出 PNG 可作 staticFile 静帧。复核修正两点：社区惯用的 `useGLTF` 在 **drei**（非 fiber）——而 drei 是 08 既有禁引依赖，故本技能口径为 GLTFLoader；`cadgen glb build --animation` 可烘焙平移/旋转 glTF 动画，但逐帧确定性与 beat 对齐仍以 Remotion 代码驱动为正路。

### 3.3 引入形态比选

| 方案 | 判定 |
|---|---|
| 常驻依赖（进模板/pyproject） | **否决**：信源画像（论文/文档/代码/课程站）与制造级 CAD 交集极小；OCP+build123d+cadgen 约 70–80 MB 边际体积（playwright 非预装：archify 图解录制同经 `uv run --with playwright` 按需解析，浏览器启动系统 Chrome）+ `build123d<0.12` 钉版 churn；着色与动画主战场仍在 three.js 层——CAD 只贡献几何（RSI 不变量 14） |
| 固化为 Stage ⑧ 子步骤 | **否决**：给低频需求设常驻流程面，制造噪声触发 |
| **按集 opt-in 独立工具（采纳）** | `npx skills add earthtojake/text-to-cad --skill cad` 只装单 skill（skills CLI `-s/--skill` 通道 [10]；整库会污染窄域触发且 step-parts 有云端外联）；须过 08 既有 3D 三条宪法（宪法 1 放宽为「曲面只许来自 CAD、手搭仍守直角体词表」；颜色仍归 theme 层覆写材质、零光源；相机零动画）与「同帧 PNG 逐字节相同」验收；依赖按集临时装用完可卸，风险面为零（MIT、本地、无 key）→ 随时可补装，不需预摊 |

边界：DXF / 工程图 PDF 不进流水线（工程图风格直接 SVG 重绘，与「资产可代码复现」哲学同向——01 规格图片纪律本就禁外采素材，本地生成不在此列）。

## 四、撤销条件与已知局限

- 版本策略：若 Remotion 官方改变「全家桶同版本」约束或推出锁文件外的版本对齐机制，重审 1.2；追新协议的 drift 登记若在实践中高频出现（模板追平滞后成为常态），考虑把「模板追新」固化为发版前检查项。
- HyperFrames：见 2.4 触发器；本仓不实施试点（内容侧动作）。
- text-to-cad：若出现稳定「硬件解说」内容线且 opt-in 频繁，再评估写入 SKILL.md 可选工具附录的更深集成；cadgen 若引入云依赖或改许可，立即重审。

## 参考文献

[1] ThreeFish-AI, "动效建模与 Web 可视化搭建工具调研（160-video-motion-modeling-web-visual-tooling）," negentropy docs/research. [Online]. Available: https://github.com/ThreeFish-AI/negentropy/blob/master/docs/research/video-production/160-video-motion-modeling-web-visual-tooling.md（数据快照 2026-09-04）

[2] Remotion, "remotion / @remotion/cli / @remotion/three," npm registry（version / peerDependencies / time / dist-tags，实测 2026-09-27：latest = 4.0.529，2026-09-25 发布；@remotion/three peer 对 remotion 精确锁定）. [Online]. Available: https://www.npmjs.com/package/remotion

[3] Remotion, "Remotion License." [Online]. Available: https://www.remotion.dev/docs/license ；FAQ：https://www.remotion.dev/docs/license/faq ；定价：https://www.remotion.dev/docs/license/pricing

[4] HeyGen, "HyperFrames," GitHub repository（README：Apache-2.0、"Built for agents"、生态与部署路径、"HyperFrames vs Remotion" 节 "Remotion's bet is React components; HyperFrames' bet is plain HTML"；实测 2026-09-27：0.8.79、53,356 stars、2026-03-10 建仓）. [Online]. Available: https://github.com/heygen-com/hyperframes

[5] HeyGen, "Rules and anti-patterns," HyperFrames Docs（静默失败机制与 lint 边界的官方自述）. [Online]. Available: https://hyperframes.heygen.com/prompting/rules-and-anti-patterns ；rendering：https://hyperframes.heygen.com/guides/rendering

[6] HeyGen, "HyperFrames vs Remotion," HyperFrames Docs（官方对比页：Remotion 帧号模型 "One pure function of the frame number, no timeline to register, no contract to get subtly wrong"；迁移 skill 的 80/20 边界 "Roughly 80% of a typical composition translates mechanically"）. [Online]. Available: https://hyperframes.heygen.com/guides/hyperframes-vs-remotion

[7] J. Fitzgerald (earthtojake), "text-to-cad," GitHub repository（实测 2026-09-27：16,401 stars、MIT、2026-04-22 建仓；skills 清单与安装通道）. [Online]. Available: https://github.com/earthtojake/text-to-cad

[8] J. Fitzgerald, "cadgen," PyPI（requires_dist：build123d<0.12,>=0.11.1、cadquery-ocp-novtk<8,>=7.9 等；requires_python ≥3.11；37 releases / 首发至 0.6.6 实测；license_expression: MIT——PEP 639 元数据，项目页据此显示）. [Online]. Available: https://pypi.org/project/cadgen/

[9] J. Fitzgerald, "Supported exports," text-to-cad skills/cad/references（"STEP is one output kind, not the primary"；glTF 2.0 Y-up、"one material per distinct part/face color"；`--animation` 通道）. [Online]. Available: https://github.com/earthtojake/text-to-cad/blob/main/skills/cad/references/supported-exports.md

[10] Vercel Labs, "skills," npm CLI（`-s, --skill <skills...>` 单 skill 安装通道，v1.7.0 实测）. [Online]. Available: https://github.com/vercel-labs/skills
