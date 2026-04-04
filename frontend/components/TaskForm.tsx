"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { submitTask, decomposeTask, executeTask } from "@/lib/api";
import { useSwarmStore } from "@/lib/store";

export default function TaskForm() {
  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState("0.97");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { setTaskId, setPhase } = useSwarmStore();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!description.trim()) return;
    setLoading(true);
    setError(null);

    try {
      // 1. Submit
      const { task_id } = await submitTask(description, parseFloat(budget));
      setTaskId(task_id);
      setPhase("submitted");

      // 2. Decompose
      await decomposeTask(task_id);
      setPhase("decomposed");

      // 3. Execute (async background on server)
      await executeTask(task_id);
      setPhase("running");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-2xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-2" style={{ color: "var(--text-muted)" }}>
            Task Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. Build a market analysis report for DeFi protocols..."
            rows={3}
            className="w-full rounded-xl px-4 py-3 text-sm resize-none outline-none transition-all"
            style={{
              background: "var(--surface-2)",
              border: "1px solid var(--border)",
              color: "var(--text)",
            }}
            disabled={loading}
          />
        </div>

        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-2" style={{ color: "var(--text-muted)" }}>
              Total Budget (ETH)
            </label>
            <input
              type="number"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              step="0.01"
              min="0.01"
              className="w-full rounded-xl px-4 py-3 text-sm outline-none transition-all"
              style={{
                background: "var(--surface-2)",
                border: "1px solid var(--border)",
                color: "var(--text)",
              }}
              disabled={loading}
            />
          </div>

          <motion.button
            type="submit"
            disabled={loading || !description.trim()}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="px-8 py-3 rounded-xl font-semibold text-sm transition-all disabled:opacity-40"
            style={{
              background: loading ? "var(--border)" : "var(--accent)",
              color: "#fff",
              boxShadow: loading ? "none" : "0 0 20px var(--accent-glow)",
            }}
          >
            {loading ? "Launching…" : "Launch Swarm"}
          </motion.button>
        </div>

        {error && (
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-sm rounded-lg px-3 py-2"
            style={{ background: "rgba(239,68,68,0.1)", color: "var(--blocked)" }}
          >
            {error}
          </motion.p>
        )}
      </form>
    </motion.div>
  );
}
