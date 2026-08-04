"""Audit reports for multihead state dataset build (human review)."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from schema_loader import MultiheadSchema


def _pack_counter(counter: Counter) -> dict:
    return {
        "unique_count": len(counter),
        "event_count": int(sum(counter.values())),
        "by_label": dict(counter.most_common()),
    }


def _default_value(schema: MultiheadSchema, head: str) -> str:
    h = schema.head_by_name().get(head)
    return h.values[-1] if h and h.values else "none"


def _supervision_stats(rows: list[dict], schema: MultiheadSchema) -> dict[str, Any]:
    """P0.5: per-head positive / negative / unknown / masked ratio."""
    n = max(len(rows), 1)
    out: dict[str, Any] = {"n_samples": len(rows), "per_head": {}}
    for h in schema.heads:
        default = _default_value(schema, h.name)
        pos = neg = unk = masked = 0
        for r in rows:
            lab = str((r.get("labels") or {}).get(h.name, "unknown"))
            mask = int((r.get("head_mask") or {}).get(h.name, 0))
            if mask == 0 or lab == "unknown":
                unk += 1
                masked += 1
            elif lab == default:
                neg += 1
            else:
                pos += 1
        out["per_head"][h.name] = {
            "kind": h.kind,
            "positive": pos,
            "negative": neg,
            "unknown": unk,
            "masked": masked,
            "masked_ratio": round(masked / n, 4),
            "positive_rate_among_supervised": (
                round(pos / max(pos + neg, 1), 4) if (pos + neg) else None
            ),
        }
    return out


def _percentiles(values: list[float], ps: tuple[int, ...] = (50, 90, 99)) -> dict:
    if not values:
        return {"count": 0}
    s = sorted(values)
    n = len(s)

    def _pct(p: int) -> float:
        if n == 1:
            return float(s[0])
        idx = min(n - 1, max(0, int(round((p / 100) * (n - 1)))))
        return float(s[idx])

    out: dict[str, Any] = {
        "count": n,
        "min": s[0],
        "max": s[-1],
        "mean": round(sum(s) / n, 2),
    }
    for p in ps:
        out[f"p{p}"] = _pct(p)
    return out


def aggregate_state_profile(
    rows: list[dict],
    schema: MultiheadSchema,
    *,
    split_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    n = len(rows)
    conv_ids = {r["conversation_id"] for r in rows}
    defaults = {h.name: _default_value(schema, h.name) for h in schema.heads}

    label_counts: dict[str, Counter] = {h.name: Counter() for h in schema.heads}
    positive_counts: Counter = Counter()
    unmapped_events: Counter = Counter()
    unmapped_first: Counter = Counter()  # first time raw appears in a conv
    relocated_events: Counter = Counter()
    conflict_heads: Counter = Counter()
    char_lens: list[float] = []
    n_turns_sel: list[float] = []
    trunc = 0
    nonempty = 0
    turns_with_raws = 0
    seen_raw_by_conv: dict[str, set[str]] = defaultdict(set)
    all_memory_raws: Counter = Counter()
    mapped_raws_c: Counter = Counter()
    split_counts: Counter = Counter()
    split_head_pos: dict[str, Counter] = defaultdict(Counter)

    for r in rows:
        split = str(r.get("split") or "unknown")
        split_counts[split] += 1
        cid = str(r["conversation_id"])
        meta = r.get("meta") or {}
        labs = r.get("labels") or {}
        inp = r.get("input") or {}

        char_lens.append(float(inp.get("char_len") or len(inp.get("context_window") or "")))
        n_turns_sel.append(float(inp.get("n_turns_selected") or 0))
        if inp.get("truncated"):
            trunc += 1

        # Prefer window-aligned raws (v3.1.2+); fall back to legacy cumulative field.
        window_raws = list(
            meta.get("window_raws")
            or meta.get("memory_raws")
            or []
        )
        if window_raws:
            turns_with_raws += 1
        for raw in window_raws:
            all_memory_raws[raw] += 1
            if raw not in seen_raw_by_conv[cid]:
                seen_raw_by_conv[cid].add(raw)

        for raw in meta.get("mapped_raws") or []:
            mapped_raws_c[raw] += 1

        for u in meta.get("unmapped_raws") or []:
            unmapped_events[u] += 1

        for item in meta.get("relocated_labels") or []:
            label = item.get("label")
            if not label:
                continue
            key = f"{label}:{item.get('from')}->{item.get('to')}"
            relocated_events[key] += 1

        for c in meta.get("conflicts_resolved") or []:
            conflict_heads[str(c.get("head") or "?")] += 1

        any_pos = False
        for h in schema.heads:
            v = str(labs.get(h.name, defaults[h.name]))
            mask = int((r.get("head_mask") or {}).get(h.name, 1))
            label_counts[h.name][v] += 1
            if mask > 0 and v not in ("unknown", defaults[h.name]):
                positive_counts[h.name] += 1
                split_head_pos[split][h.name] += 1
                any_pos = True
        if any_pos:
            nonempty += 1

    # first-seen unmapped: raws that ever appear in any memory and are never in map with rules
    by_conv: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_conv[str(r["conversation_id"])].append(r)
    for cid, samples in by_conv.items():
        samples.sort(key=lambda x: int(x.get("turn_id") or 0))
        seen: set[str] = set()
        for r in samples:
            meta = r.get("meta") or {}
            mem = list(meta.get("window_raws") or meta.get("memory_raws") or [])
            unmapped_set = set(meta.get("unmapped_raws") or [])
            for raw in mem:
                if raw in seen:
                    continue
                seen.add(raw)
                if raw in unmapped_set:
                    unmapped_first[raw] += 1

    head_positive_rate = {
        h.name: round(positive_counts[h.name] / n, 4) if n else 0.0 for h in schema.heads
    }
    zero_pos_heads = [h.name for h in schema.heads if positive_counts[h.name] == 0]

    unmap_rate_events = (
        round(sum(unmapped_events.values()) / turns_with_raws, 4) if turns_with_raws else 0.0
    )
    # sample-level: fraction of samples that have any unmapped_raws
    samples_with_unmap = sum(1 for r in rows if (r.get("meta") or {}).get("unmapped_raws"))
    unmap_rate_samples = round(samples_with_unmap / n, 4) if n else 0.0

    profile = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "n_samples": n,
        "n_conversations": len(conv_ids),
        "splits": dict(split_counts),
        "supervision": _supervision_stats(rows, schema),
        "window": {
            "truncated": trunc,
            "truncation_rate": round(trunc / n, 4) if n else 0.0,
            "char_len": _percentiles(char_lens),
            "n_turns_selected": _percentiles(n_turns_sel),
        },
        "labels": {
            "samples_with_any_nondefault": nonempty,
            "nondefault_rate": round(nonempty / n, 4) if n else 0.0,
            "per_head_value_counts": {h: dict(c) for h, c in label_counts.items()},
            "per_head_positive_count": dict(positive_counts),
            "per_head_positive_rate": head_positive_rate,
            "zero_positive_heads": zero_pos_heads,
            "per_split_positive_count": {k: dict(v) for k, v in split_head_pos.items()},
        },
        "mapping": {
            "turns_with_memory_raws": turns_with_raws,
            "unique_memory_raws": len(all_memory_raws),
            "top_memory_raws": dict(all_memory_raws.most_common(40)),
            "top_mapped_raws": dict(mapped_raws_c.most_common(40)),
            "unmapped_events": _pack_counter(unmapped_events),
            "unmapped_first_seen_per_conversation": _pack_counter(unmapped_first),
            "unmap_rate_events_per_turn_with_raws": unmap_rate_events,
            "unmap_rate_samples": unmap_rate_samples,
            "relocated_labels": _pack_counter(relocated_events),
            "conflicts_by_head": dict(conflict_heads.most_common()),
        },
        "split_manifest_summary": {
            "train_conversations": (
                len([c for c, s in (split_map or {}).items() if s == "train"]) if split_map else None
            ),
            "val_conversations": (
                len([c for c, s in (split_map or {}).items() if s == "val"]) if split_map else None
            ),
            "test_conversations": (
                len([c for c, s in (split_map or {}).items() if s == "test"]) if split_map else None
            ),
        },
    }
    return profile


def run_quality_checks(
    profile: dict,
    *,
    max_unmap_rate_samples: float = 0.15,
    max_truncation_rate: float = 0.50,
    require_positive_heads: bool = True,
    min_positive: int = 30,
    max_masked_ratio: float = 0.99,
    supervision_exclude_heads: list[str] | None = None,
) -> dict[str, Any]:
    """Dataset quality + P0.5 supervision gate (colleague: train-before review)."""
    errors: list[str] = []
    warnings: list[str] = []
    review: list[str] = []
    mapping = profile.get("mapping") or {}
    labels = profile.get("labels") or {}
    window = profile.get("window") or {}
    exclude = set(supervision_exclude_heads or ["IdentityProcess"])

    unmap_r = float(mapping.get("unmap_rate_samples") or 0.0)
    if unmap_r > max_unmap_rate_samples:
        errors.append(
            f"Q1 unmap_rate_samples={unmap_r:.3f} > {max_unmap_rate_samples}"
        )

    trunc_r = float(window.get("truncation_rate") or 0.0)
    if trunc_r > max_truncation_rate:
        warnings.append(
            f"W1 truncation_rate={trunc_r:.3f} > {max_truncation_rate}"
        )

    zero = list(labels.get("zero_positive_heads") or [])
    if require_positive_heads and zero:
        # IdentityProcess may be rare / masked — warn not error
        hard = [h for h in zero if h != "IdentityProcess"]
        if hard:
            warnings.append(f"W2 zero-positive heads: {hard}")
        if "IdentityProcess" in zero:
            warnings.append("W2 IdentityProcess has zero positives in this build")

    # P0.5 gate: positive < min OR masked_ratio > max → review (not hard fail)
    n = int(profile.get("n_samples") or 0)
    per_head = ((profile.get("supervision") or {}).get("per_head") or {})
    for head, row in per_head.items():
        if head in exclude:
            continue
        pos = int(row.get("positive") or 0)
        unk = int(row.get("unknown") or 0)
        neg = int(row.get("negative") or 0)
        if pos + neg + unk != n and n > 0:
            errors.append(
                f"Q2 supervision inconsistent on {head}: "
                f"pos+neg+unk={pos + neg + unk} != n={n}"
            )
        masked_ratio = float(row.get("masked_ratio") or 0.0)
        if pos < min_positive or masked_ratio > max_masked_ratio:
            review.append(
                f"{head}: positive={pos} masked_ratio={masked_ratio}"
            )

    if review:
        warnings.append(
            f"W3 supervision review (pos<{min_positive} or "
            f"masked_ratio>{max_masked_ratio}): {review}"
        )

    if profile.get("n_samples", 0) == 0:
        errors.append("Q0 n_samples=0")

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "supervision_review": review,
        "thresholds": {
            "max_unmap_rate_samples": max_unmap_rate_samples,
            "max_truncation_rate": max_truncation_rate,
            "min_positive": min_positive,
            "max_masked_ratio": max_masked_ratio,
            "supervision_exclude_heads": sorted(exclude),
        },
    }


def write_state_audit_reports(
    reports_dir: Path,
    rows: list[dict],
    schema: MultiheadSchema,
    *,
    split_map: dict[str, str],
    summary_extra: dict | None = None,
    quality_cfg: dict | None = None,
) -> dict[str, Any]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    qcfg = quality_cfg or {}

    profile = aggregate_state_profile(rows, schema, split_map=split_map)
    quality = run_quality_checks(
        profile,
        max_unmap_rate_samples=float(qcfg.get("max_unmap_rate_samples", 0.15)),
        max_truncation_rate=float(qcfg.get("max_truncation_rate", 0.50)),
        require_positive_heads=bool(qcfg.get("require_positive_heads", True)),
        min_positive=int(qcfg.get("min_positive", 30)),
        max_masked_ratio=float(qcfg.get("max_masked_ratio", 0.99)),
        supervision_exclude_heads=list(
            qcfg.get("supervision_exclude_heads") or ["IdentityProcess"]
        ),
    )

    # --- split manifest ---
    manifest = {"train": [], "val": [], "test": []}
    for cid, split in sorted(split_map.items()):
        if split in manifest:
            manifest[split].append(cid)
    (reports_dir / "split_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- unmap / relocate audits (full lists) ---
    unmapped = profile["mapping"]["unmapped_events"]
    unmapped_first = profile["mapping"]["unmapped_first_seen_per_conversation"]
    relocated = profile["mapping"]["relocated_labels"]
    unmap_audit = {
        "generated_at": profile["generated_at"],
        "turns_with_memory_raws": profile["mapping"]["turns_with_memory_raws"],
        "unmapped_events": unmapped,
        "unmapped_first_seen_per_conversation": unmapped_first,
        "relocated_labels": relocated,
        "conflicts_by_head": profile["mapping"]["conflicts_by_head"],
        "unmap_rate_samples": profile["mapping"]["unmap_rate_samples"],
        "unmap_rate_events_per_turn_with_raws": profile["mapping"][
            "unmap_rate_events_per_turn_with_raws"
        ],
    }
    (reports_dir / "unmapped_facts.json").write_text(
        json.dumps(unmapped, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (reports_dir / "unmapped_facts_first_seen.json").write_text(
        json.dumps(unmapped_first, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (reports_dir / "relocated_labels.json").write_text(
        json.dumps(relocated, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (reports_dir / "unmap_audit.json").write_text(
        json.dumps(unmap_audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- coverage / mapping audit ---
    coverage = {
        "n_samples": profile["n_samples"],
        "n_conversations": profile["n_conversations"],
        "unique_memory_raws": profile["mapping"]["unique_memory_raws"],
        "unique_unmapped_raws": unmapped["unique_count"],
        "unique_relocated_patterns": relocated["unique_count"],
        "per_head_positive_rate": profile["labels"]["per_head_positive_rate"],
        "nondefault_rate": profile["labels"]["nondefault_rate"],
        "truncation_rate": profile["window"]["truncation_rate"],
    }
    mapping_audit = {
        "top_memory_raws": profile["mapping"]["top_memory_raws"],
        "top_mapped_raws": profile["mapping"]["top_mapped_raws"],
        "top_unmapped": dict(list(unmapped["by_label"].items())[:50]),
        "top_relocated": dict(list(relocated["by_label"].items())[:50]),
        "zero_positive_heads": profile["labels"]["zero_positive_heads"],
        "conflicts_by_head": profile["mapping"]["conflicts_by_head"],
    }
    (reports_dir / "coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (reports_dir / "mapping_audit.json").write_text(
        json.dumps(mapping_audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- quality yaml ---
    quality_doc = {
        **quality,
        "blocking": bool(qcfg.get("blocking", False)),
        "stats": {
            "n_samples": profile["n_samples"],
            "n_conversations": profile["n_conversations"],
            "splits": profile["splits"],
            "unmap_rate_samples": profile["mapping"]["unmap_rate_samples"],
            "truncation_rate": profile["window"]["truncation_rate"],
            "relocated_event_count": relocated["event_count"],
        },
        "generated_at": profile["generated_at"],
    }
    with (reports_dir / "quality_report.yaml").open("w", encoding="utf-8") as f:
        yaml.safe_dump(quality_doc, f, allow_unicode=True, sort_keys=False)

    # --- dataset profile json + md ---
    (reports_dir / "dataset_profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_profile_md(reports_dir / "dataset_profile.md", profile, schema)
    _write_profile_md(reports_dir / "state_dataset_profile.md", profile, schema)
    _write_supervision_md(reports_dir / "head_supervision_stats.md", profile)
    (reports_dir / "head_supervision_stats.json").write_text(
        json.dumps(profile.get("supervision") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # --- summary.md ---
    extra = summary_extra or {}
    lines = [
        "# Multihead State Dataset Build Summary",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"- Schema: `{extra.get('schema') or schema.version}`",
        f"- Label source: `{extra.get('label_source') or 'raw_to_multihead_v1'}`",
        f"- Context: recent_turns={extra.get('window_turns')} char_budget={extra.get('char_budget')}",
        f"- Slot relocate: on",
        "",
        "## Sizes",
        f"- Conversations: {profile['n_conversations']}",
        f"- Samples: {profile['n_samples']}",
        f"- Splits: {profile['splits']}",
        "",
        "## Mapping / quality",
        f"- Unmap rate (samples): {profile['mapping']['unmap_rate_samples']}",
        f"- Unmapped unique raws: {unmapped['unique_count']} "
        f"(events={unmapped['event_count']})",
        f"- Relocate events: {relocated['event_count']}",
        f"- Truncation rate: {profile['window']['truncation_rate']}",
        f"- Nondefault label rate: {profile['labels']['nondefault_rate']}",
        "",
        "## Quality gate",
        f"- Passed: **{quality['passed']}**",
        f"- Errors: {len(quality['errors'])}",
        f"- Warnings: {len(quality['warnings'])}",
        "",
    ]
    if quality["errors"]:
        lines.append("### Errors")
        for e in quality["errors"]:
            lines.append(f"- {e}")
        lines.append("")
    if quality["warnings"]:
        lines.append("### Warnings")
        for w in quality["warnings"]:
            lines.append(f"- {w}")
        lines.append("")
    lines.extend(
        [
            "## Report files",
            "",
            "- `summary.md` (this file)",
            "- `dataset_profile.json` / `dataset_profile.md`",
            "- `quality_report.yaml`",
            "- `coverage.json` / `mapping_audit.json`",
            "- `split_manifest.json`",
            "- `unmapped_facts.json` / `unmapped_facts_first_seen.json`",
            "- `relocated_labels.json` / `unmap_audit.json`",
            "- `head_supervision_stats.md` / `.json` (P0.5)",
            "",
        ]
    )
    (reports_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    summary = {
        **(summary_extra or {}),
        "n_conversations": profile["n_conversations"],
        "n_samples": profile["n_samples"],
        "splits": profile["splits"],
        "quality_passed": quality["passed"],
        "quality_errors": quality["errors"],
        "quality_warnings": quality["warnings"],
        "reports_dir": str(reports_dir),
    }
    (reports_dir / "state_dataset_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"profile": profile, "quality": quality, "summary": summary}


def _write_supervision_md(path: Path, profile: dict) -> None:
    sup = profile.get("supervision") or {}
    lines = [
        "# Head Supervision Stats (P0.5)",
        "",
        "Policy: **Evidence-only** — non-default → mask=1; else label=`unknown` + mask=0. "
        "IdentityProcess always mask=0.",
        "",
        "Train-before gate: `positive < 30` or `masked_ratio > 0.99` → W3 review "
        "(see quality_report.yaml).",
        "",
        f"- n_samples: **{sup.get('n_samples', profile.get('n_samples'))}**",
        "",
        "| head | kind | positive | negative | unknown | masked_ratio |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for name, row in (sup.get("per_head") or {}).items():
        lines.append(
            f"| `{name}` | {row.get('kind')} | {row.get('positive')} | "
            f"{row.get('negative')} | {row.get('unknown')} | {row.get('masked_ratio')} |"
        )
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_profile_md(path: Path, profile: dict, schema: MultiheadSchema) -> None:
    labels = profile["labels"]
    mapping = profile["mapping"]
    window = profile["window"]
    lines = [
        "# State Dataset Profile",
        "",
        f"- generated_at: {profile['generated_at']}",
        f"- n_samples: **{profile['n_samples']}**",
        f"- n_conversations: **{profile['n_conversations']}**",
        f"- splits: `{profile['splits']}`",
        f"- truncated_windows: **{window['truncated']}** "
        f"({100 * window['truncation_rate']:.1f}%)",
        f"- mean_char_len: **{window['char_len'].get('mean', 0)}**",
        f"- samples_with_any_nondefault_label: **{labels['samples_with_any_nondefault']}** "
        f"({100 * labels['nondefault_rate']:.1f}%)",
        f"- unmap_rate_samples: **{mapping['unmap_rate_samples']}**",
        f"- slot_relocate_events: **{mapping['relocated_labels']['event_count']}**",
        "",
        "## Per-head positive rate",
        "",
    ]
    for h in schema.heads:
        rate = labels["per_head_positive_rate"].get(h.name, 0)
        cnt = labels["per_head_positive_count"].get(h.name, 0)
        top = labels["per_head_value_counts"].get(h.name) or {}
        lines.append(f"- `{h.name}`: positive={cnt} ({100 * rate:.1f}%) values={top}")
    lines.append("")
    lines.append("## Top slot relocations")
    lines.append("")
    reloc = mapping["relocated_labels"]["by_label"]
    if not reloc:
        lines.append("- (none)")
    for key, c in list(reloc.items())[:20]:
        lines.append(f"- `{key}`: {c}")
    lines.append("")
    lines.append("## Top unmapped raws (events)")
    lines.append("")
    unmapped = mapping["unmapped_events"]["by_label"]
    if not unmapped:
        lines.append("- (none)")
    for key, c in list(unmapped.items())[:30]:
        lines.append(f"- `{key}`: {c}")
    lines.append("")
    lines.append("## Top unmapped raws (first-seen / conversation)")
    lines.append("")
    first = mapping["unmapped_first_seen_per_conversation"]["by_label"]
    if not first:
        lines.append("- (none)")
    for key, c in list(first.items())[:30]:
        lines.append(f"- `{key}`: {c}")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
