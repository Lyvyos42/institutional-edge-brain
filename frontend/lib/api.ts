export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

import { authFetch } from "@/lib/auth";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await authFetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

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

export async function login(
  email: string,
  password: string
): Promise<{ access_token: string; tier: string; email: string }> {
  const form = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API}/api/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  return res.json();
}

export async function register(
  email: string,
  password: string
): Promise<{ access_token: string; tier: string; email: string }> {
  return apiFetch("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function getMe(): Promise<{ id: string; email: string; tier: string }> {
  return apiFetch("/api/auth/me");
}
