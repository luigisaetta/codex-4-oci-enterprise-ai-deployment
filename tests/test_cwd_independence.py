"""
Author: L. Saetta
Date last modified: 2026-09-29
License: MIT
Description: Verify manifest utilities work when called outside the tool home.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


@pytest.fixture(autouse=True)
def clear_allowed_roots_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent the operator's allowed-root configuration from affecting tests."""
    monkeypatch.delenv("OCI_AGENT_ALLOWED_ROOTS", raising=False)


def write_manifest(directory: Path) -> Path:
    """Create a valid local version 2 manifest for a script preflight.

    Args:
        directory: Directory that will contain the manifest and Dockerfile.

    Returns:
        Path to the created manifest.
    """
    directory.mkdir(parents=True)
    (directory / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    manifest = directory / "agent.yaml"
    manifest.write_text(
        """schema_version: 2
name: test-agent
build: {context: ., dockerfile: Dockerfile}
publish: {repository: agents/test-agent}
deploy: {application_name: test-agent, profile: public-noauth}
verify: []
""",
        encoding="utf-8",
    )
    return manifest


def test_manifest_checks_run_by_path_reports_manifest_error(tmp_path: Path) -> None:
    """The checks script accepts a path invocation outside the repository."""
    working_directory = tmp_path / "outside-tool-home"
    working_directory.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "run_manifest_checks.py"),
            "--manifest",
            "missing-agent.yaml",
            "--base-url",
            "http://127.0.0.1:8080",
            "--timeout-seconds",
            "1",
        ],
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 64
    assert "Manifest error" in result.stderr


def test_build_image_reads_an_absolute_manifest_before_rejecting_tag(
    tmp_path: Path,
) -> None:
    """The build script resolves a manifest before rejecting an invalid tag."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip(
            "Bash is unavailable, so the Bash working-directory test cannot run."
        )
    manifest = write_manifest(tmp_path / "agent")
    working_directory = tmp_path / "outside-tool-home"
    working_directory.mkdir()
    result = subprocess.run(
        [
            bash,
            str(SCRIPTS / "build_image.sh"),
            "--manifest",
            str(manifest),
            "--tag",
            "latest",
        ],
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 3
