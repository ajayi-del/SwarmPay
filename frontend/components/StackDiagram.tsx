"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

interface Layer {
  id: string;
  label: string;
  sublabel: string;
  color: string;
  glow: string;
  components: string[];
  tooltip: string;
}

const LAYERS: Layer[] = [
  {
    id: "application",
    label: "APPLICATION",
    sublabel: "Layer 6",
    color: "#a78bfa",
    glow: "#a78bfa33",
    components: ["Next.js 14", "TanStack Query", "Framer Motion", "Zustand"],
    tooltip:
      "Reactive frontend — live SSE streams, mode-aware kingdom/office UI, animated agent cards with OWS proof panels.",
  },
  {
    id: "identity",
    label: "AGENT IDENTITY",
    sublabel: "Layer 5",
    color: "#3b82f6",
    glow: "#3b82f633",
    components: ["ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"],
    tooltip:
      "Five named personas with immutable reputations, geo-locations, and skill sets. Dead Man's Switch revokes keys after 120 s silence.",
  },
  {
    id: "execution",
    label: "EXECUTION",
    sublabel: "Layer 4",
    color: "#22c55e",
    glow: "#22c55e33",
    components: ["Claude Haiku", "Firecrawl", "E2B Sandbox", "Brain Sync"],
    tooltip:
      "Parallel agent execution: ATLAS researches via Firecrawl, CIPHER runs Python in E2B, FORGE writes and publishes reports. Every result appended to REGIS brain.",
  },
  {
    id: "payment",
    label: "PAYMENT RAILS",
    sublabel: "Layer 3",
    color: "#f59e0b",
    glow: "#f59e0b33",
    components: ["OWS Sign", "Policy Engine", "Peer Transfers", "x402 USDC"],
    tooltip:
      "4-rule policy chain: REP GATE → BUDGET CAP → COORD AUTH → DOUBLE PAY. Peer payments (ATLAS→CIPHER→FORGE). x402 mock Solana USDC micropayments.",
  },
  {
    id: "governance",
    label: "GOVERNANCE",
    sublabel: "Layer 2",
    color: "#FFD700",
    glow: "#FFD70033",
    components: ["REGIS Brain", "Audit Engine", "Reputation ★", "Punishments"],
    tooltip:
      "REGIS sovereign brain: append-only memory file synced after every task. Claude-scored audits (0–100), rep deltas, slash/demote/report punishments.",
  },
  {
    id: "custody",
    label: "CUSTODY",
    sublabel: "Layer 1",
    color: "#ef4444",
    glow: "#ef444433",
    components: ["OWS Wallets", "API Keys", "PocketBase", "Key Revocation"],
    tooltip:
      "Open Wallet Standard: per-agent wallets with signed transactions, scoped API keys, balance caps. PocketBase as the shared ledger.",
  },
];

interface Props {
  onClose: () => void;
}

export default function StackDiagram({ onClose }: Props) {
  const [hoveredLayer, setHoveredLayer] = useState<string | null>(null);

  const containerVariants = {
    hidden: {},
    visible: {
      transition: { staggerChildren: 0.07, delayChildren: 0.1 },
    },
  };

  const layerVariants = {
    hidden: { opacity: 0, y: 30, scale: 0.96 },
    visible: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35 } },
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.85)", backdropFilter: "blur(6px)" }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.93, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.93, opacity: 0 }}
        transition={{ duration: 0.25 }}
        className="w-full max-w-2xl rounded-xl overflow-hidden"
        style={{ background: "#0a0a0a", border: "1px solid #222" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Title bar */}
        <div
          className="flex items-center justify-between px-5 py-4 border-b"
          style={{ borderColor: "#1a1a1a" }}
        >
          <div>
            <div className="text-sm font-bold tracking-widest uppercase text-white">
              📐 Stack Architecture
            </div>
            <div className="text-xs mt-0.5" style={{ color: "#555" }}>
              SwarmPay · 6-Layer Autonomous Economy
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-sm px-3 py-1 rounded"
            style={{ color: "#555", border: "1px solid #222" }}
          >
            ✕
          </button>
        </div>

        {/* Layers — stagger bottom-up (array is top-to-bottom, we animate in reverse visually) */}
        <motion.div
          className="p-5 space-y-2"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          {LAYERS.map((layer) => {
            const isHovered = hoveredLayer === layer.id;
            return (
              <motion.div
                key={layer.id}
                variants={layerVariants}
                onMouseEnter={() => setHoveredLayer(layer.id)}
                onMouseLeave={() => setHoveredLayer(null)}
                className="relative rounded-lg cursor-default"
                style={{
                  background: isHovered ? layer.glow : "#111",
                  border: `1px solid ${isHovered ? layer.color + "66" : "#1e1e1e"}`,
                  transition: "all 0.18s ease",
                  boxShadow: isHovered ? `0 0 12px ${layer.glow}` : "none",
                }}
              >
                <div className="flex items-start gap-3 px-4 py-3">
                  {/* Layer badge */}
                  <div className="shrink-0 mt-0.5">
                    <div
                      className="text-[10px] font-bold px-1.5 py-0.5 rounded"
                      style={{
                        background: `${layer.color}22`,
                        color: layer.color,
                        border: `1px solid ${layer.color}44`,
                      }}
                    >
                      {layer.sublabel}
                    </div>
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div
                      className="text-sm font-bold tracking-wider"
                      style={{ color: layer.color }}
                    >
                      {layer.label}
                    </div>

                    {/* Component pills */}
                    <div className="flex flex-wrap gap-1.5 mt-1.5">
                      {layer.components.map((c) => (
                        <span
                          key={c}
                          className="text-[10px] px-2 py-0.5 rounded-full"
                          style={{
                            background: "#1a1a1a",
                            color: "#888",
                            border: "1px solid #2a2a2a",
                          }}
                        >
                          {c}
                        </span>
                      ))}
                    </div>

                    {/* Tooltip on hover */}
                    <AnimatePresence>
                      {isHovered && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          transition={{ duration: 0.15 }}
                          className="overflow-hidden"
                        >
                          <p
                            className="text-xs mt-2 leading-relaxed"
                            style={{ color: "#9ca3af" }}
                          >
                            {layer.tooltip}
                          </p>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {/* Arrow indicator */}
                  <div
                    className="shrink-0 text-xs mt-0.5"
                    style={{ color: isHovered ? layer.color : "#333" }}
                  >
                    ▶
                  </div>
                </div>
              </motion.div>
            );
          })}

          {/* Data flow arrows between layers */}
          <div className="flex justify-center pt-1">
            <div className="text-xs font-jb" style={{ color: "#333" }}>
              ↑ data flows upward · ↓ control flows downward
            </div>
          </div>
        </motion.div>
      </motion.div>
    </motion.div>
  );
}
