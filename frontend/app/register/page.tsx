"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useGoogleLogin } from "@react-oauth/google";
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

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError("Password must be at least 8 characters"); return; }
    if (password !== confirm) { setError("Passwords do not match"); return; }
    setLoading(true);
    try {
      const res  = await fetch(`${API}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "Registration failed"); return; }
      saveAuth(data);
      router.replace("/dashboard");
    } catch (err: any) {
      setError(`Connection error — cannot reach ${API} (${err?.message || "network failure"})`);
    } finally {
      setLoading(false);
    }
  };

  const googleLogin = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      setError(""); setLoading(true);
      try {
        const infoRes = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
          headers: { Authorization: `Bearer ${tokenResponse.access_token}` },
        });
        if (!infoRes.ok) { setError("Google verification failed"); setLoading(false); return; }
        const googleUser = await infoRes.json();

        const res  = await fetch(`${API}/api/auth/google-token`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ access_token: tokenResponse.access_token, email: googleUser.email, sub: googleUser.sub }),
        });
        const data = await res.json();
        if (!res.ok) { setError(data.detail || "Google sign-up failed"); return; }
        saveAuth(data);
        router.replace("/dashboard");
      } catch (err: any) {
        setError(`Google login error — cannot reach ${API} (${err?.message || "network failure"})`);
      } finally {
        setLoading(false);
      }
    },
    onError: () => setError("Google sign-up cancelled or failed"),
  });

  const inputStyle: React.CSSProperties = {
    width: "100%", background: C.bg, border: `1px solid ${C.border}`,
    color: C.text, padding: "10px 12px", borderRadius: 6,
    fontSize: 13, fontFamily: "monospace", boxSizing: "border-box",
  };

  const fields = [
    { label: "EMAIL",            value: email,    set: setEmail,    type: "email"    },
    { label: "PASSWORD",         value: password, set: setPassword, type: "password" },
    { label: "CONFIRM PASSWORD", value: confirm,  set: setConfirm,  type: "password" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
      <div style={{ width: "100%", maxWidth: 400 }}>

        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ color: C.accent, fontSize: 22, fontWeight: 700, letterSpacing: 2, fontFamily: "monospace" }}>IEB</div>
          <div style={{ color: C.muted, fontSize: 11, letterSpacing: 1, fontFamily: "monospace", marginTop: 4 }}>CREATE ACCOUNT</div>
        </div>

        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: 28 }}>

          {/* Google button */}
          <button
            onClick={() => googleLogin()}
            disabled={loading}
            style={{ width: "100%", background: "#fff", border: "1px solid #dadce0", color: "#3c4043",
                     padding: "10px 16px", borderRadius: 6, cursor: "pointer", fontSize: 13,
                     fontWeight: 500, display: "flex", alignItems: "center", justifyContent: "center", gap: 10, marginBottom: 20 }}>
            <svg width="18" height="18" viewBox="0 0 18 18">
              <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
              <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"/>
              <path fill="#FBBC05" d="M3.964 10.706c-.18-.54-.282-1.117-.282-1.706s.102-1.166.282-1.706V4.962H.957C.347 6.175 0 7.55 0 9s.348 2.826.957 4.038l3.007-2.332z"/>
              <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.962L3.964 6.294C4.672 4.167 6.656 3.58 9 3.58z"/>
            </svg>
            Sign up with Google
          </button>

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
            <div style={{ flex: 1, height: 1, background: C.border }} />
            <span style={{ color: C.muted, fontSize: 11, fontFamily: "monospace" }}>OR</span>
            <div style={{ flex: 1, height: 1, background: C.border }} />
          </div>

          <form onSubmit={handleRegister}>
            {fields.map(({ label, value, set, type }) => (
              <label key={label} style={{ display: "block", marginBottom: 14 }}>
                <div style={{ color: C.muted, fontSize: 10, letterSpacing: 1, fontFamily: "monospace", marginBottom: 5 }}>{label}</div>
                <input type={type} value={value} onChange={e => set(e.target.value)} required style={inputStyle} />
              </label>
            ))}

            {error && <div style={{ color: C.red, fontSize: 12, marginBottom: 14, padding: "8px 12px", background: "#ff446611", borderRadius: 6, fontFamily: "monospace" }}>{error}</div>}

            <button type="submit" disabled={loading}
              style={{ width: "100%", background: C.accent, border: "none", color: "#fff", padding: "11px 0",
                       borderRadius: 6, fontSize: 13, fontWeight: 700, cursor: "pointer", fontFamily: "monospace", letterSpacing: 1, marginTop: 4 }}>
              {loading ? "CREATING..." : "CREATE ACCOUNT"}
            </button>
          </form>

          <div style={{ textAlign: "center", marginTop: 24, fontFamily: "monospace", fontSize: 12, color: C.muted }}>
            Already have an account?{" "}
            <a href="/login" style={{ color: C.accent, textDecoration: "none" }}>Sign in</a>
          </div>
        </div>
      </div>
    </div>
  );
}
