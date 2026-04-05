"use client";

/**
 * RegisRow — Three-column layout: [LEFT STATS | REGIS SIGIL | RIGHT STATS]
 *
 * Replaces the centered RegisCard + MetricsBar combination.
 * Left: Treasury / Spent / Blocked (financial state)
 * Center: Compact REGIS sigil card
 * Right: Efficiency / Active agents / Completed (operational state)
 */

import RegisCard from "./RegisCard";
import SovereigntyRaceMini from "./SovereigntyRaceMini";
import type { Wallet, Task, SubTask, Payment } from "@/lib/api";
import { useSolRate } from "@/lib/useSolRate";
import { useModeStore } from "@/lib/modeStore";

interface Props {
  wallet: Wallet;
  task: Task;
  subTasks: SubTask[];
  payments: Payment[];
}

function LeftStat({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div style={{ textAlign: "right" }}>
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 8,
          color: "#444",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          marginBottom: 2,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 18,
          fontWeight: 700,
          color,
          lineHeight: 1,
          letterSpacing: "0.01em",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function RightStat({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div style={{ textAlign: "left" }}>
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 8,
          color: "#444",
          letterSpacing: "0.1em",
          textTransform: "uppercase",
          marginBottom: 2,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 18,
          fontWeight: 700,
          color,
          lineHeight: 1,
          letterSpacing: "0.01em",
        }}
      >
        {value}
      </div>
    </div>
  );
}

export default function RegisRow({ wallet, task, subTasks, payments }: Props) {
  const { toSol } = useSolRate();
  const { mode } = useModeStore();
  const isKingdom = mode === "kingdom";

  const signed = payments.filter((p) => p.status === "signed");
  const blocked = payments.filter((p) => p.status === "blocked");

  const totalBudget = Number(task.total_budget);
  const totalSpent = signed.reduce((s, p) => s + Number(p.amount), 0);
  const totalBlocked = blocked.reduce((s, p) => s + Number(p.amount), 0);

  const efficiency =
    totalSpent + totalBlocked > 0
      ? Math.round((totalSpent / (totalSpent + totalBlocked)) * 100)
      : 0;

  const activeCount = subTasks.filter((st) => st.status === "working").length;
  const completedCount = subTasks.filter((st) =>
    ["paid", "blocked", "complete"].includes(st.status)
  ).length;

  const effColor =
    efficiency >= 70 ? "#22c55e" : efficiency >= 40 ? "#f59e0b" : efficiency > 0 ? "#ef4444" : "#555";

  const activeColor = activeCount > 0 ? "#f59e0b" : "#444";

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0, width: "100%", rowGap: 0 }}>
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 0,
        width: "100%",
      }}
    >
      {/* LEFT STATS */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
          paddingRight: 20,
          alignItems: "flex-end",
          borderRight: "1px solid #1a1400",
          minWidth: 120,
        }}
      >
        <LeftStat
          label={isKingdom ? "Treasury" : "Budget"}
          value={toSol(totalBudget, 3)}
          color="#F59E0B"
        />
        <LeftStat
          label={isKingdom ? "Spent" : "Disbursed"}
          value={totalSpent > 0 ? toSol(totalSpent, 4) : "◎0.000"}
          color="#22c55e"
        />
        <LeftStat
          label="Blocked"
          value={totalBlocked > 0 ? toSol(totalBlocked, 4) : "◎0.000"}
          color="#ef4444"
        />
      </div>

      {/* CENTER — REGIS SIGIL */}
      <div style={{ paddingLeft: 20, paddingRight: 20 }}>
        <RegisCard wallet={wallet} task={task} />
      </div>

      {/* RIGHT STATS */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
          paddingLeft: 20,
          alignItems: "flex-start",
          borderLeft: "1px solid #1a1400",
          minWidth: 120,
        }}
      >
        <RightStat
          label="Efficiency"
          value={efficiency > 0 ? `${efficiency}%` : "—"}
          color={effColor}
        />
        <RightStat
          label="Active"
          value={`${activeCount} agents`}
          color={activeColor}
        />
        <RightStat
          label="Completed"
          value={subTasks.length > 0 ? `${completedCount}/${subTasks.length}` : "0/0"}
          color="#888"
        />
        {/* Budget health mini bars */}
        {totalBudget > 0 && (
          <div style={{ marginTop: 2 }}>
            <div style={{ fontFamily: "monospace", fontSize: 7, color: "#333", letterSpacing: "0.12em", marginBottom: 5 }}>
              BUDGET
            </div>
            {/* Agent payments bar */}
            <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 3 }}>
              <div style={{ flex: 1, height: 3, background: "#111", borderRadius: 2, overflow: "hidden" }}>
                <div
                  style={{
                    width: `${Math.min(100, (totalSpent / totalBudget) * 100)}%`,
                    height: "100%",
                    background: "#22c55e",
                    borderRadius: 2,
                  }}
                />
              </div>
              <span style={{ fontFamily: "monospace", fontSize: 6, color: "#22c55e", minWidth: 28, textAlign: "right" }}>
                {Math.round((totalSpent / totalBudget) * 100)}%
              </span>
            </div>
            {/* Remaining bar */}
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <div style={{ flex: 1, height: 3, background: "#111", borderRadius: 2, overflow: "hidden" }}>
                {(() => {
                  const remaining = Math.max(0, totalBudget - totalSpent - totalBlocked);
                  const pct = Math.min(100, (remaining / totalBudget) * 100);
                  const color = pct < 10 ? "#ef4444" : pct < 20 ? "#f59e0b" : "#F59E0B";
                  return (
                    <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2 }} />
                  );
                })()}
              </div>
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: 6,
                  color: (() => {
                    const remaining = Math.max(0, totalBudget - totalSpent - totalBlocked);
                    const pct = (remaining / totalBudget) * 100;
                    return pct < 10 ? "#ef4444" : pct < 20 ? "#f59e0b" : "#F59E0B";
                  })(),
                  minWidth: 28,
                  textAlign: "right",
                }}
              >
                {Math.round((Math.max(0, totalBudget - totalSpent - totalBlocked) / totalBudget) * 100)}%
              </span>
            </div>
          </div>
        )}
      </div>
    </div>

    {/* Sovereignty race — directly below REGIS, no gap */}
    <div style={{ width: "100%", maxWidth: 520, marginTop: 0 }}>
      <SovereigntyRaceMini />
    </div>
    </div>
  );
}
