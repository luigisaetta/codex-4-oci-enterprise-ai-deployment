"""
Author: L. Saetta
Date last modified: 2026-09-29
License: MIT
Description: Verify OCI agent build templates and split dependency files.
"""

import re
from pathlib import Path

import pytest

from scripts.agent_manifest import load_manifest

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "skills/oci-agent-build/assets"
PLACEHOLDER = re.compile(r"{{[^}]+}}")


@pytest.fixture(autouse=True)
def clear_allowed_roots_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent operator root configuration from influencing template tests."""
    monkeypatch.delenv("OCI_AGENT_ALLOWED_ROOTS", raising=False)


def render(template: Path, values: dict[str, str]) -> str:
    """Replace supported placeholder text in a template.

    Args:
        template: Template file to render.
        values: Placeholder names and replacement values.

    Returns:
        Rendered template text.
    """
    rendered = template.read_text(encoding="utf-8")
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def test_hello_world_dockerfile_is_an_exact_template_rendering() -> None:
    """The reference Dockerfile remains the exact documented template rendering."""
    rendered = render(
        ASSETS / "Dockerfile.template",
        {
            "REQUIREMENTS_PATH": "demos/hello_world/requirements.txt",
            "PACKAGE_DIR": "demos",
            "APP_MODULE": "demos.hello_world.app:app",
        },
    )

    assert rendered == (ROOT / "demos/hello_world/Dockerfile").read_text(
        encoding="utf-8"
    )
    assert PLACEHOLDER.search(rendered) is None


def test_root_dockerignore_is_an_exact_template_copy() -> None:
    """The root Docker ignore file remains the template's exact copy."""
    assert (ROOT / ".dockerignore").read_bytes() == (
        ASSETS / "dockerignore.template"
    ).read_bytes()


def test_rendered_agent_manifest_is_valid(tmp_path: Path) -> None:
    """An external-agent manifest template renders to a valid schema version 2 file."""
    (tmp_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    rendered = render(
        ASSETS / "agent.yaml.template",
        {
            "AGENT_NAME": "sample-agent",
            "OCIR_REPOSITORY": "agents/sample-agent",
            "APPLICATION_NAME": "sample-agent",
        },
    )
    manifest_path = tmp_path / "agent.yaml"
    manifest_path.write_text(rendered, encoding="utf-8")

    manifest = load_manifest(str(manifest_path))

    assert manifest["name"] == "sample-agent"
    assert PLACEHOLDER.search(rendered) is None


def test_dependency_files_keep_tool_and_demo_packages_separate() -> None:
    """Tool dependencies exclude demo runtime packages, which stay with the demo."""
    tool_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    demo_requirements = (ROOT / "demos/hello_world/requirements.txt").read_text(
        encoding="utf-8"
    )

    for package in ("fastapi", "langgraph", "pydantic", "uvicorn"):
        assert package not in tool_requirements.lower()
        assert package in demo_requirements.lower()
