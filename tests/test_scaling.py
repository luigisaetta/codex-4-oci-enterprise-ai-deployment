"""
Author: L. Saetta
Date last modified: 2026-10-13
License: MIT
Description: Test the number of replicas at Hosted Application creation (Spec 023).
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import test_deploy_release_cases as release_cases
from scripts.agent_manifest import load_manifest, scaling_config, scaling_matches

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TOOL = ROOT / "scripts" / "agent_manifest.py"
SCALING = "  scaling: {min_replicas: 1, max_replicas: 1}\n"


def manifest_with(directory: Path, scaling: str) -> Path:
    """Write a minimal manifest with an optional deploy.scaling line.

    Args:
        directory: Folder for the manifest and its Dockerfile.
        scaling: YAML line for ``deploy.scaling``, or an empty string.

    Returns:
        Path to the manifest.
    """
    directory.mkdir()
    (directory / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    manifest = directory / "agent.yaml"
    manifest.write_text(
        "schema_version: 2\n"
        "name: scale-test\n"
        "build: {context: ., dockerfile: Dockerfile}\n"
        "publish: {repository: agents/scale-test}\n"
        "deploy:\n"
        "  application_name: scale-test\n"
        "  profile: public-noauth\n"
        f"{scaling}"
        "verify: []\n",
        encoding="utf-8",
    )
    return manifest


def test_scaling_section_builds_the_oci_configuration(tmp_path: Path) -> None:
    """A valid section yields the replicas with the platform-default metric."""
    manifest = load_manifest(str(manifest_with(tmp_path / "agent", SCALING)))

    assert scaling_config(manifest) == {
        "minReplica": 1,
        "maxReplica": 1,
        "scalingType": "REQUESTS_PER_SECOND",
        "targetRpsThreshold": 50,
    }


def test_without_scaling_nothing_is_sent_or_compared(tmp_path: Path) -> None:
    """Without the section the platform default applies and any value matches."""
    manifest = load_manifest(str(manifest_with(tmp_path / "agent", "")))

    assert scaling_config(manifest) is None
    assert scaling_matches(manifest, {"data": {"scaling-config": {"max-replica": 3}}})


@pytest.mark.parametrize(
    "scaling",
    [
        "  scaling: {min_replicas: 0, max_replicas: 1}\n",
        "  scaling: {min_replicas: 2, max_replicas: 1}\n",
        "  scaling: {min_replicas: 1, max_replicas: 31}\n",
        "  scaling: {min_replicas: 1, max_replicas: '2'}\n",
        "  scaling: {min_replicas: true, max_replicas: 1}\n",
        "  scaling: {min_replicas: 1}\n",
        "  scaling: {min_replicas: 1, max_replicas: 1, scaling_type: CPU}\n",
    ],
)
def test_invalid_scaling_is_rejected(tmp_path: Path, scaling: str) -> None:
    """Out-of-range, non-integer, missing, and unknown fields exit 64."""
    manifest = manifest_with(tmp_path / "agent", scaling)
    result = subprocess.run(
        [sys.executable, str(MANIFEST_TOOL), "validate", "--manifest", str(manifest)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 64
    assert "manifest.deploy.scaling" in result.stderr


def test_scaling_matches_compares_the_replicas(tmp_path: Path) -> None:
    """The replicas of an existing application must equal the manifest."""
    manifest = load_manifest(str(manifest_with(tmp_path / "agent", SCALING)))
    same = {"data": {"scaling-config": {"min-replica": 1, "max-replica": 1}}}
    other = {"data": {"scaling-config": {"min-replica": 1, "max-replica": 3}}}

    assert scaling_matches(manifest, same)
    assert not scaling_matches(manifest, other)
    assert not scaling_matches(manifest, {"data": {}})


def test_scaling_config_command_prints_json_or_nothing(tmp_path: Path) -> None:
    """The CLI helper prints the JSON only when the section exists."""
    with_scaling = manifest_with(tmp_path / "with", SCALING)
    without = manifest_with(tmp_path / "without", "")

    def run(manifest: Path) -> str:
        return subprocess.run(
            [
                sys.executable,
                str(MANIFEST_TOOL),
                "scaling-config",
                "--manifest",
                str(manifest),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout

    assert json.loads(run(with_scaling))["maxReplica"] == 1
    assert run(without) == ""


@pytest.fixture(
    name="release_runner",
    params=[
        pytest.param(
            (release_cases.SCRIPT, [shutil.which("bash") or "/bin/bash"]),
            id="bash",
            marks=pytest.mark.skipif(
                os.name == "nt", reason="Bash fixtures use POSIX paths."
            ),
        ),
        pytest.param(
            (
                release_cases.POWERSHELL_SCRIPT,
                [release_cases.PWSH, "-NoProfile", "-File"],
            ),
            id="powershell",
            marks=pytest.mark.skipif(
                release_cases.PWSH is None, reason="pwsh is unavailable."
            ),
        ),
    ],
)
def release_runner_fixture(request: pytest.FixtureRequest) -> tuple[Path, list[str]]:
    """Return the deploy script and shell for each offline scenario."""
    return request.param


@pytest.fixture(name="scaled_manifest")
def scaled_manifest_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the shared release runner write a manifest with deploy.scaling."""
    original = release_cases.write_manifest

    def write(directory: Path, profile: str = "public-noauth") -> Path:
        manifest = original(directory, profile)
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            text.replace(f"  profile: {profile}\n", f"  profile: {profile}\n{SCALING}"),
            encoding="utf-8",
        )
        return manifest

    monkeypatch.setattr(release_cases, "write_manifest", write)


def create_arguments(result) -> list[str]:
    """Return the arguments of the recorded Hosted Application create call.

    Args:
        result: Completed release run.

    Returns:
        The create call arguments.
    """
    return next(
        invocation
        for invocation in result.invocations
        if "hosted-application" in invocation and "create" in invocation
    )


@pytest.mark.usefixtures("scaled_manifest")
def test_first_release_sends_the_scaling_configuration(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """The creation carries --scaling-config and the plan shows the replicas."""
    result = release_cases.run_release(tmp_path, "first_release", True, release_runner)

    assert result.returncode == 0, result.stderr
    arguments = create_arguments(result)
    sent = json.loads(arguments[arguments.index("--scaling-config") + 1])
    assert sent == {
        "minReplica": 1,
        "maxReplica": 1,
        "scalingType": "REQUESTS_PER_SECOND",
        "targetRpsThreshold": 50,
    }
    assert "Scaling: 1-1 replicas" in result.stdout


def test_first_release_without_scaling_sends_none(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """Without deploy.scaling the creation is unchanged."""
    result = release_cases.run_release(tmp_path, "first_release", True, release_runner)

    assert result.returncode == 0, result.stderr
    assert "--scaling-config" not in create_arguments(result)
    assert "Scaling: platform default" in result.stdout


@pytest.mark.usefixtures("scaled_manifest")
def test_existing_application_with_other_replicas_stops(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """A difference in replicas stops the deploy with exit 20 and no mutation."""
    release_cases.EXTRA_SCENARIOS["existing_scaled_differently"] = {
        "scaling_config": {"min-replica": 1, "max-replica": 3}
    }
    try:
        result = release_cases.run_release(
            tmp_path, "existing_scaled_differently", False, release_runner
        )
    finally:
        release_cases.EXTRA_SCENARIOS.pop("existing_scaled_differently")

    assert result.returncode == 20
    assert "scaling differs from the manifest" in result.stderr
    assert not release_cases.mutating_commands(result)
