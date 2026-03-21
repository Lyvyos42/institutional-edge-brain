"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { logoutSync as logout } from "@/lib/auth";
import { getMe, changePassword as apiChangePassword } from "@/lib/api";

const C = {
  bg: "#06060f", surface: "#0d0d1a", border: "#1a1a2e",
  accent: "#2563ff", green: "#00c896", red: "#ff4466",
  gold: "#f59e0b", text: "#e2e8f0", muted: "#64748b",
};

interface UserInfo {
  email: string;
  tier: string;
  created_at: string | null;
  last_login: string | null;
  daily_used: number;
  daily_limit: number | null;
}

function TierBadge({ tier }: { tier: string }) {
  const colors: Record<string, string> = { free: C.muted, pro: C.accent, admin: C.gold };
  const color = colors[tier] || C.muted;
  return (
    <span style={{ background: color + "22", color, border: `1px solid ${color}55`,
                   padding: "2px 10px", borderRadius: 4, fontSize: 11, fontWeight: 700, letterSpacing: 1 }}>
      {tier.toUpperCase()}
    </span>
  );
}

export default function AccountPage() {
  const router = useRouter();
  const [info,      setInfo]      = useState<UserInfo | null>(null);
  const [loading,   setLoading]   = useState(true);
  const [pwCurrent, setPwCurrent] = useState("");
  const [pwNew,     setPwNew]     = useState("");
  const [pwConfirm, setPwConfirm] = useState("");
  const [pwError,   setPwError]   = useState("");
  const [pwSuccess, setPwSuccess] = useState("");
  const [pwLoading, setPwLoading] = useState(false);

  useEffect(() => {
    getMe()
      .then((d) => setInfo(d))
      .catch(() => { logout(); router.replace("/login"); })
      .finally(() => setLoading(false));
  }, [router]);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setPwError(""); setPwSuccess("");
    if (pwNew.length < 8)    { setPwError("New password must be at least 8 characters"); return; }
    if (pwNew !== pwConfirm) { setPwError("Passwords do not match"); return; }
    setPwLoading(true);
    try {
      await apiChangePassword(pwCurrent, pwNew);
      setPwSuccess("Password changed. You'll be logged out shortly.");
      setPwCurrent(""); setPwNew(""); setPwConfirm("");
      setTimeout(() => { logout(); router.replace("/login"); }, 2000);
    } catch (err: unknown) {
      setPwError(err instanceof Error ? err.message : "Error");
    } finally {
      setPwLoading(false);
    }
  };

  const fmtDate = (iso: string | null) => {
    if (!iso) return "—";
    return new Date(iso).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });
  };

  if (loading) return (
    <div style={{ minHeight: "100vh", background: C.bg, display: "flex", alignItems: "center", justifyContent: "center", color: C.muted, fontFamily: "monospace" }}>
      Loading...
    </div>
  );

  const tier = info?.tier || "free";

  const pwFields: { label: string; value: string; set: (v: string) => void }[] = [
    { label: "CURRENT PASSWORD", value: pwCurrent, set: setPwCurrent },
    { label: "NEW PASSWORD",     value: pwNew,     set: setPwNew     },
    { label: "CONFIRM NEW",      value: pwConfirm, set: setPwConfirm },
  ];

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "monospace" }}>
      {/* Nav */}
      <nav style={{ background: C.surface, borderBottom: `1px solid ${C.border}`, padding: "0 24px", display: "flex", alignItems: "center", gap: 24, height: 52 }}>
        <span style={{ color: C.accent, fontWeight: 700, fontSize: 15, letterSpacing: 1 }}>IEB</span>
        <a href="/dashboard" style={{ color: C.muted, textDecoration: "none", fontSize: 13 }}>Dashboard</a>
        <a href="/backtest"  style={{ color: C.muted, textDecoration: "none", fontSize: 13 }}>Backtest</a>
        <span style={{ color: C.text, fontSize: 13, borderBottom: `2px solid ${C.accent}`, paddingBottom: 2 }}>Account</span>
        <div style={{ flex: 1 }} />
        <button onClick={() => { logout(); router.replace("/login"); }}
          style={{ background: "transparent", border: `1px solid ${C.border}`, color: C.muted, padding: "4px 12px", borderRadius: 5, cursor: "pointer", fontSize: 12, fontFamily: "monospace" }}>
          Logout
        </button>
      </nav>

      <div style={{ maxWidth: 600, margin: "40px auto", padding: "0 24px" }}>

        {/* Profile card */}
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: 28, marginBottom: 20 }}>
          <div style={{ fontSize: 11, color: C.muted, letterSpacing: 1, marginBottom: 20 }}>ACCOUNT PROFILE</div>

          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24 }}>
            <div style={{ width: 44, height: 44, borderRadius: "50%", background: C.accent + "33", border: `1px solid ${C.accent}55`,
                          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, color: C.accent }}>
              {info?.email?.[0]?.toUpperCase() || "?"}
            </div>
            <div>
              <div style={{ color: C.text, fontSize: 14 }}>{info?.email}</div>
              <div style={{ marginTop: 4 }}><TierBadge tier={tier} /></div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            {[
              { label: "Member since", value: fmtDate(info?.created_at ?? null) },
              { label: "Last login",   value: fmtDate(info?.last_login  ?? null) },
            ].map(({ label, value }) => (
              <div key={label} style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6, padding: 14 }}>
                <div style={{ color: C.muted, fontSize: 10, letterSpacing: 1, marginBottom: 4 }}>{label.toUpperCase()}</div>
                <div style={{ color: C.text, fontSize: 12 }}>{value}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Usage card — free tier only */}
        {tier === "free" && (
          <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: 28, marginBottom: 20 }}>
            <div style={{ fontSize: 11, color: C.muted, letterSpacing: 1, marginBottom: 16 }}>DAILY USAGE</div>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, fontSize: 13 }}>
              <span style={{ color: C.text }}>{info?.daily_used ?? 0} / {info?.daily_limit ?? 10} analyses used today</span>
              <span style={{ color: (info?.daily_used ?? 0) >= (info?.daily_limit ?? 10) ? C.red : C.green }}>
                {(info?.daily_used ?? 0) >= (info?.daily_limit ?? 10)
                  ? "Limit reached"
                  : `${(info?.daily_limit ?? 10) - (info?.daily_used ?? 0)} remaining`}
              </span>
            </div>
            <div style={{ background: C.border, borderRadius: 4, height: 6, overflow: "hidden" }}>
              <div style={{ height: "100%", borderRadius: 4, transition: "width 0.3s",
                            width: `${Math.min(100, ((info?.daily_used ?? 0) / (info?.daily_limit ?? 10)) * 100)}%`,
                            background: (info?.daily_used ?? 0) >= (info?.daily_limit ?? 10) ? C.red : C.accent }} />
            </div>
            <div style={{ marginTop: 12, fontSize: 11, color: C.muted }}>
              Resets at midnight UTC · <span style={{ color: C.gold }}>Upgrade to Pro for unlimited analyses</span>
            </div>
          </div>
        )}

        {tier === "pro" && (
          <div style={{ background: C.surface, border: `1px solid ${C.accent}33`, borderRadius: 10, padding: 28, marginBottom: 20 }}>
            <div style={{ fontSize: 11, color: C.muted, letterSpacing: 1, marginBottom: 8 }}>DAILY USAGE</div>
            <div style={{ color: C.accent, fontSize: 13 }}>&#10003; Unlimited analyses &mdash; Pro tier</div>
          </div>
        )}

        {/* Change password card */}
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: 28 }}>
          <div style={{ fontSize: 11, color: C.muted, letterSpacing: 1, marginBottom: 20 }}>CHANGE PASSWORD</div>

          <form onSubmit={handleChangePassword}>
            {pwFields.map(({ label, value, set }) => (
              <label key={label} style={{ display: "block", marginBottom: 14 }}>
                <div style={{ color: C.muted, fontSize: 10, letterSpacing: 1, marginBottom: 5 }}>{label}</div>
                <input type="password" value={value} onChange={e => set(e.target.value)} required
                  style={{ width: "100%", background: C.bg, border: `1px solid ${C.border}`, color: C.text,
                           padding: "9px 12px", borderRadius: 6, fontSize: 13, fontFamily: "monospace", boxSizing: "border-box" }} />
              </label>
            ))}

            {pwError   && <div style={{ color: C.red,   fontSize: 12, marginBottom: 12, padding: "8px 12px", background: "#ff446611", borderRadius: 6 }}>{pwError}</div>}
            {pwSuccess && <div style={{ color: C.green, fontSize: 12, marginBottom: 12, padding: "8px 12px", background: "#00c89611", borderRadius: 6 }}>{pwSuccess}</div>}

            <button type="submit" disabled={pwLoading}
              style={{ background: C.surface, border: `1px solid ${C.accent}`, color: C.accent, padding: "10px 24px",
                       borderRadius: 6, fontSize: 12, fontWeight: 700, letterSpacing: 1, cursor: "pointer", fontFamily: "monospace" }}>
              {pwLoading ? "SAVING..." : "UPDATE PASSWORD"}
            </button>
          </form>
        </div>

      </div>
    </div>
  );
}
