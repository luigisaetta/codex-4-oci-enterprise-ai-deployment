#!/usr/bin/env python3
"""
Author: L. Saetta
Date last modified: 2026-10-12
License: MIT
Description: Add or refresh the OCI agent skills' rules in an agent's AGENTS.md.
"""

import argparse
import sys
from pathlib import Path

EXIT_INVALID_INPUT = 64
TOOL_HOME = Path(__file__).resolve().parent.parent
BLOCK_FILE = TOOL_HOME / "skills" / "oci-agent-new" / "assets" / "agent-instructions.md"
BEGIN_MARKER = "<!-- BEGIN oci-agent-skills: customer name (Spec 020) -->"
END_MARKER = "<!-- END oci-agent-skills: customer name -->"
NEW_FILE_HEADER = "# Instructions for Codex\n\n"


def instruction_block() -> str:
    """Return the marked instruction block shipped with the skills.

    Returns:
        The block text, from the begin marker to the end marker, with a
        trailing newline.

    Raises:
        ValueError: If the asset does not contain both markers.
    """
    text = BLOCK_FILE.read_text(encoding="utf-8").strip()
    if not text.startswith(BEGIN_MARKER) or not text.endswith(END_MARKER):
        raise ValueError(f"Instruction asset is malformed: {BLOCK_FILE}")
    return text + "\n"


def ensure_instructions(target: Path) -> str:
    """Create, extend, or refresh AGENTS.md in an agent folder.

    Content outside the marked block is never changed.

    Args:
        target: Agent repository folder.

    Returns:
        One of "created", "appended", "updated", or "unchanged".

    Raises:
        ValueError: If the target is not a folder, or AGENTS.md has a begin
            marker without a matching end marker.
    """
    if not target.is_dir():
        raise ValueError(f"Target folder does not exist: {target}")
    block = instruction_block()
    path = target / "AGENTS.md"
    if not path.exists():
        path.write_text(NEW_FILE_HEADER + block, encoding="utf-8")
        return "created"
    current = path.read_text(encoding="utf-8")
    begin = current.find(BEGIN_MARKER)
    if begin == -1:
        separator = (
            ""
            if current.endswith("\n\n")
            else ("\n" if current.endswith("\n") else "\n\n")
        )
        path.write_text(current + separator + block, encoding="utf-8")
        return "appended"
    end = current.find(END_MARKER, begin)
    if end == -1:
        raise ValueError(f"{path} has a begin marker without an end marker.")
    end += len(END_MARKER)
    if current[end : end + 1] == "\n":
        end += 1
    if current[begin:end] == block:
        return "unchanged"
    path.write_text(current[:begin] + block + current[end:], encoding="utf-8")
    return "updated"


def main() -> int:
    """Run the command-line interface.

    Returns:
        Zero on success, or 64 for an invalid target or file.
    """
    parser = argparse.ArgumentParser(
        description="Add the OCI agent skills' rules to an agent's AGENTS.md."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    ensure_parser = commands.add_parser("ensure")
    ensure_parser.add_argument("--target", default=".")
    args = parser.parse_args()
    try:
        result = ensure_instructions(Path(args.target))
    except (ValueError, OSError) as error:
        print(f"Agent instructions error: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    print(f"{result}: AGENTS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
