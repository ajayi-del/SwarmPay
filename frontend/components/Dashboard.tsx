"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTaskStatus, type TaskState } from "@/lib/api";
import { useSwarmStore } from "@/lib/store";
import { useModeStore } from "@/lib/modeStore";
import { motion } from "framer-motion";
import AgentCard from "./AgentCard";
import SleepingAgentCard from "./SleepingAgentCard";
import CoordinatorCard from "./CoordinatorCard";
import RegisRow from "./RegisRow";
import RegisConsole from "./RegisConsole";
import SkillsCompact from "./SkillsCompact";
import SwarmOrbit from "./SwarmOrbit";
import X402Panel from "./X402Panel";
import TelegramPanel from "./TelegramPanel";
import SovereigntyPanel from "./SovereigntyPanel";
import SwarmPanel from "./SwarmPanel";
import GovernanceLayer from "./GovernanceLayer";
import { ErrorBoundary } from "./ErrorBoundary";

// Active statuses — these agents are always expanded
const ACTIVE_STATUSES = new Set(["spawned", "working"]);
const ALL_AGENTS = ["ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"];

/* ── Spawn animation — shown immediately after "Launch Swarm" while backend responds ── */
function SpawnLoader() {
  const labels = [
    "Initialising OWS wallet custody…",
    "Spawning agent constellation…",
    "Allocating SOL budgets…",
    "Establishing x402 payment rail…",
    "REGIS preparing throne room…",
  ];
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIdx((i) => (i + 1) % labels.length), 900);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="w-full space-y-4">
      {/* Governance layer — visible immediately */}
      <ErrorBoundary>
        <GovernanceLayer taskState={null} />
      </ErrorBoundary>

      {/* Throne room skeleton */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "160px 1fr 260px",
          gap: 12,
          alignItems: "stretch",
          minHeight: 200,
        }}
      >
        {/* Left skeleton */}
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12 }} />

        {/* Center — REGIS awakening */}
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid #2a1f00",
            borderRadius: 12,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 16,
            padding: 24,
          }}
        >
          {/* REGIS crown pulsing */}
          <motion.div
            animate={{ scale: [1, 1.06, 1], opacity: [0.7, 1, 0.7] }}
            transition={{ duration: 1.6, repeat: Infinity }}
            style={{ fontSize: 36 }}
          >
            👑
          </motion.div>
          <div style={{ fontFamily: "monospace", fontSize: 14, color: "#F59E0B", fontWeight: 700, letterSpacing: "0.1em" }}>
            REGIS
          </div>
          <div style={{ fontFamily: "monospace", fontSize: 9, color: "#555", letterSpacing: "0.15em" }}>
            SOVEREIGN BRAIN
          </div>
          {/* Animated status line */}
          <motion.div
            key={idx}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            style={{ fontFamily: "monospace", fontSize: 9, color: "#444", letterSpacing: "0.06em", textAlign: "center" }}
          >
            {labels[idx]}
          </motion.div>
          {/* Spinner */}
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "linear" }}
            style={{
              width: 20, height: 20,
              border: "2px solid #1a1a00",
              borderTop: "2px solid #F59E0B",
              borderRadius: "50%",
            }}
          />
        </div>

        {/* Right — orbit skeleton: 5 ghost dots */}
        <div
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: 12,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <svg width="200" height="180" viewBox="0 0 200 180">
            <circle cx={100} cy={90} r={70} fill="none" stroke="#ffffff06" strokeWidth="1" strokeDasharray="4 6" />
            <circle cx={100} cy={90} r={22} fill="#110e00" stroke="#F59E0B" strokeWidth="2" />
            <text x={100} y={94} textAnchor="middle" fontSize={8} fill="#F59E0B" fontFamily="monospace" fontWeight="bold">REGIS</text>
            {ALL_AGENTS.map((name, i) => {
              const a = (i / ALL_AGENTS.length) * Math.PI * 2 - Math.PI / 2;
              const x = 100 + Math.cos(a) * 70;
              const y = 90 + Math.sin(a) * 70;
              return (
                <g key={name}>
                  <motion.circle
                    cx={x} cy={y} r={10}
                    fill="#1a1a2e"
                    stroke="#333"
                    strokeWidth="1.5"
                    animate={{ opacity: [0.3, 0.7, 0.3] }}
                    transition={{ duration: 1.5 + i * 0.3, repeat: Infinity }}
                  />
                  <text x={x} y={y + 3} textAnchor="middle" fontSize={6} fill="#555" fontFamily="monospace">
                    {name.slice(0, 2)}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      {/* Ghost agent cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {ALL_AGENTS.map((agentId) => (
          <ErrorBoundary key={`ghost-${agentId}`}>
            <SleepingAgentCard agentId={agentId} />
          </ErrorBoundary>
        ))}
      </div>

      {/* Sovereignty panel still renders (uses its own data fetch) */}
      <ErrorBoundary>
        <SovereigntyPanel />
      </ErrorBoundary>
    </div>
  );
}

/* ── Main Dashboard ──────────────────────────────────────────────────── */

export default function Dashboard() {
  const { taskId, setPhase } = useSwarmStore();
  const { mode } = useModeStore();
  const isKingdom = mode === "kingdom";

  // Track which terminal agents the user has manually expanded
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const { data: taskState } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => getTaskStatus(taskId!),
    enabled: !!taskId,
    refetchInterval: (query) => {
      const status = (query.state.data as TaskState | undefined)?.task?.status;
      if (status === "complete" || status === "failed") return false;
      return 1200;
    },
  });

  useEffect(() => {
    const status = taskState?.task?.status;
    if (status === "complete" || status === "failed") {
      setPhase("done");
    }
  }, [taskState?.task?.status, setPhase]);

  // Auto-collapse newly-terminal agents (reset when task changes)
  useEffect(() => {
    setExpandedIds(new Set());
  }, [taskId]);

  // ── KEY FIX: show spawn animation while waiting for backend response ──
  // Previously returned null here, which caused blank right panel.
  if (!taskId || !taskState) {
    return taskId ? <SpawnLoader /> : null;
  }

  const { task, coordinator_wallet, sub_tasks, payments, reputations = {}, x402_calls = [] } = taskState;

  const activeAgentIds = new Set(sub_tasks.map((st) => st.agent_id));
  const sleepingAgents = ALL_AGENTS.filter((a) => !activeAgentIds.has(a));

  function toggleExpanded(id: string) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // ── Performance flags for collapsed agent cards ──
  const signedByAgent: Record<string, number> = {};
  payments
    .filter((p) => p.status === "signed" && !p.policy_reason?.startsWith("PEER:"))
    .forEach((p) => {
      const st = sub_tasks.find((s) => s.wallet_id === p.to_wallet_id);
      if (st) signedByAgent[st.agent_id] = (signedByAgent[st.agent_id] ?? 0) + Number(p.amount);
    });
  const topEarnerAgent = Object.entries(signedByAgent).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
  const terminalTasks = sub_tasks.filter((s) => ["paid", "complete"].includes(s.status));
  const lastCompletedAgent = terminalTasks.length > 0
    ? terminalTasks[terminalTasks.length - 1].agent_id
    : null;

  return (
    <div className="w-full space-y-4">
      {/* ── 0. GOVERNANCE LAYER — always visible when task is running ── */}
      <ErrorBoundary>
        <GovernanceLayer taskState={taskState} />
      </ErrorBoundary>

      {/* ── 1. THRONE ROOM — Skills | REGIS | Orbit ── */}
      {coordinator_wallet && (
        <ErrorBoundary>
          {isKingdom ? (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "160px 1fr 260px",
                gap: 12,
                alignItems: "stretch",
              }}
            >
              {/* LEFT COURT — Skills Registry (collapsible) */}
              <SkillsCompact />

              {/* CENTER — REGIS Throne */}
              <div style={{ display: "flex", justifyContent: "center" }}>
                <RegisRow
                  wallet={coordinator_wallet}
                  task={task}
                  subTasks={sub_tasks}
                  payments={payments}
                />
              </div>

              {/* RIGHT COURT — Agent Orbit (full size) */}
              {sub_tasks.length > 0 ? (
                <SwarmOrbit
                  subTasks={sub_tasks}
                  payments={payments}
                  taskStatus={task.status}
                />
              ) : (
                <div
                  style={{
                    background: "var(--surface)",
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <span style={{ fontFamily: "monospace", fontSize: 8, color: "#333", letterSpacing: "0.1em" }}>
                    NO AGENTS
                  </span>
                </div>
              )}
            </div>
          ) : (
            <CoordinatorCard wallet={coordinator_wallet} task={task} />
          )}
          <RegisConsole coordinatorWalletId={coordinator_wallet.id} />
        </ErrorBoundary>
      )}

      {/* ── 2. Agent grid (the workers) ── */}
      {sub_tasks.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {sub_tasks.map((st, i) => {
            const payment = payments.find(
              (p) => p.to_wallet_id === st.wallet_id && !p.policy_reason?.startsWith("PEER:")
            );
            const peerPayment = payments.find(
              (p) => p.to_wallet_id === st.wallet_id && p.policy_reason?.startsWith("PEER:")
            );

            const isTerminal = !ACTIVE_STATUSES.has(st.status);
            const isCollapsed = isTerminal && !expandedIds.has(st.id);

            return (
              <ErrorBoundary key={st.id}>
                <AgentCard
                  subTask={st}
                  payment={payment}
                  peerPayment={peerPayment}
                  index={i}
                  reputation={reputations[st.agent_id]}
                  collapsed={isCollapsed}
                  onToggleCollapse={() => toggleExpanded(st.id)}
                  flags={{
                    topEarner: st.agent_id === topEarnerAgent,
                    lastCompleted: st.agent_id === lastCompletedAgent,
                    lowRepWarning: st.agent_id === "FORGE" && (reputations["FORGE"] ?? 4) < 3.5,
                  }}
                />
              </ErrorBoundary>
            );
          })}

          {/* Sleeping agents (not selected for this task) */}
          {sleepingAgents.map((agentId) => (
            <ErrorBoundary key={`sleep-${agentId}`}>
              <SleepingAgentCard agentId={agentId} />
            </ErrorBoundary>
          ))}
        </div>
      )}

      {/* ── 3. Sovereignty race ── */}
      <ErrorBoundary>
        <SovereigntyPanel />
      </ErrorBoundary>

      {/* ── 4. x402 Payment Rail (proof of Solana) ── */}
      {payments.length > 0 && (
        <ErrorBoundary>
          <X402Panel payments={payments} subTasks={sub_tasks} x402Calls={x402_calls} />
        </ErrorBoundary>
      )}

      {/* ── 5. Telegram signal feed ── */}
      {sub_tasks.length > 0 && (
        <ErrorBoundary>
          <TelegramPanel />
        </ErrorBoundary>
      )}

      {/* ── 6. Swarm Intelligence / Governance score (lifetime stats) ── */}
      {sub_tasks.length > 0 && (
        <ErrorBoundary>
          <SwarmPanel />
        </ErrorBoundary>
      )}
    </div>
  );
}
