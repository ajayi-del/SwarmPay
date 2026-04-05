"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import type { Wallet, Task } from "@/lib/api";
import { getMeteoraRate, getMoonpayOnramp } from "@/lib/api";
import { COORDINATOR_PERSONA, OFFICE_COORDINATOR } from "@/lib/personas";
import { useModeStore } from "@/lib/modeStore";
import { useSolRate } from "@/lib/useSolRate";

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
  const { mode } = useModeStore();
  const isOffice = mode === "office";
  const { toSol, rate: solRate } = useSolRate();
  const [meteoraRate, setMeteoraRate] = useState<number | null>(null);
  const [meteoraSource, setMeteoraSource] = useState<string>("");
  const [moonpayUrl, setMoonpayUrl] = useState<string | null>(null);

  useEffect(() => {
    if (task.status === "complete") {
      getMeteoraRate()
        .then((d) => { if (d.available && d.rate) { setMeteoraRate(d.rate); setMeteoraSource(d.source); } })
        .catch(() => {});
    }
  }, [task.status]);

  useEffect(() => {
    if (wallet.sol_address) {
      getMoonpayOnramp(wallet.sol_address)
        .then((d) => { if (d.url) setMoonpayUrl(d.url); })
        .catch(() => {});
    }
  }, [wallet.sol_address]);
  const p = COORDINATOR_PERSONA;
  const statusColor = TASK_STATUS_COLOR[task.status] ?? "#888";

  const accentColor = isOffice ? "#60a5fa" : "#FFD700";
  const roleLabel = isOffice ? OFFICE_COORDINATOR.title : p.role;
  const locationLabel = isOffice
    ? `${OFFICE_COORDINATOR.dept} · ${OFFICE_COORDINATOR.clearance}`
    : `${p.city} · ${p.language}`;
  const treasuryLabel = isOffice ? "Operating Budget" : "Royal Vault";
  const statusLabel = isOffice ? "OVERSEEING" : "MANAGING";
  const taskPrefix = isOffice ? "Mandate:" : "Task:";

  return (
    <motion.div
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl p-5"
      style={{
        background: "var(--surface)",
        border: isOffice ? "1px solid #2563eb22" : "1px solid #2a2400",
        boxShadow: isOffice
          ? "0 0 32px rgba(37,99,235,0.04)"
          : "0 0 32px rgba(255,215,0,0.04)",
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        {/* Identity */}
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-xl">{isOffice ? "🏛️" : p.flag}</span>
            <span className="text-xl font-bold tracking-tight">{p.name}</span>
            <span
              className="text-xs px-2.5 py-0.5 rounded-md font-semibold"
              style={{
                background: `${accentColor}18`,
                color: accentColor,
                border: `1px solid ${accentColor}35`,
              }}
            >
              {roleLabel}
            </span>
          </div>
          <p className="text-xs font-jb" style={{ color: "var(--text-muted)" }}>
            {locationLabel}
          </p>
        </div>

        {/* Task status */}
        <div className="flex items-center gap-2">
          <span
            className="text-xs px-3 py-1 rounded-full font-semibold font-jb animate-status-pulse"
            style={{
              background: `${statusColor}18`,
              color: statusColor,
              border: `1px solid ${statusColor}30`,
            }}
          >
            <span
              className="inline-block w-1.5 h-1.5 rounded-full mr-1.5 align-middle"
              style={{ background: statusColor, boxShadow: `0 0 4px ${statusColor}` }}
            />
            {statusLabel}
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
              style={{
                background: `${accentColor}12`,
                color: accentColor,
                border: `1px solid ${accentColor}30`,
              }}
            >
              {skill}
            </span>
          ))}
        </div>

        {/* Treasury / Budget */}
        <div className="ml-auto text-right space-y-0.5">
          <p className="text-xs" style={{ color: "var(--text-muted)" }}>{treasuryLabel}</p>
          <p className="text-2xl font-bold font-jb" style={{ color: "#9945FF" }}>
            {toSol(Number(wallet.budget_cap), 3)}
          </p>
          <p className="text-xs font-jb" style={{ color: "var(--text-dim)" }}>
            {Number(wallet.budget_cap).toFixed(2)} USDC · Est. APR ~8.4%
          </p>
          <p className="text-xs font-jb truncate max-w-[200px]" style={{ color: "var(--text-dim)" }}>
            {wallet.eth_address.slice(0, 10)}…{wallet.eth_address.slice(-6)}
          </p>
          {(meteoraRate ?? solRate) > 0 && (
            <p className="text-[10px] font-jb mt-0.5" style={{ color: "#555" }}>
              1 SOL = {(meteoraRate ?? solRate).toFixed(2)} USDC · {meteoraSource || "CoinGecko"}
            </p>
          )}
          {moonpayUrl && (
            <a
              href={moonpayUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block mt-2 text-xs px-2.5 py-1 rounded-md font-semibold"
              style={{
                background: "#7c3aed18",
                color: "#a78bfa",
                border: "1px solid #7c3aed35",
                textDecoration: "none",
              }}
            >
              + Top Up via Moonpay
            </a>
          )}
        </div>
      </div>

      {/* Task description */}
      <div className="mt-3 pt-3 border-t" style={{ borderColor: "var(--border)" }}>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          <span style={{ color: "var(--text-dim)" }}>{taskPrefix} </span>
          {task.description}
        </p>
      </div>
    </motion.div>
  );
}
