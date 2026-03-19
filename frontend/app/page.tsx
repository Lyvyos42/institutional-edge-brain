"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem("ieb_token")) {
      router.replace("/dashboard");
    }
  }, [router]);

  return (
    <main style={{ minHeight: "100vh", background: "#06060f", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24, textAlign: "center" }}>
      {/* Animated background dots */}
      <div style={{ position: "fixed", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
        {[...Array(20)].map((_, i) => (
          <div key={i} style={{
            position: "absolute",
            width: 2, height: 2,
            background: i % 3 === 0 ? "#00d4ff" : i % 3 === 1 ? "#7c3aed" : "#00f5a0",
            borderRadius: "50%",
            left: `${(i * 37 + 11) % 100}%`,
            top: `${(i * 53 + 7) % 100}%`,
            opacity: 0.4,
            animation: `pulse-glow ${2 + (i % 3)}s ease-in-out infinite`,
          }} />
        ))}
      </div>

      <div style={{ position: "relative", zIndex: 1, maxWidth: 600 }}>
        {/* Logo */}
        <div style={{ width: 64, height: 64, borderRadius: 16, background: "rgba(0,212,255,0.1)", border: "1px solid rgba(0,212,255,0.3)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 24px" }}>
          <svg width={32} height={32} viewBox="0 0 32 32" fill="none">
            <circle cx="16" cy="16" r="6" fill="#00d4ff" opacity="0.9"/>
            <circle cx="16" cy="16" r="12" stroke="#00d4ff" strokeWidth="1" opacity="0.3"/>
            <circle cx="16" cy="16" r="15" stroke="#00d4ff" strokeWidth="0.5" opacity="0.15"/>
            {[0, 60, 120, 180, 240, 300].map((deg, i) => (
              <circle key={i}
                cx={16 + 12 * Math.cos(deg * Math.PI / 180)}
                cy={16 + 12 * Math.sin(deg * Math.PI / 180)}
                r="2.5" fill={i % 2 === 0 ? "#7c3aed" : "#00f5a0"} opacity="0.8"
              />
            ))}
          </svg>
        </div>

        <h1 style={{ color: "#fff", fontWeight: 800, fontSize: "2rem", margin: "0 0 8px", letterSpacing: "-0.02em" }}>
          Institutional Edge Brain
        </h1>
        <p style={{ color: "#64748b", fontSize: "1rem", margin: "0 0 8px" }}>
          12-module institutional intelligence system
        </p>
        <p style={{ color: "#334155", fontSize: "0.8rem", margin: "0 0 40px", fontFamily: "monospace" }}>
          ENTROPY · VPIN · ICEBERG · COT · SWEEP · VOLATILITY · GAMMA
        </p>

        <div style={{ display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
          <Link href="/login" style={{
            background: "linear-gradient(135deg, #00d4ff, #7c3aed)",
            color: "#fff", fontWeight: 700, padding: "12px 32px",
            borderRadius: 8, textDecoration: "none", fontSize: "0.9rem",
          }}>
            Sign In
          </Link>
          <Link href="/register" style={{
            background: "rgba(255,255,255,0.05)", color: "#e2e8f0",
            fontWeight: 600, padding: "12px 32px", borderRadius: 8,
            textDecoration: "none", fontSize: "0.9rem",
            border: "1px solid rgba(255,255,255,0.1)",
          }}>
            Create Account
          </Link>
        </div>

        <p style={{ color: "#1e293b", fontSize: "0.75rem", marginTop: 40 }}>
          QuantNeuralEdge · Institutional Grade Intelligence
        </p>
      </div>
    </main>
  );
}
