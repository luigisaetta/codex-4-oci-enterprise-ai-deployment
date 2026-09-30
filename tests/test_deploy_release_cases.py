"""
Author: L. Saetta
Date last modified: 2026-09-30
License: MIT
Description: Exercise Hosted Application release cases with a scenario-driven OCI CLI.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy_hosted_application.sh"
MUTATING_COMMANDS = {
    "create",
    "create-hosted-deployment-single-docker-artifact",
    "add-artifact-create-single-docker-artifact-details",
    "delete",
    "update",
}


def write_manifest(directory: Path) -> Path:
    """Create a minimal deployable manifest fixture.

    Args:
        directory: Directory in which to create the fixture.

    Returns:
        Path to the generated manifest.
    """
    directory.mkdir()
    (directory / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    manifest = directory / "agent.yaml"
    manifest.write_text(
        """schema_version: 2
name: release-test
build: {context: ., dockerfile: Dockerfile}
publish: {repository: agents/release-test}
deploy: {application_name: release-test, profile: public-noauth}
verify: []
""",
        encoding="utf-8",
    )
    return manifest


def write_fake_oci(directory: Path) -> Path:
    """Write an OCI replacement that reads state and logs every invocation.

    Args:
        directory: Directory containing the executable and scenario files.

    Returns:
        Path to the fake OCI executable.
    """
    executable = directory / "oci"
    executable.write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

scenario = json.load(open(os.environ["OCI_RELEASE_SCENARIO"], encoding="utf-8"))
arguments = sys.argv[1:]
with open(os.environ["OCI_RELEASE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(arguments) + "\\n")

def output(value):
    if isinstance(value, (dict, list)):
        print(json.dumps(value))
    else:
        print(value)

if "iam" in arguments and "region" in arguments:
    output("FRA")
elif "iam" in arguments and "compartment" in arguments:
    query = arguments[arguments.index("--query") + 1]
    output("1" if "length(" in query else "ocid1.compartment.test")
elif "list-hosted-applications" in arguments:
    query = arguments[arguments.index("--query") + 1]
    application_id = "ocid1.generativeaihostedapplication.test"
    output(str(scenario["application_count"]) if "length(" in query else application_id)
elif "hosted-application" in arguments and "get" in arguments:
    output(
        {
            "data": {
                "lifecycle-state": "ACTIVE",
                "environment-variables": scenario["runtime"],
            }
        }
    )
elif "list-hosted-deployments" in arguments:
    query = arguments[arguments.index("--query") + 1]
    deployment_id = "ocid1.generativeaihosteddeployment.test"
    output(str(scenario["deployment_count"]) if "length(" in query else deployment_id)
elif "hosted-deployment" in arguments and "get" in arguments:
    gets = scenario.setdefault("get_count", 0)
    scenario["get_count"] = gets + 1
    with open(os.environ["OCI_RELEASE_SCENARIO"], "w", encoding="utf-8") as file:
        json.dump(scenario, file)
    active = scenario["target"]
    if not gets or not scenario["activation_succeeds"]:
        active = scenario["active"]
    output(
        {
            "data": {
                "lifecycle-state": scenario["deployment_state"],
                "active-artifact": {"tag": active},
                "artifacts": scenario["artifacts"],
            }
        }
    )
elif "hosted-application" in arguments and "create" in arguments:
    output({"data": {"id": "ocid1.generativeaihostedapplication.created"}})
elif "create-hosted-deployment-single-docker-artifact" in arguments:
    output({"data": {"id": "ocid1.generativeaihosteddeployment.created"}})
elif "update" in arguments:
    output({"data": {"status": scenario["work_request_state"]}})
else:
    output({"data": {}})
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def scenario_for(case: str) -> dict[str, object]:
    """Return OCI state for a named release case.

    Args:
        case: Release or stop-condition scenario name.

    Returns:
        JSON-serializable fake OCI state.
    """
    artifacts = [
        {
            "container-uri": "fra.ocir.io/namespace/agents/release-test",
            "tag": "1.0.0",
            "status": "ACTIVE",
        }
    ]
    scenario: dict[str, object] = {
        "application_count": 1,
        "deployment_count": 1,
        "runtime": [],
        "deployment_state": "ACTIVE",
        "active": "1.0.0",
        "target": "1.0.1",
        "artifacts": artifacts,
        "activation_succeeds": True,
        "work_request_state": "SUCCEEDED",
    }
    if case == "first_release":
        scenario.update(application_count=0, deployment_count=0)
    elif case == "application_without_deployment":
        scenario.update(deployment_count=0)
    elif case == "already_released":
        scenario.update(target="1.0.0")
    elif case == "rollback":
        artifacts.append(
            {
                "container-uri": "fra.ocir.io/namespace/agents/release-test",
                "tag": "1.0.1",
                "status": "INACTIVE",
            }
        )
    elif case == "updating":
        scenario.update(deployment_state="UPDATING")
    elif case == "failed_artifact":
        artifacts.append(
            {
                "container-uri": "fra.ocir.io/namespace/agents/release-test",
                "tag": "1.0.1",
                "status": "FAILED",
            }
        )
    elif case == "artifact_limit":
        scenario["artifacts"] = artifacts * 20
    elif case == "two_deployments":
        scenario.update(deployment_count=2)
    elif case == "runtime_mismatch":
        scenario.update(runtime=[{"name": "OTHER", "value": "value"}])
    elif case == "work_request_failed":
        scenario.update(work_request_state="FAILED", activation_succeeds=False)
    return scenario


def run_release(
    tmp_path: Path, case: str, apply: bool, shell: str
) -> subprocess.CompletedProcess[str]:
    """Run the release script with the selected fake OCI scenario.

    Args:
        tmp_path: Temporary test directory.
        case: Scenario to execute.
        apply: Whether to use apply mode.
        shell: Bash executable used to run the script.

    Returns:
        Captured script process result.
    """
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    write_fake_oci(fake_bin)
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps(scenario_for(case)), encoding="utf-8")
    log_path = tmp_path / "oci.log"
    environment = os.environ.copy()
    environment.update(
        OCI_AGENT_PYTHON=sys.executable,
        OCI_REGION="test-region",
        OCI_COMPARTMENT_NAME="test-compartment",
        OCIR_TENANCY_NAMESPACE="namespace",
        OCI_RELEASE_SCENARIO=str(scenario_path),
        OCI_RELEASE_LOG=str(log_path),
        PATH=f"{fake_bin}{os.pathsep}{environment['PATH']}",
    )
    target_tag = "1.0.1"
    if case == "already_released":
        target_tag = "1.0.0"
    result = subprocess.run(
        [
            shell,
            str(SCRIPT),
            "--apply" if apply else "--plan",
            "--manifest",
            str(write_manifest(tmp_path / "agent")),
            "--tag",
            target_tag,
        ],
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


def mutating_commands(result: subprocess.CompletedProcess[str]) -> list[str]:
    """Return the mutating OCI command names recorded by the fake CLI."""
    return [
        next(command for command in MUTATING_COMMANDS if command in invocation)
        for invocation in result.invocations
        if any(command in invocation for command in MUTATING_COMMANDS)
    ]


@pytest.mark.parametrize(
    ("case", "returncode"),
    [
        ("first_release", 0),
        ("application_without_deployment", 0),
        ("already_released", 0),
        ("new_version", 0),
        ("rollback", 0),
        ("updating", 20),
        ("failed_artifact", 20),
        ("artifact_limit", 20),
        ("two_deployments", 20),
        ("runtime_mismatch", 20),
    ],
)
def test_plan_never_mutates_for_any_scenario(
    tmp_path: Path, case: str, returncode: int
) -> None:
    """Every release and stop case remains read-only in plan mode."""
    result = run_release(
        tmp_path, case, apply=False, shell=shutil.which("bash") or "/bin/bash"
    )
    assert result.returncode == returncode, result.stderr
    assert not mutating_commands(result)


@pytest.mark.parametrize(
    "case",
    [
        "updating",
        "failed_artifact",
        "artifact_limit",
        "two_deployments",
        "runtime_mismatch",
    ],
)
def test_stop_conditions_do_not_mutate(tmp_path: Path, case: str) -> None:
    """Unsafe deployment states stop before any OCI mutation."""
    result = run_release(
        tmp_path, case, apply=True, shell=shutil.which("bash") or "/bin/bash"
    )
    assert result.returncode == 20
    assert not mutating_commands(result)


def test_apply_first_release_creates_and_reports_ocids(tmp_path: Path) -> None:
    """The first release creates application then deployment and reports both IDs."""
    result = run_release(
        tmp_path, "first_release", apply=True, shell=shutil.which("bash") or "/bin/bash"
    )
    assert result.returncode == 0, result.stderr
    assert mutating_commands(result) == [
        "create",
        "create-hosted-deployment-single-docker-artifact",
    ]
    assert (
        "Created Hosted Application: ocid1.generativeaihostedapplication.created"
        in result.stdout
    )
    assert (
        "Created Hosted Deployment: ocid1.generativeaihosteddeployment.created"
        in result.stdout
    )


def test_application_without_deployment_reuses_application(tmp_path: Path) -> None:
    """An application without a deployment creates only its first deployment."""
    result = run_release(
        tmp_path,
        "application_without_deployment",
        apply=True,
        shell=shutil.which("bash") or "/bin/bash",
    )
    assert result.returncode == 0, result.stderr
    assert mutating_commands(result) == [
        "create-hosted-deployment-single-docker-artifact"
    ]
    assert "Reusing ACTIVE Hosted Application" in result.stdout


def test_apply_already_released_does_not_mutate(tmp_path: Path) -> None:
    """An active target tag succeeds without an OCI mutation."""
    result = run_release(
        tmp_path,
        "already_released",
        apply=True,
        shell=shutil.which("bash") or "/bin/bash",
    )
    assert result.returncode == 0, result.stderr
    assert not mutating_commands(result)


def test_apply_new_version_adds_then_activates_and_confirms(tmp_path: Path) -> None:
    """A new tag is added before update and is confirmed by a final deployment get."""
    result = run_release(
        tmp_path, "new_version", apply=True, shell=shutil.which("bash") or "/bin/bash"
    )
    assert result.returncode == 0, result.stderr
    assert mutating_commands(result) == [
        "add-artifact-create-single-docker-artifact-details",
        "update",
    ]
    assert (
        sum(
            "hosted-deployment" in call and "get" in call for call in result.invocations
        )
        == 2
    )


def test_apply_rollback_only_activates(tmp_path: Path) -> None:
    """An inactive artifact is activated without adding another artifact."""
    result = run_release(
        tmp_path, "rollback", apply=True, shell=shutil.which("bash") or "/bin/bash"
    )
    assert result.returncode == 0, result.stderr
    assert mutating_commands(result) == ["update"]


def test_failed_work_request_reports_state_and_fails(tmp_path: Path) -> None:
    """A failed activation reports its work-request status and exits nonzero."""
    result = run_release(
        tmp_path,
        "work_request_failed",
        apply=True,
        shell=shutil.which("bash") or "/bin/bash",
    )
    assert result.returncode == 1
    assert "work-request status=FAILED" in result.stderr


def test_release_cases_work_with_bash_3_when_available(tmp_path: Path) -> None:
    """The release workflow avoids Bash features unavailable in macOS Bash 3.x."""
    bash32 = Path("/bin/bash")
    version = subprocess.run(
        [str(bash32), "--version"], capture_output=True, text=True, check=False
    )
    if not bash32.is_file() or not version.stdout.startswith("GNU bash, version 3."):
        pytest.skip("/bin/bash is not Bash 3.x.")
    result = run_release(tmp_path, "rollback", apply=True, shell=str(bash32))
    assert result.returncode == 0, result.stderr
