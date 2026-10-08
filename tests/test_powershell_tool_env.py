"""
Author: L. Saetta
Date last modified: 2026-10-08
License: MIT
Description: Exercise PowerShell tenancy configuration outside the tool home.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
PWSH = shutil.which("pwsh")
pytestmark = pytest.mark.skipif(PWSH is None, reason="pwsh is unavailable.")


def write_manifest(directory: Path) -> Path:
    """Create a valid version 2 manifest for interpreter preflight testing.

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


def run_pwsh(
    command: str, cwd: Path, environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """Run a PowerShell command in an external working directory.

    Args:
        command: PowerShell command text.
        cwd: Working directory outside the repository.
        environment: Process environment for the command.

    Returns:
        Completed PowerShell process.
    """
    return subprocess.run(
        [PWSH, "-NoProfile", "-Command", command],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def base_environment() -> dict[str, str]:
    """Return an environment isolated from operator tenancy configuration.

    Returns:
        Environment with the test interpreter selected.
    """
    environment = os.environ.copy()
    for key in (
        "OCI_AGENT_ENV_FILE",
        "OCI_AGENT_PYTHON",
        "OCI_AGENT_ALLOWED_ROOTS",
        "OCI_REGION",
        "OCI_COMPARTMENT_NAME",
        "OCIR_TENANCY_NAMESPACE",
        "OCIR_USERNAME",
    ):
        environment.pop(key, None)
    environment["OCI_AGENT_PYTHON"] = sys.executable
    return environment


def test_import_uses_exported_values_when_file_is_missing(tmp_path: Path) -> None:
    """PowerShell preserves exported tenancy settings when tool-config is silent."""
    environment = base_environment()
    environment["OCI_AGENT_ENV_FILE"] = str(tmp_path / "missing.env")
    environment["OCI_REGION"] = "eu-frankfurt-1"
    environment["OCI_COMPARTMENT_NAME"] = "target"
    module = SCRIPTS / "lib/ToolEnvironment.psm1"
    command = (
        f"Import-Module '{module}' -Force; "
        "$result = Import-TenancySettings "
        "-Keys @('OCI_REGION', 'OCI_COMPARTMENT_NAME'); "
        "if ($result -ne 0) { exit $result }; "
        'Write-Output "$env:OCI_REGION|$env:OCI_COMPARTMENT_NAME"'
    )

    result = run_pwsh(command, tmp_path, environment)

    assert result.returncode == 0
    assert result.stdout.strip() == "eu-frankfurt-1|target"


def test_import_reads_file_value_without_evaluation(tmp_path: Path) -> None:
    """A file value that looks like PowerShell code remains literal text."""
    injected = tmp_path / "INJECTED"
    configuration = tmp_path / "tenancy.env"
    configuration.write_text(f"OCI_REGION=$(New-Item {injected})\n", encoding="utf-8")
    environment = base_environment()
    environment["OCI_AGENT_ENV_FILE"] = str(configuration)
    module = SCRIPTS / "lib/ToolEnvironment.psm1"
    command = (
        f"Import-Module '{module}' -Force; "
        "$result = Import-TenancySettings -Keys @('OCI_REGION'); "
        "if ($result -ne 0) { exit $result }; Write-Output $env:OCI_REGION"
    )

    result = run_pwsh(command, tmp_path, environment)

    assert result.returncode == 0
    assert result.stdout.strip() == f"$(New-Item {injected})"
    assert not injected.exists()


def test_import_missing_key_names_the_configuration_file(tmp_path: Path) -> None:
    """A missing PowerShell tenancy setting returns 64 and identifies its file."""
    configuration = tmp_path / "missing.env"
    environment = base_environment()
    environment["OCI_AGENT_ENV_FILE"] = str(configuration)
    module = SCRIPTS / "lib/ToolEnvironment.psm1"
    command = (
        f"Import-Module '{module}' -Force; "
        "$result = Import-TenancySettings -Keys @('OCI_REGION'); exit $result"
    )

    result = run_pwsh(command, tmp_path, environment)

    assert result.returncode == 64
    assert str(configuration) in result.stderr


def test_nested_resolver_uses_parent_imported_region(tmp_path: Path) -> None:
    """The resolver can reload a value after a parent imports it from a file."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    if os.name == "nt":
        fake_oci = fake_bin / "oci.cmd"
        fake_oci.write_text("@echo off\necho FRA\n", encoding="utf-8")
    else:
        fake_oci = fake_bin / "oci"
        fake_oci.write_text("#!/usr/bin/env bash\nprintf 'FRA\\n'\n", encoding="utf-8")
        fake_oci.chmod(0o755)
    configuration = tmp_path / "tenancy.env"
    configuration.write_text("OCI_REGION=eu-frankfurt-1\n", encoding="utf-8")
    environment = base_environment()
    environment["OCI_AGENT_ENV_FILE"] = str(configuration)
    environment["PATH"] = f"{fake_bin}{os.pathsep}{environment['PATH']}"
    module = SCRIPTS / "lib/ToolEnvironment.psm1"
    resolver = SCRIPTS / "resolve_ocir_registry.ps1"
    command = (
        f"Import-Module '{module}' -Force; "
        "$result = Import-TenancySettings -Keys @('OCI_REGION'); "
        "if ($result -ne 0) { exit $result }; "
        f"& '{resolver}'"
    )

    result = run_pwsh(command, tmp_path, environment)

    assert result.returncode == 0
    assert result.stdout.strip() == "fra.ocir.io"


def test_build_rejects_an_invalid_selected_interpreter(tmp_path: Path) -> None:
    """The build script gives the Conda hint before it reaches Docker."""
    manifest = write_manifest(tmp_path / "agent")
    environment = base_environment()
    environment["OCI_AGENT_PYTHON"] = "/usr/bin/false"
    result = subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-File",
            str(SCRIPTS / "build_image.ps1"),
            "-Manifest",
            str(manifest),
            "-Tag",
            "1.0.0",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "codex-4-oci-enterprise-ai-deployment" in result.stderr
