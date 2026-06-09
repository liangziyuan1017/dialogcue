"""
TEST FILE — Deterministic Verification
Purpose: Verify that checklist-validator.py produces correct deterministic outputs.
Tests cover: complete report passes, missing sections fail, empty report fails.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
from checklist_validator import validate_report


class TestChecklistValidator(unittest.TestCase):
    def test_complete_report_passes(self):
        """returns valid when all required sections are present"""
        report = "愿景覆盖\n功能验收\n验证命令输出"
        self.assertEqual(validate_report(report), {'valid': True})

    def test_missing_section_fails(self):
        """returns invalid with missing section when one section is absent"""
        report = "功能验收\n验证命令输出"
        result = validate_report(report)
        self.assertFalse(result['valid'])
        self.assertIn('愿景覆盖', result['missing'])

    def test_empty_report_fails(self):
        """returns invalid with all sections missing for empty report"""
        result = validate_report("")
        self.assertFalse(result['valid'])
        self.assertEqual(len(result['missing']), 3)

    def test_partial_match_not_fooled(self):
        """does not match partial section names"""
        report = "功能\n验证"
        result = validate_report(report)
        self.assertFalse(result['valid'])
        self.assertEqual(len(result['missing']), 3)


if __name__ == '__main__':
    unittest.main()
