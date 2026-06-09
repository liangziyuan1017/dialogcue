---
name: pencil-design
description: >
  使用设计工具创建/编辑设计文件，或导出为前端代码。
  Use when: 设计 UI、编辑设计稿、从设计稿生成代码。
  Not for: 纯代码实现（无设计稿）、非设计工具的设计工作。
  Output: 设计文件 或 前端组件代码。
triggers:
  - "pencil"
  - ".pen 文件"
  - "设计稿"
---

# Pencil Design — 设计文件与代码导出

> ⚠️ **[INFRA-DEPENDENT]** This skill requires a design tool MCP integration (originally Pencil MCP + Antigravity IDE). It is migrated as a reference pattern for the design-to-code workflow. The specific tool calls and file formats are infrastructure-dependent.

## 核心知识

设计文件是加密格式，只能通过设计工具 MCP 读写。配置要求：MCP 配置需要指定目标应用环境。

## SOP 位置

```
feat-lifecycle → Design Gate → **pencil-design** → writing-plans → worktree → tdd
```

pencil-design 在 spec 确认后、写代码前。先把 UX 做对，再动手写代码。

## 风格一致性门禁

在创建任何新设计之前：

### Step 1: 分析现有 UI

如果要设计的功能是已有产品的扩展：截图现有 UI → 提取风格特征（配色方案、布局模式、间距和圆角、字体层级）→ 写入设计约束。

### Step 2: 判断设计类型

| 类型 | 做法 |
|------|------|
| 已有产品扩展 | 分析现有 UI → 提取风格 → 保持一致 |
| 全新产品 | 从品牌色/调性出发 → 建立设计系统 |
| 纯后端功能 | 跳过 pencil-design，直接进入 writing-plans |

## Porting Requirements

To fully activate this skill:
- **Design tool MCP**: Equivalent to Pencil MCP for design file read/write
- **IDE integration**: Design tool must be integrated with the development environment
- **Code export**: Design-to-code pipeline (e.g., React/Tailwind export)
