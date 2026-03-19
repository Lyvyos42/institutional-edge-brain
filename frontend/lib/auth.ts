/**
 * Auth token management with automatic refresh.
 * Access token: 15 min JWT stored in localStorage.
 * Refresh token: 30 days opaque token stored in localStorage.
 */

const TOKEN_KEY   = "ieb_token";
const REFRESH_KEY = "ieb_refresh";
const EMAIL_KEY   = "ieb_email";
const TIER_KEY    = "ieb_tier";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function getEmail(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(EMAIL_KEY) || "";
}

export function getTier(): string {
  if (typeof window === "undefined") return "free";
  return localStorage.getItem(TIER_KEY) || "free";
}

export function saveAuth(data: {
  access_token: string;
  refresh_token?: string;
  email?: string;
  tier?: string;
}) {
  localStorage.setItem(TOKEN_KEY, data.access_token);
  if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
  if (data.email)         localStorage.setItem(EMAIL_KEY,   data.email);
  if (data.tier)          localStorage.setItem(TIER_KEY,    data.tier);
}

export function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(EMAIL_KEY);
  localStorage.removeItem(TIER_KEY);
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

/** Parse JWT payload without verification (client-side only). */
function parseJwt(token: string): Record<string, unknown> | null {
  try {
    const base64 = token.split(".")[1];
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

/** Returns true if the access token expires within the next 2 minutes. */
function isTokenExpiringSoon(token: string): boolean {
  const payload = parseJwt(token);
  if (!payload?.exp) return true;
  return (payload.exp as number) * 1000 < Date.now() + 2 * 60 * 1000;
}

/** Attempt to get a new access token using the refresh token. Returns true on success. */
async function doRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  try {
    const res = await fetch(`${API}/api/auth/refresh`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    saveAuth(data);
    return true;
  } catch {
    return false;
  }
}

/**
 * Drop-in replacement for fetch() that automatically:
 * - Attaches the Authorization header
 * - Refreshes the access token if it's about to expire
 * - Retries the request once after a 401
 * - Logs out and redirects to /login if refresh fails
 */
export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  let token = getToken();

  // Proactive refresh before token expires
  if (token && isTokenExpiringSoon(token)) {
    const ok = await doRefresh();
    if (!ok) {
      logout();
      if (typeof window !== "undefined") window.location.href = "/login";
      throw new Error("Session expired");
    }
    token = getToken();
  }

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  let res = await fetch(url, { ...options, headers });

  // Reactive refresh on 401
  if (res.status === 401) {
    const ok = await doRefresh();
    if (ok) {
      token = getToken();
      headers["Authorization"] = `Bearer ${token}`;
      res = await fetch(url, { ...options, headers });
    } else {
      logout();
      if (typeof window !== "undefined") window.location.href = "/login";
      throw new Error("Session expired");
    }
  }

  return res;
}
