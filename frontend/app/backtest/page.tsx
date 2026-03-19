"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

// ── Types ──────────────────────────────────────────────────────────────────────
type Bar = { time: number; open: number; high: number; low: number; close: number; volume: number };
type TF  = "5m" | "15m" | "1h" | "4h" | "1d" | "1w";
type Tool = "none" | "trendline" | "hline" | "buy" | "sell" | "eraser";

interface HLine  { id: string; price: number; color: string }
interface TLine  { id: string; p1: { time: number; value: number }; p2: { time: number; value: number }; color: string }
interface Marker { time: number; type: "buy" | "sell" }

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SYMBOLS: Record<string, string[]> = {
  "FX":       ["EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD","EURGBP","EURJPY","GBPJPY"],
  "Metals":   ["XAUUSD","XAGUSD"],
  "Energy":   ["USOIL","UKOIL","NATGAS"],
  "Crypto":   ["BTCUSD","ETHUSD"],
  "Indices":  ["SPX500","NAS100","GER40","UK100","JPN225"],
  "Stocks":   ["AAPL","MSFT","NVDA","TSLA","AMZN","GOOGL","META"],
};

const TIMEFRAMES: { label: string; value: TF }[] = [
  { label: "5m",  value: "5m"  },
  { label: "15m", value: "15m" },
  { label: "1h",  value: "1h"  },
  { label: "4h",  value: "4h"  },
  { label: "1D",  value: "1d"  },
  { label: "1W",  value: "1w"  },
];

const TOOL_INFO: Record<Tool, string> = {
  none:      "Click a tool to start drawing",
  trendline: "Click first point → click second point to draw trend line",
  hline:     "Click any bar to draw a horizontal level at that price",
  buy:       "Click a bar to place a Buy signal marker",
  sell:      "Click a bar to place a Sell signal marker",
  eraser:    "Click a drawing to remove it",
};

// ── Colour palette ─────────────────────────────────────────────────────────────
const C = {
  bg:       "#06060f",
  surface:  "#0d0d1a",
  border:   "#1a1a2e",
  accent:   "#2563ff",
  green:    "#00c896",
  red:      "#ff4466",
  gold:     "#f59e0b",
  text:     "#e2e8f0",
  muted:    "#64748b",
  tline:    "#f59e0b",
  hline:    "#2563ff",
};

// ── Main component ─────────────────────────────────────────────────────────────
export default function BacktestPage() {
  const router    = useRouter();
  const chartRef  = useRef<HTMLDivElement>(null);
  const chartInst = useRef<any>(null);
  const candleSer = useRef<any>(null);
  const volSer    = useRef<any>(null);
  const lineRefs  = useRef<Map<string, any>>(new Map());

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
  const [tlines,    setTlines]    = useState<TLine[]>([]);
  const [markers,   setMarkers]   = useState<Marker[]>([]);
  const pendingPoint = useRef<{ time: number; value: number } | null>(null);

  // ── Fetch OHLCV & initialise chart ────────────────────────────────────────
  const loadData = useCallback(async (sym: string, tf: TF, yr: number) => {
    setLoading(true);
    setError("");
    try {
      const res  = await fetch(`${API}/api/backtest/ohlcv?symbol=${sym}&timeframe=${tf}&years=${yr}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || "Fetch failed");

      const data: Bar[] = json.data;
      setBars(data.length);

      if (!chartInst.current || !candleSer.current) return;

      const candles = data.map(b => ({ time: b.time as any, open: b.open, high: b.high, low: b.low, close: b.close }));
      const volumes = data.map(b => ({
        time:  b.time as any,
        value: b.volume,
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

  // ── Mount chart once ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!chartRef.current) return;
    let chart: any, cSeries: any, vSeries: any;

    import("lightweight-charts").then(({ createChart, CrosshairMode, LineStyle }) => {
      chart = createChart(chartRef.current!, {
        layout:     { background: { color: C.bg }, textColor: C.text },
        grid:       { vertLines: { color: C.border }, horzLines: { color: C.border } },
        crosshair:  { mode: CrosshairMode.Normal },
        rightPriceScale: { borderColor: C.border },
        timeScale:  { borderColor: C.border, timeVisible: true, secondsVisible: false },
        width:  chartRef.current!.clientWidth,
        height: 520,
      });

      cSeries = chart.addCandlestickSeries({
        upColor:       C.green,
        downColor:     C.red,
        borderUpColor: C.green,
        borderDownColor: C.red,
        wickUpColor:   C.green,
        wickDownColor: C.red,
      });

      vSeries = chart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: "vol",
      });
      chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

      // Crosshair → OHLCV tooltip
      chart.subscribeCrosshairMove((param: any) => {
        if (!param.time || !param.seriesData) return;
        const d = param.seriesData.get(cSeries);
        if (!d) return;
        const date = new Date(param.time * 1000);
        const fmt  = date.toISOString().replace("T", " ").slice(0, 16);
        setOhlcv({ t: fmt, o: d.open, h: d.high, l: d.low, c: d.close });
      });

      // Chart click → drawing tools
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

      // Resize observer
      const ro = new ResizeObserver(() => {
        chart.applyOptions({ width: chartRef.current!.clientWidth });
      });
      ro.observe(chartRef.current!);

      loadData("EURUSD", "1d", 2);

      return () => { ro.disconnect(); chart.remove(); };
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Handle chart click based on active tool ───────────────────────────────
  const handleChartClick = useCallback((time: number, price: number) => {
    const currentTool = (document.getElementById("activeTool") as HTMLInputElement)?.value as Tool;

    if (currentTool === "hline") {
      addHLine(price);
    } else if (currentTool === "trendline") {
      const pending = pendingPoint.current;
      if (!pending) {
        pendingPoint.current = { time, value: price };
      } else {
        addTLine(pending, { time, value: price });
        pendingPoint.current = null;
      }
    } else if (currentTool === "buy") {
      addMarker(time, "buy");
    } else if (currentTool === "sell") {
      addMarker(time, "sell");
    }
  }, []);

  // ── Drawing actions ───────────────────────────────────────────────────────
  const addHLine = (price: number) => {
    if (!candleSer.current) return;
    const id    = `hl-${Date.now()}`;
    const pline = candleSer.current.createPriceLine({
      price,
      color:            C.hline,
      lineWidth:        1,
      lineStyle:        2, // dashed
      axisLabelVisible: true,
      title:            "Level",
    });
    lineRefs.current.set(id, pline);
    setHlines(prev => [...prev, { id, price, color: C.hline }]);
  };

  const addTLine = (p1: { time: number; value: number }, p2: { time: number; value: number }) => {
    if (!chartInst.current) return;
    const id     = `tl-${Date.now()}`;
    const series = chartInst.current.addLineSeries({
      color:     C.tline,
      lineWidth: 1,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    series.setData([
      { time: Math.min(p1.time, p2.time) as any, value: p1.time <= p2.time ? p1.value : p2.value },
      { time: Math.max(p1.time, p2.time) as any, value: p1.time <= p2.time ? p2.value : p1.value },
    ]);
    lineRefs.current.set(id, series);
    setTlines(prev => [...prev, { id, p1, p2, color: C.tline }]);
  };

  const addMarker = (time: number, type: "buy" | "sell") => {
    setMarkers(prev => {
      const next = [...prev, { time, type }];
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
      color:    m.type === "buy" ? C.green : C.red,
      shape:    m.type === "buy" ? "arrowUp" : "arrowDown",
      text:     m.type === "buy" ? "BUY" : "SELL",
    })));
  };

  const clearAll = () => {
    // Remove trend line series
    tlines.forEach(tl => {
      const s = lineRefs.current.get(tl.id);
      if (s && chartInst.current) try { chartInst.current.removeSeries(s); } catch {}
      lineRefs.current.delete(tl.id);
    });
    // Remove price lines
    hlines.forEach(hl => {
      const pl = lineRefs.current.get(hl.id);
      if (pl && candleSer.current) try { candleSer.current.removePriceLine(pl); } catch {}
      lineRefs.current.delete(hl.id);
    });
    setHlines([]);
    setTlines([]);
    setMarkers([]);
    pendingPoint.current = null;
    if (candleSer.current) candleSer.current.setMarkers([]);
  };

  const handleLoad = () => {
    clearAll();
    loadData(symbol, timeframe, years);
  };

  const selectTool = (t: Tool) => {
    setTool(t);
    pendingPoint.current = null;
    const el = document.getElementById("activeTool") as HTMLInputElement;
    if (el) el.value = t;
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "monospace" }}>
      {/* Hidden input carries active tool to the click handler closure */}
      <input id="activeTool" type="hidden" defaultValue="none" />

      {/* ── Top Nav ── */}
      <nav style={{ background: C.surface, borderBottom: `1px solid ${C.border}`, padding: "0 24px", display: "flex", alignItems: "center", gap: 24, height: 52 }}>
        <span style={{ color: C.accent, fontWeight: 700, fontSize: 15, letterSpacing: 1 }}>IEB</span>
        <Link href="/dashboard" style={{ color: C.muted, textDecoration: "none", fontSize: 13 }}>Dashboard</Link>
        <span style={{ color: C.text, fontSize: 13, borderBottom: `2px solid ${C.accent}`, paddingBottom: 2 }}>Backtest</span>
        <div style={{ flex: 1 }} />
        <span style={{ color: C.muted, fontSize: 12 }}>Institutional Edge Brain</span>
      </nav>

      {/* ── Controls bar ── */}
      <div style={{ background: C.surface, borderBottom: `1px solid ${C.border}`, padding: "10px 24px", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        {/* Symbol group selector */}
        <select
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
          style={selectStyle}
        >
          {Object.entries(SYMBOLS).map(([group, syms]) => (
            <optgroup key={group} label={group}>
              {syms.map(s => <option key={s} value={s}>{s}</option>)}
            </optgroup>
          ))}
        </select>

        {/* Timeframe pills */}
        <div style={{ display: "flex", gap: 4 }}>
          {TIMEFRAMES.map(tf => (
            <button
              key={tf.value}
              onClick={() => setTimeframe(tf.value)}
              style={{
                ...pillStyle,
                background: timeframe === tf.value ? C.accent : "transparent",
                color:      timeframe === tf.value ? "#fff" : C.muted,
                border:     `1px solid ${timeframe === tf.value ? C.accent : C.border}`,
              }}
            >{tf.label}</button>
          ))}
        </div>

        {/* Years */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: C.muted }}>
          <span>History:</span>
          {[1, 2, 3, 5].map(y => (
            <button
              key={y}
              onClick={() => setYears(y)}
              style={{
                ...pillStyle,
                background: years === y ? C.gold + "33" : "transparent",
                color:      years === y ? C.gold : C.muted,
                border:     `1px solid ${years === y ? C.gold : C.border}`,
              }}
            >{y}Y</button>
          ))}
        </div>

        <button
          onClick={handleLoad}
          disabled={loading}
          style={{ ...btnStyle, background: C.accent, color: "#fff", opacity: loading ? 0.6 : 1 }}
        >{loading ? "Loading…" : "Load"}</button>

        {bars > 0 && (
          <span style={{ fontSize: 11, color: C.muted }}>{bars.toLocaleString()} bars</span>
        )}
        {error && <span style={{ fontSize: 11, color: C.red }}>{error}</span>}
      </div>

      {/* ── Main content ── */}
      <div style={{ display: "flex", height: "calc(100vh - 130px)" }}>

        {/* ── Left: Drawing toolbar ── */}
        <div style={{ width: 64, background: C.surface, borderRight: `1px solid ${C.border}`, display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 16, gap: 6 }}>
          {([
            { t: "trendline" as Tool, icon: "╱", label: "Trend Line"   },
            { t: "hline"     as Tool, icon: "─", label: "H-Line"       },
            { t: "buy"       as Tool, icon: "↑", label: "Buy Signal"   },
            { t: "sell"      as Tool, icon: "↓", label: "Sell Signal"  },
          ]).map(({ t, icon, label }) => (
            <button
              key={t}
              title={label}
              onClick={() => selectTool(tool === t ? "none" : t)}
              style={{
                width: 44, height: 44,
                background: tool === t ? C.accent + "33" : "transparent",
                border:     `1px solid ${tool === t ? C.accent : C.border}`,
                borderRadius: 6,
                color:  tool === t ? C.accent : C.muted,
                cursor: "pointer",
                fontSize: 18,
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.15s",
              }}
            >{icon}</button>
          ))}

          <div style={{ flex: 1 }} />

          {/* Clear all */}
          <button
            title="Clear all drawings"
            onClick={clearAll}
            style={{ ...toolBtnStyle, color: C.red, borderColor: C.border, marginBottom: 16 }}
          >✕</button>
        </div>

        {/* ── Centre: Chart ── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {/* OHLCV tooltip */}
          <div style={{ padding: "6px 16px", fontSize: 12, color: C.muted, background: C.bg, borderBottom: `1px solid ${C.border}`, display: "flex", gap: 16, minHeight: 32 }}>
            {ohlcv ? (
              <>
                <span style={{ color: C.text }}>{symbol} · {ohlcv.t}</span>
                <span>O <b style={{ color: C.text }}>{ohlcv.o}</b></span>
                <span>H <b style={{ color: C.green }}>{ohlcv.h}</b></span>
                <span>L <b style={{ color: C.red }}>{ohlcv.l}</b></span>
                <span>C <b style={{ color: ohlcv.c >= ohlcv.o ? C.green : C.red }}>{ohlcv.c}</b></span>
              </>
            ) : (
              <span>Hover over the chart to see OHLCV</span>
            )}
          </div>

          {/* Chart canvas */}
          <div
            ref={chartRef}
            style={{ flex: 1, cursor: tool !== "none" ? "crosshair" : "default" }}
          />

          {/* Status bar */}
          <div style={{ padding: "6px 16px", fontSize: 11, color: C.muted, background: C.surface, borderTop: `1px solid ${C.border}`, display: "flex", gap: 16, alignItems: "center" }}>
            <span style={{ color: tool !== "none" ? C.accent : C.muted }}>
              {tool !== "none" ? `● ${TOOL_INFO[tool]}` : TOOL_INFO["none"]}
            </span>
            {pendingPoint.current && tool === "trendline" && (
              <span style={{ color: C.gold }}>● First point set — click second point</span>
            )}
            <div style={{ flex: 1 }} />
            <span>{hlines.length} H-Lines</span>
            <span>{tlines.length} Trend Lines</span>
            <span>{markers.filter(m=>m.type==="buy").length} Buy / {markers.filter(m=>m.type==="sell").length} Sell</span>
            <span style={{ color: C.muted }}>
              {/* TODO: Future instruments — Fibonacci, Rectangle, Text label, Vertical line, Pitchfork */}
              More tools coming soon
            </span>
          </div>
        </div>

        {/* ── Right: Drawing list panel ── */}
        <div style={{ width: 200, background: C.surface, borderLeft: `1px solid ${C.border}`, overflowY: "auto", padding: "12px 0" }}>
          <div style={{ padding: "0 12px 8px", fontSize: 11, color: C.muted, fontWeight: 700, letterSpacing: 1, textTransform: "uppercase" }}>Drawings</div>

          {hlines.length === 0 && tlines.length === 0 && markers.length === 0 && (
            <div style={{ padding: "8px 12px", fontSize: 11, color: C.muted }}>No drawings yet</div>
          )}

          {hlines.map(hl => (
            <div key={hl.id} style={drawingRowStyle}>
              <span style={{ color: C.hline }}>─</span>
              <span style={{ fontSize: 11 }}>{hl.price.toFixed(4)}</span>
              <button onClick={() => {
                const pl = lineRefs.current.get(hl.id);
                if (pl && candleSer.current) try { candleSer.current.removePriceLine(pl); } catch {}
                lineRefs.current.delete(hl.id);
                setHlines(p => p.filter(x => x.id !== hl.id));
              }} style={removeBtn}>✕</button>
            </div>
          ))}

          {tlines.map(tl => (
            <div key={tl.id} style={drawingRowStyle}>
              <span style={{ color: C.tline }}>╱</span>
              <span style={{ fontSize: 11 }}>Trend</span>
              <button onClick={() => {
                const s = lineRefs.current.get(tl.id);
                if (s && chartInst.current) try { chartInst.current.removeSeries(s); } catch {}
                lineRefs.current.delete(tl.id);
                setTlines(p => p.filter(x => x.id !== tl.id));
              }} style={removeBtn}>✕</button>
            </div>
          ))}

          {markers.map((m, i) => (
            <div key={`${m.time}-${i}`} style={drawingRowStyle}>
              <span style={{ color: m.type === "buy" ? C.green : C.red }}>{m.type === "buy" ? "↑" : "↓"}</span>
              <span style={{ fontSize: 11, color: m.type === "buy" ? C.green : C.red }}>
                {m.type.toUpperCase()}
              </span>
              <button onClick={() => {
                setMarkers(p => {
                  const next = p.filter((_, idx) => idx !== i);
                  applyMarkers(next);
                  return next;
                });
              }} style={removeBtn}>✕</button>
            </div>
          ))}

          {/* Note about future tools */}
          <div style={{ margin: "16px 12px 0", padding: "10px", background: C.bg, borderRadius: 6, border: `1px solid ${C.border}` }}>
            <div style={{ fontSize: 10, color: C.muted, lineHeight: 1.6 }}>
              <b style={{ color: C.accent }}>Coming soon:</b><br />
              Rectangle zones<br />
              Fibonacci levels<br />
              Text labels<br />
              Vertical lines<br />
              Pitchfork<br />
              Save drawings
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Inline styles ──────────────────────────────────────────────────────────────
const selectStyle: React.CSSProperties = {
  background: "#0d0d1a",
  border:     "1px solid #1a1a2e",
  color:      "#e2e8f0",
  padding:    "5px 10px",
  borderRadius: 6,
  fontSize:   13,
  cursor:     "pointer",
};

const pillStyle: React.CSSProperties = {
  padding:      "4px 10px",
  borderRadius: 4,
  fontSize:     12,
  cursor:       "pointer",
  fontFamily:   "monospace",
  transition:   "all 0.15s",
};

const btnStyle: React.CSSProperties = {
  padding:      "5px 16px",
  borderRadius: 6,
  border:       "none",
  fontSize:     13,
  cursor:       "pointer",
  fontWeight:   600,
  fontFamily:   "monospace",
};

const toolBtnStyle: React.CSSProperties = {
  width: 44, height: 44,
  background: "transparent",
  border:     "1px solid #1a1a2e",
  borderRadius: 6,
  color:      "#64748b",
  cursor:     "pointer",
  fontSize:   18,
  display:    "flex", alignItems: "center", justifyContent: "center",
};

const drawingRowStyle: React.CSSProperties = {
  display:    "flex",
  alignItems: "center",
  gap:        8,
  padding:    "5px 12px",
  fontSize:   12,
  color:      "#e2e8f0",
  borderBottom: "1px solid #0d0d1a",
};

const removeBtn: React.CSSProperties = {
  marginLeft:   "auto",
  background:   "transparent",
  border:       "none",
  color:        "#64748b",
  cursor:       "pointer",
  fontSize:     11,
  padding:      2,
};
