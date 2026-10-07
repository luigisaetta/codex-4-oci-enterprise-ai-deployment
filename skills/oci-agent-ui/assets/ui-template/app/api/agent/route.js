// Server-side bridge between the browser and the agent.
// The browser never calls the agent directly: this route forwards the request
// to AGENT_BASE_URL + AGENT_PATH (from .env.local), so no address or secret
// reaches the browser. Technical failures are logged here and returned to the
// page only as a category ("rejected" or "unavailable").
import { NextResponse } from "next/server";

export const runtime = "nodejs";

const TIMEOUT_MS = 90_000;
const MAX_BODY_CHARS = 20_000;

function agentUrl() {
  const base = (process.env.AGENT_BASE_URL || "").replace(/\/+$/, "");
  const path = process.env.AGENT_PATH || "";
  if (!base || !path.startsWith("/") || path.includes("replace-with")) {
    return null;
  }
  return `${base}${path}`;
}

function unavailable(reason) {
  console.error(`Agent call failed: ${reason}`);
  return NextResponse.json({ kind: "unavailable" }, { status: 200 });
}

export async function POST(request) {
  const url = agentUrl();
  if (!url) {
    return unavailable("AGENT_BASE_URL or AGENT_PATH is missing in .env.local");
  }

  let body;
  try {
    body = await request.text();
    JSON.parse(body);
  } catch {
    return NextResponse.json({ kind: "invalid" }, { status: 200 });
  }
  if (body.length > MAX_BODY_CHARS) {
    return NextResponse.json({ kind: "invalid" }, { status: 200 });
  }

  let upstream;
  try {
    upstream = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch (error) {
    return unavailable(error?.name === "TimeoutError" ? "timeout" : String(error));
  }

  const text = await upstream.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    return unavailable(`HTTP ${upstream.status} with a non-JSON body`);
  }

  if (upstream.ok) {
    return NextResponse.json({ kind: "ok", data }, { status: 200 });
  }
  // 400 and 422 come from the agent's own input validation (guideline B3).
  // Other statuses (401, 403, 404 from the platform, 5xx) are not business
  // answers: they are logged and shown as an unavailable service.
  if (upstream.status === 400 || upstream.status === 422) {
    return NextResponse.json({ kind: "rejected", data }, { status: 200 });
  }
  return unavailable(`HTTP ${upstream.status}`);
}
