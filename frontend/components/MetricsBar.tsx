"use client";

import { motion } from "framer-motion";
import type { TaskState } from "@/lib/api";
import { useModeStore } from "@/lib/modeStore";

interface Props {
  taskState: TaskState;
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs" style={{ color: "var(--text-dim)" }}>{label}</span>
      <span
        className="text-sm font-semibold font-jb"
        style={{ color: color ?? "var(--text)" }}
      >
        {value}
      </span>
    </div>
  );
}

export default function MetricsBar({ taskState }: Props) {
  const { task, sub_tasks, payments } = taskState;
  const { mode } = useModeStore();
  const isOffice = mode === "office";

  const signed = payments.filter((p) => p.status === "signed");
  const blocked = payments.filter((p) => p.status === "blocked");

  const totalSpent = signed.reduce((s, p) => s + p.amount, 0);
  const totalBlocked = blocked.reduce((s, p) => s + p.amount, 0);

  const efficiency =
    totalSpent + totalBlocked > 0
      ? Math.round((totalSpent / (totalSpent + totalBlocked)) * 100)
      : 0;

  const activeCount = sub_tasks.filter((st) => st.status === "working").length;
  const completedCount = sub_tasks.filter((st) =>
    ["paid", "blocked", "complete"].includes(st.status)
  ).length;

  // Budget bar: signed (green) + blocked (red) + remaining (dim)
  const totalSub = sub_tasks.reduce((s, st) => s + st.budget_allocated, 0);
  const pctSigned = totalSub > 0 ? (totalSpent / totalSub) * 100 : 0;
  const pctBlocked = totalSub > 0 ? (totalBlocked / totalSub) * 100 : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl px-5 py-4"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
      }}
    >
      {/* Stats row */}
      <div className="flex flex-wrap gap-6 items-end mb-3">
        <Stat label="Total Budget" value={`${Number(task.total_budget).toFixed(2)} ETH`} />
        <Stat label={isOffice ? "Disbursed" : "Spent"} value={`${totalSpent.toFixed(4)} ETH`} color="var(--signed)" />
        <Stat label={isOffice ? "Held" : "Blocked"} value={`${totalBlocked.toFixed(4)} ETH`} color="var(--blocked)" />

        <div className="h-8 w-px" style={{ background: "var(--border)" }} />

        <Stat
          label={isOffice ? "Clearance Rate" : "Swarm Efficiency"}
          value={efficiency > 0 ? `${efficiency}%` : "—"}
          color={efficiency >= 70 ? "var(--signed)" : efficiency > 0 ? "var(--working)" : undefined}
        />
        <Stat label={isOffice ? "Active Staff" : "Active Agents"} value={String(activeCount)} color="var(--working)" />
        <Stat label="Completed" value={`${completedCount} / ${sub_tasks.length}`} />
      </div>

      {/* Budget bar */}
      <div
        className="h-1.5 rounded-full overflow-hidden w-full"
        style={{ background: "var(--border)" }}
      >
        <div className="h-full flex">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${pctSigned}%` }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            style={{ background: "var(--signed)", minWidth: pctSigned > 0 ? 2 : 0 }}
          />
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${pctBlocked}%` }}
            transition={{ duration: 0.6, ease: "easeOut", delay: 0.1 }}
            style={{ background: "var(--blocked)", minWidth: pctBlocked > 0 ? 2 : 0 }}
          />
        </div>
      </div>
    </motion.div>
  );
}
