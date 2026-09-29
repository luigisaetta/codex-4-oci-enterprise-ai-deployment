"""
Author: L. Saetta
Date last modified: 2026-09-29
License: MIT
Description: Reproduce Bash 3.2 empty-array handling in image verification.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERIFY_IMAGE = ROOT / "scripts" / "verify_image.sh"
BASH32 = Path("/bin/bash")


def write_manifest(directory: Path) -> Path:
    """Create a valid schema 2 manifest without runtime environment values.

    Args:
        directory: Directory in which to create the manifest fixtures.

    Returns:
        Path to the manifest.
    """
    directory.mkdir()
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


def test_bash32_empty_runtime_environment_fails_when_container_start_fails(
    tmp_path: Path,
) -> None:
    """A failed start cannot become a false PASS when runtime.env is absent."""
    if not BASH32.is_file():
        pytest.skip("/bin/bash is unavailable, so Bash 3.2 cannot be tested.")
    version = subprocess.run(
        [str(BASH32), "--version"], capture_output=True, text=True, check=False
    )
    if not version.stdout.startswith("GNU bash, version 3."):
        pytest.skip(
            "/bin/bash is not Bash 3.x, so this regression test is inapplicable."
        )

    manifest = write_manifest(tmp_path / "agent")
    working_directory = tmp_path / "outside-tool-home"
    working_directory.mkdir()
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text(
        """#!/bin/sh
if [ \"$1\" = info ]; then
    exit 0
fi
if [ \"$1\" = image ] && [ \"$2\" = inspect ]; then
    printf '%s\\n' linux/amd64
    exit 0
fi
if [ \"$1\" = run ]; then
    case \" $* \" in
        *' -d '*) printf '%s\\n' 'simulated container start failure' >&2; exit 1 ;;
        *) printf '%s\\n' x86_64; exit 0 ;;
    esac
fi
exit 1
""",
        encoding="utf-8",
    )
    fake_docker.chmod(0o755)
    environment = os.environ.copy()
    environment["OCI_AGENT_PYTHON"] = sys.executable
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}"

    result = subprocess.run(
        [str(BASH32), str(VERIFY_IMAGE), "--manifest", str(manifest), "--tag", "1.0.0"],
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 12
    assert "result=FAIL" in result.stdout
