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


def test_deploy_hosted_application_release_safety() -> None:
    """The deployer supports every release case without deleting resources."""
    content = (SCRIPTS / "deploy_hosted_application.ps1").read_text(encoding="utf-8")
    assert re.search(r"\bdelete\b", content, re.IGNORECASE) is None
    for case in (
        "First release",
        "Already released",
        "New version",
        "Return to a previous version",
    ):
        assert case in content
    assert "add-artifact-create-single-docker-artifact-details" in content
    assert "'hosted-deployment', 'update'" in content
    assert "Get-ManifestDeploymentName" not in content


def test_powershell_idcs_paths_avoid_secret_command_arguments() -> None:
    """PowerShell deploy and verify scripts contain the supported IDCS flow."""
    deploy = (SCRIPTS / "deploy_hosted_application.ps1").read_text(encoding="utf-8")
    verify = (SCRIPTS / "verify_deployment.ps1").read_text(encoding="utf-8")
    assert re.search(r"inbound-auth\s+--manifest \$Manifest", deploy)
    assert re.search(r"inbound-auth-matches\s+--manifest \$Manifest", deploy)
    assert re.search(r"inbound-auth-matches\s+--manifest \$Manifest", verify)
    assert "idcs_token.py" in verify
    assert "Fail 24" in verify
    assert "Fail 25" in verify
    assert "OCI_AGENT_ACCESS_TOKEN" in verify
    token_invocation = verify[
        verify.index("idcs_token.py") - 200 : verify.index("idcs_token.py") + 200
    ]
    assert "Bearer" not in token_invocation
    assert "OCI_AGENT_IDCS_CLIENT_SECRET" not in token_invocation
