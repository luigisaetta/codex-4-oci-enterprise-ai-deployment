"""
Author: L. Saetta
Date last modified: 2026-09-29
License: MIT
Description: Unit tests for the strict agent manifest configuration contract.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.agent_manifest import (
    ManifestError,
    load_manifest,
    resolve_runtime_environment,
)


def write_manifest(
    directory: Path, context: str = ".", dockerfile: str = "Dockerfile"
) -> Path:
    """Create a valid version 2 manifest and its local build inputs.

    Args:
        directory: Directory that will contain the manifest and Dockerfile.
        context: Build context path written to the manifest.
        dockerfile: Dockerfile path written to the manifest.

    Returns:
        Path to the created manifest.
    """
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    manifest = directory / "agent.yaml"
    manifest.write_text(
        "\n".join(
            [
                "schema_version: 2",
                "name: hello-world",
                f"build: {{context: {context}, dockerfile: {dockerfile}}}",
                "publish: {repository: agents/hello-world}",
                "deploy: {application_name: hello-world, profile: public-noauth}",
                "verify: []",
            ]
        ),
        encoding="utf-8",
    )
    return manifest


def test_hello_world_manifest_is_valid() -> None:
    """The reference agent keeps all stable configuration in its manifest."""
    manifest = load_manifest("demos/hello_world/agent.yaml")
    assert manifest["build"]["context"] == str(Path.cwd().resolve())
    assert manifest["build"]["dockerfile"] == str(
        (Path.cwd() / "demos/hello_world/Dockerfile").resolve()
    )
    assert manifest["publish"]["repository"] == "agents/hello-world"
    assert manifest["verify"][0]["expect_json"] == {"message": "Hello Luigi"}


def test_absolute_manifest_path_is_accepted(tmp_path: Path) -> None:
    """An absolute manifest path is resolved without reference to the tool home."""
    manifest_path = write_manifest(tmp_path / "agent")
    assert load_manifest(str(manifest_path))["name"] == "hello-world"


def test_cwd_relative_manifest_path_is_accepted(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A relative manifest path is interpreted from the current directory."""
    workspace = tmp_path / "workspace"
    write_manifest(workspace / "agent")
    monkeypatch.chdir(workspace)
    assert load_manifest("agent/agent.yaml")["name"] == "hello-world"


def test_build_paths_are_relative_to_manifest_directory(tmp_path: Path) -> None:
    """Build paths use the manifest directory even when the process is elsewhere."""
    manifest_path = write_manifest(tmp_path / "agent", "context", "Dockerfile")
    (tmp_path / "agent/context").mkdir()
    manifest = load_manifest(str(manifest_path))
    assert manifest["build"] == {
        "context": str((tmp_path / "agent/context").resolve()),
        "dockerfile": str((tmp_path / "agent/Dockerfile").resolve()),
    }


@pytest.mark.parametrize("git_entry", ["directory", "file"])
def test_git_root_discovery_allows_manifest_relative_parent_paths(
    tmp_path: Path, git_entry: str
) -> None:
    """A .git directory or worktree file identifies the allowed repository root."""
    repository = tmp_path / "repository"
    repository.mkdir()
    git_path = repository / ".git"
    if git_entry == "directory":
        git_path.mkdir()
    else:
        git_path.write_text("gitdir: /elsewhere\n", encoding="utf-8")
    (repository / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    manifest_path = write_manifest(repository / "agent", "..", "../Dockerfile")
    manifest = load_manifest(str(manifest_path))
    assert manifest["build"]["context"] == str(repository.resolve())
    assert manifest["build"]["dockerfile"] == str((repository / "Dockerfile").resolve())


def test_configured_single_allowed_root_is_used(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OCI_AGENT_ALLOWED_ROOTS can provide one root without a Git marker."""
    root = tmp_path / "allowed"
    manifest_path = write_manifest(root / "agent")
    monkeypatch.setenv("OCI_AGENT_ALLOWED_ROOTS", str(root.resolve()))
    assert load_manifest(str(manifest_path))["name"] == "hello-world"


def test_configured_several_allowed_roots_are_used(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Build inputs may be resolved into another explicitly allowed root."""
    manifest_root = tmp_path / "agent-root"
    build_root = tmp_path / "build-root"
    build_root.mkdir()
    (build_root / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    manifest_path = write_manifest(
        manifest_root / "agent", "../../build-root", "../../build-root/Dockerfile"
    )
    roots = os.pathsep.join([str(manifest_root.resolve()), str(build_root.resolve())])
    monkeypatch.setenv("OCI_AGENT_ALLOWED_ROOTS", roots)
    assert load_manifest(str(manifest_path))["build"]["context"] == str(
        build_root.resolve()
    )


def test_escaping_build_path_is_rejected_with_allowed_root(tmp_path: Path) -> None:
    """A parent traversal beyond the discovered root is rejected with its name."""
    root = tmp_path / "repository"
    (root / ".git").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    manifest_path = write_manifest(root / "agent", "../../outside", "Dockerfile")
    with pytest.raises(ManifestError, match=f"allowed root\\(s\\): {root}"):
        load_manifest(str(manifest_path))


def test_symlink_escaping_allowed_root_is_rejected(tmp_path: Path) -> None:
    """A symlink cannot bypass the containment check for build paths."""
    root = tmp_path / "repository"
    (root / ".git").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    manifest_path = write_manifest(root / "agent", "escape", "Dockerfile")
    (root / "agent/escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ManifestError, match="allowed root"):
        load_manifest(str(manifest_path))


def test_schema_version_one_is_rejected_with_migration_message(tmp_path: Path) -> None:
    """Version 1 manifests explain the version 2 path migration."""
    manifest_path = write_manifest(tmp_path / "agent")
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "schema_version: 2", "schema_version: 1"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="paths are now relative.*version to 2"):
        load_manifest(str(manifest_path))


def test_get_returns_absolute_build_paths(tmp_path: Path) -> None:
    """The command-line get output does not depend on the caller's directory."""
    manifest_path = write_manifest(tmp_path / "agent")
    script = Path(__file__).resolve().parents[1] / "scripts/agent_manifest.py"
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "get",
            "--manifest",
            str(manifest_path),
            "--field",
            "build.context",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.stdout.strip() == str(manifest_path.parent.resolve())


@pytest.mark.parametrize("field", ["tag: 0.2.0", "unknown: value"])
def test_unknown_or_release_configuration_is_rejected(
    field: str, tmp_path: Path
) -> None:
    """Unsupported stable configuration, including a tag, cannot enter a manifest."""
    manifest_path = write_manifest(tmp_path / "agent")
    manifest_path.write_text(
        f"{manifest_path.read_text(encoding='utf-8')}\n{field}\n", encoding="utf-8"
    )
    with pytest.raises(ManifestError):
        load_manifest(str(manifest_path))


def test_runtime_environment_resolves_plaintext_and_vault_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Runtime sources become OCI types and Vault overrides are local-only."""
    monkeypatch.setenv("OCI_COMPARTMENT_ID", "ocid1.compartment.oc1..example")
    monkeypatch.setenv("OCI_AGENT_VAULT_EXTERNAL_API_KEY", "local-only-value")
    manifest_path = write_manifest(tmp_path / "agent")
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "verify: []",
            """runtime:
  env:
    - {name: LOG_LEVEL, value: INFO}
    - {name: GENAI_COMPARTMENT_ID, from_env: OCI_COMPARTMENT_ID}
    - {name: EXTERNAL_API_KEY,
       vault_secret_id: ocid1.vaultsecret.oc1.eu-frankfurt-1.example}
verify: []""",
        ),
        encoding="utf-8",
    )
    manifest = load_manifest(str(manifest_path))
    remote, skipped = resolve_runtime_environment(manifest, local=False)
    local, local_skipped = resolve_runtime_environment(manifest, local=True)
    assert remote[0] == {"name": "LOG_LEVEL", "type": "PLAINTEXT", "value": "INFO"}
    assert remote[2]["type"] == "VAULT"
    assert not skipped
    assert local[2] == {
        "name": "EXTERNAL_API_KEY",
        "type": "PLAINTEXT",
        "value": "local-only-value",
    }
    assert not local_skipped


@pytest.mark.parametrize(
    "entry",
    [
        "{name: PATH, value: value}",
        "{name: API_KEY, value: secret}",
        "{name: LOG_LEVEL, value: one, from_env: TWO}",
    ],
)
def test_invalid_runtime_environment_is_rejected(entry: str, tmp_path: Path) -> None:
    """Reserved, sensitive literal, and ambiguous runtime variables are invalid."""
    manifest_path = write_manifest(tmp_path / "agent")
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8").replace(
            "verify: []", f"runtime: {{env: [{entry}]}}\nverify: []"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(str(manifest_path))
