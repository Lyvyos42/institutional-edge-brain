"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { analyze, getSignalHistory, checkAlerts, type AnalysisResult, type SignalHistoryItem, type AlertItem } from "@/lib/api";
import { getToken, getEmail as getStoredEmail, logoutSync as doLogout } from "@/lib/auth";

const SYMBOLS: Record<string, string[]> = {
  "Forex":   ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURGBP","EURJPY","GBPJPY"],
  "Metals":  ["XAUUSD","XAGUSD"],
  "Energy":  ["USOIL","UKOIL","NATGAS"],
  "Crypto":  ["BTCUSD","ETHUSD"],
  "Indices": ["SPX500","NAS100","GER40","UK100","JPN225"],
  "Stocks":  ["AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META"],
};

const TIMEFRAMES = ["1m","5m","15m","30m","1h","4h","1d"];

const MODULE_META: Record<string, { label: string; icon: string; desc: string }> = {
  entropy:     { label: "ENTROPY",     icon: "◈", desc: "Market order formation" },
  vpin:        { label: "VPIN",        icon: "◉", desc: "Smart money activity" },
  vol_accum:   { label: "VOL ACCUM",   icon: "◎", desc: "Institutional accumulation" },
  fix_time:    { label: "FIX TIME",    icon: "◷", desc: "London Fix manipulation" },
  month_flow:  { label: "MONTH FLOW",  icon: "◈", desc: "Month-end rebalancing" },
  iceberg:     { label: "ICEBERG",     icon: "◉", desc: "Hidden orders detection" },
  cot:         { label: "COT",         icon: "◎", desc: "Commitment of Traders" },
  correlation: { label: "CORRELATION", icon: "◈", desc: "Asset correlation breaks" },
  vol_profile: { label: "VPOC",        icon: "◉", desc: "Volume point of control" },
  stop_run:    { label: "STOP RUN",    icon: "◎", desc: "Stop hunt profiling" },
  sweep:       { label: "SWEEP",       icon: "◈", desc: "Liquidity sweep detection" },
  volatility:  { label: "VOLATILITY",  icon: "◉", desc: "Vol regime analysis" },
};

function signalColor(s: string): string {
  if (s === "BUY" || s === "STRONG_BUY") return "#00f5a0";
  if (s === "SELL" || s === "STRONG_SELL") return "#f72585";
  if (s === "BULLISH") return "#00c896";
  if (s === "BEARISH") return "#e0445a";
  return "#64748b";
}

function signalLabel(s: string): string {
  const map: Record<string, string> = {
    BUY: "BUY", SELL: "SELL", NEUTRAL: "NEUTRAL",
    STRONG_BUY: "STRONG BUY", STRONG_SELL: "STRONG SELL",
    HOLD: "HOLD", BULLISH: "BULL", BEARISH: "BEAR",
  };
  return map[s] || s;
}

function NeuralCanvas({ result, running }: { result: AnalysisResult | null; running: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    const moduleKeys = Object.keys(MODULE_META);

    function draw(t: number) {
      const W = canvas!.width;
      const H = canvas!.height;
      const cx = W / 2;
      const cy = H / 2;
      const nodeRadius = Math.min(W, H) * 0.34;

      const nodes = moduleKeys.map((key, i) => {
        const angle = (i / moduleKeys.length) * Math.PI * 2 - Math.PI / 2;
        return {
          x: cx + nodeRadius * Math.cos(angle),
          y: cy + nodeRadius * Math.sin(angle),
          key,
          signal: result?.modules?.[key]?.signal ?? "NEUTRAL",
        };
      });

      ctx!.clearRect(0, 0, W, H);

      // Background grid
      ctx!.strokeStyle = "rgba(0,212,255,0.025)";
      ctx!.lineWidth = 1;
      for (let x = 0; x < W; x += 40) {
        ctx!.beginPath(); ctx!.moveTo(x, 0); ctx!.lineTo(x, H); ctx!.stroke();
      }
      for (let y = 0; y < H; y += 40) {
        ctx!.beginPath(); ctx!.moveTo(0, y); ctx!.lineTo(W, y); ctx!.stroke();
      }

      // Connection lines
      nodes.forEach((n, i) => {
        nodes.forEach((m, j) => {
          if (j <= i) return;
          const sameSignal = n.signal === m.signal && n.signal !== "NEUTRAL";
          const alpha = sameSignal ? 0.15 : 0.04;
          const color = sameSignal
            ? (n.signal === "BUY" || n.signal === "STRONG_BUY" ? "0,245,160" : "247,37,133")
            : "0,212,255";
          ctx!.strokeStyle = `rgba(${color},${alpha})`;
          ctx!.lineWidth = sameSignal ? 1.5 : 0.5;
          ctx!.beginPath();
          ctx!.moveTo(n.x, n.y);
          ctx!.lineTo(m.x, m.y);
          ctx!.stroke();
        });
      });

      // Center glow
      const mainSignal = result?.signal ?? "HOLD";
      const glowColor = mainSignal === "BUY" || mainSignal === "STRONG_BUY"
        ? [0, 245, 160]
        : mainSignal === "SELL" || mainSignal === "STRONG_SELL"
          ? [247, 37, 133]
          : [0, 212, 255];
      const pulse = 0.6 + 0.4 * Math.sin(t * 0.003);
      const grd = ctx!.createRadialGradient(cx, cy, 0, cx, cy, 90 * pulse);
      grd.addColorStop(0, `rgba(${glowColor.join(",")},${running ? 0.5 : 0.25})`);
      grd.addColorStop(1, "rgba(0,0,0,0)");
      ctx!.fillStyle = grd;
      ctx!.beginPath();
      ctx!.arc(cx, cy, 90 * pulse, 0, Math.PI * 2);
      ctx!.fill();

      // Center outer ring
      ctx!.strokeStyle = `rgba(${glowColor.join(",")},0.2)`;
      ctx!.lineWidth = 1;
      ctx!.beginPath();
      ctx!.arc(cx, cy, 40, 0, Math.PI * 2);
      ctx!.stroke();

      // Center inner ring
      ctx!.strokeStyle = `rgba(${glowColor.join(",")},0.7)`;
      ctx!.lineWidth = 2;
      ctx!.beginPath();
      ctx!.arc(cx, cy, 28, 0, Math.PI * 2);
      ctx!.stroke();

      // Center fill
      const cFill = ctx!.createRadialGradient(cx, cy, 0, cx, cy, 28);
      cFill.addColorStop(0, `rgba(${glowColor.join(",")},0.15)`);
      cFill.addColorStop(1, `rgba(${glowColor.join(",")},0.02)`);
      ctx!.fillStyle = cFill;
      ctx!.beginPath();
      ctx!.arc(cx, cy, 28, 0, Math.PI * 2);
      ctx!.fill();

      // Center text
      ctx!.fillStyle = `rgba(${glowColor.join(",")},1)`;
      ctx!.font = `bold 11px 'JetBrains Mono', monospace`;
      ctx!.textAlign = "center";
      ctx!.textBaseline = "middle";
      ctx!.fillText(running ? "···" : signalLabel(mainSignal), cx, cy);

      // Module nodes
      nodes.forEach((n, i) => {
        const nc = n.signal === "BUY" || n.signal === "STRONG_BUY"
          ? [0, 245, 160]
          : n.signal === "SELL" || n.signal === "STRONG_SELL"
            ? [247, 37, 133]
            : [100, 116, 139];
        const nodePulse = 0.7 + 0.3 * Math.sin(t * 0.002 + i * 0.5);
        const r = 7 * nodePulse;

        // Node glow
        const ng = ctx!.createRadialGradient(n.x, n.y, 0, n.x, n.y, 22);
        ng.addColorStop(0, `rgba(${nc.join(",")},${n.signal !== "NEUTRAL" ? 0.5 : 0.15})`);
        ng.addColorStop(1, "rgba(0,0,0,0)");
        ctx!.fillStyle = ng;
        ctx!.beginPath();
        ctx!.arc(n.x, n.y, 22, 0, Math.PI * 2);
        ctx!.fill();

        // Node circle
        ctx!.fillStyle = `rgba(${nc.join(",")},${n.signal !== "NEUTRAL" ? 1 : 0.5})`;
        ctx!.beginPath();
        ctx!.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx!.fill();

        // Node label
        const meta = MODULE_META[n.key];
        ctx!.fillStyle = `rgba(${nc.join(",")},0.85)`;
        ctx!.font = `600 7.5px 'JetBrains Mono', monospace`;
        ctx!.textAlign = "center";
        ctx!.textBaseline = "top";
        const labelX = n.x + (n.x < cx - 5 ? -20 : n.x > cx + 5 ? 20 : 0);
        const labelY = n.y + (n.y < cy - 20 ? -20 : n.y > cy + 20 ? 12 : -5);
        ctx!.fillText(meta.label, labelX, labelY);
      });

      // Rotating scanner line while running
      if (running) {
        const scanAngle = (t * 0.005) % (Math.PI * 2);
        ctx!.strokeStyle = "rgba(0,212,255,0.25)";
        ctx!.lineWidth = 1;
        ctx!.beginPath();
        ctx!.moveTo(cx, cy);
        ctx!.lineTo(
          cx + nodeRadius * 1.15 * Math.cos(scanAngle),
          cy + nodeRadius * 1.15 * Math.sin(scanAngle)
        );
        ctx!.stroke();
      }

      animRef.current = requestAnimationFrame(draw);
    }

    animRef.current = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(animRef.current);
      ro.disconnect();
    };
  }, [result, running]);

  return (
    <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
  );
}

function ModuleCard({
  name,
  data,
}: {
  name: string;
  data: { signal: string; value: number; label: string; detail: string; error?: boolean };
}) {
  const meta = MODULE_META[name] || { label: name.toUpperCase(), icon: "◎", desc: "" };
  const color = signalColor(data.signal);
  return (
    <div style={{
      background: "rgba(255,255,255,0.02)",
      border: `1px solid ${data.error ? "rgba(247,37,133,0.2)" : "rgba(255,255,255,0.06)"}`,
      borderRadius: 8,
      padding: "10px 12px",
      borderLeft: `2px solid ${color}`,
      height: "100%",
      boxSizing: "border-box",
      overflow: "hidden",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <span style={{ color: "#94a3b8", fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.08em" }}>
          {meta.icon} {meta.label}
        </span>
        <span style={{
          color,
          background: `${color}18`,
          border: `1px solid ${color}35`,
          borderRadius: 3,
          padding: "1px 5px",
          fontSize: "0.58rem",
          fontWeight: 700,
          whiteSpace: "nowrap",
        }}>
          {signalLabel(data.signal)}
        </span>
      </div>
      <div style={{ color: "#475569", fontSize: "0.58rem", marginBottom: 3 }}>{meta.desc}</div>
      {data.label && data.label !== data.signal && (
        <div style={{ color: color, fontSize: "0.62rem", fontWeight: 600 }}>{data.label}</div>
      )}
      {data.detail && data.detail !== "Run analysis" && (
        <div style={{ color: "#334155", fontSize: "0.57rem", marginTop: 2, lineHeight: 1.4 }}>
          {data.detail.slice(0, 70)}
        </div>
      )}
    </div>
  );
}

function ModuleFeedCard({
  name,
  data,
}: {
  name: string;
  data: { signal: string; value: number; label: string; detail: string; error?: boolean };
}) {
  const meta = MODULE_META[name] || { label: name.toUpperCase(), icon: "◎", desc: "" };
  const color = signalColor(data.signal);
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 10,
      padding: "8px 12px",
      borderBottom: "1px solid rgba(255,255,255,0.03)",
      background: "rgba(255,255,255,0.01)",
    }}>
      <div style={{
        width: 7, height: 7, borderRadius: "50%",
        background: color,
        boxShadow: `0 0 6px ${color}`,
        flexShrink: 0,
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ color: "#94a3b8", fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.06em" }}>
          {meta.label}
        </div>
        {data.detail && data.detail !== "Run analysis" && (
          <div style={{ color: "#334155", fontSize: "0.58rem", marginTop: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {data.label && data.label !== data.signal ? data.label : data.detail.slice(0, 40)}
          </div>
        )}
      </div>
      <span style={{
        color,
        fontSize: "0.6rem",
        fontWeight: 700,
        background: `${color}18`,
        border: `1px solid ${color}30`,
        borderRadius: 3,
        padding: "2px 6px",
        whiteSpace: "nowrap",
        flexShrink: 0,
      }}>
        {signalLabel(data.signal)}
      </span>
    </div>
  );
}

export default function Dashboard() {
  const router = useRouter();
  const [symbol, setSymbol] = useState("XAUUSD");
  const [timeframe, setTimeframe] = useState("5m");
  const [category, setCategory] = useState("Metals");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const [history, setHistory] = useState<SignalHistoryItem[]>([]);
  const [triggeredAlerts, setTriggeredAlerts] = useState<AlertItem[]>([]);

  useEffect(() => {
    import("@/lib/supabase").then(({ supabase }) => {
      supabase.auth.getSession().then(({ data: { session } }) => {
        if (!session && !getToken()) {
          router.replace("/login");
          return;
        }
        const userEmail = session?.user?.email || getStoredEmail();
        setEmail(userEmail);
        // Load signal history on mount
        getSignalHistory(10).then(setHistory).catch(() => {});
      });
    });
  }, [router]);

  const addLog = useCallback((msg: string) => {
    setActivityLog(prev =>
      [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 20)
    );
  }, []);

  async function runAnalysis() {
    setRunning(true);
    setError("");
    addLog(`Analyzing ${symbol} / ${timeframe}...`);
    try {
      const r = await analyze(symbol, timeframe);
      setResult(r);
      addLog(`${symbol} → ${r.signal} · ${(r.confidence * 100).toFixed(1)}% confidence`);
      const mods = Object.entries(r.modules);
      const buy = mods.filter(([, v]) => v.signal === "BUY").length;
      const sell = mods.filter(([, v]) => v.signal === "SELL").length;
      addLog(`${buy} BUY · ${sell} SELL · ${mods.length - buy - sell} NEUTRAL`);
      if (r.levels?.entry) {
        addLog(`Entry ${r.levels.entry?.toFixed(2)} → TP ${r.levels.take_profit?.toFixed(2)} | SL ${r.levels.stop_loss?.toFixed(2)} | R:R ${r.levels.risk_reward}`);
      }
      // Refresh history after successful analysis
      getSignalHistory(10).then(setHistory).catch(() => {});
      // Check alerts
      checkAlerts({ symbol, timeframe, signal: r.signal, confidence: r.confidence })
        .then(({ triggered }) => {
          if (triggered.length > 0) setTriggeredAlerts(triggered);
        })
        .catch(() => {});
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Analysis failed";
      setError(msg);
      addLog(`ERROR: ${msg}`);
    } finally {
      setRunning(false);
    }
  }

  const modules = result?.modules ?? {};
  const levels = result?.levels;
  const mainSignal = result?.signal ?? "HOLD";
  const mainColor = signalColor(mainSignal);
  const confidence = result ? (result.confidence * 100).toFixed(1) : "—";

  return (
    <div style={{
      minHeight: "100vh",
      height: "100vh",
      background: "#06060f",
      display: "grid",
      gridTemplateRows: "48px 1fr 176px",
      fontFamily: "'JetBrains Mono', 'Courier New', monospace",
      overflow: "hidden",
      color: "#e2e8f0",
    }} className="ieb-root">
      <style>{`
        @media (max-width: 768px) {
          .ieb-main-grid {
            grid-template-columns: 1fr !important;
            grid-template-rows: auto 320px auto !important;
            overflow-y: auto !important;
            height: auto !important;
          }
          .ieb-left-panel {
            border-right: none !important;
            border-bottom: 1px solid rgba(0,212,255,0.06) !important;
            max-height: none !important;
          }
          .ieb-center-panel {
            height: 320px !important;
          }
          .ieb-right-panel {
            border-left: none !important;
            border-top: 1px solid rgba(0,212,255,0.06) !important;
            max-height: 300px !important;
          }
          .ieb-root {
            height: auto !important;
            overflow: auto !important;
            grid-template-rows: 48px auto auto !important;
          }
          .ieb-bottom-modules {
            height: auto !important;
            overflow-x: auto !important;
          }
          .ieb-bottom-grid {
            grid-template-columns: repeat(6, minmax(120px, 1fr)) !important;
            height: auto !important;
            min-height: 140px !important;
          }
          .ieb-header-strip {
            flex-wrap: wrap !important;
            height: auto !important;
            padding: 8px 12px !important;
            gap: 6px !important;
          }
        }
        @media (max-width: 480px) {
          .ieb-bottom-grid {
            grid-template-columns: repeat(3, minmax(120px, 1fr)) !important;
          }
        }
      `}</style>

      {/* ─── ALERT TOAST ─── */}
      {triggeredAlerts.length > 0 && (
        <div style={{
          position: "fixed", top: 60, right: 16, zIndex: 1000,
          display: "flex", flexDirection: "column", gap: 8,
        }}>
          {triggeredAlerts.map(a => (
            <div key={a.id} style={{
              background: "#0d0d1a",
              border: "1px solid #00f5a0",
              borderLeft: "3px solid #00f5a0",
              borderRadius: 8,
              padding: "10px 14px",
              minWidth: 240,
              boxShadow: "0 0 20px rgba(0,245,160,0.15)",
              fontFamily: "inherit",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                <span style={{ color: "#00f5a0", fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.1em" }}>
                  ◈ ALERT TRIGGERED
                </span>
                <button onClick={() => setTriggeredAlerts(p => p.filter(x => x.id !== a.id))}
                  style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer", fontSize: 12, padding: 0 }}>✕</button>
              </div>
              <div style={{ color: "#e2e8f0", fontSize: "0.7rem", fontWeight: 700 }}>{a.symbol} · {a.timeframe}</div>
              <div style={{ color: "#64748b", fontSize: "0.62rem", marginTop: 2 }}>
                {a.condition === "signal_is_buy"    && "Signal is BUY"}
                {a.condition === "signal_is_sell"   && "Signal is SELL"}
                {a.condition === "any_signal"       && "Signal detected"}
                {a.condition === "confidence_above" && `Confidence ≥ ${((a.threshold ?? 0) * 100).toFixed(0)}%`}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ─── HEADER ─── */}
      <header style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "0 20px",
        borderBottom: "1px solid rgba(0,212,255,0.08)",
        background: "rgba(6,6,15,0.95)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: "#00d4ff",
            boxShadow: "0 0 10px #00d4ff, 0 0 20px rgba(0,212,255,0.4)",
          }} />
          <span style={{ color: "#fff", fontWeight: 700, fontSize: "0.8rem", letterSpacing: "0.12em" }}>
            INSTITUTIONAL EDGE BRAIN
          </span>
        </div>

        {/* Symbol + price strip */}
        {result && (
          <div style={{ display: "flex", alignItems: "center", gap: 16, marginLeft: 24 }}>
            <span style={{ color: "#00d4ff", fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.15em" }}>{symbol}</span>
            {levels?.price && (
              <span style={{ color: "#fff", fontSize: "0.85rem", fontWeight: 800 }}>
                {levels.price.toFixed(levels.price > 100 ? 2 : 4)}
              </span>
            )}
            <div style={{
              color: mainColor,
              background: `${mainColor}15`,
              border: `1px solid ${mainColor}40`,
              borderRadius: 4,
              padding: "2px 10px",
              fontSize: "0.65rem",
              fontWeight: 800,
              letterSpacing: "0.1em",
            }}>
              {signalLabel(mainSignal)}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ color: "#475569", fontSize: "0.6rem" }}>CONFIDENCE</span>
              <span style={{ color: mainColor, fontSize: "0.72rem", fontWeight: 700 }}>{confidence}%</span>
            </div>
          </div>
        )}

        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 10 }}>
          <a href="/backtest" style={{ color: "#2563ff", fontSize: "0.68rem", textDecoration: "none", border: "1px solid rgba(37,99,255,0.3)", padding: "4px 12px", borderRadius: 5, letterSpacing: "0.08em" }}>
            BACKTEST
          </a>
          <a href="/alerts" style={{ color: "#00f5a0", fontSize: "0.68rem", textDecoration: "none", border: "1px solid rgba(0,245,160,0.25)", padding: "4px 12px", borderRadius: 5, letterSpacing: "0.08em", position: "relative", display: "inline-block" }}>
            ALERTS
            {triggeredAlerts.length > 0 && (
              <span style={{ position: "absolute", top: -3, right: -3, width: 7, height: 7, borderRadius: "50%", background: "#00f5a0", boxShadow: "0 0 6px #00f5a0" }} />
            )}
          </a>
          <a href="/account" style={{ color: "#64748b", fontSize: "0.68rem", textDecoration: "none", border: "1px solid rgba(255,255,255,0.07)", padding: "4px 12px", borderRadius: 5, letterSpacing: "0.08em" }}>
            ACCOUNT
          </a>
          {email && <span style={{ color: "#2d3748", fontSize: "0.65rem" }}>{email}</span>}
          <button
            onClick={() => { doLogout(); router.replace("/login"); }}
            style={{ background: "none", border: "1px solid rgba(255,255,255,0.07)", color: "#64748b", fontSize: "0.68rem", padding: "4px 10px", borderRadius: 5, cursor: "pointer", fontFamily: "inherit" }}
          >
            LOGOUT
          </button>
        </div>
      </header>

      {/* ─── MAIN GRID ─── */}
      <main className="ieb-main-grid" style={{
        display: "grid",
        gridTemplateColumns: "264px 1fr 264px",
        overflow: "hidden",
      }}>

        {/* ── LEFT: Controls + Signal ── */}
        <aside className="ieb-left-panel" style={{
          borderRight: "1px solid rgba(0,212,255,0.06)",
          overflowY: "auto",
          padding: 14,
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}>
          {/* Market category tabs */}
          <div>
            <div style={{ color: "#334155", fontSize: "0.6rem", fontWeight: 700, marginBottom: 6, letterSpacing: "0.1em" }}>MARKET</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {Object.keys(SYMBOLS).map(cat => (
                <button key={cat} onClick={() => { setCategory(cat); setSymbol(SYMBOLS[cat][0]); }}
                  style={{
                    fontSize: "0.58rem", fontWeight: 700, padding: "3px 7px", borderRadius: 4, border: "1px solid", cursor: "pointer", fontFamily: "inherit",
                    borderColor: category === cat ? "#00d4ff" : "rgba(255,255,255,0.07)",
                    background: category === cat ? "rgba(0,212,255,0.1)" : "transparent",
                    color: category === cat ? "#00d4ff" : "#64748b",
                  }}
                >{cat.toUpperCase()}</button>
              ))}
            </div>
          </div>

          {/* Symbol selector */}
          <div>
            <div style={{ color: "#334155", fontSize: "0.6rem", fontWeight: 700, marginBottom: 6, letterSpacing: "0.1em" }}>SYMBOL</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {(SYMBOLS[category] || []).map(s => (
                <button key={s} onClick={() => setSymbol(s)}
                  style={{
                    fontSize: "0.63rem", fontWeight: 600, padding: "4px 8px", borderRadius: 4, border: "1px solid", cursor: "pointer", fontFamily: "inherit",
                    borderColor: symbol === s ? "#00d4ff" : "rgba(255,255,255,0.05)",
                    background: symbol === s ? "rgba(0,212,255,0.1)" : "rgba(255,255,255,0.02)",
                    color: symbol === s ? "#00d4ff" : "#94a3b8",
                  }}
                >{s}</button>
              ))}
            </div>
          </div>

          {/* Timeframe */}
          <div>
            <div style={{ color: "#334155", fontSize: "0.6rem", fontWeight: 700, marginBottom: 6, letterSpacing: "0.1em" }}>TIMEFRAME</div>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {TIMEFRAMES.map(tf => (
                <button key={tf} onClick={() => setTimeframe(tf)}
                  style={{
                    fontSize: "0.63rem", fontWeight: 600, padding: "3px 8px", borderRadius: 4, border: "1px solid", cursor: "pointer", fontFamily: "inherit",
                    borderColor: timeframe === tf ? "#7c3aed" : "rgba(255,255,255,0.05)",
                    background: timeframe === tf ? "rgba(124,58,237,0.12)" : "rgba(255,255,255,0.02)",
                    color: timeframe === tf ? "#a78bfa" : "#64748b",
                  }}
                >{tf}</button>
              ))}
            </div>
          </div>

          {/* Analyze button */}
          <button
            onClick={runAnalysis}
            disabled={running}
            style={{
              background: running ? "rgba(0,212,255,0.08)" : "linear-gradient(135deg, #00d4ff 0%, #7c3aed 100%)",
              color: running ? "#00d4ff" : "#fff",
              fontWeight: 700, fontSize: "0.78rem",
              padding: "11px", borderRadius: 8,
              border: running ? "1px solid rgba(0,212,255,0.25)" : "none",
              cursor: running ? "not-allowed" : "pointer",
              fontFamily: "inherit", letterSpacing: "0.1em",
              boxShadow: running ? "none" : "0 0 20px rgba(0,212,255,0.2)",
            }}
          >
            {running ? "◉ ANALYZING..." : "◈ ANALYZE BRAIN"}
          </button>

          {error && (
            <div style={{ color: "#f72585", fontSize: "0.67rem", padding: "8px 10px", background: "rgba(247,37,133,0.07)", borderRadius: 6, border: "1px solid rgba(247,37,133,0.2)" }}>
              {error}
            </div>
          )}

          {/* Brain Decision panel */}
          {result && (
            <div style={{
              background: mainSignal === "BUY" || mainSignal === "STRONG_BUY"
                ? "linear-gradient(135deg, rgba(0,245,160,0.07), rgba(0,245,160,0.02))"
                : mainSignal === "SELL" || mainSignal === "STRONG_SELL"
                  ? "linear-gradient(135deg, rgba(247,37,133,0.07), rgba(247,37,133,0.02))"
                  : "rgba(255,255,255,0.02)",
              border: `1px solid ${mainColor}25`,
              borderRadius: 10,
              padding: 14,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <span style={{ color: "#475569", fontSize: "0.62rem", fontWeight: 700, letterSpacing: "0.1em" }}>BRAIN DECISION</span>
                <span style={{ color: mainColor, fontSize: "1.05rem", fontWeight: 900, letterSpacing: "0.05em" }}>
                  {signalLabel(mainSignal)}
                </span>
              </div>

              {/* Confidence bar */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ color: "#334155", fontSize: "0.58rem" }}>CONFIDENCE</span>
                  <span style={{ color: mainColor, fontSize: "0.68rem", fontWeight: 700 }}>
                    {(result.confidence * 100).toFixed(1)}%
                  </span>
                </div>
                <div style={{ height: 4, background: "rgba(255,255,255,0.05)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${result.confidence * 100}%`, background: `linear-gradient(90deg, ${mainColor}88, ${mainColor})`, borderRadius: 2, transition: "width 0.5s", boxShadow: `0 0 8px ${mainColor}` }} />
                </div>
              </div>

              {/* Trade levels */}
              {levels?.entry && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 5 }}>
                  {[
                    { label: "PRICE",  value: levels.price,       color: "#e2e8f0" },
                    { label: "ENTRY",  value: levels.entry,       color: "#e2e8f0" },
                    { label: "STOP",   value: levels.stop_loss,   color: "#f72585" },
                    { label: "TARGET", value: levels.take_profit, color: "#00f5a0" },
                  ].map(({ label, value, color }) => (
                    <div key={label} style={{ background: "rgba(0,0,0,0.25)", borderRadius: 5, padding: "6px 8px" }}>
                      <div style={{ color: "#334155", fontSize: "0.53rem", fontWeight: 700, marginBottom: 2 }}>{label}</div>
                      <div style={{ color, fontSize: "0.72rem", fontWeight: 700 }}>
                        {value?.toFixed(value > 100 ? 2 : 4)}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {levels?.risk_reward && (
                <div style={{ marginTop: 8, textAlign: "center" }}>
                  <span style={{ color: "#334155", fontSize: "0.58rem" }}>R:R </span>
                  <span style={{ color: "#00d4ff", fontSize: "0.75rem", fontWeight: 700 }}>1:{levels.risk_reward}</span>
                </div>
              )}

              {/* Ensemble */}
              {result.ensemble?.models && Object.keys(result.ensemble.models).length > 0 && (
                <div style={{ marginTop: 10, borderTop: "1px solid rgba(255,255,255,0.04)", paddingTop: 8 }}>
                  <div style={{ color: "#334155", fontSize: "0.57rem", fontWeight: 700, marginBottom: 5, letterSpacing: "0.1em" }}>ENSEMBLE MODELS</div>
                  {Object.entries(result.ensemble.models).map(([name, m]) => (
                    <div key={name} style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                      <span style={{ color: "#475569", fontSize: "0.6rem", textTransform: "uppercase" }}>{name}</span>
                      <span style={{ color: signalColor(m.signal), fontSize: "0.6rem", fontWeight: 700 }}>
                        {signalLabel(m.signal)} {(m.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </aside>

        {/* ── CENTER: Neural Canvas ── */}
        <section className="ieb-center-panel" style={{ position: "relative", background: "#06060f", overflow: "hidden" }}>
          <NeuralCanvas result={result} running={running} />

          {/* Symbol/price overlay — shown when no result yet */}
          {!result && (
            <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)", textAlign: "center", pointerEvents: "none", marginTop: 80 }}>
              <div style={{ color: "#1e293b", fontSize: "0.7rem", letterSpacing: "0.15em" }}>SELECT SYMBOL & ANALYZE</div>
            </div>
          )}

          {/* Current symbol display */}
          <div style={{ position: "absolute", top: 14, left: "50%", transform: "translateX(-50%)", textAlign: "center", pointerEvents: "none" }}>
            <div style={{ color: "#00d4ff", fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.2em", opacity: 0.7 }}>{symbol} · {timeframe}</div>
          </div>

          {running && (
            <div style={{ position: "absolute", bottom: 14, left: "50%", transform: "translateX(-50%)" }}>
              <div style={{ color: "#00d4ff", fontSize: "0.62rem", fontWeight: 700, letterSpacing: "0.2em", opacity: 0.9 }}>
                NEURAL PROCESSING...
              </div>
            </div>
          )}
        </section>

        {/* ── RIGHT: Module Signal Feed ── */}
        <aside className="ieb-right-panel" style={{ borderLeft: "1px solid rgba(0,212,255,0.06)", overflowY: "auto", display: "flex", flexDirection: "column" }}>
          {/* Feed header */}
          <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.04)", display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00f5a0", boxShadow: "0 0 8px #00f5a0" }} />
            <span style={{ color: "#334155", fontSize: "0.6rem", fontWeight: 700, letterSpacing: "0.12em" }}>MODULE ANALYSIS</span>
            {result && (
              <span style={{ marginLeft: "auto", color: "#1e293b", fontSize: "0.57rem" }}>{result.latency_ms}ms</span>
            )}
          </div>

          {/* Module signal list */}
          <div style={{ flex: 1, overflowY: "auto" }}>
            {!result && activityLog.length === 0 && (
              <div style={{ color: "#1e293b", fontSize: "0.63rem", padding: "24px 14px", textAlign: "center", lineHeight: 2 }}>
                Run analysis to see<br />module signals
              </div>
            )}

            {/* When we have results, show module feed */}
            {result && Object.entries(MODULE_META).map(([key]) => (
              <ModuleFeedCard
                key={key}
                name={key}
                data={modules[key] ?? { signal: "NEUTRAL", value: 0, label: "—", detail: "" }}
              />
            ))}

            {/* Activity log below modules */}
            {activityLog.length > 0 && (
              <div style={{ padding: "8px 14px", borderTop: result ? "1px solid rgba(255,255,255,0.04)" : "none" }}>
                <div style={{ color: "#1e293b", fontSize: "0.57rem", fontWeight: 700, letterSpacing: "0.1em", marginBottom: 6 }}>ACTIVITY</div>
                {activityLog.map((entry, i) => (
                  <div key={i} style={{ color: i === 0 ? "#475569" : "#1e293b", fontSize: "0.6rem", marginBottom: 5, lineHeight: 1.5 }}>
                    {entry}
                  </div>
                ))}
              </div>
            )}

            {/* Signal history */}
            {history.length > 0 && (
              <div style={{ borderTop: "1px solid rgba(255,255,255,0.04)", padding: "8px 0 4px" }}>
                <div style={{ padding: "0 12px 6px", color: "#1e293b", fontSize: "0.57rem", fontWeight: 700, letterSpacing: "0.1em" }}>RECENT SIGNALS</div>
                {history.map((h) => {
                  const col = signalColor(h.direction);
                  const time = h.created_at
                    ? new Date(h.created_at).toLocaleString("en-GB", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })
                    : "—";
                  return (
                    <div key={h.id} style={{
                      display: "flex", alignItems: "center", gap: 8,
                      padding: "6px 12px", borderBottom: "1px solid rgba(255,255,255,0.02)",
                    }}>
                      <div style={{ width: 5, height: 5, borderRadius: "50%", background: col, flexShrink: 0 }} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ color: "#64748b", fontSize: "0.6rem", fontWeight: 700 }}>
                          {h.symbol} <span style={{ color: "#334155", fontWeight: 400 }}>· {h.timeframe}</span>
                        </div>
                        <div style={{ color: "#1e293b", fontSize: "0.55rem" }}>{time}</div>
                      </div>
                      <span style={{ color: col, fontSize: "0.58rem", fontWeight: 700, flexShrink: 0 }}>
                        {h.direction}
                      </span>
                      {h.confidence != null && (
                        <span style={{ color: "#1e293b", fontSize: "0.55rem", flexShrink: 0 }}>
                          {(h.confidence * 100).toFixed(0)}%
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </aside>
      </main>

      {/* ─── BOTTOM: 12 Module Cards ─── */}
      <div className="ieb-bottom-modules" style={{
        borderTop: "1px solid rgba(0,212,255,0.06)",
        overflowX: "auto",
        overflowY: "hidden",
        padding: "10px 14px",
        flexShrink: 0,
      }}>
        <div className="ieb-bottom-grid" style={{
          display: "grid",
          gridTemplateColumns: "repeat(12, minmax(120px, 1fr))",
          gap: 8,
          height: 154,
        }}>
          {Object.entries(MODULE_META).map(([key]) => (
            <ModuleCard
              key={key}
              name={key}
              data={modules[key] ?? { signal: "NEUTRAL", value: 0, label: "—", detail: "Run analysis" }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
