"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { getAlerts, createAlert, deleteAlert, type AlertItem } from "@/lib/api";
import { logoutSync as logout } from "@/lib/auth";

const C = {
  bg: "#06060f", surface: "#0d0d1a", border: "#1a1a2e",
  accent: "#2563ff", green: "#00c896", red: "#ff4466",
  gold: "#f59e0b", text: "#e2e8f0", muted: "#64748b",
  cyan: "#00d4ff",
};

const SYMBOLS = [
  "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","XAUUSD","XAGUSD",
  "BTCUSD","ETHUSD","SPX500","NAS100","USOIL","AAPL","MSFT","NVDA","TSLA",
];

const TIMEFRAMES = ["1m","5m","15m","30m","1h","4h","1d"];

const CONDITIONS: { value: string; label: string; needsThreshold: boolean }[] = [
  { value: "signal_is_buy",     label: "Signal is BUY",          needsThreshold: false },
  { value: "signal_is_sell",    label: "Signal is SELL",         needsThreshold: false },
  { value: "any_signal",        label: "Any signal (not HOLD)",  needsThreshold: false },
  { value: "confidence_above",  label: "Confidence above %",     needsThreshold: true  },
];

function conditionLabel(c: string, threshold: number | null): string {
  const found = CONDITIONS.find(x => x.value === c);
  if (!found) return c;
  if (c === "confidence_above" && threshold != null) return `Confidence ≥ ${(threshold * 100).toFixed(0)}%`;
  return found.label;
}

function signalDot(c: string) {
  if (c === "signal_is_buy")  return { color: C.green,  icon: "▲" };
  if (c === "signal_is_sell") return { color: C.red,    icon: "▼" };
  if (c === "any_signal")     return { color: C.cyan,   icon: "◈" };
  return { color: C.gold, icon: "%" };
}

export default function AlertsPage() {
  const router = useRouter();
  const [alerts,  setAlerts]  = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");

  // New alert form
  const [symbol,    setSymbol]    = useState("XAUUSD");
  const [timeframe, setTimeframe] = useState("5m");
  const [condition, setCondition] = useState("signal_is_buy");
  const [threshold, setThreshold] = useState("70");
  const [saving,    setSaving]    = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    import("@/lib/supabase").then(({ supabase }) => {
      supabase.auth.getSession().then(({ data: { session } }) => {
        if (!session) { router.replace("/login"); return; }
        loadAlerts();
      });
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadAlerts() {
    setLoading(true);
    setError("");
    try {
      const data = await getAlerts();
      setAlerts(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load alerts");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSaveError("");
    setSaving(true);
    try {
      const needsThreshold = CONDITIONS.find(c => c.value === condition)?.needsThreshold;
      await createAlert({
        symbol,
        timeframe,
        condition,
        ...(needsThreshold ? { threshold: parseFloat(threshold) / 100 } : {}),
      });
      await loadAlerts();
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Failed to create alert");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteAlert(id);
      setAlerts(prev => prev.filter(a => a.id !== id));
    } catch {}
  }

  const needsThreshold = CONDITIONS.find(c => c.value === condition)?.needsThreshold;

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "'JetBrains Mono', monospace" }}>

      {/* Nav */}
      <nav style={{ background: C.surface, borderBottom: `1px solid ${C.border}`, padding: "0 24px", display: "flex", alignItems: "center", gap: 20, height: 48 }}>
        <span style={{ color: C.cyan, fontWeight: 700, fontSize: 14, letterSpacing: 1 }}>IEB</span>
        <a href="/dashboard" style={{ color: C.muted, textDecoration: "none", fontSize: 12 }}>Dashboard</a>
        <a href="/backtest"  style={{ color: C.muted, textDecoration: "none", fontSize: 12 }}>Backtest</a>
        <span style={{ color: C.text, fontSize: 12, borderBottom: `2px solid ${C.accent}`, paddingBottom: 2 }}>Alerts</span>
        <a href="/account"   style={{ color: C.muted, textDecoration: "none", fontSize: 12 }}>Account</a>
        <div style={{ flex: 1 }} />
        <button onClick={() => { logout(); router.replace("/login"); }}
          style={{ background: "transparent", border: `1px solid ${C.border}`, color: C.muted, padding: "3px 10px", borderRadius: 5, cursor: "pointer", fontSize: 11, fontFamily: "inherit" }}>
          Logout
        </button>
      </nav>

      <div style={{ maxWidth: 760, margin: "32px auto", padding: "0 20px" }}>

        {/* Page title */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ color: C.text, fontSize: 16, fontWeight: 700, letterSpacing: 1 }}>SIGNAL ALERTS</div>
          <div style={{ color: C.muted, fontSize: 12, marginTop: 4 }}>
            Alerts are checked every time you run an IEB Brain analysis on the dashboard.
          </div>
        </div>

        {/* Create alert card */}
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, padding: 24, marginBottom: 24 }}>
          <div style={{ fontSize: 10, color: C.muted, letterSpacing: 1, marginBottom: 16 }}>NEW ALERT</div>

          <form onSubmit={handleCreate}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
              {/* Symbol */}
              <label>
                <div style={{ color: C.muted, fontSize: 10, letterSpacing: 1, marginBottom: 5 }}>SYMBOL</div>
                <select value={symbol} onChange={e => setSymbol(e.target.value)} style={inputStyle}>
                  {SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>

              {/* Timeframe */}
              <label>
                <div style={{ color: C.muted, fontSize: 10, letterSpacing: 1, marginBottom: 5 }}>TIMEFRAME</div>
                <select value={timeframe} onChange={e => setTimeframe(e.target.value)} style={inputStyle}>
                  {TIMEFRAMES.map(tf => <option key={tf} value={tf}>{tf}</option>)}
                </select>
              </label>

              {/* Condition */}
              <label style={{ gridColumn: needsThreshold ? "1" : "1 / -1" }}>
                <div style={{ color: C.muted, fontSize: 10, letterSpacing: 1, marginBottom: 5 }}>CONDITION</div>
                <select value={condition} onChange={e => setCondition(e.target.value)} style={inputStyle}>
                  {CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </label>

              {/* Threshold — only for confidence_above */}
              {needsThreshold && (
                <label>
                  <div style={{ color: C.muted, fontSize: 10, letterSpacing: 1, marginBottom: 5 }}>THRESHOLD (%)</div>
                  <input
                    type="number" min="10" max="99" step="5"
                    value={threshold} onChange={e => setThreshold(e.target.value)}
                    style={inputStyle}
                  />
                </label>
              )}
            </div>

            {saveError && (
              <div style={{ color: C.red, fontSize: 11, marginBottom: 12, padding: "8px 10px", background: "#ff446611", borderRadius: 6 }}>
                {saveError}
              </div>
            )}

            <button type="submit" disabled={saving} style={{
              background: C.accent, color: "#fff", border: "none",
              padding: "9px 20px", borderRadius: 6, fontSize: 12, fontWeight: 700,
              cursor: saving ? "not-allowed" : "pointer", fontFamily: "inherit",
              letterSpacing: "0.06em", opacity: saving ? 0.6 : 1,
            }}>
              {saving ? "SAVING..." : "+ ADD ALERT"}
            </button>
          </form>
        </div>

        {/* Alert list */}
        <div style={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 10, overflow: "hidden" }}>
          <div style={{ padding: "14px 20px", borderBottom: `1px solid ${C.border}`, display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.green, boxShadow: `0 0 6px ${C.green}` }} />
            <span style={{ fontSize: 10, color: C.muted, letterSpacing: 1 }}>ACTIVE ALERTS</span>
            <span style={{ marginLeft: "auto", color: C.muted, fontSize: 11 }}>{alerts.length} / 20</span>
          </div>

          {loading && (
            <div style={{ padding: 24, textAlign: "center", color: C.muted, fontSize: 12 }}>Loading...</div>
          )}
          {!loading && error && (
            <div style={{ padding: 24, textAlign: "center", color: C.red, fontSize: 12 }}>{error}</div>
          )}
          {!loading && !error && alerts.length === 0 && (
            <div style={{ padding: 32, textAlign: "center", color: C.muted, fontSize: 12 }}>
              No active alerts. Add one above — it will trigger when you run IEB Brain analysis on the dashboard.
            </div>
          )}

          {alerts.map((alert, i) => {
            const dot = signalDot(alert.condition);
            return (
              <div key={alert.id} style={{
                display: "flex", alignItems: "center", gap: 14,
                padding: "14px 20px",
                borderBottom: i < alerts.length - 1 ? `1px solid ${C.border}` : "none",
              }}>
                <div style={{ fontSize: 14, color: dot.color }}>{dot.icon}</div>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 3 }}>
                    <span style={{ color: C.text, fontSize: 13, fontWeight: 700 }}>{alert.symbol}</span>
                    <span style={{ color: C.muted, fontSize: 11 }}>· {alert.timeframe}</span>
                    <span style={{
                      color: dot.color, background: dot.color + "18", border: `1px solid ${dot.color}30`,
                      borderRadius: 3, padding: "1px 7px", fontSize: 10, fontWeight: 700,
                    }}>
                      {conditionLabel(alert.condition, alert.threshold)}
                    </span>
                  </div>
                  <div style={{ color: C.muted, fontSize: 10 }}>
                    Created {alert.created_at ? new Date(alert.created_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "—"}
                    {alert.last_triggered && (
                      <span style={{ marginLeft: 12, color: C.gold }}>
                        Last triggered {new Date(alert.last_triggered).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
                      </span>
                    )}
                  </div>
                </div>

                <button onClick={() => handleDelete(alert.id)} style={{
                  background: "transparent", border: `1px solid ${C.border}`,
                  color: C.muted, padding: "4px 10px", borderRadius: 5,
                  cursor: "pointer", fontSize: 11, fontFamily: "inherit",
                  flexShrink: 0,
                }}>
                  Remove
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%", background: C.bg, border: `1px solid ${C.border}`,
  color: C.text, padding: "8px 10px", borderRadius: 6,
  fontSize: 12, fontFamily: "inherit", boxSizing: "border-box",
};
