"""
Author: L. Saetta
Date last modified: 2026-10-14
License: MIT
Description: Shared manifest validation error and schema helpers.
"""

import re
from typing import Any

ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
RESERVED_ENVIRONMENT_NAMES = {"PATH", "HOME", "PYTHONPATH"}


class ManifestError(ValueError):
    """Raised when an agent manifest does not meet the supported contract."""


def fail_unknown_keys(value: dict[str, Any], allowed: set[str], location: str) -> None:
    """Reject keys outside a schema object.

    Args:
        value: Object to validate.
        allowed: Allowed key names.
        location: Human-readable schema location.

    Raises:
        ManifestError: If an unknown key is present.
    """
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ManifestError(
            f"{location} has unsupported field(s): {', '.join(unknown)}"
        )


def require_object(value: Any, location: str) -> dict[str, Any]:
    """Return a mapping or raise a useful manifest validation error."""
    if not isinstance(value, dict):
        raise ManifestError(f"{location} must be an object.")
    return value
