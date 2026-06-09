---
name: video-forge
description: >
  视频制作全链路：素材入库 → 剧本冻结 → 全局配音 → 对齐 → 渲染 → 审查 → 交付。
  Use when: 做视频、做 showcase、做教程视频、录屏剪辑、video review。
  Not for: 纯代码开发（用 worktree/tdd）、纯文档写作、PPT（用 ppt-forge）。
  Output: 视频成片 + 审查通过 + 可发布。
---

# Video Forge — AI 视频生产线

> ⚠️ **[INFRA-DEPENDENT]** This skill requires a video rendering pipeline and TTS integration. The workflow pattern and schema design are preserved as reference; rendering requires equivalent infrastructure.

## 核心原则

### 铁规矩

1. **全局音频，不段级切碎** — TTS 拿完整剧本一口气读完，保住情绪和呼吸感
2. **不赌 TTS 原生 timestamps** — forced alignment 出时间戳
3. **拒绝暴力慢放** — 画面不够时：FREEZE_STYLIZED > B_ROLL > SLOW_MO
4. **Contract 和 Renderer 解耦** — video-spec JSON 是真相源，渲染器可替换

## 两条生产路径

| | 路径 B：先脚本后素材 | 路径 A：先素材后配音 |
|---|---|---|
| 触发 | "做个 showcase/教程视频" | "这段录屏帮我配个音" |
| 输入 | 分镜脚本 + 素材 + 粗标 | 原始视频 + 风格关键词 |

## 开局参数（必须声明）

| 参数 | 说明 | 示例 |
|------|------|------|
| 类型 | 视频类型 | showcase / 教程 / 播客 |
| 时长目标 | 成片目标时长 | 60s / 3min / 6-8min |
| 调性 | 整体情绪基调 | 真实生活感 / 高燃极客 / 温馨 |
| 受众 | 谁看这个视频 | 社区 / 平台观众 / 内部 |
| 配音方案 | 配音 / 纯字幕 / 原声 | 旁白 / 多声线 / 无配音 |

## Porting Requirements

To fully activate this skill:
- **Video renderer**: Remotion/FFmpeg or equivalent video rendering pipeline
- **TTS engine**: Text-to-speech for voiceover generation
- **Forced alignment**: Audio-to-text timestamp alignment tool
- **Scene detection**: PySceneDetect + VLM or equivalent for auto-spec generation
