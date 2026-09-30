"""
Author: L. Saetta
Date last modified: 2026-09-30
License: MIT
Description: Test sanitized identity-domain token request construction.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "idcs_token.py"
CHECKS_SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "run_manifest_checks.py"
)
AUTH = {
    "domain_url": "https://idcs-placeholder.example:443/",
    "audience": "placeholder-audience",
    "scope": "placeholder-scope",
}


def load_token_module() -> ModuleType:
    """Load the token helper without modifying Python's import path."""
    specification = importlib.util.spec_from_file_location("idcs_token", SCRIPT)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def load_checks_module() -> ModuleType:
    """Load the functional-check helper without modifying Python's import path."""
    specification = importlib.util.spec_from_file_location(
        "run_manifest_checks", CHECKS_SCRIPT
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


class FakeResponse:
    """Minimal successful urllib response fixture."""

    status = 200

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        """Return a placeholder access-token response."""
        return b'{"access_token":"placeholder-token"}'


def test_request_token_uses_manifest_scope_composition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default OAuth form scope concatenates the manifest audience and scope."""
    module = load_token_module()
    captured = {}

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    assert module.request_token(AUTH, "placeholder-client", "placeholder-secret") == (
        "placeholder-token"
    )
    request = captured["request"]
    assert request.full_url == "https://idcs-placeholder.example:443/oauth2/v1/token"
    assert (
        request.data
        == b"grant_type=client_credentials&scope=placeholder-audienceplaceholder-scope"
    )
    assert captured["timeout"] == 30


def test_request_token_honors_operator_scope_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The optional environment scope replaces the manifest-derived value."""
    module = load_token_module()
    captured = {}

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        captured["request"] = request
        assert timeout == 30
        return FakeResponse()

    monkeypatch.setenv("OCI_AGENT_IDCS_TOKEN_SCOPE", "placeholder-override")
    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    module.request_token(AUTH, "placeholder-client", "placeholder-secret")
    assert captured["request"].data.endswith(b"scope=placeholder-override")


def test_functional_checks_add_bearer_header_from_process_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Functional requests inherit the verifier's process-scoped access token."""
    module = load_checks_module()
    captured = {}

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        captured["request"] = request
        assert timeout == 1
        return FakeResponse()

    monkeypatch.setenv("OCI_AGENT_ACCESS_TOKEN", "placeholder-token")
    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    module.execute_check(
        "https://endpoint-placeholder.example",
        {"method": "GET", "path": "/check", "expect_status": 200},
        1,
    )
    assert captured["request"].get_header("Authorization") == "Bearer placeholder-token"
