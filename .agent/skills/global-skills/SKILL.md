---
name: global-skills
description: >
  Discover and adopt methodology skills from the global_skills/ directory.
  Use when: brainstorm, debugging, incident response, deep research, cross-session sync,
  expert panel analysis, knowledge engineering, rich messaging, video/ppt creation,
  browser automation, enterprise workflows, guide authoring, or any task matching
  a global skill's "Use When" criteria.
  Not for: tasks that already have a dedicated module skill (feat-lifecycle, tdd, etc.).
  Output: The matched global skill's methodology is adopted for the current task.
triggers:
  - "brainstorm"
  - "debugging"
  - "bug"
  - "incident"
  - "research"
  - "调研"
  - "expert panel"
  - "竞品分析"
  - "知识工程"
  - "cross-session"
  - "handoff"
  - "交接"
  - "发图"
  - "做视频"
  - "做PPT"
  - "浏览器自动化"
  - "定时任务"
  - "企业工作流"
  - "引导流程"
  - "scope guard"
  - "self-evolution"
---

# Global Skills

Gateway to 23 methodology skills across 8 categories in `global_skills/`.

## How It Works

1. Read `global_skills/README.md` for the full manifest with Use When / Not For / Triggers columns
2. Match the current task keywords against each skill's **Use When** and **Triggers**
3. If a skill matches AND its **Not For** does not match → adopt that skill
4. Read the matched `SKILL.md` at the path listed in the manifest
5. Apply the methodology to the current task

## Categories

| Category | Skills | Key Triggers |
|----------|--------|-------------|
| **collaboration** | cross-cat-handoff, expert-panel, collaborative-thinking, cross-thread-sync | 交接, 分析, brainstorm, cross-session |
| **knowledge** | knowledge-engineering, deep-research, self-evolution | 调研, 知识工程, scope guard |
| **quality** | incident-response, debugging | 闯祸了, bug, test failure |
| **meta** | writing-skills | 写 skill, SKILL.md |
| **creative** | rich-messaging, video-forge, image-generation, ppt-forge, pencil-design | 发图, 做视频, 做PPT |
| **guides** | guide-authoring, bootcamp-guide, guide-interaction | 引导流程, 新手 |
| **browser** | browser-preview, schedule-tasks, browser-automation, workspace-navigator | preview, 定时, 浏览器自动化 |
| **enterprise** | enterprise-workflow | 创建文档, 建个待办 |

## When to use

- Any task whose keywords match a global skill's Use When / Triggers
- Before making design/architecture decisions (memory-first rule)

## When NOT to use

- Tasks already covered by a dedicated module skill (feat-lifecycle, tdd, worktree, etc.)
- When no global skill's Use When matches the task

## Execution

→ Read `global_skills/router.md` for the routing table
→ Read `global_skills/README.md` for the full manifest
→ Match task → read the matched `SKILL.md` → adopt methodology

## Fallback

If no skill matches, do NOT adopt any global skill. Proceed with normal agent operations.
