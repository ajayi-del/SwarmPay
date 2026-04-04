"use client";

import TaskForm from "@/components/TaskForm";
import Dashboard from "@/components/Dashboard";
import AuditLog from "@/components/AuditLog";
import { useSwarmStore } from "@/lib/store";
import { motion } from "framer-motion";

export default function Home() {
  const { phase, reset } = useSwarmStore();
  const isActive = phase !== "idle";

  return (
    <div className="min-h-screen px-5 py-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div>
          <h1 className="text-2xl font-bold tracking-tight">SwarmPay</h1>
          <p className="text-xs mt-0.5 font-jb" style={{ color: "var(--text-muted)" }}>
            Multi-Agent Autonomous Economy · Open Wallet Standard · Category 04
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Policy legend */}
          <div className="hidden md:flex gap-3 text-xs font-jb" style={{ color: "var(--text-dim)" }}>
            <span>① budget cap</span>
            <span>② coordinator sign</span>
            <span>③ no double-pay</span>
            <span style={{ color: "var(--blocked)" }}>FORGE +50% → BLOCKED</span>
          </div>
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
      </motion.div>

      {/* Task form */}
      {!isActive && <TaskForm />}

      {/* Main content: dashboard + audit log side by side */}
      {isActive && (
        <div className="flex flex-col xl:flex-row gap-4 items-start">
          <div className="flex-1 min-w-0">
            <Dashboard />
          </div>
          <div className="w-full xl:w-72 shrink-0">
            <AuditLog />
          </div>
        </div>
      )}

      <p className="text-xs text-center pb-2 font-jb" style={{ color: "var(--text-dim)" }}>
        FastAPI · Claude Haiku · PocketBase · Next.js 14 · OWS Policy Engine
      </p>
    </div>
  );
}
