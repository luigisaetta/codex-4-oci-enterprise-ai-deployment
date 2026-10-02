"""
Author: L. Saetta
Date last modified: 2026-10-02
License: MIT
Description: Test reliable deployment waits and failed deployment replacement offline.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from test_deploy_release_cases import (
    PWSH,
    POWERSHELL_SCRIPT,
    SCRIPT,
    mutating_commands,
    run_release,
    scenario_for,
    write_fake_oci,
)


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
def release_runner_fixture(request: pytest.FixtureRequest) -> tuple[Path, list[str]]:
    """Return the deploy script and shell for each offline scenario."""
    return request.param


def deploy_options(runner: tuple[Path, list[str]], *names: str) -> list[str]:
    """Translate shared scenario options to the selected script family."""
    if runner[0].suffix == ".sh":
        return list(names)
    return [
        option.replace("--timeout-seconds", "-TimeoutSeconds").replace(
            "--replace-failed", "-ReplaceFailed"
        )
        for option in names
    ]


@pytest.mark.parametrize("case", ["header_output", "f2_output"])
def test_first_release_parses_or_recovers_create_output(
    tmp_path: Path, case: str, release_runner: tuple[Path, list[str]]
) -> None:
    """Create responses with a header or preceding stdout text still reach ACTIVE."""
    result = run_release(tmp_path, case, True, release_runner)
    assert result.returncode == 0, result.stderr
    assert "Hosted Application: ACTIVE (elapsed" in result.stdout
    assert "Hosted Deployment: ACTIVE (elapsed" in result.stdout
    assert "--wait-for-state" not in str(result.invocations)
    assert mutating_commands(result) == [
        "create",
        "create-hosted-deployment-single-docker-artifact",
    ]


@pytest.mark.parametrize(
    ("case", "expected_code", "expected_text"),
    [
        ("creating_then_active", 0, "Hosted Deployment: ACTIVE"),
        ("creating_then_failed", 1, "OutOfCapacity"),
        ("transient_404", 0, "GET_RETRY"),
        ("transient_500", 0, "GET_RETRY"),
        ("inactive_wait", 1, "INACTIVE"),
        ("five_429", 1, "5 consecutive attempts"),
        ("creation_in_progress", 0, "Creation in progress"),
    ],
)
def test_creation_wait_and_resume(
    tmp_path: Path,
    case: str,
    expected_code: int,
    expected_text: str,
    release_runner: tuple[Path, list[str]],
) -> None:
    """Poll through progress, failure and transient get errors without mutation."""
    result = run_release(tmp_path, case, True, release_runner)
    assert result.returncode == expected_code, result.stderr
    assert expected_text in result.stdout + result.stderr
    assert not mutating_commands(result)


@pytest.mark.parametrize(
    "case", ["failed_deployment", "replacement", "replacement_404"]
)
def test_failed_deployment_plan_is_read_only(
    tmp_path: Path, case: str, release_runner: tuple[Path, list[str]]
) -> None:
    """Failed deployment reports its work request reason in a read-only plan."""
    result = run_release(tmp_path, case, False, release_runner)
    assert result.returncode == 0, result.stderr
    assert "OutOfCapacity" in result.stdout
    assert "Node pool capacity unavailable" in result.stdout
    assert not mutating_commands(result)


def test_failed_deployment_apply_without_replace_stops(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """A FAILED deployment cannot be replaced implicitly."""
    result = run_release(tmp_path, "failed_deployment", True, release_runner)
    assert result.returncode == 20
    assert not mutating_commands(result)


@pytest.mark.parametrize("case", ["replacement", "replacement_404"])
def test_replace_failed_deletes_then_creates(
    tmp_path: Path, case: str, release_runner: tuple[Path, list[str]]
) -> None:
    """Replacement waits for deletion before making the create request."""
    result = run_release(
        tmp_path,
        case,
        True,
        release_runner,
        extra_options=deploy_options(release_runner, "--replace-failed"),
    )
    assert result.returncode == 0, result.stderr
    assert mutating_commands(result) == [
        "delete",
        "create-hosted-deployment-single-docker-artifact",
    ]
    assert "Hosted Deployment: DELETED" in result.stdout
    assert "Hosted Deployment: ACTIVE" in result.stdout
    delete_index = next(
        i for i, call in enumerate(result.invocations) if "delete" in call
    )
    create_index = next(
        i
        for i, call in enumerate(result.invocations)
        if "create-hosted-deployment-single-docker-artifact" in call
    )
    assert delete_index < create_index
    assert "--force" in result.invocations[delete_index]
    assert any(
        "get" in call for call in result.invocations[delete_index + 1 : create_index]
    )


def test_replacement_delete_stderr_does_not_corrupt_json(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """Successful delete diagnostics stay outside the parsed JSON response."""
    result = run_release(
        tmp_path,
        "replacement_delete_stderr",
        True,
        release_runner,
        extra_options=deploy_options(release_runner, "--replace-failed"),
    )
    assert result.returncode == 0, result.stderr
    assert mutating_commands(result) == [
        "delete",
        "create-hosted-deployment-single-docker-artifact",
    ]
    delete_index = next(
        i for i, call in enumerate(result.invocations) if "delete" in call
    )
    create_index = next(
        i
        for i, call in enumerate(result.invocations)
        if "create-hosted-deployment-single-docker-artifact" in call
    )
    assert not any(
        "list-hosted-deployments" in call
        for call in result.invocations[delete_index + 1 : create_index]
    )


@pytest.mark.parametrize("case", ["already_released", "creation_in_progress"])
def test_replace_failed_rejected_for_other_states(
    tmp_path: Path, case: str, release_runner: tuple[Path, list[str]]
) -> None:
    """Only an existing FAILED deployment accepts the replacement flag."""
    result = run_release(
        tmp_path,
        case,
        True,
        release_runner,
        extra_options=deploy_options(release_runner, "--replace-failed"),
    )
    assert result.returncode == 64
    assert not mutating_commands(result)


@pytest.mark.parametrize(
    ("case", "code"), [("deletion_failed", 1), ("deletion_timeout", 26)]
)
def test_failed_or_timed_out_delete_never_creates(
    tmp_path: Path, case: str, code: int, release_runner: tuple[Path, list[str]]
) -> None:
    """Deletion must finish before replacement can create a deployment."""
    result = run_release(
        tmp_path,
        case,
        True,
        release_runner,
        extra_options=deploy_options(
            release_runner, "--replace-failed", "--timeout-seconds", "1"
        ),
    )
    assert result.returncode == code, result.stderr
    assert mutating_commands(result) == ["delete"]
    if code == 26:
        assert "OCI continues the operation" in result.stderr


@pytest.mark.parametrize("value", ["0", "00", "-1", "abc", "1.5"])
def test_invalid_timeout_stops_before_oci(
    tmp_path: Path, value: str, release_runner: tuple[Path, list[str]]
) -> None:
    """The timeout must be a positive integer."""
    result = run_release(
        tmp_path,
        "first_release",
        True,
        release_runner,
        extra_options=deploy_options(release_runner, "--timeout-seconds", value),
    )
    assert result.returncode == 64
    assert not result.invocations


@pytest.mark.parametrize(
    "case",
    [
        "header_output",
        "f2_output",
        "no_id_output",
        "no_id_missing",
        "delete_no_id",
        "application_creating",
        "application_failed",
        "application_runtime_mismatch_after_active",
        "application_auth_mismatch_after_active",
        "rejected_application_create",
        "rejected_deployment_create",
        "rejected_deployment_delete",
        "misleading_get_401",
        "misleading_deletion_401",
        "unreadable_get_status",
        "unreadable_deletion_status",
        "failed_missing_work_requests",
        "failed_malformed_work_requests",
        "failed_missing_work_errors",
        "failed_malformed_work_errors",
        "application_create_wait",
        "transient_500",
        "inactive_wait",
        "creating_then_active",
        "creating_then_failed",
        "creation_in_progress",
        "transient_404",
        "five_429",
        "failed_deployment",
        "replacement",
        "replacement_delete_stderr",
        "replacement_404",
        "deletion_failed",
        "deletion_timeout",
        "creation_timeout",
        "secret_failure",
    ],
)
def test_new_scenarios_plan_never_mutates(
    tmp_path: Path, case: str, release_runner: tuple[Path, list[str]]
) -> None:
    """The read-only plan invariant applies to every new wait scenario."""
    result = run_release(tmp_path, case, False, release_runner)
    assert result.returncode == 0, result.stderr
    assert not mutating_commands(result)


def test_creation_timeout_preserves_created_resource(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """A timed out create exits 26 and reports the resource for a later resume."""
    result = run_release(
        tmp_path,
        "creation_timeout",
        True,
        release_runner,
        extra_options=deploy_options(release_runner, "--timeout-seconds", "1"),
    )
    assert result.returncode == 26, result.stderr
    assert "ocid1.generativeaihosteddeployment.created" in result.stderr
    assert "CREATING" in result.stderr
    assert "OCI continues the operation" in result.stderr
    assert mutating_commands(result) == [
        "create",
        "create-hosted-deployment-single-docker-artifact",
    ]


def test_progress_and_error_redact_runtime_value(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """Even an OCI work request that echoes a variable must not expose its value."""
    secret = "privateFixtureValue123"
    result = run_release(
        tmp_path, "secret_failure", True, release_runner, runtime_value=secret
    )
    assert result.returncode == 1, result.stderr
    assert "[REDACTED]" in result.stderr
    progress = [
        line
        for line in result.stdout.splitlines()
        if line.startswith(("Hosted Application:", "Hosted Deployment:"))
    ]
    assert all(secret not in line for line in progress)
    assert secret not in result.stderr


def test_missing_mutation_id_without_lookup_stops_clearly(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """An ambiguous create response never triggers another mutation."""
    result = run_release(tmp_path, "no_id_missing", True, release_runner)
    assert result.returncode == 1
    assert "lookup found no unique resource" in result.stderr
    assert mutating_commands(result) == ["create"]


def test_one_progress_line_per_wait_poll(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """Each wait get produces exactly one sanitized progress line."""
    result = run_release(tmp_path, "creating_then_active", True, release_runner)
    assert result.returncode == 0, result.stderr
    gets = sum(
        "hosted-deployment" in call and "get" in call for call in result.invocations
    )
    progress = [
        line
        for line in result.stdout.splitlines()
        if line.startswith("Hosted Deployment:") and "(elapsed " in line
    ]
    assert len(progress) == gets - 1  # The first get selects the release case.


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("failed_missing_work_requests", "No FAILED work request found"),
        ("failed_malformed_work_requests", "No FAILED work request found"),
        ("failed_missing_work_errors", "No work request errors available"),
        ("failed_malformed_work_errors", "No work request errors available"),
    ],
)
def test_work_request_missing_or_malformed_is_reported(
    tmp_path: Path, case: str, expected: str, release_runner: tuple[Path, list[str]]
) -> None:
    """Malformed or absent F9 payloads give a stable message without a traceback."""
    result = run_release(tmp_path, case, False, release_runner)
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout
    assert "Traceback" not in result.stdout + result.stderr
    assert not mutating_commands(result)


def test_work_request_calls_use_compartment_all_and_real_shapes(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """The strict fake accepts only complete F9 list requests."""
    result = run_release(tmp_path, "failed_deployment", False, release_runner)
    assert result.returncode == 0, result.stderr
    assert "OutOfCapacity" in result.stdout
    work_lists = [
        call
        for call in result.invocations
        if "list" in call and ("work-request" in call or "work-request-error" in call)
    ]
    assert len(work_lists) == 2
    work_request = next(call for call in work_lists if "work-request-error" not in call)
    work_error = next(call for call in work_lists if "work-request-error" in call)
    assert "--compartment-id" in work_request
    assert "--all" in work_request
    assert "--all" in work_error
    assert not mutating_commands(result)


@pytest.mark.parametrize("case", ["misleading_get_401", "misleading_deletion_401"])
def test_service_error_status_ignores_incidental_digits(
    tmp_path: Path, case: str, release_runner: tuple[Path, list[str]]
) -> None:
    """A real 401 is neither transient nor a completed deletion."""
    options = (
        deploy_options(release_runner, "--replace-failed")
        if case == "misleading_deletion_401"
        else []
    )
    result = run_release(tmp_path, case, True, release_runner, extra_options=options)
    assert result.returncode == 1, result.stderr
    assert "last error: HTTP 401" in result.stderr
    assert "GET_RETRY" not in result.stdout
    assert mutating_commands(result) == (["delete"] if options else [])


@pytest.mark.parametrize(
    ("case", "mutation", "kind"),
    [
        ("rejected_application_create", "create", "Hosted Application create"),
        (
            "rejected_deployment_create",
            "create-hosted-deployment-single-docker-artifact",
            "Hosted Deployment create",
        ),
        ("rejected_deployment_delete", "delete", "Hosted Deployment delete"),
    ],
)
def test_rejected_requests_report_redacted_service_error(
    tmp_path: Path,
    case: str,
    mutation: str,
    kind: str,
    release_runner: tuple[Path, list[str]],
) -> None:
    """A rejected request prints its structured error and makes no later mutation."""
    secret = "privateFixtureValue123"
    options = (
        deploy_options(release_runner, "--replace-failed")
        if mutation == "delete"
        else []
    )
    result = run_release(
        tmp_path,
        case,
        True,
        release_runner,
        extra_options=options,
        runtime_value=secret,
    )
    assert result.returncode == 1, result.stderr
    assert f"{kind} request failed: status=403; code=NotAllowed;" in result.stderr
    assert "message=" in result.stderr and "[REDACTED]" in result.stderr
    assert secret not in result.stderr
    assert "ServiceError:" not in result.stdout + result.stderr
    assert mutating_commands(result) == [mutation]


def test_application_creation_in_progress_completes_first_release(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """The application wait and checks finish before deployment creation."""
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    apply_dir = tmp_path / "apply"
    apply_dir.mkdir()
    plan = run_release(plan_dir, "application_creating", False, release_runner)
    assert plan.returncode == 0, plan.stderr
    assert "Release case: Application creation in progress" in plan.stdout
    assert "Create Hosted Deployment with tag: 1.0.1" in plan.stdout
    assert not mutating_commands(plan)
    apply_result = run_release(apply_dir, "application_creating", True, release_runner)
    assert apply_result.returncode == 0, apply_result.stderr
    assert mutating_commands(apply_result) == [
        "create-hosted-deployment-single-docker-artifact"
    ]
    create_index = next(
        i
        for i, call in enumerate(apply_result.invocations)
        if "create-hosted-deployment-single-docker-artifact" in call
    )
    application_gets = [
        i
        for i, call in enumerate(apply_result.invocations)
        if "hosted-application" in call and "get" in call
    ]
    assert len(application_gets) >= 4
    assert all(i < create_index for i in application_gets)
    assert any(
        "hosted-deployment" in call and "get" in call
        for call in apply_result.invocations[create_index + 1 :]
    )


@pytest.mark.parametrize(
    ("case", "code", "message"),
    [
        ("application_failed", 1, "OutOfCapacity"),
        (
            "application_runtime_mismatch_after_active",
            20,
            "runtime environment differs",
        ),
        (
            "application_auth_mismatch_after_active",
            20,
            "different inbound authentication",
        ),
    ],
)
def test_application_resume_stops_before_create_on_failure(
    tmp_path: Path,
    case: str,
    code: int,
    message: str,
    release_runner: tuple[Path, list[str]],
) -> None:
    """A failed application or post-wait check prevents deployment creation."""
    result = run_release(tmp_path, case, True, release_runner)
    assert result.returncode == code, result.stderr
    assert message in result.stdout + result.stderr
    assert not mutating_commands(result)


@pytest.mark.parametrize(
    "case", ["unreadable_get_status", "unreadable_deletion_status"]
)
def test_unreadable_status_never_retries_or_completes_delete(
    tmp_path: Path, case: str, release_runner: tuple[Path, list[str]]
) -> None:
    """A string status in ServiceError is not a valid HTTP result."""
    options = (
        deploy_options(release_runner, "--replace-failed")
        if case == "unreadable_deletion_status"
        else []
    )
    result = run_release(tmp_path, case, True, release_runner, extra_options=options)
    assert result.returncode == 1, result.stderr
    assert "last error: HTTP unknown" in result.stderr
    assert "GET_RETRY" not in result.stdout
    assert "Hosted Deployment: DELETED" not in result.stdout
    assert mutating_commands(result) == (["delete"] if options else [])


def test_creating_application_with_deployment_stops_for_review(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """The resume path never creates a second deployment."""
    result = run_release(
        tmp_path, "application_creating_with_deployment", True, release_runner
    )
    assert result.returncode == 20
    assert "already has a deployment" in result.stderr
    assert not mutating_commands(result)


def test_fake_work_request_requires_compartment(tmp_path: Path) -> None:
    """The fake CLI enforces the real work-request list input contract."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    executable = write_fake_oci(fake_bin)
    scenario = tmp_path / "scenario.json"
    scenario.write_text(json.dumps(scenario_for("failed_deployment")), encoding="utf-8")
    environment = os.environ.copy()
    environment.update(
        OCI_RELEASE_SCENARIO=str(scenario),
        OCI_RELEASE_LOG=str(tmp_path / "oci.log"),
    )
    result = subprocess.run(
        [
            str(executable),
            "generative-ai",
            "work-request",
            "list",
            "--resource-id",
            "ocid1.test",
            "--status",
            "FAILED",
            "--all",
        ],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "--compartment-id" in result.stderr
