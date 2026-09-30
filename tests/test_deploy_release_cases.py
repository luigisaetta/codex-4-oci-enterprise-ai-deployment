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
POWERSHELL_SCRIPT = ROOT / "scripts" / "deploy_hosted_application.ps1"
PWSH = shutil.which("pwsh")
MUTATING_COMMANDS = {
    "create",
    "create-hosted-deployment-single-docker-artifact",
    "add-artifact-create-single-docker-artifact-details",
    "delete",
    "update",
}


def write_manifest(directory: Path, profile: str = "public-noauth") -> Path:
    """Create a minimal deployable manifest fixture.

    Args:
        directory: Directory in which to create the fixture.

    Returns:
        Path to the generated manifest.
    """
    directory.mkdir()
    (directory / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    manifest = directory / "agent.yaml"
    auth = ""
    if profile == "public-idcs":
        auth = (
            "  auth:\n"
            "    domain_url: https://idcs-example.identity.oraclecloud.com:443\n"
            "    audience: example-audience\n"
            "    scope: example-scope\n"
        )
    manifest.write_text(
        "schema_version: 2\n"
        "name: release-test\n"
        "build: {context: ., dockerfile: Dockerfile}\n"
        "publish: {repository: agents/release-test}\n"
        "deploy:\n"
        "  application_name: release-test\n"
        f"  profile: {profile}\n"
        f"{auth}"
        "verify: []\n",
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
                "inbound-auth-config": scenario["inbound_auth"],
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
    if "--force" not in arguments:
        print("Abort", file=sys.stderr)
        sys.exit(1)
    if scenario.get("update_command_fails"):
        sys.exit(1)
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
        "inbound_auth": {"inboundAuthConfigType": "NO_AUTH_CONFIG"},
        "deployment_state": "ACTIVE",
        "active": "1.0.0",
        "target": "1.0.1",
        "artifacts": artifacts,
        "activation_succeeds": True,
        "work_request_state": "SUCCEEDED",
    }
    updates = {
        "first_release": {"application_count": 0, "deployment_count": 0},
        "idcs_first_release": {"application_count": 0, "deployment_count": 0},
        "application_without_deployment": {"deployment_count": 0},
        "already_released": {"target": "1.0.0"},
        "updating": {"deployment_state": "UPDATING"},
        "two_deployments": {"deployment_count": 2},
        "runtime_mismatch": {"runtime": [{"name": "OTHER", "value": "value"}]},
        "unknown_inbound_auth": {
            "inbound_auth": {"inboundAuthConfigType": "UNKNOWN_ENUM_VALUE"}
        },
        "work_request_failed": {
            "work_request_state": "FAILED",
            "activation_succeeds": False,
        },
        "update_command_fails": {"update_command_fails": True},
    }
    scenario.update(updates.get(case, {}))
    if case == "rollback":
        artifacts.append(
            {
                "container-uri": "fra.ocir.io/namespace/agents/release-test",
                "tag": "1.0.1",
                "status": "INACTIVE",
            }
        )
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
    elif case in {"idcs_application", "idcs_to_noauth_mismatch"}:
        scenario["inbound_auth"] = {
            "inboundAuthConfigType": "IDCS_AUTH_CONFIG",
            "idcsConfig": {
                "domainUrl": "https://idcs-example.identity.oraclecloud.com:443",
                "scope": "example-scope",
                "audience": "example-audience",
            },
        }
    return scenario


def profile_for_case(case: str) -> str:
    """Return the manifest profile required by an inbound authentication scenario."""
    idcs_cases = {
        "idcs_first_release",
        "noauth_to_idcs_mismatch",
        "unknown_inbound_auth",
    }
    return "public-idcs" if case in idcs_cases else "public-noauth"


def run_release(
    tmp_path: Path,
    case: str,
    apply: bool,
    runner: tuple[Path, list[str]],
    tag: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the release script with the selected fake OCI scenario.

    Args:
        tmp_path: Temporary test directory.
        case: Scenario to execute.
        apply: Whether to use apply mode.
        runner: Script path and executable command used to run it.
        tag: Optional release tag to validate or deploy.

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
    target_tag = tag or "1.0.1"
    if tag is None and case == "already_released":
        target_tag = "1.0.0"
    script, command = runner
    manifest = str(write_manifest(tmp_path / "agent", profile_for_case(case)))
    options = [
        "-Apply" if apply else "-Plan",
        "-Manifest",
        manifest,
        "-Tag",
        target_tag,
    ]
    if script.suffix == ".sh":
        options[0] = "--apply" if apply else "--plan"
        options[1] = "--manifest"
        options[3] = "--tag"
    result = subprocess.run(
        [*command, str(script), *options],
        capture_output=True,
        check=False,
        cwd=tmp_path,
        env=environment,
        text=True,
    )
    result.invocations = []
    if log_path.exists():
        result.invocations = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
        ]
    return result


@pytest.fixture(
    name="release_runner",
    params=[
        pytest.param((SCRIPT, [shutil.which("bash") or "/bin/bash"]), id="bash"),
        pytest.param(
            (POWERSHELL_SCRIPT, [PWSH, "-NoProfile", "-File"]),
            id="powershell",
            marks=pytest.mark.skipif(PWSH is None, reason="pwsh is unavailable."),
        ),
    ],
)
def _release_runner(request: pytest.FixtureRequest) -> tuple[Path, list[str]]:
    """Return an available deployer command for shared release scenarios."""
    return request.param


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
    tmp_path: Path, case: str, returncode: int, release_runner: tuple[Path, list[str]]
) -> None:
    """Every release and stop case remains read-only in plan mode."""
    result = run_release(tmp_path, case, apply=False, runner=release_runner)
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
def test_stop_conditions_do_not_mutate(
    tmp_path: Path, case: str, release_runner: tuple[Path, list[str]]
) -> None:
    """Unsafe deployment states stop before any OCI mutation."""
    result = run_release(tmp_path, case, apply=True, runner=release_runner)
    assert result.returncode == 20
    assert not mutating_commands(result)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        (
            "updating",
            "Hosted Deployment must be ACTIVE; observed: UPDATING. Check it and retry.",
        ),
        (
            "failed_artifact",
            "Target artifact tag 1.0.1 is FAILED. Check it and retry; "
            "no changes were made.",
        ),
        (
            "artifact_limit",
            "Adding tag 1.0.1 exceeds the artifact limit of 20; no changes were made.",
        ),
        (
            "two_deployments",
            "Expected zero or one non-deleted Hosted Deployment; found 2.",
        ),
        (
            "runtime_mismatch",
            "Existing Hosted Application runtime environment differs from "
            "the manifest.",
        ),
    ],
)
def test_stop_condition_messages_match_bash(
    tmp_path: Path,
    case: str,
    message: str,
    release_runner: tuple[Path, list[str]],
) -> None:
    """Both deployers report the documented stop condition verbatim."""
    result = run_release(tmp_path, case, apply=True, runner=release_runner)
    assert result.returncode == 20
    assert result.stderr.strip() == message


@pytest.mark.parametrize("tag", ["01.2.3", "1.2.3.4", "latest"])
def test_invalid_tags_stop_before_calling_oci(
    tmp_path: Path, tag: str, release_runner: tuple[Path, list[str]]
) -> None:
    """Invalid tags fail consistently before the deployer reads OCI state."""
    result = run_release(
        tmp_path, "new_version", apply=False, runner=release_runner, tag=tag
    )
    assert result.returncode == 64
    assert result.stderr.strip() == "Tag must be semantic (MAJOR.MINOR.PATCH)."
    assert not result.invocations


@pytest.mark.parametrize("tag", ["1.2.3", "1.2.3-rc.1"])
def test_valid_semantic_tags_are_accepted(
    tmp_path: Path, tag: str, release_runner: tuple[Path, list[str]]
) -> None:
    """Strict SemVer tags proceed to OCI state discovery."""
    result = run_release(
        tmp_path, "new_version", apply=False, runner=release_runner, tag=tag
    )
    assert result.returncode == 0, result.stderr
    assert result.invocations


def test_apply_first_release_creates_and_reports_ocids(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """The first release creates application then deployment and reports both IDs."""
    result = run_release(tmp_path, "first_release", apply=True, runner=release_runner)
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


def test_public_idcs_first_release_uses_manifest_inbound_auth(tmp_path: Path) -> None:
    """A Bash first release sends the exact IDCS inbound configuration to OCI."""
    runner = (SCRIPT, [shutil.which("bash") or "/bin/bash"])
    result = run_release(
        tmp_path,
        "idcs_first_release",
        apply=True,
        runner=runner,
    )
    assert result.returncode == 0, result.stderr
    create_call = next(
        call
        for call in result.invocations
        if "hosted-application" in call and "create" in call
    )
    assert create_call[create_call.index("--inbound-auth-config") + 1] == (
        '{"inboundAuthConfigType":"IDCS_AUTH_CONFIG","idcsConfig":'
        '{"domainUrl":"https://idcs-example.identity.oraclecloud.com:443",'
        '"scope":"example-scope","audience":"example-audience"}}'
    )


def test_public_idcs_plan_reports_token_access_settings(tmp_path: Path) -> None:
    """A Bash IDCS plan describes the public endpoint and manifest settings."""
    runner = (SCRIPT, [shutil.which("bash") or "/bin/bash"])
    result = run_release(
        tmp_path,
        "idcs_first_release",
        apply=False,
        runner=runner,
    )
    assert result.returncode == 0, result.stderr
    assert "Access: public endpoint, identity-domain token required" in result.stdout
    assert (
        "Identity domain URL: https://idcs-example.identity.oraclecloud.com:443"
        in result.stdout
    )
    assert "Audience: example-audience" in result.stdout
    assert "Scope: example-scope" in result.stdout
    assert not mutating_commands(result)


@pytest.mark.parametrize(
    "case",
    [
        "idcs_to_noauth_mismatch",
        "noauth_to_idcs_mismatch",
        "unknown_inbound_auth",
    ],
)
def test_inbound_auth_mismatches_stop_bash_reuse_before_mutation(
    tmp_path: Path, case: str
) -> None:
    """Reusing an application never changes a mismatched inbound configuration."""
    runner = (SCRIPT, [shutil.which("bash") or "/bin/bash"])
    result = run_release(
        tmp_path,
        case,
        apply=True,
        runner=runner,
    )
    assert result.returncode == 20
    assert result.stderr.strip() == (
        "The existing Hosted Application uses a different inbound authentication; "
        "changing authentication is not supported."
    )
    assert not mutating_commands(result)


def test_application_without_deployment_reuses_application(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """An application without a deployment creates only its first deployment."""
    result = run_release(
        tmp_path, "application_without_deployment", apply=True, runner=release_runner
    )
    assert result.returncode == 0, result.stderr
    assert mutating_commands(result) == [
        "create-hosted-deployment-single-docker-artifact"
    ]
    assert "Reusing ACTIVE Hosted Application" in result.stdout


def test_apply_already_released_does_not_mutate(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """An active target tag succeeds without an OCI mutation."""
    result = run_release(
        tmp_path, "already_released", apply=True, runner=release_runner
    )
    assert result.returncode == 0, result.stderr
    assert not mutating_commands(result)


def test_apply_new_version_adds_then_activates_and_confirms(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """A new tag is added before update and is confirmed by a final deployment get."""
    result = run_release(tmp_path, "new_version", apply=True, runner=release_runner)
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
    update_call = next(call for call in result.invocations if "update" in call)
    assert "--force" in update_call


def test_apply_rollback_only_activates(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """An inactive artifact is activated without adding another artifact."""
    result = run_release(tmp_path, "rollback", apply=True, runner=release_runner)
    assert result.returncode == 0, result.stderr
    assert mutating_commands(result) == ["update"]


def test_failed_work_request_reports_state_and_fails(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """A failed activation reports its work-request status and exits nonzero."""
    result = run_release(
        tmp_path, "work_request_failed", apply=True, runner=release_runner
    )
    assert result.returncode == 1
    assert "work-request status=FAILED" in result.stderr


def test_failed_update_reports_unknown_work_request_status(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """An OCI update error reports the activation-specific failure message."""
    result = run_release(
        tmp_path, "update_command_fails", apply=True, runner=release_runner
    )
    assert result.returncode == 1
    expected_message = (
        "Artifact activation failed: work-request status=unknown. "
        "See the OCI CLI error above."
    )
    assert result.stderr.strip() == expected_message


def test_release_cases_work_with_bash_3_when_available(tmp_path: Path) -> None:
    """The release workflow avoids Bash features unavailable in macOS Bash 3.x."""
    bash32 = Path("/bin/bash")
    version = subprocess.run(
        [str(bash32), "--version"], capture_output=True, text=True, check=False
    )
    if not bash32.is_file() or not version.stdout.startswith("GNU bash, version 3."):
        pytest.skip("/bin/bash is not Bash 3.x.")
    result = run_release(
        tmp_path, "rollback", apply=True, runner=(SCRIPT, [str(bash32)])
    )
    assert result.returncode == 0, result.stderr
