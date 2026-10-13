#!/usr/bin/env python3
"""
Author: L. Saetta
Date last modified: 2026-10-13
License: MIT
Description: Execute validated functional HTTP checks from an agent manifest.
"""

import argparse
import json
import os
import re
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def is_subset(expected: Any, observed: Any) -> bool:
    """Return whether expected JSON is recursively contained in observed JSON."""
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(
            key in observed and is_subset(value, observed[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(observed, list) and all(item in observed for item in expected)
    return expected == observed


TERMINAL_FAILURE = "failed"
JOB_ID = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def send(
    base_url: str, method: str, path: str, body: Any, timeout_seconds: int
) -> tuple[int, str]:
    """Send one HTTP request to the agent and return its status and body.

    Raises:
        RuntimeError: If the request cannot reach the agent.
    """
    data = None
    headers: dict[str, str] = {}
    access_token = os.environ.get("OCI_AGENT_ACCESS_TOKEN")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(
        base_url.rstrip("/") + path, data=data, headers=headers, method=method
    )
    try:
        with urlopen(
            request, timeout=timeout_seconds
        ) as response:  # nosec B310: URL is an explicit operator input.
            return response.status, response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")
    except URLError as error:
        raise RuntimeError(
            f"{method} {path} transport failure: {error.reason}"
        ) from error


def parse_json(label: str, body: str) -> Any:
    """Parse a JSON response body.

    Raises:
        RuntimeError: If the body is not JSON.
    """
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"{label} did not return JSON: {body}") from error


def poll_job(
    base_url: str, check: dict[str, Any], start_body: str, timeout_seconds: int
) -> tuple[int, str]:
    """Poll an asynchronous job until it reaches the expected status (Spec 024).

    Args:
        base_url: Agent base URL.
        check: Validated check with a ``poll`` section.
        start_body: Body of the start response, which contains ``job_id``.
        timeout_seconds: Timeout of each HTTP request.

    Returns:
        Status and body of the final status response.

    Raises:
        RuntimeError: If the job fails, disappears, or does not finish in time.
    """
    poll = check["poll"]
    label = f"{check['method']} {check['path']}"
    started = parse_json(label, start_body)
    job_id = started.get("job_id") if isinstance(started, dict) else None
    if not isinstance(job_id, str) or not JOB_ID.fullmatch(job_id):
        raise RuntimeError(f"{label} did not return a valid job_id: {start_body}")
    path = poll["path"].replace("{job_id}", job_id)
    deadline = time.monotonic() + poll["timeout_seconds"]
    while True:
        status, body = send(base_url, "GET", path, None, timeout_seconds)
        if status != 200:
            raise RuntimeError(f"GET {path} returned HTTP {status}: {body}")
        job = parse_json(f"GET {path}", body)
        job_status = job.get("status") if isinstance(job, dict) else None
        if job_status == poll["until_status"]:
            print(f"Job {job_id} reached {job_status}")
            return status, body
        if job_status == TERMINAL_FAILURE:
            raise RuntimeError(f"job {job_id} failed: {job.get('error')}")
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"job {job_id} still {job_status} after {poll['timeout_seconds']}s"
            )
        time.sleep(poll["interval_seconds"])


def execute_check(base_url: str, check: dict[str, Any], timeout_seconds: int) -> None:
    """Invoke one functional check and validate its response.

    Raises:
        RuntimeError: If transport, status, or JSON expectations do not match.
    """
    label = f"{check['method']} {check['path']}"
    status, response_body = send(
        base_url, check["method"], check["path"], check.get("body"), timeout_seconds
    )
    if status != check["expect_status"]:
        raise RuntimeError(
            f"{label} returned HTTP {status}, "
            f"expected {check['expect_status']}: {response_body}"
        )
    if "poll" in check:
        status, response_body = poll_job(
            base_url, check, response_body, timeout_seconds
        )
    if "expect_json" in check:
        response_json = parse_json(label, response_body)
        if not is_subset(check["expect_json"], response_json):
            raise RuntimeError(
                f"{label} JSON did not contain expected fields: {check['expect_json']}"
            )
    print(f"Functional check passed: {label} HTTP {status}")


def main() -> int:
    """Run all configured functional checks."""
    parser = argparse.ArgumentParser(
        description="Run agent manifest functional checks."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--timeout-seconds", required=True, type=int)
    args = parser.parse_args()
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be positive")
    try:
        checks = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        print(f"Invalid checks JSON: {error}", file=sys.stderr)
        return 64
    if not isinstance(checks, list):
        print("Invalid checks JSON: expected a list.", file=sys.stderr)
        return 64
    try:
        for index, check in enumerate(checks):
            if not isinstance(check, dict):
                print(
                    f"Invalid checks JSON: item {index} must be an object.",
                    file=sys.stderr,
                )
                return 64
            execute_check(args.base_url, check, args.timeout_seconds)
    except RuntimeError as error:
        print(f"Functional check failed: {error}", file=sys.stderr)
        return 13
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
