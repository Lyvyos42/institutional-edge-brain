/**
 * Auth helpers — Supabase handles token storage and refresh automatically.
 * These are thin wrappers used by pages that were written before the Supabase
 * migration and still import from here.
 */

import { supabase } from "@/lib/supabase";

// ── Getters (read Supabase session or legacy localStorage fallback) ────────────
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("ieb_token");
}

export function getEmail(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("ieb_email") || "";
}

export function getTier(): string {
  if (typeof window === "undefined") return "free";
  return localStorage.getItem("ieb_tier") || "free";
}

export function isLoggedIn(): boolean {
  if (typeof window === "undefined") return false;
  return document.cookie.includes("ieb_auth=1");
}

// ── saveAuth — kept for legacy custom-JWT pages (forgot-password flow etc.) ───
export function saveAuth(data: {
  access_token: string;
  refresh_token?: string;
  email?: string;
  tier?: string;
}) {
  localStorage.setItem("ieb_token", data.access_token);
  if (data.email) localStorage.setItem("ieb_email", data.email);
  if (data.tier)  localStorage.setItem("ieb_tier",  data.tier);
  document.cookie = "ieb_auth=1; path=/; max-age=2592000; SameSite=Lax";
}

// ── logout ────────────────────────────────────────────────────────────────────
export async function logout(): Promise<void> {
  await supabase.auth.signOut();
  localStorage.removeItem("ieb_token");
  localStorage.removeItem("ieb_email");
  localStorage.removeItem("ieb_tier");
  document.cookie = "ieb_auth=; path=/; max-age=0";
}

// Sync alias for components that call it without await
export function logoutSync(): void {
  logout().catch(() => {});
}
