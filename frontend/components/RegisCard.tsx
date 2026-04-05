"use client";

/**
 * RegisCard — Compact institutional sigil card (center column of RegisRow).
 *
 * Bloomberg terminal meets medieval seal.
 * Width: 240px max. Height: compact — 30% smaller than before.
 * USDC line removed (treasury shown in flanking stats).
 */

import { motion } from "framer-motion";
import type { Wallet, Task } from "@/lib/api";
import { COORDINATOR_PERSONA } from "@/lib/personas";

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
          animation: rc-spin 60s linear infinite;
          transform-origin: center;
        }
      `}</style>
      <div
        className={isActive ? "rc-sigil-active" : "rc-sigil-resting"}
        style={{ display: "flex", alignItems: "center", justifyContent: "center" }}
      >
        <svg width="40" height="40" viewBox="0 0 48 48" fill="none">
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
        <span key={i} style={{ color: i < n ? "#F59E0B" : "#333", fontSize: 8 }}>★</span>
      ))}
    </span>
  );
}

// ── Main card ──────────────────────────────────────────────────────────────────

export default function RegisCard({ task }: Props) {
  const p = COORDINATOR_PERSONA;

  const isActive = task.status !== "complete" && task.status !== "failed";
  const statusLabel = isActive ? "MANAGING" : "RESTING";
  const statusColor = isActive ? "#F59E0B" : "#666";

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      style={{
        width: 220,
        background: "#0A0A0A",
        border: "1px solid #F59E0B",
        borderRadius: 10,
        boxShadow: "0 0 16px rgba(245,158,11,0.18)",
        padding: "12px 14px",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 7,
      }}
    >
      {/* Seal inscription */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 10,
          color: "#F59E0B",
          letterSpacing: "0.3em",
          textTransform: "uppercase",
          fontWeight: 700,
          textAlign: "center",
        }}
      >
        REGIS
      </div>

      {/* SVG Sigil */}
      <RegisSigil isActive={isActive} />

      {/* Status */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 9,
          color: statusColor,
          letterSpacing: "0.2em",
          textTransform: "uppercase",
        }}
      >
        {statusLabel}
      </div>

      <Stars n={p.reputation} />

      {/* Skills — minimal text dots */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 7,
          color: "#3a3000",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          textAlign: "center",
          lineHeight: 1.6,
          whiteSpace: "nowrap",
        }}
      >
        {p.skills.join("  ·  ")}
      </div>

    </motion.div>
  );
}
