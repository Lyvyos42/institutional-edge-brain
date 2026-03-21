import { supabase } from "@/lib/supabase";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getToken(): Promise<string | null> {
  // Prefer live Supabase session (handles refresh automatically)
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) return session.access_token;
  } catch {}
  // Fallback: legacy localStorage token
  return typeof window !== "undefined" ? localStorage.getItem("ieb_token") : null;
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getToken();
  const reqOptions: RequestInit = {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
    ...options,
  };

  // Exponential backoff — 3 retries on network errors (handles Render cold-start)
  const DELAYS = [2_000, 6_000, 18_000];
  let lastError: unknown;
  for (let attempt = 0; attempt <= DELAYS.length; attempt++) {
    try {
      const res = await fetch(`${API}${path}`, reqOptions);
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      return await res.json();
    } catch (err) {
      lastError = err;
      if (err instanceof Error && !err.message.startsWith("HTTP ") && attempt < DELAYS.length) {
        await new Promise(r => setTimeout(r, DELAYS[attempt]));
        continue;
      }
      throw err;
    }
  }
  throw lastError;
}

/** Fire-and-forget ping to wake Render from sleep. Call on page mount. */
export function wakeBackend(): void {
  fetch(`${API}/health`, { method: "GET" }).catch(() => {});
}

// ─── Auth ─────────────────────────────────────────────────────────────────────
export async function login(email: string, password: string): Promise<void> {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message);
  // Set cookie for middleware
  document.cookie = "ieb_auth=1; path=/; max-age=2592000; SameSite=Lax";
  if (data.session?.access_token) {
    localStorage.setItem("ieb_token", data.session.access_token);
  }
}

export async function register(email: string, password: string): Promise<{ needsConfirmation: boolean }> {
  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error) throw new Error(error.message);
  if (data.session) {
    document.cookie = "ieb_auth=1; path=/; max-age=2592000; SameSite=Lax";
    localStorage.setItem("ieb_token", data.session.access_token);
    return { needsConfirmation: false };
  }
  return { needsConfirmation: true };
}

export async function loginWithGoogle(): Promise<void> {
  const { error } = await supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo: `${typeof window !== "undefined" ? window.location.origin : ""}/auth/callback`,
    },
  });
  if (error) throw new Error(error.message);
}

export async function sendMagicLink(email: string): Promise<void> {
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: `${typeof window !== "undefined" ? window.location.origin : ""}/auth/callback`,
    },
  });
  if (error) throw new Error(error.message);
}

export async function logoutUser(): Promise<void> {
  await supabase.auth.signOut();
  localStorage.removeItem("ieb_token");
  document.cookie = "ieb_auth=; path=/; max-age=0";
}

// ─── Signals ──────────────────────────────────────────────────────────────────
export interface ModuleResult {
  signal: "BUY" | "SELL" | "NEUTRAL";
  value: number;
  label: string;
  detail: string;
  error?: boolean;
}

export interface AnalysisResult {
  signal_id: string;
  symbol: string;
  timeframe: string;
  signal: "BUY" | "SELL" | "HOLD";
  confidence: number;
  ensemble: {
    signal: string;
    confidence: number;
    models: Record<string, { signal: string; confidence: number }>;
  };
  levels: {
    price: number;
    entry: number;
    stop_loss: number;
    take_profit: number;
    risk_reward: number;
    support: number;
    resistance: number;
    atr: number;
  };
  modules: Record<string, ModuleResult>;
  latency_ms: number;
}

export async function analyze(symbol: string, timeframe = "5m"): Promise<AnalysisResult> {
  return apiFetch("/api/signals/analyze", {
    method: "POST",
    body: JSON.stringify({ symbol, timeframe }),
  });
}

export async function getMe(): Promise<{ id: string; email: string; tier: string; daily_used: number; daily_limit: number | null; created_at: string | null; last_login: string | null }> {
  return apiFetch("/api/auth/me");
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  return apiFetch("/api/auth/change-password", {
    method: "PUT",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}
