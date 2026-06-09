---
name: enterprise-workflow
description: >
  企业 IM 工作流自动化：文档、表格、待办/任务、会议/日程一键创建。
  Use when: 要求创建企业 IM 的文档/表格/待办/会议/日程/幻灯片，或"一句话生成完整工作流"。
  Not for: 普通聊天、消息收发。
  Output: 资源链接通过 callback 返回。
triggers:
  - "创建文档"
  - "create doc"
  - "建个表格"
  - "建个待办"
  - "创建任务"
  - "创建会议"
  - "幻灯片"
  - "工作流"
  - "enterprise workflow"
---

# Enterprise Workflow — 企业 IM 工作流自动化

> ⚠️ **[INFRA-DEPENDENT]** This skill requires enterprise IM API integration. It is migrated as a reference pattern for IM-based workflow automation.

## 支持的操作

| 操作 | 说明 |
|------|------|
| 创建文档 | 一键创建企业文档 |
| 建表格 | 创建智能表格/多维表 |
| 建待办 | 创建任务/待办项 |
| 创建会议 | 预约会议并生成链接 |
| 创建日程 | 添加日历事件 |
| 幻灯片 | 创建演示文稿 |

## 工作流模式

"一句话生成完整工作流"：用户描述需求 → 自动拆解为多个企业 IM 操作 → 依次执行 → 返回所有资源链接。

## Porting Requirements

To fully activate this skill:
- **Enterprise IM API**: 飞书/企微 or equivalent enterprise IM platform API
- **Callback route**: Endpoint to receive action results
- **CLI executor**: Command-line interface for enterprise operations
