#!/usr/bin/env python3
"""
Author: L. Saetta
Date last modified: 2026-09-23
License: MIT
Description: Validate and expose the versioned agent deployment manifest.
"""

import argparse
import json
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
        {"schema_version", "name", "build", "publish", "deploy", "verify"},
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
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
        if args.command == "validate":
            print(f"Manifest valid: {args.manifest}")
        elif args.command == "get":
            print(value_for_path(manifest, args.field))
        elif args.command == "checks":
            print(json.dumps(manifest["verify"], separators=(",", ":")))
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
