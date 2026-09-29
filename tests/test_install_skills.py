"""
Author: L. Saetta
Date last modified: 2026-09-29
License: MIT
Description: Verify user-scope skill installers without changing the real user scope.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SKILLS = sorted(path.parent for path in (ROOT / "skills").glob("*/SKILL.md"))
BASH = shutil.which("bash")
PWSH = shutil.which("pwsh")


def run_bash(arguments: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the Bash installer outside the repository.

    Args:
        arguments: Installer options excluding the script path.
        cwd: Temporary external working directory.

    Returns:
        Completed Bash installer process.
    """
    return subprocess.run(
        [BASH, str(SCRIPTS / "install_skills.sh"), *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.skipif(BASH is None, reason="Bash is unavailable.")
def test_bash_installer_install_repeat_conflicts_and_uninstall(tmp_path: Path) -> None:
    """The Bash installer handles each target state without overwriting entries."""
    target = tmp_path / "target"
    first = run_bash(["--target", str(target)], tmp_path)
    assert first.returncode == 0
    for skill in SKILLS:
        assert (target / skill.name).resolve() == skill.resolve()

    repeated = run_bash(["--target", str(target)], tmp_path)
    assert repeated.returncode == 0
    assert "unchanged:" in repeated.stdout

    foreign = target / "foreign"
    foreign.mkdir()
    removed = run_bash(["--uninstall", "--target", str(target)], tmp_path)
    assert removed.returncode == 0
    assert foreign.is_dir()
    assert all(not (target / skill.name).exists() for skill in SKILLS)


@pytest.mark.skipif(BASH is None, reason="Bash is unavailable.")
def test_bash_installer_keeps_foreign_folder_and_link_conflicts(tmp_path: Path) -> None:
    """Foreign paths with a skill name remain untouched while other skills install."""
    target = tmp_path / "target"
    target.mkdir()
    conflict_skill = SKILLS[0]
    foreign_folder = target / conflict_skill.name
    foreign_folder.mkdir()
    folder_result = run_bash(["--target", str(target)], tmp_path)
    assert folder_result.returncode == 1
    assert foreign_folder.is_dir()
    assert all((target / skill.name).is_symlink() for skill in SKILLS[1:])

    other_target = tmp_path / "other"
    link_target = tmp_path / "link-target"
    link_target.mkdir()
    other_target.mkdir()
    (other_target / conflict_skill.name).symlink_to(
        link_target, target_is_directory=True
    )
    link_result = run_bash(["--target", str(other_target)], tmp_path)
    assert link_result.returncode == 1
    assert (other_target / conflict_skill.name).resolve() == link_target.resolve()


@pytest.mark.skipif(BASH is None, reason="Bash is unavailable.")
def test_bash_installer_dry_run_and_unknown_option(tmp_path: Path) -> None:
    """Dry runs leave missing targets absent and bad options use exit code 64."""
    target = tmp_path / "missing-target"
    dry_run = run_bash(["--dry-run", "--target", str(target)], tmp_path)
    assert dry_run.returncode == 0
    assert not target.exists()

    unknown = run_bash(["--unknown", "--target", str(target)], tmp_path)
    assert unknown.returncode == 64


@pytest.mark.skipif(PWSH is None, reason="pwsh is unavailable.")
def test_powershell_installer_has_matching_safe_lifecycle(tmp_path: Path) -> None:
    """The PowerShell installer creates, preserves, and removes only own links."""
    target = tmp_path / "target"
    script = SCRIPTS / "install_skills.ps1"
    command = [PWSH, "-NoProfile", "-File", str(script), "-Target", str(target)]
    first = subprocess.run(
        command, cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert first.returncode == 0
    repeated = subprocess.run(
        command, cwd=tmp_path, capture_output=True, text=True, check=False
    )
    assert repeated.returncode == 0
    assert "unchanged:" in repeated.stdout
    foreign = target / "foreign"
    foreign.mkdir()
    removed = subprocess.run(
        [
            PWSH,
            "-NoProfile",
            "-File",
            str(script),
            "-Uninstall",
            "-Target",
            str(target),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert removed.returncode == 0
    assert foreign.is_dir()
