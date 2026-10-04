"""
Author: L. Saetta
Date last modified: 2026-10-04
License: MIT
Description: Offline tests for the read-only setup check orchestrator.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_setup.sh"
BASH = shutil.which("bash")
TENANCY = {
    "OCI_REGION": "eu-frankfurt-1",
    "OCI_COMPARTMENT_NAME": "compartment-marker",
    "OCIR_TENANCY_NAMESPACE": "namespace-marker",
    "OCIR_USERNAME": "user-marker",
}
FAKE_DOCKER = """#!/usr/bin/env bash
case "$*" in
  "info "*) printf '27.0|arm64|Docker Desktop\\n' ;;
  "buildx version") printf 'buildx v0.17\\n' ;;
  "buildx inspect"*) printf 'Name: default\\nPlatforms: linux/arm64, linux/amd64\\n' ;;
  *) exit 0 ;;
esac
"""
FAKE_OCI = """#!/usr/bin/env bash
if [[ -n "${FAKE_OCI_FAIL:-}" ]]; then
  printf 'ServiceError: {"status": 401}\\n' >&2
  exit 1
fi
case "$*" in
  *"iam region list"*) printf 'FRA\\n' ;;
  *"iam compartment list"*"length("*) printf '1\\n' ;;
  *"iam compartment list"*) printf 'ocid1.compartment.oc1..fake\\n' ;;
  *"repository list"*"length("*) printf '%s\\n' "${FAKE_REPO_COUNT:-1}" ;;
  *"repository list"*) printf 'ocid1.containerrepo.oc1..fake\\n' ;;
  *) exit 0 ;;
esac
"""
MANIFEST = """schema_version: 2
name: sample
build:
  context: .
  dockerfile: Dockerfile
publish:
  repository: agents/sample
deploy:
  application_name: sample
  profile: public-noauth
verify:
  - method: POST
    path: /hello
    body: {name: World}
    expect_status: 200
"""

pytestmark = pytest.mark.skipif(BASH is None, reason="Bash is unavailable.")


@pytest.fixture(name="setup_env")
def setup_env_fixture(tmp_path: Path) -> dict[str, str]:
    """Return an environment with fake CLIs, a tenancy file, and linked skills."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name, content in (("docker", FAKE_DOCKER), ("oci", FAKE_OCI)):
        executable = fake_bin / name
        executable.write_text(content, encoding="utf-8")
        executable.chmod(0o755)
    tenancy = tmp_path / "tenancy.env"
    tenancy.write_text(
        "".join(f"{key}={value}\n" for key, value in TENANCY.items()), encoding="utf-8"
    )
    skills = tmp_path / "skills"
    skills.mkdir()
    for skill in sorted((ROOT / "skills").glob("*/SKILL.md")):
        (skills / skill.parent.name).symlink_to(skill.parent, target_is_directory=True)
    environment = {
        key: value for key, value in os.environ.items() if key not in TENANCY
    }
    environment["PATH"] = (
        f"{fake_bin}{os.pathsep}{Path(sys.executable).parent}"
        f"{os.pathsep}{environment.get('PATH', '')}"
    )
    environment["OCI_AGENT_PYTHON"] = sys.executable
    environment["OCI_AGENT_ENV_FILE"] = str(tenancy)
    environment["SKILLS_TARGET"] = str(skills)
    return environment


def run_check(
    environment: dict[str, str], *arguments: str, cwd: Path
) -> subprocess.CompletedProcess[str]:
    """Run the setup check with the prepared environment.

    Args:
        environment: Process environment from the fixture.
        *arguments: Command-line arguments.
        cwd: Working directory.

    Returns:
        Captured process result.
    """
    return subprocess.run(
        [str(BASH), str(SCRIPT), *arguments],
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_every_check_passes(setup_env: dict[str, str], tmp_path: Path) -> None:
    """All four base checks pass and no tenancy value is printed."""
    result = run_check(
        setup_env, "--skills-target", setup_env["SKILLS_TARGET"], cwd=tmp_path
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("[PASS]") == 4
    assert "Result: all 4 checks passed." in result.stdout
    assert all(value not in result.stdout for value in TENANCY.values())


def test_failure_does_not_stop_later_checks(
    setup_env: dict[str, str], tmp_path: Path
) -> None:
    """A failing OCI CLI is reported, and the skills check still runs."""
    setup_env["FAKE_OCI_FAIL"] = "1"
    result = run_check(
        setup_env, "--skills-target", setup_env["SKILLS_TARGET"], cwd=tmp_path
    )
    assert result.returncode == 1
    assert "[FAIL] OCI CLI and region" in result.stdout
    assert "[PASS] Skills installed" in result.stdout
    assert "Result: 1 of 4 checks failed." in result.stdout


def test_missing_skills_target_fails_without_creating_it(
    setup_env: dict[str, str], tmp_path: Path
) -> None:
    """The installer is not run against a missing target directory."""
    missing = tmp_path / "missing-skills"
    result = run_check(setup_env, "--skills-target", str(missing), cwd=tmp_path)
    assert result.returncode == 1
    assert "[FAIL] Skills installed" in result.stdout
    assert not missing.exists()


def test_manifest_with_absent_repository_passes(
    setup_env: dict[str, str], tmp_path: Path
) -> None:
    """An OCIR repository that does not exist yet is not a failure."""
    manifest = tmp_path / "agent" / "agent.yaml"
    manifest.parent.mkdir()
    manifest.write_text(MANIFEST, encoding="utf-8")
    (manifest.parent / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    setup_env["FAKE_REPO_COUNT"] = "0"
    result = run_check(
        setup_env,
        "--manifest",
        str(manifest),
        "--skills-target",
        setup_env["SKILLS_TARGET"],
        cwd=manifest.parent,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[PASS] Agent manifest" in result.stdout
    assert "not created yet" in result.stdout
    assert "Result: all 6 checks passed." in result.stdout


@pytest.mark.parametrize("arguments", [["--unknown"], ["--manifest"], ["extra"]])
def test_invalid_arguments_exit_64(
    setup_env: dict[str, str], tmp_path: Path, arguments: list[str]
) -> None:
    """Malformed arguments use the project's invalid-input exit code."""
    assert run_check(setup_env, *arguments, cwd=tmp_path).returncode == 64
