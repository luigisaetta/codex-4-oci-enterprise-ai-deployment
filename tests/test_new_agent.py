"""
Author: L. Saetta
Date last modified: 2026-10-01
License: MIT
Description: Offline tests for agent planning, rendering, and safe configuration checks.
"""

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from scripts import new_agent, tool_config
from scripts.agent_manifest import load_manifest

TOOL_HOME = Path(__file__).resolve().parents[1]
SCRIPT = TOOL_HOME / "scripts" / "new_agent.py"
FILES = """
agent.yaml Dockerfile .dockerignore .gitignore requirements.txt
sample_agent/__init__.py sample_agent/app.py sample_agent/agent.py
""".split()
TENANCY_VALUES = {
    "OCI_REGION": "file-region-marker",
    "OCI_COMPARTMENT_NAME": "file-compartment-marker",
    "OCIR_TENANCY_NAMESPACE": "file-namespace-marker",
    "OCIR_USERNAME": "file-user-marker",
}


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep tests independent of operator tenancy settings and allowed roots."""
    for key in tool_config.ALLOWED_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("OCI_AGENT_ALLOWED_ROOTS", raising=False)
    monkeypatch.setenv("OCI_AGENT_ENV_FILE", str(tmp_path / "tenancy.env"))


def run_helper(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the real helper CLI without network or cloud credentials.

    Args:
        *arguments: CLI arguments.
        cwd: Agent working directory.

    Returns:
        Captured process result and exit status.
    """
    return subprocess.run(
        [sys.executable, str(SCRIPT), *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def write_tenancy(tmp_path: Path, values: dict[str, str]) -> Path:
    """Write a temporary, non-secret tenancy fixture.

    Args:
        tmp_path: Temporary directory selected by the isolation fixture.
        values: Fixture settings.

    Returns:
        Path to the selected tenancy file.
    """
    path = tmp_path / "tenancy.env"
    path.write_text(
        "".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8"
    )
    return path


def test_plan_lists_files_and_writes_nothing(tmp_path: Path) -> None:
    """Default values and every future file appear without side effects."""
    result = run_helper("plan", "--name", "SampleAgent", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert f"Target: {tmp_path.resolve()}" in result.stdout
    assert "Name: SampleAgent" in result.stdout
    assert "Package: sample_agent" in result.stdout
    assert "Repository: agents/sampleagent" in result.stdout
    assert [
        line for line in result.stdout.splitlines() if line.startswith("Create:")
    ] == [f"Create: {filename}" for filename in FILES]
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("command", ["plan", "render"])
@pytest.mark.parametrize("filename", [name for name in FILES if name != ".gitignore"])
def test_conflicts_leave_every_file_unchanged(
    tmp_path: Path, command: str, filename: str
) -> None:
    """Even files reserved for later authoring block all helper writes."""
    conflict = tmp_path / filename
    conflict.parent.mkdir(parents=True, exist_ok=True)
    conflict.write_text("original content\n", encoding="utf-8")
    result = run_helper(command, "--name", "SampleAgent", cwd=tmp_path)
    assert result.returncode == 30
    assert f"Conflict: {filename}" in result.stdout
    assert conflict.read_text(encoding="utf-8") == "original content\n"
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == [conflict]


@pytest.mark.parametrize("command", ["plan", "render"])
def test_existing_gitignore_reports_exact_missing_entries(
    tmp_path: Path, command: str
) -> None:
    """Missing entries are advisory and existing bytes, including CRLF, survive."""
    path = tmp_path / ".gitignore"
    original = (
        b"# Existing rules\r\n __pycache__ \r\n*.py[cod]/\r\n"
        b".pytest_cache\r\n.venv/\r\n# .env\r\n.env*\r\n"
    )
    path.write_bytes(original)
    result = run_helper(command, "--name", "SampleAgent", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Keep: .gitignore" in result.stdout.splitlines()
    assert "Create: .gitignore" not in result.stdout
    assert [
        line for line in result.stdout.splitlines() if line.startswith("Missing")
    ] == ["Missing .gitignore entries: .env, .env.*"]
    assert path.read_bytes() == original
    expected = FILES[:4] if command == "render" else [".gitignore"]
    assert sorted(item.name for item in tmp_path.iterdir()) == sorted(expected)


@pytest.mark.parametrize("command", ["plan", "render"])
def test_existing_gitignore_with_all_entries(tmp_path: Path, command: str) -> None:
    """Whitespace, comments, and optional trailing slashes count as exact entries."""
    path = tmp_path / ".gitignore"
    original = (
        b"# Comment\n __pycache__ \n *.py[cod]/ \n# Another comment\n"
        b" .pytest_cache \n .venv \n .env/ \n .env.*/ \n"
    )
    path.write_bytes(original)
    result = run_helper(command, "--name", "SampleAgent", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "Keep: .gitignore" in result.stdout.splitlines()
    assert "Missing .gitignore entries:" not in result.stdout
    assert path.read_bytes() == original


@pytest.mark.parametrize("command", ["plan", "render"])
@pytest.mark.parametrize("kind", ["directory", "symlink", "dangling-symlink"])
def test_gitignore_non_regular_entries_conflict(
    tmp_path: Path, command: str, kind: str
) -> None:
    """Directories and symlinks never receive the regular-file exception."""
    path = tmp_path / ".gitignore"
    if kind == "directory":
        path.mkdir()
    else:
        destination = tmp_path / "existing.ignore"
        if kind == "symlink":
            destination.write_bytes(b"keep destination\n")
        path.symlink_to(destination)
    before = sorted(tmp_path.iterdir())
    result = run_helper(command, "--name", "SampleAgent", cwd=tmp_path)
    assert result.returncode == 30
    assert "Conflict: .gitignore" in result.stdout.splitlines()
    assert sorted(tmp_path.iterdir()) == before
    if kind == "directory":
        assert path.is_dir()
    else:
        assert path.is_symlink()
        if kind == "symlink":
            assert path.read_bytes() == b"keep destination\n"


@pytest.mark.parametrize("keep_gitignore", [False, True])
def test_failed_final_validation_removes_only_created_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, keep_gitignore: bool
) -> None:
    """Invalid allowed roots roll back new files and preserve the kept ignore file."""
    original = b"# keep these bytes\r\n.env\r\n"
    if keep_gitignore:
        (tmp_path / ".gitignore").write_bytes(original)
    monkeypatch.setenv("OCI_AGENT_ALLOWED_ROOTS", str(tmp_path / "absent-root"))
    result = run_helper("render", "--name", "SampleAgent", cwd=tmp_path)
    assert result.returncode == 64
    assert (
        "OCI_AGENT_ALLOWED_ROOTS must contain absolute existing directories"
        in result.stderr
    )
    expected = [tmp_path / ".gitignore"] if keep_gitignore else []
    assert list(tmp_path.iterdir()) == expected
    if keep_gitignore:
        assert (tmp_path / ".gitignore").read_bytes() == original


@pytest.mark.parametrize("failure", ["open", "write", "conflict"])
def test_failed_writing_rolls_back_owned_files(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    """Open/write failures clean partial output; late conflicts remain untouched."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_bytes(b"# original\r\n")
    original_open = Path.open

    def failing_open(path, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if path == tmp_path / "Dockerfile" and mode == "x":
            if failure == "open":
                raise OSError("simulated open failure")
            if failure == "conflict":
                with original_open(path, "w", encoding="utf-8") as existing:
                    existing.write("late existing file\n")
                raise FileExistsError("simulated conflict")
            # The helper closes the returned handle in its own context manager.
            # pylint: disable-next=consider-using-with
            output = original_open(path, *args, **kwargs)
            original_write = output.write

            def failing_write(content):
                original_write(content[:5])
                raise OSError("simulated write failure")

            monkeypatch.setattr(output, "write", failing_write)
            return output
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", failing_open)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT), "render", "--name", "SampleAgent", "--target", str(tmp_path)],
    )
    assert new_agent.main() == (30 if failure == "conflict" else 64)
    expected = [".gitignore", "Dockerfile"] if failure == "conflict" else [".gitignore"]
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(expected)
    assert gitignore.read_bytes() == b"# original\r\n"
    if failure == "conflict":
        assert (tmp_path / "Dockerfile").read_text(
            encoding="utf-8"
        ) == "late existing file\n"


def test_cleanup_failure_reports_remaining_file_and_original_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed removal does not suppress validation failure or stop other cleanup."""
    gitignore = tmp_path / ".gitignore"
    gitignore.write_bytes(b"# original\n")
    manifest = tmp_path / "agent.yaml"
    original_unlink = Path.unlink

    def failing_unlink(path, *args, **kwargs):
        if path == manifest:
            raise OSError("simulated removal failure")
        return original_unlink(path, *args, **kwargs)

    def failing_validation(_path):
        raise ValueError("original validation failure")

    monkeypatch.setattr(Path, "unlink", failing_unlink)
    monkeypatch.setattr(new_agent.agent_manifest, "load_manifest", failing_validation)
    monkeypatch.setattr(
        sys,
        "argv",
        [str(SCRIPT), "render", "--name", "SampleAgent", "--target", str(tmp_path)],
    )
    assert new_agent.main() == 64
    errors = capsys.readouterr().err
    assert f"file remains at {manifest}" in errors
    assert "simulated removal failure" in errors
    assert "original validation failure" in errors
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        ".gitignore",
        "agent.yaml",
    ]
    assert gitignore.read_bytes() == b"# original\n"


@pytest.mark.parametrize("command", ["plan", "render"])
def test_invalid_derived_package_suggests_explicit_package(
    tmp_path: Path, command: str
) -> None:
    """A numeric name is valid for the manifest but needs an explicit package."""
    result = run_helper(command, "--name", "123", cwd=tmp_path)
    assert result.returncode == 64
    assert "package name derived from --name is invalid" in result.stderr
    assert "pass --package explicitly" in result.stderr
    assert not list(tmp_path.iterdir())
    result = run_helper(command, "--name", "123", "--package", "123", cwd=tmp_path)
    assert result.returncode == 64
    assert "Invalid --package;" in result.stderr
    assert "derived" not in result.stderr


@pytest.mark.parametrize("name", ["SampleAgent", "true", "123"])
def test_render_only_fixed_files_and_validate(tmp_path: Path, name: str) -> None:
    """Rendering preserves string names, template content, and the empty checks."""
    result = run_helper(
        "render",
        "--name",
        name,
        "--package",
        "sample_agent",
        "--repository",
        "custom/sample",
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted(FILES[:4])
    for filename in FILES[:4]:
        assert "{{" not in (tmp_path / filename).read_text(encoding="utf-8")
    assert (tmp_path / ".dockerignore").read_bytes() == (
        new_agent.ASSETS / "dockerignore.template"
    ).read_bytes()
    assert (tmp_path / ".gitignore").read_text(encoding="utf-8") == (
        "__pycache__/\n*.py[cod]\n.pytest_cache/\n.venv/\n.env\n.env.*\n"
    )
    manifest = load_manifest(str(tmp_path / "agent.yaml"))
    assert manifest["name"] == name
    assert manifest["deploy"] == {"application_name": name, "profile": "public-noauth"}
    assert manifest["publish"]["repository"] == "custom/sample"
    assert manifest["verify"] == []
    raw = yaml.safe_load((tmp_path / "agent.yaml").read_text(encoding="utf-8"))
    assert "runtime" not in raw
    dockerfile = (tmp_path / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY requirements.txt ./requirements.txt" in dockerfile
    assert "COPY sample_agent/ ./sample_agent/" in dockerfile
    assert '"sample_agent.app:app"' in dockerfile
    validated = subprocess.run(
        [
            sys.executable,
            str(TOOL_HOME / "scripts/agent_manifest.py"),
            "validate",
            "--manifest",
            str(tmp_path / "agent.yaml"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert validated.returncode == 0, validated.stderr


def test_check_manifest_requires_one_valid_check(tmp_path: Path) -> None:
    """An author must add a functional check after rendering the fixed files."""
    assert run_helper("render", "--name", "SampleAgent", cwd=tmp_path).returncode == 0
    path = tmp_path / "agent.yaml"
    result = run_helper("check-manifest", "--manifest", str(path), cwd=tmp_path)
    assert result.returncode == 64
    assert "Add at least one functional check" in result.stderr
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    manifest["verify"] = [
        {"method": "POST", "path": "/analyze", "body": {}, "expect_status": 200}
    ]
    path.write_text(yaml.safe_dump(manifest), encoding="utf-8")
    result = run_helper("check-manifest", "--manifest", str(path), cwd=tmp_path)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("command", ["plan", "render"])
@pytest.mark.parametrize(
    "arguments",
    [
        ["--name", "bad name"],
        ["--name", "-bad"],
        ["--repository", "Agents/sample"],
        ["--repository", "agents//sample"],
        ["--package", "tests"],
        ["--package", "class"],
        ["--package", "Upper"],
        ["--package", "bad-name"],
        ["--package", ""],
        ["--name", "123"],
    ],
)
def test_invalid_values_write_nothing(
    tmp_path: Path, command: str, arguments: list[str]
) -> None:
    """Invalid defaults, explicit values, and excluded packages fail safely."""
    result = run_helper(command, "--name", "SampleAgent", *arguments, cwd=tmp_path)
    assert result.returncode == 64
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("command", ["plan", "render"])
@pytest.mark.parametrize("relative", ["", "demos", "missing/agent"])
def test_tool_home_targets_rejected(
    tmp_path: Path, command: str, relative: str
) -> None:
    """Both existing and absent targets inside the tool home are forbidden."""
    result = run_helper(
        command, "--name", "sample", "--target", str(TOOL_HOME / relative), cwd=tmp_path
    )
    assert result.returncode == 64
    assert "outside the tool home" in result.stderr


def test_symlink_targets_resolved(tmp_path: Path) -> None:
    """Symlink aliases cannot bypass containment and valid aliases are resolved."""
    alias = tmp_path / "tool-link"
    alias.symlink_to(TOOL_HOME, target_is_directory=True)
    result = run_helper(
        "plan", "--name", "sample", "--target", str(alias), cwd=tmp_path
    )
    assert result.returncode == 64
    target = tmp_path / "agent"
    target.mkdir()
    alias.unlink()
    alias.symlink_to(target, target_is_directory=True)
    result = run_helper(
        "plan", "--name", "sample", "--target", str(alias), cwd=tmp_path
    )
    assert result.returncode == 0
    assert f"Target: {target.resolve()}" in result.stdout
    assert not list(target.iterdir())


def test_package_exclusions_read_from_template(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """C8 derives exclusions from the template instead of a copied list."""
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "dockerignore.template").write_text("custom_*\n", encoding="utf-8")
    monkeypatch.setattr(new_agent, "ASSETS", assets)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(SCRIPT),
            "plan",
            "--name",
            "sample",
            "--package",
            "custom_agent",
            "--target",
            str(tmp_path),
        ],
    )
    assert new_agent.main() == 64


def test_check_env_only_reports_key_names(tmp_path: Path) -> None:
    """Missing and placeholder keys are reported without any file value."""
    values = dict(TENANCY_VALUES)
    del values["OCI_REGION"]
    values["OCIR_USERNAME"] = "replace-with-private-marker"
    path = write_tenancy(tmp_path, values)
    original = path.read_bytes()
    result = run_helper("check-env", cwd=tmp_path)
    assert result.returncode == 31
    output = result.stdout + result.stderr
    assert str(path) in output
    assert "Missing configuration key(s): OCI_REGION" in output
    assert "Placeholder configuration key(s): OCIR_USERNAME" in output
    assert all(value not in output for value in values.values())
    assert path.read_bytes() == original


def test_check_env_complete_file(tmp_path: Path) -> None:
    """Complete file settings pass without exposing their contents."""
    path = write_tenancy(tmp_path, TENANCY_VALUES)
    result = run_helper("check-env", cwd=tmp_path)
    assert result.returncode == 0
    assert str(path) in result.stdout
    assert all(
        value not in result.stdout + result.stderr for value in TENANCY_VALUES.values()
    )


def test_check_env_environment_precedence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Environment settings override file settings, including placeholders."""
    values = dict(TENANCY_VALUES, OCI_REGION="replace-with-file-marker")
    write_tenancy(tmp_path, values)
    monkeypatch.setenv("OCI_REGION", "environment-marker")
    assert run_helper("check-env", cwd=tmp_path).returncode == 0
    monkeypatch.setenv("OCI_REGION", "replace-with-env-marker")
    result = run_helper("check-env", cwd=tmp_path)
    assert result.returncode == 31
    assert "OCI_REGION" in result.stderr
    assert "replace-with-env-marker" not in result.stdout + result.stderr
    assert tool_config.configuration_issues(values) == ([], ["OCI_REGION"])


def test_missing_file_fails_even_with_complete_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Spec 011 requires the selected file to exist independently of the keys."""
    for key, value in TENANCY_VALUES.items():
        monkeypatch.setenv(key, value)
    result = run_helper("check-env", cwd=tmp_path)
    assert result.returncode == 31
    assert "Configuration file is missing" in result.stderr


@pytest.mark.parametrize("content", [b"OCI_REGION=\n", b"OCI_REGION=\xff\n"])
def test_check_env_empty_or_unreadable_file(tmp_path: Path, content: bytes) -> None:
    """Empty settings and malformed UTF-8 fail without leaking a decode exception."""
    (tmp_path / "tenancy.env").write_bytes(content)
    result = run_helper("check-env", cwd=tmp_path)
    assert result.returncode == 31
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "arguments",
    [[], ["plan"], ["unknown"], ["check-manifest"], ["check-env", "--unknown"]],
)
def test_invalid_arguments_exit_64(tmp_path: Path, arguments: list[str]) -> None:
    """Argparse failures share the manifest invalid-input exit code."""
    assert run_helper(*arguments, cwd=tmp_path).returncode == 64
