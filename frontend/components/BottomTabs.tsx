"use client";

/**
 * BottomTabs — Tabbed panel housing x402 Rail, Sovereignty, Orbit, and Signal.
 * Fixed ~230px height. Tab content scrolls internally.
 */

import { useState } from "react";
import type { Payment, SubTask } from "@/lib/api";
import X402Panel from "./X402Panel";
import SovereigntyPanel from "./SovereigntyPanel";
import OrbitDiagram from "./OrbitDiagram";
import TelegramPanel from "./TelegramPanel";
import SwarmPanel from "./SwarmPanel";

interface Props {
  payments: Payment[];
  subTasks: SubTask[];
  taskStatus: string;
}

type Tab = "x402" | "sovereignty" | "orbit" | "signal" | "swarm";

const TABS: { id: Tab; label: string; dot?: string }[] = [
  { id: "x402",        label: "x402 RAIL",   dot: "#9945FF" },
  { id: "sovereignty", label: "SOVEREIGNTY", dot: "#F59E0B" },
  { id: "orbit",       label: "ORBIT",       dot: "#3b82f6" },
  { id: "signal",      label: "SIGNAL",      dot: "#22c55e" },
  { id: "swarm",       label: "SWARM",       dot: "#a78bfa" },
];

export default function BottomTabs({ payments, subTasks, taskStatus }: Props) {
  const [active, setActive] = useState<Tab>("x402");

  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 14,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Tab header */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid var(--border)",
          background: "#080808",
          overflowX: "auto",
          flexShrink: 0,
        }}
      >
        {TABS.map((t) => {
          const isActive = active === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActive(t.id)}
              style={{
                padding: "8px 14px",
                fontFamily: "monospace",
                fontSize: 9,
                letterSpacing: "0.15em",
                textTransform: "uppercase",
                background: "transparent",
                border: "none",
                borderBottom: isActive ? `2px solid ${t.dot ?? "#666"}` : "2px solid transparent",
                color: isActive ? (t.dot ?? "#fff") : "#444",
                cursor: "pointer",
                whiteSpace: "nowrap",
                display: "flex",
                alignItems: "center",
                gap: 5,
                transition: "color 0.15s",
                flexShrink: 0,
              }}
            >
              {t.dot && (
                <span
                  style={{
                    width: 5,
                    height: 5,
                    borderRadius: "50%",
                    background: isActive ? t.dot : "#333",
                    flexShrink: 0,
                  }}
                />
              )}
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab body */}
      <div
        style={{
          height: 220,
          overflowY: "auto",
          padding: active === "orbit" ? 0 : "0",
        }}
      >
        {active === "x402" && (
          payments.length > 0
            ? <X402Panel payments={payments} subTasks={subTasks} />
            : <EmptyState label="No payments yet" />
        )}
        {active === "sovereignty" && <SovereigntyPanel />}
        {active === "orbit" && (
          subTasks.length > 0
            ? (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", padding: 12 }}>
                <OrbitDiagram subTasks={subTasks} />
              </div>
            )
            : <EmptyState label="No agents active" />
        )}
        {active === "signal" && <TelegramPanel />}
        {active === "swarm" && <SwarmPanel />}
      </div>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div
      style={{
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "monospace",
        fontSize: 10,
        color: "#333",
        letterSpacing: "0.1em",
      }}
    >
      {label}
    </div>
  );
}
