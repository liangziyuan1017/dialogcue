"""
SCRIPT FILE — Deterministic Execution Unit
Purpose: Validate that a quality-gate report contains all required sections.
It does ONE thing: check report completeness against required sections.
Invoked by: workflows/quality-gate.md (Step 8)
Tested by:  tests/test_quality_gate.py
"""

REQUIRED_SECTIONS = [
    "愿景覆盖",
    "功能验收",
    "验证命令输出",
]


def validate_report(report_text: str) -> dict:
    """
    Validate that a quality gate report has all required sections.

    Args:
        report_text: The full text of the quality gate report.

    Returns:
        dict: {'valid': True} if all sections present,
              or {'valid': False, 'missing': [section_names]} if sections are missing.

    Related:
        Invoked by: workflows/quality-gate.md (Step 8)
        Tested by:  tests/test_quality_gate.py
    """
    missing = [s for s in REQUIRED_SECTIONS if s not in report_text]
    if missing:
        return {'valid': False, 'missing': missing}
    return {'valid': True}
