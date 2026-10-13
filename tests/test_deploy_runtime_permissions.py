"""
Author: L. Saetta
Date last modified: 2026-10-13
License: MIT
Description: Test the stop on missing runtime permissions (Spec 019) offline.
"""

import os
from pathlib import Path
import shutil

import pytest

from test_deploy_release_cases import (
    EXTRA_SCENARIOS,
    PWSH,
    POWERSHELL_SCRIPT,
    SCRIPT,
    mutating_commands,
    run_release,
)

IMAGE_ACCESS_ERROR = (
    "Generative AI application deployment failed because the container image "
    "could not be accessed or validated. Verify the OCI Container Registry image "
    "path and tag, required IAM policies, and vulnerability scan results, then "
    "try again."
)


def runtime_permission_scenarios() -> dict[str, dict[str, object]]:
    """Return the Spec 019 scenarios: failed deployments that cannot read the image.

    Returns:
        Scenario updates keyed by case name.
    """
    first = {"application_count": 0, "deployment_count": 0}
    image = {"work_error_code": "500", "work_error_message": IMAGE_ACCESS_ERROR}
    attention = {"deployment_states": ["CREATING", "NEEDS_ATTENTION"]}
    return {
        "first_release_image_access": {**first, **attention, **image},
        "first_release_image_access_failed": {
            **first,
            **image,
            "deployment_states": ["CREATING", "FAILED"],
        },
        "first_release_image_missing": {
            **first,
            **attention,
            **image,
            "image_exists": False,
        },
        "first_release_needs_attention_other": {**first, **attention},
        "first_release_image_access_secret": {
            **first,
            **attention,
            **image,
            "work_error_echo_runtime": True,
        },
        "existing_needs_attention_image_access": {
            "deployment_state": "NEEDS_ATTENTION",
            **image,
        },
        "existing_needs_attention_other": {"deployment_state": "NEEDS_ATTENTION"},
        "existing_failed_image_access": {"deployment_state": "FAILED", **image},
    }


EXTRA_SCENARIOS.update(runtime_permission_scenarios())


@pytest.fixture(
    name="release_runner",
    params=[
        pytest.param(
            (SCRIPT, [shutil.which("bash") or "/bin/bash"]),
            id="bash",
            marks=pytest.mark.skipif(
                os.name == "nt", reason="Bash fixtures use POSIX paths."
            ),
        ),
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


def creates(result) -> list[str]:
    """Return the deployment create commands recorded by the fake CLI.

    Args:
        result: Completed release run.

    Returns:
        Recorded deployment create command names.
    """
    return [
        name
        for name in mutating_commands(result)
        if name == "create-hosted-deployment-single-docker-artifact"
    ]


@pytest.mark.parametrize(
    ("case", "state", "next_step"),
    [
        (
            "first_release_image_access",
            "NEEDS_ATTENTION",
            "delete it in the OCI Console",
        ),
        (
            "first_release_image_access_failed",
            "FAILED",
            "the plan offers to replace the failed deployment",
        ),
    ],
)
def test_image_access_failure_stops_with_exit_27(
    tmp_path: Path,
    case: str,
    state: str,
    next_step: str,
    release_runner: tuple[Path, list[str]],
) -> None:
    """A first release whose runtime cannot read the image stops for the administrator."""
    result = run_release(tmp_path, case, True, release_runner)

    assert result.returncode == 27, result.stderr
    stderr = result.stderr
    assert (
        "Release stopped: the Hosted Deployment cannot read its image from OCIR."
        in (stderr)
    )
    assert "The image exists: fra.ocir.io/namespace/" in stderr
    assert "compartment test-compartment (ocid1.compartment.test)" in stderr
    assert "read repos in compartment test-compartment" in stderr
    assert "Do not create or change dynamic groups or policies." in stderr
    assert f"is {state}." in stderr
    assert next_step in stderr
    assert len(creates(result)) == 1


def test_image_access_failure_without_image_asks_for_push(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """When the tag is missing in OCIR, the message is about the push, not IAM."""
    result = run_release(tmp_path, "first_release_image_missing", True, release_runner)

    assert result.returncode == 1, result.stderr
    assert "is not in an OCIR repository of compartment test-compartment" in result.stderr
    assert "Push it with oci-agent-push to a repository of this compartment" in result.stderr
    assert "runtime permissions" not in result.stderr


def test_other_needs_attention_error_is_reported_without_iam_message(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """NEEDS_ATTENTION with another cause shows the OCI error and exits 1."""
    result = run_release(
        tmp_path, "first_release_needs_attention_other", True, release_runner
    )

    assert result.returncode == 1, result.stderr
    assert "is NEEDS_ATTENTION." in result.stderr
    assert "Node pool capacity unavailable" in result.stderr
    assert "Release stopped" not in result.stderr


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("existing_needs_attention_image_access", 27),
        ("existing_needs_attention_other", 20),
        ("existing_failed_image_access", 27),
    ],
)
def test_plan_on_failed_deployment_reports_cause_without_mutation(
    tmp_path: Path,
    case: str,
    expected_code: int,
    release_runner: tuple[Path, list[str]],
) -> None:
    """The read-only plan shows the cause and stops with the matching exit code."""
    result = run_release(tmp_path, case, False, release_runner)

    assert result.returncode == expected_code, result.stderr
    assert "OCI work request error" in result.stderr
    assert not mutating_commands(result)


def test_replacement_request_is_not_blocked_by_exit_27(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """With --replace-failed, the plan of a FAILED deployment still proceeds."""
    option = (
        "--replace-failed" if release_runner[0].suffix == ".sh" else "-ReplaceFailed"
    )
    result = run_release(
        tmp_path,
        "existing_failed_image_access",
        False,
        release_runner,
        extra_options=[option],
    )

    assert result.returncode == 0, result.stderr
    assert "Replace failed deployment" in result.stdout


def test_runtime_value_is_masked_in_the_image_access_error(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """A runtime value echoed by OCI is redacted in the reported errors."""
    secret = "super-secret-value"
    result = run_release(
        tmp_path,
        "first_release_image_access_secret",
        True,
        release_runner,
        runtime_value=secret,
    )

    assert result.returncode == 27, result.stderr
    error_lines = [
        line for line in result.stderr.splitlines() if "OCI work request error" in line
    ]
    assert error_lines
    assert all(secret not in line and "[REDACTED]" in line for line in error_lines)
    assert secret not in result.stderr.split("Release stopped", 1)[1]
