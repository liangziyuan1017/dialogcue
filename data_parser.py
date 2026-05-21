import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data_0520.json"


@dataclass
class DialogTurn:
    role: str
    text: str


@dataclass
class PlanEvaluation:
    reduction_plan: str = ""
    reduction_evidence: str = ""
    mina_plan: str = ""
    mina_evidence: str = ""
    technique: str = ""
    technique_evidence: str = ""


@dataclass
class CallRecord:
    call_id: str
    dialog_raw: str
    calldate: str
    custno: str
    colluserid: str
    mobtyp: str
    talktime: str
    planevaluation_raw: str = ""
    turns: list[DialogTurn] = field(default_factory=list)
    evaluation: PlanEvaluation = field(default_factory=PlanEvaluation)


ROLE_COLLECTOR = "催收员"
ROLE_CUSTOMER = "客户"
VALID_ROLES = {ROLE_COLLECTOR, ROLE_CUSTOMER}


def parse_dialog(dialog_raw: str) -> list[DialogTurn]:
    turns = []
    segments = re.split(r"[；;]", dialog_raw)
    for seg in segments:
        seg = seg.strip()
        if not seg:
            continue
        m = re.match(rf"^({'|'.join(VALID_ROLES)})[：:]\s*(.*)", seg)
        if m:
            turns.append(DialogTurn(role=m.group(1), text=m.group(2).strip()))
        else:
            if turns:
                turns[-1].text += seg
            else:
                turns.append(DialogTurn(role="", text=seg))
    return turns


def parse_planevaluation(pe_raw: str) -> PlanEvaluation:
    pe = PlanEvaluation()
    if not pe_raw:
        return pe

    def _extract(label: str, text: str) -> tuple[str, str]:
        pattern = rf"{label}\s*\|\s*([^|]+)\s*\|\s*([^|]*)"
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return "", ""

    pe.reduction_plan, pe.reduction_evidence = _extract("调减方案", pe_raw)
    pe.mina_plan, pe.mina_evidence = _extract("MINA方案", pe_raw)
    pe.technique, pe.technique_evidence = _extract("促成技巧", pe_raw)
    return pe


def load_records(filepath: Optional[str] = None) -> list[CallRecord]:
    path = Path(filepath) if filepath else DATA_FILE
    with open(path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    records = []
    for item in raw_data:
        rec = CallRecord(
            call_id=item.get("call_id", ""),
            dialog_raw=item.get("dialog", ""),
            calldate=item.get("calldate", ""),
            custno=item.get("custno", ""),
            colluserid=item.get("colluserid", ""),
            mobtyp=item.get("mobtyp", ""),
            talktime=item.get("talktime", ""),
            planevaluation_raw=item.get("planevaluation", ""),
        )
        rec.turns = parse_dialog(rec.dialog_raw)
        rec.evaluation = parse_planevaluation(rec.planevaluation_raw)
        records.append(rec)
    return records


def get_collector_turns(record: CallRecord) -> list[DialogTurn]:
    return [t for t in record.turns if t.role == ROLE_COLLECTOR]


def get_customer_turns(record: CallRecord) -> list[DialogTurn]:
    return [t for t in record.turns if t.role == ROLE_CUSTOMER]


def filter_by_date(records: list[CallRecord], date: str) -> list[CallRecord]:
    return [r for r in records if r.calldate == date]


def filter_by_mobtyp(records: list[CallRecord], mobtyp: str) -> list[CallRecord]:
    return [r for r in records if r.mobtyp == mobtyp]


def filter_by_user(records: list[CallRecord], colluserid: str) -> list[CallRecord]:
    return [r for r in records if r.colluserid == colluserid]


def search_dialog(records: list[CallRecord], keyword: str) -> list[CallRecord]:
    return [r for r in records if keyword in r.dialog_raw]


def summary(records: list[CallRecord]) -> dict:
    dates = sorted(set(r.calldate for r in records))
    users = sorted(set(r.colluserid for r in records))
    mobtyps = sorted(set(r.mobtyp for r in records))
    reduction_provided = sum(
        1 for r in records if "提供" in r.evaluation.reduction_plan
    )
    technique_used = sum(
        1 for r in records if "运用" in r.evaluation.technique
    )
    return {
        "total": len(records),
        "dates": dates,
        "collectors": users,
        "mobtyps": mobtyps,
        "reduction_plan_provided": reduction_provided,
        "technique_used": technique_used,
    }


if __name__ == "__main__":
    records = load_records()
    s = summary(records)
    print(f"Total records: {s['total']}")
    print(f"Dates: {s['dates']}")
    print(f"Collectors: {s['collectors']}")
    print(f"Reduction plan provided: {s['reduction_plan_provided']}")
    print(f"Technique used: {s['technique_used']}")
    print()
    rec = records[0]
    print(f"Example call_id: {rec.call_id}")
    print(f"Turns: {len(rec.turns)}")
    print(f"Collector turns: {len(get_collector_turns(rec))}")
    print(f"Customer turns: {len(get_customer_turns(rec))}")
    print(f"Evaluation: reduction={rec.evaluation.reduction_plan}, technique={rec.evaluation.technique}")
