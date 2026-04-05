"use client";

import { useEffect, useState } from "react";
import TaskForm from "@/components/TaskForm";
import Dashboard from "@/components/Dashboard";
import AuditLog from "@/components/AuditLog";
import ModeToggle from "@/components/ModeToggle";
import DryRunBadge from "@/components/DryRunBadge";
import StatusBar from "@/components/StatusBar";
import SwarmPanel from "@/components/SwarmPanel";
import StackDiagram from "@/components/StackDiagram";
import { useSwarmStore } from "@/lib/store";
import { useModeStore } from "@/lib/modeStore";
import { useSolRate } from "@/lib/useSolRate";
import { useQuery } from "@tanstack/react-query";
import { getTaskStatus, type TaskState } from "@/lib/api";
import { motion, AnimatePresence } from "framer-motion";

// ── CSS star field for right panel bg (pure box-shadow, no canvas) ─────────────

const STARS = (() => {
  const shadows: string[] = [];
  for (let i = 0; i < 80; i++) {
    const x = Math.round(Math.abs(Math.sin(i * 7.3) * 2200));
    const y = Math.round(Math.abs(Math.cos(i * 3.7) * 900));
    const a = (0.08 + Math.abs(Math.sin(i * 1.9)) * 0.18).toFixed(2);
    shadows.push(`${x}px ${y}px 0 rgba(255,255,255,${a})`);
  }
  return shadows.join(", ");
})();

// ── Token Ticker ──────────────────────────────────────────────────────────────

function TokenTicker({ taskState }: { taskState: TaskState | undefined }) {
  const { toSol } = useSolRate();

  if (!taskState) return null;
  const { sub_tasks, payments } = taskState;
  const isActive = taskState.task?.status !== "complete" && taskState.task?.status !== "failed";
  if (!isActive) return null;

  const consumed = payments
    .filter(p => p.status === "signed" && !p.policy_reason?.startsWith("PEER:"))
    .reduce((s, p) => s + (p.amount ?? 0), 0);

  const approxTokens = sub_tasks.reduce((s, st) => {
    if (!st.output) return s;
    try { return s + Math.ceil((JSON.parse(st.output)?.text?.length ?? 0) / 4); }
    catch { return s + Math.ceil(st.output.length / 4); }
  }, 0);

  const x402Count = payments.filter(p =>
    p.policy_reason?.includes("x402") || p.policy_reason?.includes("X402")
  ).length;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "6px 14px",
        background: "#050508",
        borderTop: "1px solid #1a1a2e",
        fontFamily: "monospace",
        fontSize: 10,
        flexWrap: "wrap",
      }}
    >
      <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
        <motion.span
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 1.2, repeat: Infinity }}
          style={{ width: 5, height: 5, borderRadius: "50%", background: "#22c55e", display: "inline-block" }}
        />
        <span style={{ color: "#22c55e", letterSpacing: "0.1em" }}>LIVE</span>
      </span>
      <span style={{ color: "#444" }}>·</span>
      <span style={{ color: "#9945FF" }}>{toSol(consumed, 4)} consumed</span>
      {approxTokens > 0 && <>
        <span style={{ color: "#444" }}>·</span>
        <span style={{ color: "#555" }}>~{approxTokens.toLocaleString()} tokens</span>
      </>}
      {x402Count > 0 && <>
        <span style={{ color: "#444" }}>·</span>
        <span style={{ color: "#9945FF" }}>{x402Count} x402 txs on Solana</span>
      </>}
      <span style={{ color: "#444" }}>·</span>
      <span style={{ color: "#333" }}>{sub_tasks.length} agents</span>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Home() {
  const { phase, taskId, reset } = useSwarmStore();
  const { mode } = useModeStore();
  const [showArch, setShowArch] = useState(false);
  const isActive = phase !== "idle";
  const isKingdom = mode === "kingdom";

  useEffect(() => {
    document.body.classList.toggle("office-mode", mode === "office");
  }, [mode]);

  // Task state for token ticker (same query key → deduplicated by TanStack)
  const { data: taskState } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => getTaskStatus(taskId!),
    enabled: !!taskId && isActive,
    refetchInterval: (query) => {
      const s = (query.state.data as TaskState | undefined)?.task?.status;
      return (s === "complete" || s === "failed") ? false : 2000;
    },
  });

  return (
    <div
      style={{
        height: "100vh",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        background: "#080808",
      }}
    >
      {/* ── TOP ACCENT LINE ── */}
      <div className="accent-line" style={{ position: "relative", zIndex: 50 }} />

      {/* ── TOP BAR ── */}
      <header
        style={{
          flexShrink: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 20px",
          borderBottom: "1px solid #1a1a1a",
          background: "#0a0a0f",
          gap: 12,
        }}
      >
        {/* Left: branding */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <h1
                style={{
                  fontSize: 18,
                  fontWeight: 700,
                  letterSpacing: "-0.03em",
                  margin: 0,
                  color: "var(--text)",
                }}
              >
                SwarmPay
              </h1>
              <span
                className="badge"
                style={{
                  background: "var(--accent-deep)",
                  color: "var(--accent-2)",
                  border: "1px solid rgba(108,99,255,0.2)",
                  fontSize: 9,
                  padding: "2px 6px",
                }}
              >
                v2.0 · DEVNET
              </span>
            </div>
          </div>

          {/* Gate indicators (hidden on small screens) */}
          <div
            className="hidden lg:flex"
            style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 10, fontFamily: "monospace" }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--text-dim)" }}>
              <span style={{ color: "var(--signed)", fontSize: 7 }}>●</span> budget gate
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--text-dim)" }}>
              <span style={{ color: "var(--working)", fontSize: 7 }}>●</span> rep gate
            </span>
            <span style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--text-dim)" }}>
              <span style={{ color: "var(--blocked)", fontSize: 7 }}>●</span> FORGE +50% blocked
            </span>
          </div>

          {/* System health dots */}
          <div className="hidden lg:flex" style={{ borderLeft: "1px solid #1a1a1a", paddingLeft: 14 }}>
            <StatusBar />
          </div>
        </div>

        {/* Right: controls */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            onClick={() => setShowArch(true)}
            aria-label="View architecture diagram"
            title="Architecture: system overview, tech stack, and service topology"
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              color: "var(--text-muted)",
              fontSize: 10,
              fontFamily: "monospace",
              letterSpacing: "0.06em",
              padding: "5px 10px",
              borderRadius: 8,
              cursor: "pointer",
            }}
          >
            ARCH
          </button>
          <DryRunBadge />
          <ModeToggle />
          {isActive && (
            <button
              onClick={reset}
              aria-label="Start a new task"
              title="Reset dashboard and start a new task"
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                color: "var(--text-muted)",
                fontSize: 10,
                padding: "5px 10px",
                borderRadius: 8,
                cursor: "pointer",
              }}
            >
              ← New Task
            </button>
          )}
        </div>
      </header>

      {/* ── MAIN SPLIT LAYOUT ── */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* ── LEFT PANEL: Audit Log (35%) ── */}
        <div
          style={{
            width: "35%",
            flexShrink: 0,
            borderRight: "1px solid #141414",
            background: "#080808",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* Wrapper forces AuditLog to fill full panel height */}
          <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
            <div style={{ flex: 1, minHeight: 0 }} className="audit-panel-fill">
              <AuditLog />
            </div>
          </div>
        </div>

        {/* ── RIGHT PANEL: Kingdom (65%) ── */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
            position: "relative",
          }}
        >
          {/* Star field */}
          <div
            style={{
              position: "absolute",
              inset: 0,
              pointerEvents: "none",
              zIndex: 0,
            }}
          >
            <div
              style={{
                position: "absolute",
                width: 1,
                height: 1,
                boxShadow: STARS,
                background: "rgba(255,255,255,0.9)",
                borderRadius: "50%",
              }}
            />
          </div>

          {/* Right panel content */}
          <div
            style={{
              position: "relative",
              zIndex: 1,
              flex: 1,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {/* Kingdom header (when active) */}
            {isActive && (
              <div
                style={{
                  flexShrink: 0,
                  padding: "10px 20px 6px",
                  display: "flex",
                  alignItems: "baseline",
                  justifyContent: "space-between",
                  borderBottom: "1px solid #111",
                }}
              >
                <span
                  style={{
                    fontFamily: "monospace",
                    fontSize: 9,
                    color: isKingdom ? "#F59E0B" : "#60a5fa",
                    letterSpacing: "0.4em",
                    textTransform: "uppercase",
                    fontWeight: 700,
                  }}
                >
                  {isKingdom ? "KINGDOM OF SWARMPAY" : "EXECUTIVE OPERATIONS CENTER"}
                </span>
                {taskState?.task?.description && (
                  <span
                    style={{
                      fontFamily: "monospace",
                      fontSize: 9,
                      color: "#333",
                      letterSpacing: "0.04em",
                      maxWidth: "55%",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                    title={taskState.task.description}
                  >
                    {taskState.task.description}
                  </span>
                )}
              </div>
            )}

            {/* Scrollable main area */}
            <div style={{ flex: 1, overflowY: "auto", padding: isActive ? "16px 20px" : "0" }}>
              <AnimatePresence mode="wait">
                {!isActive ? (
                  <motion.div
                    key="idle"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      minHeight: "100%",
                      padding: "24px",
                    }}
                  >
                    <div style={{ width: "100%", maxWidth: 560 }}>
                      <TaskForm />
                      <div style={{ marginTop: 32 }}>
                        <SwarmPanel />
                      </div>
                    </div>
                  </motion.div>
                ) : (
                  <motion.div
                    key={`active-${mode}`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <Dashboard />
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Token ticker at bottom — active tasks only */}
            <TokenTicker taskState={taskState} />
          </div>
        </div>
      </div>

      {/* Architecture diagram modal */}
      <AnimatePresence>
        {showArch && <StackDiagram onClose={() => setShowArch(false)} />}
      </AnimatePresence>
    </div>
  );
}
