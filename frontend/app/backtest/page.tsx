"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import Link from "next/link";
import { analyze, type AnalysisResult } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────────
type Bar  = { time: number; open: number; high: number; low: number; close: number; volume: number };
type TF   = "5m" | "15m" | "1h" | "4h" | "1d" | "1w";
type Tool = "none" | "trendline" | "hline" | "vline" | "buy" | "sell" | "fib" | "rect";

interface HLine  { id: string; price: number }
interface VLine  { id: string; time: number }
interface TLine  { id: string; p1: { time: number; value: number }; p2: { time: number; value: number } }
interface Rect   { id: string; t1: number; p1: number; t2: number; p2: number }
interface FibLevel { id: string; p1: { time: number; value: number }; p2: { time: number; value: number } }
interface Marker { time: number; type: "buy" | "sell"; source?: "ieb" | "manual" }

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SYMBOLS: Record<string, string[]> = {
  "FX":      ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURGBP","EURJPY","GBPJPY"],
  "Metals":  ["XAUUSD","XAGUSD"],
  "Energy":  ["USOIL","UKOIL","NATGAS"],
  "Crypto":  ["BTCUSD","ETHUSD"],
  "Indices": ["SPX500","NAS100","GER40","UK100","JPN225"],
  "Stocks":  ["AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META"],
};

const TIMEFRAMES: { label: string; value: TF }[] = [
  { label: "5m", value: "5m" }, { label: "15m", value: "15m" },
  { label: "1h", value: "1h" }, { label: "4h",  value: "4h"  },
  { label: "1D", value: "1d" }, { label: "1W",  value: "1w"  },
];

const TOOL_INFO: Record<Tool, string> = {
  none:      "Click a tool to start drawing",
  trendline: "Click first point → click second point",
  hline:     "Click any bar to draw a horizontal level",
  vline:     "Click any bar to draw a vertical line",
  buy:       "Click a bar to place a Buy marker",
  sell:      "Click a bar to place a Sell marker",
  fib:       "Click swing high → click swing low for Fibonacci",
  rect:      "Click first corner → click second corner for zone",
};

// Fibonacci ratios
const FIB_RATIOS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
const FIB_COLORS = ["#f59e0b","#00c896","#2563ff","#e2e8f0","#2563ff","#00c896","#f59e0b"];

const C = {
  bg: "#06060f", surface: "#0d0d1a", border: "#1a1a2e",
  accent: "#2563ff", green: "#00c896", red: "#ff4466",
  gold: "#f59e0b", text: "#e2e8f0", muted: "#64748b",
  cyan: "#00d4ff",
};

function signalColor(s: string) {
  if (s === "BUY")  return C.green;
  if (s === "SELL") return C.red;
  return C.muted;
}

// ── Main component ──────────────────────────────────────────────────────────────
export default function BacktestPage() {
  const chartRef  = useRef<HTMLDivElement>(null);
  const chartInst = useRef<any>(null);
  const candleSer = useRef<any>(null);
  const volSer    = useRef<any>(null);
  const lineRefs  = useRef<Map<string, any>>(new Map());
  const lastBarsRef = useRef<Bar[]>([]);

  const [symbol,    setSymbol]    = useState("EURUSD");
  const [timeframe, setTimeframe] = useState<TF>("1d");
  const [years,     setYears]     = useState(2);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState("");
  const [bars,      setBars]      = useState(0);
  const [ohlcv,     setOhlcv]     = useState<{ o: number; h: number; l: number; c: number; t: string } | null>(null);

  // Drawing state
  const [tool,      setTool]      = useState<Tool>("none");
  const [hlines,    setHlines]    = useState<HLine[]>([]);
  const [vlines,    setVlines]    = useState<VLine[]>([]);
  const [tlines,    setTlines]    = useState<TLine[]>([]);
  const [fibs,      setFibs]      = useState<FibLevel[]>([]);
  const [rects,     setRects]     = useState<Rect[]>([]);
  const [markers,   setMarkers]   = useState<Marker[]>([]);
  const pendingPoint = useRef<{ time: number; value: number } | null>(null);
  const pendingRect  = useRef<{ time: number; value: number } | null>(null);

  // IEB analysis
  const [iebRunning, setIebRunning] = useState(false);
  const [iebResult,  setIebResult]  = useState<AnalysisResult | null>(null);
  const [iebError,   setIebError]   = useState("");

  // ── Fetch OHLCV ───────────────────────────────────────────────────────────────
  const loadData = useCallback(async (sym: string, tf: TF, yr: number) => {
    setLoading(true);
    setError("");
    setIebResult(null);
    setIebError("");
    try {
      const res  = await fetch(`${API}/api/backtest/ohlcv?symbol=${sym}&timeframe=${tf}&years=${yr}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || "Fetch failed");

      const data: Bar[] = json.data;
      lastBarsRef.current = data;
      setBars(data.length);

      if (!chartInst.current || !candleSer.current) return;

      const candles = data.map(b => ({ time: b.time as any, open: b.open, high: b.high, low: b.low, close: b.close }));
      const volumes = data.map(b => ({
        time: b.time as any, value: b.volume,
        color: b.close >= b.open ? "rgba(0,200,150,0.35)" : "rgba(255,68,102,0.35)",
      }));

      candleSer.current.setData(candles);
      volSer.current.setData(volumes);
      chartInst.current.timeScale().fitContent();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Mount chart ────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!chartRef.current) return;

    import("lightweight-charts").then(({ createChart, CrosshairMode }) => {
      const chart = createChart(chartRef.current!, {
        layout:    { background: { color: C.bg }, textColor: C.text },
        grid:      { vertLines: { color: C.border }, horzLines: { color: C.border } },
        crosshair: { mode: CrosshairMode.Normal },
        rightPriceScale: { borderColor: C.border },
        timeScale: { borderColor: C.border, timeVisible: true, secondsVisible: false },
        width:  chartRef.current!.clientWidth,
        height: chartRef.current!.clientHeight || 520,
      });

      const cSeries = chart.addCandlestickSeries({
        upColor: C.green, downColor: C.red,
        borderUpColor: C.green, borderDownColor: C.red,
        wickUpColor: C.green, wickDownColor: C.red,
      });

      const vSeries = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol" });
      chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

      chart.subscribeCrosshairMove((param: any) => {
        if (!param.time || !param.seriesData) return;
        const d = param.seriesData.get(cSeries);
        if (!d) return;
        const date = new Date(param.time * 1000);
        setOhlcv({ t: date.toISOString().replace("T", " ").slice(0, 16), o: d.open, h: d.high, l: d.low, c: d.close });
      });

      chart.subscribeClick((param: any) => {
        if (!param.point || !param.time) return;
        const price = cSeries.coordinateToPrice(param.point.y);
        const time  = param.time as number;
        if (price == null) return;
        handleChartClick(time, price);
      });

      chartInst.current = chart;
      candleSer.current = cSeries;
      volSer.current    = vSeries;

      const ro = new ResizeObserver(() => {
        chart.applyOptions({ width: chartRef.current!.clientWidth, height: chartRef.current!.clientHeight });
      });
      ro.observe(chartRef.current!);

      loadData("EURUSD", "1d", 2);

      return () => { ro.disconnect(); chart.remove(); };
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Chart click handler ────────────────────────────────────────────────────────
  const handleChartClick = useCallback((time: number, price: number) => {
    const currentTool = (document.getElementById("activeTool") as HTMLInputElement)?.value as Tool;

    if (currentTool === "hline") {
      addHLine(price);
    } else if (currentTool === "vline") {
      addVLine(time);
    } else if (currentTool === "trendline") {
      const pending = pendingPoint.current;
      if (!pending) {
        pendingPoint.current = { time, value: price };
      } else {
        addTLine(pending, { time, value: price });
        pendingPoint.current = null;
      }
    } else if (currentTool === "fib") {
      const pending = pendingPoint.current;
      if (!pending) {
        pendingPoint.current = { time, value: price };
      } else {
        addFib(pending, { time, value: price });
        pendingPoint.current = null;
      }
    } else if (currentTool === "rect") {
      const pending = pendingRect.current;
      if (!pending) {
        pendingRect.current = { time, value: price };
      } else {
        addRect(pendingRect.current, { time, value: price });
        pendingRect.current = null;
      }
    } else if (currentTool === "buy") {
      addMarker(time, "buy", "manual");
    } else if (currentTool === "sell") {
      addMarker(time, "sell", "manual");
    }
  }, []);

  // ── Drawing helpers ────────────────────────────────────────────────────────────
  const addHLine = (price: number) => {
    if (!candleSer.current) return;
    const id = `hl-${Date.now()}`;
    const pl = candleSer.current.createPriceLine({
      price, color: C.accent, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "Level",
    });
    lineRefs.current.set(id, pl);
    setHlines(prev => [...prev, { id, price }]);
  };

  const addVLine = (time: number) => {
    if (!chartInst.current) return;
    const id = `vl-${Date.now()}`;
    const series = chartInst.current.addLineSeries({
      color: C.gold + "88", lineWidth: 1, lastValueVisible: false, priceLineVisible: false,
    });
    // Use a very high and low price to simulate a vertical line
    series.setData([
      { time: time as any, value: 1e8 },
    ]);
    // Actually lightweight-charts doesn't natively support vertical lines
    // We'll simulate via a thin line series with just one visible point + label
    lineRefs.current.set(id, series);
    setVlines(prev => [...prev, { id, time }]);
  };

  const addTLine = (p1: { time: number; value: number }, p2: { time: number; value: number }) => {
    if (!chartInst.current) return;
    const id = `tl-${Date.now()}`;
    const series = chartInst.current.addLineSeries({
      color: C.gold, lineWidth: 1, lastValueVisible: false, priceLineVisible: false,
    });
    series.setData([
      { time: Math.min(p1.time, p2.time) as any, value: p1.time <= p2.time ? p1.value : p2.value },
      { time: Math.max(p1.time, p2.time) as any, value: p1.time <= p2.time ? p2.value : p1.value },
    ]);
    lineRefs.current.set(id, series);
    setTlines(prev => [...prev, { id, p1, p2 }]);
  };

  const addFib = (p1: { time: number; value: number }, p2: { time: number; value: number }) => {
    if (!candleSer.current) return;
    const id = `fib-${Date.now()}`;
    const high  = Math.max(p1.value, p2.value);
    const low   = Math.min(p1.value, p2.value);
    const range = high - low;
    const fibLines: any[] = [];
    FIB_RATIOS.forEach((ratio, i) => {
      const price = high - range * ratio;
      const pl = candleSer.current.createPriceLine({
        price,
        color: FIB_COLORS[i],
        lineWidth: 1,
        lineStyle: 1, // dotted
        axisLabelVisible: true,
        title: `Fib ${(ratio * 100).toFixed(1)}%`,
      });
      fibLines.push(pl);
    });
    lineRefs.current.set(id, fibLines);
    setFibs(prev => [...prev, { id, p1, p2 }]);
  };

  const addRect = (
    p1: { time: number; value: number },
    p2: { time: number; value: number },
  ) => {
    if (!candleSer.current) return;
    const id   = `rect-${Date.now()}`;
    const high = Math.max(p1.value, p2.value);
    const low  = Math.min(p1.value, p2.value);
    // Draw top and bottom price lines for the zone
    const top = candleSer.current.createPriceLine({
      price: high, color: "#7c3aed88", lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: "Zone",
    });
    const bot = candleSer.current.createPriceLine({
      price: low, color: "#7c3aed88", lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: "",
    });
    lineRefs.current.set(id, [top, bot]);
    setRects(prev => [...prev, { id, t1: p1.time, p1: p1.value, t2: p2.time, p2: p2.value }]);
  };

  const addMarker = (time: number, type: "buy" | "sell", source: "ieb" | "manual" = "manual") => {
    setMarkers(prev => {
      const next = [...prev, { time, type, source }];
      applyMarkers(next);
      return next;
    });
  };

  const applyMarkers = (all: Marker[]) => {
    if (!candleSer.current) return;
    const sorted = [...all].sort((a, b) => a.time - b.time);
    candleSer.current.setMarkers(sorted.map(m => ({
      time:     m.time as any,
      position: m.type === "buy" ? "belowBar" : "aboveBar",
      color:    m.source === "ieb"
        ? (m.type === "buy" ? C.cyan : "#f72585")
        : (m.type === "buy" ? C.green : C.red),
      shape:    m.type === "buy" ? "arrowUp" : "arrowDown",
      text:     m.source === "ieb"
        ? (m.type === "buy" ? "IEB BUY" : "IEB SELL")
        : (m.type === "buy" ? "BUY" : "SELL"),
    })));
  };

  const clearAll = () => {
    tlines.forEach(tl => {
      const s = lineRefs.current.get(tl.id);
      if (s && chartInst.current) try { chartInst.current.removeSeries(s); } catch {}
      lineRefs.current.delete(tl.id);
    });
    vlines.forEach(vl => {
      const s = lineRefs.current.get(vl.id);
      if (s && chartInst.current) try { chartInst.current.removeSeries(s); } catch {}
      lineRefs.current.delete(vl.id);
    });
    hlines.forEach(hl => {
      const pl = lineRefs.current.get(hl.id);
      if (pl && candleSer.current) try { candleSer.current.removePriceLine(pl); } catch {}
      lineRefs.current.delete(hl.id);
    });
    fibs.forEach(f => {
      const pls = lineRefs.current.get(f.id) as any[];
      if (pls && candleSer.current) pls.forEach(pl => { try { candleSer.current.removePriceLine(pl); } catch {} });
      lineRefs.current.delete(f.id);
    });
    rects.forEach(r => {
      const pls = lineRefs.current.get(r.id) as any[];
      if (pls && candleSer.current) pls.forEach(pl => { try { candleSer.current.removePriceLine(pl); } catch {} });
      lineRefs.current.delete(r.id);
    });
    setHlines([]); setVlines([]); setTlines([]); setFibs([]); setRects([]);
    setMarkers([]);
    pendingPoint.current = null;
    pendingRect.current  = null;
    if (candleSer.current) candleSer.current.setMarkers([]);
  };

  const handleLoad = () => { clearAll(); loadData(symbol, timeframe, years); };

  const selectTool = (t: Tool) => {
    setTool(t);
    pendingPoint.current = null;
    pendingRect.current  = null;
    const el = document.getElementById("activeTool") as HTMLInputElement;
    if (el) el.value = t;
  };

  // ── IEB Brain Analysis ────────────────────────────────────────────────────────
  const runIebAnalysis = async () => {
    setIebRunning(true);
    setIebError("");
    setIebResult(null);
    try {
      // Map backtest TF to analyze TF (1w not supported → fallback 1d)
      const tf = timeframe === "1w" ? "1d" : timeframe;
      const result = await analyze(symbol, tf);
      setIebResult(result);

      // Plot signal on the last bar
      const bars = lastBarsRef.current;
      if (bars.length > 0 && (result.signal === "BUY" || result.signal === "SELL")) {
        const lastBar = bars[bars.length - 1];
        setMarkers(prev => {
          // Remove previous IEB markers
          const withoutIeb = prev.filter(m => m.source !== "ieb");
          const next = [...withoutIeb, {
            time: lastBar.time,
            type: result.signal === "BUY" ? "buy" as const : "sell" as const,
            source: "ieb" as const,
          }];
          applyMarkers(next);
          return next;
        });
        // Jump to end of chart
        if (chartInst.current) chartInst.current.timeScale().scrollToRealTime();
      }
    } catch (e: unknown) {
      setIebError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setIebRunning(false);
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "'JetBrains Mono', monospace", display: "flex", flexDirection: "column" }}>
      <input id="activeTool" type="hidden" defaultValue="none" />

      {/* ── Nav ── */}
      <nav style={{ background: C.surface, borderBottom: `1px solid ${C.border}`, padding: "0 20px", display: "flex", alignItems: "center", gap: 20, height: 48, flexShrink: 0 }}>
        <span style={{ color: C.cyan, fontWeight: 700, fontSize: 14, letterSpacing: 1 }}>IEB</span>
        <Link href="/dashboard" style={{ color: C.muted, textDecoration: "none", fontSize: 12 }}>Dashboard</Link>
        <span style={{ color: C.text, fontSize: 12, borderBottom: `2px solid ${C.accent}`, paddingBottom: 2 }}>Backtest</span>
        <div style={{ flex: 1 }} />
        <Link href="/account" style={{ color: C.muted, textDecoration: "none", fontSize: 12 }}>Account</Link>
      </nav>

      {/* ── Controls bar ── */}
      <div style={{ background: C.surface, borderBottom: `1px solid ${C.border}`, padding: "8px 20px", display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", flexShrink: 0 }}>
        {/* Symbol */}
        <select value={symbol} onChange={e => setSymbol(e.target.value)} style={selectStyle}>
          {Object.entries(SYMBOLS).map(([group, syms]) => (
            <optgroup key={group} label={group}>
              {syms.map(s => <option key={s} value={s}>{s}</option>)}
            </optgroup>
          ))}
        </select>

        {/* Timeframes */}
        <div style={{ display: "flex", gap: 3 }}>
          {TIMEFRAMES.map(tf => (
            <button key={tf.value} onClick={() => setTimeframe(tf.value)} style={{
              ...pillStyle,
              background: timeframe === tf.value ? C.accent : "transparent",
              color:      timeframe === tf.value ? "#fff" : C.muted,
              border:     `1px solid ${timeframe === tf.value ? C.accent : C.border}`,
            }}>{tf.label}</button>
          ))}
        </div>

        {/* History years */}
        <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: C.muted }}>
          <span>History:</span>
          {[1, 2, 3, 5].map(y => (
            <button key={y} onClick={() => setYears(y)} style={{
              ...pillStyle,
              background: years === y ? C.gold + "33" : "transparent",
              color:      years === y ? C.gold : C.muted,
              border:     `1px solid ${years === y ? C.gold : C.border}`,
            }}>{y}Y</button>
          ))}
        </div>

        <button onClick={handleLoad} disabled={loading} style={{ ...btnStyle, background: C.accent, color: "#fff", opacity: loading ? 0.6 : 1 }}>
          {loading ? "Loading…" : "Load"}
        </button>

        {bars > 0 && <span style={{ fontSize: 11, color: C.muted }}>{bars.toLocaleString()} bars</span>}

        {/* Divider */}
        <div style={{ width: 1, height: 20, background: C.border, margin: "0 4px" }} />

        {/* IEB Analysis button */}
        <button
          onClick={runIebAnalysis}
          disabled={iebRunning || bars === 0}
          style={{
            ...btnStyle,
            background: iebRunning ? "rgba(0,212,255,0.08)" : "linear-gradient(135deg, #00d4ff, #7c3aed)",
            color: iebRunning ? C.cyan : "#fff",
            border: iebRunning ? `1px solid ${C.cyan}44` : "none",
            opacity: bars === 0 ? 0.4 : 1,
            letterSpacing: "0.06em",
            fontWeight: 700,
          }}
        >
          {iebRunning ? "◉ ANALYZING..." : "◈ IEB BRAIN"}
        </button>

        {error    && <span style={{ fontSize: 11, color: C.red }}>{error}</span>}
        {iebError && <span style={{ fontSize: 11, color: C.red }}>{iebError}</span>}
      </div>

      {/* ── Main content ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* ── Left: Drawing toolbar ── */}
        <div style={{ width: 56, background: C.surface, borderRight: `1px solid ${C.border}`, display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 12, gap: 5 }}>
          {([
            { t: "trendline" as Tool, icon: "╱",  label: "Trend Line"    },
            { t: "hline"     as Tool, icon: "─",  label: "H-Line"        },
            { t: "vline"     as Tool, icon: "│",  label: "V-Line"        },
            { t: "fib"       as Tool, icon: "Φ",  label: "Fibonacci"     },
            { t: "rect"      as Tool, icon: "▭",  label: "Zone / Rect"   },
            { t: "buy"       as Tool, icon: "↑",  label: "Buy Marker"    },
            { t: "sell"      as Tool, icon: "↓",  label: "Sell Marker"   },
          ]).map(({ t, icon, label }) => (
            <button key={t} title={label} onClick={() => selectTool(tool === t ? "none" : t)} style={{
              width: 40, height: 40,
              background: tool === t ? C.accent + "33" : "transparent",
              border:     `1px solid ${tool === t ? C.accent : C.border}`,
              borderRadius: 6,
              color:  tool === t ? C.accent : C.muted,
              cursor: "pointer", fontSize: 16,
              display: "flex", alignItems: "center", justifyContent: "center",
              transition: "all 0.15s",
            }}>{icon}</button>
          ))}
          <div style={{ flex: 1 }} />
          <button title="Clear all" onClick={clearAll} style={{
            width: 40, height: 40, background: "transparent",
            border: `1px solid ${C.border}`, borderRadius: 6,
            color: C.red, cursor: "pointer", fontSize: 14,
            display: "flex", alignItems: "center", justifyContent: "center",
            marginBottom: 12,
          }}>✕</button>
        </div>

        {/* ── Centre: Chart ── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>

          {/* OHLCV tooltip */}
          <div style={{ padding: "5px 14px", fontSize: 11, color: C.muted, background: C.bg, borderBottom: `1px solid ${C.border}`, display: "flex", gap: 14, alignItems: "center", minHeight: 28, flexShrink: 0 }}>
            {ohlcv ? (
              <>
                <span style={{ color: C.text, fontWeight: 700 }}>{symbol}</span>
                <span style={{ color: C.muted }}>{ohlcv.t}</span>
                <span>O <b style={{ color: C.text }}>{ohlcv.o}</b></span>
                <span>H <b style={{ color: C.green }}>{ohlcv.h}</b></span>
                <span>L <b style={{ color: C.red }}>{ohlcv.l}</b></span>
                <span>C <b style={{ color: ohlcv.c >= ohlcv.o ? C.green : C.red }}>{ohlcv.c}</b></span>
              </>
            ) : (
              <span>Hover chart to see OHLCV</span>
            )}
          </div>

          {/* Chart canvas */}
          <div ref={chartRef} style={{ flex: 1, cursor: tool !== "none" ? "crosshair" : "default" }} />

          {/* Status bar */}
          <div style={{ padding: "5px 14px", fontSize: 11, color: C.muted, background: C.surface, borderTop: `1px solid ${C.border}`, display: "flex", gap: 14, alignItems: "center", flexShrink: 0 }}>
            <span style={{ color: tool !== "none" ? C.accent : C.muted }}>
              {tool !== "none" ? `● ${TOOL_INFO[tool]}` : TOOL_INFO["none"]}
            </span>
            {(pendingPoint.current || pendingRect.current) && (
              <span style={{ color: C.gold }}>● First point set — click second point</span>
            )}
            <div style={{ flex: 1 }} />
            <span>{hlines.length + vlines.length} Lines</span>
            <span>{tlines.length} Trends</span>
            <span>{fibs.length} Fib</span>
            <span>{rects.length} Zones</span>
            <span>{markers.filter(m => m.source !== "ieb").length} Manual · {markers.filter(m => m.source === "ieb").length} IEB</span>
          </div>
        </div>

        {/* ── Right: Drawings + IEB result panel ── */}
        <div style={{ width: 220, background: C.surface, borderLeft: `1px solid ${C.border}`, overflowY: "auto", display: "flex", flexDirection: "column" }}>

          {/* IEB result card */}
          {iebResult && (
            <div style={{ padding: 12, borderBottom: `1px solid ${C.border}`, flexShrink: 0 }}>
              <div style={{ fontSize: 10, color: C.muted, letterSpacing: 1, marginBottom: 8 }}>IEB BRAIN SIGNAL</div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ color: signalColor(iebResult.signal), fontSize: 16, fontWeight: 900 }}>{iebResult.signal}</span>
                <span style={{ color: signalColor(iebResult.signal), fontSize: 11 }}>{(iebResult.confidence * 100).toFixed(1)}%</span>
              </div>
              {/* Confidence bar */}
              <div style={{ height: 3, background: "rgba(255,255,255,0.06)", borderRadius: 2, marginBottom: 8, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${iebResult.confidence * 100}%`, background: signalColor(iebResult.signal), borderRadius: 2 }} />
              </div>
              {/* Levels */}
              {iebResult.levels?.entry && (
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 4 }}>
                  {[
                    { label: "PRICE",  val: iebResult.levels.price,       col: C.text  },
                    { label: "ENTRY",  val: iebResult.levels.entry,       col: C.text  },
                    { label: "STOP",   val: iebResult.levels.stop_loss,   col: C.red   },
                    { label: "TARGET", val: iebResult.levels.take_profit, col: C.green },
                  ].map(({ label, val, col }) => (
                    <div key={label} style={{ background: C.bg, borderRadius: 4, padding: "5px 7px" }}>
                      <div style={{ color: C.muted, fontSize: 9, marginBottom: 2 }}>{label}</div>
                      <div style={{ color: col, fontSize: 11, fontWeight: 700 }}>
                        {val?.toFixed(val > 100 ? 2 : 4)}
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {iebResult.levels?.risk_reward && (
                <div style={{ marginTop: 6, textAlign: "center", color: C.cyan, fontSize: 11 }}>
                  R:R 1:{iebResult.levels.risk_reward}
                </div>
              )}
              {/* Module summary */}
              <div style={{ marginTop: 8, borderTop: `1px solid ${C.border}`, paddingTop: 6 }}>
                <div style={{ fontSize: 9, color: C.muted, marginBottom: 4 }}>MODULES</div>
                {Object.entries(iebResult.modules).slice(0, 6).map(([key, m]) => (
                  <div key={key} style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                    <span style={{ color: C.muted, fontSize: 10, textTransform: "uppercase" }}>{key.replace("_", " ")}</span>
                    <span style={{ color: signalColor(m.signal), fontSize: 10, fontWeight: 700 }}>{m.signal}</span>
                  </div>
                ))}
                {Object.keys(iebResult.modules).length > 6 && (
                  <div style={{ color: C.muted, fontSize: 9, marginTop: 2 }}>+{Object.keys(iebResult.modules).length - 6} more modules</div>
                )}
              </div>
            </div>
          )}

          {/* Drawings list */}
          <div style={{ padding: "10px 0", flex: 1 }}>
            <div style={{ padding: "0 12px 6px", fontSize: 10, color: C.muted, fontWeight: 700, letterSpacing: 1 }}>DRAWINGS</div>

            {hlines.length === 0 && vlines.length === 0 && tlines.length === 0 && fibs.length === 0 && rects.length === 0 && markers.filter(m => m.source !== "ieb").length === 0 && (
              <div style={{ padding: "6px 12px", fontSize: 11, color: C.muted }}>No drawings yet</div>
            )}

            {hlines.map(hl => (
              <DrawRow key={hl.id} icon="─" iconColor={C.accent} label={`${hl.price.toFixed(4)}`} onRemove={() => {
                const pl = lineRefs.current.get(hl.id);
                if (pl && candleSer.current) try { candleSer.current.removePriceLine(pl); } catch {}
                lineRefs.current.delete(hl.id);
                setHlines(p => p.filter(x => x.id !== hl.id));
              }} />
            ))}

            {vlines.map(vl => (
              <DrawRow key={vl.id} icon="│" iconColor={C.gold} label={new Date(vl.time * 1000).toLocaleDateString()} onRemove={() => {
                const s = lineRefs.current.get(vl.id);
                if (s && chartInst.current) try { chartInst.current.removeSeries(s); } catch {}
                lineRefs.current.delete(vl.id);
                setVlines(p => p.filter(x => x.id !== vl.id));
              }} />
            ))}

            {tlines.map(tl => (
              <DrawRow key={tl.id} icon="╱" iconColor={C.gold} label="Trend line" onRemove={() => {
                const s = lineRefs.current.get(tl.id);
                if (s && chartInst.current) try { chartInst.current.removeSeries(s); } catch {}
                lineRefs.current.delete(tl.id);
                setTlines(p => p.filter(x => x.id !== tl.id));
              }} />
            ))}

            {fibs.map(f => (
              <DrawRow key={f.id} icon="Φ" iconColor={C.gold} label={`Fib ${Math.max(f.p1.value, f.p2.value).toFixed(2)}→${Math.min(f.p1.value, f.p2.value).toFixed(2)}`} onRemove={() => {
                const pls = lineRefs.current.get(f.id) as any[];
                if (pls && candleSer.current) pls.forEach(pl => { try { candleSer.current.removePriceLine(pl); } catch {} });
                lineRefs.current.delete(f.id);
                setFibs(p => p.filter(x => x.id !== f.id));
              }} />
            ))}

            {rects.map(r => (
              <DrawRow key={r.id} icon="▭" iconColor="#7c3aed" label={`Zone ${Math.max(r.p1, r.p2).toFixed(2)}→${Math.min(r.p1, r.p2).toFixed(2)}`} onRemove={() => {
                const pls = lineRefs.current.get(r.id) as any[];
                if (pls && candleSer.current) pls.forEach(pl => { try { candleSer.current.removePriceLine(pl); } catch {} });
                lineRefs.current.delete(r.id);
                setRects(p => p.filter(x => x.id !== r.id));
              }} />
            ))}

            {markers.filter(m => m.source !== "ieb").map((m, i) => (
              <DrawRow key={`${m.time}-${i}`}
                icon={m.type === "buy" ? "↑" : "↓"}
                iconColor={m.type === "buy" ? C.green : C.red}
                label={m.type.toUpperCase()}
                onRemove={() => {
                  setMarkers(p => {
                    const next = p.filter((x, idx) => !(x.source !== "ieb" && idx === p.indexOf(m)));
                    applyMarkers(next);
                    return next;
                  });
                }}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── DrawRow helper ─────────────────────────────────────────────────────────────
function DrawRow({ icon, iconColor, label, onRemove }: { icon: string; iconColor: string; label: string; onRemove: () => void }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 12px", fontSize: 11, color: "#e2e8f0", borderBottom: "1px solid #0d0d1a" }}>
      <span style={{ color: iconColor, fontWeight: 700 }}>{icon}</span>
      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "#94a3b8" }}>{label}</span>
      <button onClick={onRemove} style={{ background: "transparent", border: "none", color: "#475569", cursor: "pointer", fontSize: 11, padding: 2, flexShrink: 0 }}>✕</button>
    </div>
  );
}

// ── Inline styles ──────────────────────────────────────────────────────────────
const selectStyle: React.CSSProperties = {
  background: "#0d0d1a", border: "1px solid #1a1a2e", color: "#e2e8f0",
  padding: "4px 8px", borderRadius: 5, fontSize: 12, cursor: "pointer",
  fontFamily: "inherit",
};

const pillStyle: React.CSSProperties = {
  padding: "3px 8px", borderRadius: 4, fontSize: 11, cursor: "pointer",
  fontFamily: "inherit", transition: "all 0.15s",
};

const btnStyle: React.CSSProperties = {
  padding: "5px 14px", borderRadius: 6, border: "none", fontSize: 12,
  cursor: "pointer", fontWeight: 600, fontFamily: "inherit",
};
