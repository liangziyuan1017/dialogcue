from .common import CheckResult, Report, load_rewarded
from .check_structure import check_structure
from .check_nodes import check_nodes
from .check_sentences import check_sentences, check_termination
from .check_gestures import check_gestures, check_coverage
from .check_scoring import check_scoring
from .check_branching import check_branching, check_additive
from .check_output import check_output, check_per_dialog

__all__ = [
    "CheckResult",
    "Report",
    "check_tree",
    "load_rewarded",
]


def check_tree(tree, records=None, scored=False, scored_tree=None):
    r = Report()
    check_structure(tree, r)
    check_nodes(tree, r)
    check_sentences(tree, r)
    check_termination(tree, r)
    check_gestures(tree, records, r)
    check_coverage(tree, records, r)
    if scored:
        check_scoring(tree, r)
    else:
        from .common import skip
        for i in range(1, 29):
            skip(r, f"SC{i}", "scoring", "hard", "not scored mode")
    check_branching(tree, r)
    check_additive(tree, r)
    check_output(tree, scored_tree, r)
    check_per_dialog(tree, records, r)
    return r
