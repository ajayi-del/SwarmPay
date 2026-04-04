"use client";

import { motion } from "framer-motion";
import type { Wallet, Task } from "@/lib/api";
import { COORDINATOR_PERSONA } from "@/lib/personas";

function Stars({ n }: { n: number }) {
  return (
    <span className="flex gap-px text-xs">
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} style={{ color: i < n ? "#FFD700" : "var(--border-hover)" }}>★</span>
      ))}
    </span>
  );
}

function Sparkline({ data }: { data: number[] }) {
  const color = "#FFD700";
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const W = 72, H = 18;
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * W;
      const y = H - ((v - min) / range) * H * 0.75 - H * 0.1;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="opacity-60">
      <polyline fill="none" stroke={color} strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round" points={pts} />
    </svg>
  );
}

interface Props {
  wallet: Wallet;
  task: Task;
}

const TASK_STATUS_COLOR: Record<string, string> = {
  pending: "#6c63ff",
  decomposed: "#3b82f6",
  in_progress: "#f59e0b",
  complete: "#22c55e",
  failed: "#ef4444",
};

export default function CoordinatorCard({ wallet, task }: Props) {
  const p = COORDINATOR_PERSONA;
  const statusColor = TASK_STATUS_COLOR[task.status] ?? "#888";

  return (
    <motion.div
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl p-5"
      style={{
        background: "var(--surface)",
        border: "1px solid #2a2400",
        boxShadow: "0 0 32px rgba(255,215,0,0.04)",
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        {/* Identity */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xl">{p.flag}</span>
            <span className="text-xl font-bold tracking-tight">{p.name}</span>
            <span
              className="text-xs px-2.5 py-0.5 rounded-md font-semibold"
              style={{ background: "#FFD70018", color: "#FFD700", border: "1px solid #FFD70035" }}
            >
              {p.role}
            </span>
          </div>
          <p className="text-xs font-jb" style={{ color: "var(--text-muted)" }}>
            {p.city} · {p.language}
          </p>
        </div>

        {/* Task status */}
        <div className="flex items-center gap-2">
          <span
            className="text-xs px-3 py-1 rounded-full font-semibold font-jb animate-status-pulse"
            style={{ background: `${statusColor}18`, color: statusColor, border: `1px solid ${statusColor}30` }}
          >
            <span className="inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle"
              style={{ background: statusColor, boxShadow: `0 0 4px ${statusColor}` }} />
            MANAGING
          </span>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-6 items-end">
        {/* Stats */}
        <div className="space-y-2">
          <Stars n={p.reputation} />
          <div className="flex gap-4 text-xs font-jb" style={{ color: "var(--text-muted)" }}>
            <span>Tasks: <strong style={{ color: "var(--text)" }}>{p.stats.tasks}</strong></span>
            <span>Success: <strong style={{ color: "var(--text)" }}>{p.stats.successRate}%</strong></span>
            <span>Avg: <strong style={{ color: "var(--text)" }}>{p.stats.avgSpeed}s</strong></span>
          </div>
          <Sparkline data={p.stats.sparkline} />
        </div>

        {/* Skills */}
        <div className="flex gap-2 flex-wrap">
          {p.skills.map((skill) => (
            <span
              key={skill}
              className="text-xs px-2 py-0.5 rounded-md font-jb"
              style={{ background: "#FFD70012", color: "#FFD700", border: "1px solid #FFD70030" }}
            >
              {skill}
            </span>
          ))}
        </div>

        {/* Treasury */}
        <div className="ml-auto text-right space-y-0.5">
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>Treasury</p>
          <p className="text-2xl font-bold font-jb" style={{ color: "#FFD700" }}>
            {wallet.budget_cap.toFixed(2)}{" "}
            <span className="text-sm font-normal" style={{ color: "var(--text-muted)" }}>ETH</span>
          </p>
          <p className="text-xs font-jb truncate max-w-[200px]" style={{ color: "var(--text-dim)" }}>
            {wallet.eth_address.slice(0, 10)}…{wallet.eth_address.slice(-6)}
          </p>
        </div>
      </div>

      {/* Task description */}
      <div className="mt-3 pt-3 border-t" style={{ borderColor: "var(--border)" }}>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          <span style={{ color: "var(--text-dim)" }}>Task: </span>
          {task.description}
        </p>
      </div>
    </motion.div>
  );
}
