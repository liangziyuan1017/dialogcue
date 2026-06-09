# Global Skills Manifest

Shared reference patterns callable by any module's workflow. Each skill is a standalone SKILL.md with YAML frontmatter for trigger-based matching.

## How the Agent Uses This

1. **Read this manifest** to discover available skills
2. **Match task keywords** against Description, Use When, and Triggers columns
3. **Read the matching SKILL.md** directly at the path listed
4. **Apply the methodology** described in the skill body

---

## collaboration

| Skill | Path | Description | Use When | Not For | Output | Triggers |
|-------|------|-------------|----------|---------|--------|----------|
| **cross-cat-handoff** | `global_skills/collaboration/cross-cat-handoff/SKILL.md` | Task handoff protocol using the 5-part structure（What/Why/Tradeoff/Open/Next） | 交接工作、传递信息、写 review 请求。 | 自己的任务、不需要交接的工作。 | 结构化交接/通信。 | task handoff, communicate change |
| **expert-panel** | `global_skills/collaboration/expert-panel/SKILL.md` | Structured Multi-Perspective Analysis — single agent analyzes problem from mu... | 技术趋势判断、竞品分析、行业事件分析、需要多视角决策支持、Human说"帮我分析一下"。 | 简单问题（直接回答）、代码实现、bug fix、日常聊天。 | Multi-perspective analysis report with WHY-chain (Evidence/Reasoning/So What/... | 帮我分析一下, expert panel, 技术参谋, 竞品分析, 行业分析, 趋势判断, 多视角分析, showcase |
| **collaborative-thinking** | `global_skills/collaboration/collaborative-thinking/SKILL.md` | 单人或multi-agent的创意探索、独立思考、讨论收敛 | brainstorm、multi-agent独立思考、讨论结束需要收敛、方向性问题需要多视角。 | 已有明确 spec 直接写代码、单猫执行已定方案。 | 收敛报告（共识/分歧/行动项）+ 三件套沉淀检查。 | brainstorm, 讨论, multi-agent独立思考, 收敛, 讨论结束, 总结一下 |
| **cross-thread-sync** | `global_skills/collaboration/cross-thread-sync/SKILL.md` | cross-session 协同：发现平行 session → 通知（3+2 件套）→ 争用协调 → 确认 | 平行 session 之间需要协同、通知改动影响、共享文件争用。 | cross-check工作交接（用 cross-cat-handoff）。 | cross-post 通知 + 争用协调完成。 | 通知另一个 session, cross-session, 平行世界, parallel session sync, 另一只agent, cross-thread |

## knowledge

| Skill | Path | Description | Use When | Not For | Output | Triggers |
|-------|------|-------------|----------|---------|--------|----------|
| **knowledge-engineering** | `global_skills/knowledge/knowledge-engineering/SKILL.md` | Agent指导外部项目文档重构 — AI FDE 知识工程方法论 | Agent部署到外部项目、用户项目缺少结构化文档、需要知识工程指导、冷启动理解业务。 | cat-cafe 项目自身开发、已有完善 docs/ 结构的项目（直接用 CatCafeScanner）。 | 文档现状诊断 + 路径选择 + 三层知识注入建议 + 文档骨架模板。 | 知识工程, 文档重构, 外部项目, knowledge engineering, 冷启动, AI FDE, 帮我整理文档 |
| **deep-research** | `global_skills/knowledge/deep-research/SKILL.md` | 多源深度调研管道（Web Deep Research + Coder 合成 + 云端模型咨询） | 技术问题需要多源调查、设计决策需要证据、Human说"调研"/"research"、需要咨询云端模型。 | 简单搜索（直接用 WebSearch）、已有结论的确认。 | 调研报告 + 证据合成 或 咨询文档（含回填区）。 | 调研, research, 深度研究, 问一下 GPT Pro, 咨询云端 |
| **self-evolution** | `global_skills/knowledge/self-evolution/SKILL.md` | Scope Guard + Process Evolution + Knowledge Evolution — 主动护栏与自我进化 | Human scope 发散偏离愿景、同类错误反复出现、SOP 流程缺口、有价值的知识/方法论值得沉淀。 | 日常 SOP 推进（正常执行）、一次性个案 bug fix。 | Scope Guard Log 记录 / Evolution Proposal 提案 / Episode Card → Method/Skill 蒸馏 →... | — |

## quality

| Skill | Path | Description | Use When | Not For | Output | Triggers |
|-------|------|-------------|----------|---------|--------|----------|
| **incident-response** | `global_skills/quality/incident-response/SKILL.md` | 不可逆事故发生后的应急响应：情绪急救 → 止损 → 补偿性劳动 → 教训沉淀 | 犯了不可挽回的错误、造成了人类伙伴的情绪波动、需要危机处理。 | 可撤销的小失误、日常 bug fix（用 debugging）、预防性确认（用 shared-rules 铁律）。 | 情绪修复 + 止损行动 + 教训沉淀（lessons-learned / shared-rules）。 | 闯祸了, 搞砸了, 不可挽回, 犯了大错, incident, 对不起, 怎么补救, 人很难过 |
| **debugging** | `global_skills/quality/debugging/SKILL.md` | 系统化 bug 定位：根因调查 → 模式分析 → 假设验证 → 修复 | 遇到 bug、测试失败、unexpected behavior。 | 新功能开发、重构、已知原因的简单修复。 | Bug report（5件套）+ 根因 + 修复（含回归测试）。 | bug, 报错, test failure, unexpected behavior |

## meta

| Skill | Path | Description | Use When | Not For | Output | Triggers |
|-------|------|-------------|----------|---------|--------|----------|
| **writing-skills** | `global_skills/meta/writing-skills/SKILL.md` | 创建或修改 Cat Café skill / MCP tool description 的元技能（含质量标准、范本、发布） | 写新 skill、修改现有 skill、写/改 MCP tool description、验证 skill 质量； 或者功能实现中产出了 SKILL.md / global_skills/ 新目... | 使用 skill（直接触发对应 skill）。 | 新/更新的 SKILL.md + manifest 条目 + symlinks。 GOTCHA: 软硬同重——skill/MCP 质量 = 代码质量，写之... | 写 skill, 新 skill, 修改 skill, SKILL.md, global_skills/, manifest.yaml skill, 创建 hook, 新增 hook, 写 MCP, MCP description |

## creative

| Skill | Path | Description | Use When | Not For | Output | Triggers |
|-------|------|-------------|----------|---------|--------|----------|
| **rich-messaging** | `global_skills/creative/rich-messaging/SKILL.md` | 富媒体消息：语音、图片、卡片、清单、代码 diff、交互选择 | 发语音、发图、发卡片、展示结构化信息、让用户选、确认操作。 | 纯文字聊天、技术讨论、日常回复。 | rich block 附着在消息上。 | 发语音, voice, audio, 发图, 截图, 发个卡片, rich block, checklist, 让我选, 确认一下 |
| **video-forge** | `global_skills/creative/video-forge/SKILL.md` | 视频制作全链路：素材入库 → 剧本冻结 → 全局配音 → 对齐 → 渲染 → 审查 → 交付 | 做视频、做 showcase、做教程视频、录屏剪辑、video review。 | 纯代码开发（用 worktree/tdd）、纯文档写作、PPT（用 ppt-forge）。 | 视频成片 + 审查通过 + 可发布。 | — |
| **image-generation** | `global_skills/creative/image-generation/SKILL.md` | 通过浏览器自动化在 AI 平台上生成图片并下载 | 需要 AI 生成概念图、UI 参考、像素画素材。 | 已有图片的展示、SVG 图标制作（手写或用设计工具）。 |  | — |
| **ppt-forge** | `global_skills/creative/ppt-forge/SKILL.md` | PPT 制作全链路：内容规划 → 风格定调 → Slide 制作 → 视觉审查 → 导出验证 → 交付 | 做 PPT、做演示文稿、做 slide、做海报、PPT review、视觉审查。 | 纯代码开发（用 worktree/tdd）、纯文档写作（直接写）。 | 高密度 HTML slide + 自查通过 + 导出验证。 | — |
| **pencil-design** | `global_skills/creative/pencil-design/SKILL.md` | 使用设计工具创建/编辑设计文件，或导出为前端代码 | 设计 UI、编辑设计稿、从设计稿生成代码。 | 纯代码实现（无设计稿）、非设计工具的设计工作。 | 设计文件 或 前端组件代码。 | pencil, .pen 文件, 设计稿 |

## guides

| Skill | Path | Description | Use When | Not For | Output | Triggers |
|-------|------|-------------|----------|---------|--------|----------|
| **guide-authoring** | `global_skills/guides/guide-authoring/SKILL.md` | 标准引导流程设计 SOP：场景识别 → YAML 编排 → 标签标注 → 注册发现 → 测试验证 | 新建引导流程、添加场景引导、维护 Guide Catalog、编写引导 YAML。 | 使用引导（用户侧）、Guide Engine 代码实现（用 tdd）、视觉设计（用 pencil-design）。 | Flow YAML + tag-manifest 更新 + registry 注册 + CI 校验通过。 | 新建引导, 添加场景引导, 写引导流程, guide authoring, 引导 YAML |
| **bootcamp-guide** | `global_skills/guides/bootcamp-guide/SKILL.md` | Onboarding guide structure — reference pattern for new user orientation | designing onboarding flows for new users | experienced users, regular development |  | bootcamp, 训练营, 我是新手 |
| **guide-interaction** | `global_skills/guides/guide-interaction/SKILL.md` | 场景引导交互模式：当用户在询问某项功能的使用/配置流程时，判断该直接解释还是进入交互引导 | 系统注入了引导状态，或用户明确在问某项功能怎么操作。 | 普通闲聊、代码实现、没有流程诉求的概念讨论。 |  | 引导流程, 怎么配置, 怎么操作 |


## browser

| Skill | Path | Description | Use When | Not For | Output | Triggers |
|-------|------|-------------|----------|---------|--------|----------|
| **browser-preview** | `global_skills/browser/browser-preview/SKILL.md` | Hub 内嵌浏览器预览 localhost 应用 | 写前端代码、跑 dev server、需要看页面效果、调 UI、Human说"看看效果"。 | 后端纯 API 开发、不涉及页面的工作。 | 前端页面在 Hub browser panel 中实时预览。 | 看效果, 看看页面, preview, 浏览器预览, 打开浏览器, project-pkg-mgr dev, dev server, localhost, 前端效果, 看看 UI |
| **schedule-tasks** | `global_skills/browser/schedule-tasks/SKILL.md` | 定时任务注册、管理、能力指南。支持周期任务和一次性延迟任务 | 用户想设定时任务、定期提醒、周期巡检、定时发送内容、延迟执行一次性操作。 | 已有 builtin 任务的手动触发。 | 注册/管理定时任务，任务到点wake agent to execute。 | 定时, 每天, 每小时, 每隔, 提醒我, remind me, schedule, cron, 定期, 周期 |
| **browser-automation** | `global_skills/browser/browser-automation/SKILL.md` | 浏览器工作流总路由：为外部网站浏览、登录态流程、浏览器自动化、证据采集选择合适后端 | 需要操作外部网站、登录页、JS 重页面、需要浏览器，或需要在多种浏览器工具之间路由。 | localhost 页面预览（用 browser-preview）、简单网页抓取/搜索。 | 选定浏览器后端 + 执行路径 + 证据/结果。 | 浏览器自动化, browser mcp, 用浏览器, 登录网站, 登录态, playwright |
| **workspace-navigator** | `global_skills/browser/workspace-navigator/SKILL.md` | Agent可编程导航 Workspace 面板：Human说模糊意图，Agent找到路径，自动打开文件/目录 | Human说"打开日志""看看代码""打开设计图""帮我打开那个文档"等模糊指令。 | 打开 localhost 前端页面（用 browser-preview）、纯代码编写（不涉及展示给Human看）。 | Hub 右侧 Workspace 面板自动打开并导航到目标文件/目录。 | 打开文件, 看看代码, 看日志, 帮我打开, 一起看看, 打开设计图, 看看这个文档, 打开 discussion, 看看 feature, 打开审计日志 |

## enterprise

| Skill | Path | Description | Use When | Not For | Output | Triggers |
|-------|------|-------------|----------|---------|--------|----------|
| **enterprise-workflow** | `global_skills/enterprise/enterprise-workflow/SKILL.md` | 企业 IM 工作流自动化：文档、表格、待办/任务、会议/日程一键创建 | 要求创建企业 IM 的文档/表格/待办/会议/日程/幻灯片，或"一句话生成完整工作流"。 | 普通聊天、消息收发。 | 资源链接通过 callback 返回。 | 创建文档, create doc, 建个表格, 建个待办, 创建任务, 创建会议, 幻灯片, 工作流, enterprise workflow |

---
**Total**: 23 skills across 8 categories
