"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTaskStatus, type TaskState } from "@/lib/api";
import { useSwarmStore } from "@/lib/store";
import AgentCard from "./AgentCard";
import CoordinatorCard from "./CoordinatorCard";
import MetricsBar from "./MetricsBar";
import { ErrorBoundary } from "./ErrorBoundary";

export default function Dashboard() {
  const { taskId, setPhase } = useSwarmStore();

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

  // Transition to "done" phase via effect, not inside a query callback
  useEffect(() => {
    const status = taskState?.task?.status;
    if (status === "complete" || status === "failed") {
      setPhase("done");
    }
  }, [taskState?.task?.status, setPhase]);

  if (!taskId || !taskState) return null;

  const { task, coordinator_wallet, sub_tasks, payments, reputations = {} } = taskState;

  return (
    <div className="w-full space-y-4">
      {/* REGIS — coordinator */}
      {coordinator_wallet && (
        <ErrorBoundary>
          <CoordinatorCard wallet={coordinator_wallet} task={task} />
        </ErrorBoundary>
      )}

      {/* 5 agent cards — responsive grid */}
      {sub_tasks.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {sub_tasks.map((st, i) => {
            // Coordinator payment — excludes peer payments (which start with "PEER:")
            const payment = payments.find(
              (p) =>
                p.to_wallet_id === st.wallet_id &&
                !p.policy_reason?.startsWith("PEER:")
            );
            // Peer payment received by this agent
            const peerPayment = payments.find(
              (p) =>
                p.to_wallet_id === st.wallet_id &&
                p.policy_reason?.startsWith("PEER:")
            );
            return (
              <ErrorBoundary key={st.id}>
                <AgentCard
                  subTask={st}
                  payment={payment}
                  peerPayment={peerPayment}
                  index={i}
                  reputation={reputations[st.agent_id]}
                />
              </ErrorBoundary>
            );
          })}
        </div>
      )}

      {/* Metrics bar */}
      {sub_tasks.length > 0 && (
        <ErrorBoundary>
          <MetricsBar taskState={taskState} />
        </ErrorBoundary>
      )}
    </div>
  );
}
