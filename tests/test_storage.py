"""
Author: L. Saetta
Date last modified: 2026-10-14
License: MIT
Description: Test managed ADB storage at Hosted Application creation (Spec 026).
"""

# The release fixtures follow test_scaling.py on purpose, section by section.
# pylint: disable=duplicate-code

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import test_deploy_release_cases as release_cases
from scripts.agent_manifest import (
    ManifestError,
    load_manifest,
    storage_config,
    storage_configs,
    storage_matches,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TOOL = ROOT / "scripts" / "agent_manifest.py"
STORAGE = "  storage: {type: ADB}\n"
STORAGE_ID = "ocid1.generativeaiapplicationstorage.oc1.test"
STORAGE_NAME = "release-test-storage"


def manifest_with(directory: Path, storage: str, runtime: str = "") -> Path:
    """Write a minimal manifest with an optional deploy.storage line.

    Args:
        directory: Folder for the manifest and its Dockerfile.
        storage: YAML line for ``deploy.storage``, or an empty string.
        runtime: Optional YAML ``runtime`` block.

    Returns:
        Path to the manifest.
    """
    directory.mkdir()
    (directory / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    manifest = directory / "agent.yaml"
    manifest.write_text(
        "schema_version: 2\n"
        "name: storage-test\n"
        "build: {context: ., dockerfile: Dockerfile}\n"
        "publish: {repository: agents/storage-test}\n"
        "deploy:\n"
        "  application_name: storage-test\n"
        "  profile: public-noauth\n"
        f"{storage}"
        f"{runtime}"
        "verify: []\n",
        encoding="utf-8",
    )
    return manifest


def run_manifest_tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the manifest command-line tool without raising on failure."""
    return subprocess.run(
        [sys.executable, str(MANIFEST_TOOL), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def test_storage_section_defaults_the_connect_variable(tmp_path: Path) -> None:
    """A section with only the type gets DB_CONNECT_STRING and a derived name."""
    manifest = load_manifest(str(manifest_with(tmp_path / "agent", STORAGE)))

    assert storage_config(manifest) == {
        "type": "ADB",
        "connect_env": "DB_CONNECT_STRING",
        "display_name": "storage-test-storage",
    }
    assert storage_configs(manifest, STORAGE_ID) == [
        {"environmentVariableKey": "DB_CONNECT_STRING", "storageId": STORAGE_ID}
    ]


def test_without_storage_nothing_is_configured(tmp_path: Path) -> None:
    """Without the section there is no storage, and only storage-free apps match."""
    manifest = load_manifest(str(manifest_with(tmp_path / "agent", "")))

    assert storage_config(manifest) is None
    assert storage_matches(manifest, {"data": {"storage-configs": None}})
    assert storage_matches(manifest, {"data": {"storage-configs": []}})
    assert not storage_matches(
        manifest,
        {"data": {"storage-configs": [{"environment-variable-key": "X"}]}},
    )
    with pytest.raises(ManifestError):
        storage_configs(manifest, STORAGE_ID)


@pytest.mark.parametrize(
    ("storage", "runtime"),
    [
        ("  storage: {type: POSTGRESQL}\n", ""),
        ("  storage: {}\n", ""),
        ("  storage: {type: ADB, connect_env: db_url}\n", ""),
        ("  storage: {type: ADB, connect_env: OCI_REGION}\n", ""),
        ("  storage: {type: ADB, connect_env: OCIR_USERNAME}\n", ""),
        ("  storage: {type: ADB, connect_env: PATH}\n", ""),
        ("  storage: {type: ADB, size: 20}\n", ""),
        ("  storage: ADB\n", ""),
        (
            "  storage: {type: ADB, connect_env: GENAI_MODEL}\n",
            "runtime:\n  env:\n    - {name: GENAI_MODEL, value: model}\n",
        ),
    ],
)
def test_invalid_storage_is_rejected(
    tmp_path: Path, storage: str, runtime: str
) -> None:
    """Other types, bad or reserved names, collisions, unknown fields exit 64."""
    manifest = manifest_with(tmp_path / "agent", storage, runtime)
    result = run_manifest_tool("validate", "--manifest", str(manifest))

    assert result.returncode == 64
    assert "manifest.deploy.storage" in result.stderr


def test_storage_matches_compares_the_variable(tmp_path: Path) -> None:
    """An existing application must have exactly one storage with the same variable."""
    manifest = load_manifest(
        str(
            manifest_with(
                tmp_path / "agent", "  storage: {type: ADB, connect_env: ORDERS_DB}\n"
            )
        )
    )
    same = [{"environment-variable-key": "ORDERS_DB", "storage-id": STORAGE_ID}]
    other = [
        {"environment-variable-key": "DB_CONNECT_STRING", "storage-id": STORAGE_ID}
    ]

    assert storage_matches(manifest, {"data": {"storage-configs": same}})
    assert not storage_matches(manifest, {"data": {"storage-configs": other}})
    assert not storage_matches(manifest, {"data": {"storage-configs": same * 2}})
    assert not storage_matches(manifest, {"data": {}})


def test_storage_commands_print_json_or_nothing(tmp_path: Path) -> None:
    """The CLI helpers print the JSON only when the section exists."""
    with_storage = manifest_with(tmp_path / "with", STORAGE)
    without = manifest_with(tmp_path / "without", "")

    config = run_manifest_tool("storage-config", "--manifest", str(with_storage))
    assert json.loads(config.stdout)["display_name"] == "storage-test-storage"
    assert run_manifest_tool("storage-config", "--manifest", str(without)).stdout == ""
    configs = run_manifest_tool(
        "storage-configs", "--manifest", str(with_storage), "--storage-id", STORAGE_ID
    )
    assert json.loads(configs.stdout)[0]["storageId"] == STORAGE_ID
    invalid = run_manifest_tool(
        "storage-configs", "--manifest", str(with_storage), "--storage-id", "bad"
    )
    assert invalid.returncode == 64


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


@pytest.fixture(name="storage_manifest")
def storage_manifest_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the shared release runner write a manifest with deploy.storage."""
    original = release_cases.write_manifest

    def write(directory: Path, profile: str = "public-noauth") -> Path:
        manifest = original(directory, profile)
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            text.replace(f"  profile: {profile}\n", f"  profile: {profile}\n{STORAGE}"),
            encoding="utf-8",
        )
        return manifest

    monkeypatch.setattr(release_cases, "write_manifest", write)


@pytest.fixture(name="scenario")
def scenario_fixture():
    """Register temporary scenarios and remove them after the test."""
    names: list[str] = []

    def register(name: str, values: dict[str, object]) -> str:
        release_cases.EXTRA_SCENARIOS[name] = {
            "application_count": 0,
            "deployment_count": 0,
            **values,
        }
        names.append(name)
        return name

    yield register
    for name in names:
        release_cases.EXTRA_SCENARIOS.pop(name, None)


def create_arguments(result, command: str) -> list[str]:
    """Return the arguments of the first recorded create call of a command.

    Args:
        result: Completed release run.
        command: ``hosted-application`` or ``hosted-application-storage``.

    Returns:
        The create call arguments.
    """
    return next(
        invocation
        for invocation in result.invocations
        if command in invocation and "create" in invocation
    )


def storage_item(state: str = "ACTIVE", links: list[str] | None = None) -> dict:
    """Return one storage list item of the fake OCI CLI."""
    return {
        "id": STORAGE_ID,
        "display-name": STORAGE_NAME,
        "lifecycle-state": state,
        "application-ids": links or [],
    }


@pytest.mark.usefixtures("storage_manifest")
def test_first_release_creates_and_links_the_storage(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """The storage is created first, then linked at application creation."""
    result = release_cases.run_release(tmp_path, "first_release", True, release_runner)

    assert result.returncode == 0, result.stderr
    storage_create = create_arguments(result, "hosted-application-storage")
    assert storage_create[storage_create.index("--display-name") + 1] == STORAGE_NAME
    assert storage_create[storage_create.index("--storage-type") + 1] == "ADB"
    arguments = create_arguments(result, "hosted-application")
    sent = json.loads(arguments[arguments.index("--storage-configs") + 1])
    assert sent == [
        {
            "environmentVariableKey": "DB_CONNECT_STRING",
            "storageId": "ocid1.generativeaiapplicationstorage.created",
        }
    ]
    assert "Storage: ADB, connect string in DB_CONNECT_STRING" in result.stdout
    assert f"Storage action: create {STORAGE_NAME}" in result.stdout
    assert "Created managed storage" in result.stdout


@pytest.mark.usefixtures("storage_manifest")
def test_orphaned_storage_is_reused(
    tmp_path: Path, release_runner: tuple[Path, list[str]], scenario
) -> None:
    """An ACTIVE storage without applications is reused, not duplicated."""
    case = scenario("storage_orphan", {"storages": [storage_item()]})
    result = release_cases.run_release(tmp_path, case, True, release_runner)

    assert result.returncode == 0, result.stderr
    assert not any(
        "hosted-application-storage" in invocation and "create" in invocation
        for invocation in result.invocations
    )
    arguments = create_arguments(result, "hosted-application")
    sent = json.loads(arguments[arguments.index("--storage-configs") + 1])
    assert sent[0]["storageId"] == STORAGE_ID
    assert "Storage action: reuse" in result.stdout


@pytest.mark.usefixtures("storage_manifest")
@pytest.mark.parametrize(
    ("storages", "message"),
    [
        ([storage_item(links=["ocid1.generativeaihostedapplication.other"])], "linked"),
        ([storage_item(state="CREATING")], "cannot be reused"),
        ([storage_item(), storage_item()], "zero or one non-deleted managed storage"),
    ],
)
def test_unusable_storage_stops_without_mutation(
    tmp_path: Path,
    release_runner: tuple[Path, list[str]],
    scenario,
    storages: list[dict],
    message: str,
) -> None:
    """A linked, busy, or duplicated storage stops with exit 20 and no mutation."""
    case = scenario("storage_unusable", {"storages": storages})
    result = release_cases.run_release(tmp_path, case, True, release_runner)

    assert result.returncode == 20
    assert message in result.stderr
    assert not release_cases.mutating_commands(result)


def test_without_storage_no_storage_call_is_made(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """Without deploy.storage the release is unchanged."""
    result = release_cases.run_release(tmp_path, "first_release", True, release_runner)

    assert result.returncode == 0, result.stderr
    assert not any(
        any("storage" in argument for argument in invocation)
        for invocation in result.invocations
    )
    assert "Storage: none" in result.stdout


@pytest.mark.usefixtures("storage_manifest")
def test_plan_does_not_create_the_storage(
    tmp_path: Path, release_runner: tuple[Path, list[str]]
) -> None:
    """The plan lists storages read-only and announces the creation."""
    result = release_cases.run_release(tmp_path, "first_release", False, release_runner)

    assert result.returncode == 0, result.stderr
    assert not release_cases.mutating_commands(result)
    assert f"Storage action: create {STORAGE_NAME}" in result.stdout
    assert "takes several minutes" in result.stdout


@pytest.mark.usefixtures("storage_manifest")
def test_existing_application_without_storage_stops(
    tmp_path: Path, release_runner: tuple[Path, list[str]], scenario
) -> None:
    """Storage cannot be added to an existing application."""
    case = scenario(
        "existing_without_storage", {"application_count": 1, "deployment_count": 1}
    )
    result = release_cases.run_release(tmp_path, case, False, release_runner)

    assert result.returncode == 20
    assert "storage differs from the manifest" in result.stderr
    assert "starts with an empty database" in result.stderr
    assert not release_cases.mutating_commands(result)


def test_existing_application_with_storage_needs_the_section(
    tmp_path: Path, release_runner: tuple[Path, list[str]], scenario
) -> None:
    """A manifest without storage cannot reuse an application that has one."""
    case = scenario(
        "existing_with_storage",
        {
            "application_count": 1,
            "deployment_count": 1,
            "storage_configs": [
                {
                    "environment-variable-key": "DB_CONNECT_STRING",
                    "storage-id": STORAGE_ID,
                }
            ],
        },
    )
    result = release_cases.run_release(tmp_path, case, False, release_runner)

    assert result.returncode == 20
    assert "storage differs from the manifest" in result.stderr


@pytest.mark.usefixtures("storage_manifest")
def test_new_version_keeps_the_linked_storage(
    tmp_path: Path, release_runner: tuple[Path, list[str]], scenario
) -> None:
    """A matching application releases a new version without storage calls."""
    case = scenario(
        "new_version_with_storage",
        {
            **release_cases.scenario_for("new_version"),
            "storage_configs": [
                {
                    "environment-variable-key": "DB_CONNECT_STRING",
                    "storage-id": STORAGE_ID,
                }
            ],
        },
    )
    result = release_cases.run_release(tmp_path, case, True, release_runner)

    assert result.returncode == 0, result.stderr
    assert "linked to the existing application; data is kept" in result.stdout
    assert not any(
        "list-hosted-application-storages" in invocation
        for invocation in result.invocations
    )


@pytest.mark.usefixtures("storage_manifest")
@pytest.mark.parametrize("rejection", ["reject_storage_list", "reject_storage_create"])
def test_storage_permission_errors_stop_with_the_iam_rule(
    tmp_path: Path, release_runner: tuple[Path, list[str]], scenario, rejection: str
) -> None:
    """A NotAuthorizedOrNotFound on storage stops with the administrator message."""
    case = scenario("storage_rejected", {rejection: True})
    result = release_cases.run_release(tmp_path, case, True, release_runner)

    assert result.returncode == 1
    assert "NotAuthorizedOrNotFound" in result.stderr
    assert "done by your tenancy administrator" in result.stderr
    assert not any(
        "hosted-application" in invocation and "create" in invocation
        for invocation in result.invocations
    )
