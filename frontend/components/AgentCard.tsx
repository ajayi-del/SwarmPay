"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { SubTask, Payment } from "@/lib/api";
import { AGENT_PERSONAS, getStatusDisplay } from "@/lib/personas";

/* ── Helpers ─────────────────────────────────────────────────────────── */

function parseOutput(raw: string): { text: string; ms?: number } {
  if (!raw) return { text: "" };
  try {
    const p = JSON.parse(raw);
    return { text: p.text ?? raw, ms: p.ms };
  } catch {
    return { text: raw };
  }
}

function Stars({ n }: { n: number }) {
  return (
    <span className="flex gap-px text-xs" aria-label={`${n} of 5 stars`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span key={i} style={{ color: i < n ? "#FFD700" : "var(--border-hover)" }}>★</span>
      ))}
    </span>
  );
}

function Sparkline({ data, color }: { data: number[]; color: string }) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const W = 56;
  const H = 18;
  const pts = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * W;
      const y = H - ((v - min) / range) * H * 0.75 - H * 0.1;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="opacity-70">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={pts}
      />
    </svg>
  );
}

/* ── Status pill ─────────────────────────────────────────────────────── */

function StatusPill({ agentName, status }: { agentName: string; status: string }) {
  const { label, color, animate } = getStatusDisplay(agentName, status);
  const cls =
    animate === "pulse"
      ? "animate-status-pulse"
      : animate === "blink"
      ? "animate-status-blink"
      : "";
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-jb tracking-wide ${cls}`}
      style={{ background: `${color}18`, color, border: `1px solid ${color}33` }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: color, boxShadow: `0 0 4px ${color}` }}
      />
      {label}
    </span>
  );
}

/* ── Main card ───────────────────────────────────────────────────────── */

interface Props {
  subTask: SubTask;
  payment?: Payment;
  index: number;
}

export default function AgentCard({ subTask, payment, index }: Props) {
  const persona = AGENT_PERSONAS[subTask.agent_id];
  const { text: outputText, ms: latencyMs } = parseOutput(subTask.output);

  // Skill visibility: all 3 show by terminal states, 3rd unlocks on complete/paid/blocked
  const terminalStatuses = ["complete", "paid", "blocked", "failed"];
  const isTerminal = terminalStatuses.includes(subTask.status);
  const visibleSkillCount = subTask.status === "spawned" ? 2 : isTerminal ? 3 : 2;

  const rc = persona?.roleColor ?? "#6c63ff";
  const isBlocked = subTask.status === "blocked";
  const isPaid = subTask.status === "paid";

  const borderColor = isBlocked
    ? "rgba(239,68,68,0.3)"
    : isPaid
    ? "rgba(34,197,94,0.2)"
    : "var(--border)";

  const approxTokens = outputText ? Math.ceil(outputText.length / 4) : 0;

  if (!persona) {
    // Graceful fallback for unknown agent names
    return (
      <div className="rounded-2xl p-4" style={{ background: "var(--surface)", border: "1px solid var(--border)" }}>
        <p className="font-jb text-xs" style={{ color: "var(--text-muted)" }}>{subTask.agent_id}</p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.06 }}
      className="rounded-2xl p-4 flex flex-col gap-3"
      style={{
        background: "var(--surface)",
        border: `1px solid ${borderColor}`,
        boxShadow: isBlocked
          ? "0 0 20px rgba(239,68,68,0.06)"
          : isPaid
          ? "0 0 20px rgba(34,197,94,0.05)"
          : "none",
      }}
    >
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className="text-base">{persona.flag}</span>
            <span className="font-bold tracking-tight text-sm">{persona.name}</span>
            <span style={{ color: "var(--text-dim)" }} className="text-xs">·</span>
            <span className="text-xs font-jb" style={{ color: "var(--text-muted)" }}>
              {persona.city}
            </span>
          </div>
          <p className="text-xs" style={{ color: "var(--text-dim)" }}>
            {persona.language}
          </p>
        </div>
        <span
          className="text-xs px-2 py-0.5 rounded-md font-semibold shrink-0"
          style={{ background: `${rc}18`, color: rc, border: `1px solid ${rc}30` }}
        >
          {persona.role}
        </span>
      </div>

      {/* ── Stars + stats + sparkline ── */}
      <div className="flex items-center gap-3 flex-wrap">
        <Stars n={persona.reputation} />
        <span className="text-xs font-jb" style={{ color: "var(--text-muted)" }}>
          T:{persona.stats.tasks} · {persona.stats.successRate}%
        </span>
        <Sparkline data={persona.stats.sparkline} color={rc} />
        <span className="text-xs font-jb" style={{ color: "var(--text-dim)" }}>
          {persona.stats.avgSpeed}s avg
        </span>
      </div>

      {/* ── Skills (unlock on terminal) ── */}
      <div className="flex flex-wrap gap-1.5">
        <AnimatePresence>
          {persona.skills.slice(0, visibleSkillCount).map((skill, i) => (
            <motion.span
              key={skill}
              initial={{ opacity: 0, scale: 0.7 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.08, type: "spring", stiffness: 400, damping: 20 }}
              className="text-xs px-2 py-0.5 rounded-md font-jb"
              style={{
                background: i === 2 && isTerminal ? `${rc}22` : "var(--surface-2)",
                color: i === 2 && isTerminal ? rc : "var(--text-muted)",
                border: `1px solid ${i === 2 && isTerminal ? `${rc}40` : "var(--border)"}`,
              }}
            >
              {skill}
              {i === 2 && isTerminal && (
                <span className="ml-1 text-xs" style={{ color: rc }}>★</span>
              )}
            </motion.span>
          ))}
        </AnimatePresence>
      </div>

      {/* ── Status ── */}
      <div>
        <StatusPill agentName={persona.name} status={subTask.status} />
      </div>

      {/* ── Output area ── */}
      {outputText && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          className="rounded-lg px-3 py-2.5 space-y-1.5"
          style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
        >
          <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
            {outputText}
          </p>
          <div className="flex gap-3 text-xs font-jb" style={{ color: "var(--text-dim)" }}>
            {latencyMs !== undefined && <span>{latencyMs}ms</span>}
            {approxTokens > 0 && <span>~{approxTokens} tokens</span>}
          </div>
        </motion.div>
      )}

      {/* ── Footer: budget + wallet ── */}
      <div
        className="flex items-center justify-between text-xs font-jb pt-1 border-t"
        style={{ borderColor: "var(--border)", color: "var(--text-dim)" }}
      >
        <span>
          Budget:{" "}
          <span style={{ color: "var(--text-muted)" }}>
            {Number(subTask.budget_allocated).toFixed(4)} ETH
          </span>
        </span>
        <span className="truncate ml-2">
          {subTask.wallet_id ? `${subTask.wallet_id.slice(0, 6)}…${subTask.wallet_id.slice(-4)}` : "—"}
        </span>
      </div>

      {/* ── Payment overlay ── */}
      {payment && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="rounded-lg px-3 py-2 space-y-1"
          style={{
            background: payment.status === "signed" ? "rgba(34,197,94,0.06)" : "rgba(239,68,68,0.07)",
            border: `1px solid ${payment.status === "signed" ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.25)"}`,
          }}
        >
          <div className="flex items-center justify-between text-xs font-jb">
            <span
              style={{ color: payment.status === "signed" ? "var(--signed)" : "var(--blocked)" }}
            >
              {payment.status === "signed" ? "✓ SIGNED" : "✗ BLOCKED"}
            </span>
            <span style={{ color: "var(--text)" }}>{Number(payment.amount).toFixed(4)} ETH</span>
          </div>
          {payment.policy_reason && (
            <p className="text-xs" style={{ color: "var(--blocked)", opacity: 0.85 }}>
              {payment.policy_reason}
            </p>
          )}
          {payment.tx_hash && (
            <p className="text-xs font-jb truncate" style={{ color: "var(--text-dim)" }}>
              tx: {payment.tx_hash.slice(0, 28)}…
            </p>
          )}
        </motion.div>
      )}
    </motion.div>
  );
}
