"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { API, analyze, getSignalHistory, checkAlerts, type AnalysisResult, type SignalHistoryItem, type AlertItem } from "@/lib/api";
import { getToken, getEmail as getStoredEmail, logoutSync as doLogout } from "@/lib/auth";

// ── Constants ──────────────────────────────────────────────────────────────────
const SYMBOLS: Record<string, string[]> = {
  "Forex":   ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURGBP","EURJPY","GBPJPY"],
  "Metals":  ["XAUUSD","XAGUSD"],
  "Energy":  ["USOIL","UKOIL","NATGAS"],
  "Crypto":  ["BTCUSD","ETHUSD"],
  "Indices": ["SPX500","NAS100","GER40","UK100","JPN225"],
  "Stocks":  ["AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META"],
};

const TIMEFRAMES = ["1m","5m","15m","30m","1h","4h","1d"];

const MODULE_META: Record<string, { label: string; desc: string }> = {
  entropy:     { label: "ENTROPY",     desc: "Market order formation" },
  vpin:        { label: "VPIN",        desc: "Smart money activity" },
  vol_accum:   { label: "VOL ACCUM",   desc: "Institutional accumulation" },
  fix_time:    { label: "FIX TIME",    desc: "London Fix manipulation" },
  month_flow:  { label: "MONTH FLOW",  desc: "Month-end rebalancing" },
  iceberg:     { label: "ICEBERG",     desc: "Hidden orders detection" },
  cot:         { label: "COT",         desc: "Commitment of Traders" },
  correlation: { label: "CORRELATION", desc: "Asset correlation breaks" },
  vol_profile: { label: "VPOC",        desc: "Volume point of control" },
  stop_run:    { label: "STOP RUN",    desc: "Stop hunt profiling" },
  sweep:       { label: "SWEEP",       desc: "Liquidity sweep detection" },
  volatility:  { label: "VOLATILITY",  desc: "Vol regime analysis" },
};

function signalColor(s: string): string {
  if (s === "BUY"  || s === "STRONG_BUY"  || s === "BULLISH") return "#4ade80";
  if (s === "SELL" || s === "STRONG_SELL" || s === "BEARISH") return "#f87171";
  return "#64748b";
}
function signalClass(s: string): string {
  if (s === "BUY"  || s === "STRONG_BUY"  || s === "BULLISH") return "buy";
  if (s === "SELL" || s === "STRONG_SELL" || s === "BEARISH") return "sell";
  return "neutral";
}
function signalLabel(s: string): string {
  const map: Record<string,string> = {
    BUY:"BUY",SELL:"SELL",NEUTRAL:"NEUTRAL",HOLD:"HOLD",
    STRONG_BUY:"STRONG BUY",STRONG_SELL:"STRONG SELL",
    BULLISH:"BULL",BEARISH:"BEAR",
  };
  return map[s] || s;
}

// ── Neural Canvas ──────────────────────────────────────────────────────────────
function NeuralCanvas({ result, running }: { result: AnalysisResult | null; running: boolean }) {
  const canvasRef  = useRef<HTMLCanvasElement>(null);
  const animRef    = useRef<number>(0);
  const stateRef   = useRef<{
    initialized: boolean;
    time: number;
    dust: { x:number; y:number; vx:number; vy:number; size:number; brightness:number }[];
    coreRings: { radius:number; speed:number; segments:number; offset:number }[];
    energyParticles: { linkIndex:number; progress:number; speed:number; size:number; brightness:number }[];
    moduleState: Record<string, { active:boolean; intensity:number; pulsePhase:number; orbitals:{ angle:number; radius:number; speed:number }[] }>;
    particles: { x:number; y:number; targetX:number; targetY:number; progress:number; speed:number; color:string; size:number; trail:{ x:number; y:number }[] }[];
    internalLinks: { source:string; target:string; type:"primary"|"secondary"|"cross" }[];
    prevResultId: string;
  }>({
    initialized: false,
    time: 0,
    dust: [],
    coreRings: [
      { radius: 30, speed: 0.02,   segments: 8,  offset: 0 },
      { radius: 45, speed: -0.015, segments: 12, offset: Math.PI / 6 },
      { radius: 60, speed: 0.01,   segments: 16, offset: 0 },
    ],
    energyParticles: [],
    moduleState: {},
    particles: [],
    internalLinks: [],
    prevResultId: "",
  });

  // ── One-time init + re-init on resize via ResizeObserver
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    function initState(W: number, H: number) {
      const s = stateRef.current;
      const moduleKeys = Object.keys(MODULE_META);
      const n = moduleKeys.length;
      const cx = W / 2, cy = H / 2;
      const ringRadius = Math.min(W, H) * 0.36;

      // Dust
      s.dust = Array.from({ length: 80 }, () => ({
        x: Math.random() * W,
        y: Math.random() * H,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        size: Math.random() * 1.5,
        brightness: 0.1 + Math.random() * 0.2,
      }));

      // Module state (preserve existing active/intensity if already set)
      moduleKeys.forEach((key, i) => {
        if (!s.moduleState[key]) {
          s.moduleState[key] = {
            active: false,
            intensity: 0,
            pulsePhase: Math.random() * Math.PI * 2,
            orbitals: Array.from({ length: 3 }, (_, j) => ({
              angle: (Math.PI * 2 / 3) * j,
              radius: 15 + Math.random() * 5,
              speed: 0.02 + Math.random() * 0.02,
            })),
          };
        }
      });

      // Internal links
      s.internalLinks = [];
      moduleKeys.forEach((id, i) => {
        s.internalLinks.push({ source: id, target: moduleKeys[(i + 1) % n], type: "primary" });
        s.internalLinks.push({ source: id, target: moduleKeys[(i + 2) % n], type: "secondary" });
        s.internalLinks.push({ source: id, target: moduleKeys[(i + Math.floor(n / 2)) % n], type: "cross" });
      });

      // Energy particles
      s.energyParticles = Array.from({ length: 30 }, () => ({
        linkIndex: Math.floor(Math.random() * s.internalLinks.length),
        progress: Math.random(),
        speed: 0.005 + Math.random() * 0.01,
        size: 1 + Math.random() * 2,
        brightness: 0.5 + Math.random() * 0.5,
      }));

      s.initialized = true;
    }

    const ro = new ResizeObserver(() => {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
      initState(canvas.width, canvas.height);
    });
    ro.observe(canvas);
    canvas.width  = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
    initState(canvas.width, canvas.height);

    return () => ro.disconnect();
  }, []);

  // ── React to result changes: update module states + spawn trail particles
  useEffect(() => {
    if (!result) return;
    const s = stateRef.current;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2;
    const ringRadius = Math.min(W, H) * 0.36;
    const moduleKeys = Object.keys(MODULE_META);
    const n = moduleKeys.length;

    const resultId = result.signal + JSON.stringify(Object.keys(result.modules ?? {}).map(k => result.modules[k]?.signal).join(""));
    if (resultId === s.prevResultId) return;
    s.prevResultId = resultId;

    moduleKeys.forEach((key, i) => {
      const sig = result.modules?.[key]?.signal ?? "NEUTRAL";
      const isBuy  = sig === "BUY";
      const isSell = sig === "SELL";
      const active = isBuy || isSell;
      const intensity = isBuy ? 1.0 : isSell ? -1.0 : 0;

      if (!s.moduleState[key]) {
        s.moduleState[key] = {
          active, intensity,
          pulsePhase: Math.random() * Math.PI * 2,
          orbitals: Array.from({ length: 3 }, (_, j) => ({
            angle: (Math.PI * 2 / 3) * j,
            radius: 15 + Math.random() * 5,
            speed: 0.02 + Math.random() * 0.02,
          })),
        };
      } else {
        s.moduleState[key].active = active;
        s.moduleState[key].intensity = intensity;
      }

      if (active) {
        const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
        const nx = cx + ringRadius * Math.cos(angle);
        const ny = cy + ringRadius * Math.sin(angle);
        const color = isBuy ? "#4ade80" : "#f87171";
        for (let p = 0; p < 3; p++) {
          s.particles.push({
            x: nx, y: ny,
            targetX: cx, targetY: cy,
            progress: 0,
            speed: 0.015 + Math.random() * 0.02,
            color,
            size: 2 + Math.random() * 2,
            trail: [],
          });
        }
      }
    });
  }, [result]);

  // ── Animation loop (stable — no deps on result/running to avoid restarts)
  const runningRef = useRef(running);
  const resultRef  = useRef(result);
  useEffect(() => { runningRef.current = running; }, [running]);
  useEffect(() => { resultRef.current = result; }, [result]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    function draw() {
      const s = stateRef.current;
      if (!s.initialized) { animRef.current = requestAnimationFrame(draw); return; }

      const W = canvas!.width, H = canvas!.height;
      const cx = W / 2, cy = H / 2;
      const ringRadius = Math.min(W, H) * 0.36;
      const moduleKeys = Object.keys(MODULE_META);
      const n = moduleKeys.length;
      s.time += 0.016;
      const time = s.time;

      // Pre-compute node positions
      const nodePos: Record<string, { x: number; y: number }> = {};
      moduleKeys.forEach((key, i) => {
        const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
        nodePos[key] = {
          x: cx + ringRadius * Math.cos(angle),
          y: cy + ringRadius * Math.sin(angle),
        };
      });

      ctx!.clearRect(0, 0, W, H);

      // ── LAYER 1: Background dust
      s.dust.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = W;
        if (p.x > W) p.x = 0;
        if (p.y < 0) p.y = H;
        if (p.y > H) p.y = 0;
        ctx!.fillStyle = `rgba(6,182,212,${p.brightness})`;
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx!.fill();
      });

      // ── LAYER 2: Radial grid
      ctx!.strokeStyle = "rgba(6,182,212,0.05)";
      ctx!.lineWidth = 1;
      for (let r = 50; r < ringRadius + 120; r += 50) {
        ctx!.beginPath();
        ctx!.arc(cx, cy, r, 0, Math.PI * 2);
        ctx!.stroke();
      }
      for (let i = 0; i < 12; i++) {
        const a = (Math.PI * 2 / 12) * i;
        ctx!.beginPath();
        ctx!.moveTo(cx, cy);
        ctx!.lineTo(cx + Math.cos(a) * (ringRadius + 120), cy + Math.sin(a) * (ringRadius + 120));
        ctx!.stroke();
      }

      // ── LAYER 3: Bezier synaptic web
      const pulse = (Math.sin(time * 2) + 1) * 0.5;
      s.internalLinks.forEach(link => {
        const a = nodePos[link.source];
        const b = nodePos[link.target];
        if (!a || !b) return;
        let alpha: number, width: number;
        if (link.type === "primary")   { alpha = 0.15 + pulse * 0.1; width = 1.5; }
        else if (link.type === "secondary") { alpha = 0.08 + pulse * 0.05; width = 1.0; }
        else                           { alpha = 0.04 + pulse * 0.02; width = 0.5; }

        const midX = (a.x + b.x) / 2;
        const midY = (a.y + b.y) / 2;
        const cpX  = midX + (cx - midX) * 0.3;
        const cpY  = midY + (cy - midY) * 0.3;

        ctx!.beginPath();
        ctx!.moveTo(a.x, a.y);
        ctx!.quadraticCurveTo(cpX, cpY, b.x, b.y);
        ctx!.strokeStyle = `rgba(6,182,212,${alpha})`;
        ctx!.lineWidth = width + (link.type === "primary" ? pulse * 0.5 : 0);
        ctx!.stroke();
      });

      // ── LAYER 4: Energy flow particles
      s.energyParticles.forEach(ep => {
        if (s.internalLinks.length === 0) return;
        const link = s.internalLinks[ep.linkIndex % s.internalLinks.length];
        const a = nodePos[link?.source];
        const b = nodePos[link?.target];
        if (!a || !b) return;

        const t = ep.progress;
        const midX = (a.x + b.x) / 2;
        const midY = (a.y + b.y) / 2;
        const cpX  = midX + (cx - midX) * 0.3;
        const cpY  = midY + (cy - midY) * 0.3;
        const px = (1-t)*(1-t)*a.x + 2*(1-t)*t*cpX + t*t*b.x;
        const py = (1-t)*(1-t)*a.y + 2*(1-t)*t*cpY + t*t*b.y;

        ctx!.shadowBlur = 8;
        ctx!.shadowColor = "#06b6d4";
        ctx!.fillStyle = `rgba(6,182,212,${ep.brightness})`;
        ctx!.beginPath();
        ctx!.arc(px, py, ep.size, 0, Math.PI * 2);
        ctx!.fill();
        ctx!.shadowBlur = 0;

        ep.progress += ep.speed;
        if (ep.progress > 1) {
          ep.progress = 0;
          ep.linkIndex = Math.floor(Math.random() * s.internalLinks.length);
        }
      });

      // ── LAYER 5: Core processor
      const corePulse = (Math.sin(time * 3) + 1) * 0.5;
      const outerGlow = ctx!.createRadialGradient(cx, cy, 0, cx, cy, 80);
      outerGlow.addColorStop(0, "rgba(6,182,212,0.3)");
      outerGlow.addColorStop(0.5, "rgba(6,182,212,0.1)");
      outerGlow.addColorStop(1, "rgba(6,182,212,0)");
      ctx!.fillStyle = outerGlow;
      ctx!.beginPath();
      ctx!.arc(cx, cy, 80 + corePulse * 10, 0, Math.PI * 2);
      ctx!.fill();

      s.coreRings.forEach(ring => {
        ring.offset += ring.speed;
        ctx!.strokeStyle = `rgba(6,182,212,${0.2 + corePulse * 0.1})`;
        ctx!.lineWidth = 1;
        for (let i = 0; i < ring.segments; i++) {
          const segAngle = (Math.PI * 2 / ring.segments);
          const startA = ring.offset + i * segAngle;
          const endA   = startA + segAngle * 0.6;
          ctx!.beginPath();
          ctx!.arc(cx, cy, ring.radius + corePulse * 3, startA, endA);
          ctx!.stroke();
        }
      });

      ctx!.shadowBlur = 20;
      ctx!.shadowColor = "#06b6d4";
      const coreGrad = ctx!.createRadialGradient(cx, cy, 0, cx, cy, 15);
      coreGrad.addColorStop(0, "#ffffff");
      coreGrad.addColorStop(0.3, "#67e8f9");
      coreGrad.addColorStop(1, "#0891b2");
      ctx!.fillStyle = coreGrad;
      ctx!.beginPath();
      ctx!.arc(cx, cy, 12 + corePulse * 3, 0, Math.PI * 2);
      ctx!.fill();
      ctx!.shadowBlur = 0;

      // Core label
      const sig = resultRef.current?.signal ?? "HOLD";
      const gc = sig === "BUY"
        ? "74,222,128"
        : sig === "SELL"
          ? "248,113,113"
          : "6,182,212";
      ctx!.fillStyle = `rgba(${gc},1)`;
      ctx!.font = "bold 10px 'Roboto Mono', monospace";
      ctx!.textAlign = "center";
      ctx!.textBaseline = "middle";
      ctx!.fillText(runningRef.current ? "···" : signalLabel(sig), cx, cy + 28);

      // ── LAYER 6: Module nodes
      moduleKeys.forEach((key, i) => {
        const pos  = nodePos[key];
        const ms   = s.moduleState[key];
        if (!pos || !ms) return;

        const sig    = resultRef.current?.modules?.[key]?.signal ?? "NEUTRAL";
        const isBuy  = sig === "BUY";
        const isSell = sig === "SELL";
        const isActive = isBuy || isSell;

        ms.pulsePhase = (ms.pulsePhase || 0) + 0.05;
        const nodePulse = (Math.sin(ms.pulsePhase) + 1) * 0.5;
        const baseSize  = 8;
        const intensity = Math.abs(ms.intensity);
        const size = baseSize + intensity * 4;

        // Orbital particles
        if (isActive && ms.orbitals) {
          ms.orbitals.forEach(orb => {
            orb.angle += orb.speed;
            const ox = pos.x + Math.cos(orb.angle) * (orb.radius + nodePulse * 3);
            const oy = pos.y + Math.sin(orb.angle) * (orb.radius + nodePulse * 3);
            ctx!.fillStyle = "rgba(6,182,212,0.6)";
            ctx!.beginPath();
            ctx!.arc(ox, oy, 2, 0, Math.PI * 2);
            ctx!.fill();
          });
        }

        // Outer ring
        ctx!.strokeStyle = `rgba(6,182,212,${0.2 + nodePulse * 0.1})`;
        ctx!.lineWidth = 1;
        ctx!.beginPath();
        ctx!.arc(pos.x, pos.y, size + 8 + nodePulse * 2, 0, Math.PI * 2);
        ctx!.stroke();

        // Glow
        const glowColor = isBuy ? "#4ade80" : isSell ? "#f87171" : "#06b6d4";
        ctx!.shadowBlur = 15 + nodePulse * 10;
        ctx!.shadowColor = glowColor;

        // Node gradient fill
        const ng = ctx!.createRadialGradient(
          pos.x - size * 0.3, pos.y - size * 0.3, 0,
          pos.x, pos.y, size
        );
        if (isBuy) {
          ng.addColorStop(0, "#ffffff");
          ng.addColorStop(0.5, "#4ade80");
          ng.addColorStop(1, "#16a34a");
        } else if (isSell) {
          ng.addColorStop(0, "#ffffff");
          ng.addColorStop(0.5, "#f87171");
          ng.addColorStop(1, "#dc2626");
        } else {
          ng.addColorStop(0, "#67e8f9");
          ng.addColorStop(0.5, "#0e7490");
          ng.addColorStop(1, "#164e63");
        }
        ctx!.fillStyle = ng;
        ctx!.beginPath();
        ctx!.arc(pos.x, pos.y, size, 0, Math.PI * 2);
        ctx!.fill();
        ctx!.shadowBlur = 0;

        // Inner highlight
        ctx!.fillStyle = "rgba(255,255,255,0.3)";
        ctx!.beginPath();
        ctx!.arc(pos.x - size * 0.25, pos.y - size * 0.25, size * 0.3, 0, Math.PI * 2);
        ctx!.fill();

        // Label pill
        const meta = MODULE_META[key];
        ctx!.font = "10px 'Roboto Mono', monospace";
        ctx!.textAlign = "center";
        const labelW = ctx!.measureText(meta.label).width + 8;
        ctx!.fillStyle = "rgba(0,0,0,0.6)";
        const ly = pos.y + size + 8;
        ctx!.fillRect(pos.x - labelW / 2, ly, labelW, 14);
        ctx!.fillStyle = "rgba(255,255,255,0.9)";
        ctx!.textBaseline = "top";
        ctx!.fillText(meta.label, pos.x, ly + 2);
      });

      // ── LAYER 7: Trail particles toward center
      s.particles = s.particles.filter(p => {
        p.progress += p.speed;
        p.trail.push({ x: p.x, y: p.y });
        if (p.trail.length > 10) p.trail.shift();

        p.x += (p.targetX - p.x) * p.speed * 3;
        p.y += (p.targetY - p.y) * p.speed * 3;

        p.trail.forEach((pt, idx) => {
          const alpha = (idx / p.trail.length) * 0.5;
          ctx!.fillStyle = `rgba(6,182,212,${alpha})`;
          ctx!.beginPath();
          ctx!.arc(pt.x, pt.y, p.size * (idx / p.trail.length), 0, Math.PI * 2);
          ctx!.fill();
        });

        ctx!.shadowBlur = 10;
        ctx!.shadowColor = p.color;
        ctx!.fillStyle = p.color;
        ctx!.beginPath();
        ctx!.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx!.fill();
        ctx!.shadowBlur = 0;

        return p.progress < 1;
      });

      // ── LAYER 8: Scanner sweep (running state)
      if (runningRef.current) {
        const sa = (time * 0.3) % (Math.PI * 2);
        ctx!.strokeStyle = "rgba(6,182,212,0.35)";
        ctx!.lineWidth = 1.5;
        ctx!.beginPath();
        ctx!.moveTo(cx, cy);
        ctx!.lineTo(
          cx + (ringRadius + 20) * Math.cos(sa),
          cy + (ringRadius + 20) * Math.sin(sa)
        );
        ctx!.stroke();

        // Sweep arc glow
        ctx!.strokeStyle = "rgba(6,182,212,0.08)";
        ctx!.lineWidth = ringRadius;
        ctx!.beginPath();
        ctx!.arc(cx, cy, ringRadius / 2, sa - 0.4, sa);
        ctx!.stroke();
      }

      animRef.current = requestAnimationFrame(draw);
    }

    animRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animRef.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: "100%",
        height: "100%",
        display: "block",
        filter: "drop-shadow(0 0 20px rgba(6,182,212,0.12))",
      }}
    />
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────────────
export default function Dashboard() {
  const router  = useRouter();
  const [symbol,   setSymbol]   = useState("XAUUSD");
  const [timeframe,setTimeframe]= useState("5m");
  const [category, setCategory] = useState("Metals");
  const [result,   setResult]   = useState<AnalysisResult | null>(null);
  const [running,  setRunning]  = useState(false);
  const [error,    setError]    = useState("");
  const [email,    setEmail]    = useState("");
  const [clock,    setClock]    = useState("");
  const [history,  setHistory]  = useState<SignalHistoryItem[]>([]);
  const [triggeredAlerts, setTriggeredAlerts] = useState<AlertItem[]>([]);
  const [livePrice,  setLivePrice]  = useState<number | null>(null);
  const [priceChange, setPriceChange] = useState<number | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);

  // Clock
  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString("en-GB", { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  // Live price polling — no auth required
  useEffect(() => {
    let cancelled = false;

    async function fetchPrice() {
      try {
        const res = await fetch(`${API}/api/market/price/${symbol}`);
        if (!res.ok) return;
        const data: { symbol: string; price: number | null; change_pct?: number; error?: string } = await res.json();
        if (cancelled || data.price == null) return;
        setLivePrice(data.price);
        setPriceChange(data.change_pct ?? null);
      } catch {
        // Silently keep last known price on any network error
      }
    }

    fetchPrice();
    const id = setInterval(fetchPrice, 5_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [symbol]);

  // Auth check
  useEffect(() => {
    import("@/lib/supabase").then(({ supabase }) => {
      supabase.auth.getSession().then(({ data: { session } }) => {
        if (!session && !getToken()) { router.replace("/login"); return; }
        setEmail(session?.user?.email || getStoredEmail() || "");
        getSignalHistory(10).then(setHistory).catch(() => {});
      });
    });
  }, [router]);

  const addFeed = useCallback((msg: string, cls: "buy"|"sell"|"neutral"|"info" = "info") => {
    if (!feedRef.current) return;
    const div = document.createElement("div");
    div.className = `feed-item ${cls}`;
    const time = new Date().toLocaleTimeString("en-GB", { hour12: false });
    div.innerHTML = `<span style="color:#475569;font-size:0.6rem">${time}</span><br/>${msg}`;
    feedRef.current.insertBefore(div, feedRef.current.firstChild);
    while (feedRef.current.children.length > 30) feedRef.current.removeChild(feedRef.current.lastChild!);
  }, []);

  async function runAnalysis() {
    setRunning(true); setError("");
    addFeed(`Analyzing ${symbol} / ${timeframe}...`, "info");
    try {
      const r = await analyze(symbol, timeframe);
      setResult(r);
      const cls = r.signal === "BUY" ? "buy"
                : r.signal === "SELL" ? "sell" : "neutral";
      addFeed(`<b style="color:${signalColor(r.signal)}">${symbol} → ${signalLabel(r.signal)}</b> · ${(r.confidence*100).toFixed(1)}% confidence`, cls);
      const mods = Object.entries(r.modules);
      const buy  = mods.filter(([,v]) => v.signal === "BUY").length;
      const sell = mods.filter(([,v]) => v.signal === "SELL").length;
      addFeed(`Modules: <b style="color:#4ade80">${buy} BUY</b> · <b style="color:#f87171">${sell} SELL</b> · ${mods.length-buy-sell} NEUTRAL`, "info");
      if (r.levels?.entry) {
        addFeed(`Entry <b>${r.levels.entry?.toFixed(2)}</b> → TP <b style="color:#4ade80">${r.levels.take_profit?.toFixed(2)}</b> | SL <b style="color:#f87171">${r.levels.stop_loss?.toFixed(2)}</b>`, cls);
      }
      getSignalHistory(10).then(setHistory).catch(() => {});
      checkAlerts({ symbol, timeframe, signal: r.signal, confidence: r.confidence })
        .then(({ triggered }) => { if (triggered.length) setTriggeredAlerts(triggered); })
        .catch(() => {});
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Analysis failed";
      setError(msg); addFeed(`ERROR: ${msg}`, "sell");
    } finally {
      setRunning(false);
    }
  }

  const modules = result?.modules ?? {};
  const levels  = result?.levels;
  const sig     = result?.signal ?? "HOLD";
  const sigCol  = signalColor(sig);
  const conf    = result ? (result.confidence * 100).toFixed(1) : "0";

  return (
    <>
      <style>{`
        body { background: #000 !important; }
        .bg-grid {
          background-size: 50px 50px;
          background-image:
            linear-gradient(to right, rgba(6,182,212,0.05) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(6,182,212,0.05) 1px, transparent 1px);
        }
        .feed-item {
          border-left: 3px solid #334155;
          padding: 6px 8px 6px 12px;
          margin-bottom: 6px;
          border-radius: 0 4px 4px 0;
          font-size: 0.7rem;
          line-height: 1.5;
          animation: slideIn 0.3s ease-out;
          background: linear-gradient(90deg, rgba(0,0,0,0.5), transparent);
          font-family: 'Roboto Mono', monospace;
          color: #94a3b8;
        }
        .feed-item.buy  { border-color: #4ade80; background: linear-gradient(90deg, rgba(74,222,128,0.1), transparent); }
        .feed-item.sell { border-color: #f87171; background: linear-gradient(90deg, rgba(248,113,113,0.1), transparent); }
        .feed-item.neutral { border-color: #64748b; }
        @keyframes slideIn {
          from { opacity:0; transform:translateX(20px); }
          to   { opacity:1; transform:translateX(0); }
        }
        .module-card {
          background: rgba(0,0,0,0.7);
          border: 1px solid rgba(22,78,99,0.5);
          border-radius: 6px;
          padding: 10px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          transition: all 0.3s ease;
          position: relative;
          overflow: hidden;
        }
        .module-card::before {
          content: '';
          position: absolute; top:0; left:-100%; width:100%; height:100%;
          background: linear-gradient(90deg, transparent, rgba(6,182,212,0.1), transparent);
          transition: left 0.5s ease;
        }
        .module-card:hover::before { left:100%; }
        .module-card:hover {
          border-color: #06b6d4;
          box-shadow: 0 0 20px rgba(6,182,212,0.3), inset 0 0 10px rgba(6,182,212,0.1);
          transform: translateY(-2px);
        }
        .module-card.active-buy  { border-color:#4ade80; background:rgba(74,222,128,0.08); box-shadow:inset 0 0 20px rgba(74,222,128,0.2), 0 0 10px rgba(74,222,128,0.15); }
        .module-card.active-sell { border-color:#f87171; background:rgba(248,113,113,0.08); box-shadow:inset 0 0 20px rgba(248,113,113,0.2), 0 0 10px rgba(248,113,113,0.15); }
        .module-card .mlabel { font-size:0.58rem; color:#67e8f9; letter-spacing:0.15em; margin-bottom:4px; font-family:'Roboto Mono',monospace; }
        .module-card .mvalue { font-size:0.82rem; font-weight:bold; }
        .no-scrollbar::-webkit-scrollbar { display:none; }
        .no-scrollbar { -ms-overflow-style:none; scrollbar-width:none; }
        .scan-overlay { position:relative; overflow:hidden; }
        .scan-overlay::after {
          content:''; position:absolute; top:-10%; left:0; width:100%; height:10px;
          background:linear-gradient(to bottom, transparent, rgba(6,182,212,0.08), transparent);
          animation:scan 4s linear infinite; pointer-events:none;
        }
        @keyframes scan { 0%{top:-10%} 100%{top:110%} }
        .glow-cyan { text-shadow:0 0 10px #06b6d4, 0 0 20px #06b6d4; }
        @media (max-width:900px) {
          .ieb-main { grid-template-columns: 1fr !important; }
          .ieb-left, .ieb-right { display:none; }
        }
      `}</style>

      {/* Background grid */}
      <div className="bg-grid" style={{ position:"fixed", inset:0, zIndex:0, opacity:0.2, pointerEvents:"none" }} />

      {/* Alert toasts */}
      {triggeredAlerts.length > 0 && (
        <div style={{ position:"fixed", top:72, right:16, zIndex:1000, display:"flex", flexDirection:"column", gap:8 }}>
          {triggeredAlerts.map(a => (
            <div key={a.id} style={{ background:"#000", border:"1px solid #4ade80", borderLeft:"3px solid #4ade80", borderRadius:8, padding:"10px 14px", minWidth:240, boxShadow:"0 0 20px rgba(74,222,128,0.2)", fontFamily:"'Roboto Mono',monospace" }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:4 }}>
                <span style={{ color:"#4ade80", fontSize:"0.6rem", fontWeight:700, letterSpacing:"0.1em" }}>◈ ALERT TRIGGERED</span>
                <button onClick={() => setTriggeredAlerts(p=>p.filter(x=>x.id!==a.id))} style={{ background:"none", border:"none", color:"#64748b", cursor:"pointer", fontSize:12 }}>✕</button>
              </div>
              <div style={{ color:"#e2e8f0", fontSize:"0.7rem", fontWeight:700 }}>{a.symbol} · {a.timeframe}</div>
              <div style={{ color:"#64748b", fontSize:"0.62rem", marginTop:2 }}>
                {a.condition==="signal_is_buy"?"Signal is BUY":a.condition==="signal_is_sell"?"Signal is SELL":a.condition==="any_signal"?"Signal detected":`Confidence ≥ ${((a.threshold??0)*100).toFixed(0)}%`}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── HEADER ── */}
      <header style={{
        position:"fixed", top:0, left:0, width:"100%", height:64, zIndex:50,
        display:"flex", alignItems:"center", justifyContent:"space-between",
        padding:"0 24px", boxSizing:"border-box",
        background:"rgba(0,0,0,0.85)", backdropFilter:"blur(10px)",
        borderBottom:"1px solid rgba(6,182,212,0.2)",
      }}>
        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          <div style={{ width:12, height:12, borderRadius:"50%", background:"#06b6d4", boxShadow:"0 0 10px #06b6d4, 0 0 20px #06b6d4", animation:"pulse 2s ease-in-out infinite" }} />
          <h1 style={{ color:"#e2e8f0", fontWeight:700, fontSize:"1.4rem", letterSpacing:"0.2em", margin:0, fontFamily:"'Rajdhani',sans-serif" }}>
            INSTITUTIONAL <span style={{ color:"#06b6d4" }}>EDGE</span> BRAIN
          </h1>
        </div>

        <div style={{ display:"flex", alignItems:"center", gap:16, fontFamily:"'Roboto Mono',monospace", fontSize:"0.72rem", color:"#67e8f9" }}>
          {/* Symbol selector */}
          <select value={symbol} onChange={e => setSymbol(e.target.value)} style={{ background:"#000", border:"1px solid rgba(22,78,99,0.8)", color:"#06b6d4", borderRadius:4, padding:"3px 8px", fontSize:"0.72rem", fontFamily:"inherit", cursor:"pointer", outline:"none" }}>
            {Object.entries(SYMBOLS).map(([group, syms]) => (
              <optgroup key={group} label={group}>
                {syms.map(s => <option key={s} value={s}>{s}</option>)}
              </optgroup>
            ))}
          </select>

          {/* Timeframe pills */}
          <div style={{ display:"flex", gap:4 }}>
            {TIMEFRAMES.map(tf => (
              <button key={tf} onClick={() => setTimeframe(tf)} style={{
                background: timeframe===tf ? "rgba(6,182,212,0.2)" : "transparent",
                border: `1px solid ${timeframe===tf ? "#06b6d4" : "rgba(22,78,99,0.6)"}`,
                color: timeframe===tf ? "#06b6d4" : "#475569",
                borderRadius:4, padding:"2px 8px", fontSize:"0.65rem",
                cursor:"pointer", fontFamily:"inherit", transition:"all 0.15s",
              }}>{tf}</button>
            ))}
          </div>

          <div style={{ display:"flex", alignItems:"center", gap:6, color:"#10b981", fontSize:"0.65rem" }}>
            <div style={{ width:6, height:6, borderRadius:"50%", background:"#10b981", animation:"pulse 2s ease-in-out infinite" }} />
            CONNECTED
          </div>
          <div style={{ color:"#475569" }}>{clock}</div>

          {/* Nav links */}
          <a href="/backtest" style={{ color:"#2563ff", fontSize:"0.65rem", textDecoration:"none", border:"1px solid rgba(37,99,255,0.3)", padding:"3px 10px", borderRadius:4 }}>BACKTEST</a>
          <a href="/alerts"   style={{ color:"#4ade80", fontSize:"0.65rem", textDecoration:"none", border:"1px solid rgba(74,222,128,0.25)", padding:"3px 10px", borderRadius:4, position:"relative" }}>
            ALERTS
            {triggeredAlerts.length>0 && <span style={{ position:"absolute", top:-3, right:-3, width:7, height:7, borderRadius:"50%", background:"#4ade80", boxShadow:"0 0 6px #4ade80" }} />}
          </a>
          <a href="/account"  style={{ color:"#64748b", fontSize:"0.65rem", textDecoration:"none", border:"1px solid rgba(100,116,139,0.3)", padding:"3px 10px", borderRadius:4 }}>ACCOUNT</a>
          {email && <span style={{ color:"#334155", fontSize:"0.62rem" }}>{email}</span>}
          <button onClick={() => { doLogout(); router.replace("/login"); }} style={{ background:"transparent", border:"1px solid rgba(100,116,139,0.3)", color:"#475569", fontSize:"0.65rem", padding:"3px 10px", borderRadius:4, cursor:"pointer", fontFamily:"inherit" }}>LOGOUT</button>
        </div>
      </header>

      {/* ── MAIN LAYOUT ── */}
      <main className="ieb-main" style={{
        position:"relative", zIndex:10,
        display:"grid",
        gridTemplateColumns:"300px 1fr 300px",
        gridTemplateRows:"1fr auto",
        paddingTop:64,
        height:"100vh",
        boxSizing:"border-box",
        gap:0,
      }}>

        {/* ── LEFT: Market Metrics ── */}
        <div className="ieb-left no-scrollbar scan-overlay" style={{
          background:"rgba(0,0,0,0.4)", borderRight:"1px solid rgba(6,182,212,0.15)",
          overflowY:"auto", padding:"16px", display:"flex", flexDirection:"column", gap:14,
        }}>
          <div style={{ color:"#67e8f9", fontSize:"0.65rem", letterSpacing:"0.15em", fontFamily:"'Roboto Mono',monospace" }}>MARKET METRICS</div>

          {/* Price display */}
          <div style={{ textAlign:"center" }}>
            <div style={{ color:"#475569", fontSize:"0.6rem", fontFamily:"'Roboto Mono',monospace", letterSpacing:"0.1em" }}>CURRENT PRICE</div>
            <div style={{ color:"#fff", fontSize:"2.8rem", fontWeight:700, letterSpacing:"-0.02em", lineHeight:1.1, fontFamily:"'Rajdhani',sans-serif", textShadow:"0 0 20px rgba(255,255,255,0.3)" }}>
              {(() => {
                const displayPrice = livePrice ?? levels?.price ?? null;
                if (displayPrice == null) return <span style={{ color:"#1e293b" }}>—</span>;
                return displayPrice.toFixed(displayPrice > 100 ? 2 : 4);
              })()}
            </div>
            <div style={{ display:"flex", alignItems:"center", justifyContent:"center", gap:8, marginTop:4 }}>
              <span style={{ color:"#06b6d4", fontSize:"0.7rem", fontFamily:"'Roboto Mono',monospace" }}>{symbol}</span>
              {priceChange != null && (
                <span style={{
                  fontSize:"0.65rem",
                  fontFamily:"'Roboto Mono',monospace",
                  color: priceChange >= 0 ? "#4ade80" : "#f87171",
                  fontWeight: 600,
                }}>
                  {priceChange >= 0 ? "+" : ""}{priceChange.toFixed(2)}%
                </span>
              )}
            </div>
          </div>

          {/* Signal confidence box */}
          <div style={{ border:"1px solid rgba(6,182,212,0.3)", background:"rgba(6,182,212,0.07)", borderRadius:6, padding:"14px", textAlign:"center" }}>
            <div style={{ color:"#67e8f9", fontSize:"0.62rem", letterSpacing:"0.1em", fontFamily:"'Roboto Mono',monospace", marginBottom:8 }}>SIGNAL CONFIDENCE</div>
            <div style={{ color:"#fff", fontSize:"2.2rem", fontWeight:700, fontFamily:"'Rajdhani',sans-serif", marginBottom:8, textShadow:`0 0 15px ${sigCol}` }}>
              {conf}%
            </div>
            <div style={{ height:4, background:"#1e293b", borderRadius:2, overflow:"hidden" }}>
              <div style={{ height:"100%", width:`${conf}%`, background:`linear-gradient(90deg,${sigCol}88,${sigCol})`, borderRadius:2, transition:"width 0.5s", boxShadow:`0 0 8px ${sigCol}` }} />
            </div>
          </div>

          {/* Controls: Category tabs */}
          <div>
            <div style={{ color:"#334155", fontSize:"0.58rem", fontFamily:"'Roboto Mono',monospace", letterSpacing:"0.1em", marginBottom:6 }}>MARKET</div>
            <div style={{ display:"flex", flexWrap:"wrap", gap:4 }}>
              {Object.keys(SYMBOLS).map(cat => (
                <button key={cat} onClick={() => { setCategory(cat); setSymbol(SYMBOLS[cat][0]); }} style={{
                  fontSize:"0.58rem", fontWeight:700, padding:"3px 7px", borderRadius:4, border:"1px solid", cursor:"pointer",
                  fontFamily:"'Roboto Mono',monospace",
                  borderColor: category===cat ? "#06b6d4" : "rgba(22,78,99,0.5)",
                  background:  category===cat ? "rgba(6,182,212,0.15)" : "transparent",
                  color:       category===cat ? "#06b6d4" : "#475569",
                }}>
                  {cat.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Symbol grid */}
          <div style={{ display:"flex", flexWrap:"wrap", gap:4 }}>
            {(SYMBOLS[category]||[]).map(s => (
              <button key={s} onClick={() => setSymbol(s)} style={{
                fontSize:"0.63rem", padding:"4px 8px", borderRadius:4, border:"1px solid", cursor:"pointer",
                fontFamily:"'Roboto Mono',monospace",
                borderColor: symbol===s ? "#06b6d4" : "rgba(22,78,99,0.4)",
                background:  symbol===s ? "rgba(6,182,212,0.15)" : "rgba(0,0,0,0.3)",
                color:       symbol===s ? "#06b6d4" : "#64748b",
              }}>{s}</button>
            ))}
          </div>

          {/* Analyze button */}
          <button onClick={runAnalysis} disabled={running} style={{
            background: running ? "rgba(6,182,212,0.08)" : "linear-gradient(135deg,#0e7490,#7c3aed)",
            color: running ? "#06b6d4" : "#fff",
            fontWeight:700, fontSize:"0.85rem", padding:"12px",
            borderRadius:8, border: running ? "1px solid rgba(6,182,212,0.3)" : "none",
            cursor: running ? "not-allowed" : "pointer",
            fontFamily:"'Rajdhani',sans-serif", letterSpacing:"0.15em",
            boxShadow: running ? "none" : "0 0 20px rgba(6,182,212,0.25)",
            display:"flex", alignItems:"center", justifyContent:"center", gap:8,
          }}>
            <span style={{ width:8, height:8, borderRadius:"50%", background: running ? "#06b6d4" : "#fff", display:"inline-block", animation:"pulse 1.5s ease-in-out infinite" }} />
            {running ? "ANALYZING..." : "ANALYZE BRAIN"}
          </button>

          {error && (
            <div style={{ color:"#f87171", fontSize:"0.68rem", padding:"8px 10px", background:"rgba(248,113,113,0.07)", borderRadius:6, border:"1px solid rgba(248,113,113,0.2)", fontFamily:"'Roboto Mono',monospace" }}>
              {error}
            </div>
          )}

          {/* ACT NOW — trade plan */}
          {result && (
            <div style={{ border:"1px solid rgba(6,182,212,0.25)", background:"rgba(6,182,212,0.05)", borderRadius:6, padding:12 }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:10 }}>
                <div style={{ color:"#eab308", fontSize:"0.58rem", letterSpacing:"0.15em", fontFamily:"'Roboto Mono',monospace" }}>ACT NOW</div>
                <div style={{ color:sigCol, fontSize:"1.4rem", fontWeight:900, fontFamily:"'Rajdhani',sans-serif", letterSpacing:"0.05em", textShadow:`0 0 15px ${sigCol}` }}>
                  {signalLabel(sig)}
                </div>
              </div>
              {levels?.entry && (
                <div style={{ fontFamily:"'Roboto Mono',monospace" }}>
                  {[
                    { label:"ENTRY",  val:levels.entry,       col:"#e2e8f0" },
                    { label:"STOP",   val:levels.stop_loss,   col:"#f87171" },
                    { label:"TARGET", val:levels.take_profit, col:"#4ade80" },
                  ].map(({ label, val, col }) => (
                    <div key={label} style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"5px 0", borderBottom:"1px solid rgba(255,255,255,0.04)" }}>
                      <span style={{ color:"#475569", fontSize:"0.6rem" }}>{label}</span>
                      <span style={{ color:col, fontSize:"0.85rem", fontWeight:700 }}>{val?.toFixed(val > 100 ? 2 : 4)}</span>
                    </div>
                  ))}
                  {levels.risk_reward && (
                    <div style={{ textAlign:"center", marginTop:8, color:"#06b6d4", fontSize:"0.7rem" }}>
                      R:R RATIO: <b>{levels.risk_reward}</b>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Brain Decision */}
          <div style={{ textAlign:"center", marginTop:4 }}>
            <div style={{ color:"#334155", fontSize:"0.6rem", fontFamily:"'Roboto Mono',monospace", letterSpacing:"0.1em", marginBottom:4 }}>BRAIN DECISION</div>
            <div style={{ color: result ? sigCol : "#1e293b", fontSize:"1.8rem", fontWeight:900, fontFamily:"'Rajdhani',sans-serif", letterSpacing:"0.15em", textShadow: result ? `0 0 15px ${sigCol}` : "none", animation: result ? "pulse 2s ease-in-out infinite" : "none" }}>
              {result ? signalLabel(sig) : "WAIT"}
            </div>
          </div>

          {/* Ensemble models */}
          {result?.ensemble?.models && Object.keys(result.ensemble.models).length > 0 && (
            <div style={{ borderTop:"1px solid rgba(6,182,212,0.1)", paddingTop:10 }}>
              <div style={{ color:"#334155", fontSize:"0.58rem", fontFamily:"'Roboto Mono',monospace", letterSpacing:"0.1em", marginBottom:6 }}>ENSEMBLE MODELS</div>
              {Object.entries(result.ensemble.models).map(([name, m]) => (
                <div key={name} style={{ display:"flex", justifyContent:"space-between", marginBottom:3, fontFamily:"'Roboto Mono',monospace" }}>
                  <span style={{ color:"#334155", fontSize:"0.6rem", textTransform:"uppercase" }}>{name}</span>
                  <span style={{ color:signalColor(m.signal), fontSize:"0.6rem", fontWeight:700 }}>{signalLabel(m.signal)} {(m.confidence*100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── CENTER: Neural Canvas ── */}
        <div style={{
          position:"relative",
          display:"flex", alignItems:"center", justifyContent:"center",
          background:"radial-gradient(circle at center, rgba(6,182,212,0.1) 0%, rgba(6,182,212,0.03) 40%, transparent 70%)",
          borderLeft:"1px solid rgba(6,182,212,0.08)",
          borderRight:"1px solid rgba(6,182,212,0.08)",
        }}>
          <NeuralCanvas result={result} running={running} />

          {/* Symbol overlay */}
          <div style={{ position:"absolute", top:16, left:"50%", transform:"translateX(-50%)", textAlign:"center", pointerEvents:"none" }}>
            <div style={{ color:"#06b6d4", fontSize:"0.75rem", fontWeight:700, letterSpacing:"0.2em", fontFamily:"'Roboto Mono',monospace", opacity:0.7 }}>{symbol} · {timeframe}</div>
          </div>

          {/* Gamma overlay placeholder */}
          {result && (
            <div style={{ position:"absolute", bottom:16, left:"50%", transform:"translateX(-50%)", display:"flex", gap:10, pointerEvents:"none" }}>
              {levels?.support && (
                <div style={{ background:"rgba(0,0,0,0.6)", border:"1px solid rgba(124,58,237,0.5)", borderRadius:4, padding:"3px 10px", fontFamily:"'Roboto Mono',monospace", fontSize:"0.62rem", color:"#a78bfa" }}>
                  SUP: <b style={{ color:"#fff" }}>{levels.support?.toFixed(levels.support > 100 ? 2 : 4)}</b>
                </div>
              )}
              {levels?.resistance && (
                <div style={{ background:"rgba(0,0,0,0.6)", border:"1px solid rgba(239,68,68,0.5)", borderRadius:4, padding:"3px 10px", fontFamily:"'Roboto Mono',monospace", fontSize:"0.62rem", color:"#f87171" }}>
                  RES: <b style={{ color:"#fff" }}>{levels.resistance?.toFixed(levels.resistance > 100 ? 2 : 4)}</b>
                </div>
              )}
            </div>
          )}

          {running && (
            <div style={{ position:"absolute", top:"50%", left:"50%", transform:"translate(-50%,-50%)", marginTop:60, pointerEvents:"none" }}>
              <div style={{ color:"#06b6d4", fontSize:"0.65rem", fontWeight:700, letterSpacing:"0.2em", fontFamily:"'Roboto Mono',monospace" }}>NEURAL PROCESSING...</div>
            </div>
          )}
        </div>

        {/* ── RIGHT: Module Analysis Feed ── */}
        <div className="ieb-right no-scrollbar" style={{
          background:"rgba(0,0,0,0.4)", borderLeft:"1px solid rgba(6,182,212,0.15)",
          display:"flex", flexDirection:"column",
        }}>
          <div style={{ padding:"12px 16px", borderBottom:"1px solid rgba(6,182,212,0.1)", display:"flex", alignItems:"center", gap:8, flexShrink:0 }}>
            <div style={{ width:6, height:6, borderRadius:"50%", background:"#4ade80", boxShadow:"0 0 8px #4ade80" }} />
            <span style={{ color:"#67e8f9", fontSize:"0.65rem", fontFamily:"'Roboto Mono',monospace", letterSpacing:"0.12em" }}>MODULE ANALYSIS FEED</span>
            {result && <span style={{ marginLeft:"auto", color:"#1e293b", fontSize:"0.58rem", fontFamily:"'Roboto Mono',monospace" }}>{result.latency_ms}ms</span>}
          </div>

          {/* Live feed */}
          <div ref={feedRef} className="no-scrollbar" style={{ flex:1, overflowY:"auto", padding:"10px 14px" }}>
            {!result && (
              <div style={{ color:"#1e293b", fontSize:"0.65rem", padding:"16px 0", fontFamily:"'Roboto Mono',monospace" }}>
                Waiting for feed...
              </div>
            )}
          </div>

          {/* Module results when analysis done */}
          {result && (
            <div className="no-scrollbar" style={{ borderTop:"1px solid rgba(6,182,212,0.08)", maxHeight:"50%", overflowY:"auto" }}>
              {Object.entries(MODULE_META).map(([key]) => {
                const m = modules[key];
                if (!m) return null;
                const col = signalColor(m.signal);
                const cls = signalClass(m.signal);
                return (
                  <div key={key} style={{
                    display:"flex", alignItems:"center", gap:10,
                    padding:"6px 14px", borderBottom:"1px solid rgba(255,255,255,0.02)",
                    background: cls==="buy" ? "rgba(74,222,128,0.04)" : cls==="sell" ? "rgba(248,113,113,0.04)" : "transparent",
                  }}>
                    <div style={{ width:6, height:6, borderRadius:"50%", background:col, boxShadow:`0 0 5px ${col}`, flexShrink:0 }} />
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ color:"#94a3b8", fontSize:"0.62rem", fontFamily:"'Roboto Mono',monospace", fontWeight:700 }}>{MODULE_META[key].label}</div>
                      {m.label && m.label !== m.signal && (
                        <div style={{ color:"#334155", fontSize:"0.57rem", fontFamily:"'Roboto Mono',monospace", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{m.label}</div>
                      )}
                    </div>
                    <span style={{ color:col, fontSize:"0.6rem", fontWeight:700, background:`${col}18`, border:`1px solid ${col}30`, borderRadius:3, padding:"1px 5px", flexShrink:0, fontFamily:"'Roboto Mono',monospace" }}>
                      {signalLabel(m.signal)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Recent signals history */}
          {history.length > 0 && !result && (
            <div className="no-scrollbar" style={{ borderTop:"1px solid rgba(6,182,212,0.08)", flex:1, overflowY:"auto", padding:"8px 0" }}>
              <div style={{ padding:"0 14px 6px", color:"#1e293b", fontSize:"0.57rem", fontFamily:"'Roboto Mono',monospace", letterSpacing:"0.1em" }}>RECENT SIGNALS</div>
              {history.map(h => {
                const col = signalColor(h.direction);
                return (
                  <div key={h.id} style={{ display:"flex", alignItems:"center", gap:8, padding:"5px 14px", borderBottom:"1px solid rgba(255,255,255,0.02)" }}>
                    <div style={{ width:5, height:5, borderRadius:"50%", background:col, flexShrink:0 }} />
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ color:"#475569", fontSize:"0.6rem", fontFamily:"'Roboto Mono',monospace", fontWeight:700 }}>{h.symbol} <span style={{ color:"#334155", fontWeight:400 }}>· {h.timeframe}</span></div>
                    </div>
                    <span style={{ color:col, fontSize:"0.58rem", fontWeight:700, fontFamily:"'Roboto Mono',monospace" }}>{h.direction}</span>
                    <span style={{ color:"#1e293b", fontSize:"0.55rem", fontFamily:"'Roboto Mono',monospace" }}>{h.confidence != null ? `${(h.confidence*100).toFixed(0)}%` : ""}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ── BOTTOM: Module Cards (spans full width) ── */}
        <div style={{
          gridColumn:"1 / -1",
          borderTop:"1px solid rgba(6,182,212,0.1)",
          overflowX:"auto", overflowY:"hidden",
          padding:"10px 16px",
          background:"rgba(0,0,0,0.5)",
        }}>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(12, minmax(100px, 1fr))", gap:8, height:120 }}>
            {Object.entries(MODULE_META).map(([key, meta]) => {
              const m = modules[key];
              const sig = m?.signal ?? "NEUTRAL";
              const col = signalColor(sig);
              const isBuy  = sig === "BUY";
              const isSell = sig === "SELL";
              const activeClass = isBuy ? "active-buy" : isSell ? "active-sell" : "";
              return (
                <div key={key} className={`module-card ${activeClass}`}>
                  <div className="mlabel">{meta.label}</div>
                  <div className="mvalue" style={{ color: col, textShadow: m ? `0 0 8px ${col}` : "none" }}>
                    {m ? signalLabel(sig) : "—"}
                  </div>
                  {m?.label && m.label !== sig && (
                    <div style={{ fontSize:"0.52rem", color:"#334155", fontFamily:"'Roboto Mono',monospace", marginTop:2, textAlign:"center" }}>{m.label.slice(0,16)}</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </main>
    </>
  );
}
