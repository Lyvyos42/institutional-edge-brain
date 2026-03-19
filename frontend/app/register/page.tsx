"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { register } from "@/lib/api";

export default function RegisterPage() {
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
      const data = await register(email, password);
      localStorage.setItem("ieb_token", data.access_token);
      localStorage.setItem("ieb_email", data.email);
      localStorage.setItem("ieb_tier", data.tier);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed");
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
            <svg width={24} height={24} viewBox="0 0 32 32" fill="none">
              <circle cx="16" cy="16" r="6" fill="#00d4ff" opacity="0.9"/>
              <circle cx="16" cy="16" r="12" stroke="#00d4ff" strokeWidth="1" opacity="0.3"/>
              {[0, 120, 240].map((deg, i) => (
                <circle key={i}
                  cx={16 + 12 * Math.cos(deg * Math.PI / 180)}
                  cy={16 + 12 * Math.sin(deg * Math.PI / 180)}
                  r="2.5" fill="#7c3aed" opacity="0.8"
                />
              ))}
            </svg>
          </div>
          <h1 style={{ color: "#fff", fontWeight: 800, fontSize: "1.3rem", margin: "0 0 4px" }}>Create Account</h1>
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
              minLength={6}
              value={password}
              onChange={e => setPassword(e.target.value)}
              placeholder="Min. 6 characters"
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
            {loading ? "Creating account..." : "Create Account"}
          </button>
          <p style={{ textAlign: "center", color: "#475569", fontSize: "0.82rem", margin: 0 }}>
            Already have an account?{" "}
            <Link href="/login" style={{ color: "#00d4ff", textDecoration: "none" }}>
              Sign in
            </Link>
          </p>
        </form>
      </div>
    </main>
  );
}
