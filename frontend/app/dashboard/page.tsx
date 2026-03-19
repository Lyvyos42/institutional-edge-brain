"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { analyze, type AnalysisResult } from "@/lib/api";
import { getToken, getEmail as getStoredEmail, logout as doLogout } from "@/lib/auth";

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
  if (s === "BUY" || s === "BULLISH") return "#00f5a0";
  if (s === "SELL" || s === "BEARISH") return "#f72585";
  return "#64748b";
}

function NeuralCanvas({ result, running }: { result: AnalysisResult | null; running: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const W = canvas.width = canvas.offsetWidth;
    const H = canvas.height = canvas.offsetHeight;
    const cx = W / 2;
    const cy = H / 2;

    const moduleKeys = Object.keys(MODULE_META);
    const nodeRadius = Math.min(W, H) * 0.36;
    const nodes = moduleKeys.map((key, i) => {
      const angle = (i / moduleKeys.length) * Math.PI * 2 - Math.PI / 2;
      return {
        x: cx + nodeRadius * Math.cos(angle),
        y: cy + nodeRadius * Math.sin(angle),
        key,
        signal: result?.modules?.[key]?.signal ?? "NEUTRAL",
      };
    });

    function draw(t: number) {
      ctx!.clearRect(0, 0, W, H);

      // Background grid
      ctx!.strokeStyle = "rgba(0,212,255,0.03)";
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
          const alpha = sameSignal ? 0.12 : 0.04;
          const color = sameSignal
            ? (n.signal === "BUY" ? "0,245,160" : "247,37,133")
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
      const glowColor = mainSignal === "BUY"
        ? [0, 245, 160]
        : mainSignal === "SELL"
          ? [247, 37, 133]
          : [0, 212, 255];
      const pulse = 0.6 + 0.4 * Math.sin(t * 0.003);
      const grd = ctx!.createRadialGradient(cx, cy, 0, cx, cy, 80 * pulse);
      grd.addColorStop(0, `rgba(${glowColor.join(",")},${running ? 0.4 : 0.2})`);
      grd.addColorStop(1, "rgba(0,0,0,0)");
      ctx!.fillStyle = grd;
      ctx!.beginPath();
      ctx!.arc(cx, cy, 80 * pulse, 0, Math.PI * 2);
      ctx!.fill();

      // Center ring
      ctx!.strokeStyle = `rgba(${glowColor.join(",")},0.6)`;
      ctx!.lineWidth = 2;
      ctx!.beginPath();
      ctx!.arc(cx, cy, 28, 0, Math.PI * 2);
      ctx!.stroke();

      // Center text
      ctx!.fillStyle = `rgba(${glowColor.join(",")},1)`;
      ctx!.font = `bold 13px 'JetBrains Mono', monospace`;
      ctx!.textAlign = "center";
      ctx!.textBaseline = "middle";
      ctx!.fillText(running ? "..." : mainSignal, cx, cy);

      // Module nodes
      nodes.forEach((n, i) => {
        const nc = n.signal === "BUY"
          ? [0, 245, 160]
          : n.signal === "SELL"
            ? [247, 37, 133]
            : [100, 116, 139];
        const nodePulse = 0.7 + 0.3 * Math.sin(t * 0.002 + i * 0.5);
        const r = 8 * nodePulse;

        // Node glow
        const ng = ctx!.createRadialGradient(n.x, n.y, 0, n.x, n.y, 20);
        ng.addColorStop(0, `rgba(${nc.join(",")},0.4)`);
        ng.addColorStop(1, "rgba(0,0,0,0)");
        ctx!.fillStyle = ng;
        ctx!.beginPath();
        ctx!.arc(n.x, n.y, 20, 0, Math.PI * 2);
        ctx!.fill();

        // Node circle
        ctx!.fillStyle = `rgba(${nc.join(",")},0.9)`;
        ctx!.beginPath();
        ctx!.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx!.fill();

        // Node label
        const meta = MODULE_META[n.key];
        ctx!.fillStyle = `rgba(${nc.join(",")},0.8)`;
        ctx!.font = `500 8px 'JetBrains Mono', monospace`;
        ctx!.textAlign = "center";
        ctx!.textBaseline = "top";
        const labelX = n.x + (n.x < cx ? -18 : n.x > cx + 5 ? 18 : 0);
        const labelY = n.y + (n.y < cy - 20 ? -22 : n.y > cy + 20 ? 14 : -6);
        ctx!.fillText(meta.label, labelX, labelY);
      });

      // Rotating scanner line while running
      if (running) {
        const scanAngle = (t * 0.005) % (Math.PI * 2);
        ctx!.strokeStyle = "rgba(0,212,255,0.3)";
        ctx!.lineWidth = 1;
        ctx!.beginPath();
        ctx!.moveTo(cx, cy);
        ctx!.lineTo(
          cx + nodeRadius * 1.1 * Math.cos(scanAngle),
          cy + nodeRadius * 1.1 * Math.sin(scanAngle)
        );
        ctx!.stroke();
      }

      animRef.current = requestAnimationFrame(draw);
    }

    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
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
      transition: "border-color 0.3s",
      height: "100%",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 4 }}>
        <span style={{ color: "#94a3b8", fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.1em" }}>
          {meta.icon} {meta.label}
        </span>
        <span style={{
          color,
          background: `${color}15`,
          border: `1px solid ${color}30`,
          borderRadius: 4,
          padding: "1px 6px",
          fontSize: "0.6rem",
          fontWeight: 700,
        }}>
          {data.signal}
        </span>
      </div>
      <div style={{ color: "#64748b", fontSize: "0.6rem", marginBottom: 4 }}>{meta.desc}</div>
      {data.label && data.label !== data.signal && (
        <div style={{ color: "#94a3b8", fontSize: "0.65rem" }}>{data.label}</div>
      )}
      {data.detail && (
        <div style={{ color: "#334155", fontSize: "0.58rem", marginTop: 2, lineHeight: 1.4 }}>
          {data.detail.slice(0, 80)}
        </div>
      )}
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

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setEmail(getStoredEmail());
  }, [router]);

  const addLog = useCallback((msg: string) => {
    setActivityLog(prev =>
      [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev].slice(0, 30)
    );
  }, []);

  async function runAnalysis() {
    setRunning(true);
    setError("");
    addLog(`Analyzing ${symbol} on ${timeframe}...`);
    try {
      const r = await analyze(symbol, timeframe);
      setResult(r);
      addLog(`${symbol} → ${r.signal} (${(r.confidence * 100).toFixed(1)}% confidence)`);
      const mods = Object.entries(r.modules);
      const buy = mods.filter(([, v]) => v.signal === "BUY").length;
      const sell = mods.filter(([, v]) => v.signal === "SELL").length;
      addLog(`Modules: ${buy} BUY · ${sell} SELL · ${mods.length - buy - sell} NEUTRAL`);
      if (r.levels?.entry) {
        addLog(`Entry ${r.levels.entry} → TP ${r.levels.take_profit} | SL ${r.levels.stop_loss} | R:R ${r.levels.risk_reward}`);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Analysis failed";
      setError(msg);
      addLog(`ERROR: ${msg}`);
    } finally {
      setRunning(false);
    }
  }

  function signalBgGradient(s: string): string {
    if (s === "BUY")  return "linear-gradient(135deg, rgba(0,245,160,0.08), rgba(0,245,160,0.02))";
    if (s === "SELL") return "linear-gradient(135deg, rgba(247,37,133,0.08), rgba(247,37,133,0.02))";
    return "rgba(255,255,255,0.02)";
  }

  const modules = result?.modules ?? {};
  const levels = result?.levels;
  const mainColor = signalColor(result?.signal ?? "HOLD");

  return (
    <div style={{
      minHeight: "100vh",
      background: "#06060f",
      display: "grid",
      gridTemplateRows: "52px 1fr auto",
      fontFamily: "'JetBrains Mono', monospace",
    }}>

      {/* HEADER */}
      <header style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "0 20px",
        borderBottom: "1px solid rgba(255,255,255,0.05)",
        background: "#06060f",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#00d4ff", boxShadow: "0 0 8px #00d4ff", animation: "pulse-glow 2s ease-in-out infinite" }} />
          <span style={{ color: "#fff", fontWeight: 700, fontSize: "0.8rem", letterSpacing: "0.1em" }}>
            INSTITUTIONAL EDGE BRAIN
          </span>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
          <a href="/backtest" style={{ color: "#2563ff", fontSize: "0.7rem", textDecoration: "none", border: "1px solid rgba(37,99,255,0.35)", padding: "4px 12px", borderRadius: 5, letterSpacing: "0.08em" }}>
            BACKTEST
          </a>
          <a href="/account" style={{ color: "#64748b", fontSize: "0.7rem", textDecoration: "none", border: "1px solid rgba(255,255,255,0.08)", padding: "4px 12px", borderRadius: 5, letterSpacing: "0.08em" }}>
            ACCOUNT
          </a>
          <span style={{ color: "#334155", fontSize: "0.7rem" }}>{email}</span>
          <button
            onClick={() => { doLogout(); router.replace("/login"); }}
            style={{ background: "none", border: "1px solid rgba(255,255,255,0.08)", color: "#64748b", fontSize: "0.7rem", padding: "4px 10px", borderRadius: 5, cursor: "pointer", fontFamily: "inherit" }}
          >
            LOGOUT
          </button>
        </div>
      </header>

      {/* MAIN GRID */}
      <main style={{
        display: "grid",
        gridTemplateColumns: "260px 1fr 260px",
        overflow: "hidden",
        height: "calc(100vh - 52px - 160px)",
      }}>

        {/* LEFT — Controls + Signal */}
        <aside style={{
          borderRight: "1px solid rgba(255,255,255,0.05)",
          overflowY: "auto",
          padding: 16,
          display: "flex",
          flexDirection: "column",
          gap: 12,
        }}>
          {/* Category tabs */}
          <div>
            <div style={{ color: "#334155", fontSize: "0.6rem", fontWeight: 700, marginBottom: 6, letterSpacing: "0.1em" }}>MARKET</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {Object.keys(SYMBOLS).map(cat => (
                <button
                  key={cat}
                  onClick={() => { setCategory(cat); setSymbol(SYMBOLS[cat][0]); }}
                  style={{
                    fontSize: "0.6rem", fontWeight: 700, padding: "3px 8px", borderRadius: 4, border: "1px solid", cursor: "pointer", fontFamily: "inherit",
                    borderColor: category === cat ? "#00d4ff" : "rgba(255,255,255,0.08)",
                    background: category === cat ? "rgba(0,212,255,0.1)" : "transparent",
                    color: category === cat ? "#00d4ff" : "#64748b",
                  }}
                >
                  {cat.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Symbol selector */}
          <div>
            <div style={{ color: "#334155", fontSize: "0.6rem", fontWeight: 700, marginBottom: 6, letterSpacing: "0.1em" }}>SYMBOL</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
              {(SYMBOLS[category] || []).map(s => (
                <button
                  key={s}
                  onClick={() => setSymbol(s)}
                  style={{
                    fontSize: "0.65rem", fontWeight: 600, padding: "4px 8px", borderRadius: 4, border: "1px solid", cursor: "pointer", fontFamily: "inherit",
                    borderColor: symbol === s ? "#00d4ff" : "rgba(255,255,255,0.06)",
                    background: symbol === s ? "rgba(0,212,255,0.1)" : "rgba(255,255,255,0.02)",
                    color: symbol === s ? "#00d4ff" : "#94a3b8",
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Timeframe */}
          <div>
            <div style={{ color: "#334155", fontSize: "0.6rem", fontWeight: 700, marginBottom: 6, letterSpacing: "0.1em" }}>TIMEFRAME</div>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {TIMEFRAMES.map(tf => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  style={{
                    fontSize: "0.65rem", fontWeight: 600, padding: "3px 8px", borderRadius: 4, border: "1px solid", cursor: "pointer", fontFamily: "inherit",
                    borderColor: timeframe === tf ? "#7c3aed" : "rgba(255,255,255,0.06)",
                    background: timeframe === tf ? "rgba(124,58,237,0.1)" : "rgba(255,255,255,0.02)",
                    color: timeframe === tf ? "#a78bfa" : "#64748b",
                  }}
                >
                  {tf}
                </button>
              ))}
            </div>
          </div>

          {/* Analyze button */}
          <button
            onClick={runAnalysis}
            disabled={running}
            style={{
              background: running ? "rgba(0,212,255,0.1)" : "linear-gradient(135deg,#00d4ff,#7c3aed)",
              color: running ? "#00d4ff" : "#fff",
              fontWeight: 700, fontSize: "0.8rem",
              padding: "12px", borderRadius: 8,
              border: running ? "1px solid rgba(0,212,255,0.3)" : "none",
              cursor: running ? "not-allowed" : "pointer",
              fontFamily: "inherit", letterSpacing: "0.1em",
            }}
          >
            {running ? "◉ ANALYZING..." : "◈ ANALYZE BRAIN"}
          </button>

          {error && (
            <div style={{ color: "#f72585", fontSize: "0.7rem", padding: "8px 10px", background: "rgba(247,37,133,0.08)", borderRadius: 6, border: "1px solid rgba(247,37,133,0.2)" }}>
              {error}
            </div>
          )}

          {/* Signal output */}
          {result && (
            <div style={{ background: signalBgGradient(result.signal), border: `1px solid ${mainColor}25`, borderRadius: 10, padding: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <span style={{ color: "#64748b", fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.1em" }}>BRAIN DECISION</span>
                <span style={{ color: mainColor, fontSize: "1.1rem", fontWeight: 900 }}>{result.signal}</span>
              </div>

              {/* Confidence bar */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ color: "#475569", fontSize: "0.6rem" }}>CONFIDENCE</span>
                  <span style={{ color: mainColor, fontSize: "0.7rem", fontWeight: 700 }}>
                    {(result.confidence * 100).toFixed(1)}%
                  </span>
                </div>
                <div style={{ height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ height: "100%", width: `${result.confidence * 100}%`, background: mainColor, borderRadius: 2, transition: "width 0.5s" }} />
                </div>
              </div>

              {/* Trade levels */}
              {levels?.entry && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
                  {[
                    { label: "PRICE",  value: levels.price,       color: undefined },
                    { label: "ENTRY",  value: levels.entry,       color: undefined },
                    { label: "STOP",   value: levels.stop_loss,   color: "#f72585" },
                    { label: "TARGET", value: levels.take_profit, color: "#00f5a0" },
                  ].map(({ label, value, color }) => (
                    <div key={label} style={{ background: "rgba(0,0,0,0.3)", borderRadius: 6, padding: "6px 8px" }}>
                      <div style={{ color: "#334155", fontSize: "0.55rem", fontWeight: 700, marginBottom: 2 }}>{label}</div>
                      <div style={{ color: color || "#e2e8f0", fontSize: "0.75rem", fontWeight: 700 }}>
                        {value?.toFixed(value > 100 ? 2 : 4)}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {levels?.risk_reward && (
                <div style={{ marginTop: 8, textAlign: "center" }}>
                  <span style={{ color: "#334155", fontSize: "0.6rem" }}>R:R </span>
                  <span style={{ color: "#00d4ff", fontSize: "0.75rem", fontWeight: 700 }}>
                    1:{levels.risk_reward}
                  </span>
                </div>
              )}

              {/* Ensemble models */}
              {result.ensemble?.models && Object.keys(result.ensemble.models).length > 0 && (
                <div style={{ marginTop: 10, borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: 8 }}>
                  <div style={{ color: "#334155", fontSize: "0.58rem", fontWeight: 700, marginBottom: 6, letterSpacing: "0.1em" }}>
                    ENSEMBLE MODELS
                  </div>
                  {Object.entries(result.ensemble.models).map(([name, m]) => (
                    <div key={name} style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                      <span style={{ color: "#475569", fontSize: "0.62rem", textTransform: "uppercase" }}>{name}</span>
                      <span style={{ color: signalColor(m.signal), fontSize: "0.62rem", fontWeight: 700 }}>
                        {m.signal} {(m.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </aside>

        {/* CENTER — Neural Canvas */}
        <section style={{ position: "relative", background: "#06060f", overflow: "hidden" }}>
          <NeuralCanvas result={result} running={running} />
          {/* Symbol + price overlay */}
          <div style={{ position: "absolute", top: 16, left: "50%", transform: "translateX(-50%)", textAlign: "center", pointerEvents: "none" }}>
            <div style={{ color: "#00d4ff", fontSize: "0.75rem", fontWeight: 700, letterSpacing: "0.2em" }}>{symbol}</div>
            {result?.levels?.price && (
              <div style={{ color: "#fff", fontSize: "1.4rem", fontWeight: 800, marginTop: 2 }}>
                {result.levels.price.toFixed(result.levels.price > 100 ? 2 : 4)}
              </div>
            )}
          </div>
          {running && (
            <div style={{ position: "absolute", bottom: 16, left: "50%", transform: "translateX(-50%)" }}>
              <div style={{ color: "#00d4ff", fontSize: "0.65rem", fontWeight: 700, letterSpacing: "0.2em", animation: "pulse-glow 2s ease-in-out infinite" }}>
                NEURAL PROCESSING...
              </div>
            </div>
          )}
        </section>

        {/* RIGHT — Activity Log */}
        <aside style={{ borderLeft: "1px solid rgba(255,255,255,0.05)", overflowY: "auto", display: "flex", flexDirection: "column" }}>
          <div style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.04)", display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00f5a0", animation: "pulse-glow 2s ease-in-out infinite" }} />
            <span style={{ color: "#334155", fontSize: "0.6rem", fontWeight: 700, letterSpacing: "0.1em" }}>MODULE FEED</span>
          </div>
          <div style={{ flex: 1, overflowY: "auto", padding: "8px 14px" }}>
            {activityLog.length === 0 && (
              <div style={{ color: "#1e293b", fontSize: "0.65rem", marginTop: 20, textAlign: "center" }}>
                Run analysis to see output
              </div>
            )}
            {activityLog.map((entry, i) => (
              <div key={i} style={{ color: i === 0 ? "#94a3b8" : "#334155", fontSize: "0.62rem", marginBottom: 6, lineHeight: 1.5, borderBottom: "1px solid rgba(255,255,255,0.02)", paddingBottom: 4 }}>
                {entry}
              </div>
            ))}
          </div>

          {/* Latency info */}
          {result && (
            <div style={{ padding: "8px 14px", borderTop: "1px solid rgba(255,255,255,0.04)", fontSize: "0.58rem", color: "#1e293b" }}>
              Analysis: {result.latency_ms}ms · {Object.keys(result.modules).length} modules
            </div>
          )}
        </aside>
      </main>

      {/* BOTTOM — 12 Module Cards */}
      <div style={{ height: 160, borderTop: "1px solid rgba(255,255,255,0.05)", overflowX: "auto", overflowY: "hidden", padding: "12px 16px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(12, minmax(130px, 1fr))", gap: 8, height: "100%" }}>
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
