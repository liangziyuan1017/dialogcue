# Knowledge Objects

> Normalized from clowder-ai ADR-015 (Knowledge Object Contract).
> Defines the extended metadata for durable knowledge entries.

## Knowledge Block

Any document that represents durable knowledge can include an optional `knowledge:` block in its frontmatter:

```yaml
knowledge:
  artifact_type: lesson    # What kind of knowledge?
  domain: development      # What domain?
  scope: team-shared       # Who can access?
  authority: validated     # How trusted?
  activation: scoped       # When loaded?
  status: active           # Is it current?
  trust_level: tested      # How confident?
  source_ids: [ADR-005]    # What proved this?
  exportability: generalized # Can it leave the project?
```

## Artifact Types

| Type | Description |
|------|-------------|
| `episode` | A specific event or interaction |
| `method` | A reusable technique or process |
| `skill` | A capability definition |
| `proposal` | A proposed change |
| `eval` | An evaluation result |
| `lesson` | A lesson learned (LL-XXX) |
| `log` | A log entry |

## The Three Axes (Authority × Activation × Status)

These are orthogonal — they don't cascade. A document can be high-authority but dormant, or low-authority but always-on.

| Axis | Values | Question |
|------|--------|----------|
| `authority` | observed → candidate → validated → constitutional | How trusted? |
| `activation` | query → scoped → always_on → backstop | When loaded? |
| `status` | active → review → invalidated → archived | Is it current? |

**How they combine:**
- `constitutional + always_on` → in every agent's system prompt
- `validated + scoped` → loaded when relevant context is detected
- `observed + query` → only when explicitly searched
- `archived + backstop` → preserved but never proactively surfaced

## Provenance

Every knowledge entry must trace to its source:
- `source_ids`: What proved this? (ADR IDs, lesson IDs, commit SHAs)
- `evolved_from`: What did this replace or refine?
- `superseded_by`: What replaced this?

Minimum 1 source anchor. Recommended 2 (rule + instance).
