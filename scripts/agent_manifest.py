#!/usr/bin/env python3
"""
Author: L. Saetta
Date last modified: 2026-09-30
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
from urllib.parse import urlparse

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


def is_within(path: Path, root: Path) -> bool:
    """Return whether a resolved path is inside a resolved root.

    Args:
        path: Canonical path to inspect.
        root: Canonical allowed root.

    Returns:
        True when path is root or one of its descendants.
    """
    return root in (path, *path.parents)


def find_allowed_roots(manifest_path: Path) -> list[Path]:
    """Find canonical roots permitted for a manifest and its build inputs.

    Args:
        manifest_path: Canonical path to the manifest file.

    Returns:
        Canonical allowed root directories.

    Raises:
        ManifestError: If OCI_AGENT_ALLOWED_ROOTS contains an invalid entry.
    """
    configured_roots = os.environ.get("OCI_AGENT_ALLOWED_ROOTS")
    if configured_roots is not None:
        roots = [Path(value) for value in configured_roots.split(os.pathsep) if value]
        if not roots or any(
            not root.is_absolute() or not root.is_dir() for root in roots
        ):
            raise ManifestError(
                "OCI_AGENT_ALLOWED_ROOTS must contain absolute existing directories."
            )
        return [root.resolve() for root in roots]

    for parent in (manifest_path.parent, *manifest_path.parent.parents):
        if (parent / ".git").exists():
            return [parent]
    return [manifest_path.parent]


def validate_path(
    value: Any,
    location: str,
    manifest_directory: Path,
    allowed_roots: list[Path],
    require_file: bool,
) -> str:
    """Validate a manifest-relative build path and return its canonical location.

    Args:
        value: Path value from the manifest.
        location: Human-readable schema location.
        manifest_directory: Canonical directory containing the manifest.
        allowed_roots: Canonical directories that may contain the path.
        require_file: Whether the path must identify a file instead of a directory.

    Returns:
        Absolute canonical path as a string.

    Raises:
        ManifestError: If the path is invalid, missing, or outside the allowed roots.
    """
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{location} must be a non-empty relative path.")
    candidate = Path(value)
    if candidate.is_absolute():
        raise ManifestError(f"{location} must be relative to the manifest directory.")
    resolved = (manifest_directory / candidate).resolve()
    if not any(is_within(resolved, root) for root in allowed_roots):
        roots = ", ".join(str(root) for root in allowed_roots)
        raise ManifestError(f"{location} must stay inside allowed root(s): {roots}")
    if require_file and not resolved.is_file():
        raise ManifestError(f"{location} is not a file: {value}")
    if not require_file and not resolved.is_dir():
        raise ManifestError(f"{location} is not a directory: {value}")
    return str(resolved)


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


def validate_auth_text(value: Any, location: str) -> str:
    """Validate a non-empty authentication value without whitespace.

    Args:
        value: Authentication field value from the manifest.
        location: Human-readable schema location.

    Returns:
        The validated value.

    Raises:
        ManifestError: If the value is empty, not text, or contains whitespace.
    """
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        raise ManifestError(
            f"{location} must be a non-empty string without whitespace."
        )
    return value


def validate_domain_url(value: Any) -> str:
    """Validate the identity-domain URL accepted by OCI inbound authentication.

    Args:
        value: Domain URL from ``manifest.deploy.auth``.

    Returns:
        The validated URL.

    Raises:
        ManifestError: If the URL is not an HTTPS origin with an optional port.
    """
    location = "manifest.deploy.auth.domain_url"
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{location} must be a non-empty HTTPS URL.")
    if "?" in value or "#" in value:
        raise ManifestError(f"{location} must not contain a query or fragment marker.")
    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ManifestError(
            f"{location} must be a valid HTTPS URL with an optional port."
        ) from error
    has_valid_origin = (
        parsed.scheme == "https"
        and hostname
        and not any(char.isspace() for char in hostname)
        and parsed.username is None
        and parsed.password is None
    )
    has_unsupported_parts = any(
        (
            parsed.path not in {"", "/"},
            bool(parsed.params),
            bool(parsed.query),
            bool(parsed.fragment),
            port is not None and not 0 < port <= 65535,
        )
    )
    if not has_valid_origin or has_unsupported_parts:
        raise ManifestError(
            f"{location} must be an HTTPS URL with a host, optional port, and no path, "
            "query, fragment, or user info."
        )
    return value


def validate_deploy_auth(value: Any) -> dict[str, str]:
    """Validate identity-domain inbound authentication configuration.

    Args:
        value: ``manifest.deploy.auth`` object.

    Returns:
        The validated authentication object.

    Raises:
        ManifestError: If the authentication settings violate the manifest contract.
    """
    location = "manifest.deploy.auth"
    auth = require_object(value, location)
    fail_unknown_keys(auth, {"domain_url", "audience", "scope"}, location)
    return {
        "domain_url": validate_domain_url(auth.get("domain_url")),
        "audience": validate_auth_text(auth.get("audience"), f"{location}.audience"),
        "scope": validate_auth_text(auth.get("scope"), f"{location}.scope"),
    }


def validate_deploy(value: Any) -> dict[str, Any]:
    """Validate deployment settings, including the selected public access profile.

    Args:
        value: ``manifest.deploy`` object.

    Returns:
        The validated deployment object.

    Raises:
        ManifestError: If deployment settings violate the manifest contract.
    """
    deploy = require_object(value, "manifest.deploy")
    fail_unknown_keys(
        deploy, {"application_name", "profile", "auth"}, "manifest.deploy"
    )
    if not isinstance(deploy.get("application_name"), str) or not NAME.fullmatch(
        deploy["application_name"]
    ):
        raise ManifestError(
            "manifest.deploy.application_name contains unsupported characters."
        )
    profile = deploy.get("profile")
    if profile not in {"public-noauth", "public-idcs"}:
        raise ManifestError(
            "manifest.deploy.profile must be public-noauth or public-idcs."
        )
    if profile == "public-idcs":
        if "auth" not in deploy:
            raise ManifestError("manifest.deploy.auth is required for public-idcs.")
        deploy["auth"] = validate_deploy_auth(deploy["auth"])
    elif "auth" in deploy:
        raise ManifestError("manifest.deploy.auth is not supported for public-noauth.")
    return deploy


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
        manifest_path: Absolute path or a path relative to the current directory.

    Returns:
        The validated manifest mapping.

    Raises:
        ManifestError: If the file or its contents violate the schema.
    """
    resolved_manifest = Path(manifest_path).resolve()
    if not resolved_manifest.is_file():
        raise ManifestError(f"Manifest file is unavailable: {manifest_path}")
    allowed_roots = find_allowed_roots(resolved_manifest)
    if not any(is_within(resolved_manifest, root) for root in allowed_roots):
        roots = ", ".join(str(root) for root in allowed_roots)
        raise ManifestError(f"Manifest must stay inside allowed root(s): {roots}")
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
    if manifest.get("schema_version") == 1:
        raise ManifestError(
            "manifest.schema_version 1 is unsupported: build paths are now relative "
            "to the manifest directory; update schema_version to 2."
        )
    if manifest.get("schema_version") != 2:
        raise ManifestError("manifest.schema_version must be 2.")
    if not isinstance(manifest.get("name"), str) or not NAME.fullmatch(
        manifest["name"]
    ):
        raise ManifestError("manifest.name contains unsupported characters.")
    build = require_object(manifest.get("build"), "manifest.build")
    fail_unknown_keys(build, {"context", "dockerfile"}, "manifest.build")
    build["context"] = validate_path(
        build.get("context"),
        "manifest.build.context",
        resolved_manifest.parent,
        allowed_roots,
        False,
    )
    build["dockerfile"] = validate_path(
        build.get("dockerfile"),
        "manifest.build.dockerfile",
        resolved_manifest.parent,
        allowed_roots,
        True,
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
    manifest["deploy"] = validate_deploy(manifest.get("deploy"))
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
    if manifest["deploy"]["profile"] == "public-idcs":
        auth = manifest["deploy"]["auth"]
        values.update(
            {
                "deploy.auth.domain_url": auth["domain_url"],
                "deploy.auth.audience": auth["audience"],
                "deploy.auth.scope": auth["scope"],
            }
        )
    elif field.startswith("deploy.auth."):
        raise ManifestError(
            f"{field} is unavailable because the public-noauth profile "
            "has no auth section."
        )
    if field not in values:
        raise ManifestError(f"Unsupported manifest field: {field}")
    return values[field]


def inbound_auth_config(manifest: dict[str, Any]) -> dict[str, Any]:
    """Build OCI inbound-authentication JSON from a validated manifest.

    Args:
        manifest: Validated agent manifest.

    Returns:
        OCI inbound authentication configuration.
    """
    if manifest["deploy"]["profile"] == "public-noauth":
        return {"inboundAuthConfigType": "NO_AUTH_CONFIG"}
    auth = manifest["deploy"]["auth"]
    return {
        "inboundAuthConfigType": "IDCS_AUTH_CONFIG",
        "idcsConfig": {
            "domainUrl": auth["domain_url"],
            "scope": auth["scope"],
            "audience": auth["audience"],
        },
    }


def inbound_auth_matches(manifest: dict[str, Any], payload: dict[str, Any]) -> bool:
    """Compare a Hosted Application inbound configuration to the manifest.

    Args:
        manifest: Validated agent manifest.
        payload: Raw JSON returned by ``hosted-application get``.

    Returns:
        True when the supported inbound authentication fields match exactly.
    """
    data = payload.get("data")
    if not isinstance(data, dict):
        return False
    observed = data.get("inbound-auth-config")
    if not isinstance(observed, dict):
        return False
    expected = inbound_auth_config(manifest)
    if observed.get("inboundAuthConfigType") != expected["inboundAuthConfigType"]:
        return False
    if manifest["deploy"]["profile"] == "public-noauth":
        return True
    observed_idcs = observed.get("idcsConfig")
    if not isinstance(observed_idcs, dict):
        return False
    expected_idcs = expected["idcsConfig"]
    return all(
        observed_idcs.get(field) == expected_idcs[field]
        for field in ("domainUrl", "scope", "audience")
    )


def print_runtime_environment(manifest: dict[str, Any], output_format: str) -> None:
    """Print resolved runtime environment variables in a requested format.

    Args:
        manifest: Validated agent manifest.
        output_format: Runtime environment output format requested by the CLI.
    """
    local = output_format.startswith("local-")
    if output_format.endswith("json"):
        variables, _ = resolve_runtime_environment(manifest, local)
        print(json.dumps(variables, separators=(",", ":")))
    else:
        print(runtime_report(manifest, local))


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
    inbound_auth_parser = subparsers.add_parser("inbound-auth")
    inbound_auth_parser.add_argument("--manifest", required=True)
    inbound_matches_parser = subparsers.add_parser("inbound-auth-matches")
    inbound_matches_parser.add_argument("--manifest", required=True)
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
            print_runtime_environment(manifest, args.format)
        elif args.command in {"runtime-matches", "inbound-auth-matches"}:
            matcher = (
                runtime_matches
                if args.command == "runtime-matches"
                else inbound_auth_matches
            )
            if not matcher(manifest, json.load(sys.stdin)):
                return 1
        elif args.command == "inbound-auth":
            print(json.dumps(inbound_auth_config(manifest), separators=(",", ":")))
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
