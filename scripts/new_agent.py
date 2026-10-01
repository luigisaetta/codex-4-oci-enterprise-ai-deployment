#!/usr/bin/env python3
"""
Author: L. Saetta
Date last modified: 2026-10-01
License: MIT
Description: Plan agent files, render fixed templates, and check local inputs offline.
"""

import argparse
import fnmatch
import json
import keyword
import re
import sys
from pathlib import Path

if __package__:
    from . import agent_manifest, tool_config
else:
    # Direct script execution puts scripts/ on sys.path.
    import agent_manifest  # pylint: disable=import-error
    import tool_config  # pylint: disable=import-error

TOOL_HOME = Path(__file__).resolve().parent.parent
ASSETS = TOOL_HOME / "skills" / "oci-agent-build" / "assets"
EXIT_CONFLICT = 30
EXIT_CONFIGURATION = 31
EXIT_INVALID_INPUT = 64
GITIGNORE = "__pycache__/\n*.py[cod]\n.pytest_cache/\n.venv/\n.env\n.env.*\n"


class ArgumentParser(argparse.ArgumentParser):
    """Use the project's invalid-input exit code for argument errors."""

    def error(self, message: str) -> None:
        """Print usage and terminate with exit 64.

        Args:
            message: Argument parsing failure description.

        Raises:
            SystemExit: Always, with the invalid-input exit code.
        """
        self.print_usage(sys.stderr)
        self.exit(EXIT_INVALID_INPUT, f"Agent input error: {message}\n")


def _snake_case(name: str) -> str:
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return re.sub(r"[._-]+", "_", name).lower()


def _validate_inputs(args: argparse.Namespace) -> tuple[Path, str, str, list[str]]:
    target = Path(args.target).resolve()
    if target == TOOL_HOME or TOOL_HOME in target.parents:
        raise ValueError("Target must be outside the tool home; choose --target DIR.")
    if not target.is_dir():
        raise ValueError("Target must be an existing directory; create it first.")
    if not agent_manifest.NAME.fullmatch(args.name):
        raise ValueError(
            "Invalid --name; use letters, digits, dots, underscores or hyphens."
        )
    package = args.package if args.package is not None else _snake_case(args.name)
    if (
        not package.isidentifier()
        or keyword.iskeyword(package)
        or package != package.lower()
    ):
        raise ValueError(
            "Invalid --package; use a lowercase, non-keyword Python identifier."
        )
    for line in (
        (ASSETS / "dockerignore.template").read_text(encoding="utf-8").splitlines()
    ):
        pattern = line.strip().strip("/")
        if pattern and "/" not in pattern and not pattern.startswith(("#", "!")):
            if fnmatch.fnmatchcase(package, pattern):
                raise ValueError(
                    "Invalid --package; it is excluded by dockerignore.template."
                )
    repository = (
        args.repository
        if args.repository is not None
        else f"agents/{args.name.lower()}"
    )
    if not agent_manifest.REPOSITORY.fullmatch(repository) or "//" in repository:
        raise ValueError(
            "Invalid --repository; use the manifest's lowercase repository rule."
        )
    files = [
        "agent.yaml",
        "Dockerfile",
        ".dockerignore",
        ".gitignore",
        "requirements.txt",
        f"{package}/__init__.py",
        f"{package}/app.py",
        f"{package}/agent.py",
    ]
    return target, package, repository, files


def _conflicts(target: Path, files: list[str]) -> list[str]:
    conflicts = []
    for filename in files:
        path = target / filename
        if path.exists() or path.is_symlink():
            conflicts.append(filename)
        elif path.parent != target and (
            path.parent.is_symlink()
            or (path.parent.exists() and not path.parent.is_dir())
        ):
            conflicts.append(filename)
    return conflicts


def _render(target: Path, name: str, package: str, repository: str) -> None:
    replacements = {
        "AGENT_NAME": json.dumps(name),
        "APPLICATION_NAME": json.dumps(name),
        "OCIR_REPOSITORY": json.dumps(repository),
        "REQUIREMENTS_PATH": "requirements.txt",
        "PACKAGE_DIR": package,
        "APP_MODULE": f"{package}.app:app",
    }
    contents = {}
    for filename, template in (
        ("agent.yaml", "agent.yaml.template"),
        ("Dockerfile", "Dockerfile.template"),
        (".dockerignore", "dockerignore.template"),
    ):
        content = (ASSETS / template).read_text(encoding="utf-8")
        if filename != ".dockerignore":
            for key, value in replacements.items():
                content = content.replace("{{" + key + "}}", value)
        contents[filename] = content
    contents[".gitignore"] = GITIGNORE
    if any("{{" in content for content in contents.values()):
        raise ValueError(
            "Unresolved template placeholder; review the tool home templates."
        )
    for filename, content in contents.items():
        with (target / filename).open("x", encoding="utf-8", newline="\n") as output:
            output.write(content)
    agent_manifest.load_manifest(str(target / "agent.yaml"))


def _check_env() -> int:
    path = tool_config.configuration_file()
    print(f"Configuration file: {path}")
    try:
        values = tool_config.read_configuration(path)
    except (OSError, UnicodeError):
        print("Configuration file must be readable UTF-8.", file=sys.stderr)
        return EXIT_CONFIGURATION
    missing, placeholders = tool_config.configuration_issues(values)
    if not path.is_file():
        print(
            "Configuration file is missing; create the selected file.", file=sys.stderr
        )
    if missing:
        print(f"Missing configuration key(s): {', '.join(missing)}", file=sys.stderr)
    if placeholders:
        print(
            f"Placeholder configuration key(s): {', '.join(placeholders)}",
            file=sys.stderr,
        )
    return EXIT_CONFIGURATION if missing or placeholders or not path.is_file() else 0


def main() -> int:
    """Run offline planning, fixed-file rendering, or validation.

    Returns:
        Zero on success, 30 for conflicts, 31 for incomplete tenancy settings,
        or 64 for invalid inputs. Argument parsing errors exit directly with 64.
    """
    parser = ArgumentParser(description="Prepare an OCI agent repository offline.")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("plan", "render"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--name", required=True)
        subparser.add_argument("--package")
        subparser.add_argument("--repository")
        subparser.add_argument("--target", default=".")
    manifest_parser = commands.add_parser("check-manifest")
    manifest_parser.add_argument("--manifest", required=True)
    commands.add_parser("check-env")
    args = parser.parse_args()
    try:
        if args.command == "check-env":
            return _check_env()
        if args.command == "check-manifest":
            manifest = agent_manifest.load_manifest(args.manifest)
            if not manifest["verify"]:
                raise ValueError(
                    "Add at least one functional check to manifest.verify."
                )
            print(f"Manifest valid: {args.manifest}")
            return 0
        target, package, repository, files = _validate_inputs(args)
        print(
            f"Target: {target}\nName: {args.name}\n"
            f"Package: {package}\nRepository: {repository}"
        )
        conflicts = _conflicts(target, files)
        for filename in files:
            label = "Conflict" if filename in conflicts else "Create"
            print(f"{label}: {filename}")
        if conflicts:
            return EXIT_CONFLICT
        if args.command == "render":
            _render(target, args.name, package, repository)
    except FileExistsError:
        print(
            "Agent conflict: a target file appeared; no file was overwritten.",
            file=sys.stderr,
        )
        return EXIT_CONFLICT
    except (ValueError, OSError) as error:
        print(f"Agent input error: {error}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
