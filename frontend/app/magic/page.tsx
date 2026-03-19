"use client";
import { useEffect, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { saveAuth } from "@/lib/auth";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const C = { bg: "#06060f", surface: "#0d0d1a", border: "#1a1a2e", accent: "#2563ff", green: "#00c896", red: "#ff4466", text: "#e2e8f0", muted: "#64748b" };

function MagicVerify() {
  const router = useRouter();
  const params = useSearchParams();
  const [status, setStatus] = useState<"verifying" | "success" | "error">("verifying");
  const [msg,    setMsg]    = useState("");

  useEffect(() => {
    const token = params.get("token");
    const email = params.get("email");
    if (!token || !email) { setStatus("error"); setMsg("Invalid magic link."); return; }

    fetch(`${API}/api/auth/magic-verify`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ token, email }),
    })
      .then(r => r.json().then(d => ({ ok: r.ok, data: d })))
      .then(({ ok, data }) => {
        if (!ok) { setStatus("error"); setMsg(data.detail || "Invalid or expired link."); return; }
        saveAuth(data);
        setStatus("success");
        setTimeout(() => router.replace("/dashboard"), 1500);
      })
      .catch(() => { setStatus("error"); setMsg("Connection error."); });
  }, [params, router]);

  return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "monospace" }}>
      <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: 40, maxWidth: 360, width: "100%", textAlign: "center" }}>
        <div style={{ color: C.accent, fontSize: 18, fontWeight: 700, letterSpacing: 2, marginBottom: 24 }}>IEB</div>
        {status === "verifying" && <div style={{ color: C.muted, fontSize: 13 }}>Verifying your link...</div>}
        {status === "success"   && <div style={{ color: C.green, fontSize: 13 }}>&#10003; Logged in — redirecting...</div>}
        {status === "error"     && (
          <>
            <div style={{ color: C.red, fontSize: 13, marginBottom: 20 }}>{msg}</div>
            <a href="/login" style={{ color: C.accent, fontSize: 12, textDecoration: "none" }}>Back to login</a>
          </>
        )}
      </div>
    </div>
  );
}

export default function MagicPage() {
  return (
    <Suspense>
      <MagicVerify />
    </Suspense>
  );
}
