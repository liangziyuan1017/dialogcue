# State Multihead Eval

- scoring: **evidence-only** (unknown / mask=0 excluded per head)
- macro-F1 (primary): **0.4527**
- weighted macro-F1: **0.4669**
- by kind: `{'state': 0.46, 'process': 0.5, 'event': 0.2413}`

## Per-head

| head | kind | support | macro-F1 | pos-F1 | pos-P | pos-R | acc |
|------|------|--------:|---------:|-------:|------:|------:|----:|
| `Employment` | state | 9 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `Income` | state | 701 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `FinancialHardship` | state | 1350 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `RepaymentCapability` | state | 98 | 0.3333 | 1.0 | 1.0 | 1.0 | 1.0 |
| `Health` | state | 79 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `FamilyBurden` | state | 186 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `Asset` | state | 108 | 0.312 | 0.8796 | 0.8796 | 0.8796 | 0.8796 |
| `Contactability` | state | 89 | 0.3849 | 0.7978 | 0.7978 | 0.7978 | 0.7978 |
| `Commitment` | state | 157 | 0.3301 | 0.9809 | 0.9809 | 0.9809 | 0.9809 |
| `Responsibility` | state | 195 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `DebtDispute` | state | 83 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `LegalProceeding` | state | 32 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `ComplianceRisk` | state | 29 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `BankConstraint` | state | 54 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `ObjectiveBlocker` | state | 18 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `CognitiveSupport` | state | 160 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `NegotiationRequest` | process | 202 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| `IdentityProcess` | event | 217 | 0.2413 | 0.4825 | 1.0 | 0.318 | 0.318 |
| `Grievance` | process | 147 | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |

## Head confusion (top)

### Asset
- `unavailable->available`: 11
- `available->unavailable`: 2

### Contactability
- `unreachable->reachable`: 14
- `reachable->unreachable`: 4

### Commitment
- `resistant->committed`: 3

### IdentityProcess
- `yes->no`: 148
