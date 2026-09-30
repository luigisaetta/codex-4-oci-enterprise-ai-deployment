#!/usr/bin/env python3
"""
Author: L. Saetta
Date last modified: 2026-09-30
License: MIT
Description: Obtain an identity-domain client-credentials access token safely.
"""

import argparse
import base64
import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

EXIT_INVALID_INPUT = 64
EXIT_TOKEN_FAILURE = 24


def load_manifest_auth(manifest_path: str) -> dict[str, str]:
    """Load the identity-domain values from a validated agent manifest.

    Args:
        manifest_path: Path to an agent manifest.

    Returns:
        The domain URL, audience, and scope.

    Raises:
        ValueError: If the manifest is not an IDCS deployment manifest.
    """
    # pylint: disable=import-error,import-outside-toplevel
    from agent_manifest import load_manifest

    manifest: dict[str, Any] = load_manifest(manifest_path)
    if manifest["deploy"]["profile"] != "public-idcs":
        raise ValueError("The manifest profile must be public-idcs.")
    return manifest["deploy"]["auth"]


def token_scope(auth: dict[str, str]) -> str:
    """Return the operator override or the audience-plus-scope default."""
    # U5: use audience plus scope unless the operator supplies the exact scope.
    return os.environ.get(
        "OCI_AGENT_IDCS_TOKEN_SCOPE", auth["audience"] + auth["scope"]
    )


def request_token(auth: dict[str, str], client_id: str, client_secret: str) -> str:
    """Request a client-credentials token without exposing credential values.

    Args:
        auth: Validated identity-domain manifest values.
        client_id: OAuth confidential-application client ID.
        client_secret: OAuth confidential-application client secret.

    Returns:
        The access token returned by the identity domain.

    Raises:
        HTTPError: If the identity domain returns an HTTP error.
        URLError: If the request cannot reach the identity domain.
        ValueError: If a successful response does not contain an access token.
    """
    credentials = base64.b64encode(
        f"{client_id}:{client_secret}".encode("utf-8")
    ).decode("ascii")
    request = Request(
        auth["domain_url"].rstrip("/") + "/oauth2/v1/token",
        data=urlencode(
            {"grant_type": "client_credentials", "scope": token_scope(auth)}
        ).encode("utf-8"),
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urlopen(request, timeout=30) as response:  # nosec B310: manifest URL.
        payload = json.loads(response.read().decode("utf-8"))
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("Identity domain response did not contain an access token.")
    return token


def print_failure(status: str, oauth_error: str) -> int:
    """Print a sanitized token-request failure and return its exit status."""
    print(f"HTTP status: {status}", file=sys.stderr)
    print(f"OAuth error: {oauth_error}", file=sys.stderr)
    return EXIT_TOKEN_FAILURE


def main() -> int:
    """Read credentials and print only a successfully acquired access token."""
    parser = argparse.ArgumentParser(description="Request an IDCS access token.")
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    for name in ("OCI_AGENT_IDCS_CLIENT_ID", "OCI_AGENT_IDCS_CLIENT_SECRET"):
        if not os.environ.get(name):
            print(f"Missing required environment variable: {name}", file=sys.stderr)
            return EXIT_INVALID_INPUT
    try:
        auth = load_manifest_auth(args.manifest)
        token = request_token(
            auth,
            os.environ["OCI_AGENT_IDCS_CLIENT_ID"],
            os.environ["OCI_AGENT_IDCS_CLIENT_SECRET"],
        )
    except HTTPError as error:
        oauth_error = "unavailable"
        try:
            payload = json.loads(error.read().decode("utf-8", errors="replace"))
            value = payload.get("error")
            if isinstance(value, str):
                oauth_error = value
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        return print_failure(str(error.code), oauth_error)
    except (OSError, URLError, ValueError):
        return print_failure("unavailable", "unavailable")
    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
