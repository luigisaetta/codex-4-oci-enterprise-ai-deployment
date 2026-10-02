"""
Author: L. Saetta
Date last modified: 2026-10-02
License: MIT
Description: Structurally validate OCI agent skill metadata and local references.
"""

# pylint: disable=duplicate-code

import re
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
MARKDOWN_LINK = re.compile(r"\[[^]]*\]\(([^)]+)\)")
SCRIPT_PATH = re.compile(r"scripts[\\/]([A-Za-z0-9_-]+\.(?:sh|ps1))")
FENCED_CODE_BLOCK = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)


def skill_directories() -> list[Path]:
    """Return skill folders that contain their primary instruction file.

    Returns:
        Sorted folders containing SKILL.md.
    """
    return sorted(path.parent for path in SKILLS.glob("*/SKILL.md"))


def skill_content_files() -> list[Path]:
    """Return instruction and reference Markdown files subject to content rules.

    Returns:
        Sorted skill instructions and their reference files.
    """
    return sorted([*SKILLS.glob("*/SKILL.md"), *SKILLS.glob("*/references/*.md")])


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
        assert "Hosted Application" in metadata["description"]
        agent_config = directory / "agents/openai.yaml"
        assert agent_config.is_file()
        interface = yaml.safe_load(agent_config.read_text(encoding="utf-8"))[
            "interface"
        ]
        assert "Hosted Application" in interface["short_description"]
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


def test_skill_content_uses_user_scope_instructions() -> None:
    """Skill instructions avoid checkout-root and unsafe tenancy-file guidance."""
    prohibited_phrases = (
        "checkout's root",
        "run from this checkout",
        "from the repository root",
        ". ./.env",
        "source .env",
        "set -a",
    )
    for markdown in skill_content_files():
        content = markdown.read_text(encoding="utf-8")
        lowered = content.lower()
        for phrase in prohibited_phrases:
            assert (
                phrase not in lowered
            ), f"{markdown} contains prohibited phrase {phrase}"
        if markdown.name == "SKILL.md":
            assert "## Tool home and working directory" in content
        for block in FENCED_CODE_BLOCK.findall(content):
            for line in block.splitlines():
                if SCRIPT_PATH.search(line):
                    assert (
                        "$TOOL_HOME/scripts/" in line or "$TOOL_HOME\\scripts\\" in line
                    )


def test_mutating_skills_require_explicit_authorization() -> None:
    """Push and deploy require explicit authorization before OCI mutations."""
    for name in ("oci-agent-push", "oci-agent-deploy"):
        content = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
        workflow = content.split("## Workflow", maxsplit=1)[1].lower()
        assert "explicit" in workflow
        assert "authorization" in workflow


def test_deploy_skill_documents_release_cases_and_no_delete_rule() -> None:
    """The deploy skill names script cases and limits deletion to failed replacement."""
    content = (SKILLS / "oci-agent-deploy" / "SKILL.md").read_text(encoding="utf-8")
    for case in (
        "First release",
        "Already released",
        "New version",
        "Return to a previous version",
        "Creation in progress",
        "Application creation in progress",
        "Failed deployment",
        "Replace failed deployment",
    ):
        assert case in content
    assert (
        "Never delete or recreate an application or a deployment, "
        "except a deployment in" in content
    )
    assert "| 26 |" in content
    assert "--replace-failed" in content


def test_skills_include_target_platform_check() -> None:
    """Every skill checks its platform; lifecycle skills retain their routing."""
    lifecycle_skills = {
        "oci-agent-build",
        "oci-agent-push",
        "oci-agent-deploy",
        "oci-agent-verify-deployment",
    }
    for directory in skill_directories():
        content = (directory / "SKILL.md").read_text(encoding="utf-8")
        assert "## Target platform check" in content
        if directory.name in lifecycle_skills:
            assert "aidp-agent-deploy" in content


def test_new_skill_documents_helper_and_first_iteration() -> None:
    """The authoring skill exposes the reviewed helper contract and its status."""
    content = (SKILLS / "oci-agent-new" / "SKILL.md").read_text(encoding="utf-8")
    for command in ("plan", "render", "check-manifest", "check-env"):
        assert f'"$TOOL_HOME/scripts/new_agent.py" {command}' in content
    for code in (30, 31, 64):
        assert f"| {code} |" in content
    for section in ("## Prerequisites", "## Closing message"):
        assert section in content
    assert "work in progress" in content.lower()
    assert "../../specs/011-skill-oci-agent-new.md" in MARKDOWN_LINK.findall(content)


def test_idcs_skill_guidance_uses_placeholders_and_required_exit_codes() -> None:
    """IDCS deployment guidance keeps examples sanitized and actionable."""
    deploy = (SKILLS / "oci-agent-deploy" / "SKILL.md").read_text(encoding="utf-8")
    verify = (SKILLS / "oci-agent-verify-deployment" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    assert "public-idcs" in deploy
    assert "public-idcs" in verify
    assert "| 24 |" in verify
    assert "| 25 |" in verify
    for path in skill_content_files():
        content = path.read_text(encoding="utf-8")
        assert re.search(r"idcs-[0-9a-f]{8,}", content, re.IGNORECASE) is None
        assert "hostedApplications/" not in content or "eu-" not in content
