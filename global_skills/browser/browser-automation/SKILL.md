---
name: browser-automation
description: >
  浏览器工作流总路由：为外部网站浏览、登录态流程、浏览器自动化、证据采集选择合适后端。
  Use when: 需要操作外部网站、登录页、JS 重页面、需要浏览器，或需要在多种浏览器工具之间路由。
  Not for: localhost 页面预览（用 browser-preview）、简单网页抓取/搜索。
  Output: 选定浏览器后端 + 执行路径 + 证据/结果。
triggers:
  - "浏览器自动化"
  - "browser mcp"
  - "用浏览器"
  - "登录网站"
  - "登录态"
  - "playwright"
---

# Browser Automation

> ⚠️ **[INFRA-DEPENDENT]** This skill routes across multiple browser automation backends. It is migrated as a reference pattern. The backend routing requires equivalent browser automation infrastructure.

这是浏览器的上层路由 skill。它只做三件事：判断该不该用浏览器、选择合适的浏览器后端、把任务转给更具体的 skill/ref。

## 执行前四问

1. **真的需要浏览器吗？** 如果只是读文档、抓纯文本、做搜索，不要默认上浏览器。
2. **目标是 localhost 还是外部网站？** `localhost` → `browser-preview`；外部网站才留在本 skill。
3. **客户端能力是什么？** MCP 原生、CLI-only、是否有 webfetch、是否能跑 shell。
4. **这次任务的 session 属于谁？** 匿名访问、自己的浏览器会话、还是接手已登录会话。

## Porting Requirements

To fully activate this skill:
- **Playwright MCP** or equivalent browser automation backend
- **Multiple backend support**: At least 2 browser automation tools for routing
- **Session management**: Ability to handle authenticated and anonymous browser sessions
