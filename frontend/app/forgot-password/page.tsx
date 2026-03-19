"use client";
import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const C = {
  bg: "#06060f", surface: "#0d0d1a", border: "#1a1a2e",
  accent: "#2563ff", green: "#00c896", red: "#ff4466",
  text: "#e2e8f0", muted: "#64748b",
};

export default function ForgotPasswordPage() {
  const [email,   setEmail]   = useState("");
  const [sent,    setSent]    = useState(false);
  const [error,   setError]   = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/auth/forgot-password`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ email }),
      });
      if (!res.ok) { const d = await res.json(); setError(d.detail || "Request failed"); return; }
      setSent(true);
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "monospace" }}>
      <div style={{ width: 380, background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: 40 }}>
        <div style={{ color: C.accent, fontWeight: 700, fontSize: 15, letterSpacing: 2, marginBottom: 4 }}>INSTITUTIONAL EDGE BRAIN</div>
        <div style={{ color: C.muted, fontSize: 11, marginBottom: 32 }}>Password Recovery</div>

        {sent ? (
          <div>
            <div style={{ color: C.green, fontSize: 24, marginBottom: 16 }}>&#10003;</div>
            <div style={{ color: C.text, fontSize: 14, marginBottom: 8 }}>Check your email</div>
            <div style={{ color: C.muted, fontSize: 12, lineHeight: 1.7, marginBottom: 24 }}>
              If <strong style={{ color: C.text }}>{email}</strong> is registered, you&apos;ll receive a reset link within a minute. The link expires in 15 minutes.
            </div>
            <a href="/login" style={{ color: C.accent, fontSize: 12, textDecoration: "none" }}>&#8592; Back to login</a>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ color: C.muted, fontSize: 12, lineHeight: 1.7, marginBottom: 24 }}>
              Enter your email address and we&apos;ll send you a link to reset your password.
            </div>

            <label style={{ display: "block", marginBottom: 20 }}>
              <div style={{ color: C.muted, fontSize: 11, marginBottom: 6, letterSpacing: 1 }}>EMAIL ADDRESS</div>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} required
                style={{ width: "100%", background: C.bg, border: `1px solid ${C.border}`, color: C.text,
                         padding: "10px 12px", borderRadius: 6, fontSize: 13, fontFamily: "monospace", boxSizing: "border-box" }} />
            </label>

            {error && <div style={{ color: C.red, fontSize: 12, marginBottom: 16, padding: "8px 12px", background: "#ff446611", borderRadius: 6 }}>{error}</div>}

            <button type="submit" disabled={loading}
              style={{ width: "100%", background: C.accent, color: "#fff", border: "none", padding: "12px",
                       borderRadius: 6, fontSize: 13, fontWeight: 700, letterSpacing: 1, cursor: loading ? "not-allowed" : "pointer",
                       opacity: loading ? 0.7 : 1, fontFamily: "monospace" }}>
              {loading ? "SENDING..." : "SEND RESET LINK"}
            </button>

            <div style={{ marginTop: 20, textAlign: "center" }}>
              <a href="/login" style={{ color: C.muted, fontSize: 12, textDecoration: "none" }}>&#8592; Back to login</a>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
