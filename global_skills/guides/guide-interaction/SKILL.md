---
name: guide-interaction
description: >
  场景引导交互模式：当用户在询问某项功能的使用/配置流程时，判断该直接解释还是进入交互引导。
  Use when: 系统注入了引导状态，或用户明确在问某项功能怎么操作。
  Not for: 普通闲聊、代码实现、没有流程诉求的概念讨论。
triggers:
  - "引导流程"
  - "怎么配置"
  - "怎么操作"
---

# Guide Interaction — 场景引导交互模式

> ⚠️ **[INFRA-DEPENDENT]** This skill requires frontend overlay protocol, state persistence, and [INFRA] SystemPromptBuilder injection. The interaction pattern is preserved as reference; the UI layer requires equivalent infrastructure.

## 核心边界

- 不要因为看到了关键词就擅自造一个引导
- 如果用户只是想知道说明，直接回答
- 如果用户明显需要一步一步操作，再查看当前可用的 guide 目录

## 状态驱动

运行时可能注入的状态：Guide Matched → Guide Pending → Guide Selection → Guide Active → Guide Completed

## 工具速查

| 动作 | 何时使用 |
|------|----------|
| 获取可用 guides | 用户需要操作引导时 |
| 启动 guide | 用户确认开始后 |
| 下一步 | 当前步骤完成后 |
| 跳过 | 用户要求跳过当前步骤 |
| 完成 | 所有步骤完成后 |

## Porting Requirements

To fully activate this skill:
- **Frontend overlay**: Guide UI overlay system for step-by-step interaction
- **State persistence**: Session-level guide state management
- **Guide registry**: Available guides catalog with metadata
