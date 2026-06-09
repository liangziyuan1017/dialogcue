"""
test_summarize_conversation.py — Summarize eligibility and generation tests.

Covers: Phase 9 summarize eligibility checklist items.
- No-summary-of-summary guard
- Threshold enforcement
- L1 summary generation
"""
import sys
import json
import subprocess
from pathlib import Path
import tempfile
import os

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def run_script(script_name: str, args: list[str]) -> dict:
    script_path = SCRIPTS_DIR / script_name
    result = subprocess.run(
        [sys.executable, str(script_path)] + args,
        capture_output=True, text=True,
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"error": result.stdout, "stderr": result.stderr, "exit_code": result.returncode}


class TestSummarizeConversation:
    """Test summarization workflow."""

    def test_summary_of_summary_rejected(self):
        """A summary doc used as input should be rejected."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("""---
id: SUM-20260526-1000-test
title: "Existing Summary"
doc_kind: summary
is_summary_of_summary: false
layer: L1
---

# Existing Summary

Some content.
""")
            f.flush()
            result = run_script("summarize-check-eligibility.py", [
                "--input", f.name,
                "--check-is-summary",
            ])
            os.unlink(f.name)
            assert result.get("eligible") is False
            assert "no-summary-of-summary" in result.get("reason", "")

    def test_insufficient_messages_rejected(self):
        """A short conversation with too few messages should be ineligible."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("user: hello\nagent: hi\nuser: how are you\n")
            f.flush()
            result = run_script("summarize-check-eligibility.py", [
                "--input", f.name,
                "--min-messages", "20",
            ])
            os.unlink(f.name)
            assert result.get("eligible") is False
            assert "not eligible" in result.get("reason", "").lower()

    def test_eligible_conversation_passes(self):
        """A conversation with enough messages passes eligibility."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            lines = []
            for i in range(30):
                lines.append(f"user: message {i}")
                lines.append(f"agent: response {i}")
            f.write("\n".join(lines))
            f.flush()
            result = run_script("summarize-check-eligibility.py", [
                "--input", f.name,
                "--min-messages", "20",
            ])
            os.unlink(f.name)
            assert result.get("eligible") is True, f"Should be eligible: {result}"

    def test_generate_l1_summary(self):
        """L1 summary generation produces output with correct frontmatter."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            lines = []
            for i in range(30):
                lines.append(f"user: message {i}")
                lines.append(f"agent: response {i} - we decided to use PostgreSQL")
            f.write("\n".join(lines))
            src_path = f.name
            f.flush()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as out:
            out_path = out.name

        try:
            result = run_script("summarize-generate.py", [
                "--source", src_path,
                "--layer", "L1",
                "--output", out_path,
            ])
            assert result.get("result") == "generated"
            assert result.get("is_summary_of_summary") is False

            with open(out_path, "r") as f:
                content = f.read()
            assert "doc_kind: summary" in content
            assert "layer: L1" in content
            assert "is_summary_of_summary: false" in content
            assert "Conversation Summary" in content
        finally:
            os.unlink(src_path)
            os.unlink(out_path)

    def test_l2_summary_rejected(self):
        """Only L1 summarization is allowed (no summary-of-summary)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("test content")
            f.flush()
            result = run_script("summarize-generate.py", [
                "--source", f.name,
                "--layer", "L2",
                "--output", "/tmp/test-output.md",
            ])
            os.unlink(f.name)
            assert "error" in result, f"L2 should be rejected: {result}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
