"""
Author: L. Saetta
Date last modified: 2026-09-23
License: MIT
Description: Unit tests for the strict agent manifest configuration contract.
"""

from pathlib import Path

import pytest

from scripts.agent_manifest import (
    ManifestError,
    load_manifest,
    resolve_runtime_environment,
)


def write_manifest(tmp_path: Path, content: str) -> str:
    """Write a manifest beneath the checkout for test input handling.

    Args:
        tmp_path: Pytest temporary directory (unused outside this test helper).
        content: YAML content to write.

    Returns:
        A checkout-relative manifest path.
    """
    del tmp_path
    manifest = (
        Path(__file__).resolve().parents[1]
        / "demos"
        / "hello_world"
        / "agent-test.yaml"
    )
    manifest.write_text(content, encoding="utf-8")
    return "demos/hello_world/agent-test.yaml"


def test_hello_world_manifest_is_valid() -> None:
    """The reference agent keeps all stable configuration in its manifest."""
    manifest = load_manifest("demos/hello_world/agent.yaml")
    assert manifest["build"]["context"] == "."
    assert manifest["publish"]["repository"] == "agents/hello-world"
    assert manifest["verify"][0]["expect_json"] == {"message": "Hello Luigi"}


@pytest.mark.parametrize("field", ["tag: 0.2.0", "unknown: value"])
def test_unknown_or_release_configuration_is_rejected(
    field: str, tmp_path: Path
) -> None:
    """Unsupported stable configuration, including a tag, cannot enter a manifest."""
    path = write_manifest(
        tmp_path,
        "\n".join(
            [
                "schema_version: 1",
                "name: hello-world",
                "build: {context: ., dockerfile: demos/hello_world/Dockerfile}",
                "publish: {repository: agents/hello-world}",
                "deploy: {application_name: hello-world, profile: public-noauth}",
                "verify: []",
                field,
            ]
        ),
    )
    try:
        with pytest.raises(ManifestError):
            load_manifest(path)
    finally:
        (Path(__file__).resolve().parents[1] / path).unlink(missing_ok=True)


def test_unsafe_build_path_is_rejected(tmp_path: Path) -> None:
    """A manifest cannot select a Dockerfile outside the checkout."""
    path = write_manifest(
        tmp_path,
        """schema_version: 1
name: hello-world
build: {context: ., dockerfile: ../Dockerfile}
publish: {repository: agents/hello-world}
deploy: {application_name: hello-world, profile: public-noauth}
verify: []
""",
    )
    try:
        with pytest.raises(ManifestError, match="stay below"):
            load_manifest(path)
    finally:
        (Path(__file__).resolve().parents[1] / path).unlink(missing_ok=True)


def test_runtime_environment_resolves_plaintext_and_vault_sources(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Runtime sources become OCI types and Vault overrides are local-only."""
    monkeypatch.setenv("OCI_COMPARTMENT_ID", "ocid1.compartment.oc1..example")
    monkeypatch.setenv("OCI_AGENT_VAULT_EXTERNAL_API_KEY", "local-only-value")
    path = write_manifest(
        tmp_path,
        """schema_version: 1
name: hello-world
build: {context: ., dockerfile: demos/hello_world/Dockerfile}
publish: {repository: agents/hello-world}
deploy: {application_name: hello-world, profile: public-noauth}
runtime:
  env:
    - {name: LOG_LEVEL, value: INFO}
    - {name: GENAI_COMPARTMENT_ID, from_env: OCI_COMPARTMENT_ID}
    - {name: EXTERNAL_API_KEY,
       vault_secret_id: ocid1.vaultsecret.oc1.eu-frankfurt-1.example}
verify: []
""",
    )
    try:
        manifest = load_manifest(path)
        remote, skipped = resolve_runtime_environment(manifest, local=False)
        local, local_skipped = resolve_runtime_environment(manifest, local=True)
        assert remote[0] == {
            "name": "LOG_LEVEL",
            "type": "PLAINTEXT",
            "value": "INFO",
        }
        assert remote[2]["type"] == "VAULT"
        assert not skipped
        assert local[2] == {
            "name": "EXTERNAL_API_KEY",
            "type": "PLAINTEXT",
            "value": "local-only-value",
        }
        assert not local_skipped
    finally:
        (Path(__file__).resolve().parents[1] / path).unlink(missing_ok=True)


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
    path = write_manifest(
        tmp_path,
        "\n".join(
            [
                "schema_version: 1",
                "name: hello-world",
                "build: {context: ., dockerfile: demos/hello_world/Dockerfile}",
                "publish: {repository: agents/hello-world}",
                "deploy: {application_name: hello-world, profile: public-noauth}",
                f"runtime: {{env: [{entry}]}}",
                "verify: []",
            ]
        ),
    )
    try:
        with pytest.raises(ManifestError):
            load_manifest(path)
    finally:
        (Path(__file__).resolve().parents[1] / path).unlink(missing_ok=True)
