#!/usr/bin/env python3
"""
Author: L. Saetta
Date last modified: 2026-09-29
License: MIT
Description: Execute validated functional HTTP checks from an agent manifest.
"""

import argparse
import json
import os
import sys
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


def execute_check(base_url: str, check: dict[str, Any], timeout_seconds: int) -> None:
    """Invoke one functional check and validate its response.

    Raises:
        RuntimeError: If transport, status, or JSON expectations do not match.
    """
    body = None
    headers: dict[str, str] = {}
    access_token = os.environ.get("OCI_AGENT_ACCESS_TOKEN")
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    if "body" in check:
        body = json.dumps(check["body"]).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(
        base_url.rstrip("/") + check["path"],
        data=body,
        headers=headers,
        method=check["method"],
    )
    try:
        with urlopen(
            request, timeout=timeout_seconds
        ) as response:  # nosec B310: URL is an explicit operator input.
            status = response.status
            response_body = response.read().decode("utf-8")
    except HTTPError as error:
        status = error.code
        response_body = error.read().decode("utf-8", errors="replace")
    except URLError as error:
        raise RuntimeError(
            f"{check['method']} {check['path']} transport failure: {error.reason}"
        ) from error
    if status != check["expect_status"]:
        raise RuntimeError(
            f"{check['method']} {check['path']} returned HTTP {status}, "
            f"expected {check['expect_status']}: {response_body}"
        )
    if "expect_json" in check:
        try:
            response_json = json.loads(response_body)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"{check['method']} {check['path']} did not return JSON: "
                f"{response_body}"
            ) from error
        if not is_subset(check["expect_json"], response_json):
            raise RuntimeError(
                f"{check['method']} {check['path']} JSON did not contain "
                f"expected fields: {check['expect_json']}"
            )
    print(f"Functional check passed: {check['method']} {check['path']} HTTP {status}")


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
