---
id: LL-XXX
title: "[One-line lesson summary]"
doc_kind: lesson
feature_ids: []
topics: []
status: draft
created: YYYY-MM-DD
schema_version: 1
# knowledge:                              # Optional — add for knowledge-carrying lessons
#   authority: observed                   # observed | candidate | validated | constitutional
#   activation: query                    # query | scoped | always_on | backstop
#   status: active                       # active | review | invalidated | archived
#   exportability: project_only          # private | project_only | generalized
#   source_ids: []                       # Evidence supporting this lesson
#   review_cycle_days: 90
---

# LL-XXX: [Lesson Title]

## 1. Pitfall

[What went wrong? One sentence.]

## 2. Root Cause

[Why did it happen? What was the underlying cause, not just the symptom?]

## 3. Trigger Conditions

[Under what conditions will this recur? Be specific — environment, configuration, workflow step.]

## 4. Fix

[How was it resolved in this instance? What was the immediate fix?]

## 5. Guard (Executable)

[What mechanism prevents recurrence? Must be a script, test, CI check, or automated rule — NOT just "be careful next time."]

- Script: `[path/to/script]`
- Test: `[path/to/test]`
- CI Rule: `[description]`

## 6. Source Anchor

- [file path or commit SHA]
- [additional anchor — recommended]

## 7. Related

- [ADR-XXX]
- [LL-XXX]

---

## First-Principles Root Cause (Optional)

[Which axiom (P1-P5) does this trace to? Only fill if a real failure case supports it.]

---

## Quality Gate Checklist

- [ ] QG1: Source anchor has at least 1 entry
- [ ] QG2: Timeliness verified (no subsequent addendum invalidates this)
- [ ] QG3: Executable guard references a real script/test/rule
- [ ] QG4: Principle slot is null unless supported by a real failure case
- [ ] QG5: No existing LL-XXX describes the same pitfall with the same root cause
