"""
Author: L. Saetta
Date last modified: 2026-10-13
License: MIT
Description: Test sanitized identity-domain token request construction.
"""

import base64
import http.server
import importlib.util
import os
import subprocess
import sys
import threading
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


def test_token_helper_reads_credentials_from_the_tool_env_file(tmp_path: Path) -> None:
    """Without exported credentials, the helper uses the tool's .env (Spec 022)."""
    seen: dict[str, str] = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        """Fake token endpoint that records the Basic credentials."""

        def do_POST(self) -> None:  # pylint: disable=invalid-name
            """Answer one token request."""
            self.rfile.read(int(self.headers["Content-Length"]))
            seen["basic"] = base64.b64decode(
                self.headers["Authorization"].split()[1]
            ).decode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"access_token":"file-token"}')

        def log_message(self, *_: object) -> None:
            """Keep test output quiet."""

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    configuration = tmp_path / "tool.env"
    configuration.write_text(
        "OCI_AGENT_IDCS_CLIENT_ID=file-client\n"
        "OCI_AGENT_IDCS_CLIENT_SECRET=file-secret\n",
        encoding="utf-8",
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("OCI_AGENT_IDCS_")
    }
    environment["OCI_AGENT_ENV_FILE"] = str(configuration)
    port = server.server_address[1]
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--domain-url",
            f"http://127.0.0.1:{port}",
            "--audience",
            "aud/",
            "--scope",
            "invoke",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    thread.join(timeout=10)
    server.server_close()

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "file-token"
    assert seen["basic"] == "file-client:file-secret"
    assert "file-secret" not in result.stderr


def test_token_helper_names_both_places_when_credentials_are_missing(
    tmp_path: Path,
) -> None:
    """A missing credential is named, with no value, and exits 64."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("OCI_AGENT_IDCS_")
    }
    environment["OCI_AGENT_ENV_FILE"] = str(tmp_path / "missing.env")
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--domain-url",
            "https://idcs-placeholder.example",
            "--audience",
            "a",
            "--scope",
            "b",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )

    assert result.returncode == 64
    assert "OCI_AGENT_IDCS_CLIENT_ID" in result.stderr
    assert "tool's .env" in result.stderr
