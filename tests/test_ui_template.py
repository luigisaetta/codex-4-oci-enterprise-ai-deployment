"""
Author: L. Saetta
Date last modified: 2026-10-07
License: MIT
Description: Static checks for the oci-agent-ui skill and its Next.js template.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "oci-agent-ui"
TEMPLATE = SKILL / "assets" / "ui-template"
TEMPLATE_FILES = sorted(path for path in TEMPLATE.rglob("*") if path.is_file())


def template_text() -> dict[str, str]:
    """Return the text of every template file, keyed by relative path.

    Returns:
        Template contents.
    """
    return {
        str(path.relative_to(TEMPLATE)): path.read_text(encoding="utf-8")
        for path in TEMPLATE_FILES
    }


def test_template_has_the_expected_files() -> None:
    """The template holds the bridge, the generic page, and its configuration."""
    names = set(template_text())
    for expected in (
        "package.json",
        "next.config.mjs",
        ".gitignore",
        ".env.local.example",
        "README.md",
        "app/layout.jsx",
        "app/page.jsx",
        "app/globals.css",
        "app/demo-config.js",
        "app/api/agent/route.js",
    ):
        assert expected in names


def test_template_contains_no_address_ocid_or_secret() -> None:
    """Addresses live only in .env.local; examples use placeholders."""
    for name, content in template_text().items():
        assert (
            re.search(r"ocid1\.[a-z]+\.oc1\.[a-z0-9-]*\.[a-z0-9]{10,}", content) is None
        ), name
        for match in re.findall(r"https://[^\s\"'`)]+", content):
            assert "<" in match or match.startswith("https://nodejs.org"), (name, match)
        assert (
            re.search(r"(?i)(api[_-]?key|password|secret)\s*[:=]\s*\S", content) is None
        ), name


def test_bridge_reads_the_address_from_the_environment() -> None:
    """The API route forwards to AGENT_BASE_URL + AGENT_PATH only."""
    route = (TEMPLATE / "app/api/agent/route.js").read_text(encoding="utf-8")
    assert "process.env.AGENT_BASE_URL" in route
    assert "process.env.AGENT_PATH" in route
    assert "status === 400 || upstream.status === 422" in route
    page = (TEMPLATE / "app/page.jsx").read_text(encoding="utf-8")
    assert 'fetch("/api/agent"' in page
    assert "AGENT_BASE_URL" not in page


def test_server_listens_only_on_loopback() -> None:
    """The dev and start scripts bind to 127.0.0.1."""
    scripts = json.loads((TEMPLATE / "package.json").read_text(encoding="utf-8"))[
        "scripts"
    ]
    assert "--hostname 127.0.0.1" in scripts["dev"]
    assert "--hostname 127.0.0.1" in scripts["start"]


def test_env_example_holds_placeholders_and_git_ignores_env_local() -> None:
    """The example configuration is safe; the real one is never committed."""
    example = (TEMPLATE / ".env.local.example").read_text(encoding="utf-8")
    assert "AGENT_BASE_URL=http://127.0.0.1:8080" in example
    assert "AGENT_PATH=/replace-with-agent-path" in example
    ignored = (TEMPLATE / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in ("node_modules/", ".next/", ".env.local"):
        assert entry in ignored


def test_technical_view_is_off_by_default() -> None:
    """The default configuration shows no technical data."""
    config = (TEMPLATE / "app/demo-config.js").read_text(encoding="utf-8")
    assert "technicalView: false" in config


def test_agent_images_exclude_the_ui() -> None:
    """The Dockerfile template's ignore list keeps the UI out of agent images."""
    entries = (
        (ROOT / "skills/oci-agent-build/assets/dockerignore.template")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert "ui" in entries
    assert "**/node_modules" in entries


def test_skill_documents_the_end_user_rules_and_links() -> None:
    """The skill links its specification, guidelines, and UI spec template."""
    content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for link in (
        "../../specs/018-skill-oci-agent-ui.md",
        "references/ui-guidelines.md",
        "assets/ui-spec.template.md",
    ):
        assert f"]({link})" in content
    guidelines = (SKILL / "references/ui-guidelines.md").read_text(encoding="utf-8")
    for rule in ("E1.", "E3.", "E6.", "T2.", "T3.", "T4."):
        assert f"**{rule}" in guidelines
