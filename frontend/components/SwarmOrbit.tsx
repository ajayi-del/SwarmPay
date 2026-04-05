"use client";

/**
 * SwarmOrbit — CSS-only agent constellation.
 *
 * The Three.js/R3F version was removed because @react-three/fiber v9
 * accesses React 19 internals (x.S) that don't exist in React 18,
 * causing a fatal runtime crash ("undefined is not an object evaluating x.S").
 *
 * This CSS/SVG replacement renders a radial orbit diagram. No WebGL. No crashes.
 */

import { motion } from "framer-motion";
import type { SubTask, Payment } from "@/lib/api";
import { AGENT_PERSONAS } from "@/lib/personas";

interface Props {
  subTasks: SubTask[];
  payments: Payment[];
  taskStatus: string;
}

const STATUS_COLOR: Record<string, string> = {
  working:   "#f59e0b",
  spawned:   "#6c63ff",
  complete:  "#22c55e",
  paid:      "#22c55e",
  blocked:   "#ef4444",
  failed:    "#555",
  timed_out: "#333",
};

export default function SwarmOrbit({ subTasks, payments }: Props) {
  if (subTasks.length === 0) return null;

  const totalBudget = subTasks.reduce((s, st) => s + (st.budget_allocated ?? 0), 0) || 1;
  const N = subTasks.length;
  const CX = 110;
  const CY = 100;
  const RADIUS = 72;

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        height: 220,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 20px",
        gap: 12,
      }}
    >
      {/* Radial SVG diagram */}
      <svg width={220} height={200} viewBox="0 0 220 200" style={{ flexShrink: 0 }}>
        {/* Orbit rings */}
        <circle cx={CX} cy={CY} r={RADIUS}        fill="none" stroke="#ffffff06" strokeWidth="1" strokeDasharray="4 6" />
        <circle cx={CX} cy={CY} r={RADIUS * 0.55} fill="none" stroke="#ffffff04" strokeWidth="1" />

        {/* Peer payment lines */}
        {payments
          .filter(p => p.policy_reason?.startsWith("PEER:"))
          .slice(0, 4)
          .map((p, i) => {
            const fi = subTasks.findIndex(st => st.wallet_id === p.from_wallet_id);
            const ti = subTasks.findIndex(st => st.wallet_id === p.to_wallet_id);
            if (fi < 0 || ti < 0) return null;
            const fa = (fi / N) * Math.PI * 2 - Math.PI / 2;
            const ta = (ti / N) * Math.PI * 2 - Math.PI / 2;
            const r1 = subTasks[fi].is_lead ? RADIUS * 0.55 : RADIUS;
            const r2 = subTasks[ti].is_lead ? RADIUS * 0.55 : RADIUS;
            return (
              <line key={i}
                x1={CX + Math.cos(fa) * r1} y1={CY + Math.sin(fa) * r1}
                x2={CX + Math.cos(ta) * r2} y2={CY + Math.sin(ta) * r2}
                stroke={p.status === "signed" ? "#22c55e" : "#ef4444"}
                strokeWidth="1" strokeOpacity="0.35" strokeDasharray="3 4"
              />
            );
          })}

        {/* REGIS core */}
        <circle cx={CX} cy={CY} r={16} fill="#110e00" stroke="#F59E0B" strokeWidth="1.5" />
        <text x={CX} y={CY + 4} textAnchor="middle" fontSize={6.5} fill="#F59E0B" fontFamily="monospace" letterSpacing="0.1em">REGIS</text>

        {/* Agent dots */}
        {subTasks.map((st, i) => {
          const angle  = (i / N) * Math.PI * 2 - Math.PI / 2;
          const r      = st.is_lead ? RADIUS * 0.55 : RADIUS;
          const x      = CX + Math.cos(angle) * r;
          const y      = CY + Math.sin(angle) * r;
          const color  = AGENT_PERSONAS[st.agent_id]?.roleColor ?? "#6c63ff";
          const sColor = STATUS_COLOR[st.status] ?? color;
          const dotR   = 5.5 + ((st.budget_allocated ?? 0) / totalBudget) * 7;
          const isActive = st.status === "working";

          return (
            <g key={st.id}>
              {st.is_lead && (
                <circle cx={x} cy={y} r={dotR + 4} fill="none" stroke="#F59E0B" strokeWidth="0.8" strokeOpacity="0.5" />
              )}
              {isActive && (
                <motion.circle
                  cx={x} cy={y} r={dotR + 8}
                  fill="none" stroke={sColor} strokeWidth="0.5"
                  animate={{ opacity: [0.4, 0, 0.4], r: [dotR + 8, dotR + 14, dotR + 8] }}
                  transition={{ duration: 1.5, repeat: Infinity }}
                />
              )}
              <circle cx={x} cy={y} r={dotR} fill={color + "25"} stroke={sColor} strokeWidth="1.5" />
              <text x={x} y={y + 3} textAnchor="middle" fontSize={6} fill={color} fontFamily="monospace" fontWeight="bold">
                {st.agent_id.slice(0, 2)}
              </text>
              <circle cx={x + dotR - 1} cy={y - dotR + 1} r={2} fill={sColor} />
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 10, fontFamily: "monospace", minWidth: 100 }}>
        <span style={{ color: "#444", letterSpacing: "0.12em", fontSize: 9, marginBottom: 2 }}>AGENTS</span>
        {subTasks.map(st => {
          const color  = AGENT_PERSONAS[st.agent_id]?.roleColor ?? "#6c63ff";
          const sColor = STATUS_COLOR[st.status] ?? color;
          return (
            <div key={st.id} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 5, height: 5, borderRadius: "50%", background: sColor, flexShrink: 0 }} />
              <span style={{ color: "var(--text-dim)" }}>{st.agent_id}</span>
              {st.is_lead && <span style={{ color: "#F59E0B", fontSize: 8 }}>★</span>}
              <span style={{ color: sColor, marginLeft: "auto", fontSize: 9 }}>{st.status.slice(0, 4).toUpperCase()}</span>
            </div>
          );
        })}
        {payments.filter(p => p.status === "blocked").length > 0 && (
          <div style={{ borderTop: "1px solid var(--border)", paddingTop: 4, color: "#ef4444", fontSize: 9, marginTop: 2 }}>
            {payments.filter(p => p.status === "blocked").length} blocked
          </div>
        )}
      </div>
    </div>
  );
}
