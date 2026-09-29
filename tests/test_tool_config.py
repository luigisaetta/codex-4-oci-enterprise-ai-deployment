"""
Author: L. Saetta
Date last modified: 2026-09-29
License: MIT
Description: Unit tests for non-secret OCI tenancy configuration loading.
"""

import subprocess
import sys
from pathlib import Path

import pytest

TOOL_CONFIG = Path(__file__).resolve().parents[1] / "scripts/tool_config.py"


@pytest.fixture(autouse=True)
def clear_configuration_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent operator configuration from influencing configuration tests."""
    monkeypatch.delenv("OCI_AGENT_ENV_FILE", raising=False)
    monkeypatch.delenv("OCI_AGENT_PYTHON", raising=False)
    monkeypatch.delenv("OCI_AGENT_ALLOWED_ROOTS", raising=False)
    monkeypatch.delenv("OCI_REGION", raising=False)
    monkeypatch.delenv("OCI_COMPARTMENT_NAME", raising=False)
    monkeypatch.delenv("OCIR_TENANCY_NAMESPACE", raising=False)
    monkeypatch.delenv("OCIR_USERNAME", raising=False)


def run_tool_config(*keys: str) -> subprocess.CompletedProcess[str]:
    """Run the configuration command with the current isolated environment.

    Args:
        *keys: Requested tenancy keys.

    Returns:
        Completed process containing output and exit status.
    """
    return subprocess.run(
        [sys.executable, str(TOOL_CONFIG), "env", "--keys", *keys],
        capture_output=True,
        text=True,
        check=False,
    )


def test_configuration_parses_comments_quotes_and_allowed_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Comments, blanks, quotes, and unrelated keys are handled safely."""
    configuration = tmp_path / "tenancy.env"
    configuration.write_text(
        """# comment

OCI_REGION = 'eu-frankfurt-1'
OCI_COMPARTMENT_NAME="target compartment"
CODE_AUTHOR=not-exported
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("OCI_AGENT_ENV_FILE", str(configuration))

    result = run_tool_config("OCI_REGION", "OCI_COMPARTMENT_NAME")

    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "OCI_REGION=eu-frankfurt-1",
        "OCI_COMPARTMENT_NAME=target compartment",
    ]
    assert "CODE_AUTHOR" not in result.stdout


def test_environment_value_takes_precedence_and_is_not_printed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exported non-empty values override file values without being emitted."""
    configuration = tmp_path / "tenancy.env"
    configuration.write_text(
        "OCI_REGION=file-region\nOCI_COMPARTMENT_NAME=file-compartment\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OCI_AGENT_ENV_FILE", str(configuration))
    monkeypatch.setenv("OCI_REGION", "environment-region")

    result = run_tool_config("OCI_REGION", "OCI_COMPARTMENT_NAME")

    assert result.returncode == 0
    assert result.stdout == "OCI_COMPARTMENT_NAME=file-compartment\n"


def test_configured_environment_file_is_honored(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OCI_AGENT_ENV_FILE selects the file used for requested values."""
    configuration = tmp_path / "selected.env"
    configuration.write_text("OCIR_USERNAME=selected-user\n", encoding="utf-8")
    monkeypatch.setenv("OCI_AGENT_ENV_FILE", str(configuration))

    result = run_tool_config("OCIR_USERNAME")

    assert result.returncode == 0
    assert result.stdout == "OCIR_USERNAME=selected-user\n"


def test_missing_keys_name_the_file_without_printing_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Missing requested values are safe configuration errors."""
    configuration = tmp_path / "missing.env"
    monkeypatch.setenv("OCI_AGENT_ENV_FILE", str(configuration))

    result = run_tool_config("OCI_REGION", "OCIR_USERNAME")

    assert result.returncode == 64
    assert "OCI_REGION, OCIR_USERNAME" in result.stderr
    assert str(configuration) in result.stderr
    assert "value" not in result.stderr.lower()


def test_missing_file_is_allowed_when_environment_has_every_requested_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A configuration file is optional when requested values are exported."""
    monkeypatch.setenv("OCI_AGENT_ENV_FILE", str(tmp_path / "absent.env"))
    monkeypatch.setenv("OCI_REGION", "environment-region")

    result = run_tool_config("OCI_REGION")

    assert result.returncode == 0
    assert not result.stdout


def test_configuration_value_is_not_evaluated_as_shell_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A command-substitution-looking value remains literal text."""
    injected = tmp_path / "INJECTED"
    configuration = tmp_path / "tenancy.env"
    configuration.write_text(f"OCI_REGION=$(touch {injected})\n", encoding="utf-8")
    monkeypatch.setenv("OCI_AGENT_ENV_FILE", str(configuration))

    result = run_tool_config("OCI_REGION")

    assert result.returncode == 0
    assert result.stdout == f"OCI_REGION=$(touch {injected})\n"
    assert not injected.exists()


def test_unknown_requested_key_is_rejected() -> None:
    """Only the four supported tenancy keys can be requested."""
    result = run_tool_config("CODE_AUTHOR")

    assert result.returncode == 64
    assert "Unsupported configuration key" in result.stderr
