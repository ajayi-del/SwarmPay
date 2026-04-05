"use client";

import { useEffect, useState } from "react";
import TaskForm from "@/components/TaskForm";
import Dashboard from "@/components/Dashboard";
import AuditLog from "@/components/AuditLog";
import ModeToggle from "@/components/ModeToggle";
import DryRunBadge from "@/components/DryRunBadge";
import SwarmPanel from "@/components/SwarmPanel";
import StackDiagram from "@/components/StackDiagram";
import { useSwarmStore } from "@/lib/store";
import { useModeStore } from "@/lib/modeStore";
import { motion, AnimatePresence } from "framer-motion";

export default function Home() {
  const { phase, reset } = useSwarmStore();
  const { mode } = useModeStore();
  const [showArch, setShowArch] = useState(false);
  const isActive = phase !== "idle";

  useEffect(() => {
    document.body.classList.toggle("office-mode", mode === "office");
  }, [mode]);

  return (
    <div className="min-h-screen perspective-container">
      {/* Top accent bar */}
      <div className="accent-line fixed top-0 left-0 right-0 z-50" />

      <div className="px-5 py-8 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <motion.header
          initial={{ opacity: 0, y: -12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center justify-between"
        >
          <div className="space-y-0.5">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight" style={{ letterSpacing: "-0.03em" }}>
                SwarmPay
              </h1>
              <span
                className="badge"
                style={{ background: "var(--accent-deep)", color: "var(--accent-2)", border: "1px solid rgba(108,99,255,0.2)" }}
              >
                v2.0 · DEVNET
              </span>
            </div>
            <p className="text-xs font-jb" style={{ color: "var(--text-dim)", letterSpacing: "0.06em" }}>
              MULTI-AGENT AUTONOMOUS ECONOMY · OWS · SOLANA DEVNET · x402
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden lg:flex items-center gap-3 mr-2 text-xs font-jb" style={{ color: "var(--text-dim)" }}>
              <span className="flex items-center gap-1.5">
                <span style={{ color: "var(--signed)", fontSize: 8 }}>●</span>
                budget gate
              </span>
              <span className="flex items-center gap-1.5">
                <span style={{ color: "var(--working)", fontSize: 8 }}>●</span>
                rep gate
              </span>
              <span className="flex items-center gap-1.5">
                <span style={{ color: "var(--blocked)", fontSize: 8 }}>●</span>
                FORGE +50% blocked
              </span>
            </div>
            <button
              onClick={() => setShowArch(true)}
              className="text-xs px-3 py-1.5 rounded-lg transition-colors font-jb"
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                color: "var(--text-muted)",
                letterSpacing: "0.04em",
              }}
            >
              ARCH
            </button>
            <DryRunBadge />
            <ModeToggle />
            {isActive && (
              <button
                onClick={reset}
                className="text-xs px-3 py-1.5 rounded-lg transition-colors"
                style={{
                  background: "var(--surface)",
                  border: "1px solid var(--border)",
                  color: "var(--text-muted)",
                }}
              >
                ← New Task
              </button>
            )}
          </div>
        </motion.header>

        {/* Divider */}
        <div className="divider" />

        {/* Task form */}
        {!isActive && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <TaskForm />
          </motion.div>
        )}

        {/* Dashboard + Audit */}
        {isActive && (
          <AnimatePresence mode="wait">
            <motion.div
              key={mode}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="flex flex-col xl:flex-row gap-4 items-start"
            >
              <div className="flex-1 min-w-0">
                <Dashboard />
              </div>
              <div className="w-full xl:w-72 shrink-0">
                <AuditLog />
              </div>
            </motion.div>
          </AnimatePresence>
        )}

        {/* Swarm Intelligence Panel */}
        <SwarmPanel />

        {/* Footer */}
        <footer className="flex items-center justify-between pb-2">
          <p className="text-xs font-jb" style={{ color: "var(--text-dim)", letterSpacing: "0.06em" }}>
            FASTAPI · DEEPSEEK · CLAUDE HAIKU 4.5 · POCKETBASE · NEXT.JS 14 · SOLANA DEVNET
          </p>
          <p className="text-xs font-jb" style={{ color: "var(--text-dim)", letterSpacing: "0.04em" }}>
            OWS HACKATHON · SOLANA x402 TRACK
          </p>
        </footer>
      </div>

      {/* Architecture diagram */}
      <AnimatePresence>
        {showArch && <StackDiagram onClose={() => setShowArch(false)} />}
      </AnimatePresence>
    </div>
  );
}
