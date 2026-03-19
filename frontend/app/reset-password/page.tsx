"use client";
import { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const C = {
  bg: "#06060f", surface: "#0d0d1a", border: "#1a1a2e",
  accent: "#2563ff", green: "#00c896", red: "#ff4466",
  text: "#e2e8f0", muted: "#64748b",
};

function ResetPasswordForm() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const token        = searchParams.get("token") || "";
  const email        = searchParams.get("email") || "";

  const [password, setPassword] = useState("");
  const [confirm,  setConfirm]  = useState("");
  const [error,    setError]    = useState("");
  const [success,  setSuccess]  = useState(false);
  const [loading,  setLoading]  = useState(false);

  useEffect(() => {
    if (!token || !email) setError("Invalid reset link. Please request a new one.");
  }, [token, email]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError("Password must be at least 8 characters"); return; }
    if (password !== confirm) { setError("Passwords do not match"); return; }
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/auth/reset-password`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ email, token, new_password: password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "Reset failed"); return; }
      setSuccess(true);
      setTimeout(() => router.replace("/login"), 2500);
    } catch {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  const fields: { label: string; value: string; set: (v: string) => void }[] = [
    { label: "NEW PASSWORD",     value: password, set: setPassword },
    { label: "CONFIRM PASSWORD", value: confirm,  set: setConfirm  },
  ];

  return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "monospace" }}>
      <div style={{ width: 380, background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: 40 }}>
        <div style={{ color: C.accent, fontWeight: 700, fontSize: 15, letterSpacing: 2, marginBottom: 4 }}>INSTITUTIONAL EDGE BRAIN</div>
        <div style={{ color: C.muted, fontSize: 11, marginBottom: 32 }}>Set New Password</div>

        {success ? (
          <div>
            <div style={{ color: C.green, fontSize: 24, marginBottom: 16 }}>&#10003;</div>
            <div style={{ color: C.text, fontSize: 14, marginBottom: 8 }}>Password reset successfully</div>
            <div style={{ color: C.muted, fontSize: 12 }}>Redirecting to login...</div>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            {fields.map(({ label, value, set }) => (
              <label key={label} style={{ display: "block", marginBottom: 16 }}>
                <div style={{ color: C.muted, fontSize: 11, marginBottom: 6, letterSpacing: 1 }}>{label}</div>
                <input type="password" value={value} onChange={e => set(e.target.value)} required
                  style={{ width: "100%", background: C.bg, border: `1px solid ${C.border}`, color: C.text,
                           padding: "10px 12px", borderRadius: 6, fontSize: 13, fontFamily: "monospace", boxSizing: "border-box" }} />
              </label>
            ))}

            <div style={{ color: C.muted, fontSize: 10, marginBottom: 20 }}>Minimum 8 characters</div>

            {error && <div style={{ color: C.red, fontSize: 12, marginBottom: 16, padding: "8px 12px", background: "#ff446611", borderRadius: 6 }}>{error}</div>}

            <button type="submit" disabled={loading || !token}
              style={{ width: "100%", background: C.accent, color: "#fff", border: "none", padding: "12px",
                       borderRadius: 6, fontSize: 13, fontWeight: 700, letterSpacing: 1, cursor: "pointer",
                       opacity: loading ? 0.7 : 1, fontFamily: "monospace" }}>
              {loading ? "RESETTING..." : "RESET PASSWORD"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div style={{ background: "#06060f", minHeight: "100vh" }} />}>
      <ResetPasswordForm />
    </Suspense>
  );
}
