"""
Author: L. Saetta
Date last modified: 2026-09-29
License: MIT
Description: Structurally validate OCI agent skill metadata and local references.
"""

import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
MARKDOWN_LINK = re.compile(r"\[[^]]*\]\(([^)]+)\)")
SCRIPT_PATH = re.compile(r"scripts/([A-Za-z0-9_-]+\.(?:sh|ps1))")


def skill_directories() -> list[Path]:
    """Return skill folders that contain their primary instruction file.

    Returns:
        Sorted folders containing SKILL.md.
    """
    return sorted(path.parent for path in SKILLS.glob("*/SKILL.md"))


def frontmatter(path: Path) -> dict[str, object]:
    """Read YAML frontmatter from a skill instruction file.

    Args:
        path: Skill instruction file to parse.

    Returns:
        Parsed YAML mapping.
    """
    content = path.read_text(encoding="utf-8")
    assert content.startswith("---\n")
    _, yaml_text, _ = content.split("---", maxsplit=2)
    parsed = yaml.safe_load(yaml_text)
    assert isinstance(parsed, dict)
    return parsed


def test_skill_frontmatter_names_and_agents_are_complete() -> None:
    """Every skill has matching metadata, a description, and an agent definition."""
    directories = skill_directories()
    names = []
    for directory in directories:
        metadata = frontmatter(directory / "SKILL.md")
        assert metadata.get("name") == directory.name
        assert isinstance(metadata.get("description"), str) and metadata["description"]
        assert (directory / "agents/openai.yaml").is_file()
        names.append(directory.name)
    assert len(names) == len(set(names))
    assert all(name.startswith("oci-agent-") for name in names)


def test_named_skill_scripts_exist() -> None:
    """Skill Markdown script paths resolve below the repository scripts folder."""
    markdown_files = [*SKILLS.rglob("SKILL.md"), SKILLS / "README.md"]
    for markdown in markdown_files:
        for script_name in SCRIPT_PATH.findall(markdown.read_text(encoding="utf-8")):
            assert (
                ROOT / "scripts" / script_name
            ).is_file(), f"{markdown} names unavailable script {script_name}"


def test_relative_markdown_links_resolve() -> None:
    """Relative file links in skill Markdown point to files that exist."""
    for markdown in SKILLS.rglob("*.md"):
        for target in MARKDOWN_LINK.findall(markdown.read_text(encoding="utf-8")):
            destination = target.split("#", maxsplit=1)[0].strip()
            parsed = urlparse(destination)
            if not destination or destination.startswith("#") or parsed.scheme:
                continue
            assert (
                (markdown.parent / destination).resolve().is_file()
            ), f"{markdown} links to unavailable file {target}"
