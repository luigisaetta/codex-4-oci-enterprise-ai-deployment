"""
Author: L. Saetta
Date last modified: 2026-09-29
License: MIT
Description: Verify manifest utilities work when called outside the tool home.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
TENANCY_KEYS = (
    "OCI_REGION",
    "OCI_COMPARTMENT_NAME",
    "OCIR_TENANCY_NAMESPACE",
    "OCIR_USERNAME",
)


@pytest.fixture(autouse=True)
def clear_allowed_roots_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent operator configuration from affecting working-directory tests."""
    monkeypatch.delenv("OCI_AGENT_ENV_FILE", raising=False)
    monkeypatch.delenv("OCI_AGENT_PYTHON", raising=False)
    monkeypatch.delenv("OCI_AGENT_ALLOWED_ROOTS", raising=False)
    for key in TENANCY_KEYS:
        monkeypatch.delenv(key, raising=False)


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


def test_manifest_checks_run_by_path_rejects_invalid_json(tmp_path: Path) -> None:
    """The checks script validates standard input outside the repository."""
    working_directory = tmp_path / "outside-tool-home"
    working_directory.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "run_manifest_checks.py"),
            "--base-url",
            "http://127.0.0.1:8080",
            "--timeout-seconds",
            "1",
        ],
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
        input="not-json",
    )

    assert result.returncode == 64
    assert "Invalid checks JSON" in result.stderr


def test_manifest_checks_run_by_path_accepts_an_empty_list(tmp_path: Path) -> None:
    """The checks script accepts an empty check list outside the repository."""
    working_directory = tmp_path / "outside-tool-home"
    working_directory.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "run_manifest_checks.py"),
            "--base-url",
            "http://127.0.0.1:8080",
            "--timeout-seconds",
            "1",
        ],
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
        input="[]",
    )

    assert result.returncode == 0


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
    environment = os.environ.copy()
    environment["PATH"] = (
        f"{Path(sys.executable).parent}{os.pathsep}{environment.get('PATH', '')}"
    )
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
        env=environment,
    )

    assert result.returncode == 3


def test_tool_environment_library_loads_literal_configuration(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The Bash library exports file-backed values without evaluating them."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash is unavailable, so the Bash configuration test cannot run.")
    injected = tmp_path / "INJECTED"
    configuration = tmp_path / "tenancy.env"
    configuration.write_text(f"OCI_REGION=$(touch {injected})\n", encoding="utf-8")
    monkeypatch.setenv("OCI_AGENT_ENV_FILE", str(configuration))
    monkeypatch.setenv("OCI_AGENT_PYTHON", sys.executable)
    result = subprocess.run(
        [
            bash,
            "-c",
            'source "$1"; resolve_python; load_tenancy_settings OCI_REGION; '
            'printf "%s" "$OCI_REGION"',
            "bash",
            str(SCRIPTS / "lib/tool_env.sh"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == f"$(touch {injected})"
    assert not injected.exists()


def test_build_image_rejects_an_interpreter_without_pyyaml(tmp_path: Path) -> None:
    """The build script gives the Conda hint before reading a manifest."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash is unavailable, so the Bash interpreter test cannot run.")
    manifest = write_manifest(tmp_path / "agent")
    working_directory = tmp_path / "outside-tool-home"
    working_directory.mkdir()
    environment = os.environ.copy()
    environment["OCI_AGENT_PYTHON"] = "/usr/bin/false"
    result = subprocess.run(
        [
            bash,
            str(SCRIPTS / "build_image.sh"),
            "--manifest",
            str(manifest),
            "--tag",
            "1.0.0",
        ],
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 1
    assert "codex-4-oci-enterprise-ai-deployment" in result.stderr


def test_tool_environment_keeps_exported_values_with_a_missing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An empty tool-config response preserves already exported tenancy values."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash is unavailable, so the Bash environment test cannot run.")
    monkeypatch.setenv("OCI_AGENT_ENV_FILE", str(tmp_path / "missing.env"))
    monkeypatch.setenv("OCI_AGENT_PYTHON", sys.executable)
    monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")
    monkeypatch.setenv("OCI_COMPARTMENT_NAME", "target")
    monkeypatch.setenv("OCIR_TENANCY_NAMESPACE", "namespace")
    monkeypatch.setenv("OCIR_USERNAME", "user")
    result = subprocess.run(
        [
            bash,
            "-c",
            'source "$1"; resolve_python; load_tenancy_settings "${@:2}"; '
            'printf "%s|%s|%s|%s" "$OCI_REGION" "$OCI_COMPARTMENT_NAME" '
            '"$OCIR_TENANCY_NAMESPACE" "$OCIR_USERNAME"',
            "bash",
            str(SCRIPTS / "lib/tool_env.sh"),
            *TENANCY_KEYS,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == "eu-frankfurt-1|target|namespace|user"


def test_tool_environment_allows_nested_configuration_loading(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A child Bash process reloads an exported value without failure."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash is unavailable, so the nested Bash test cannot run.")
    configuration = tmp_path / "tenancy.env"
    configuration.write_text("OCI_REGION=eu-frankfurt-1\n", encoding="utf-8")
    monkeypatch.setenv("OCI_AGENT_ENV_FILE", str(configuration))
    monkeypatch.setenv("OCI_AGENT_PYTHON", sys.executable)
    parent_command = (
        'source "$1"; resolve_python; load_tenancy_settings OCI_REGION; '
        'bash -c \'source "$1"; resolve_python; '
        'load_tenancy_settings OCI_REGION; printf "%s" "$OCI_REGION"\' '
        'bash "$1"'
    )
    result = subprocess.run(
        [
            bash,
            "-c",
            parent_command,
            "bash",
            str(SCRIPTS / "lib/tool_env.sh"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout == "eu-frankfurt-1"


def test_resolve_registry_uses_an_exported_region_with_fake_oci(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The registry resolver accepts exported configuration in a child script."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("Bash is unavailable, so the registry test cannot run.")
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_oci = fake_bin / "oci"
    fake_oci.write_text(
        """#!/usr/bin/env bash
if [[ " $* " == *" --raw-output "* ]]; then
  printf 'FRA\\n'
else
  printf '%s\\n' '{"data":[{"name":"eu-frankfurt-1","key":"FRA"}]}'
fi
""",
        encoding="utf-8",
    )
    fake_oci.chmod(0o755)
    monkeypatch.setenv("OCI_REGION", "eu-frankfurt-1")
    monkeypatch.setenv("OCI_AGENT_PYTHON", sys.executable)
    environment = os.environ.copy()
    environment["PATH"] = (
        f"{fake_bin}{os.pathsep}{Path(sys.executable).parent}"
        f"{os.pathsep}{environment.get('PATH', '')}"
    )
    result = subprocess.run(
        [bash, str(SCRIPTS / "resolve_ocir_registry.sh")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 0
    assert result.stdout == "fra.ocir.io\n"
