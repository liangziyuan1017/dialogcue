# src/ — Debt Collection Script Recommendation System

Source code and data artifacts for the phase-based pipeline.

## Pipeline Modules

| File | Feature | Purpose |
|------|---------|---------|
| `discover_keywords.py` | F000 | Discover state keyword taxonomy from all turns across 31 records |
| `analyze_customer_turns.py` | F000 | Group customer-turn keywords into fact/emotion canonical groups |
| `analyze_collector_turns.py` | F000 | Group collector-turn keywords into action canonical groups |
| `define_willingness_levels.py` | F000 | Define willingness levels ordered resistant → cooperative |
| `align_schema.py` | F001 | Map raw records to SOP-aligned schema with `turns_annotated`, `context` |
| `reward_label.py` | F003 | Label R∈{0,1} per conversation; credit customer acceptance turn; cross-validate |
| `llm_client.py` | — | DeepSeek API wrapper (`call_deepseek`, `call_deepseek_json`) |
| `load_data.py` | — | Load raw records from `/data/output_manual.py` |

## Data Artifacts

| File | Feature | Description |
|------|---------|-------------|
| `state_keywords.json` | F000 | Keyword taxonomy: facts, emotions, willingness_levels, collector_actions |
| `output_labeled.py` | F000 | 31 records with LLM-annotated state labels on turns (493/805 labeled) |
| `output_aligned.py` | F001 | 31 records in SOP-aligned schema with `turns_annotated`, `context`, `reward: None` |
| `output_rewarded.py` | F003 | 31 records with `reward` ∈ {0,1}, `reward_evidence`, `reward_action_credit` |

## Tests

| File | Covers |
|------|--------|
| `test_discover_keywords.py` | F000 keyword discovery + labeled output |
| `test_analyze_customer_turns.py` | F000 customer keyword grouping |
| `test_analyze_collector_turns.py` | F000 collector action grouping |
| `test_define_willingness_levels.py` | F000 willingness level ordering |
| `test_e2e_keyword_discovery.py` | F000 end-to-end taxonomy validation |
| `test_align_schema.py` | F001 schema alignment, context fields, state label carry-over |
| `test_reward_label.py` | F003 reward labeling, action credit, cross-validation |
| `test_llm_client.py` | DeepSeek API client |
| `test_load_data.py` | Raw data loading |

## Dependency Graph

```
F000 ──► F001 ──► F003 ──► F004 ──► F005 ──► F006
                                    │
                             F007 ──┘
```

F002 was removed (ADR-009): LLM State Extraction eliminated; F001's manual annotations provide sufficient coverage.
