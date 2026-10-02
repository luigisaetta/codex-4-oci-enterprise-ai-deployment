"""
Author: L. Saetta
Date last modified: 2026-10-02
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


def test_powershell_scripts_import_modules_for_exported_function_calls() -> None:
    """Every script importing a lib export also imports its defining module."""
    modules = sorted((SCRIPTS / "lib").glob("*.psm1"))
    exports_by_module = {}
    for module in modules:
        content = module.read_text(encoding="utf-8")
        match = re.search(r"Export-ModuleMember -Function (.+)", content)
        assert match is not None
        exports_by_module[module.name] = [
            function.strip() for function in match.group(1).split(",")
        ]
    for script in sorted(SCRIPTS.rglob("*.ps1")):
        content = script.read_text(encoding="utf-8")
        for module_name, functions in exports_by_module.items():
            imports_module = module_name in content
            for function in functions:
                if re.search(rf"\b{re.escape(function)}\b", content):
                    assert (
                        imports_module
                    ), f"{script.name} calls {function} without {module_name}"


def test_deploy_hosted_application_release_safety() -> None:
    """Only the explicit failed-deployment case can delete a deployment."""
    content = (SCRIPTS / "deploy_hosted_application.ps1").read_text(encoding="utf-8")
    replacement = content.split("'Replace failed deployment' {", 1)[1].split(
        "'Already released' {", 1
    )[0]
    assert "'delete', '--hosted-deployment-id', $deploymentId, '--force'" in replacement
    assert content.count("'delete'") == 1
    assert "'hosted-application', 'delete'" not in content
    for case in (
        "First release",
        "Already released",
        "New version",
        "Return to a previous version",
        "Creation in progress",
        "Failed deployment",
        "Replace failed deployment",
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
