---
name: rich-messaging
description: >
  富媒体消息：语音、图片、卡片、清单、代码 diff、交互选择。
  Use when: 发语音、发图、发卡片、展示结构化信息、让用户选、确认操作。
  Not for: 纯文字聊天、技术讨论、日常回复。
  Output: rich block 附着在消息上。
triggers:
  - "发语音"
  - "voice"
  - "audio"
  - "发图"
  - "截图"
  - "发个卡片"
  - "rich block"
  - "checklist"
  - "让我选"
  - "确认一下"
---

# Rich Messaging

> ⚠️ **[INFRA-DEPENDENT]** This skill requires a rich block rendering system. The block type definitions and usage guidelines are preserved as reference; implementation requires equivalent structured message infrastructure.

## 三大纪律

1. **先文字后块** — 富块是文字的增强，不是替代。永远先发文字消息，再跟富块
2. **audio 只说短句** — 口语化的短句，不是长篇朗读
3. **不确定就纯文本** — 当不确定用哪种 rich block 时，发纯文本永远不会错

## 七种 Rich Block 一览

| Kind | 什么时候用 | 关键字段 |
|------|-----------|---------|
| **audio** | 打招呼、表达情感、庆祝、鼓励、定时播报 | `text`（短句口语化） |
| **card** | 状态报告、决策摘要、review 结论 | `title` + `tone` |
| **checklist** | 待办、验证步骤、行动项 | `items` |
| **diff** | 代码修改建议、重构对比 | `filePath` + `diff` |
| **media_gallery** | 发送已有图片、截图、设计稿、多图对比 | `items` (url) |
| **interactive** | 让用户选方案、勾选项、确认操作 | `interactiveType` + `options` |
| **html_widget** | 图表、计算器、CSS 动画、数据面板 | `html`（完整 HTML/JS/CSS） |

## 最小工作示例

**语音**: `{"id": "a1", "kind": "audio", "v": 1, "text": "喵，恭喜完成了喵！"}`

**卡片**: `{"id": "c1", "kind": "card", "v": 1, "title": "Review 通过", "tone": "success", "bodyMarkdown": "0 P1 / 0 P2"}`

**清单**: `{"id": "cl1", "kind": "checklist", "v": 1, "title": "下一步", "items": [{"id": "i1", "text": "跑测试"}]}`

**交互选择**: `{"id": "int1", "kind": "interactive", "v": 1, "interactiveType": "single_choice", "title": "选一个方案", "options": [{"id": "opt1", "label": "方案 A"}]}`

## Porting Requirements

To fully activate this skill:
- **Rich block system**: Equivalent structured message rendering for all 7 block kinds
- **Audio TTS**: Text-to-speech for audio block generation
- **Media hosting**: Image/file hosting for media_gallery blocks
- **HTML sandbox**: Secure HTML widget rendering environment
