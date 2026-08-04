"""Relocate misplaced fact labels from emotion / willingness slots.

LLM raw_state may put fact-like labels under emotions or willingness.
If a label maps to a multihead fact (raw_to_multihead) and does NOT map to
emotion or willingness, move it into the fact stream.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from remap.emotion_mapper import EmotionMapper
from remap.willingness_mapper import WillingnessMapper
from raw_to_multihead import RawToMultiheadMapper


@dataclass
class SlotRelocateResult:
    facts: list[str]
    relocated: list[dict[str, str]] = field(default_factory=list)


class SlotRelocator:
    def __init__(
        self,
        fact_mapper: RawToMultiheadMapper,
        emotion_mapper: EmotionMapper,
        willingness_mapper: WillingnessMapper,
    ):
        self.fact_mapper = fact_mapper
        self.emotion_mapper = emotion_mapper
        self.willingness_mapper = willingness_mapper

    def is_fact_raw(self, label: str) -> bool:
        """Known in raw→multihead table (including explicit empty drops)."""
        return label in self.fact_mapper.mappings

    def is_emotion_raw(self, label: str) -> bool:
        if self.emotion_mapper.is_dropped(label):
            return False
        return self.emotion_mapper.map_label(label) is not None

    def is_willingness_raw(self, label: str) -> bool:
        return self.willingness_mapper.map_label(label) is not None

    def collect_facts(self, raw_state: dict | None) -> SlotRelocateResult:
        if not raw_state:
            return SlotRelocateResult(facts=[])

        facts = [str(x) for x in (raw_state.get("facts") or []) if x]
        emotions = [str(x) for x in (raw_state.get("emotions") or []) if x]

        willingness_raw = raw_state.get("willingness")
        if willingness_raw is None:
            willingness_raw = raw_state.get("willing_to_pay")
        willingness_list: list[str] = []
        if isinstance(willingness_raw, list):
            willingness_list = [str(x) for x in willingness_raw if x]
        elif willingness_raw is not None and str(willingness_raw).strip():
            willingness_list = [str(willingness_raw)]

        out = list(facts)
        seen = set(out)
        relocated: list[dict[str, str]] = []

        def _maybe_relocate(label: str, source: str) -> None:
            if self.is_emotion_raw(label) or self.is_willingness_raw(label):
                return
            if not self.is_fact_raw(label):
                return
            if label not in seen:
                seen.add(label)
                out.append(label)
            relocated.append({"label": label, "from": source, "to": "facts"})

        for label in emotions:
            _maybe_relocate(label, "emotions")
        for label in willingness_list:
            _maybe_relocate(label, "willingness")

        return SlotRelocateResult(facts=out, relocated=relocated)


def build_slot_relocator(
    fact_mapper: RawToMultiheadMapper,
    emotion_mapping: Path,
    willingness_ontology: Path,
) -> SlotRelocator:
    return SlotRelocator(
        fact_mapper=fact_mapper,
        emotion_mapper=EmotionMapper(emotion_mapping),
        willingness_mapper=WillingnessMapper(willingness_ontology),
    )
