"use client";

/**
 * TelegramPanel — chat UI mockup showing REGIS signal events from audit_log.
 *
 * Reads from the live audit log query. Renders each event as a dark bubble
 * in a Telegram-style chat feed, with REGIS avatar and timestamps.
 * Filters to events that would generate Telegram notifications.
 */

import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { getAuditLogs } from "@/lib/api";
import { useSolRate } from "@/lib/useSolRate";

const NOTIFY_EVENTS = new Set([
  "task_complete",
  "payment_signed",
  "payment_blocked",
  "task_failed",
  "x402_payment",
  "peer_payment",
]);

const EVENT_COLOR: Record<string, string> = {
  task_complete:  "#F59E0B",
  payment_signed: "#22c55e",
  payment_blocked:"#ef4444",
  task_failed:    "#ef4444",
  x402_payment:   "#9945FF",
  peer_payment:   "#3B82F6",
};

function formatMessage(msg: string, toSol: (n: number, d?: number) => string): string {
  // Replace USDC amounts with ◎ SOL
  return msg.replace(/(\d+\.?\d*)\s*USDC/g, (_, n) => toSol(parseFloat(n), 4));
}

function timeLabel(isoDate: string): string {
  const d = new Date(isoDate);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// REGIS avatar SVG (mini sigil)
function RegisAvatar() {
  return (
    <div
      style={{
        width: 28,
        height: 28,
        borderRadius: "50%",
        background: "#0A0A0A",
        border: "1px solid #F59E0B",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      <svg width="14" height="14" viewBox="0 0 48 48" fill="none">
        <polygon points="24,2 38,8 46,22 46,26 38,40 24,46 10,40 2,26 2,22 10,8"
          fill="none" stroke="#F59E0B" strokeWidth="2.5" opacity="0.8" />
        <circle cx="24" cy="24" r="4" fill="#F59E0B" />
      </svg>
    </div>
  );
}

export default function TelegramPanel() {
  const { toSol } = useSolRate();

  const { data } = useQuery({
    queryKey: ["audit"],
    queryFn: getAuditLogs,
    refetchInterval: 3000,
    staleTime: 1500,
  });

  const messages = (data?.logs ?? [])
    .filter((e) => NOTIFY_EVENTS.has(e.event_type))
    .slice(-12)
    .reverse();

  if (messages.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{
        background: "#07070d",
        border: "1px solid #1a1a2e",
        borderRadius: 10,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 14px",
          borderBottom: "1px solid #111",
          background: "#0a0a14",
        }}
      >
        <RegisAvatar />
        <div>
          <div style={{ fontFamily: "monospace", fontSize: 10, color: "#F59E0B", letterSpacing: "0.08em", fontWeight: 700 }}>
            REGIS
          </div>
          <div style={{ fontFamily: "monospace", fontSize: 8, color: "#333", letterSpacing: "0.06em" }}>
            SwarmPay Signal Feed · {messages.length} events
          </div>
        </div>
        {/* Telegram icon hint */}
        <div style={{ marginLeft: "auto", fontFamily: "monospace", fontSize: 8, color: "#1a1a3a", letterSpacing: "0.06em" }}>
          ✈ TELEGRAM
        </div>
      </div>

      {/* Messages */}
      <div
        style={{
          maxHeight: 240,
          overflowY: "auto",
          padding: "8px 12px",
          display: "flex",
          flexDirection: "column",
          gap: 6,
        }}
      >
        <AnimatePresence initial={false}>
          {messages.map((entry) => {
            const color = EVENT_COLOR[entry.event_type] ?? "#444";
            const text = formatMessage(entry.message, toSol);
            return (
              <motion.div
                key={entry.id}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2 }}
                style={{ display: "flex", alignItems: "flex-start", gap: 6 }}
              >
                <RegisAvatar />
                <div
                  style={{
                    flex: 1,
                    background: "#0f0f1a",
                    borderRadius: "0 8px 8px 8px",
                    padding: "6px 10px",
                    border: `1px solid ${color}18`,
                  }}
                >
                  <div
                    style={{
                      fontFamily: "monospace",
                      fontSize: 8,
                      color: color,
                      letterSpacing: "0.08em",
                      marginBottom: 3,
                      textTransform: "uppercase",
                    }}
                  >
                    {entry.event_type.replace(/_/g, " ")}
                  </div>
                  <div
                    style={{
                      fontFamily: "monospace",
                      fontSize: 9,
                      color: "#666",
                      lineHeight: 1.5,
                      letterSpacing: "0.02em",
                    }}
                  >
                    {text}
                  </div>
                  <div
                    style={{
                      fontFamily: "monospace",
                      fontSize: 7,
                      color: "#222",
                      marginTop: 4,
                      textAlign: "right",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {timeLabel(entry.created)}
                  </div>
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}
