#!/usr/bin/env python3
"""
Author: L. Saetta
Date last modified: 2026-09-23
License: MIT
Description: Validate and expose the versioned agent deployment manifest.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

SEMVER = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$"
)
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
REPOSITORY = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")
ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
VAULT_SECRET_ID = re.compile(r"^ocid1\.vaultsecret\.oc1\.[A-Za-z0-9._-]+$")
RESERVED_ENVIRONMENT_NAMES = {"PATH", "HOME", "PYTHONPATH"}
SENSITIVE_ENVIRONMENT_TOKENS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "APIKEY",
    "API_KEY",
    "PRIVATE_KEY",
)


class ManifestError(ValueError):
    """Raised when an agent manifest does not meet the supported contract."""


def fail_unknown_keys(value: dict[str, Any], allowed: set[str], location: str) -> None:
    """Reject keys outside a schema object.

    Args:
        value: Object to validate.
        allowed: Allowed key names.
        location: Human-readable schema location.

    Raises:
        ManifestError: If an unknown key is present.
    """
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ManifestError(
            f"{location} has unsupported field(s): {', '.join(unknown)}"
        )


def require_object(value: Any, location: str) -> dict[str, Any]:
    """Return a mapping or raise a useful manifest validation error."""
    if not isinstance(value, dict):
        raise ManifestError(f"{location} must be an object.")
    return value


def validate_path(
    value: Any, location: str, repository_root: Path, require_file: bool
) -> str:
    """Validate a checkout-root-relative path and confirm its expected type."""
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{location} must be a non-empty relative path.")
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ManifestError(f"{location} must stay below the repository root.")
    resolved = (repository_root / candidate).resolve()
    if repository_root not in (resolved, *resolved.parents):
        raise ManifestError(f"{location} must stay below the repository root.")
    if require_file and not resolved.is_file():
        raise ManifestError(f"{location} is not a file: {value}")
    if not require_file and not resolved.is_dir():
        raise ManifestError(f"{location} is not a directory: {value}")
    return value


def validate_check(value: Any, index: int) -> dict[str, Any]:
    """Validate one functional HTTP check from a manifest."""
    location = f"verify[{index}]"
    check = require_object(value, location)
    fail_unknown_keys(
        check, {"method", "path", "body", "expect_status", "expect_json"}, location
    )
    method = check.get("method")
    path = check.get("path")
    status = check.get("expect_status")
    if method not in {"GET", "POST"}:
        raise ManifestError(f"{location}.method must be GET or POST.")
    if (
        not isinstance(path, str)
        or not path.startswith("/")
        or path.startswith("//")
        or ".." in path
    ):
        raise ManifestError(f"{location}.path must be a safe absolute path.")
    if (
        not isinstance(status, int)
        or isinstance(status, bool)
        or not 100 <= status <= 599
    ):
        raise ManifestError(f"{location}.expect_status must be an HTTP status integer.")
    if method == "GET" and "body" in check:
        raise ManifestError(f"{location}.body is supported only for POST checks.")
    if "expect_json" in check and not isinstance(check["expect_json"], dict):
        raise ManifestError(f"{location}.expect_json must be an object.")
    return check


def validate_runtime_variable(value: Any, index: int) -> dict[str, Any]:
    """Validate one runtime environment variable declaration."""
    location = f"manifest.runtime.env[{index}]"
    variable = require_object(value, location)
    fail_unknown_keys(
        variable, {"name", "value", "from_env", "vault_secret_id"}, location
    )
    name = variable.get("name")
    if not isinstance(name, str) or not ENVIRONMENT_NAME.fullmatch(name):
        raise ManifestError(f"{location}.name must match ^[A-Z][A-Z0-9_]*$.")
    if name in RESERVED_ENVIRONMENT_NAMES:
        raise ManifestError(f"{location}.name is reserved: {name}.")
    sources = [
        key for key in ("value", "from_env", "vault_secret_id") if key in variable
    ]
    if len(sources) != 1:
        raise ManifestError(f"{location} must define exactly one value source.")
    source = sources[0]
    source_value = variable[source]
    if (
        not isinstance(source_value, str)
        or not source_value
        or "\n" in source_value
        or "\r" in source_value
    ):
        raise ManifestError(
            f"{location}.{source} must be a non-empty single-line string."
        )
    if source == "value" and any(
        token in name for token in SENSITIVE_ENVIRONMENT_TOKENS
    ):
        raise ManifestError(
            f"{location}.value is forbidden for sensitive-looking name {name}."
        )
    if source == "from_env" and not ENVIRONMENT_NAME.fullmatch(source_value):
        raise ManifestError(f"{location}.from_env must name an environment variable.")
    if source == "vault_secret_id" and not VAULT_SECRET_ID.fullmatch(source_value):
        raise ManifestError(
            f"{location}.vault_secret_id must be an OCI Vault secret OCID."
        )
    return variable


def validate_runtime(value: Any) -> dict[str, Any]:
    """Validate optional runtime configuration."""
    if value is None:
        return {"env": []}
    runtime = require_object(value, "manifest.runtime")
    fail_unknown_keys(runtime, {"env"}, "manifest.runtime")
    variables = runtime.get("env", [])
    if not isinstance(variables, list):
        raise ManifestError("manifest.runtime.env must be a list.")
    validated = [
        validate_runtime_variable(variable, index)
        for index, variable in enumerate(variables)
    ]
    if len({variable["name"] for variable in validated}) != len(validated):
        raise ManifestError("manifest.runtime.env names must be unique.")
    return {"env": validated}


def resolve_runtime_environment(
    manifest: dict[str, Any], local: bool
) -> tuple[list[dict[str, str]], list[str]]:
    """Resolve runtime variables for OCI or local Docker execution."""
    resolved: list[dict[str, str]] = []
    skipped: list[str] = []
    for variable in manifest["runtime"]["env"]:
        name = variable["name"]
        if "value" in variable:
            resolved.append(
                {"name": name, "type": "PLAINTEXT", "value": variable["value"]}
            )
        elif "from_env" in variable:
            source = variable["from_env"]
            source_value = os.environ.get(source)
            if not source_value:
                raise ManifestError(
                    f"Runtime environment source is undefined: {source}."
                )
            if "\n" in source_value or "\r" in source_value:
                raise ManifestError(
                    f"Runtime environment source contains line breaks: {source}."
                )
            resolved.append({"name": name, "type": "PLAINTEXT", "value": source_value})
        elif local:
            override = f"OCI_AGENT_VAULT_{name}"
            override_value = os.environ.get(override)
            if not override_value:
                skipped.append(name)
            elif "\n" in override_value or "\r" in override_value:
                raise ManifestError(
                    f"Local Vault override contains line breaks: {override}."
                )
            else:
                resolved.append(
                    {"name": name, "type": "PLAINTEXT", "value": override_value}
                )
        else:
            resolved.append(
                {"name": name, "type": "VAULT", "value": variable["vault_secret_id"]}
            )
    return resolved, skipped


def runtime_report(manifest: dict[str, Any], local: bool) -> str:
    """Format a safe source report without printing Vault values."""
    _, skipped = resolve_runtime_environment(manifest, local)
    lines = []
    for variable in manifest["runtime"]["env"]:
        name = variable["name"]
        if "value" in variable:
            lines.append(
                f"Runtime environment: {name} source=value value={variable['value']}"
            )
        elif "from_env" in variable:
            source_name = variable["from_env"]
            lines.append(
                f"Runtime environment: {name} source=from_env "
                f"value={os.environ[source_name]}"
            )
        elif local and name in skipped:
            lines.append(
                f"Runtime environment: {name} source=vault skipped "
                f"(set OCI_AGENT_VAULT_{name} to override locally)"
            )
        elif local:
            lines.append(f"Runtime environment: {name} source=vault local_override")
        else:
            lines.append(f"Runtime environment: {name} source=vault")
    return "\n".join(lines)


def runtime_matches(manifest: dict[str, Any], payload: dict[str, Any]) -> bool:
    """Compare OCI application runtime variables with the resolved manifest."""
    expected, _ = resolve_runtime_environment(manifest, local=False)
    observed = payload.get("data", {}).get("environment-variables") or []
    if not isinstance(observed, list):
        return False

    def normalize(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            (
                {
                    "name": item.get("name"),
                    "type": item.get("type"),
                    "value": item.get("value"),
                }
                for item in items
            ),
            key=lambda item: item["name"] or "",
        )

    return normalize(expected) == normalize(observed)


def load_manifest(manifest_path: str) -> dict[str, Any]:
    """Load and strictly validate a manifest.

    Args:
        manifest_path: Path supplied by the operator, relative to the checkout.

    Returns:
        The validated manifest mapping.

    Raises:
        ManifestError: If the file or its contents violate the schema.
    """
    repository_root = Path(__file__).resolve().parent.parent
    candidate = Path(manifest_path)
    if candidate.is_absolute():
        raise ManifestError("Manifest path must be relative to the repository root.")
    resolved_manifest = (repository_root / candidate).resolve()
    if (
        repository_root not in (resolved_manifest, *resolved_manifest.parents)
        or not resolved_manifest.is_file()
    ):
        raise ManifestError(f"Manifest file is unavailable: {manifest_path}")
    try:
        with resolved_manifest.open(encoding="utf-8") as manifest_file:
            loaded = yaml.safe_load(manifest_file)
    except yaml.YAMLError as error:
        raise ManifestError(f"Manifest YAML is invalid: {error}") from error
    manifest = require_object(loaded, "manifest")
    fail_unknown_keys(
        manifest,
        {"schema_version", "name", "build", "publish", "deploy", "runtime", "verify"},
        "manifest",
    )
    if manifest.get("schema_version") != 1:
        raise ManifestError("manifest.schema_version must be 1.")
    if not isinstance(manifest.get("name"), str) or not NAME.fullmatch(
        manifest["name"]
    ):
        raise ManifestError("manifest.name contains unsupported characters.")
    build = require_object(manifest.get("build"), "manifest.build")
    fail_unknown_keys(build, {"context", "dockerfile"}, "manifest.build")
    build["context"] = validate_path(
        build.get("context"), "manifest.build.context", repository_root, False
    )
    build["dockerfile"] = validate_path(
        build.get("dockerfile"), "manifest.build.dockerfile", repository_root, True
    )
    publish = require_object(manifest.get("publish"), "manifest.publish")
    fail_unknown_keys(publish, {"repository"}, "manifest.publish")
    repository = publish.get("repository")
    if (
        not isinstance(repository, str)
        or not REPOSITORY.fullmatch(repository)
        or "//" in repository
    ):
        raise ManifestError("manifest.publish.repository is invalid.")
    deploy = require_object(manifest.get("deploy"), "manifest.deploy")
    fail_unknown_keys(deploy, {"application_name", "profile"}, "manifest.deploy")
    if not isinstance(deploy.get("application_name"), str) or not NAME.fullmatch(
        deploy["application_name"]
    ):
        raise ManifestError(
            "manifest.deploy.application_name contains unsupported characters."
        )
    if deploy.get("profile") != "public-noauth":
        raise ManifestError("manifest.deploy.profile must be public-noauth.")
    manifest["runtime"] = validate_runtime(manifest.get("runtime"))
    checks = manifest.get("verify")
    if not isinstance(checks, list):
        raise ManifestError("manifest.verify must be a list.")
    manifest["verify"] = [
        validate_check(check, index) for index, check in enumerate(checks)
    ]
    return manifest


def value_for_path(manifest: dict[str, Any], field: str) -> Any:
    """Read a supported scalar field from a validated manifest."""
    values: dict[str, Any] = {
        "name": manifest["name"],
        "build.context": manifest["build"]["context"],
        "build.dockerfile": manifest["build"]["dockerfile"],
        "publish.repository": manifest["publish"]["repository"],
        "deploy.application_name": manifest["deploy"]["application_name"],
        "deploy.profile": manifest["deploy"]["profile"],
    }
    if field not in values:
        raise ManifestError(f"Unsupported manifest field: {field}")
    return values[field]


def main() -> int:
    """Run the manifest command-line interface."""
    parser = argparse.ArgumentParser(description="Validate an OCI agent manifest.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--manifest", required=True)
    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("--manifest", required=True)
    get_parser.add_argument("--field", required=True)
    checks_parser = subparsers.add_parser("checks")
    checks_parser.add_argument("--manifest", required=True)
    deployment_parser = subparsers.add_parser("deployment-name")
    deployment_parser.add_argument("--manifest", required=True)
    deployment_parser.add_argument("--tag", required=True)
    runtime_parser = subparsers.add_parser("runtime-env")
    runtime_parser.add_argument("--manifest", required=True)
    runtime_parser.add_argument(
        "--format",
        choices={"oci-json", "report", "local-json", "local-report"},
        required=True,
    )
    matches_parser = subparsers.add_parser("runtime-matches")
    matches_parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        if args.command == "validate":
            print(f"Manifest valid: {args.manifest}")
        elif args.command == "get":
            print(value_for_path(manifest, args.field))
        elif args.command == "checks":
            print(json.dumps(manifest["verify"], separators=(",", ":")))
        elif args.command == "runtime-env":
            local = args.format.startswith("local-")
            if args.format.endswith("json"):
                variables, _ = resolve_runtime_environment(manifest, local)
                print(json.dumps(variables, separators=(",", ":")))
            else:
                print(runtime_report(manifest, local))
        elif args.command == "runtime-matches":
            if not runtime_matches(manifest, json.load(sys.stdin)):
                return 1
        else:
            if not SEMVER.fullmatch(args.tag):
                raise ManifestError("Tag must be semantic (MAJOR.MINOR.PATCH).")
            print(
                f"{manifest['deploy']['application_name']}-{args.tag.replace('.', '-')}"
            )
    except ManifestError as error:
        print(f"Manifest error: {error}", file=sys.stderr)
        return 64
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
