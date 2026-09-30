"""
Author: L. Saetta
Date last modified: 2026-09-30
License: MIT
Description: Exercise Bash verifier identity-domain authentication without
network access.
"""

# pylint: disable=duplicate-code

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_deployment.sh"
APPLICATION_ID = "ocid1.generativeaihostedapplication.oc1.test"
CLIENT_SECRET = "placeholder-client-secret"
ACCESS_TOKEN = "placeholder-access-token"


def write_manifest(directory: Path, profile: str, functional: bool = False) -> Path:
    """Write an authenticated or unauthenticated verifier manifest fixture."""
    directory.mkdir()
    (directory / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    auth = ""
    if profile == "public-idcs":
        auth = (
            "  auth:\n"
            "    domain_url: https://idcs-placeholder.example:443\n"
            "    audience: placeholder-audience\n"
            "    scope: placeholder-scope\n"
        )
    checks = "[]"
    if functional:
        checks = "[{method: GET, path: /check, expect_status: 200}]"
    manifest = directory / "agent.yaml"
    manifest.write_text(
        "schema_version: 2\n"
        "name: verify-idcs\n"
        "build: {context: ., dockerfile: Dockerfile}\n"
        "publish: {repository: agents/verify-idcs}\n"
        "deploy:\n"
        "  application_name: verify-idcs\n"
        f"  profile: {profile}\n"
        f"{auth}"
        f"verify: {checks}\n",
        encoding="utf-8",
    )
    return manifest


def write_fake_tools(directory: Path) -> None:
    """Write OCI, curl, and Python wrappers that record no secret-bearing data."""
    (directory / "oci").write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

scenario = json.load(open(os.environ["IDCS_SCENARIO"], encoding="utf-8"))
arguments = sys.argv[1:]
with open(os.environ["IDCS_OCI_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(arguments) + "\\n")
query = arguments[arguments.index("--query") + 1] if "--query" in arguments else ""
if "hosted-application" in arguments and "get" in arguments:
    if "--output" in arguments:
        print(json.dumps({"data": {"inbound-auth-config": scenario["inbound"]}}))
    elif "lifecycle-state" in query:
        print("ACTIVE")
    else:
        print("ocid1.compartment.test")
elif "list-hosted-deployments" in arguments:
    if "length(" in query:
        print("1")
    elif "active-artifact" in query:
        print("1.2.3")
    else:
        print("ocid1.generativeaihosteddeployment.test")
elif "hosted-deployment" in arguments and "get" in arguments:
    print("ACTIVE" if "lifecycle-state" in query else "1.2.3")
else:
    raise SystemExit("Unexpected OCI invocation")
""",
        encoding="utf-8",
    )
    (directory / "curl").write_text(
        """#!/usr/bin/env python3
import json
import os
import sys

arguments = sys.argv[1:]
config = sys.stdin.read()
authenticated = "Authorization: Bearer " + os.environ["IDCS_ACCESS_TOKEN"] in config
with open(os.environ["IDCS_CURL_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps({"argv": arguments, "authenticated": authenticated}) + "\\n")
print("200" if authenticated else os.environ["IDCS_UNAUTHENTICATED_STATUS"])
""",
        encoding="utf-8",
    )
    (directory / "python-wrapper").write_text(
        f"""#!{sys.executable}
import os
import sys

name = os.path.basename(sys.argv[1])
with open(os.environ["IDCS_PYTHON_LOG"], "a", encoding="utf-8") as log:
    log.write(name + "\\n")
if name == "idcs_token.py":
    if os.environ.get("IDCS_TOKEN_FAILURE"):
        print("HTTP status: 401", file=sys.stderr)
        print("OAuth error: invalid_client", file=sys.stderr)
        raise SystemExit(24)
    print(os.environ["IDCS_ACCESS_TOKEN"])
    raise SystemExit(0)
if name == "run_manifest_checks.py":
    if os.environ.get("OCI_AGENT_ACCESS_TOKEN") != os.environ["IDCS_ACCESS_TOKEN"]:
        raise SystemExit(13)
    raise SystemExit(0)
os.execv(sys.executable, [sys.executable] + sys.argv[1:])
""",
        encoding="utf-8",
    )
    for name in ("oci", "curl", "python-wrapper"):
        (directory / name).chmod(0o755)


def run_verifier(
    tmp_path: Path,
    profile: str = "public-idcs",
    **scenario_updates: object,
) -> subprocess.CompletedProcess[str]:
    """Run the Bash verifier against offline identity-domain scenarios."""
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    write_fake_tools(fake_bin)
    inbound = {
        "inbound-auth-config-type": "IDCS_AUTH_CONFIG",
        "idcs-config": {
            "domain-url": "https://idcs-placeholder.example:443",
            "scope": "placeholder-scope",
            "audience": "placeholder-audience",
        },
    }
    scenario = {"inbound": inbound, **scenario_updates}
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text(json.dumps(scenario), encoding="utf-8")
    log_paths = {name: tmp_path / f"{name}.log" for name in ("oci", "curl", "python")}
    environment = os.environ.copy()
    environment.update(
        OCI_AGENT_PYTHON=str(fake_bin / "python-wrapper"),
        OCI_REGION="test-region",
        IDCS_SCENARIO=str(scenario_path),
        IDCS_OCI_LOG=str(log_paths["oci"]),
        IDCS_CURL_LOG=str(log_paths["curl"]),
        IDCS_PYTHON_LOG=str(log_paths["python"]),
        IDCS_ACCESS_TOKEN=ACCESS_TOKEN,
        IDCS_UNAUTHENTICATED_STATUS=str(
            scenario.get(
                "unauthenticated_status", 200 if profile == "public-noauth" else 401
            )
        ),
        OCI_AGENT_IDCS_CLIENT_ID="placeholder-client-id",
        OCI_AGENT_IDCS_CLIENT_SECRET=CLIENT_SECRET,
        PATH=f"{fake_bin}{os.pathsep}{environment['PATH']}",
    )
    if scenario.get("token_failure"):
        environment["IDCS_TOKEN_FAILURE"] = "1"
    if scenario.get("missing"):
        environment.pop(str(scenario["missing"]))
    options = [
        "--application-id",
        APPLICATION_ID,
        "--manifest",
        str(
            write_manifest(
                tmp_path / "agent", profile, bool(scenario.get("functional"))
            )
        ),
        "--tag",
        "1.2.3",
        "--timeout-seconds",
        "1",
        "--poll-seconds",
        "1",
    ]
    if scenario.get("functional"):
        options.append("--functional")
    result = subprocess.run(
        [shutil.which("bash") or "/bin/bash", str(SCRIPT), *options],
        capture_output=True,
        check=False,
        cwd=tmp_path,
        env=environment,
        text=True,
    )
    result.log_paths = log_paths
    return result


def read_log(path: Path) -> str:
    """Return an optional fake-tool log without creating a new artifact."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.mark.parametrize(
    "missing",
    ["OCI_AGENT_IDCS_CLIENT_ID", "OCI_AGENT_IDCS_CLIENT_SECRET"],
)
def test_missing_idcs_credentials_stop_before_oci_or_http(
    tmp_path: Path, missing: str
) -> None:
    """Credential preflight names an absent variable without invoking external tools."""
    result = run_verifier(tmp_path, missing=missing)
    assert result.returncode == 64
    assert missing in result.stderr
    assert not read_log(result.log_paths["oci"])
    assert not read_log(result.log_paths["curl"])


def test_idcs_success_uses_stdin_bearer_auth_and_functional_token(
    tmp_path: Path,
) -> None:
    """Protected probes authenticate after a rejected unauthenticated health request."""
    result = run_verifier(tmp_path, functional=True)
    curl_log = [
        json.loads(line) for line in read_log(result.log_paths["curl"]).splitlines()
    ]
    all_output = result.stdout + result.stderr + read_log(result.log_paths["oci"])
    all_output += read_log(result.log_paths["curl"]) + read_log(
        result.log_paths["python"]
    )
    assert result.returncode == 0, result.stderr
    assert "auth=idcs unauthenticated_status=401 result=PASS" in result.stdout
    assert [entry["authenticated"] for entry in curl_log] == [False, True, True]
    assert "idcs_token.py" in read_log(result.log_paths["python"])
    assert "run_manifest_checks.py" in read_log(result.log_paths["python"])
    assert CLIENT_SECRET not in all_output
    assert ACCESS_TOKEN not in all_output
    assert all(ACCESS_TOKEN not in " ".join(entry["argv"]) for entry in curl_log)


def test_idcs_token_failure_is_sanitized(tmp_path: Path) -> None:
    """Token failure returns 24 while exposing only the status and OAuth error."""
    result = run_verifier(tmp_path, token_failure=True)
    assert result.returncode == 24
    assert "HTTP status: 401" in result.stderr
    assert "OAuth error: invalid_client" in result.stderr
    assert CLIENT_SECRET not in result.stderr
    assert ACCESS_TOKEN not in result.stderr


def test_idcs_accepted_unauthenticated_request_stops(tmp_path: Path) -> None:
    """A protected application accepting anonymous health requests returns exit 25."""
    result = run_verifier(tmp_path, unauthenticated_status=200)
    assert result.returncode == 25
    assert "The endpoint accepted a request without a token" in result.stderr


def test_idcs_inbound_mismatch_stops_before_token_request(tmp_path: Path) -> None:
    """Verifier reuse rejects an application whose inbound authentication differs."""
    result = run_verifier(
        tmp_path,
        inbound={"inbound-auth-config-type": "UNKNOWN_ENUM_VALUE", "idcs-config": None},
    )
    assert result.returncode == 20
    assert "inbound authentication differs" in result.stderr
    assert "idcs_token.py" not in read_log(result.log_paths["python"])


def test_public_noauth_keeps_unauthenticated_behavior(tmp_path: Path) -> None:
    """Unauthenticated manifests do not request a token and report auth=none."""
    result = run_verifier(tmp_path, profile="public-noauth")
    assert result.returncode == 0, result.stderr
    assert "auth=none result=PASS" in result.stdout
    assert "idcs_token.py" not in read_log(result.log_paths["python"])
