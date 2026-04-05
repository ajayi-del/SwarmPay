"use client";

/**
 * SovereigntyPanel — ⚔️ Race to Sovereignty dashboard.
 *
 * Polls /sovereignty/leaderboard every 5s.
 * Shows a horizontal bar chart: bar width = proportion of max earnings.
 * Gold border = current ruler.
 * Closest non-ruler bar pulses.
 * Overthrow threshold line (REGIS distributed) overlaid as a gold vertical line.
 * Succession history below bars.
 */

import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { useSolRate } from "@/lib/useSolRate";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface SovereigntyEntry {
  agent_id: string;
  city: string;
  flag: string;
  role: string;
  lifetime_earnings_usdc: number;
  lifetime_earnings_sol: number;
  lifetime_distributed_usdc: number;
  lifetime_distributed_sol: number;
  is_ruler: boolean;
  times_ruled: number;
  overthrow_count: number;
  ascended_at: string;
}

interface LeaderboardResponse {
  leaderboard: SovereigntyEntry[];
  count: number;
}

const AGENT_COLORS: Record<string, string> = {
  REGIS:  "#F59E0B",
  ATLAS:  "#3b82f6",
  CIPHER: "#a855f7",
  FORGE:  "#f97316",
  BISHOP: "#e8e8f0",
  "SØN":  "#00ffff",
};

function timeAgo(isoDate: string): string {
  if (!isoDate) return "";
  const diffMs = Date.now() - new Date(isoDate).getTime();
  const m = Math.floor(diffMs / 60000);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d > 0) return `${d}d ${h % 24}h`;
  if (h > 0) return `${h}h ${m % 60}m`;
  return `${m}m`;
}

export default function SovereigntyPanel() {
  const { toSol } = useSolRate();

  const { data } = useQuery<LeaderboardResponse>({
    queryKey: ["sovereignty-leaderboard"],
    queryFn: async () => {
      const r = await fetch(`${API}/sovereignty/leaderboard`);
      if (!r.ok) throw new Error("leaderboard unavailable");
      return r.json();
    },
    refetchInterval: 5000,
    staleTime: 3000,
    retry: 1,
  });

  const board = data?.leaderboard ?? [];
  if (board.length === 0) return null;

  const ruler = board.find((e) => e.is_ruler);
  const threshold_usdc = ruler?.lifetime_distributed_usdc ?? 0;
  const maxEarnings = Math.max(...board.map((e) => e.lifetime_earnings_usdc), threshold_usdc, 0.0001);

  // Closest non-ruler to the threshold
  const challengers = board.filter((e) => !e.is_ruler && e.lifetime_earnings_usdc > 0);
  const closest = challengers.length > 0
    ? challengers.reduce((a, b) =>
        a.lifetime_earnings_usdc > b.lifetime_earnings_usdc ? a : b
      )
    : null;

  const thresholdPct = threshold_usdc > 0 ? (threshold_usdc / maxEarnings) * 100 : 0;

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
          justifyContent: "space-between",
          padding: "8px 14px",
          borderBottom: "1px solid #111",
          background: "#0a0a14",
        }}
      >
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 10,
            color: "#F59E0B",
            letterSpacing: "0.2em",
            fontWeight: 700,
          }}
        >
          ⚔️ RACE TO SOVEREIGNTY
        </span>
        {ruler && (
          <span style={{ fontFamily: "monospace", fontSize: 8, color: "#555", letterSpacing: "0.06em" }}>
            {ruler.flag} {ruler.agent_id} reigns · {timeAgo(ruler.ascended_at)}
          </span>
        )}
      </div>

      {/* Bar chart */}
      <div style={{ padding: "10px 14px", position: "relative" }}>
        {/* Threshold line */}
        {thresholdPct > 0 && thresholdPct < 99 && (
          <div
            style={{
              position: "absolute",
              left: `calc(14px + ${thresholdPct}% * 0.82)`,  // 82% of inner width is bars
              top: 10,
              bottom: 10,
              width: 1,
              background: "rgba(245,158,11,0.4)",
              zIndex: 2,
              pointerEvents: "none",
            }}
            title={`Overthrow threshold: ${toSol(threshold_usdc, 4)}`}
          />
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {board.map((entry) => {
            const color = AGENT_COLORS[entry.agent_id] ?? "#555";
            const barPct = maxEarnings > 0
              ? Math.min(100, (entry.lifetime_earnings_usdc / maxEarnings) * 100)
              : 0;
            const isClosest = closest?.agent_id === entry.agent_id;
            const isRuler = entry.is_ruler;
            const gap = threshold_usdc - entry.lifetime_earnings_usdc;

            return (
              <div
                key={entry.agent_id}
                style={{ display: "grid", gridTemplateColumns: "52px 1fr 64px 52px", alignItems: "center", gap: 8 }}
              >
                {/* Label */}
                <span
                  style={{
                    fontFamily: "monospace",
                    fontSize: 9,
                    color: isRuler ? "#F59E0B" : color,
                    letterSpacing: "0.06em",
                    fontWeight: isRuler ? 700 : 400,
                  }}
                >
                  {entry.flag} {entry.agent_id}
                </span>

                {/* Bar */}
                <div style={{ position: "relative", height: 8, background: "#111", borderRadius: 4, overflow: "visible" }}>
                  {isClosest && gap < threshold_usdc * 0.1 ? (
                    <motion.div
                      animate={{ opacity: [0.7, 1, 0.7] }}
                      transition={{ duration: 1.5, repeat: Infinity }}
                      style={{
                        position: "absolute",
                        left: 0,
                        top: 0,
                        height: "100%",
                        width: `${barPct}%`,
                        background: color,
                        borderRadius: 4,
                        boxShadow: `0 0 6px ${color}`,
                      }}
                    />
                  ) : (
                    <div
                      style={{
                        position: "absolute",
                        left: 0,
                        top: 0,
                        height: "100%",
                        width: `${barPct}%`,
                        background: isRuler ? `linear-gradient(90deg, ${color}, ${color}cc)` : color,
                        borderRadius: 4,
                        opacity: isRuler ? 1 : 0.7,
                        boxShadow: isRuler ? `0 0 8px ${color}80` : "none",
                        transition: "width 0.5s ease",
                      }}
                    />
                  )}
                </div>

                {/* Amount */}
                <span
                  style={{
                    fontFamily: "monospace",
                    fontSize: 9,
                    color: isRuler ? "#F59E0B" : "#555",
                    textAlign: "right",
                    letterSpacing: "0.02em",
                  }}
                >
                  {toSol(entry.lifetime_earnings_usdc, 4)}
                </span>

                {/* Status badge */}
                <span
                  style={{
                    fontFamily: "monospace",
                    fontSize: 7,
                    color: isRuler ? "#F59E0B" : isClosest ? "#ef4444" : "#333",
                    letterSpacing: "0.06em",
                    textAlign: "right",
                  }}
                >
                  {isRuler
                    ? "👑 RULER"
                    : isClosest && gap <= 0
                    ? "⚔️ SEIZING"
                    : isClosest
                    ? `← ${toSol(gap, 3)}`
                    : entry.overthrow_count > 0
                    ? "DEPOSED"
                    : ""}
                </span>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        {thresholdPct > 0 && (
          <div
            style={{
              marginTop: 8,
              fontFamily: "monospace",
              fontSize: 7,
              color: "#333",
              letterSpacing: "0.08em",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <span style={{ color: "rgba(245,158,11,0.5)" }}>│</span>
            <span>OVERTHROW THRESHOLD: {toSol(threshold_usdc, 4)} (REGIS total distributed)</span>
          </div>
        )}
      </div>

      {/* Succession history */}
      <AnimatePresence>
        {ruler && (
          <div
            style={{
              borderTop: "1px solid #111",
              padding: "6px 14px",
              fontFamily: "monospace",
              fontSize: 8,
              color: "#333",
              letterSpacing: "0.06em",
            }}
          >
            <span style={{ color: "#444" }}>👑 Succession: </span>
            {board
              .filter((e) => e.overthrow_count > 0 || e.is_ruler)
              .map((e, i) => (
                <span key={e.agent_id}>
                  {i > 0 && <span style={{ color: "#222" }}> → </span>}
                  <span style={{ color: e.is_ruler ? "#F59E0B" : "#444" }}>
                    {e.agent_id}
                    {e.is_ruler ? " (NOW)" : ` ×${e.overthrow_count}`}
                  </span>
                </span>
              ))}
            {ruler.ascended_at && (
              <span style={{ color: "#222", marginLeft: 6 }}>
                · Current reign: {timeAgo(ruler.ascended_at)}
              </span>
            )}
          </div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
