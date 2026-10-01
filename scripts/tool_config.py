#!/usr/bin/env python3
"""
Author: L. Saetta
Date last modified: 2026-10-01
License: MIT
Description: Read the non-secret tenancy configuration for OCI agent scripts.
"""

import argparse
import os
import sys
from pathlib import Path

ALLOWED_KEYS = {
    "OCI_REGION",
    "OCI_COMPARTMENT_NAME",
    "OCIR_TENANCY_NAMESPACE",
    "OCIR_USERNAME",
}


def configuration_file() -> Path:
    """Return the selected tenancy configuration file path.

    Returns:
        Path from OCI_AGENT_ENV_FILE or the tool home's .env file.
    """
    selected = os.environ.get("OCI_AGENT_ENV_FILE")
    if selected:
        return Path(selected)
    return Path(__file__).resolve().parent.parent / ".env"


def unquote(value: str) -> str:
    """Remove one matching pair of surrounding single or double quotes.

    Args:
        value: Trimmed value read from a configuration line.

    Returns:
        The value without one matching surrounding quote pair.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def read_configuration(path: Path) -> dict[str, str]:
    """Read allowed non-secret keys from a KEY=VALUE configuration file.

    Args:
        path: Configuration file to parse.

    Returns:
        Parsed allowed keys and values, or an empty mapping when absent.
    """
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", maxsplit=1)
        key = key.strip()
        if key in ALLOWED_KEYS:
            values[key] = unquote(value.strip())
    return values


def configuration_issues(file_values: dict[str, str]) -> tuple[list[str], list[str]]:
    """Identify incomplete effective tenancy settings without exposing values.

    Non-empty environment values take precedence over file values, matching
    the lifecycle scripts. Empty effective values are treated as missing.

    Args:
        file_values: Allowed settings returned by read_configuration.

    Returns:
        Sorted missing key names and sorted placeholder key names.
    """
    missing: list[str] = []
    placeholders: list[str] = []
    for key in sorted(ALLOWED_KEYS):
        value = os.environ.get(key) or file_values.get(key, "")
        if not value:
            missing.append(key)
        elif value.startswith("replace-with-"):
            placeholders.append(key)
    return missing, placeholders


def emit_environment(keys: list[str]) -> int:
    """Print requested file-backed values after checking required settings.

    Args:
        keys: Allowed tenancy keys requested by the calling script.

    Returns:
        Zero when all requested settings are available, otherwise 64.
    """
    unknown = sorted(set(keys) - ALLOWED_KEYS)
    if unknown:
        print(
            f"Unsupported configuration key(s): {', '.join(unknown)}", file=sys.stderr
        )
        return 64
    path = configuration_file()
    try:
        file_values = read_configuration(path)
    except UnicodeDecodeError:
        print(f"Configuration file is not valid UTF-8: {path}", file=sys.stderr)
        return 64
    missing = [
        key for key in keys if not os.environ.get(key) and key not in file_values
    ]
    if missing:
        print(
            f"Missing configuration key(s): {', '.join(missing)}; file: {path}",
            file=sys.stderr,
        )
        return 64
    for key in keys:
        if not os.environ.get(key) and key in file_values:
            print(f"{key}={file_values[key]}")
    return 0


def main() -> int:
    """Run the tenancy configuration command-line interface.

    Returns:
        Process exit code for the requested subcommand.
    """
    parser = argparse.ArgumentParser(description="Read OCI agent tenancy settings.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    environment_parser = subparsers.add_parser("env")
    environment_parser.add_argument("--keys", nargs="+", required=True)
    args = parser.parse_args()
    return emit_environment(args.keys)


if __name__ == "__main__":
    raise SystemExit(main())
