"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useModeStore } from "@/lib/modeStore";
import {
  probeRegis,
  auditRegis,
  punishRegis,
  type AuditResult,
} from "@/lib/api";

interface Message {
  role: "user" | "regis";
  text: string;
}

interface Props {
  coordinatorWalletId?: string;
}

export default function RegisConsole({ coordinatorWalletId }: Props) {
  const { mode } = useModeStore();
  const isKingdom = mode === "kingdom";

  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [audit, setAudit] = useState<AuditResult | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [punishLoading, setPunishLoading] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const accent = isKingdom ? "#FFD700" : "#3b82f6";
  const title = isKingdom ? "REGIS — Sovereign Brain" : "AI Governance Console";
  const placeholder = isKingdom
    ? "Interrogate REGIS…"
    : "Query governance AI…";

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  async function sendProbe() {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text: q }]);
    setLoading(true);
    try {
      const data = await probeRegis(q);
      setMessages((m) => [...m, { role: "regis", text: data.response }]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "regis", text: "⚠ Communication with REGIS failed." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function runAudit() {
    setAuditLoading(true);
    try {
      const result = await auditRegis();
      setAudit(result);
    } catch {
      /* ignore */
    } finally {
      setAuditLoading(false);
    }
  }

  async function applyPunishment(type: string) {
    setPunishLoading(type);
    try {
      const result = await punishRegis(type, coordinatorWalletId);
      setMessages((m) => [
        ...m,
        {
          role: "regis",
          text: `[PUNISHMENT: ${type.replace(/_/g, " ").toUpperCase()}]\n\n${result.response}${result.report ? `\n\n${result.report}` : ""}`,
        },
      ]);
      if (!open) setOpen(true);
    } catch {
      /* ignore */
    } finally {
      setPunishLoading(null);
    }
  }

  const verdictColor = (v?: string) =>
    v === "PASSED" ? "#22c55e" : v === "FAILED" ? "#ef4444" : "#f59e0b";

  const gaugeArc = (score: number) => {
    const r = 28;
    const circ = Math.PI * r; // half circumference for semi-circle
    const offset = circ - (score / 100) * circ;
    return { circ, offset };
  };

  return (
    <div
      className="rounded-lg border mt-3"
      style={{ borderColor: `${accent}33`, background: "#0a0a0a" }}
    >
      {/* ── Header ── */}
      <button
        className="w-full flex items-center justify-between px-4 py-3"
        onClick={() => setOpen((o) => !o)}
      >
        <div className="flex items-center gap-2">
          <span style={{ color: accent, fontSize: 18 }}>
            {isKingdom ? "👑" : "🤖"}
          </span>
          <span
            className="text-sm font-bold tracking-widest uppercase"
            style={{ color: accent }}
          >
            {title}
          </span>
        </div>
        <span style={{ color: accent, opacity: 0.6, fontSize: 12 }}>
          {open ? "▲" : "▼"}
        </span>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            style={{ overflow: "hidden" }}
          >
            <div className="px-4 pb-4 space-y-4">
              {/* ── Audit gauge + run button ── */}
              <div className="flex items-center gap-4">
                {/* Semi-circle gauge */}
                <div className="relative" style={{ width: 72, height: 40 }}>
                  <svg width={72} height={40} viewBox="0 0 72 40">
                    {/* track */}
                    <path
                      d="M 8 36 A 28 28 0 0 1 64 36"
                      fill="none"
                      stroke="#222"
                      strokeWidth={7}
                      strokeLinecap="round"
                    />
                    {/* fill */}
                    {audit && (() => {
                      const { circ, offset } = gaugeArc(audit.score);
                      return (
                        <path
                          d="M 8 36 A 28 28 0 0 1 64 36"
                          fill="none"
                          stroke={verdictColor(audit.verdict)}
                          strokeWidth={7}
                          strokeLinecap="round"
                          strokeDasharray={circ}
                          strokeDashoffset={offset}
                          style={{ transition: "stroke-dashoffset 0.6s ease" }}
                        />
                      );
                    })()}
                  </svg>
                  <div
                    className="absolute inset-0 flex items-end justify-center pb-0.5"
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color: audit ? verdictColor(audit.verdict) : "#444",
                    }}
                  >
                    {audit ? audit.score : "--"}
                  </div>
                </div>

                <div className="flex-1">
                  {audit ? (
                    <div>
                      <div
                        className="text-xs font-bold"
                        style={{ color: verdictColor(audit.verdict) }}
                      >
                        {audit.verdict}
                        <span className="ml-2 font-normal text-gray-400">
                          rep {audit.rep_delta > 0 ? "+" : ""}
                          {audit.rep_delta.toFixed(1)}★
                        </span>
                      </div>
                      <div className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                        {audit.reason}
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-gray-600">
                      {isKingdom
                        ? "Run audit to evaluate REGIS governance"
                        : "Run governance review"}
                    </div>
                  )}
                </div>

                <button
                  onClick={runAudit}
                  disabled={auditLoading}
                  className="text-xs px-3 py-1.5 rounded font-bold uppercase tracking-wider"
                  style={{
                    background: `${accent}22`,
                    color: accent,
                    border: `1px solid ${accent}44`,
                    opacity: auditLoading ? 0.5 : 1,
                  }}
                >
                  {auditLoading ? "…" : isKingdom ? "Audit" : "Review"}
                </button>
              </div>

              {/* ── Punishment buttons ── */}
              <div className="flex gap-2 flex-wrap">
                {[
                  { type: "slash_treasury", label: isKingdom ? "⚔ Slash Treasury" : "✂ Cut Budget", color: "#ef4444" },
                  { type: "demote_reputation", label: isKingdom ? "↓ Demote" : "↓ Downgrade", color: "#f97316" },
                  { type: "governance_report", label: isKingdom ? "📜 Demand Report" : "📋 Request Report", color: "#a78bfa" },
                ].map(({ type, label, color }) => (
                  <button
                    key={type}
                    onClick={() => applyPunishment(type)}
                    disabled={!!punishLoading}
                    className="text-xs px-2.5 py-1 rounded font-semibold"
                    style={{
                      background: `${color}18`,
                      color,
                      border: `1px solid ${color}33`,
                      opacity: punishLoading === type ? 0.5 : 1,
                    }}
                  >
                    {punishLoading === type ? "…" : label}
                  </button>
                ))}
              </div>

              {/* ── Chat log ── */}
              <div
                ref={scrollRef}
                className="space-y-2 max-h-64 overflow-y-auto pr-1"
                style={{ scrollbarWidth: "none" }}
              >
                <AnimatePresence initial={false}>
                  {messages.map((msg, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.2 }}
                      className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className="text-xs rounded px-3 py-2 max-w-[85%] whitespace-pre-wrap leading-relaxed"
                        style={
                          msg.role === "user"
                            ? {
                                background: `${accent}22`,
                                color: accent,
                                border: `1px solid ${accent}33`,
                              }
                            : {
                                background: "#111",
                                color: "#d1d5db",
                                border: "1px solid #222",
                              }
                        }
                      >
                        {msg.role === "regis" && (
                          <span
                            className="block text-[10px] font-bold mb-1 uppercase tracking-widest"
                            style={{ color: accent }}
                          >
                            {isKingdom ? "REGIS" : "AI GOVERNOR"}
                          </span>
                        )}
                        {msg.text}
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>

                {loading && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex justify-start"
                  >
                    <div
                      className="text-xs px-3 py-2 rounded"
                      style={{ background: "#111", border: "1px solid #222" }}
                    >
                      <span
                        className="inline-flex gap-1"
                        style={{ color: accent }}
                      >
                        <span className="animate-bounce" style={{ animationDelay: "0ms" }}>•</span>
                        <span className="animate-bounce" style={{ animationDelay: "150ms" }}>•</span>
                        <span className="animate-bounce" style={{ animationDelay: "300ms" }}>•</span>
                      </span>
                    </div>
                  </motion.div>
                )}
              </div>

              {/* ── Input ── */}
              <div className="flex gap-2">
                <input
                  className="flex-1 text-xs rounded px-3 py-2 outline-none"
                  style={{
                    background: "#111",
                    color: "#d1d5db",
                    border: `1px solid ${accent}33`,
                  }}
                  placeholder={placeholder}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendProbe()}
                  disabled={loading}
                />
                <button
                  onClick={sendProbe}
                  disabled={loading || !input.trim()}
                  className="text-xs px-3 py-2 rounded font-bold"
                  style={{
                    background: `${accent}22`,
                    color: accent,
                    border: `1px solid ${accent}44`,
                    opacity: loading || !input.trim() ? 0.4 : 1,
                  }}
                >
                  Send
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
