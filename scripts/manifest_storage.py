"""
Author: L. Saetta
Date last modified: 2026-10-14
License: MIT
Description: Validate and expose the managed storage of a manifest (Spec 026).
"""

import re
from typing import Any

if __package__:
    from .manifest_common import (
        ENVIRONMENT_NAME,
        RESERVED_ENVIRONMENT_NAMES,
        ManifestError,
        fail_unknown_keys,
        require_object,
    )
else:
    # Direct script execution puts scripts/ on sys.path.
    from manifest_common import (  # pylint: disable=import-error
        ENVIRONMENT_NAME,
        RESERVED_ENVIRONMENT_NAMES,
        ManifestError,
        fail_unknown_keys,
        require_object,
    )

# Spec 026: managed storage types and the default connect-string variable.
STORAGE_TYPES = {"ADB"}
DEFAULT_STORAGE_ENV = "DB_CONNECT_STRING"
STORAGE_OCID = re.compile(r"^ocid1\.generativeaiapplicationstorage\.[A-Za-z0-9._-]+$")
TOOL_KEY_PREFIXES = ("OCI_", "OCIR_")


def validate_storage(value: Any) -> dict[str, str]:
    """Validate the optional managed storage of the Hosted Application.

    Args:
        value: ``manifest.deploy.storage`` object.

    Returns:
        The validated storage object, with ``connect_env`` filled in.

    Raises:
        ManifestError: If the type is unsupported, the variable name is
            invalid or reserved, or an unknown field is present.
    """
    location = "manifest.deploy.storage"
    storage = require_object(value, location)
    fail_unknown_keys(storage, {"type", "connect_env"}, location)
    if storage.get("type") not in STORAGE_TYPES:
        raise ManifestError(f"{location}.type must be ADB.")
    connect_env = storage.get("connect_env", DEFAULT_STORAGE_ENV)
    if not isinstance(connect_env, str) or not ENVIRONMENT_NAME.fullmatch(connect_env):
        raise ManifestError(f"{location}.connect_env must match ^[A-Z][A-Z0-9_]*$.")
    if connect_env in RESERVED_ENVIRONMENT_NAMES or connect_env.startswith(
        TOOL_KEY_PREFIXES
    ):
        raise ManifestError(
            f"{location}.connect_env is reserved for the tool or the system: "
            f"{connect_env}."
        )
    return {"type": storage["type"], "connect_env": connect_env}


def storage_config(manifest: dict[str, Any]) -> dict[str, str] | None:
    """Describe the managed storage that the deploy needs (Spec 026).

    Args:
        manifest: Validated agent manifest.

    Returns:
        The storage type, connect-string variable, and storage display name,
        or None when the manifest has no storage.
    """
    storage = manifest["deploy"].get("storage")
    if storage is None:
        return None
    return {
        "type": storage["type"],
        "connect_env": storage["connect_env"],
        "display_name": f"{manifest['deploy']['application_name']}-storage",
    }


def storage_configs(manifest: dict[str, Any], storage_id: str) -> list[dict[str, str]]:
    """Build the ``--storage-configs`` JSON of ``hosted-application create``.

    Args:
        manifest: Validated agent manifest with a storage section.
        storage_id: OCID of the managed storage to link.

    Returns:
        The OCI storage configuration list.

    Raises:
        ManifestError: If the manifest has no storage or the OCID is invalid.
    """
    storage = manifest["deploy"].get("storage")
    if storage is None:
        raise ManifestError("manifest.deploy.storage is not defined.")
    if not STORAGE_OCID.fullmatch(storage_id):
        raise ManifestError("The storage identifier must be a storage OCID.")
    return [{"environmentVariableKey": storage["connect_env"], "storageId": storage_id}]


def storage_matches(manifest: dict[str, Any], payload: dict[str, Any]) -> bool:
    """Compare the storage of a Hosted Application with the manifest.

    Args:
        manifest: Validated agent manifest.
        payload: Raw JSON returned by ``hosted-application get``.

    Returns:
        True when both have no storage, or both have one storage with the same
        connect-string variable.
    """
    data = payload.get("data")
    observed = data.get("storage-configs") if isinstance(data, dict) else None
    observed = observed or []
    storage = manifest["deploy"].get("storage")
    if storage is None:
        return not observed
    return (
        isinstance(observed, list)
        and len(observed) == 1
        and isinstance(observed[0], dict)
        and observed[0].get("environment-variable-key") == storage["connect_env"]
    )
