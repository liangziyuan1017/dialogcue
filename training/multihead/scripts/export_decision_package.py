#!/usr/bin/env python3
"""Export v3.1.2 → v3.3 decision package (residual / boundary / long-tail).

Run on the **full-data** machine (needs checkpoint + state_*.jsonl + ontology).
Does not overwrite eval metrics; writes a new directory of decision materials.

Minimal (batch 1 — residual cases only):
  python training/multihead/scripts/export_decision_package.py \\
    --ckpt training/multihead/checkpoints/state_v312/state_best.pt \\
    --parts residual \\
    --device npu:0

Full package (recommended):
  python training/multihead/scripts/export_decision_package.py \\
    --ckpt training/multihead/checkpoints/state_v312/state_best.pt \\
    --parts all \\
    --device npu:0

Outputs under --out-dir (default: <ckpt_dir>/decision_package_v312/):
  01_residual_audit/     confusion windows + confidence (P0 / P2)
  02_identity_process/   ontology + positive examples + boundary checklist (P0.5)
  03_longtail_distribution/  train/test multi-state counts (P1)
  04_ontology_heads/     Asset/Contact/Commitment/RC/IP definitions (P1)
  00_DECISION_TEMPLATE.md
  README.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
import yaml
from torch.utils.data import DataLoader

MH_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MH_ROOT.parents[1]
sys.path.insert(0, str(MH_ROOT / "src"))

from datasets.state_dataset import (  # noqa: E402
    StateDataset,
    StateSample,
    collate_state,
    load_state_jsonl,
)
from device_utils import describe_device_env, get_device  # noqa: E402
from models.state_model import StateMultiheadModel  # noqa: E402
from schema_loader import MultiheadSchema, load_schema  # noqa: E402

# Default residual pairs from v3.2 full-data eval (Asset/Contactability/Commitment).
DEFAULT_CONFUSION_SPECS: list[tuple[str, str, str]] = [
    ("Asset", "unavailable", "available"),
    ("Asset", "available", "unavailable"),
    ("Contactability", "unreachable", "reachable"),
    ("Contactability", "reachable", "unreachable"),
    ("Commitment", "resistant", "committed"),
]

MULTI_STATE_HEADS = (
    "Asset",
    "Contactability",
    "Commitment",
    "RepaymentCapability",
)

ONTOLOGY_FOCUS_HEADS = (
    "Asset",
    "Contactability",
    "Commitment",
    "RepaymentCapability",
    "IdentityProcess",
)

TURN_SPLIT_RE = re.compile(r"(?=\[(?:collector|customer|agent|user)\])", re.I)


def resolve_path(cfg_path: Path, maybe_rel: str) -> Path:
    p = Path(maybe_rel)
    if p.is_absolute():
        return p
    for base in (cfg_path.parent, MH_ROOT, REPO_ROOT):
        cand = (base / p).resolve()
        if cand.exists():
            return cand
    return (cfg_path.parent / p).resolve()


def find_ontology(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    candidates = [
        REPO_ROOT / "label_handler" / "ontology_v2" / "training_ontology_v3.yaml",
        MH_ROOT
        / "artifacts"
        / "v3.1.2_must_replace"
        / "label_handler"
        / "ontology_v2"
        / "training_ontology_v3.yaml",
        MH_ROOT / "artifacts" / "v3.1.2_freeze" / "training_ontology_v3.1.2.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    raise SystemExit(
        "Ontology yaml not found. Pass --ontology path/to/training_ontology_v3.yaml"
    )


def format_window_turns(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in TURN_SPLIT_RE.split(text) if p.strip()]
    if parts:
        return parts
    return [text]


def sample_id(s: StateSample) -> str:
    return f"{s.conversation_id}#turn{s.turn_id}"


def is_evidence_row(h_name: str, lab: str, mask: float) -> bool:
    if lab in ("unknown", ""):
        return False
    if h_name == "IdentityProcess":
        return True
    return float(mask) >= 0.5


def load_model(
    config: dict[str, Any],
    ckpt_path: Path,
    device: torch.device,
) -> StateMultiheadModel:
    ckpt = torch.load(ckpt_path, map_location="cpu")
    if ckpt.get("config", {}).get("model_name") == "__mock__":
        config["model_name"] = "__mock__"
    model = StateMultiheadModel.from_config(config)
    model.load_state_dict(ckpt["model"])
    model.to(device)
    model.eval()
    return model


# ---------------------------------------------------------------------------
# P0 / P2: residual confusion cases with confidence
# ---------------------------------------------------------------------------


def collect_confusion_cases(
    model: StateMultiheadModel,
    samples: list[StateSample],
    schema: MultiheadSchema,
    device: torch.device,
    batch_size: int,
    specs: list[tuple[str, str, str]],
) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    wanted_heads = {h for h, _, _ in specs}
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    loader = DataLoader(
        StateDataset(samples, schema),
        batch_size=batch_size,
        shuffle=False,
        collate_fn=collate_state,
    )
    idx2val = {h.name: list(h.values) for h in schema.heads}
    sample_by_key = {(s.conversation_id, s.turn_id): s for s in samples}

    with torch.no_grad():
        for batch in loader:
            out = model(batch["texts"], device)
            labels_rows = batch.get("labels") or []
            cids = batch["conversation_id"]
            tids = batch["turn_id"]
            for h in schema.heads:
                if h.name not in wanted_heads:
                    continue
                logits = out["logits"][h.name]
                probs = F.softmax(logits, dim=-1)
                pred_i = logits.argmax(-1).tolist()
                masks = batch["head_mask"][h.name].tolist()
                values = idx2val[h.name]
                for i, (pi, m) in enumerate(zip(pred_i, masks)):
                    lab = str((labels_rows[i] or {}).get(h.name, "unknown"))
                    if not is_evidence_row(h.name, lab, m):
                        continue
                    if lab not in values:
                        continue
                    pred = values[int(pi)]
                    key = (h.name, lab, pred)
                    if key not in {(a, b, c) for a, b, c in specs}:
                        continue
                    s = sample_by_key.get((cids[i], int(tids[i])))
                    conf = {
                        values[j]: round(float(probs[i, j].item()), 4)
                        for j in range(len(values))
                    }
                    logits_row = {
                        values[j]: round(float(logits[i, j].item()), 4)
                        for j in range(len(values))
                    }
                    meta = dict(s.meta) if s else {}
                    buckets[key].append(
                        {
                            "sample_id": sample_id(s) if s else f"{cids[i]}#turn{tids[i]}",
                            "conversation_id": cids[i],
                            "turn_id": int(tids[i]),
                            "head": h.name,
                            "gold": lab,
                            "prediction": pred,
                            "confidence": conf,
                            "logits": logits_row,
                            "pred_confidence": conf.get(pred),
                            "gold_confidence": conf.get(lab),
                            "margin_pred_minus_gold": round(
                                float(conf.get(pred, 0) - conf.get(lab, 0)), 4
                            ),
                            "conversation_window": (s.text if s else batch["texts"][i]),
                            "window_turns": format_window_turns(
                                s.text if s else batch["texts"][i]
                            ),
                            "window_raws": list(
                                meta.get("window_raws")
                                or meta.get("memory_raws")
                                or []
                            ),
                            "fired": list(meta.get("fired") or []),
                        }
                    )
    return buckets


def write_residual_audit(
    out_dir: Path,
    buckets: dict[tuple[str, str, str], list[dict[str, Any]]],
    specs: list[tuple[str, str, str]],
) -> None:
    d = out_dir / "01_residual_audit"
    d.mkdir(parents=True, exist_ok=True)
    jsonl_path = d / "residual_cases.jsonl"
    index_lines = [
        "# Residual Audit — confusion cases",
        "",
        "Classify each case as: **model_error** / **ontology_boundary** / **label_error**.",
        "",
        "| Head | gold → pred | n | file |",
        "|---|---|---:|---|",
    ]
    with jsonl_path.open("w", encoding="utf-8") as jf:
        for head, gold, pred in specs:
            cases = buckets.get((head, gold, pred), [])
            slug = f"{head}__{gold}_to_{pred}"
            md_path = d / f"{slug}.md"
            index_lines.append(
                f"| `{head}` | `{gold}` → `{pred}` | {len(cases)} | `{md_path.name}` |"
            )
            md: list[str] = [
                f"# {head}: `{gold}` → `{pred}` ({len(cases)} cases)",
                "",
                "Decision guide:",
                "- **A model_error**: utterance clearly matches gold; model wrong",
                "- **B ontology_boundary**: utterance ambiguous under current definition",
                "- **C label_error**: gold inconsistent with utterance / include_raw",
                "",
            ]
            if not cases:
                md.append("_No cases found on this split (counts may differ from report)._")
            for n, c in enumerate(cases, 1):
                jf.write(json.dumps(c, ensure_ascii=False) + "\n")
                md.append(f"## Case {n}")
                md.append("")
                md.append(f"sample_id: `{c['sample_id']}`")
                md.append("")
                md.append("conversation window:")
                for ti, turn in enumerate(c["window_turns"], 1):
                    md.append(f"turn{ti}:")
                    md.append(turn)
                    md.append("")
                md.append(f"gold:\n{c['head']}={c['gold']}")
                md.append("")
                md.append(f"prediction:\n{c['head']}={c['prediction']}")
                md.append("")
                md.append("confidence:")
                for k, v in (c.get("confidence") or {}).items():
                    md.append(f"  {k}: {v}")
                md.append("")
                md.append("logits:")
                for k, v in (c.get("logits") or {}).items():
                    md.append(f"  {k}: {v}")
                md.append("")
                md.append(
                    f"margin (pred − gold confidence): {c.get('margin_pred_minus_gold')}"
                )
                md.append("")
                if c.get("window_raws"):
                    md.append(f"window_raws: `{c['window_raws']}`")
                    md.append("")
                if c.get("fired"):
                    md.append("fired:")
                    for fr in c["fired"]:
                        md.append(f"- `{fr}`")
                    md.append("")
                md.append("audit_label: _TODO: model_error | ontology_boundary | label_error_")
                md.append("")
                md.append("---")
                md.append("")
            md_path.write_text("\n".join(md), encoding="utf-8")

    index_lines.extend(
        [
            "",
            f"Machine-readable: `{jsonl_path.name}`",
            "",
            "### Confidence quick read",
            "",
            "- pred≈0.5 / gold≈0.5 → boundary / hard case",
            "- pred≈0.99 / gold≈0.01 → class not learned or systematic bias",
            "",
        ]
    )
    (d / "INDEX.md").write_text("\n".join(index_lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# P0.5: IdentityProcess
# ---------------------------------------------------------------------------


def extract_head_ontology(
    ont: dict[str, Any], schema: MultiheadSchema, head_name: str
) -> dict[str, Any]:
    heads_block = (ont.get("heads") or {}).get(head_name) or {}
    schema_h = next((h for h in schema.heads if h.name == head_name), None)
    values = list(schema_h.values) if schema_h else list(heads_block.get("values") or [])
    labels_out: dict[str, Any] = {}
    labels = ont.get("labels") or {}
    for v in values:
        key = f"{head_name}.{v}"
        if key in labels:
            lab = labels[key]
            labels_out[key] = {
                k: lab[k]
                for k in (
                    "definition",
                    "collector_action",
                    "include_raw",
                    "fact_type",
                    "knowledge_id",
                    "train",
                    "note",
                    "state_value",
                    "dimension",
                )
                if k in lab
            }
    # positive / negative helpers for binary
    pos_key = f"{head_name}.{values[0]}" if values else None
    neg_key = f"{head_name}.{values[-1]}" if len(values) >= 2 else None
    return {
        "head": head_name,
        "schema_values": values,
        "schema_kind": schema_h.kind if schema_h else None,
        "schema_type": schema_h.type if schema_h else None,
        "ontology_head": {
            k: heads_block[k]
            for k in ("type", "values", "exclusive", "train", "train_labels", "note")
            if k in heads_block
        },
        "positive_definition": (labels_out.get(pos_key) or {}).get("definition")
        if pos_key
        else None,
        "negative_definition": (labels_out.get(neg_key) or {}).get("definition")
        if neg_key
        else None,
        "positive_collector_action": (labels_out.get(pos_key) or {}).get(
            "collector_action"
        )
        if pos_key
        else None,
        "labels": labels_out,
    }


def write_identity_process(
    out_dir: Path,
    ont: dict[str, Any],
    schema: MultiheadSchema,
    train_samples: list[StateSample],
    test_samples: list[StateSample],
    n_pos: int,
) -> None:
    d = out_dir / "02_identity_process"
    d.mkdir(parents=True, exist_ok=True)
    bundle = extract_head_ontology(ont, schema, "IdentityProcess")
    (d / "ontology_snippet.yaml").write_text(
        yaml.safe_dump(bundle, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    positives: list[StateSample] = []
    for pool in (train_samples, test_samples):
        for s in pool:
            if s.labels.get("IdentityProcess") == "yes":
                positives.append(s)
    # Prefer train, then test; dedupe by sample_id
    seen: set[str] = set()
    picked: list[StateSample] = []
    for s in positives:
        sid = sample_id(s)
        if sid in seen:
            continue
        seen.add(sid)
        picked.append(s)
        if len(picked) >= n_pos:
            break

    md = [
        "# IdentityProcess positive examples",
        "",
        f"n_requested={n_pos}, n_exported={len(picked)} "
        f"(pool positives={len(positives)}; train+test evidence yes)",
        "",
        "Use these to decide Event vs Process vs Fact (see `boundary_checklist.md`).",
        "",
    ]
    jsonl = d / "positive_examples.jsonl"
    with jsonl.open("w", encoding="utf-8") as jf:
        for i, s in enumerate(picked, 1):
            all_fired = list(s.meta.get("fired") or [])
            ip_fired = [
                fr
                for fr in all_fired
                if str(fr.get("head") or "") == "IdentityProcess"
            ]
            row = {
                "sample_id": sample_id(s),
                "split": s.split,
                "conversation_id": s.conversation_id,
                "turn_id": s.turn_id,
                "gold": "IdentityProcess=yes",
                "conversation_window": s.text,
                "window_turns": format_window_turns(s.text),
                "window_raws": list(
                    s.meta.get("window_raws") or s.meta.get("memory_raws") or []
                ),
                "fired_identity": ip_fired,
                "fired_sample": all_fired[:12],
            }
            jf.write(json.dumps(row, ensure_ascii=False) + "\n")
            md.append(f"## Example {i} (`{s.split}`)")
            md.append("")
            md.append(f"sample_id: `{row['sample_id']}`")
            md.append("")
            md.append("conversation window:")
            for ti, turn in enumerate(row["window_turns"], 1):
                md.append(f"turn{ti}:")
                md.append(turn)
                md.append("")
            md.append("gold: IdentityProcess=yes")
            md.append("")
            if row.get("window_raws"):
                md.append(f"window_raws: `{row['window_raws']}`")
                md.append("")
            md.append("---")
            md.append("")
    (d / "positive_examples.md").write_text("\n".join(md), encoding="utf-8")

    checklist = f"""# IdentityProcess — Task Boundary Checklist

## Ontology (auto-extracted)

```yaml
{yaml.safe_dump({
    'definition': bundle.get('positive_definition'),
    'collector_action': bundle.get('positive_collector_action'),
    'fact_type': ((bundle.get('labels') or {}).get('IdentityProcess.yes') or {{}}).get('fact_type'),
    'train': ((bundle.get('labels') or {}).get('IdentityProcess.yes') or {{}}).get('train'),
    'schema_kind': bundle.get('schema_kind'),
}, allow_unicode=True, sort_keys=False).strip()}
```

## Business use (fill in)

Pick **one** primary use (or document mix):

| Option | Description | Implication |
|--------|-------------|-------------|
| A Event | Gate: identity verified → then allow negotiation | Redesign as event / drop from State primary score |
| B Process state | Ongoing identity-verification status in dialogue | Keep as process; may need train=true |
| C Fact | Durable identity/debt-awareness fact | Move to Fact/Memory, not Softmax state |

Your choice: _TODO_

Collector next move this head uniquely enables (V4 principle):
_TODO_

## Decision

- [ ] delete from Softmax schema
- [ ] keep eval-only (current: train=false) / Excluded from primary score
- [ ] event redesign + separate metric
- [ ] promote to trained process head

Notes: _TODO_
"""
    (d / "boundary_checklist.md").write_text(checklist, encoding="utf-8")


# ---------------------------------------------------------------------------
# P1: long-tail distribution
# ---------------------------------------------------------------------------


def count_head_values(
    samples: list[StateSample],
    schema: MultiheadSchema,
    head_name: str,
) -> dict[str, int]:
    h = next(x for x in schema.heads if x.name == head_name)
    counts = {v: 0 for v in h.values}
    unknown = 0
    masked = 0
    for s in samples:
        lab = s.labels.get(h.name, "unknown")
        m = float(s.head_mask.get(h.name, 0))
        if h.name == "IdentityProcess":
            if lab in ("unknown", ""):
                unknown += 1
                continue
        elif m < 0.5 or lab in ("unknown", ""):
            masked += 1
            continue
        if lab not in counts:
            unknown += 1
            continue
        counts[lab] += 1
    out = dict(counts)
    out["_unknown_or_masked"] = unknown + masked
    out["_supervised_total"] = sum(counts.values())
    return out


def write_distributions(
    out_dir: Path,
    schema: MultiheadSchema,
    train_samples: list[StateSample],
    test_samples: list[StateSample],
    val_samples: list[StateSample] | None,
) -> None:
    d = out_dir / "03_longtail_distribution"
    d.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"note": "evidence-only counts (mask=1; IdentityProcess: label≠unknown)"}
    md = [
        "# Multi-state train / test distribution",
        "",
        "Evidence-only: `head_mask=1` and label ≠ unknown "
        "(IdentityProcess: label ≠ unknown even if mask=0).",
        "",
        "Interpretation:",
        "- train rare + test rare → data collection / merge",
        "- train ample + test recall≈0 → model or definition",
        "",
    ]
    for head in MULTI_STATE_HEADS:
        tr = count_head_values(train_samples, schema, head)
        te = count_head_values(test_samples, schema, head)
        va = count_head_values(val_samples, schema, head) if val_samples else None
        payload[head] = {"train": tr, "test": te, "val": va}
        h = next(x for x in schema.heads if x.name == head)
        md.append(f"## `{head}`")
        md.append("")
        md.append("| value | train | test | val |")
        md.append("|---|---:|---:|---:|")
        for v in h.values:
            md.append(
                f"| `{v}` | {tr.get(v, 0)} | {te.get(v, 0)} | "
                f"{(va or {}).get(v, '—')} |"
            )
        md.append(
            f"| **supervised total** | {tr['_supervised_total']} | "
            f"{te['_supervised_total']} | "
            f"{(va or {}).get('_supervised_total', '—')} |"
        )
        md.append("")
    (d / "multi_state_train_test.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (d / "multi_state_train_test.md").write_text("\n".join(md), encoding="utf-8")


# ---------------------------------------------------------------------------
# P1: ontology snippets
# ---------------------------------------------------------------------------


def write_ontology_heads(
    out_dir: Path, ont: dict[str, Any], schema: MultiheadSchema
) -> None:
    d = out_dir / "04_ontology_heads"
    d.mkdir(parents=True, exist_ok=True)
    bundle: dict[str, Any] = {}
    for name in ONTOLOGY_FOCUS_HEADS:
        block = extract_head_ontology(ont, schema, name)
        bundle[name] = block
        (d / f"{name}.yaml").write_text(
            yaml.safe_dump(block, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    (d / "heads_bundle.yaml").write_text(
        yaml.safe_dump(bundle, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    md = [
        "# Ontology decision pack (5 heads)",
        "",
        "V4 check: does each **value** imply a distinct **collector next move**?",
        "",
        "| Head | Value | collector_action (short) | Distinct action? |",
        "|---|---|---|---|",
    ]
    for name in ONTOLOGY_FOCUS_HEADS:
        labs = (bundle[name].get("labels") or {})
        for key, lab in labs.items():
            val = key.split(".", 1)[-1]
            action = (lab.get("collector_action") or "")[:80]
            md.append(f"| `{name}` | `{val}` | {action} | _TODO_ |")
    md.extend(["", "Files: `*.yaml`, `heads_bundle.yaml`", ""])
    (d / "INDEX.md").write_text("\n".join(md), encoding="utf-8")


# ---------------------------------------------------------------------------
# Templates / README
# ---------------------------------------------------------------------------


def write_templates(out_dir: Path) -> None:
    (out_dir / "00_DECISION_TEMPLATE.md").write_text(
        """# Decision package template (fill after audit)

## Business priority (edit stars)

| Head | Business importance | Notes |
|------|---------------------|-------|
| IdentityProcess | ★★★★★ | |
| FinancialHardship | ★★★★★ | |
| NegotiationRequest | ★★★★★ | |
| Contactability | ★★★★ | |
| RepaymentCapability | ★★★★ | |
| Commitment | ★★★ | |
| Asset | ★★ | |
| (other) | | |

## Decision table

| Head | Problem type | Evidence | Action | Priority |
|------|--------------|----------|--------|----------|
| Asset | ontology / model / data | residual 01_ | freeze / patch / retrain / resample | |
| Contactability | boundary / model | residual 01_ | keep / adjust def / retrain | |
| Commitment | long-tail | dist 03_ + residual | merge / sample / loss | |
| RepaymentCapability | coverage | dist 03_ | collect insufficient data | |
| IdentityProcess | task boundary | 02_ | event redesign / drop primary | |

## Confidence rule of thumb (from residual cases)

| Pattern | Likely cause | Next step |
|---------|--------------|-----------|
| pred≈0.99, gold≈0.01 | not learned / systematic | check train count; then loss/sample or ontology |
| pred≈0.55, gold≈0.45 | boundary | ontology / annotation first |
| gold contradicts text | label_error | fix mapping / include_raw |
""",
        encoding="utf-8",
    )


def write_readme(
    out_dir: Path,
    *,
    ckpt: Path,
    split: str,
    parts: list[str],
    ontology: Path,
    residual_counts: dict[str, int] | None,
) -> None:
    lines = [
        "# Decision package v3.1.2",
        "",
        f"- generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"- ckpt: `{ckpt}`",
        f"- residual split: `{split}`",
        f"- ontology: `{ontology}`",
        f"- parts: {', '.join(parts)}",
        "",
        "## Contents",
        "",
        "| Dir | Answers |",
        "|-----|---------|",
        "| `01_residual_audit/` | Which errors? model vs ontology vs label (P0) + confidence (P2) |",
        "| `02_identity_process/` | Keep / event / drop? (P0.5) |",
        "| `03_longtail_distribution/` | Need data vs model? (P1) |",
        "| `04_ontology_heads/` | Patch ontology? (P1) |",
        "| `00_DECISION_TEMPLATE.md` | Fill decision + business priority (P2) |",
        "",
    ]
    if residual_counts:
        lines.append("## Residual case counts")
        lines.append("")
        for k, n in residual_counts.items():
            lines.append(f"- `{k}`: **{n}**")
        lines.append("")
    lines.extend(
        [
            "## Suggested review order",
            "",
            "1. Read all cases under `01_residual_audit/` (batch 1)",
            "2. Fill IdentityProcess `02_identity_process/boundary_checklist.md` (batch 2)",
            "3. Compare `03_longtail_distribution/` train vs test (batch 3)",
            "4. Complete `00_DECISION_TEMPLATE.md`",
            "",
        ]
    )
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def parse_parts(raw: str) -> list[str]:
    allowed = {"residual", "identity", "distribution", "ontology", "all"}
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if "all" in parts:
        return ["residual", "identity", "distribution", "ontology"]
    bad = [p for p in parts if p not in allowed]
    if bad:
        raise SystemExit(f"Unknown --parts {bad}; allowed={sorted(allowed)}")
    if not parts:
        raise SystemExit("--parts empty")
    return parts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=MH_ROOT / "configs" / "train_state.yaml")
    ap.add_argument(
        "--ckpt",
        type=Path,
        default=None,
        help="Required when --parts includes residual",
    )
    ap.add_argument(
        "--parts",
        type=str,
        default="all",
        help="Comma list: residual,identity,distribution,ontology,all",
    )
    ap.add_argument("--split", choices=["val", "test"], default="test", help="Split for residual inference")
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--device", type=str, default=None)
    ap.add_argument("--ontology", type=Path, default=None)
    ap.add_argument("--identity-positives", type=int, default=20)
    ap.add_argument("--batch-size", type=int, default=None)
    ap.add_argument("--train-jsonl", type=Path, default=None, help="Override train jsonl")
    ap.add_argument("--val-jsonl", type=Path, default=None, help="Override val jsonl")
    ap.add_argument("--test-jsonl", type=Path, default=None, help="Override test jsonl")
    args = ap.parse_args()
    parts = parse_parts(args.parts)
    if "residual" in parts and args.ckpt is None:
        raise SystemExit("--ckpt is required for --parts residual / all")

    config = yaml.safe_load(args.config.read_text(encoding="utf-8")) or {}
    if args.device:
        config["device"] = args.device
    schema_path = resolve_path(args.config, config.get("schema_path", "configs/schema_v3.1.yaml"))
    schema = load_schema(str(schema_path))
    config["schema_path"] = str(schema_path)

    data_cfg = config.get("data") or {}
    train_path = args.train_jsonl or resolve_path(
        args.config, data_cfg.get("train", "data/state/state_train.jsonl")
    )
    val_path = args.val_jsonl or resolve_path(
        args.config, data_cfg.get("val", "data/state/state_val.jsonl")
    )
    test_path = args.test_jsonl or resolve_path(
        args.config, data_cfg.get("test", "data/state/state_test.jsonl")
    )
    residual_path = test_path if args.split == "test" else val_path

    if args.out_dir is not None:
        out_dir = args.out_dir
    elif args.ckpt is not None:
        out_dir = args.ckpt.parent / "decision_package_v312"
    else:
        out_dir = MH_ROOT / "artifacts" / "decision_package_v312"
    out_dir.mkdir(parents=True, exist_ok=True)

    model_name = config.get("model_name", "__mock__")
    if model_name != "__mock__":
        mp = resolve_path(args.config, model_name)
        if mp.exists():
            config["model_name"] = str(mp)

    ont_path = find_ontology(args.ontology)
    ont = yaml.safe_load(ont_path.read_text(encoding="utf-8")) or {}

    print(
        f"export decision package → {out_dir}\n"
        f"  parts={parts} ckpt={args.ckpt} residual_data={residual_path}\n"
        f"  ontology={ont_path} env=({describe_device_env()})",
        flush=True,
    )

    train_samples = load_state_jsonl(train_path) if (
        "identity" in parts or "distribution" in parts
    ) else []
    val_samples = load_state_jsonl(val_path) if "distribution" in parts and val_path.exists() else []
    test_samples = load_state_jsonl(test_path) if (
        "identity" in parts or "distribution" in parts or "residual" in parts
    ) else []
    residual_samples = (
        load_state_jsonl(residual_path) if "residual" in parts else []
    )
    if "residual" in parts and not residual_samples:
        raise SystemExit(f"No residual samples at {residual_path}")

    residual_counts: dict[str, int] | None = None
    if "residual" in parts:
        device = get_device(config)
        print(f"device={device}", flush=True)
        model = load_model(config, args.ckpt, device)
        bs = int(args.batch_size or config.get("batch_size", 16))
        buckets = collect_confusion_cases(
            model,
            residual_samples,
            schema,
            device,
            bs,
            DEFAULT_CONFUSION_SPECS,
        )
        write_residual_audit(out_dir, buckets, DEFAULT_CONFUSION_SPECS)
        residual_counts = {
            f"{h}:{g}→{p}": len(buckets.get((h, g, p), []))
            for h, g, p in DEFAULT_CONFUSION_SPECS
        }
        print("residual counts:", json.dumps(residual_counts, ensure_ascii=False), flush=True)

    if "identity" in parts:
        # ensure pools loaded
        if not train_samples:
            train_samples = load_state_jsonl(train_path)
        if not test_samples:
            test_samples = load_state_jsonl(test_path)
        write_identity_process(
            out_dir,
            ont,
            schema,
            train_samples,
            test_samples,
            args.identity_positives,
        )
        print(f"wrote identity pack ({args.identity_positives} positives target)", flush=True)

    if "distribution" in parts:
        if not train_samples:
            train_samples = load_state_jsonl(train_path)
        if not test_samples:
            test_samples = load_state_jsonl(test_path)
        write_distributions(out_dir, schema, train_samples, test_samples, val_samples or None)
        print("wrote long-tail distributions", flush=True)

    if "ontology" in parts:
        write_ontology_heads(out_dir, ont, schema)
        print("wrote ontology head snippets", flush=True)

    write_templates(out_dir)
    write_readme(
        out_dir,
        ckpt=args.ckpt or Path("(not used)"),
        split=args.split,
        parts=parts,
        ontology=ont_path,
        residual_counts=residual_counts,
    )
    print(f"DONE → {out_dir / 'README.md'}", flush=True)


if __name__ == "__main__":
    main()
