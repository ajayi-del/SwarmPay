"use client";

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { SubTask, Payment } from "@/lib/api";
import {
  AGENT_PERSONAS,
  OFFICE_PERSONAS,
  getStatusDisplay,
  getOfficeStatusDisplay,
} from "@/lib/personas";
import OWSProofPanel from "@/components/OWSProofPanel";
import AgentAvatar from "@/components/AgentAvatar";
import { useModeStore } from "@/lib/modeStore";

/* ── Extended output type ────────────────────────────────────────────── */

interface X402Payment {
  amount: number;
  currency: string;
  network: string;
  endpoint: string;
  txHash: string;
  wallet_id: string;
  nonce: string;
}

interface ParsedOutput {
  text: string;
  english_text?: string;
  lang?: string;
  ms?: number;
  tools?: { name: string; result: string }[];
  sources?: string[];
  code?: string;
  code_output?: string;
  code_execution_ms?: number;
  report_content?: string;
  report_filename?: string;
  key_revoked?: boolean;
  key_revoked_at?: string;
  swept_amount?: number;
  x402_payments?: X402Payment[];
  model?: "claude" | "deepseek";
}

function parseOutput(raw: string): ParsedOutput {
  if (!raw) return { text: "" };
  try {
    const p = JSON.parse(raw);
    return {
      text: p.text ?? raw,
      english_text: p.english_text,
      lang: p.lang,
      ms: p.ms,
      tools: p.tools,
      sources: p.sources,
      code: p.code,
      code_output: p.code_output,
      code_execution_ms: p.code_execution_ms,
      report_content: p.report_content,
      report_filename: p.report_filename,
      key_revoked: p.key_revoked,
      key_revoked_at: p.key_revoked_at,
      swept_amount: p.swept_amount,
      x402_payments: p.x402_payments,
      model: p.model,
    };
  } catch {
    return { text: raw };
  }
}

/* ── Countdown hook ──────────────────────────────────────────────────── */

function useCountdown(createdAt: string, limitSeconds: number, active: boolean): number | null {
  const [remaining, setRemaining] = useState<number | null>(null);
  useEffect(() => {
    if (!active) { setRemaining(null); return; }
    const deadline = new Date(createdAt).getTime() + limitSeconds * 1000;
    const tick = () => setRemaining(Math.floor((deadline - Date.now()) / 1000));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [createdAt, limitSeconds, active]);
  return remaining;
}

function fmtCountdown(s: number): string {
  const clamped = Math.max(0, s);
  return `${Math.floor(clamped / 60)}:${(clamped % 60).toString().padStart(2, "0")}`;
}

/* ── Download helper ─────────────────────────────────────────────────── */

function triggerDownload(content: string, filename: string) {
  const blob = new Blob([content], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

/* ── Collapsible code block ──────────────────────────────────────────── */

function CodeBlock({ code, output, rc }: { code: string; output: string; rc: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 text-xs font-jb w-full text-left"
        style={{ color: "var(--text-dim)" }}
      >
        <motion.span animate={{ rotate: open ? 90 : 0 }} transition={{ duration: 0.2 }} className="inline-block">▶</motion.span>
        <span style={{ color: rc }}>Code Executed</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div
            key="code"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden mt-1.5"
          >
            <pre
              className="text-xs font-jb rounded-lg p-3 overflow-x-auto"
              style={{ background: "#0d0d14", color: "#c9d1d9", border: "1px solid var(--border)" }}
            >
              {code}
            </pre>
            {output && (
              <div className="mt-1 text-xs font-jb px-3 py-2 rounded-lg"
                style={{ background: "var(--surface-2)", color: "#a78bfa", border: "1px solid var(--border)" }}>
                {output}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Stars({ n }: { n: number }) {
  const filled = Math.floor(n);
  const half = n - filled >= 0.5;
  return (
    <span className="flex items-center gap-px text-xs" aria-label={`${n} of 5 stars`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span
          key={i}
          style={{
            color:
              i < filled
                ? "#FFD700"
                : i === filled && half
                ? "#FFD70066"
                : "var(--border-hover)",
          }}
        >★</span>
      ))}
      <span className="ml-1 font-jb" style={{ color: "var(--text-dim)", fontSize: "0.6rem" }}>
        {n.toFixed(1)}
      </span>
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

/* ── Translation toggle ──────────────────────────────────────────────── */

function TranslationToggle({ original, english, lang }: { original: string; english: string; lang: string }) {
  const [showEnglish, setShowEnglish] = useState(false);
  return (
    <div className="space-y-1.5">
      <div className="flex items-center gap-2">
        <button
          onClick={() => setShowEnglish(false)}
          className="text-[9px] px-1.5 py-0.5 rounded font-jb transition-all"
          style={{
            background: !showEnglish ? "rgba(108,99,255,0.2)" : "transparent",
            color: !showEnglish ? "#a78bfa" : "var(--text-dim)",
            border: `1px solid ${!showEnglish ? "rgba(108,99,255,0.35)" : "transparent"}`,
          }}
        >
          {lang || "Original"}
        </button>
        <button
          onClick={() => setShowEnglish(true)}
          className="text-[9px] px-1.5 py-0.5 rounded font-jb transition-all"
          style={{
            background: showEnglish ? "rgba(16,185,129,0.15)" : "transparent",
            color: showEnglish ? "#10b981" : "var(--text-dim)",
            border: `1px solid ${showEnglish ? "rgba(16,185,129,0.3)" : "transparent"}`,
          }}
        >
          EN
        </button>
      </div>
      <AnimatePresence mode="wait">
        <motion.p
          key={showEnglish ? "en" : "orig"}
          initial={{ opacity: 0, y: 2 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="text-xs leading-relaxed"
          style={{ color: "var(--text-muted)" }}
        >
          {showEnglish ? english : original}
        </motion.p>
      </AnimatePresence>
    </div>
  );
}

/* ── Output text block ───────────────────────────────────────────────── */

function OutputTextBlock({ parsed, approxTokens }: { parsed: ParsedOutput; approxTokens: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      className="rounded-lg px-3 py-2.5 space-y-1.5"
      style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
    >
      {parsed.english_text ? (
        <TranslationToggle
          original={parsed.text}
          english={parsed.english_text}
          lang={parsed.lang ?? ""}
        />
      ) : (
        <p className="text-xs leading-relaxed" style={{ color: "var(--text-muted)" }}>
          {parsed.text}
        </p>
      )}
      {/* Sources */}
      {parsed.sources && parsed.sources.length > 0 && (
        <div className="space-y-0.5">
          <span className="text-xs" style={{ color: "var(--text-dim)" }}>Sources:</span>
          {parsed.sources.map((url, i) => (
            <div key={i} className="text-xs font-jb truncate" style={{ color: "#3b82f6" }}>{url}</div>
          ))}
        </div>
      )}
      <div className="flex items-center gap-3 text-xs font-jb flex-wrap" style={{ color: "var(--text-dim)" }}>
        {parsed.ms !== undefined && <span>{parsed.ms}ms</span>}
        {approxTokens > 0 && <span>~{approxTokens} tokens</span>}
        {parsed.code_execution_ms !== undefined && parsed.code_execution_ms > 0 && (
          <span style={{ color: "#a78bfa" }}>E2B: {parsed.code_execution_ms}ms</span>
        )}
        {parsed.model && (
          <span
            className="px-1.5 py-0.5 rounded text-[9px]"
            style={{
              background: parsed.model === "claude" ? "rgba(108,99,255,0.12)" : "rgba(34,197,94,0.10)",
              color: parsed.model === "claude" ? "#a78bfa" : "#22c55e",
              border: `1px solid ${parsed.model === "claude" ? "rgba(108,99,255,0.25)" : "rgba(34,197,94,0.25)"}`,
              letterSpacing: "0.05em",
            }}
          >
            {parsed.model === "claude" ? "Claude Haiku" : "DeepSeek"}
          </span>
        )}
      </div>
    </motion.div>
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

// Spend limit derived from reputation score — mirrors policy_service.py _REP_TIERS
function repLimit(rep: number): number {
  if (rep >= 5.0) return 10.0;
  if (rep >= 4.0) return 2.0;
  if (rep >= 3.0) return 1.0;
  if (rep >= 2.0) return 0.5;
  return 0.0;
}

interface Props {
  subTask: SubTask;
  payment?: Payment;
  peerPayment?: Payment;
  index: number;
  reputation?: number;
}

export default function AgentCard({ subTask, payment, peerPayment, index, reputation }: Props) {
  const { mode } = useModeStore();
  const isOffice = mode === "office";

  const persona = AGENT_PERSONAS[subTask.agent_id];
  const officePers = OFFICE_PERSONAS[subTask.agent_id];
  const liveRep = reputation ?? persona?.reputation ?? 3;
  // parsed is defined below alongside approxTokens

  const terminalStatuses = ["complete", "paid", "blocked", "failed", "timed_out"];
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

  const parsed = parseOutput(subTask.output);
  const approxTokens = parsed.text ? Math.ceil(parsed.text.length / 4) : 0;

  const isLive = subTask.status === "spawned" || subTask.status === "working";
  const countdown = useCountdown(subTask.created, 120, isLive);

  // Mode-specific labels
  const displayRole = isOffice && officePers ? officePers.dept : persona?.role ?? subTask.agent_id;
  const displaySubtitle = isOffice && officePers
    ? `${officePers.title} · ${officePers.clearance}`
    : persona?.language ?? "";
  const displaySkills = isOffice && officePers
    ? officePers.officeSkills
    : persona?.skills ?? ["—", "—", "—"];
  const statusDisplay = isOffice
    ? getOfficeStatusDisplay(subTask.status)
    : getStatusDisplay(subTask.agent_id, subTask.status);

  if (!persona) {
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
      <div className="flex items-start gap-3">
        {/* 3D avatar — shows agent identity and status visually */}
        {!isOffice && (
          <AgentAvatar
            agentName={subTask.agent_id}
            status={subTask.status}
            color={rc}
            size={56}
            isLead={!!subTask.is_lead}
            reputation={liveRep}
          />
        )}

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="flex items-center gap-1.5 mb-0.5">
                <span className="text-base">{isOffice ? "👤" : persona.flag}</span>
                <span className="font-bold tracking-tight text-sm">{persona.name}</span>
                <span style={{ color: "var(--text-dim)" }} className="text-xs">·</span>
                <span className="text-xs font-jb" style={{ color: "var(--text-muted)" }}>
                  {isOffice ? (officePers?.dept ?? persona.city) : persona.city}
                </span>
              </div>
              <p className="text-xs" style={{ color: "var(--text-dim)" }}>
                {displaySubtitle}
              </p>
            </div>
            <span
              className="text-xs px-2 py-0.5 rounded-md font-semibold shrink-0"
              style={{ background: `${rc}18`, color: rc, border: `1px solid ${rc}30` }}
            >
              {displayRole}
            </span>
          </div>
        </div>
      </div>

      {/* ── Stars + stats + sparkline ── */}
      <div className="flex items-center gap-3 flex-wrap">
        <Stars n={liveRep} />
        <span className="text-xs font-jb" style={{ color: "var(--text-muted)" }}>
          {isOffice ? `CLR: ${officePers?.clearance ?? "LEVEL ?"}` : `T:${persona.stats.tasks} · ${persona.stats.successRate}%`}
        </span>
        <Sparkline data={persona.stats.sparkline} color={rc} />
        {!isOffice && (
          <span className="text-xs font-jb" style={{ color: "var(--text-dim)" }}>
            {persona.stats.avgSpeed}s avg
          </span>
        )}
      </div>

      {/* ── Skills (unlock on terminal) ── */}
      <div className="flex flex-wrap gap-1.5">
        <AnimatePresence>
          {displaySkills.slice(0, visibleSkillCount).map((skill, i) => (
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
                <span className="ml-1 text-xs" style={{ color: rc }}>{isOffice ? "✓" : "★"}</span>
              )}
            </motion.span>
          ))}
        </AnimatePresence>
      </div>

      {/* ── Status ── */}
      <div>
        {isOffice ? (
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold font-jb tracking-wide ${
              statusDisplay.animate === "pulse" ? "animate-status-pulse" : ""
            }`}
            style={{
              background: `${statusDisplay.color}18`,
              color: statusDisplay.color,
              border: `1px solid ${statusDisplay.color}33`,
            }}
          >
            <span className="w-1.5 h-1.5 rounded-full"
              style={{ background: statusDisplay.color, boxShadow: `0 0 4px ${statusDisplay.color}` }} />
            {statusDisplay.label}
          </span>
        ) : (
          <StatusPill agentName={persona.name} status={subTask.status} />
        )}
      </div>

      {/* ── Countdown timer ── */}
      {isLive && countdown !== null && (
        <div className="flex items-center gap-1.5 text-xs font-jb"
          style={{ color: countdown <= 30 ? "#ef4444" : "var(--text-dim)" }}>
          <span>⏱</span>
          <span>{fmtCountdown(countdown)} remaining</span>
          {countdown <= 30 && (
            <span className="animate-status-pulse" style={{ color: "#ef4444" }}>· DMS ARMED</span>
          )}
        </div>
      )}

      {/* ── Output area ── */}
      {parsed.text && (
        <OutputTextBlock parsed={parsed} approxTokens={approxTokens} />
      )}

      {/* ── Tools used ── */}
      {parsed.tools && parsed.tools.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs" style={{ color: "var(--text-dim)" }}>🔧 Tools Used</p>
          {parsed.tools.map((tool, i) => (
            <div key={i} className="flex gap-2 text-xs font-jb rounded px-2 py-1"
              style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}>
              <span className="shrink-0" style={{ color: "#a78bfa" }}>{tool.name}</span>
              <span className="truncate" style={{ color: "var(--text-muted)" }}>{tool.result}</span>
            </div>
          ))}
        </div>
      )}

      {/* ── CIPHER — collapsible code block ── */}
      {parsed.code && parsed.code.trim() && (
        <CodeBlock code={parsed.code} output={parsed.code_output ?? ""} rc={rc} />
      )}

      {/* ── FORGE — download report ── */}
      {parsed.report_content && parsed.report_filename && (
        <button
          onClick={() => triggerDownload(parsed.report_content!, parsed.report_filename!)}
          className="flex items-center gap-2 text-xs font-jb px-3 py-1.5 rounded-lg w-full text-left"
          style={{
            background: `${rc}10`,
            border: `1px solid ${rc}30`,
            color: rc,
          }}
        >
          <span>📄</span>
          <span>Download Report</span>
          <span className="ml-auto" style={{ color: "var(--text-dim)" }}>{parsed.report_filename}</span>
        </button>
      )}

      {/* ── x402 micropayments ── */}
      {parsed.x402_payments && parsed.x402_payments.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs" style={{ color: "var(--text-dim)" }}>⚡ x402 Payments</p>
          {parsed.x402_payments.map((xp, i) => (
            <div
              key={i}
              className="text-xs font-jb rounded px-2 py-1.5 space-y-1"
              style={{ background: "#051218", border: "1px solid #06b6d433" }}
            >
              <div className="flex items-center gap-2">
                <span style={{ color: "#06b6d4" }}>◎ Solana devnet</span>
                <span className="ml-auto font-bold" style={{ color: "#06b6d4" }}>
                  {xp.amount} {xp.currency}
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <span style={{ color: "#555" }}>tx</span>
                <span className="truncate flex-1" style={{ color: "#6b7280" }}>
                  {xp.txHash.slice(0, 28)}…
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span style={{ color: "#444" }}>{xp.endpoint}</span>
                {(xp as unknown as { explorer_url?: string; on_chain?: boolean }).on_chain &&
                 (xp as unknown as { explorer_url?: string }).explorer_url && (
                  <a
                    href={(xp as unknown as { explorer_url: string }).explorer_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-[10px] font-semibold underline"
                    style={{ color: "#06b6d4" }}
                  >
                    Settled on Solana devnet ◎ →
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Email draft (ATLAS + BISHOP) ── */}
      {(parsed as unknown as { email_summary?: { subject: string; body: string; to: string } }).email_summary && (() => {
        const em = (parsed as unknown as { email_summary: { subject: string; body: string; to: string } }).email_summary;
        return (
          <details className="mt-2">
            <summary
              className="text-[10px] cursor-pointer select-none font-semibold"
              style={{ color: "#a78bfa" }}
            >
              Email Draft
            </summary>
            <div
              className="mt-1 rounded-md p-2 text-[10px] font-jb whitespace-pre-wrap"
              style={{ background: "#a78bfa10", color: "var(--text-muted)", border: "1px solid #a78bfa25" }}
            >
              <div style={{ color: "#a78bfa88" }}>To: {em.to}</div>
              <div style={{ color: "#a78bfa88" }} className="mb-1">Subject: {em.subject}</div>
              {em.body}
            </div>
          </details>
        );
      })()}

      {/* ── Footer: budget + rep limit + wallet ── */}
      <div
        className="flex items-center justify-between text-xs font-jb pt-1 border-t"
        style={{ borderColor: "var(--border)", color: "var(--text-dim)" }}
      >
        <span className="flex gap-2">
          <span>
            Alloc:{" "}
            <span style={{ color: "var(--text-muted)" }}>
              {Number(subTask.budget_allocated).toFixed(4)}
            </span>
          </span>
          <span style={{ color: "var(--border-hover)" }}>·</span>
          <span>
            Limit:{" "}
            <span style={{ color: rc }}>
              ${repLimit(liveRep).toFixed(2)}
            </span>
          </span>
        </span>
        <span className="truncate ml-2">
          {subTask.wallet_id ? `${subTask.wallet_id.slice(0, 6)}…${subTask.wallet_id.slice(-4)}` : "—"}
        </span>
      </div>

      {/* ── Peer payment received badge ── */}
      {peerPayment && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex items-center gap-2 rounded-lg px-3 py-1.5"
          style={{
            background: "rgba(167,139,250,0.08)",
            border: "1px solid rgba(167,139,250,0.25)",
          }}
        >
          <span style={{ color: "#a78bfa", fontSize: "0.65rem" }}>⇄ PEER IN</span>
          <span className="text-xs font-jb" style={{ color: "#a78bfa" }}>
            {Number(peerPayment.amount).toFixed(3)} USDC
          </span>
          <span className="text-xs" style={{ color: "var(--text-dim)" }}>
            {peerPayment.policy_reason?.replace("PEER: ", "") ?? ""}
          </span>
        </motion.div>
      )}

      {/* ── OWS Proof Panel ── */}
      {isTerminal && (
        <OWSProofPanel subTask={subTask} payment={payment} />
      )}

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
              {payment.status === "signed"
                ? isOffice ? "✓ APPROVED TRANSFER" : "✓ SIGNED"
                : isOffice ? "✗ COMPLIANCE REJECTED" : "✗ BLOCKED"}
            </span>
            <span style={{ color: "var(--text)" }}>{Number(payment.amount).toFixed(4)} USDC</span>
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
