"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { saveAuth } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const C = {
  bg: "#06060f", surface: "#0d0d1a", border: "#1a1a2e",
  accent: "#2563ff", green: "#00c896", red: "#ff4466",
  text: "#e2e8f0", muted: "#64748b",
};

export default function RegisterPage() {
  const router = useRouter();
  const [email,    setEmail]    = useState("");
  const [password, setPassword] = useState("");
  const [confirm,  setConfirm]  = useState("");
  const [error,    setError]    = useState("");
  const [loading,  setLoading]  = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError("Password must be at least 8 characters"); return; }
    if (password !== confirm) { setError("Passwords do not match"); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/auth/register`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "Registration failed"); return; }
      saveAuth(data);
      router.replace("/dashboard");
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  const fields: { label: string; value: string; set: (v: string) => void; type: string }[] = [
    { label: "EMAIL",            value: email,    set: setEmail,    type: "email"    },
    { label: "PASSWORD",         value: password, set: setPassword, type: "password" },
    { label: "CONFIRM PASSWORD", value: confirm,  set: setConfirm,  type: "password" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "monospace" }}>
      <div style={{ width: 380, background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: 40 }}>
        <div style={{ color: C.accent, fontWeight: 700, fontSize: 15, letterSpacing: 2, marginBottom: 4 }}>INSTITUTIONAL EDGE BRAIN</div>
        <div style={{ color: C.muted, fontSize: 11, marginBottom: 32 }}>Create your account</div>

        <form onSubmit={handleSubmit}>
          {fields.map(({ label, value, set, type }) => (
            <label key={label} style={{ display: "block", marginBottom: 16 }}>
              <div style={{ color: C.muted, fontSize: 11, marginBottom: 6, letterSpacing: 1 }}>{label}</div>
              <input type={type} value={value} onChange={e => set(e.target.value)} required
                style={{ width: "100%", background: C.bg, border: `1px solid ${C.border}`, color: C.text,
                         padding: "10px 12px", borderRadius: 6, fontSize: 13, fontFamily: "monospace", boxSizing: "border-box" }} />
            </label>
          ))}

          <div style={{ color: C.muted, fontSize: 10, marginBottom: 20 }}>Minimum 8 characters · Free tier: 10 analyses/day</div>

          {error && <div style={{ color: C.red, fontSize: 12, marginBottom: 16, padding: "8px 12px", background: "#ff446611", borderRadius: 6, border: `1px solid ${C.red}33` }}>{error}</div>}

          <button type="submit" disabled={loading}
            style={{ width: "100%", background: C.accent, color: "#fff", border: "none", padding: "12px",
                     borderRadius: 6, fontSize: 13, fontWeight: 700, letterSpacing: 1, cursor: loading ? "not-allowed" : "pointer",
                     opacity: loading ? 0.7 : 1, fontFamily: "monospace" }}>
            {loading ? "CREATING ACCOUNT..." : "CREATE ACCOUNT"}
          </button>
        </form>

        <div style={{ marginTop: 24, textAlign: "center", fontSize: 12, color: C.muted }}>
          Already have an account?{" "}
          <a href="/login" style={{ color: C.accent, textDecoration: "none" }}>Sign in</a>
        </div>
      </div>
    </div>
  );
}
