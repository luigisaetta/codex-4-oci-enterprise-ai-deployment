// Identity-domain access token for agents with the public-idcs profile (Spec 022).
// Runs only on the local server: the values come from .env.local, never from the
// browser, and neither the secret nor the token is ever logged or returned.

const TOKEN_TIMEOUT_MS = 30_000;
const REFRESH_MARGIN_SECONDS = 60;
const DEFAULT_LIFETIME_SECONDS = 3600;
const REQUIRED = [
  "IDCS_DOMAIN_URL",
  "IDCS_TOKEN_SCOPE",
  "IDCS_CLIENT_ID",
  "IDCS_CLIENT_SECRET",
];

let cached = null;

export class TokenError extends Error {}

// Return true when .env.local asks for token-protected calls.
export function tokenRequired(env = process.env) {
  return Boolean((env.IDCS_CLIENT_ID || "").trim());
}

// Forget the cached token, for example after the agent answered 401.
export function discardToken() {
  cached = null;
}

// Return a valid access token, requesting a new one when needed.
export async function accessToken(env = process.env, now = Date.now()) {
  if (cached && now < cached.expiresAt) {
    return cached.token;
  }
  const missing = REQUIRED.filter((name) => !(env[name] || "").trim());
  if (missing.length) {
    throw new TokenError(`missing in .env.local: ${missing.join(", ")}`);
  }
  const basic = Buffer.from(
    `${env.IDCS_CLIENT_ID.trim()}:${env.IDCS_CLIENT_SECRET.trim()}`,
  ).toString("base64");
  let response;
  try {
    response = await fetch(
      `${env.IDCS_DOMAIN_URL.trim().replace(/\/+$/, "")}/oauth2/v1/token`,
      {
        method: "POST",
        headers: {
          Authorization: `Basic ${basic}`,
          "Content-Type": "application/x-www-form-urlencoded",
          Accept: "application/json",
        },
        body: new URLSearchParams({
          grant_type: "client_credentials",
          scope: env.IDCS_TOKEN_SCOPE.trim(),
        }),
        cache: "no-store",
        signal: AbortSignal.timeout(TOKEN_TIMEOUT_MS),
      },
    );
  } catch (error) {
    throw new TokenError(
      error?.name === "TimeoutError" ? "token request timeout" : "token request failed",
    );
  }
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok || typeof payload.access_token !== "string") {
    throw new TokenError(
      `token request: HTTP ${response.status}, OAuth error ${payload.error || "unknown"}`,
    );
  }
  const lifetime = Number(payload.expires_in) || DEFAULT_LIFETIME_SECONDS;
  cached = {
    token: payload.access_token,
    expiresAt: now + Math.max(0, lifetime - REFRESH_MARGIN_SECONDS) * 1000,
  };
  return cached.token;
}
