"use client";

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { submitTask, decomposeTask, executeTask } from "@/lib/api";
import { useSwarmStore } from "@/lib/store";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";

const EXAMPLE_TASKS = [
  "Analyze top 5 Solana DeFi protocols by TVL, run Python yield calculations, publish report",
  "Research AI agent frameworks, compare architectures, write competitive analysis",
  "Audit smart contract risk exposure for a portfolio of 3 DeFi positions",
];

const STEPS = [
  { id: "submit",    label: "INIT",       color: "#6c63ff" },
  { id: "decompose", label: "DECOMPOSE",  color: "#a78bfa" },
  { id: "execute",   label: "EXECUTE",    color: "#f59e0b" },
];

export default function TaskForm() {
  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState("15");
  const [loading, setLoading] = useState(false);
  const [activeStep, setActiveStep] = useState(-1);
  const [error, setError] = useState<string | null>(null);

  const { setTaskId, setPhase } = useSwarmStore();

  const onSpeechResult = useCallback((text: string) => {
    setDescription(text);
  }, []);

  const { state: speechState, start: startSpeech, stop: stopSpeech, supported: speechSupported, error: speechError } =
    useSpeechRecognition(onSpeechResult);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!description.trim()) return;
    setLoading(true);
    setError(null);
    setActiveStep(0);

    try {
      const { task_id } = await submitTask(description, parseFloat(budget) || 15);
      setTaskId(task_id);
      setPhase("submitted");
      setActiveStep(1);

      await decomposeTask(task_id);
      setPhase("decomposed");
      setActiveStep(2);

      await executeTask(task_id);
      setPhase("running");
      setActiveStep(-1);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setActiveStep(-1);
    } finally {
      setLoading(false);
    }
  }

  const isMicActive = speechState === "listening";
  const isMicProcessing = speechState === "processing";

  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="w-full max-w-2xl"
    >
      {/* Card with depth */}
      <div
        className="rounded-2xl p-6 card-depth"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          boxShadow: "var(--shadow-raised), var(--shadow-inset)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div>
            <p className="text-label">Task Dispatch</p>
            <p className="text-base font-semibold mt-0.5" style={{ letterSpacing: "-0.02em" }}>
              Launch Agent Swarm
            </p>
          </div>
          {/* Step pipeline */}
          <div className="hidden sm:flex items-center gap-1">
            {STEPS.map((step, i) => (
              <div key={step.id} className="flex items-center gap-1">
                <div
                  className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[9px] font-jb transition-all"
                  style={{
                    background: activeStep === i ? `${step.color}20` : "transparent",
                    color: activeStep === i ? step.color : "var(--text-dim)",
                    border: `1px solid ${activeStep === i ? step.color + "40" : "transparent"}`,
                  }}
                >
                  {activeStep === i && (
                    <motion.span
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: "linear" }}
                      className="inline-block w-1.5 h-1.5 rounded-full"
                      style={{ background: step.color }}
                    />
                  )}
                  {step.label}
                </div>
                {i < STEPS.length - 1 && (
                  <span style={{ color: "var(--text-dim)", fontSize: 8 }}>›</span>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="accent-line mb-5" />

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Description field */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-label">Mission Brief</label>
              <div className="flex items-center gap-2">
                {speechSupported && (
                  <motion.button
                    type="button"
                    onClick={isMicActive ? stopSpeech : startSpeech}
                    whileTap={{ scale: 0.92 }}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-jb transition-all"
                    style={{
                      background: isMicActive ? "rgba(239,68,68,0.12)" : "var(--surface-2)",
                      color: isMicActive ? "#ef4444" : "var(--text-muted)",
                      border: `1px solid ${isMicActive ? "rgba(239,68,68,0.3)" : "var(--border)"}`,
                    }}
                    title={isMicActive ? "Stop recording" : "Dictate task via microphone"}
                  >
                    <AnimatePresence mode="wait">
                      {isMicActive ? (
                        <motion.span
                          key="stop"
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          exit={{ scale: 0 }}
                        >
                          ⏹
                        </motion.span>
                      ) : (
                        <motion.span key="mic" initial={{ scale: 0 }} animate={{ scale: 1 }}>
                          🎙
                        </motion.span>
                      )}
                    </AnimatePresence>
                    {isMicActive ? "Stop" : isMicProcessing ? "Processing…" : "Voice"}
                  </motion.button>
                )}
              </div>
            </div>
            <div className="relative">
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe the mission for your agent swarm…"
                rows={3}
                className="w-full rounded-xl px-4 py-3 text-sm resize-none transition-all"
                style={{
                  background: "var(--surface-2)",
                  border: `1px solid ${isMicActive ? "rgba(239,68,68,0.4)" : "var(--border)"}`,
                  color: "var(--text)",
                  lineHeight: 1.6,
                  boxShadow: isMicActive ? "0 0 0 3px rgba(239,68,68,0.08)" : "none",
                }}
                disabled={loading}
              />
              {isMicActive && (
                <motion.div
                  className="absolute bottom-2 right-2 flex items-center gap-1.5 text-[9px] font-jb"
                  style={{ color: "#ef4444" }}
                  animate={{ opacity: [1, 0.4, 1] }}
                  transition={{ duration: 1, repeat: Infinity }}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                  LISTENING
                </motion.div>
              )}
            </div>
            {speechError && (
              <p className="text-[10px] mt-1 font-jb" style={{ color: "var(--blocked)" }}>
                {speechError}
              </p>
            )}
          </div>

          {/* Example tasks */}
          <div className="flex flex-wrap gap-1.5">
            {EXAMPLE_TASKS.map((ex, i) => (
              <button
                key={i}
                type="button"
                onClick={() => setDescription(ex)}
                className="text-[10px] px-2.5 py-1 rounded-lg transition-colors font-jb truncate max-w-xs"
                style={{
                  background: "var(--surface-3)",
                  color: "var(--text-dim)",
                  border: "1px solid var(--border)",
                }}
              >
                {ex.slice(0, 40)}…
              </button>
            ))}
          </div>

          {/* Budget + Submit row */}
          <div className="flex gap-3 items-end pt-1">
            <div className="w-32">
              <label className="text-label block mb-2">Budget (USDC)</label>
              <input
                type="number"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                step="1"
                min="1"
                className="w-full rounded-xl px-3 py-2.5 text-sm transition-all"
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
              whileHover={{ scale: 1.02, y: -1 }}
              whileTap={{ scale: 0.97 }}
              className="flex-1 py-2.5 rounded-xl font-semibold text-sm transition-all disabled:opacity-40"
              style={{
                background: loading
                  ? "var(--surface-3)"
                  : "linear-gradient(135deg, #6c63ff, #a78bfa)",
                color: "#fff",
                boxShadow: loading
                  ? "none"
                  : "0 4px 20px rgba(108,99,255,0.3), 0 1px 4px rgba(0,0,0,0.4), var(--shadow-inset)",
                letterSpacing: "0.04em",
              }}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <motion.span
                    animate={{ rotate: 360 }}
                    transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
                    className="inline-block w-3 h-3 border border-white/30 border-t-white rounded-full"
                  />
                  {STEPS[activeStep]?.label ?? "LAUNCHING"}…
                </span>
              ) : (
                "LAUNCH SWARM →"
              )}
            </motion.button>
          </div>

          {/* Error */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="rounded-lg px-3 py-2 text-sm font-jb"
                style={{ background: "rgba(239,68,68,0.08)", color: "var(--blocked)", border: "1px solid rgba(239,68,68,0.2)" }}
              >
                {error}
              </motion.div>
            )}
          </AnimatePresence>
        </form>
      </div>

      {/* Agent roster preview */}
      <div className="mt-3 flex items-center justify-center gap-2">
        {["ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"].map((name) => (
          <div key={name} className="flex flex-col items-center gap-1">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center text-[9px] font-bold font-jb"
              style={{
                background: "var(--surface)",
                border: "1px solid var(--border)",
                color: "var(--text-dim)",
                letterSpacing: "0.02em",
              }}
            >
              {name.slice(0, 2)}
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
