"use client";

/**
 * AuditLog — Live terminal feed with institutional styling.
 *
 * Each entry is a single line: [BADGE] message  timestamp
 * Left border color-coded by event type.
 * New entries animate in from x:-20, opacity:0 → x:0, opacity:1.
 * Max 20 entries visible, auto-scrolls to latest.
 */

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { getAuditLogs, type AuditEntry } from "@/lib/api";
import { useSolRate } from "@/lib/useSolRate";

// ── Event configuration ────────────────────────────────────────────────────────

const EVENT_CONFIG: Record<string, { badge: string; color: string }> = {
  // ── Core task events ──────────────────────────────────────────────────
  task_complete:      { badge: "DONE  ", color: "#F59E0B" },
  task_submitted:     { badge: "TASK  ", color: "#F59E0B" },
  payment_signed:     { badge: "SIGN  ", color: "#22C55E" },
  payment_blocked:    { badge: "BLOCK ", color: "#EF4444" },
  peer_payment:       { badge: "PEER  ", color: "#3B82F6" },
  x402_payment:       { badge: "x402  ", color: "#9945FF" },
  work_started:       { badge: "START ", color: "#F59E0B" },
  work_complete:      { badge: "WORK  ", color: "#22C55E" },
  agent_spawned:      { badge: "SPAWN ", color: "#3B82F6" },
  reputation_updated: { badge: "REP   ", color: "#FFD700" },
  dead_mans_switch:   { badge: "DMS   ", color: "#EF4444" },
  security:           { badge: "SEC   ", color: "#F97316" },
  // ── Sponsor integrations ─────────────────────────────────────────────
  myriad_bet:         { badge: "⚔ BET ", color: "#F97316" },   // Myriad prediction markets
  atlas_intel:        { badge: "⚡ INTEL", color: "#60A5FA" }, // Helius real-time
  atlas_stream:       { badge: "⚡ STRM", color: "#60A5FA" },  // Allium/Helius stream
  multichain:         { badge: "🌐 MLTC", color: "#9945FF" },  // Uniblock cross-chain
  moonpay_price:      { badge: "◎ PAY  ", color: "#F59E0B" },  // MoonPay price update
  // ── Autonomous economy ───────────────────────────────────────────────
  decree:             { badge: "👑 DCRE", color: "#F59E0B" },  // REGIS governance decree
  bishop_fine:        { badge: "⚖ FINE", color: "#EF4444" },  // BISHOP fine issued
  yield_proposal:     { badge: "📊 PROP", color: "#22C55E" },  // CIPHER yield proposal
  proposal_approved:  { badge: "✅ APPR", color: "#22C55E" },  // REGIS approved
  // ── Agent scans ──────────────────────────────────────────────────────
  forge_monitor:      { badge: "🔨 FORG", color: "#F59E0B" },
  son_learning:       { badge: "📚 SØN ", color: "#3B82F6" },
  bishop_compliance:  { badge: "⚖ COMP", color: "#F59E0B" },
};

const DEFAULT_CONFIG = { badge: "EVENT ", color: "#6B7280" };

// ── Extract SOL amount from audit message ──────────────────────────────────────

function extractAndFormatAmounts(message: string, toSol: (u: number, d?: number) => string): string {
  // Replace USDC amounts with SOL display: "3.3333 USDC" → "◎0.0417"
  return message.replace(
    /(\d+(?:\.\d+)?)\s*USDC/gi,
    (_, amt) => toSol(parseFloat(amt), 4)
  );
}

// ── Single terminal line ───────────────────────────────────────────────────────

function TerminalLine({ entry, toSol }: { entry: AuditEntry; toSol: (u: number, d?: number) => string }) {
  const cfg  = EVENT_CONFIG[entry.event_type] ?? DEFAULT_CONFIG;
  const time = new Date(entry.created).toLocaleTimeString("en-GB", {
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
  const msg          = extractAndFormatAmounts(entry.message, toSol);
  const xmtpVerified = entry.metadata?.xmtp_verified === true;
  const isPeer       = entry.event_type === "peer_payment";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: 0,
        borderLeft: `2px solid ${cfg.color}`,
        paddingLeft: 10,
        paddingTop: 3,
        paddingBottom: 3,
        minHeight: 22,
      }}
    >
      {/* Badge */}
      <span
        style={{
          fontFamily: "monospace",
          fontSize: "0.65rem",
          color: cfg.color,
          background: "transparent",
          border: `1px solid ${cfg.color}40`,
          borderRadius: 3,
          padding: "0px 5px",
          letterSpacing: "0.04em",
          flexShrink: 0,
          marginRight: 8,
          lineHeight: "1.6",
        }}
      >
        {cfg.badge.trimEnd()}
      </span>

      {/* Message */}
      <span
        style={{
          fontFamily: "monospace",
          fontSize: "0.7rem",
          color: cfg.color,
          flex: 1,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          lineHeight: "1.6",
        }}
        title={msg}
      >
        {msg}
      </span>

      {/* XMTP verified badge — peer payments only */}
      {isPeer && (
        <span
          style={{
            fontFamily: "monospace",
            fontSize: "0.55rem",
            flexShrink: 0,
            marginLeft: 4,
            padding: "1px 4px",
            borderRadius: 3,
            color:      xmtpVerified ? "#22C55E" : "#444",
            background: xmtpVerified ? "rgba(34,197,94,0.08)" : "transparent",
            border:     `1px solid ${xmtpVerified ? "rgba(34,197,94,0.3)" : "#222"}`,
          }}
          title={xmtpVerified ? "Message verified on XMTP network" : "Internal log only"}
        >
          {xmtpVerified ? "✓ XMTP" : "internal"}
        </span>
      )}

      {/* Timestamp */}
      <span
        style={{
          fontFamily: "monospace",
          fontSize: "0.6rem",
          color: "var(--text-dim)",
          flexShrink: 0,
          marginLeft: 12,
          letterSpacing: "0.03em",
          lineHeight: "1.6",
        }}
      >
        {time}
      </span>
    </motion.div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function AuditLog() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toSol } = useSolRate();

  const { data } = useQuery({
    queryKey: ["audit"],
    queryFn: getAuditLogs,
    refetchInterval: 1500,
  });

  // Auto-scroll to bottom on new entries
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [data]);

  // Newest 20, sorted oldest→newest for terminal feed (scroll to see latest at bottom)
  const raw = data?.logs ?? [];
  const logs = [...raw].slice(0, 20).reverse();

  return (
    <div
      style={{
        background: "#050508",
        border: "1px solid var(--border)",
        borderRadius: 16,
        padding: "14px 16px",
        height: "100%",
        maxHeight: 480,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 10,
          paddingBottom: 8,
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {/* Terminal dot indicators */}
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#ef4444", display: "inline-block" }} />
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#f59e0b", display: "inline-block" }} />
          <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#22c55e", display: "inline-block" }} />
          <span
            style={{
              fontFamily: "monospace",
              fontSize: "0.65rem",
              color: "var(--text-dim)",
              letterSpacing: "0.1em",
              marginLeft: 6,
            }}
          >
            AUDIT LOG — LIVE FEED
          </span>
        </div>
        <span
          style={{
            fontFamily: "monospace",
            fontSize: "0.6rem",
            color: "var(--text-dim)",
            letterSpacing: "0.05em",
          }}
        >
          {raw.length} events
        </span>
      </div>

      {/* Feed */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: 1,
        }}
      >
        {logs.length === 0 ? (
          <div
            style={{
              fontFamily: "monospace",
              fontSize: "0.7rem",
              color: "var(--text-dim)",
              padding: "12px 0",
              letterSpacing: "0.05em",
            }}
          >
            ▊ awaiting events…
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {logs.map((entry) => (
              <TerminalLine key={entry.id} entry={entry} toSol={toSol} />
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
