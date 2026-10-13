"""
Author: L. Saetta
Date last modified: 2026-10-13
License: MIT
Description: Static checks for the oci-agent-ui skill and its Next.js template.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "oci-agent-ui"
TEMPLATE = SKILL / "assets" / "ui-template"
TEMPLATE_FILES = sorted(path for path in TEMPLATE.rglob("*") if path.is_file())


def template_text() -> dict[str, str]:
    """Return the text of every template file, keyed by relative path.

    Returns:
        Template contents.
    """
    return {
        str(path.relative_to(TEMPLATE)): path.read_text(encoding="utf-8")
        for path in TEMPLATE_FILES
    }


def test_template_has_the_expected_files() -> None:
    """The template holds the bridge, the generic page, and its configuration."""
    names = set(template_text())
    for expected in (
        "package.json",
        "next.config.mjs",
        ".gitignore",
        ".env.local.example",
        "README.md",
        "app/layout.jsx",
        "app/page.jsx",
        "app/globals.css",
        "app/demo-config.js",
        "app/api/agent/route.js",
        "app/api/agent/idcs-token.js",
    ):
        assert expected in names


def test_template_contains_no_address_ocid_or_secret() -> None:
    """Addresses live only in .env.local; examples use placeholders."""
    for name, content in template_text().items():
        assert (
            re.search(r"ocid1\.[a-z]+\.oc1\.[a-z0-9-]*\.[a-z0-9]{10,}", content) is None
        ), name
        for match in re.findall(r"https://[^\s\"'`)]+", content):
            assert "<" in match or match.startswith("https://nodejs.org"), (name, match)
        assert (
            re.search(r"(?i)(api[_-]?key|password|secret)\s*[:=]\s*\S", content) is None
        ), name


def test_bridge_reads_the_address_from_the_environment() -> None:
    """The API route forwards to AGENT_BASE_URL + AGENT_PATH only."""
    route = (TEMPLATE / "app/api/agent/route.js").read_text(encoding="utf-8")
    assert "process.env.AGENT_BASE_URL" in route
    assert "process.env.AGENT_PATH" in route
    assert "status === 400 || upstream.status === 422" in route
    page = (TEMPLATE / "app/page.jsx").read_text(encoding="utf-8")
    assert 'fetch("/api/agent"' in page
    assert "AGENT_BASE_URL" not in page


def test_server_listens_only_on_loopback() -> None:
    """The dev and start scripts bind to 127.0.0.1."""
    scripts = json.loads((TEMPLATE / "package.json").read_text(encoding="utf-8"))[
        "scripts"
    ]
    assert "--hostname 127.0.0.1" in scripts["dev"]
    assert "--hostname 127.0.0.1" in scripts["start"]


def test_env_example_holds_placeholders_and_git_ignores_env_local() -> None:
    """The example configuration is safe; the real one is never committed."""
    example = (TEMPLATE / ".env.local.example").read_text(encoding="utf-8")
    assert "AGENT_BASE_URL=http://127.0.0.1:8080" in example
    assert "AGENT_PATH=/replace-with-agent-path" in example
    ignored = (TEMPLATE / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in ("node_modules/", ".next/", ".env.local"):
        assert entry in ignored


def test_technical_view_is_off_by_default() -> None:
    """The default configuration shows no technical data."""
    config = (TEMPLATE / "app/demo-config.js").read_text(encoding="utf-8")
    assert "technicalView: false" in config


def test_agent_images_exclude_the_ui() -> None:
    """The Dockerfile template's ignore list keeps the UI out of agent images."""
    entries = (
        (ROOT / "skills/oci-agent-build/assets/dockerignore.template")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert "ui" in entries
    assert "**/node_modules" in entries


def test_skill_documents_the_end_user_rules_and_links() -> None:
    """The skill links its specification, guidelines, and UI spec template."""
    content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for link in (
        "../../specs/018-skill-oci-agent-ui.md",
        "references/ui-guidelines.md",
        "assets/ui-spec.template.md",
    ):
        assert f"]({link})" in content
    guidelines = (SKILL / "references/ui-guidelines.md").read_text(encoding="utf-8")
    for rule in ("E1.", "E3.", "E6.", "T2.", "T3.", "T4."):
        assert f"**{rule}" in guidelines


def test_idcs_values_are_server_side_and_documented() -> None:
    """The bridge reads the IDCS entries on the server only (Spec 022)."""
    sources = template_text()
    token_module = sources["app/api/agent/idcs-token.js"]
    for name in (
        "IDCS_DOMAIN_URL",
        "IDCS_TOKEN_SCOPE",
        "IDCS_CLIENT_ID",
        "IDCS_CLIENT_SECRET",
    ):
        assert name in token_module
        assert f"# {name}=" in sources[".env.local.example"]
    assert "./idcs-token.js" in sources["app/api/agent/route.js"]
    for name, content in sources.items():
        assert "NEXT_PUBLIC_" not in content, name
    assert "console" not in token_module


NODE_SCENARIO = r"""
import http from "node:http";
const { accessToken, discardToken, tokenRequired } = await import(process.argv[2]);
const seen = [];
const server = http.createServer((request, response) => {
  let body = "";
  request.on("data", (chunk) => { body += chunk; });
  request.on("end", () => {
    seen.push({ path: request.url, auth: request.headers.authorization, body });
    response.setHeader("Content-Type", "application/json");
    if (body.includes("bad-scope")) {
      response.statusCode = 400;
      response.end(JSON.stringify({ error: "invalid_scope" }));
      return;
    }
    response.end(JSON.stringify({ access_token: `token-${seen.length}`, expires_in: 3600 }));
  });
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const env = {
  IDCS_DOMAIN_URL: `http://127.0.0.1:${server.address().port}/`,
  IDCS_TOKEN_SCOPE: "https://aud/invoke",
  IDCS_CLIENT_ID: "cid",
  IDCS_CLIENT_SECRET: "csecret",
};
const results = { required: tokenRequired(env), notRequired: tokenRequired({}) };
results.first = await accessToken(env, 1000);
results.cached = await accessToken(env, 2000);
results.expired = await accessToken(env, 1000 + 3600 * 1000);
discardToken();
results.afterDiscard = await accessToken(env, 5000);
discardToken();
try { await accessToken({ ...env, IDCS_TOKEN_SCOPE: "bad-scope" }, 6000); }
catch (error) { results.badScope = error.message; }
discardToken();
try { await accessToken({ ...env, IDCS_CLIENT_SECRET: "" }, 7000); }
catch (error) { results.missing = error.message; }
results.requests = seen;
server.close();
console.log(JSON.stringify(results));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is unavailable.")
def test_idcs_token_module_requests_caches_and_refreshes(tmp_path: Path) -> None:
    """The token module uses Basic credentials, caches, and refreshes (Spec 022)."""
    script = tmp_path / "scenario.mjs"
    script.write_text(NODE_SCENARIO, encoding="utf-8")
    module = (TEMPLATE / "app/api/agent/idcs-token.js").as_uri()
    result = subprocess.run(
        ["node", str(script), module],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    results = json.loads(result.stdout)

    assert results["required"] is True and results["notRequired"] is False
    assert results["first"] == "token-1"
    assert results["cached"] == "token-1"
    assert results["expired"] == "token-2"
    assert results["afterDiscard"] == "token-3"
    assert "HTTP 400" in results["badScope"] and "invalid_scope" in results["badScope"]
    assert "IDCS_CLIENT_SECRET" in results["missing"]
    first = results["requests"][0]
    assert first["path"] == "/oauth2/v1/token"
    assert first["auth"] == "Basic Y2lkOmNzZWNyZXQ="
    assert "grant_type=client_credentials" in first["body"]
    assert "scope=https%3A%2F%2Faud%2Finvoke" in first["body"]
    assert "csecret" not in result.stdout.replace(first["auth"], "")


def test_template_supports_asynchronous_agents() -> None:
    """The bridge reads job status safely and the page polls it (Spec 024)."""
    sources = template_text()
    route = sources["app/api/agent/route.js"]
    page = sources["app/page.jsx"]
    config = sources["app/demo-config.js"]
    assert "export async function GET(request)" in route
    assert "const JOB_ID = /^[A-Za-z0-9_-]{1,128}$/;" in route
    assert 'searchParams.get("job")' in route
    assert "/api/agent?job=" in page and 'demo.mode === "async"' in page
    assert 'mode: "sync"' in config and "steps: []" in config
    assert "failed:" in config
