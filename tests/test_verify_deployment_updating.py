"""
Author: L. Saetta
Date last modified: 2026-09-30
License: MIT
Description: Exercise verifier handling of OCI Hosted Deployment update states.
"""

# pylint: disable=duplicate-code

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASH_SCRIPT = ROOT / "scripts" / "verify_deployment.sh"
POWERSHELL_SCRIPT = ROOT / "scripts" / "verify_deployment.ps1"
PWSH = shutil.which("pwsh")
APPLICATION_ID = "ocid1.generativeaihostedapplication.oc1.test"
MUTATING_COMMANDS = {"create", "delete", "update", "add-artifact"}


def write_manifest(directory: Path) -> Path:
    """Write a minimal manifest accepted by the verifier.

    Args:
        directory: Fixture directory.

    Returns:
        Path to the generated manifest.
    """
    directory.mkdir()
    (directory / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    manifest = directory / "agent.yaml"
    manifest.write_text(
        """schema_version: 2
name: verify-test
build: {context: ., dockerfile: Dockerfile}
publish: {repository: agents/verify-test}
deploy: {application_name: verify-test, profile: public-noauth}
verify: []
""",
        encoding="utf-8",
    )
    return manifest


def write_fake_tools(directory: Path) -> None:
    """Write read-only OCI and successful curl replacements.

    Args:
        directory: Directory placed first on PATH.
    """
    oci = directory / "oci"
    oci.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

scenario_path = os.environ["OCI_VERIFY_SCENARIO"]
scenario = json.load(open(scenario_path, encoding="utf-8"))
arguments = sys.argv[1:]
with open(os.environ["OCI_VERIFY_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(arguments) + "\\n")

query = arguments[arguments.index("--query") + 1] if "--query" in arguments else ""
state_index = scenario.get("state_index", 0)
states = scenario["states"]
state = states[min(state_index, len(states) - 1)]

if "hosted-application" in arguments and "get" in arguments:
    print("ACTIVE" if "lifecycle-state" in query else "ocid1.compartment.test")
elif "list-hosted-deployments" in arguments:
    if "length(" in query:
        print("1" if "!=`DELETED`" in query or state == "ACTIVE" else "0")
    elif "active-artifact" in query:
        print("1.2.3")
    else:
        print("ocid1.generativeaihosteddeployment.test")
elif "hosted-deployment" in arguments and "get" in arguments:
    if "lifecycle-state" in query:
        print(state)
        scenario["state_index"] = state_index + 1
        with open(scenario_path, "w", encoding="utf-8") as file:
            json.dump(scenario, file)
    else:
        print("1.2.3")
else:
    raise SystemExit("Unexpected OCI command: " + " ".join(arguments))
""",
        encoding="utf-8",
    )
    oci.chmod(0o755)
    curl = directory / "curl"
    curl.write_text("#!/bin/sh\nprintf '200'\n", encoding="utf-8")
    curl.chmod(0o755)


def run_verifier(
    tmp_path: Path, states: list[str], runner: tuple[Path, list[str]]
) -> subprocess.CompletedProcess[str]:
    """Run one verifier scenario without OCI or network access.

    Args:
        tmp_path: Temporary fixture directory.
        states: Ordered deployment states returned by fake OCI.
        runner: Verifier script and its interpreter command.

    Returns:
        Captured verifier result with recorded OCI invocations.
    """
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    write_fake_tools(fake_bin)
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps({"states": states}), encoding="utf-8")
    log_path = tmp_path / "oci.log"
    script, command = runner
    options = [
        "--application-id",
        APPLICATION_ID,
        "--manifest",
        str(write_manifest(tmp_path / "agent")),
        "--tag",
        "1.2.3",
        "--timeout-seconds",
        "1",
        "--poll-seconds",
        "1",
    ]
    if script.suffix == ".ps1":
        options = [
            "-ApplicationId",
            APPLICATION_ID,
            "-Manifest",
            options[3],
            "-Tag",
            "1.2.3",
            "-TimeoutSeconds",
            "1",
            "-PollSeconds",
            "1",
        ]
    environment = os.environ.copy()
    environment.update(
        OCI_AGENT_PYTHON=sys.executable,
        OCI_REGION="test-region",
        OCI_VERIFY_SCENARIO=str(scenario_path),
        OCI_VERIFY_LOG=str(log_path),
        PATH=f"{fake_bin}{os.pathsep}{environment['PATH']}",
    )
    result = subprocess.run(
        [*command, str(script), *options],
        capture_output=True,
        check=False,
        cwd=tmp_path,
        env=environment,
        text=True,
    )
    result.invocations = [
        json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
    ]
    return result


@pytest.fixture(
    name="verifier_runner",
    params=[
        pytest.param((BASH_SCRIPT, [shutil.which("bash") or "/bin/bash"]), id="bash"),
        pytest.param(
            (POWERSHELL_SCRIPT, [PWSH, "-NoProfile", "-File"]),
            id="powershell",
            marks=pytest.mark.skipif(PWSH is None, reason="pwsh is unavailable."),
        ),
    ],
)
def _verifier_runner(request: pytest.FixtureRequest) -> tuple[Path, list[str]]:
    """Return an available verifier command."""
    return request.param


def assert_read_only(result: subprocess.CompletedProcess[str]) -> None:
    """Assert that a verifier scenario made no OCI mutation.

    Args:
        result: Completed verifier invocation.
    """
    assert not any(
        any(command in invocation for command in MUTATING_COMMANDS)
        for invocation in result.invocations
    )


def test_updating_deployment_becomes_active_and_passes(
    tmp_path: Path, verifier_runner: tuple[Path, list[str]]
) -> None:
    """An updating deployment is rechecked before standard probes pass."""
    result = run_verifier(tmp_path, ["UPDATING", "ACTIVE"], verifier_runner)
    assert result.returncode == 0, result.stderr
    assert "result=PASS" in result.stdout
    assert_read_only(result)


def test_updating_deployment_times_out_with_state_message(
    tmp_path: Path, verifier_runner: tuple[Path, list[str]]
) -> None:
    """An update that exhausts the shared budget returns deployment exit code 21."""
    result = run_verifier(tmp_path, ["UPDATING", "UPDATING"], verifier_runner)
    assert result.returncode == 21
    assert "still UPDATING" in result.stderr
    assert_read_only(result)


def test_active_deployment_passes_without_waiting(
    tmp_path: Path, verifier_runner: tuple[Path, list[str]]
) -> None:
    """An already active deployment retains the verifier's existing pass behavior."""
    result = run_verifier(tmp_path, ["ACTIVE"], verifier_runner)
    assert result.returncode == 0, result.stderr
    assert "result=PASS" in result.stdout
    assert_read_only(result)
