"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { getAuditLogs, type AuditEntry } from "@/lib/api";

const EVENT_COLORS: Record<string, string> = {
  task_submitted: "#6c63ff",
  agent_spawned: "#3b82f6",
  work_started: "#f59e0b",
  work_complete: "#22c55e",
  payment_signed: "#22c55e",
  payment_blocked: "#ef4444",
  task_complete: "#6c63ff",
  reputation_updated: "#FFD700",
  peer_payment: "#a78bfa",
};

function LogRow({ entry }: { entry: AuditEntry }) {
  const color = EVENT_COLORS[entry.event_type] ?? "#888";
  const time = new Date(entry.created).toLocaleTimeString();

  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 10 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0 }}
      className="flex gap-3 items-start py-2 border-b"
      style={{ borderColor: "var(--border)" }}
    >
      <span
        className="text-xs px-2 py-0.5 rounded-full font-medium shrink-0 mt-0.5"
        style={{ background: `${color}22`, color }}
      >
        {entry.event_type.replace(/_/g, " ")}
      </span>
      <span className="text-sm flex-1" style={{ color: "var(--text)" }}>
        {entry.message}
      </span>
      <span className="text-xs shrink-0 font-mono" style={{ color: "var(--text-muted)" }}>
        {time}
      </span>
    </motion.div>
  );
}

export default function AuditLog() {
  const { data } = useQuery({
    queryKey: ["audit"],
    queryFn: getAuditLogs,
    refetchInterval: 1500,
  });

  const logs = data?.logs ?? [];

  return (
    <div
      className="rounded-2xl p-5 space-y-1 h-full max-h-[480px] overflow-y-auto"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
      }}
    >
      <h3 className="text-sm font-semibold mb-3" style={{ color: "var(--text-muted)" }}>
        Audit Log
      </h3>
      {logs.length === 0 ? (
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          No events yet. Submit a task to start.
        </p>
      ) : (
        <AnimatePresence>
          {logs.map((entry) => (
            <LogRow key={entry.id} entry={entry} />
          ))}
        </AnimatePresence>
      )}
    </div>
  );
}
