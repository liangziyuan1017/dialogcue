---
name: bootcamp-guide
description: >
  Onboarding guide structure — reference pattern for new user orientation.
  Use when: designing onboarding flows for new users.
  Not for: experienced users, regular development.
triggers:
  - "bootcamp"
  - "训练营"
  - "我是新手"
---
# Bootcamp Guide — Onboarding Reference Pattern

> ⚠️ **Reference Pattern** — This is a structure template for designing onboarding flows. The original implementation was tied to cat-cafe infrastructure (bootcampState injection, SystemPromptBuilder, cat selection). The 11-phase progression structure is preserved as a reference.

## Onboarding Phase Structure

The original skill had 11 phases for new user onboarding. This structure can be adapted for any project:

| Phase | Purpose |
|-------|---------|
| 0: Welcome & Setup | Greet user, explain the system, let them choose preferences |
| 1: Introduction | Introduce capabilities, set expectations |
| 2: Environment Check | Verify development environment is ready |
| 3: First Task | Guide through completing a simple first task |
| 4: Task Selection | Help user choose their next real task |
| 5: Kickoff | Guide through starting the first real project |
| 6: Design | Guide through design decisions |
| 7: Development | Guide through implementation |
| 8: Review | Guide through the review process |
| 9: Complete | Celebrate completion, review what was learned |
| 10: Retrospective | Reflect on the experience, suggest next steps |
| 11: Farewell | Graduation — user is now independent |

## Key Principles

1. **Patience**: New users need more explanation and encouragement
2. **Progressive autonomy**: Each phase reduces guidance, increases independence
3. **Context-aware**: Adapt pace based on user's demonstrated competence
4. **Celebrate milestones**: Acknowledge progress at each phase completion

## Porting Requirements

This skill was migrated from Clowder AI's cat-cafe-skills. Infrastructure-dependent sections are marked `[INFRA]`. To fully activate this skill, the following infrastructure is needed:

- **MCP tools**: The original skill uses `cat_cafe_*` MCP functions. Equivalent tool interfaces must be implemented.
- **Hooks**: [INFRA] [INFRA] PostToolUse hooks and [INFRA] SystemPromptBuilder injection are clowder-specific and need equivalent hook mechanisms.
- **Rich blocks**: Structured UI block rendering requires an equivalent rich messaging system.
- **Port/Redis**: Development environment isolation patterns (Redis dev/prod ports) need adaptation to the target project.

The transferable methodology (quality standards, structure patterns, process checklists) remains intact. Infrastructure-dependent sections are clearly tagged for future implementation.
