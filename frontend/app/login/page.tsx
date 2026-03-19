"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await login(email, password);
      localStorage.setItem("ieb_token", data.access_token);
      localStorage.setItem("ieb_email", data.email);
      localStorage.setItem("ieb_tier", data.tier);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main style={{ minHeight: "100vh", background: "#06060f", display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ width: "100%", maxWidth: 420 }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ width: 48, height: 48, borderRadius: 12, background: "rgba(0,212,255,0.1)", border: "1px solid rgba(0,212,255,0.3)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 16px" }}>
            <svg width={24} height={24} viewBox="0 0 24 24" fill="none">
              <rect x={3} y={11} width={18} height={11} rx={2} stroke="#00d4ff" strokeWidth={1.8}/>
              <path d="M7 11V7a5 5 0 0110 0v4" stroke="#00d4ff" strokeWidth={1.8} strokeLinecap="round"/>
            </svg>
          </div>
          <h1 style={{ color: "#fff", fontWeight: 800, fontSize: "1.3rem", margin: "0 0 4px" }}>Welcome back</h1>
          <p style={{ color: "#475569", fontSize: "0.82rem", margin: 0 }}>Institutional Edge Brain</p>
        </div>

        <form onSubmit={handleSubmit} style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)", borderRadius: 16, padding: 28, display: "flex", flexDirection: "column", gap: 16 }}>
          <div>
            <label style={{ display: "block", color: "#94a3b8", fontSize: "0.75rem", fontWeight: 600, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="you@example.com"
              style={{ width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, color: "#e2e8f0", fontSize: "0.9rem", padding: "10px 14px", outline: "none", boxSizing: "border-box", fontFamily: "inherit" }}
            />
          </div>
          <div>
            <label style={{ display: "block", color: "#94a3b8", fontSize: "0.75rem", fontWeight: 600, marginBottom: 6, textTransform: "uppercase", letterSpacing: "0.08em" }}>Password</label>
            <input
              type="password"
              required
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="••••••••"
              style={{ width: "100%", background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 8, color: "#e2e8f0", fontSize: "0.9rem", padding: "10px 14px", outline: "none", boxSizing: "border-box", fontFamily: "inherit" }}
            />
          </div>
          {error && (
            <p style={{ color: "#f72585", fontSize: "0.82rem", margin: 0 }}>{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            style={{ background: "linear-gradient(135deg,#00d4ff,#7c3aed)", color: "#fff", fontWeight: 700, fontSize: "0.9rem", padding: "11px", borderRadius: 8, border: "none", cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.7 : 1, fontFamily: "inherit" }}
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
          <p style={{ textAlign: "center", color: "#475569", fontSize: "0.82rem", margin: 0 }}>
            No account?{" "}
            <Link href="/register" style={{ color: "#00d4ff", textDecoration: "none" }}>
              Create one
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}
