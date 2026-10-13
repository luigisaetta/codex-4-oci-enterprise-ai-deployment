"""
Author: L. Saetta
Date last modified: 2026-10-13
License: MIT
Description: Test asynchronous functional checks: validation and job polling (Spec 024).
"""

# pylint: disable=duplicate-code

import http.server
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_TOOL = ROOT / "scripts" / "agent_manifest.py"
RUNNER = ROOT / "scripts" / "run_manifest_checks.py"


def manifest_with_checks(directory: Path, checks: str) -> Path:
    """Write a minimal manifest whose verify section is the given YAML.

    Args:
        directory: Folder for the manifest and its Dockerfile.
        checks: YAML flow sequence for ``verify``.

    Returns:
        Path to the manifest.
    """
    directory.mkdir()
    (directory / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    manifest = directory / "agent.yaml"
    manifest.write_text(
        "schema_version: 2\n"
        "name: async-test\n"
        "build: {context: ., dockerfile: Dockerfile}\n"
        "publish: {repository: agents/async-test}\n"
        "deploy: {application_name: async-test, profile: public-noauth}\n"
        f"verify: {checks}\n",
        encoding="utf-8",
    )
    return manifest


def manifest_command(manifest: Path, *arguments: str) -> subprocess.CompletedProcess:
    """Run the manifest tool on a manifest."""
    return subprocess.run(
        [sys.executable, str(MANIFEST_TOOL), *arguments, "--manifest", str(manifest)],
        capture_output=True,
        text=True,
        check=False,
    )


ASYNC_CHECK = (
    "{method: POST, path: /jobs, body: {text: hi}, expect_status: 202, "
    "poll: {path: '/jobs/{job_id}', until_status: completed, timeout_seconds: 10, "
    "interval_seconds: 1}, expect_json: {status: completed}}"
)


def test_poll_check_is_valid_and_gets_defaults(tmp_path: Path) -> None:
    """A complete poll section validates; defaults fill missing timings."""
    check = (
        "{method: POST, path: /jobs, expect_status: 202, "
        "poll: {path: '/jobs/{job_id}', until_status: completed}}"
    )
    result = manifest_command(
        manifest_with_checks(tmp_path / "agent", f"[{check}]"), "checks"
    )

    assert result.returncode == 0, result.stderr
    poll = json.loads(result.stdout)[0]["poll"]
    assert poll["timeout_seconds"] == 300 and poll["interval_seconds"] == 3


@pytest.mark.parametrize(
    "check",
    [
        "{method: POST, path: /jobs, expect_status: 202, "
        "poll: {path: /jobs/x, until_status: completed}}",
        "{method: GET, path: /jobs, expect_status: 200, "
        "poll: {path: '/jobs/{job_id}', until_status: completed}}",
        "{method: POST, path: /jobs, expect_status: 202, "
        "poll: {path: '/jobs/{job_id}', until_status: completed, timeout_seconds: 0}}",
        "{method: POST, path: /jobs, expect_status: 202, "
        "poll: {path: '/jobs/{job_id}', until_status: completed, "
        "interval_seconds: 61}}",
        "{method: POST, path: /jobs, expect_status: 202, "
        "poll: {path: '/jobs/{job_id}'}}",
        "{method: POST, path: /jobs, expect_status: 202, "
        "poll: {path: '/jobs/{job_id}', until_status: completed, every: 2}}",
        "{method: POST, path: /jobs, expect_status: 202, local: maybe}",
    ],
)
def test_invalid_poll_or_local_is_rejected(tmp_path: Path, check: str) -> None:
    """Incomplete, out-of-range, misplaced, and unknown settings exit 64."""
    result = manifest_command(
        manifest_with_checks(tmp_path / "agent", f"[{check}]"), "validate"
    )

    assert result.returncode == 64
    assert "verify[0]" in result.stderr


def test_local_filter_drops_remote_only_checks(tmp_path: Path) -> None:
    """checks --local omits checks marked local: false."""
    checks = (
        "[{method: POST, path: /jobs, expect_status: 400}, "
        "{method: POST, path: /jobs, body: {text: hi}, expect_status: 202, "
        "local: false}]"
    )
    manifest = manifest_with_checks(tmp_path / "agent", checks)

    remote = json.loads(manifest_command(manifest, "checks").stdout)
    local = json.loads(manifest_command(manifest, "checks", "--local").stdout)

    assert len(remote) == 2
    assert len(local) == 1 and local[0]["expect_status"] == 400


class FakeAsyncAgent(http.server.BaseHTTPRequestHandler):
    """A job API whose behavior is chosen by the request path prefix."""

    polls: dict[str, int] = {}
    scenario = "ok"

    def reply(self, status: int, payload: object) -> None:
        """Send a JSON response."""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # pylint: disable=invalid-name
        """Start a job."""
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if FakeAsyncAgent.scenario == "no_job_id":
            self.reply(202, {"status": "queued"})
            return
        FakeAsyncAgent.polls["job-1"] = 0
        self.reply(202, {"job_id": "job-1", "status": "queued", "steps": []})

    def do_GET(self) -> None:  # pylint: disable=invalid-name
        """Report the job status."""
        if FakeAsyncAgent.scenario == "missing":
            self.reply(404, {"error": {"code": "not_found"}})
            return
        count = FakeAsyncAgent.polls.get("job-1", 0) + 1
        FakeAsyncAgent.polls["job-1"] = count
        if FakeAsyncAgent.scenario == "failed" and count >= 2:
            self.reply(
                200,
                {
                    "job_id": "job-1",
                    "status": "failed",
                    "error": {"code": "step_failed", "message": "Step 2 failed"},
                },
            )
            return
        if FakeAsyncAgent.scenario == "slow" or count < 3:
            self.reply(200, {"job_id": "job-1", "status": "running", "result": None})
            return
        self.reply(200, {"job_id": "job-1", "status": "completed", "result": {"a": 1}})

    def log_message(self, *_: object) -> None:
        """Keep test output quiet."""


@pytest.fixture(name="agent_url")
def agent_url_fixture():
    """Start the fake asynchronous agent and return its base URL."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeAsyncAgent)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def run_checks(base_url: str, checks: list[dict]) -> subprocess.CompletedProcess:
    """Run the functional-check runner on a list of checks."""
    return subprocess.run(
        [sys.executable, str(RUNNER), "--base-url", base_url, "--timeout-seconds", "5"],
        input=json.dumps(checks),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def async_check(timeout_seconds: int = 10) -> dict:
    """Return a validated-shape asynchronous check."""
    return {
        "method": "POST",
        "path": "/jobs",
        "body": {"text": "hi"},
        "expect_status": 202,
        "poll": {
            "path": "/jobs/{job_id}",
            "until_status": "completed",
            "timeout_seconds": timeout_seconds,
            "interval_seconds": 1,
        },
        "expect_json": {"status": "completed"},
    }


def test_polling_check_passes_when_the_job_completes(agent_url: str) -> None:
    """The runner polls until completed and applies expect_json to the end."""
    FakeAsyncAgent.scenario = "ok"
    result = run_checks(agent_url, [async_check()])

    assert result.returncode == 0, result.stderr
    assert "Job job-1 reached completed" in result.stdout
    assert "Functional check passed: POST /jobs HTTP 200" in result.stdout


@pytest.mark.parametrize(
    ("scenario", "timeout_seconds", "message"),
    [
        ("failed", 10, "job job-1 failed"),
        ("missing", 10, "returned HTTP 404"),
        ("no_job_id", 10, "did not return a valid job_id"),
        ("slow", 2, "still running after 2s"),
    ],
)
def test_polling_check_fails_clearly(
    agent_url: str, scenario: str, timeout_seconds: int, message: str
) -> None:
    """A failed job, a lost job, a missing job_id, and a timeout fail the check."""
    FakeAsyncAgent.scenario = scenario
    result = run_checks(agent_url, [async_check(timeout_seconds)])

    assert result.returncode == 13
    assert message in result.stderr
