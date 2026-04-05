"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { getSwarmStats } from "@/lib/api";
import { useModeStore } from "@/lib/modeStore";
import { AGENT_PERSONAS } from "@/lib/personas";
import { useSolRate } from "@/lib/useSolRate";

/* ── Health ring ──────────────────────────────────────────────────────── */

function HealthRing({ score }: { score: number }) {
  const R = 28;
  const C = 2 * Math.PI * R;
  const pct = Math.min(100, Math.max(0, score)) / 100;
  const color =
    score >= 70 ? "#22c55e" : score >= 40 ? "#f59e0b" : "#ef4444";

  return (
    <div className="relative flex items-center justify-center" style={{ width: 72, height: 72 }}>
      <svg width={72} height={72} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={36} cy={36} r={R} fill="none" stroke="var(--border)" strokeWidth={5} />
        <motion.circle
          cx={36} cy={36} r={R}
          fill="none"
          stroke={color}
          strokeWidth={5}
          strokeLinecap="round"
          strokeDasharray={C}
          initial={{ strokeDashoffset: C }}
          animate={{ strokeDashoffset: C * (1 - pct) }}
          transition={{ duration: 1.2, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-lg font-bold font-jb" style={{ color, lineHeight: 1 }}>{score}</span>
        <span className="text-xs" style={{ color: "var(--text-dim)", fontSize: "0.55rem" }}>/ 100</span>
      </div>
    </div>
  );
}

/* ── Mini star row ────────────────────────────────────────────────────── */

function MiniStars({ n }: { n: number }) {
  return (
    <span className="flex gap-px">
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} style={{ color: i < Math.round(n) ? "#FFD700" : "var(--border-hover)", fontSize: "0.6rem" }}>★</span>
      ))}
    </span>
  );
}

/* ── Stat cell ────────────────────────────────────────────────────────── */

function Cell({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs" style={{ color: "var(--text-dim)" }}>{label}</span>
      <span className="text-sm font-semibold font-jb" style={{ color: color ?? "var(--text)" }}>
        {value}
      </span>
    </div>
  );
}

/* ── Main ─────────────────────────────────────────────────────────────── */

export default function SwarmPanel() {
  const { mode } = useModeStore();
  const isOffice = mode === "office";
  const { toSol } = useSolRate();

  const { data: stats } = useQuery({
    queryKey: ["swarm-stats"],
    queryFn: getSwarmStats,
    refetchInterval: 5000,
  });

  if (!stats || stats.total_tasks === 0) return null;

  const title = isOffice ? "Economy Dashboard" : "Swarm Intelligence";
  const signedLabel  = isOffice ? "Approved"  : "Signed";
  const blockedLabel = isOffice ? "Rejected"  : "Blocked";
  const peerLabel    = isOffice ? "Internal Transfers" : "Peer Transfers";
  const rankTitle    = isOffice ? "Staff Performance" : "Agent Leaderboard";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2 }}
      className="rounded-2xl p-5 space-y-4"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
      }}
    >
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold tracking-tight">{title}</span>
        <span className="text-xs font-jb px-2 py-0.5 rounded-md"
          style={{ background: "var(--surface-2)", color: "var(--text-muted)", border: "1px solid var(--border)" }}>
          lifetime
        </span>
      </div>

      <div className="flex flex-wrap gap-6 items-center">
        {/* ── Health ring ── */}
        <div className="flex flex-col items-center gap-0.5">
          <HealthRing score={stats.health_score} />
          <span className="text-xs font-jb font-semibold" style={{ color: "var(--text-dim)" }}>
            {isOffice ? "Efficiency" : "Governance Score"}
          </span>
          <span
            className="text-[8px] font-jb text-center"
            style={{ color: "#333", maxWidth: 90, lineHeight: 1.3 }}
          >
            Payment accuracy · Policy compliance · Agent performance
          </span>
        </div>

        {/* ── Core stats ── */}
        <div className="flex flex-wrap gap-5">
          <Cell label="Tasks Run"     value={String(stats.total_tasks)} />
          <Cell label={signedLabel}   value={String(stats.total_signed)}  color="var(--signed)" />
          <Cell label={blockedLabel}  value={String(stats.total_blocked)} color="var(--blocked)" />
          <Cell label="◎ Processed" value={toSol(stats.eth_processed, 4)} color="var(--signed)" />
          <Cell label="◎ Held"      value={toSol(stats.eth_held, 4)}      color="var(--blocked)" />
          <Cell
            label={peerLabel}
            value={`${stats.peer_count} · ${toSol(stats.eth_peer, 4)}`}
            color="#a78bfa"
          />
        </div>

        {/* ── Agent leaderboard ── */}
        <div className="ml-auto space-y-1 min-w-[160px]">
          <p className="text-xs mb-2" style={{ color: "var(--text-dim)" }}>{rankTitle}</p>
          {stats.agent_rankings.map((a, i) => {
            const persona = AGENT_PERSONAS[a.agent_id];
            return (
              <div key={a.agent_id} className="flex items-center gap-2">
                <span className="text-xs font-jb w-4 text-right" style={{ color: "var(--text-dim)" }}>
                  {i + 1}.
                </span>
                <span className="text-xs" style={{ color: persona?.roleColor ?? "var(--text-muted)" }}>
                  {isOffice ? (persona?.name ?? a.agent_id) : `${persona?.flag ?? ""} ${persona?.name ?? a.agent_id}`}
                </span>
                <MiniStars n={a.reputation} />
                <span className="ml-auto text-xs font-jb" style={{ color: "var(--text-muted)" }}>
                  {a.reputation.toFixed(1)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}
