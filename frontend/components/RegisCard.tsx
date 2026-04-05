"use client";

/**
 * RegisCard — Compact institutional sigil card.
 *
 * Bloomberg terminal meets medieval seal.
 * Replaces the emoji-based CoordinatorCard header in Kingdom mode.
 * Used in the split-layout right panel, centered above agent grid.
 *
 * Width: ~280px  Height: auto  Background: #0A0A0A
 */

import { motion } from "framer-motion";
import type { Wallet, Task } from "@/lib/api";
import { COORDINATOR_PERSONA } from "@/lib/personas";
import { useSolRate } from "@/lib/useSolRate";

interface Props {
  wallet: Wallet;
  task: Task;
}

// ── SVG Sigil ──────────────────────────────────────────────────────────────────

function RegisSigil({ isActive }: { isActive: boolean }) {
  return (
    <>
      <style>{`
        @keyframes rc-spin {
          to { transform: rotate(360deg); }
        }
        .rc-sigil-active {
          animation: rc-spin 20s linear infinite;
          transform-origin: center;
        }
        .rc-sigil-resting {
          animation: rc-spin 20s linear infinite;
          animation-play-state: paused;
          transform-origin: center;
        }
      `}</style>
      <div
        className={isActive ? "rc-sigil-active" : "rc-sigil-resting"}
        style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
      >
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
          {/* Outer octagon */}
          <polygon
            points="24,2 38,8 46,22 46,26 38,40 24,46 10,40 2,26 2,22 10,8"
            fill="none"
            stroke="#F59E0B"
            strokeWidth="1.5"
            opacity="0.6"
          />
          {/* Inner diamond */}
          <polygon
            points="24,10 34,24 24,38 14,24"
            fill="none"
            stroke="#F59E0B"
            strokeWidth="1"
          />
          {/* Center dot */}
          <circle cx="24" cy="24" r="3" fill="#F59E0B" />
          {/* Four cardinal marks */}
          <line x1="24" y1="2"  x2="24" y2="8"  stroke="#F59E0B" strokeWidth="1" />
          <line x1="46" y1="24" x2="40" y2="24" stroke="#F59E0B" strokeWidth="1" />
          <line x1="24" y1="46" x2="24" y2="40" stroke="#F59E0B" strokeWidth="1" />
          <line x1="2"  y1="24" x2="8"  y2="24" stroke="#F59E0B" strokeWidth="1" />
        </svg>
      </div>
    </>
  );
}

// ── Stars (compact inline) ─────────────────────────────────────────────────────

function Stars({ n }: { n: number }) {
  return (
    <span style={{ display: "inline-flex", gap: 1 }}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} style={{ color: i < n ? "#F59E0B" : "#333", fontSize: 9 }}>★</span>
      ))}
    </span>
  );
}

// ── Main card ──────────────────────────────────────────────────────────────────

export default function RegisCard({ wallet, task }: Props) {
  const { toSol } = useSolRate();
  const p = COORDINATOR_PERSONA;

  const isActive = task.status !== "complete" && task.status !== "failed";
  const statusLabel = isActive ? "MANAGING" : "RESTING";
  const statusColor = isActive ? "#F59E0B" : "#555";

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        width: 280,
        background: "#0A0A0A",
        border: "1px solid #F59E0B",
        borderRadius: 12,
        boxShadow: "0 0 12px rgba(245,158,11,0.15)",
        padding: "16px 18px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 10,
      }}
    >
      {/* Seal inscription */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 11,
          color: "#F59E0B",
          letterSpacing: "0.3em",
          textTransform: "uppercase",
          fontWeight: 600,
          textAlign: "center",
        }}
      >
        REGIS
      </div>

      {/* SVG Sigil */}
      <RegisSigil isActive={isActive} />

      {/* Status */}
      <div style={{ textAlign: "center" }}>
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 10,
            color: statusColor,
            letterSpacing: "0.2em",
            textTransform: "uppercase",
          }}
        >
          {statusLabel}
        </div>
      </div>

      {/* Treasury */}
      <div style={{ textAlign: "center" }}>
        <div
          style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 20,
            fontWeight: 700,
            color: "#F59E0B",
            letterSpacing: "0.02em",
            lineHeight: 1,
          }}
        >
          {toSol(Number(wallet.budget_cap), 3)}
        </div>
        <div
          style={{
            fontFamily: "monospace",
            fontSize: 9,
            color: "#444",
            marginTop: 2,
            letterSpacing: "0.08em",
          }}
        >
          {Number(wallet.budget_cap).toFixed(2)} USDC
        </div>
      </div>

      {/* Stats row */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 9,
          color: "#555",
          letterSpacing: "0.06em",
          textAlign: "center",
        }}
      >
        T:{p.stats.tasks} · {p.stats.successRate}% · {p.stats.avgSpeed}s avg
      </div>

      <Stars n={p.reputation} />

      {/* Skills — minimal text dots, no pills */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 8,
          color: "#3a3000",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          textAlign: "center",
          lineHeight: 1.8,
        }}
      >
        {p.skills.join("  ·  ")}
      </div>
    </motion.div>
  );
}
