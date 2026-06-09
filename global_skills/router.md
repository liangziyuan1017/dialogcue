<!--
  ROUTER FILE — Global Skills Routing Layer
  Purpose: Map skill IDs to their SKILL.md files with decision columns.
  This file contains ROUTING INFORMATION ONLY.
  The runtime reads this file to resolve a global skill by name or intention.
-->

# global_skills Router

## capability_map

| skill_id | skill_path | Description | Use When | Not For | Output | Triggers |
|---|---|---|---|---|---|---|
| `cross-cat-handoff` | `collaboration/cross-cat-handoff/SKILL.md` | Task handoff protocol using 5-part structure (What/Why/Tradeoff/Open/Next) | 交接工作、传递信息、写 review 请求 | 自己的任务、不需要交接的工作 | 结构化交接/通信 | task handoff, communicate change |
| `expert-panel` | `collaboration/expert-panel/SKILL.md` | Structured Multi-Perspective Analysis — single agent analyzes from multiple viewpoints | 技术趋势判断、竞品分析、行业事件分析、需要多视角决策支持 | 简单问题、代码实现、bug fix、日常聊天 | Multi-perspective analysis report with WHY-chain | 帮我分析一下, expert panel, 竞品分析, 趋势判断, 多视角分析 |
| `collaborative-thinking` | `collaboration/collaborative-thinking/SKILL.md` | 单人或multi-agent的创意探索、独立思考、讨论收敛 | brainstorm、multi-agent独立思考、讨论结束需要收敛、方向性问题需要多视角 | 已有明确spec直接写代码、单猫执行已定方案 | 收敛报告（共识/分歧/行动项） | brainstorm, 讨论, 收敛, 总结一下 |
| `cross-thread-sync` | `collaboration/cross-thread-sync/SKILL.md` | cross-session协同：发现平行session→通知→争用协调→确认 | 平行session之间需要协同、通知改动影响、共享文件争用 | cross-check工作交接（用cross-cat-handoff） | cross-post通知+争用协调完成 | cross-session, parallel session sync, cross-thread |
| `knowledge-engineering` | `knowledge/knowledge-engineering/SKILL.md` | Agent指导外部项目文档重构 — AI FDE知识工程方法论 | Agent部署到外部项目、用户项目缺少结构化文档、需要知识工程指导、冷启动理解业务 | 已有完善docs/结构的项目 | 文档现状诊断+路径选择+三层知识注入建议 | 知识工程, 文档重构, knowledge engineering, 冷启动 |
| `deep-research` | `knowledge/deep-research/SKILL.md` | 多源深度调研管道（Web Deep Research + Coder合成 + 云端模型咨询） | 技术问题需要多源调查、设计决策需要证据、需要咨询云端模型 | 简单搜索（直接用WebSearch）、已有结论的确认 | 调研报告+证据合成 | 调研, research, 深度研究, 咨询云端 |
| `self-evolution` | `knowledge/self-evolution/SKILL.md` | Scope Guard + Process Evolution + Knowledge Evolution — 主动护栏与自我进化 | Human scope发散偏离愿景、同类错误反复出现、SOP流程缺口、有价值的知识/方法论值得沉淀 | 日常SOP推进、一次性个案bug fix | Scope Guard Log / Evolution Proposal / Episode Card蒸馏 | — |
| `incident-response` | `quality/incident-response/SKILL.md` | 不可逆事故发生后的应急响应：情绪急救→止损→补偿性劳动→教训沉淀 | 犯了不可挽回的错误、造成了人类伙伴的情绪波动、需要危机处理 | 可撤销的小失误、日常bug fix、预防性确认 | 情绪修复+止损行动+教训沉淀 | 闯祸了, 搞砸了, 不可挽回, incident, 怎么补救 |
| `debugging` | `quality/debugging/SKILL.md` | 系统化bug定位：根因调查→模式分析→假设验证→修复 | 遇到bug、测试失败、unexpected behavior | 新功能开发、重构、已知原因的简单修复 | Bug report五件套+根因+修复 | bug, 报错, test failure, unexpected behavior |
| `writing-skills` | `meta/writing-skills/SKILL.md` | 创建或修改skill / MCP tool description的元技能 | 写新skill、修改现有skill、写/改MCP tool description、验证skill质量 | 使用skill（直接触发对应skill） | 新/更新的SKILL.md + manifest条目 | 写 skill, 新 skill, SKILL.md, 写 MCP |
| `rich-messaging` | `creative/rich-messaging/SKILL.md` | 富媒体消息：语音、图片、卡片、清单、代码diff、交互选择 | 发语音、发图、发卡片、展示结构化信息、让用户选、确认操作 | 纯文字聊天、技术讨论、日常回复 | rich block附着在消息上 | 发语音, voice, 发图, 截图, 发个卡片, checklist |
| `video-forge` | `creative/video-forge/SKILL.md` | 视频制作全链路：素材入库→剧本冻结→配音→对齐→渲染→审查→交付 | 做视频、做showcase、做教程视频、录屏剪辑 | 纯代码开发、纯文档写作、PPT（用ppt-forge） | 视频成片+审查通过 | — |
| `image-generation` | `creative/image-generation/SKILL.md` | 通过浏览器自动化在AI平台上生成图片并下载 | 需要AI生成概念图、UI参考、像素画素材 | 已有图片的展示、SVG图标制作 | 生成图片 | — |
| `ppt-forge` | `creative/ppt-forge/SKILL.md` | PPT制作全链路：内容规划→风格定调→Slide制作→视觉审查→导出验证→交付 | 做PPT、做演示文稿、做slide、做海报、视觉审查 | 纯代码开发、纯文档写作 | 高密度HTML slide+自查通过 | — |
| `pencil-design` | `creative/pencil-design/SKILL.md` | 使用设计工具创建/编辑设计文件，或导出为前端代码 | 设计UI、编辑设计稿、从设计稿生成代码 | 纯代码实现（无设计稿）、非设计工具的设计工作 | 设计文件或前端组件代码 | pencil, .pen 文件, 设计稿 |
| `guide-authoring` | `guides/guide-authoring/SKILL.md` | 标准引导流程设计SOP：场景识别→YAML编排→标签标注→注册发现→测试验证 | 新建引导流程、添加场景引导、维护Guide Catalog | 使用引导（用户侧）、Guide Engine代码实现 | Flow YAML + tag-manifest更新 | 新建引导, guide authoring, 引导 YAML |
| `bootcamp-guide` | `guides/bootcamp-guide/SKILL.md` | Onboarding guide structure — reference pattern for new user orientation | designing onboarding flows for new users | experienced users, regular development | Onboarding guide | bootcamp, 训练营, 我是新手 |
| `guide-interaction` | `guides/guide-interaction/SKILL.md` | 场景引导交互模式：判断该直接解释还是进入交互引导 | 用户在询问某项功能的使用/配置流程 | 普通闲聊、代码实现、没有流程诉求的概念讨论 | 交互引导或直接解释 | 引导流程, 怎么配置, 怎么操作 |
| `browser-preview` | `browser/browser-preview/SKILL.md` | Hub内嵌浏览器预览localhost应用 | 写前端代码、跑dev server、需要看页面效果、调UI | 后端纯API开发、不涉及页面的工作 | 前端页面实时预览 | 看效果, preview, 浏览器预览, dev server, localhost |
| `schedule-tasks` | `browser/schedule-tasks/SKILL.md` | 定时任务注册、管理、能力指南 | 用户想设定时任务、定期提醒、周期巡检、延迟执行 | 已有builtin任务的手动触发 | 注册/管理定时任务 | 定时, 每天, 提醒我, schedule, cron, 周期 |
| `browser-automation` | `browser/browser-automation/SKILL.md` | 浏览器工作流总路由：为外部网站浏览、登录态流程、证据采集选择合适后端 | 需要操作外部网站、登录页、JS重页面、需要浏览器 | localhost页面预览（用browser-preview）、简单网页抓取 | 选定浏览器后端+执行路径+证据 | 浏览器自动化, browser mcp, 用浏览器, 登录网站, playwright |
| `workspace-navigator` | `browser/workspace-navigator/SKILL.md` | Agent可编程导航Workspace面板：模糊意图→找到路径→自动打开文件/目录 | Human说"打开日志""看看代码"等模糊指令 | 打开localhost前端页面（用browser-preview）、纯代码编写 | Workspace面板自动打开并导航到目标 | 打开文件, 看看代码, 看日志, 帮我打开 |
| `enterprise-workflow` | `enterprise/enterprise-workflow/SKILL.md` | 企业IM工作流自动化：文档、表格、待办/任务、会议/日程一键创建 | 要求创建企业IM的文档/表格/待办/会议/日程/幻灯片 | 普通聊天、消息收发 | 资源链接通过callback返回 | 创建文档, 建个表格, 建个待办, enterprise workflow |

## fallback_rule

- If no skill above matches the intention, do NOT adopt any global skill.
- Proceed with the module's own execution pipeline or normal agent operations.
- Global skills are methodology tools — they are optional, not required.
