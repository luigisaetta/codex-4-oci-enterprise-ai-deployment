#!/usr/bin/env python3
"""
Author: L. Saetta
Date last modified: 2026-10-16
License: MIT
Description: Plan or apply the complete removal of one agent (Spec 029): Hosted
Application and deployment, managed storage, OCIR repository, local images.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Any

if __package__:
    from . import agent_manifest, tool_config
else:
    # Direct script execution puts scripts/ on sys.path.
    import agent_manifest  # pylint: disable=import-error
    import tool_config  # pylint: disable=import-error

EXIT_FAILURE = 1
EXIT_REVIEW = 20
EXIT_STILL_DELETING = 26
EXIT_INVALID_INPUT = 64
EXIT_REGION_NOT_FOUND = 65
TENANCY_KEYS = ("OCI_REGION", "OCI_COMPARTMENT_NAME", "OCIR_TENANCY_NAMESPACE")
BUSY_STATES = {"CREATING", "UPDATING"}
KEPT_RESOURCES = (
    "IAM policies and dynamic groups (tenancy administrator)",
    "the identity-domain confidential application",
    "OCI Vault secrets",
    "the Generative AI project",
    "the agent folder and its files",
)
IAM_RULE = (
    "If OCI reports NotAuthorizedOrNotFound, a permission is missing. This is "
    "tenancy IAM setup, done by your tenancy administrator. Do not create or "
    "change dynamic groups or policies."
)


class TeardownError(Exception):
    """A failure that stops the teardown with an exit code."""

    def __init__(self, message: str, code: int = EXIT_FAILURE) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Target:
    """One resource of the agent and the action planned for it."""

    kind: str
    name: str
    ocid: str = ""
    state: str = ""
    action: str = "not found"
    detail: str = ""


# One field per resource kind keeps the plan readable.
@dataclass
class Plan:  # pylint: disable=too-many-instance-attributes
    """Everything the teardown would remove, and what it keeps."""

    compartment_id: str
    registry_path: str
    application: Target
    deployment: Target
    storage: Target | None
    repository: Target
    images: dict[str, list[str]] = field(default_factory=dict)
    engines_unavailable: bool = False
    notes: list[str] = field(default_factory=list)

    def has_work(self) -> bool:
        """Return whether any OCI resource or local image would be removed."""
        targets = [self.application, self.repository]
        if self.storage is not None:
            targets.append(self.storage)
        return any(t.action in {"delete", "wait"} for t in targets) or any(
            self.images.values()
        )


def setting(key: str) -> str:
    """Return a tenancy setting: the environment first, then the tool's .env."""
    return os.environ.get(key, "").strip() or tool_config.configured_value(key).strip()


def service_error(stderr: str) -> dict[str, Any]:
    """Parse the JSON ServiceError that the OCI CLI prints on failure."""
    marker = stderr.find("ServiceError:")
    if marker < 0:
        return {}
    try:
        return json.loads(stderr[marker + len("ServiceError:") :].strip())
    except ValueError:
        return {}


class Oci:
    """Minimal OCI CLI runner that returns parsed JSON."""

    def __init__(self, region: str) -> None:
        self.region = region

    def run(self, *arguments: str, allow_404: bool = False) -> Any:
        """Run one OCI CLI command; return its JSON output, or None on a 404.

        Raises:
            TeardownError: If the command fails, with the selected ServiceError
                fields and, for permission errors, the IAM rule.
        """
        command = ["oci", "--region", self.region, "--output", "json", *arguments]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return json.loads(result.stdout) if result.stdout.strip() else {}
        error = service_error(result.stderr)
        if allow_404 and error.get("status") == 404:
            return None
        summary = (
            f"status={error.get('status', 'unknown')}; "
            f"code={error.get('code', 'unknown')}; "
            f"message={error.get('message', 'see the OCI CLI error')}"
        )
        message = f"OCI request failed ({' '.join(arguments[:2])}): {summary}."
        if error.get("code") == "NotAuthorizedOrNotFound":
            message += "\n" + IAM_RULE
        raise TeardownError(message)

    def items(self, *arguments: str) -> list[dict[str, Any]]:
        """Return the non-deleted items of a list command."""
        data = (self.run(*arguments, "--all") or {}).get("data") or {}
        listed = data.get("items", []) if isinstance(data, dict) else data
        return [item for item in listed if item.get("lifecycle-state") != "DELETED"]


def ocir_registry(oci: Oci) -> str:
    """Resolve the OCIR endpoint of the region, as resolve_ocir_registry.sh does."""
    regions = (oci.run("iam", "region", "list", "--all") or {}).get("data") or []
    for region in regions:
        if region.get("name") == oci.region and region.get("key"):
            return f"{region['key'].lower()}.ocir.io"
    raise TeardownError(
        f"OCI_REGION was not found by the configured OCI CLI profile: {oci.region}",
        EXIT_REGION_NOT_FOUND,
    )


def compartment_id(oci: Oci, name: str) -> str:
    """Return the OCID of the only active compartment with the given name."""
    found = (
        oci.run(
            "iam",
            "compartment",
            "list",
            "--name",
            name,
            "--compartment-id-in-subtree",
            "true",
            "--all",
        )
        or {}
    ).get("data") or []
    active = [item for item in found if item.get("lifecycle-state") == "ACTIVE"]
    if len(active) != 1:
        raise TeardownError(
            f'Expected exactly one active compartment named "{name}"; '
            f"found {len(active)}."
        )
    return active[0]["id"]


def find_application(oci: Oci, compartment: str, name: str) -> tuple[Target, Target]:
    """Find the application and its deployment, and plan their deletion."""
    application = Target("Hosted Application", name)
    deployment = Target("Hosted Deployment", "", action="none")
    found = oci.items(
        "generative-ai",
        "hosted-application-collection",
        "list-hosted-applications",
        "--compartment-id",
        compartment,
        "--display-name",
        name,
    )
    if len(found) > 1:
        raise TeardownError(
            f'Expected zero or one non-deleted Hosted Application named "{name}"; '
            f"found {len(found)}.",
            EXIT_REVIEW,
        )
    if not found:
        return application, deployment
    application.ocid = found[0]["id"]
    application.state = found[0].get("lifecycle-state", "")
    application.action = "wait" if application.state == "DELETING" else "delete"
    deployments = oci.items(
        "generative-ai",
        "hosted-deployment-collection",
        "list-hosted-deployments",
        "--compartment-id",
        compartment,
        "--application-id",
        application.ocid,
    )
    if deployments:
        deployment.ocid = deployments[0]["id"]
        deployment.state = deployments[0].get("lifecycle-state", "")
        deployment.action = "delete with the application"
    if application.state in BUSY_STATES or deployment.state in BUSY_STATES:
        raise TeardownError(
            f"The Hosted Application is {application.state} and its deployment is "
            f"{deployment.state or 'absent'}; wait until OCI finishes, "
            "then plan again.",
            EXIT_REVIEW,
        )
    return application, deployment


def find_storage(oci: Oci, compartment: str, name: str, application_id: str) -> Target:
    """Find the managed storage of the manifest and plan its deletion."""
    storage = Target("Managed storage", name)
    found = oci.items(
        "generative-ai",
        "hosted-application-storage-collection",
        "list-hosted-application-storages",
        "--compartment-id",
        compartment,
        "--display-name",
        name,
    )
    if len(found) > 1:
        raise TeardownError(
            f'Expected zero or one non-deleted managed storage named "{name}"; '
            f"found {len(found)}.",
            EXIT_REVIEW,
        )
    if not found:
        return storage
    storage.ocid = found[0]["id"]
    storage.state = found[0].get("lifecycle-state", "")
    links = [link for link in found[0].get("application-ids") or [] if link]
    if storage.state in BUSY_STATES:
        raise TeardownError(
            f"The managed storage is {storage.state}; wait until OCI finishes, "
            "then plan again.",
            EXIT_REVIEW,
        )
    if links and links != [application_id]:
        storage.action = "keep"
        storage.detail = "linked to another application: " + ", ".join(links)
    elif storage.state == "DELETING":
        storage.action = "wait"
    else:
        storage.action = "delete"
        storage.detail = "its data is lost"
    return storage


def repository_users(oci: Oci, compartment: str, uri: str, own_id: str) -> list[str]:
    """Return the names of other applications whose artifacts use the repository."""
    users = []
    applications = oci.items(
        "generative-ai",
        "hosted-application-collection",
        "list-hosted-applications",
        "--compartment-id",
        compartment,
    )
    for application in applications:
        if application["id"] == own_id:
            continue
        deployments = oci.items(
            "generative-ai",
            "hosted-deployment-collection",
            "list-hosted-deployments",
            "--compartment-id",
            compartment,
            "--application-id",
            application["id"],
        )
        for deployment in deployments:
            data = (
                oci.run(
                    "generative-ai",
                    "hosted-deployment",
                    "get",
                    "--hosted-deployment-id",
                    deployment["id"],
                )
                or {}
            ).get("data") or {}
            artifacts = [
                *(data.get("artifacts") or []),
                data.get("active-artifact") or {},
            ]
            if any(artifact.get("container-uri") == uri for artifact in artifacts):
                users.append(application.get("display-name", application["id"]))
                break
    return users


def find_repository(oci: Oci, compartment: str, name: str) -> Target:
    """Find the OCIR repository of the manifest in the compartment."""
    repository = Target("OCIR repository", name)
    found = oci.items(
        "artifacts",
        "container",
        "repository",
        "list",
        "--compartment-id",
        compartment,
        "--display-name",
        name,
    )
    if not found:
        return repository
    repository.ocid = found[0]["id"]
    repository.state = found[0].get("lifecycle-state", "")
    repository.action = "delete"
    repository.detail = f"{found[0].get('image-count', 'unknown')} image(s) are lost"
    return repository


def usable_engines(selected: str) -> list[str]:
    """Return the container engines whose CLI is on PATH and whose engine runs."""
    candidates = ["docker", "podman"] if selected == "auto" else [selected]
    usable = []
    for engine in candidates:
        if not shutil.which(engine):
            continue
        check = subprocess.run(
            [engine, "info"], capture_output=True, text=True, check=False
        )
        if check.returncode == 0:
            usable.append(engine)
    return usable


def local_images(engine: str, repositories: set[str]) -> list[str]:
    """Return the local image references of the agent for one engine."""
    listed = subprocess.run(
        [engine, "images", "--format", "{{.Repository}}:{{.Tag}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    references = []
    for line in listed.stdout.splitlines():
        repository, _, tag = line.strip().rpartition(":")
        if repository in repositories and tag and tag != "<none>":
            references.append(line.strip())
    return sorted(set(references))


def build_plan(oci: Oci, manifest: dict[str, Any], engine: str) -> Plan:
    """Resolve every target read-only and decide its action."""
    settings = {key: setting(key) for key in TENANCY_KEYS}
    compartment = compartment_id(oci, settings["OCI_COMPARTMENT_NAME"])
    repository_name = manifest["publish"]["repository"]
    registry_path = (
        f"{ocir_registry(oci)}/{settings['OCIR_TENANCY_NAMESPACE']}/{repository_name}"
    )
    application, deployment = find_application(
        oci, compartment, manifest["deploy"]["application_name"]
    )
    storage = None
    if manifest["deploy"].get("storage") is not None:
        storage = find_storage(
            oci,
            compartment,
            agent_manifest.storage_config(manifest)["display_name"],
            application.ocid,
        )
    repository = find_repository(oci, compartment, repository_name)
    plan = Plan(
        compartment, registry_path, application, deployment, storage, repository
    )
    if repository.action == "delete":
        users = repository_users(oci, compartment, registry_path, application.ocid)
        if users:
            repository.action = "keep"
            repository.detail = "used by " + ", ".join(users)
    plan.notes.append(
        "Applications in other compartments that may pull images of this "
        "repository cannot be checked."
    )
    collect_images(plan, engine, {manifest["name"], registry_path})
    return plan


def collect_images(plan: Plan, engine: str, repositories: set[str]) -> None:
    """Record the local images of the agent for every usable engine."""
    engines = usable_engines(engine)
    plan.engines_unavailable = not engines
    for name in engines:
        plan.images[name] = local_images(name, repositories)


def describe(target: Target) -> str:
    """Return one plan line for a target."""
    if not target.ocid:
        return f"{target.kind}: {target.name or '-'}: not found (nothing to delete)"
    detail = f" - {target.detail}" if target.detail else ""
    label = f"{target.name} " if target.name else ""
    return (
        f"{target.kind}: {label}({target.ocid}; {target.state}): "
        f"{target.action}{detail}"
    )


def print_plan(plan: Plan, apply: bool) -> None:
    """Print the plan: one line per target, warnings, and the kept resources."""
    print(f"Mode: {'apply' if apply else 'plan'}")
    print(f"Compartment: {plan.compartment_id}")
    print(describe(plan.application))
    if plan.deployment.ocid:
        print(describe(plan.deployment))
    if plan.storage is not None:
        print(describe(plan.storage))
    print(describe(plan.repository))
    for engine, references in plan.images.items():
        listed = ", ".join(references) if references else "none found"
        print(f"Local images ({engine}): {listed}")
    if plan.engines_unavailable:
        print("Local images: no container engine is available; they are not removed.")
    print("Kept, never touched: " + "; ".join(KEPT_RESOURCES) + ".")
    for note in plan.notes:
        print(f"Note: {note}")
    if plan.storage is not None and plan.storage.action == "delete":
        print("Warning: deleting the managed storage loses its data permanently.")
    if plan.repository.action == "delete":
        print("Warning: deleting the repository loses all its images.")


def wait_deleted(oci: Oci, kind: str, command: list[str], timeout: int) -> None:
    """Poll a get command until the resource is DELETED or answers 404.

    Raises:
        TeardownError: With exit 26 when the timeout expires.
    """
    interval = int(os.environ.get("OCI_DEPLOY_POLL_INTERVAL", "30"))
    start = time.monotonic()
    while True:
        elapsed = int(time.monotonic() - start)
        response = oci.run(*command, allow_404=True)
        state = (
            "DELETED"
            if response is None
            else (response.get("data") or {}).get("lifecycle-state", "UNKNOWN")
        )
        print(f"{kind}: {state} (elapsed {elapsed}s)")
        if state == "DELETED":
            return
        if elapsed >= timeout:
            raise TeardownError(
                f"{kind} is still {state} after {elapsed}s; OCI continues the "
                "deletion. Run the teardown again to resume waiting.",
                EXIT_STILL_DELETING,
            )
        time.sleep(interval)


def delete_application(oci: Oci, target: Target, timeout: int) -> None:
    """Delete the application (and its deployment) and wait for DELETED."""
    if target.action == "delete":
        oci.run(
            "generative-ai",
            "hosted-application",
            "delete",
            "--hosted-application-id",
            target.ocid,
            "--force",
        )
    get = ["generative-ai", "hosted-application", "get", "--hosted-application-id"]
    wait_deleted(oci, target.kind, [*get, target.ocid], timeout)


def delete_storage(oci: Oci, target: Target, timeout: int) -> None:
    """Delete the managed storage and wait for DELETED."""
    if target.action == "delete":
        oci.run(
            "generative-ai",
            "hosted-application-storage",
            "delete",
            "--hosted-application-storage-id",
            target.ocid,
            "--force",
        )
    get = [
        "generative-ai",
        "hosted-application-storage",
        "get",
        "--hosted-application-storage-id",
    ]
    wait_deleted(oci, target.kind, [*get, target.ocid], timeout)


def remove_images(plan: Plan) -> list[str]:
    """Remove the local images; return the references that were kept."""
    kept = []
    for engine, references in plan.images.items():
        for reference in references:
            result = subprocess.run(
                [engine, "rmi", reference], capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                print(f"Removed local image ({engine}): {reference}")
            else:
                kept.append(f"{reference} ({engine})")
    return kept


def apply_plan(oci: Oci, plan: Plan, timeout: int) -> None:
    """Delete the planned resources in order; report what is left on failure."""
    done: list[str] = []
    steps = [(plan.application, delete_application)]
    if plan.storage is not None:
        steps.append((plan.storage, delete_storage))
    try:
        for target, action in steps:
            if target.action in {"delete", "wait"}:
                action(oci, target, timeout)
                done.append(f"{target.kind} {target.ocid}")
        if plan.repository.action == "delete":
            oci.run(
                "artifacts",
                "container",
                "repository",
                "delete",
                "--repository-id",
                plan.repository.ocid,
                "--force",
            )
            print(f"Deleted OCIR repository: {plan.repository.name}")
            done.append(f"{plan.repository.kind} {plan.repository.ocid}")
    except TeardownError as error:
        if done:
            error.args = (f"{error}\nDeleted before the failure: {'; '.join(done)}.",)
        error.args = (f"{error}\nRun the teardown again to continue.",)
        raise
    kept = remove_images(plan)
    if kept:
        print(
            "Warning: these local images were kept (in use or not removable): "
            + ", ".join(kept)
        )
    if plan.engines_unavailable:
        print(
            "Warning: no container engine was available. Remove the local images "
            "later with: docker images, then docker rmi <image>."
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description="Plan or apply an agent teardown.")
    parser.add_argument("--manifest", required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument(
        "--container-engine", choices=("auto", "docker", "podman"), default="auto"
    )
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    return parser


def run(arguments: list[str] | None = None) -> int:
    """Run the teardown command-line interface and return its exit code."""
    options = build_parser().parse_args(arguments)
    try:
        manifest = agent_manifest.load_manifest(options.manifest)
        name = manifest["deploy"]["application_name"]
        if options.apply and options.confirm != name:
            raise TeardownError(
                f"--apply requires --confirm {name} (the exact application name).",
                EXIT_INVALID_INPUT,
            )
        if options.timeout_seconds < 1:
            raise TeardownError(
                "--timeout-seconds must be positive.", EXIT_INVALID_INPUT
            )
        missing = [key for key in TENANCY_KEYS if not setting(key)]
        if missing:
            raise TeardownError(
                "Missing tenancy settings: " + ", ".join(missing), EXIT_INVALID_INPUT
            )
        if not shutil.which("oci"):
            raise TeardownError("Missing required tool: oci")
        oci = Oci(setting("OCI_REGION"))
        plan = build_plan(oci, manifest, options.container_engine)
        print_plan(plan, options.apply)
        if not plan.has_work():
            print("Nothing to delete: every resource of this agent is already gone.")
            return 0
        if not options.apply:
            print(
                "Plan complete. Re-run with --apply --confirm "
                f"{name} only after explicit authorization."
            )
            return 0
        apply_plan(oci, plan, options.timeout_seconds)
        print(f"Teardown complete for {name}.")
        return 0
    except agent_manifest.ManifestError as error:
        print(f"Manifest error: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except TeardownError as error:
        print(str(error), file=sys.stderr)
        return error.code


if __name__ == "__main__":
    raise SystemExit(run())
