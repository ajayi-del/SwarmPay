"use client";

/**
 * SovereigntyRaceMini — Compact ⚔️ race panel showing top agents by earnings.
 * Polls /sovereignty/leaderboard every 10s. Max ~120px height. No scroll.
 */

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { useSolRate } from "@/lib/useSolRate";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface LeaderboardEntry {
  agent_id: string;
  flag: string;
  lifetime_earnings_sol: number;
  lifetime_distributed_sol: number;
  is_ruler: boolean;
  ascended_at?: string;
}

const AGENT_COLORS: Record<string, string> = {
  ATLAS:  "#3b82f6",
  CIPHER: "#a78bfa",
  FORGE:  "#f59e0b",
  BISHOP: "#22c55e",
  "SØN":  "#06b6d4",
  REGIS:  "#F59E0B",
};

async function fetchLeaderboard(): Promise<{ leaderboard: LeaderboardEntry[] }> {
  const r = await fetch(`${API}/sovereignty/leaderboard`, { cache: "no-store" });
  if (!r.ok) throw new Error("leaderboard unavailable");
  return r.json();
}

export default function SovereigntyRaceMini() {
  const { toSol } = useSolRate();

  const { data } = useQuery({
    queryKey: ["sovereignty-mini"],
    queryFn: fetchLeaderboard,
    refetchInterval: 10_000,
    staleTime: 8_000,
  });

  if (!data?.leaderboard?.length) return null;

  const all = data.leaderboard;
  const regisEntry = all.find((e) => e.agent_id === "REGIS");
  const threshold = regisEntry?.lifetime_distributed_sol ?? 0;

  // Agents only (exclude REGIS), top 3 by earnings
  const agents = all
    .filter((e) => e.agent_id !== "REGIS")
    .sort((a, b) => b.lifetime_earnings_sol - a.lifetime_earnings_sol)
    .slice(0, 3);

  if (!agents.length) return null;

  const maxEarnings = Math.max(...agents.map((a) => a.lifetime_earnings_sol), threshold * 0.01);
  const leader = agents[0];
  const gap = threshold > 0 ? threshold - leader.lifetime_earnings_sol : 0;
  const pctLeader = threshold > 0 ? leader.lifetime_earnings_sol / threshold : 0;
  const dangerZone = pctLeader >= 0.9;
  const warningZone = pctLeader >= 0.8 && !dangerZone;

  // Succession history — show if any agent has been ruler
  const successions = all.filter((e) => e.agent_id !== "REGIS" && e.ascended_at);

  return (
    <div
      style={{
        marginTop: 10,
        padding: "8px 10px",
        background: "#06040000",
        borderTop: "1px solid #1a1400",
        width: "100%",
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 6 }}>
        <div>
          <span style={{ fontFamily: "monospace", fontSize: 9, color: "#F59E0B", letterSpacing: "0.25em", fontWeight: 700 }}>
            ⚔️ SOVEREIGNTY RACE
          </span>
          <span style={{ fontFamily: "monospace", fontSize: 7, color: "#444", letterSpacing: "0.1em", marginLeft: 8 }}>
            Merit determines the crown
          </span>
        </div>
        {threshold > 0 && (
          <span style={{ fontFamily: "monospace", fontSize: 7, color: "#555" }}>
            REGIS holds {toSol(threshold, 3)}
          </span>
        )}
      </div>

      {/* Bar race */}
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {agents.map((entry, i) => {
          const color = AGENT_COLORS[entry.agent_id] ?? "#666";
          const barPct = maxEarnings > 0 ? (entry.lifetime_earnings_sol / maxEarnings) * 100 : 0;
          const pctOfThreshold = threshold > 0 ? entry.lifetime_earnings_sol / threshold : 0;
          const isPulsing = pctOfThreshold >= 0.8;
          const isLeader = i === 0;

          return (
            <div key={entry.agent_id} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {/* Flag + name */}
              <span style={{ fontFamily: "monospace", fontSize: 8, color: "#888", width: 62, flexShrink: 0 }}>
                {entry.flag} {entry.agent_id}
              </span>

              {/* Bar */}
              <div style={{ flex: 1, height: 6, background: "#111", borderRadius: 3, overflow: "hidden" }}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${barPct}%` }}
                  transition={{ duration: 0.6, ease: "easeOut" }}
                  style={{
                    height: "100%",
                    background: color,
                    borderRadius: 3,
                    opacity: isPulsing ? undefined : 0.7,
                  }}
                  className={isPulsing ? "animate-status-pulse" : undefined}
                />
              </div>

              {/* Earnings */}
              <span style={{ fontFamily: "monospace", fontSize: 7, color, flexShrink: 0, width: 50, textAlign: "right" }}>
                {toSol(entry.lifetime_earnings_sol, 3)}
                {isLeader && threshold > 0 && " 👑"}
              </span>
            </div>
          );
        })}
      </div>

      {/* Gap line */}
      {threshold > 0 && leader && (
        <div style={{ marginTop: 5, fontFamily: "monospace", fontSize: 7, color: dangerZone ? "#ef4444" : warningZone ? "#f59e0b" : "#555" }}>
          {dangerZone && "⚠️ "}
          {leader.flag} {leader.agent_id} leads — {toSol(Math.max(0, gap), 3)} to throne
          {dangerZone && " · IMMINENT"}
        </div>
      )}

      {/* Succession history */}
      {successions.length > 0 && (
        <div style={{ marginTop: 4, fontFamily: "monospace", fontSize: 7, color: "#a78bfa" }}>
          {successions.slice(0, 2).map((e) => {
            const time = e.ascended_at
              ? new Date(e.ascended_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
              : "—";
            return (
              <div key={e.agent_id}>
                👑 {e.agent_id} seized power at {time}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
