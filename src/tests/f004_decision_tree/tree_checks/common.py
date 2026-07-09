import json
import os
from dataclasses import dataclass, field

_REWARDED_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "f003_reward_labeling", "data", "output_rewarded.py",
)


@dataclass
class CheckResult:
    id: str
    category: str
    severity: str
    status: str
    message: str
    details: list = field(default_factory=list)


@dataclass
class Report:
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, r: CheckResult):
        self.checks.append(r)

    def summary(self) -> str:
        p = sum(1 for c in self.checks if c.status == "pass")
        f = sum(1 for c in self.checks if c.status == "fail")
        w = sum(1 for c in self.checks if c.status == "warn")
        s = sum(1 for c in self.checks if c.status == "skip")
        return f"pass={p} fail={f} warn={w} skip={s} total={len(self.checks)}"

    def exit_code(self) -> int:
        return 1 if any(c.status == "fail" for c in self.checks) else 0

    def to_dict(self) -> dict:
        return {
            "pass": sum(1 for c in self.checks if c.status == "pass"),
            "fail": sum(1 for c in self.checks if c.status == "fail"),
            "warn": sum(1 for c in self.checks if c.status == "warn"),
            "skip": sum(1 for c in self.checks if c.status == "skip"),
            "checks": [
                {"id": c.id, "category": c.category, "severity": c.severity,
                 "status": c.status, "message": c.message, "details": c.details}
                for c in self.checks
            ],
        }


def ok(r, id, cat, sev, msg=""):
    r.add(CheckResult(id, cat, sev, "pass", msg))


def fail(r, id, cat, sev, msg, details=None):
    r.add(CheckResult(id, cat, sev, "fail", msg, details or []))


def warn(r, id, cat, sev, msg, details=None):
    r.add(CheckResult(id, cat, sev, "warn", msg, details or []))


def skip(r, id, cat, sev, msg=""):
    r.add(CheckResult(id, cat, sev, "skip", msg))


def walk(tree):
    yield tree
    for c in tree.get("children", []):
        yield from walk(c)


def walk_sentences(tree):
    for n in walk(tree):
        for s in n.get("sentence_pool", []):
            yield n, s


def is_end(node):
    sid = node.get("state_id", "")
    return sid in ("normal_end", "abrupt_end")


def node_identity(n):
    return (
        tuple(sorted(n.get("inherited_facts", []))),
        tuple(sorted(n.get("inherited_emotions", []))),
        json.dumps(n.get("branch_key", {}), sort_keys=True),
    )


def load_rewarded():
    import importlib.util
    spec = importlib.util.spec_from_file_location("output_rewarded", _REWARDED_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.results


def trace_call_id(tree, call_id):
    path = []

    def _walk(node):
        has = any(call_id in s.get("source_call_ids", []) for s in node.get("sentence_pool", []))
        if has:
            path.append(node)
        for c in node.get("children", []):
            _walk(c)

    _walk(tree)
    return path
