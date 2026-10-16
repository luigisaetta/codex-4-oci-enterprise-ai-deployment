"""
Author: L. Saetta
Date last modified: 2026-10-16
License: MIT
Description: Test the agent teardown (Spec 029) with a scenario-driven fake OCI CLI
and a fake container engine.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEARDOWN = ROOT / "scripts" / "teardown_agent.py"
BASH_WRAPPER = ROOT / "scripts" / "teardown_agent.sh"
PWSH = shutil.which("pwsh")
APP_ID = "ocid1.generativeaihostedapplication.test"
DEP_ID = "ocid1.generativeaihosteddeployment.test"
STORAGE_ID = "ocid1.generativeaiapplicationstorage.test"
REPO_ID = "ocid1.containerrepo.test"
REGISTRY_PATH = "fra.ocir.io/namespace/agents/teardown-test"
MUTATIONS = ("delete", "rmi")

FAKE_OCI = r"""#!/usr/bin/env python3
import json, os, sys
path = os.environ["FAKE_STATE"]
state = json.load(open(path, encoding="utf-8"))
args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(["oci", *args]) + "\n")

def save():
    json.dump(state, open(path, "w", encoding="utf-8"))

def out(value):
    print(json.dumps(value))
    sys.exit(0)

def error(status, code, message="failed"):
    print("ServiceError:", file=sys.stderr)
    print(json.dumps({"status": status, "code": code, "message": message}), file=sys.stderr)
    sys.exit(2)

def value(option):
    return args[args.index(option) + 1] if option in args else None

if "region" in args and "list" in args:
    out({"data": [{"name": "test-region", "key": "FRA"}]})
if "compartment" in args and "list" in args:
    out({"data": [{"id": "ocid1.compartment.test", "lifecycle-state": "ACTIVE"}]})
if "list-hosted-applications" in args:
    name = value("--display-name")
    items = [a for a in state["apps"] if name is None or a["display-name"] == name]
    out({"data": {"items": items}})
if "list-hosted-deployments" in args:
    owner = value("--application-id")
    out({"data": {"items": [d for d in state["deployments"] if d["app"] == owner]}})
if "hosted-deployment" in args and "get" in args:
    ident = value("--hosted-deployment-id")
    out({"data": next(d for d in state["deployments"] if d["id"] == ident)})
if "list-hosted-application-storages" in args:
    out({"data": {"items": state["storages"]}})
if "repository" in args and "list" in args:
    out({"data": {"items": state["repos"]}})
if "hosted-application" in args and "delete" in args:
    if state.get("reject_delete"):
        error(404, "NotAuthorizedOrNotFound", "Authorization failed")
    for app in state["apps"]:
        if app["id"] == value("--hosted-application-id"):
            app["lifecycle-state"] = "DELETING"
    save()
    out({"data": {}})
if "hosted-application" in args and "get" in args:
    ident = value("--hosted-application-id")
    app = next((a for a in state["apps"] if a["id"] == ident), None)
    if app is None:
        error(404, "NotFound")
    if app["lifecycle-state"] == "DELETING" and not state.get("never_finishes"):
        app["lifecycle-state"] = "DELETED"
        state["deployments"] = [d for d in state["deployments"] if d["app"] != ident]
        for storage in state["storages"]:
            storage["application-ids"] = [x for x in storage["application-ids"] if x != ident]
        save()
    out({"data": app})
if "hosted-application-storage" in args and "delete" in args:
    for storage in state["storages"]:
        storage["lifecycle-state"] = "DELETING"
    save()
    out({"data": {}})
if "hosted-application-storage" in args and "get" in args:
    storage = state["storages"][0]
    if storage["lifecycle-state"] == "DELETING":
        storage["lifecycle-state"] = "DELETED"
        save()
    out({"data": storage})
if "repository" in args and "delete" in args:
    if state.get("reject_repo_delete"):
        error(500, "InternalServerError")
    state["repos"] = []
    save()
    out({})
print("unexpected oci call", args, file=sys.stderr)
sys.exit(3)
"""

FAKE_DOCKER = r"""#!/usr/bin/env python3
import json, os, sys
path = os.environ["FAKE_STATE"]
state = json.load(open(path, encoding="utf-8"))
args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(["docker", *args]) + "\n")
if args[0] == "info":
    sys.exit(0 if state.get("docker_running", True) else 1)
if args[0] == "images":
    print("\n".join(state["images"]))
    sys.exit(0)
if args[0] == "rmi":
    if args[1] in state.get("images_in_use", []):
        print("conflict: image is being used by a running container", file=sys.stderr)
        sys.exit(1)
    state["images"] = [i for i in state["images"] if i != args[1]]
    json.dump(state, open(path, "w", encoding="utf-8"))
    sys.exit(0)
sys.exit(3)
"""


def base_state() -> dict:
    """Return an agent with application, deployment, storage, repo, and images."""
    return {
        "apps": [
            {"id": APP_ID, "display-name": "teardown-test", "lifecycle-state": "ACTIVE"}
        ],
        "deployments": [
            {
                "id": DEP_ID,
                "app": APP_ID,
                "lifecycle-state": "ACTIVE",
                "artifacts": [{"container-uri": REGISTRY_PATH, "tag": "0.1.0"}],
            }
        ],
        "storages": [
            {
                "id": STORAGE_ID,
                "display-name": "teardown-test-storage",
                "lifecycle-state": "ACTIVE",
                "application-ids": [APP_ID],
            }
        ],
        "repos": [
            {
                "id": REPO_ID,
                "display-name": "agents/teardown-test",
                "lifecycle-state": "AVAILABLE",
                "image-count": 2,
            }
        ],
        "images": [
            "teardown-test:0.1.0",
            f"{REGISTRY_PATH}:0.1.0",
            "other-agent:1.0.0",
        ],
    }


def write_manifest(directory: Path, storage: bool = True) -> Path:
    """Write a minimal manifest, with or without deploy.storage."""
    (directory / "agent").mkdir()
    (directory / "agent" / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    manifest = directory / "agent" / "agent.yaml"
    manifest.write_text(
        "schema_version: 2\n"
        "name: teardown-test\n"
        "build: {context: ., dockerfile: Dockerfile}\n"
        "publish: {repository: agents/teardown-test}\n"
        "deploy:\n"
        "  application_name: teardown-test\n"
        "  profile: public-noauth\n"
        + ("  storage: {type: ADB}\n" if storage else "")
        + "verify: []\n",
        encoding="utf-8",
    )
    return manifest


# The scenario runner keeps every input explicit for each test.
# pylint: disable=too-many-arguments,too-many-positional-arguments
def run_teardown(
    tmp_path: Path,
    state: dict,
    options: list[str],
    storage: bool = True,
    command: list[str] | None = None,
    manifest_flag: str = "--manifest",
) -> subprocess.CompletedProcess[str]:
    """Run the teardown with fake executables; attach the calls and final state."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    for name, source in (("oci", FAKE_OCI), ("docker", FAKE_DOCKER)):
        executable = fake_bin / name
        executable.write_text(source, encoding="utf-8")
        executable.chmod(0o755)
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    log_path = tmp_path / "calls.log"
    manifest = write_manifest(tmp_path, storage)
    environment = os.environ.copy()
    environment.update(
        PATH=f"{fake_bin}{os.pathsep}{environment['PATH']}",
        OCI_AGENT_ENV_FILE=str(tmp_path / "missing.env"),
        OCI_AGENT_PYTHON=sys.executable,
        OCI_REGION="test-region",
        OCI_COMPARTMENT_NAME="test-compartment",
        OCIR_TENANCY_NAMESPACE="namespace",
        OCI_DEPLOY_POLL_INTERVAL="0",
        FAKE_STATE=str(state_path),
        FAKE_LOG=str(log_path),
    )
    result = subprocess.run(
        [
            *(command or [sys.executable, str(TEARDOWN)]),
            manifest_flag,
            str(manifest),
            *options,
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    result.calls = (
        [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        if log_path.exists()
        else []
    )
    result.state = json.loads(state_path.read_text(encoding="utf-8"))
    return result


def mutations(result) -> list[list[str]]:
    """Return the recorded calls that delete or remove something."""
    return [call for call in result.calls if any(word in call for word in MUTATIONS)]


APPLY = ["--apply", "--confirm", "teardown-test"]


def test_plan_lists_everything_and_never_mutates(tmp_path: Path) -> None:
    """The plan shows each target and the kept resources, with no deletion."""
    result = run_teardown(tmp_path, base_state(), ["--plan"])

    assert result.returncode == 0, result.stderr
    assert not mutations(result)
    assert (
        f"Hosted Application: teardown-test ({APP_ID}; ACTIVE): delete" in result.stdout
    )
    assert "delete with the application" in result.stdout
    assert "teardown-test-storage" in result.stdout
    assert "its data is lost" in result.stdout
    assert "2 image(s) are lost" in result.stdout
    assert f"{REGISTRY_PATH}:0.1.0, teardown-test:0.1.0" in result.stdout
    assert "other-agent" not in result.stdout
    assert "Kept, never touched: IAM policies" in result.stdout


@pytest.mark.parametrize(
    "options", [["--apply"], ["--apply", "--confirm", "other-name"]]
)
def test_apply_requires_the_exact_confirmation(tmp_path: Path, options) -> None:
    """A missing or different --confirm stops before any OCI call."""
    result = run_teardown(tmp_path, base_state(), options)

    assert result.returncode == 64
    assert "--confirm teardown-test" in result.stderr
    assert not result.calls


def test_full_teardown_removes_everything_in_order(tmp_path: Path) -> None:
    """Application, storage, repository, then local images; others untouched."""
    result = run_teardown(tmp_path, base_state(), APPLY)

    assert result.returncode == 0, result.stderr
    deletes = [call for call in mutations(result) if call[0] == "oci"]
    assert [call[6] for call in deletes] == [
        "hosted-application",
        "hosted-application-storage",
        "container",
    ]
    assert result.state["apps"][0]["lifecycle-state"] == "DELETED"
    assert result.state["storages"][0]["lifecycle-state"] == "DELETED"
    assert result.state["repos"] == []
    assert result.state["images"] == ["other-agent:1.0.0"]
    assert "Teardown complete for teardown-test." in result.stdout


def test_rerun_reports_nothing_to_delete(tmp_path: Path) -> None:
    """When everything is gone, the teardown says so and changes nothing."""
    state = base_state()
    state.update(apps=[], deployments=[], storages=[], repos=[], images=[])
    result = run_teardown(tmp_path, state, APPLY)

    assert result.returncode == 0, result.stderr
    assert "Nothing to delete" in result.stdout
    assert not mutations(result)


def test_without_storage_section_no_storage_is_touched(tmp_path: Path) -> None:
    """A manifest without deploy.storage never lists or deletes a storage."""
    result = run_teardown(tmp_path, base_state(), APPLY, storage=False)

    assert result.returncode == 0, result.stderr
    assert not any("list-hosted-application-storages" in c for c in result.calls)
    assert result.state["storages"][0]["lifecycle-state"] == "ACTIVE"


def test_repository_used_by_another_application_is_kept(tmp_path: Path) -> None:
    """The repository stays when another application deploys its images."""
    state = base_state()
    state["apps"].append(
        {"id": "ocid1.other", "display-name": "other-app", "lifecycle-state": "ACTIVE"}
    )
    state["deployments"].append(
        {
            "id": "ocid1.otherdep",
            "app": "ocid1.other",
            "lifecycle-state": "ACTIVE",
            "artifacts": [{"container-uri": REGISTRY_PATH, "tag": "0.2.0"}],
        }
    )
    result = run_teardown(tmp_path, state, APPLY)

    assert result.returncode == 0, result.stderr
    assert "keep - used by other-app" in result.stdout
    assert result.state["repos"], "the repository must be kept"


def test_storage_linked_to_another_application_is_kept(tmp_path: Path) -> None:
    """A storage linked to another application is reported and kept."""
    state = base_state()
    state["storages"][0]["application-ids"] = ["ocid1.another"]
    result = run_teardown(tmp_path, state, APPLY)

    assert result.returncode == 0, result.stderr
    assert "keep - linked to another application" in result.stdout
    assert result.state["storages"][0]["lifecycle-state"] == "ACTIVE"


@pytest.mark.parametrize(
    ("resource", "index", "state_name"),
    [
        ("apps", 0, "CREATING"),
        ("deployments", 0, "UPDATING"),
        ("storages", 0, "CREATING"),
    ],
)
def test_busy_states_stop_before_any_deletion(
    tmp_path: Path, resource: str, index: int, state_name: str
) -> None:
    """A resource that OCI is still changing stops the teardown with exit 20."""
    state = base_state()
    state[resource][index]["lifecycle-state"] = state_name
    result = run_teardown(tmp_path, state, APPLY)

    assert result.returncode == 20
    assert not mutations(result)


def test_permission_error_stops_with_the_iam_rule(tmp_path: Path) -> None:
    """NotAuthorizedOrNotFound on a delete stops with the administrator message."""
    state = base_state()
    state["reject_delete"] = True
    result = run_teardown(tmp_path, state, APPLY)

    assert result.returncode == 1
    assert "NotAuthorizedOrNotFound" in result.stderr
    assert "done by your tenancy administrator" in result.stderr
    assert result.state["repos"], "nothing after the failure may be deleted"


def test_partial_failure_reports_progress_and_rerun_finishes(tmp_path: Path) -> None:
    """A failure after some deletions says what was deleted; a rerun completes."""
    state = base_state()
    state["reject_repo_delete"] = True
    (tmp_path / "first").mkdir()
    first = run_teardown(tmp_path / "first", state, APPLY)

    assert first.returncode == 1
    assert "Deleted before the failure" in first.stderr
    assert "Run the teardown again to continue." in first.stderr
    rerun_state = first.state
    rerun_state.pop("reject_repo_delete")
    (tmp_path / "second").mkdir()
    second = run_teardown(tmp_path / "second", rerun_state, APPLY)
    assert second.returncode == 0, second.stderr
    assert second.state["repos"] == []


def test_wait_timeout_exits_26(tmp_path: Path) -> None:
    """An application that stays DELETING past the timeout gives exit 26."""
    state = base_state()
    state["never_finishes"] = True
    result = run_teardown(tmp_path, state, [*APPLY, "--timeout-seconds", "1"])

    assert result.returncode == 26
    assert "Run the teardown again to resume waiting." in result.stderr


def test_image_in_use_is_kept_and_reported(tmp_path: Path) -> None:
    """An image used by a container stays; the rest of the teardown completes."""
    state = base_state()
    state["images_in_use"] = ["teardown-test:0.1.0"]
    result = run_teardown(tmp_path, state, APPLY)

    assert result.returncode == 0, result.stderr
    assert "were kept (in use or not removable): teardown-test:0.1.0" in result.stdout
    assert "teardown-test:0.1.0" in result.state["images"]


def test_engine_unavailable_gives_a_warning(tmp_path: Path) -> None:
    """Without a running engine the OCI steps run and the images are reported."""
    state = base_state()
    state["docker_running"] = False
    result = run_teardown(tmp_path, state, [*APPLY, "--container-engine", "docker"])

    assert result.returncode == 0, result.stderr
    assert "no container engine was available" in result.stdout
    assert result.state["repos"] == []


@pytest.mark.skipif(os.name == "nt", reason="Bash fixtures use POSIX paths.")
def test_bash_wrapper_runs_the_same_teardown(tmp_path: Path) -> None:
    """The Bash wrapper passes the arguments through and keeps the exit code."""
    bash = shutil.which("bash") or "/bin/bash"
    result = run_teardown(
        tmp_path, base_state(), ["--plan"], command=[bash, str(BASH_WRAPPER)]
    )

    assert result.returncode == 0, result.stderr
    assert "Mode: plan" in result.stdout


@pytest.mark.skipif(PWSH is None, reason="pwsh is unavailable.")
def test_powershell_wrapper_runs_the_same_teardown(tmp_path: Path) -> None:
    """The PowerShell wrapper maps its parameters to the same teardown."""
    wrapper = ROOT / "scripts" / "teardown_agent.ps1"
    result = run_teardown(
        tmp_path,
        base_state(),
        ["-Plan"],
        command=[PWSH, "-NoProfile", "-File", str(wrapper)],
        manifest_flag="-Manifest",
    )

    assert result.returncode == 0, result.stderr
    assert "Mode: plan" in result.stdout
