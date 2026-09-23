"""
Author: L. Saetta
Date last modified: 2026-09-23
License: MIT
Description: Keep the Bash and PowerShell lifecycle scripts interchangeable.

The skills document one workflow and let the operator pick the script family
from the current shell. That only works if every Bash option has a PowerShell
parameter with the same name (``--timeout-seconds`` and ``-TimeoutSeconds``)
and every Bash script has a PowerShell twin. This test enforces both.
"""

import re
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
BASH_SCRIPTS = sorted(SCRIPTS.glob("*.sh"))

# Parameters that exist only on one side by design.
POWERSHELL_ONLY = {"container-engine", "help"}
BASH_ONLY = {"help"}


def bash_options(script: Path) -> set[str]:
    """Return the long options advertised by a Bash script's usage() function."""
    text = script.read_text(encoding="utf-8")
    usage = re.search(r"usage\(\)\s*\{(.*?)\}", text, re.DOTALL)
    if usage is None:
        return set()
    return set(re.findall(r"--([a-z][a-z-]*)", usage.group(1))) - BASH_ONLY


def kebab_case(name: str) -> str:
    """Convert a PowerShell parameter name such as TimeoutSeconds to timeout-seconds."""
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def powershell_options(script: Path) -> set[str]:
    """Return the parameters declared in a PowerShell script's param() block."""
    text = script.read_text(encoding="utf-8")
    block = re.search(r"^param\((.*?)^\)", text, re.DOTALL | re.MULTILINE)
    assert block is not None, f"{script.name} must declare a multi-line param() block"
    names = re.findall(r"\]\$(\w+)", block.group(1))
    return {kebab_case(name) for name in names} - POWERSHELL_ONLY


@pytest.mark.parametrize("bash_script", BASH_SCRIPTS, ids=lambda path: path.name)
def test_every_bash_script_has_a_powershell_twin(bash_script: Path) -> None:
    """A skill can name one operation and trust that both shells provide it."""
    assert (SCRIPTS / f"{bash_script.stem}.ps1").is_file()


@pytest.mark.parametrize("bash_script", BASH_SCRIPTS, ids=lambda path: path.name)
def test_powershell_parameters_mirror_bash_options(bash_script: Path) -> None:
    """Options match one-to-one apart from the prefix and the documented extras."""
    powershell_script = SCRIPTS / f"{bash_script.stem}.ps1"
    if not powershell_script.is_file():
        pytest.skip("twin script is covered by the previous test")
    assert powershell_options(powershell_script) == bash_options(bash_script)
