"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTaskStatus, type TaskState } from "@/lib/api";
import { useSwarmStore } from "@/lib/store";
import { useModeStore } from "@/lib/modeStore";
import AgentCard from "./AgentCard";
import SleepingAgentCard from "./SleepingAgentCard";
import CoordinatorCard from "./CoordinatorCard";
import RegisCard from "./RegisCard";
import MetricsBar from "./MetricsBar";
import RegisConsole from "./RegisConsole";
import SkillsPanel from "./SkillsPanel";
import SwarmOrbit from "./SwarmOrbit";
import X402Panel from "./X402Panel";
import TelegramPanel from "./TelegramPanel";
import { ErrorBoundary } from "./ErrorBoundary";

// Active statuses — these agents are always expanded
const ACTIVE_STATUSES = new Set(["spawned", "working"]);

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

  if (!taskId || !taskState) return null;

  const { task, coordinator_wallet, sub_tasks, payments, reputations = {} } = taskState;

  const ALL_AGENTS = ["ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"];
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

  return (
    <div className="w-full space-y-4">
      {/* Kingdom: compact REGIS sigil card | Office: full coordinator card */}
      {coordinator_wallet && (
        <ErrorBoundary>
          {isKingdom ? (
            <div className="flex justify-center">
              <RegisCard wallet={coordinator_wallet} task={task} />
            </div>
          ) : (
            <CoordinatorCard wallet={coordinator_wallet} task={task} />
          )}
          <RegisConsole coordinatorWalletId={coordinator_wallet.id} />
        </ErrorBoundary>
      )}

      {/* CSS-only orbit constellation — no Three.js */}
      {sub_tasks.length > 0 && (
        <ErrorBoundary>
          <SwarmOrbit
            subTasks={sub_tasks}
            payments={payments}
            taskStatus={task.status}
          />
        </ErrorBoundary>
      )}

      {/* Agent grid */}
      {sub_tasks.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {sub_tasks.map((st, i) => {
            const payment = payments.find(
              (p) => p.to_wallet_id === st.wallet_id && !p.policy_reason?.startsWith("PEER:")
            );
            const peerPayment = payments.find(
              (p) => p.to_wallet_id === st.wallet_id && p.policy_reason?.startsWith("PEER:")
            );

            // Active agents always expand; terminal agents collapse unless user expanded them
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

      {/* Metrics bar */}
      {sub_tasks.length > 0 && (
        <ErrorBoundary>
          <MetricsBar taskState={taskState} />
        </ErrorBoundary>
      )}

      {/* x402 payment rail */}
      {payments.length > 0 && (
        <ErrorBoundary>
          <X402Panel payments={payments} subTasks={sub_tasks} />
        </ErrorBoundary>
      )}

      {/* Telegram signal feed */}
      {sub_tasks.length > 0 && (
        <ErrorBoundary>
          <TelegramPanel />
        </ErrorBoundary>
      )}

      {/* Skills registry */}
      {sub_tasks.length > 0 && (
        <ErrorBoundary>
          <SkillsPanel />
        </ErrorBoundary>
      )}
    </div>
  );
}
