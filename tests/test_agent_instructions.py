"""
Author: L. Saetta
Date last modified: 2026-10-13
License: MIT
Description: Unit tests for the AGENTS.md instruction block of agent repositories.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "agent_instructions.py"


def run_ensure(target: Path) -> subprocess.CompletedProcess[str]:
    """Run the ensure command on a target folder.

    Args:
        target: Agent folder.

    Returns:
        Completed process containing output and exit status.
    """
    return subprocess.run(
        [sys.executable, str(SCRIPT), "ensure", "--target", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_creates_agents_md_with_the_block(tmp_path: Path) -> None:
    """A missing AGENTS.md is created with the customer-name rules."""
    result = run_ensure(tmp_path)

    assert result.returncode == 0
    assert result.stdout == "created: AGENTS.md\n"
    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert content.startswith("# Instructions for Codex\n")
    assert "Customer name in demos" in content
    assert "demo-customer" in content
    assert "Supremo" in content
    assert "## IAM changes" in content
    assert "Never create, change, or delete dynamic groups, policies" in content


def test_appends_to_existing_file_and_is_idempotent(tmp_path: Path) -> None:
    """Existing content is kept; a second run changes nothing."""
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# My rules\n\nKeep this line.\n", encoding="utf-8")

    first = run_ensure(tmp_path)
    after_first = agents.read_text(encoding="utf-8")
    second = run_ensure(tmp_path)

    assert first.stdout == "appended: AGENTS.md\n"
    assert after_first.startswith("# My rules\n\nKeep this line.\n\n<!-- BEGIN")
    assert second.stdout == "unchanged: AGENTS.md\n"
    assert agents.read_text(encoding="utf-8") == after_first


def test_refreshes_a_stale_block_only(tmp_path: Path) -> None:
    """Only the marked block is replaced; text around it is preserved."""
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        "Before.\n\n"
        "<!-- BEGIN oci-agent-skills: customer name (Spec 020) -->\nold\n"
        "<!-- END oci-agent-skills: customer name -->\n\nAfter.\n",
        encoding="utf-8",
    )

    result = run_ensure(tmp_path)

    content = agents.read_text(encoding="utf-8")
    assert result.stdout == "updated: AGENTS.md\n"
    assert content.startswith("Before.\n\n<!-- BEGIN")
    assert content.endswith("<!-- END oci-agent-skills: customer name -->\n\nAfter.\n")
    assert "\nold\n" not in content


def test_rejects_missing_target_and_unbalanced_markers(tmp_path: Path) -> None:
    """Invalid inputs exit 64 without writing."""
    assert run_ensure(tmp_path / "missing").returncode == 64

    agents = tmp_path / "AGENTS.md"
    broken = "<!-- BEGIN oci-agent-skills: customer name (Spec 020) -->\nno end\n"
    agents.write_text(broken, encoding="utf-8")
    result = run_ensure(tmp_path)

    assert result.returncode == 64
    assert agents.read_text(encoding="utf-8") == broken
