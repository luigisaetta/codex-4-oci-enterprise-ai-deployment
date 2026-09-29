"""
Author: L. Saetta
Date last modified: 2026-09-29
License: MIT
Description: Statically enforce safe PowerShell interpreter and config handling.
"""

import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
POWERSHELL_FILES = sorted([*SCRIPTS.rglob("*.ps1"), *SCRIPTS.rglob("*.psm1")])


def test_powershell_uses_the_selected_python_interpreter() -> None:
    """PowerShell files contain no legacy direct Python discovery or invocation."""
    for path in POWERSHELL_FILES:
        content = path.read_text(encoding="utf-8")
        assert "& python" not in content
        assert "Get-Command python" not in content
        assert re.search(r"foreach\s*\(\$tool.*'python'", content) is None
        assert "Test-PythonAvailable" not in content


def test_powershell_never_evaluates_tenancy_configuration() -> None:
    """PowerShell files must not evaluate configuration content as source code."""
    for path in POWERSHELL_FILES:
        content = path.read_text(encoding="utf-8")
        assert "Invoke-Expression" not in content
        assert re.search(r"\biex\b", content, re.IGNORECASE) is None
