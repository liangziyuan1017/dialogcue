"""Per-head evaluation metrics for state multihead (evidence-only).

Report framework v3.2: primary business metrics are pos-* for binary heads
and per-class recall for multi-state heads. Legacy head-macro averages stay
in the appendix only.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from schema_loader import MultiheadSchema


def _f1(p: float, r: float) -> float:
    if p + r <= 0:
        return 0.0
    return 2 * p * r / (p + r)


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    return p, r, _f1(p, r)


def head_report_family(h: Any) -> str:
    """binary_evidence vs multi_state for v3.2 reporting."""
    n = len(getattr(h, "values", ()) or ())
    t = str(getattr(h, "type", "") or "").lower()
    if t == "binary" or n <= 2:
        return "binary_evidence"
    return "multi_state"


def is_non_primary_head(h: Any, train_mask: dict) -> bool:
    """Heads excluded from primary State Multihead score (e.g. IdentityProcess)."""
    if train_mask.get(h.name, 1) == 0:
        return True
    if h.name == "IdentityProcess" or h.kind == "event":
        return True
    return False


def _primary_metric_name(h: Any, family: str, train_mask: dict) -> str:
    if is_non_primary_head(h, train_mask):
        return "Excluded from primary score"
    if family == "multi_state":
        return "class-macro-F1"
    if h.kind == "process":
        return "pos-F1"
    return "pos-F1"


def _class_coverage_fields(
    per_class: dict[str, Any], labels: list[str]
) -> dict[str, Any]:
    n_classes = len(labels)
    active = sum(
        1
        for lab in labels
        if int((per_class.get(lab) or {}).get("support") or 0) > 0
    )
    return {
        "n_classes": n_classes,
        "active_classes": active,
        "class_coverage": round(active / n_classes, 4) if n_classes else 0.0,
    }


def evaluate_predictions(
    schema: MultiheadSchema,
    y_true: dict[str, list[str]],
    y_pred: dict[str, list[str]],
    *,
    head_mask_rows: dict[str, list[int]] | None = None,
) -> dict[str, Any]:
    """
    y_true/y_pred: head -> list of value strings (per-head lengths may differ).
    Only pass evidence-supervised rows (caller filters unknown/mask=0).
    """
    del head_mask_rows
    per_head: dict[str, Any] = {}
    macro_f1s: list[float] = []
    weighted_num = 0.0
    weighted_den = 0.0
    wpos_f1_num = wpos_p_num = wpos_r_num = 0.0
    wpos_den = 0.0

    for h in schema.heads:
        truths = list(y_true.get(h.name) or [])
        preds = list(y_pred.get(h.name) or [])
        if len(truths) != len(preds):
            raise ValueError(
                f"{h.name}: y_true len {len(truths)} != y_pred len {len(preds)}"
            )
        labels = list(h.values)
        class_scores = {}
        f1s = []
        support_sum = 0
        for lab in labels:
            tp = fp = fn = 0
            for t, p in zip(truths, preds):
                if t == lab and p == lab:
                    tp += 1
                elif p == lab and t != lab:
                    fp += 1
                elif t == lab and p != lab:
                    fn += 1
            prec, rec, f1 = _prf(tp, fp, fn)
            support = sum(1 for t in truths if t == lab)
            class_scores[lab] = {
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
                "support": support,
                "tp": tp,
                "fp": fp,
                "fn": fn,
            }
            f1s.append(f1)
            support_sum += support

        default = h.values[-1]
        pos_labs = [v for v in labels if v != default]
        tp = fp = fn = 0
        for lab in pos_labs:
            for t, p in zip(truths, preds):
                if t == lab and p == lab:
                    tp += 1
                elif p == lab and t != lab:
                    fp += 1
                elif t == lab and p != lab:
                    fn += 1
        pos_p, pos_r, pos_f1 = _prf(tp, fp, fn)

        macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
        cw_num = cw_den = 0.0
        for sc in class_scores.values():
            s = int(sc["support"])
            if s <= 0:
                continue
            cw_num += float(sc["f1"]) * s
            cw_den += s
        class_weighted_f1 = cw_num / cw_den if cw_den else 0.0

        conf: Counter = Counter()
        for t, p in zip(truths, preds):
            if t != p:
                conf[f"{t}→{p}"] += 1

        n_h = len(truths)
        family = head_report_family(h)
        coverage = _class_coverage_fields(class_scores, labels)
        per_head[h.name] = {
            "kind": h.kind,
            "type": h.type,
            "report_family": family,
            "macro_f1": round(macro_f1, 4),
            "class_weighted_f1": round(class_weighted_f1, 4),
            "positive_f1": round(pos_f1, 4),
            "positive_precision": round(pos_p, 4),
            "positive_recall": round(pos_r, 4),
            "accuracy": round(
                sum(1 for t, p in zip(truths, preds) if t == p) / max(n_h, 1), 4
            ),
            "per_class": class_scores,
            "confusion_top": dict(conf.most_common(12)),
            "support": n_h,
            "default_value": default,
            **coverage,
        }
        if n_h > 0:
            macro_f1s.append(macro_f1)
            weighted_num += macro_f1 * max(support_sum, 1)
            weighted_den += max(support_sum, 1)
            wpos_f1_num += pos_f1 * n_h
            wpos_p_num += pos_p * n_h
            wpos_r_num += pos_r * n_h
            wpos_den += n_h

    overall_macro = sum(macro_f1s) / len(macro_f1s) if macro_f1s else 0.0
    overall_weighted = weighted_num / weighted_den if weighted_den else 0.0

    by_kind: dict[str, list[float]] = defaultdict(list)
    for h in schema.heads:
        if per_head[h.name]["support"] > 0:
            by_kind[h.kind].append(per_head[h.name]["macro_f1"])

    return {
        "report_version": "v3.2_eval",
        "n_samples_scored_note": (
            "head-level evidence instances (sum of per-head supports); "
            "not dialogue count — lengths differ under evidence-only"
        ),
        "n_heads_scored": len(macro_f1s),
        "evidence_samples": int(wpos_den),
        "head_level_evidence_instances": int(wpos_den),
        "exact_match": None,
        "weighted_positive_f1": round(wpos_f1_num / wpos_den, 4) if wpos_den else 0.0,
        "weighted_positive_precision": round(wpos_p_num / wpos_den, 4)
        if wpos_den
        else 0.0,
        "weighted_positive_recall": round(wpos_r_num / wpos_den, 4) if wpos_den else 0.0,
        "macro_f1": round(overall_macro, 4),
        "weighted_macro_f1": round(overall_weighted, 4),
        "macro_f1_by_kind": {
            k: round(sum(v) / len(v), 4) if v else 0.0 for k, v in by_kind.items()
        },
        "per_head": per_head,
    }


def enrich_metrics_from_per_head(metrics: dict[str, Any], schema: MultiheadSchema) -> dict[str, Any]:
    """Fill v3.2 fields if loading an older eval_*.json that only has per_head."""
    out = dict(metrics)
    per_head = out.get("per_head") or {}
    wpos_f1_num = wpos_p_num = wpos_r_num = wpos_den = 0.0
    for h in schema.heads:
        m = dict(per_head.get(h.name) or {})
        m["report_family"] = m.get("report_family") or head_report_family(h)
        m.setdefault("type", h.type)
        m.setdefault("default_value", h.values[-1] if h.values else "")
        if "class_weighted_f1" not in m and m.get("per_class"):
            cw_num = cw_den = 0.0
            for sc in m["per_class"].values():
                s = int(sc.get("support") or 0)
                if s <= 0:
                    continue
                cw_num += float(sc.get("f1") or 0.0) * s
                cw_den += s
            m["class_weighted_f1"] = round(cw_num / cw_den, 4) if cw_den else 0.0
        if m.get("per_class") is not None:
            cov = _class_coverage_fields(m.get("per_class") or {}, list(h.values))
            m.update(cov)
        per_head[h.name] = m
        n = int(m.get("support") or 0)
        if n > 0:
            wpos_f1_num += float(m.get("positive_f1") or 0.0) * n
            wpos_p_num += float(m.get("positive_precision") or 0.0) * n
            wpos_r_num += float(m.get("positive_recall") or 0.0) * n
            wpos_den += n
    out["per_head"] = per_head
    out["evidence_samples"] = int(wpos_den)
    out["head_level_evidence_instances"] = int(wpos_den)
    out["n_samples_scored_note"] = (
        "head-level evidence instances (sum of per-head supports); "
        "not dialogue count — lengths differ under evidence-only"
    )
    out["weighted_positive_f1"] = (
        round(wpos_f1_num / wpos_den, 4) if wpos_den else 0.0
    )
    out["weighted_positive_precision"] = (
        round(wpos_p_num / wpos_den, 4) if wpos_den else 0.0
    )
    out["weighted_positive_recall"] = (
        round(wpos_r_num / wpos_den, 4) if wpos_den else 0.0
    )
    out["n_heads_scored"] = sum(
        1 for h in schema.heads if int((per_head.get(h.name) or {}).get("support") or 0) > 0
    )
    out["report_version"] = "v3.2_eval"
    return out


def format_metrics_md(
    metrics: dict,
    schema: MultiheadSchema,
    *,
    meta: dict[str, Any] | None = None,
) -> str:
    metrics = enrich_metrics_from_per_head(metrics, schema)
    train_mask = schema.default_head_mask or {}
    meta = dict(meta or {})
    meta.setdefault("ontology", "v3.1.2 freeze")
    meta.setdefault("model", "state_best.pt")
    meta.setdefault("split", "test")
    meta.setdefault(
        "timestamp",
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    n_evidence = metrics.get("head_level_evidence_instances") or metrics.get(
        "evidence_samples"
    )

    lines: list[str] = [
        "# State Multihead Eval Report v3.2",
        "",
        "## Evaluation Setting",
        "",
        f"- ontology: {meta.get('ontology')}",
        f"- model: {meta.get('model')}",
        "- scoring: evidence-only",
        "  - unknown excluded",
        "  - head_mask=0 excluded",
        f"- split: {meta.get('split')}",
        f"- heads evaluated: {metrics.get('n_heads_scored')}",
        f"- head-level evidence instances (sum of per-head supports): {n_evidence}",
        "  - not dialogue count; each row is one (head, labeled instance) under evidence-only",
        f"- timestamp: {meta.get('timestamp')}",
        "",
        "## 1. Overall Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Evidence Positive F1 (weighted) | **{metrics.get('weighted_positive_f1')}** |",
        f"| Evidence Positive Precision (weighted) | {metrics.get('weighted_positive_precision')} |",
        f"| Evidence Positive Recall (weighted) | {metrics.get('weighted_positive_recall')} |",
        f"| Evaluated Heads | {metrics.get('n_heads_scored')} |",
        f"| Head-level evidence instances | {n_evidence} |",
        "",
        "By slice:",
        "",
        "| slice | heads (support>0) | main metric shown |",
        "|---|---:|---|",
    ]

    def _count_slice(pred) -> int:
        return sum(
            1
            for h in schema.heads
            if int((metrics["per_head"].get(h.name) or {}).get("support") or 0) > 0
            and pred(h, metrics["per_head"][h.name])
        )

    lines.append(
        f"| state (binary-like) | {_count_slice(lambda h, m: h.kind == 'state' and m.get('report_family') == 'binary_evidence')} | weighted pos-F1 |"
    )
    lines.append(
        f"| state (multi-state) | {_count_slice(lambda h, m: h.kind == 'state' and m.get('report_family') == 'multi_state')} | class-macro-F1 + per-class recall |"
    )
    lines.append(
        f"| process | {_count_slice(lambda h, m: h.kind == 'process' and not is_non_primary_head(h, train_mask))} | pos-F1 |"
    )
    lines.append(
        f"| non-primary | {_count_slice(lambda h, m: is_non_primary_head(h, train_mask))} | Excluded from primary score |"
    )
    lines.extend(
        [
            "",
            "> Evidence Positive *: support-weighted mean of per-head pos-P/R/F1 "
            "(binary: positive class; multi-state: non-default micro aggregation). "
            "**Interpret together with class coverage** — a head can score near 1.0 "
            "while only one state appears in the eval set.",
            "",
            "## 1b. Coverage Summary",
            "",
            "| Head | Supported classes | Total classes | Class coverage |",
            "|---|---:|---:|---:|",
        ]
    )
    for h in schema.heads:
        m = metrics["per_head"][h.name]
        if int(m.get("support") or 0) <= 0:
            continue
        active = int(m.get("active_classes") or 0)
        total = int(m.get("n_classes") or len(h.values))
        cov = float(m.get("class_coverage") or 0.0)
        mark = " †" if is_non_primary_head(h, train_mask) else ""
        lines.append(
            f"| `{h.name}`{mark} | {active} | {total} | {cov:.1%} |"
        )
    lines.extend(
        [
            "",
            "† Non-primary head (excluded from primary State Multihead score).",
            "",
            "## 2. Head Summary",
            "",
            "| Head | Kind | Type | Support | Active/Total | Primary Metric |",
            "|---|---|---|---:|---:|---|",
        ]
    )
    for h in schema.heads:
        m = metrics["per_head"][h.name]
        family = m.get("report_family") or head_report_family(h)
        type_label = "multi-state" if family == "multi_state" else "binary"
        if is_non_primary_head(h, train_mask):
            type_label = "non-primary"
        elif h.kind == "event":
            type_label = "event"
        primary = _primary_metric_name(h, family, train_mask)
        active = int(m.get("active_classes") or 0)
        total = int(m.get("n_classes") or len(h.values))
        lines.append(
            f"| `{h.name}` | {m['kind']} | {type_label} | {m['support']} | "
            f"{active}/{total} | {primary} |"
        )

    # --- Binary state ---
    lines.extend(
        [
            "",
            "## 3. Binary Heads (state, primary: pos-F1)",
            "",
            "| Head | Support | Pos-P | Pos-R | Pos-F1 | Acc |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for h in schema.heads:
        m = metrics["per_head"][h.name]
        if m.get("report_family") != "binary_evidence" or h.kind != "state":
            continue
        lines.append(
            f"| `{h.name}` | {m['support']} | {m['positive_precision']} | "
            f"{m['positive_recall']} | {m['positive_f1']} | {m['accuracy']} |"
        )
    lines.extend(
        [
            "",
            "Note: class-macro-F1 is **not** primary for evidence-only binary heads "
            "(default class often has zero support → macro ≈ 0.5 even when pos-F1 = 1.0).",
            "",
            "## 4. Multi-state Heads (primary: per-class recall)",
            "",
        ]
    )
    for h in schema.heads:
        m = metrics["per_head"][h.name]
        if m.get("report_family") != "multi_state":
            continue
        default = m.get("default_value") or (h.values[-1] if h.values else "")
        active = int(m.get("active_classes") or 0)
        total = int(m.get("n_classes") or len(h.values))
        cov = float(m.get("class_coverage") or 0.0)
        lines.append(f"### `{h.name}`")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("|---|---:|")
        lines.append(f"| support | {m['support']} |")
        lines.append(f"| Active classes | {active}/{total} |")
        lines.append(f"| Classes with support>0 | {active} |")
        lines.append(f"| Class coverage | {cov:.1%} |")
        lines.append(f"| class-macro-F1 | {m['macro_f1']} |")
        lines.append(f"| class-weighted-F1 | {m.get('class_weighted_f1', 'n/a')} |")
        lines.append(f"| acc | {m['accuracy']} |")
        lines.append(f"| Evidence Positive F1 (non-default micro) | {m['positive_f1']} |")
        lines.append(f"| default value | `{default}` |")
        lines.append("")
        lines.append("| Class | Support | Precision | Recall | F1 |")
        lines.append("|---|---:|---:|---:|---:|")
        for lab in h.values:
            sc = (m.get("per_class") or {}).get(lab) or {}
            lines.append(
                f"| `{lab}` | {sc.get('support', 0)} | {sc.get('precision', 0.0)} | "
                f"{sc.get('recall', 0.0)} | {sc.get('f1', 0.0)} |"
            )
        conf = m.get("confusion_top") or {}
        if conf:
            lines.append("")
            lines.append("Confusion (top):")
            for k, c in conf.items():
                lines.append(f"- `{k}`: {c}")
        if active < total:
            lines.append("")
            lines.append(
                f"> Class coverage {cov:.1%} ({active}/{total}): high acc / "
                "class-weighted-F1 may reflect only the observed states — "
                "do not read as full multi-state mastery."
            )
        lines.append("")

    # --- Process / Event ---
    lines.extend(
        [
            "## 5. Process / Event Heads",
            "",
            "| Head | Kind | Support | Pos-P | Pos-R | Pos-F1 | Note |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for h in schema.heads:
        if h.kind not in ("process", "event"):
            continue
        m = metrics["per_head"][h.name]
        notes = []
        if is_non_primary_head(h, train_mask):
            notes.append("Excluded from primary score")
        if train_mask.get(h.name, 1) == 0:
            notes.append("train=false")
        if h.kind == "event" and float(m.get("positive_recall") or 0) < 0.5:
            notes.append("low recall")
        lines.append(
            f"| `{h.name}` | {h.kind} | {m['support']} | "
            f"{m['positive_precision']} | {m['positive_recall']} | "
            f"{m['positive_f1']} | {'; '.join(notes) or '-'} |"
        )

    # --- Error summary ---
    lines.extend(["", "## 6. Error Summary", "", "Top confusion:", ""])
    any_err = False
    for h in schema.heads:
        conf = metrics["per_head"][h.name].get("confusion_top") or {}
        if not conf:
            continue
        any_err = True
        lines.append(f"### {h.name}")
        lines.append("")
        for k, c in conf.items():
            lines.append(f"- `{k}`: {c}")
        lines.append("")
    if not any_err:
        lines.append("_No confusions recorded._")
        lines.append("")

    # --- Confidence placeholder ---
    lines.extend(
        [
            "## 7. Confidence Analysis",
            "",
            "_Not populated in offline reformat (requires eval-time logit/confidence "
            "capture). Re-run `eval_state.py` after confidence logging is enabled._",
            "",
            "| Head | Avg confidence (correct) | Avg confidence (error) |",
            "|---|---:|---:|",
            "| _(pending)_ | — | — |",
            "",
            "## 8. Appendix — Legacy Metrics",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| macro-F1 | {metrics.get('macro_f1')} |",
            f"| weighted macro-F1 | {metrics.get('weighted_macro_f1')} |",
            f"| by kind | `{metrics.get('macro_f1_by_kind')}` |",
            "",
            "> Legacy metrics are kept for backward compatibility only and are "
            "**not** primary evaluation criteria under evidence-only binary heads.",
            "",
            "> Not comparable across ontology versions when evidence policy changes.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"
