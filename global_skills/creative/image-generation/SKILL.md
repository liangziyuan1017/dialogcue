---
name: image-generation
description: >
  通过浏览器自动化在 AI 平台上生成图片并下载。
  Use when: 需要 AI 生成概念图、UI 参考、像素画素材。
  Not for: 已有图片的展示、SVG 图标制作（手写或用设计工具）。
---

# AI 图片生成

> ⚠️ **[INFRA-DEPENDENT]** This skill requires browser automation to interact with image generation platforms. The workflow pattern is preserved; implementation requires equivalent browser automation infrastructure.

## 何时使用

- 需要为 feature 生成概念图、UI 参考图、像素画素材
- 要求生成特定风格的图片
- 需要批量生成多个变体

## 支持平台

| 平台 | 模型 | 风格选择 | 下载 |
|------|------|---------|------|
| agent | agent 3 Pro | ✅ 多种预设风格 | ✅ |
| ChatGPT | GPT-4o / DALL-E | ✅ 风格预设 | ✅ |

## 快速流程

**agent 画图**: 导航到 gemini.google.com/app → 工具 → 制作图片 → 注入 prompt → 发送 → 等待生成 → 下载

**ChatGPT 画图**: 导航到 chatgpt.com/images → 输入 prompt → 等待生成 → 下载

## Porting Requirements

To fully activate this skill:
- **Browser automation**: Chrome MCP or equivalent to navigate image generation platforms
- **Platform accounts**: Access to agent/ChatGPT or equivalent image generation services
