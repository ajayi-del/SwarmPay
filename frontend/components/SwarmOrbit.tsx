"use client";

/**
 * SwarmOrbit — dynamic wrapper for SwarmOrbitScene.
 * Three.js/R3F cannot run during SSR, so we load it client-side only.
 * Falls back to a subtle status grid during loading.
 */

import dynamic from "next/dynamic";
import type { SubTask, Payment } from "@/lib/api";

const SwarmOrbitScene = dynamic(() => import("./SwarmOrbitScene"), {
  ssr: false,
  loading: () => (
    <div
      className="rounded-2xl"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        height: 280,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <p className="text-xs font-jb" style={{ color: "var(--text-dim)", letterSpacing: "0.1em" }}>
        ORBIT LOADING…
      </p>
    </div>
  ),
});

interface Props {
  subTasks: SubTask[];
  payments: Payment[];
  taskStatus: string;
}

export default function SwarmOrbit({ subTasks, payments, taskStatus }: Props) {
  return <SwarmOrbitScene subTasks={subTasks} payments={payments} taskStatus={taskStatus} />;
}
