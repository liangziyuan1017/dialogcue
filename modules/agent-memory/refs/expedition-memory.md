# Expedition Memory — External Project Bootstrap

> Normalized from clowder-ai F152 (Expedition Memory).
> How agents cold-start understanding of an external project and reflux patterns back.

## AI FDE (Forward Deployed Engineer) Pattern

Agents deploy to external projects like Palantir's Forward Deployed Engineers:

```
1. Cold-start: Scan existing project docs (README, CHANGELOG, specs, configs)
2. Understand: Build a bootstrap summary of the project's architecture and patterns
3. Operate: Use the memory index while working on the project
4. Reflux: Generalizable patterns learned here → global methodology layer
```

## Pluggable Scanners

Different file types need different scanners. Each scanner extracts structured metadata:

| Scanner | Reads | Extracts |
|---------|-------|----------|
| `MarkdownScanner` | `*.md` | Frontmatter, headings, links, topic tags |
| `PackageScanner` | `package.json`, `pyproject.toml`, `Cargo.toml` | Dependencies, scripts, runtime metadata |
| `ChangelogScanner` | `CHANGELOG*`, `RELEASES*` | Version history, breaking changes, migration notes |
| `ConfigScanner` | `*.yaml`, `*.toml`, `*.json` (config files) | Configuration structure, environment variables |
| `CodeStructureScanner` | `src/**`, `lib/**` | Module tree, exports, entry points |
| `DocScanner` | `docs/**/*.md` | Documentation structure with frontmatter extraction |

## Provenance Tiers

Not all bootstrapped knowledge has equal weight:

```
Tier 1: kindCoverage  ← Structural facts ("this project uses React + FastAPI")
Tier 2: tierCoverage  ← Domain facts ("the auth module handles JWT validation")
Tier 3: decisionLog   ← Reasoning ("we chose JWT over sessions because...")
```

**Display rule**: Show `kindCoverage` first, fall back to `tierCoverage`. `decisionLog` is linked but not inlined.

## Bootstrap Process

1. **Scan**: Run all applicable scanners against the project root
2. **Extract**: Collect structured metadata from each scanner
3. **Summarize**: Generate a one-shot bootstrap summary (LLM call — not streaming)
4. **Index**: Build the initial searchable memory index
5. **Structure**: Create `BACKLOG.md` or `ROADMAP.md` if the project lacks one

## Cross-Project Reflux

```
Project A: Agent learns "Python 3.14 breaks pydantic v1 — upgrade to pydantic v2"
  → Promoted to global methodology as lesson LL-042
  → Exportability: generalized (no project-specific data)
  → Project B: Agent cold-starts, global lessons auto-loaded
  → Agent B already knows about the pydantic issue
```

**Reflux gate**: Only `exportability: generalized` entries cross the boundary. `project_only` and `private` entries stay local.
