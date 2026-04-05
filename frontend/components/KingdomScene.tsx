"use client";

/**
 * KingdomScene — CSS-only atmospheric header for Kingdom mode.
 *
 * A dark 180px banner with:
 *   Left  — 🏰 castle, "KINGDOM OF SWARMPAY" title, torch
 *   Center — REGIS crown 👑 with SOL balance + status
 *   Right  — agent dots (accent colors) with initial letters
 *   Bottom — scrolling marquee of active agent status
 *   BG     — CSS box-shadow star field (no canvas, no library)
 *
 * All animations are pure CSS keyframes via style tags.
 * No Three.js, no canvas, no external libraries beyond Framer Motion.
 */

import { useEffect, useState } from "react";
import { useSolRate } from "@/lib/useSolRate";
import type { SubTask } from "@/lib/api";

// ── Agent dot config ───────────────────────────────────────────────────────────

const AGENTS = [
  { id: "ATLAS",  initial: "A", color: "#3b82f6" },
  { id: "CIPHER", initial: "C", color: "#a855f7" },
  { id: "FORGE",  initial: "F", color: "#f97316" },
  { id: "BISHOP", initial: "S", color: "#e8e8f0" },
  { id: "SØN",    initial: "Ø", color: "#00ffff" },
];

// ── CSS star field (pure box-shadow) ──────────────────────────────────────────

function generateStars(count: number): string {
  const shadows: string[] = [];
  // Deterministic using seeded positions so SSR matches client
  for (let i = 0; i < count; i++) {
    // Simple pseudo-random using sin
    const x = Math.round(Math.abs(Math.sin(i * 7.3) * 1800));
    const y = Math.round(Math.abs(Math.cos(i * 3.7) * 180));
    const alpha = 0.2 + Math.abs(Math.sin(i * 1.9)) * 0.6;
    shadows.push(`${x}px ${y}px 0 rgba(255,255,255,${alpha.toFixed(2)})`);
  }
  return shadows.join(", ");
}

const STARS_SM = generateStars(60);   // 1px stars
const STARS_MD = generateStars(30);   // 1.5px stars

// ── Marquee text builder ───────────────────────────────────────────────────────

function buildMarquee(subTasks: SubTask[]): string {
  if (subTasks.length === 0) {
    return "KINGDOM OF SWARMPAY · AGENTS STANDING BY · REGIS GOVERNING · TREASURY SECURE · ";
  }
  const segments = subTasks.map((st) => {
    const statusWord =
      st.status === "working"   ? "ACTIVE" :
      st.status === "paid"      ? "PAID" :
      st.status === "blocked"   ? "BLOCKED" :
      st.status === "complete"  ? "COMPLETE" :
      st.status === "spawned"   ? "SPAWNED" :
      "STANDBY";
    return `${st.agent_id} ${statusWord}…`;
  });
  return segments.join("   ·   ") + "   ·   ";
}

// ── Props ──────────────────────────────────────────────────────────────────────

interface Props {
  subTasks?: SubTask[];
  treasuryBalance?: number; // USDC
  taskActive?: boolean;
  reputations?: Record<string, number>;
}

export default function KingdomScene({
  subTasks = [],
  treasuryBalance = 0,
  taskActive = false,
  reputations = {},
}: Props) {
  const { toSol } = useSolRate();
  const [tick, setTick] = useState(0);
  const torchFrames = ["🔥", "🕯️", "🔥", "🔥", "🕯️"];
  const torch = torchFrames[tick % torchFrames.length];

  // Torch flicker at ~3fps
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 300);
    return () => clearInterval(id);
  }, []);

  const activeAgents = new Set(
    subTasks.filter((s) => s.status === "working").map((s) => s.agent_id)
  );
  const activeCount = activeAgents.size;
  const totalAgents = AGENTS.length;

  const regisStatus = taskActive
    ? subTasks.some((s) => s.status === "working") ? "OVERSEEING" : "PROCESSING"
    : "RESTING";

  const marqueeText = buildMarquee(subTasks);

  return (
    <>
      {/* Injected keyframes — tiny, one-time */}
      <style>{`
        @keyframes ks-crown-pulse {
          0%, 100% { transform: scale(1); filter: drop-shadow(0 0 6px #FFD70080); }
          50% { transform: scale(1.05); filter: drop-shadow(0 0 14px #FFD700bb); }
        }
        @keyframes ks-dot-pulse {
          0%, 100% { opacity: 0.5; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.25); }
        }
        @keyframes ks-marquee {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        @keyframes ks-torch-flicker {
          0%, 100% { opacity: 0.7; }
          25% { opacity: 1; }
          75% { opacity: 0.85; }
        }
      `}</style>

      <div
        style={{
          position: "relative",
          width: "100%",
          height: 180,
          background: "#080808",
          borderRadius: 16,
          border: "1px solid #1a1a2e",
          overflow: "hidden",
          boxShadow: "0 0 40px rgba(255,215,0,0.04) inset",
        }}
      >
        {/* ── Star field layers ── */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            width: 1,
            height: 1,
            boxShadow: STARS_SM,
            background: "rgba(255,255,255,0.9)",
            borderRadius: "50%",
            pointerEvents: "none",
          }}
        />
        <div
          style={{
            position: "absolute",
            inset: 0,
            width: 1.5,
            height: 1.5,
            boxShadow: STARS_MD,
            background: "rgba(255,255,255,0.6)",
            borderRadius: "50%",
            pointerEvents: "none",
          }}
        />

        {/* ── Atmospheric gradient overlay ── */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "radial-gradient(ellipse at 50% 60%, rgba(255,215,0,0.04) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />

        {/* ── Main content layer ── */}
        <div
          style={{
            position: "absolute",
            inset: "0 0 28px 0",   // leave 28px at bottom for marquee
            display: "flex",
            alignItems: "center",
            padding: "0 24px",
            gap: 0,
          }}
        >
          {/* ──────── LEFT: Castle + Title + Torch ──────── */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-start",
              gap: 4,
              flex: "0 0 auto",
              minWidth: 160,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ fontSize: 36, lineHeight: 1 }}>🏰</span>
              <span
                style={{
                  fontSize: 9,
                  fontFamily: "monospace",
                  color: "#FFD700",
                  letterSpacing: "0.15em",
                  fontWeight: 700,
                  textTransform: "uppercase",
                  lineHeight: 1.3,
                }}
              >
                KINGDOM OF
                <br />
                SWARMPAY
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span
                style={{
                  fontSize: 20,
                  animation: "ks-torch-flicker 0.8s ease-in-out infinite",
                  display: "inline-block",
                }}
              >
                {torch}
              </span>
              <span
                style={{
                  fontSize: 8,
                  fontFamily: "monospace",
                  color: "#555",
                  letterSpacing: "0.1em",
                }}
              >
                DEVNET LIVE
              </span>
            </div>
          </div>

          {/* ──────── CENTER: REGIS Throne ──────── */}
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 4,
            }}
          >
            {/* Raised platform */}
            <div
              style={{
                background: "linear-gradient(180deg, #1a1200 0%, #0d0a00 100%)",
                border: "1px solid #2a2200",
                borderRadius: 12,
                padding: "10px 20px 8px",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: 3,
                boxShadow: "0 0 20px rgba(255,215,0,0.06)",
              }}
            >
              <span
                style={{
                  fontSize: 36,
                  lineHeight: 1,
                  animation: taskActive
                    ? "ks-crown-pulse 2s ease-in-out infinite"
                    : "none",
                  display: "inline-block",
                }}
              >
                👑
              </span>
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  color: "#9945FF",
                  letterSpacing: "0.05em",
                }}
              >
                {toSol(treasuryBalance, 3)} SOL
              </span>
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: "0.55rem",
                  color: taskActive ? "#22c55e" : "#555",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                }}
              >
                {regisStatus}
              </span>
            </div>
            <span
              style={{
                fontFamily: "monospace",
                fontSize: "0.5rem",
                color: "#333",
                letterSpacing: "0.12em",
              }}
            >
              REGIS
            </span>
          </div>

          {/* ──────── RIGHT: Agent Dots ──────── */}
          <div
            style={{
              flex: "0 0 auto",
              minWidth: 120,
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-end",
              gap: 6,
            }}
          >
            <span
              style={{
                fontFamily: "monospace",
                fontSize: "0.55rem",
                color: "#444",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              {activeCount > 0 ? `${activeCount} AGENT${activeCount > 1 ? "S" : ""} ACTIVE` : "AGENTS IDLE"}
            </span>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              {AGENTS.map((agent) => {
                const isActive = activeAgents.has(agent.id);
                const rep = reputations[agent.id] ?? 3;
                const opacity = 0.3 + (rep / 5) * 0.3;
                return (
                  <div
                    key={agent.id}
                    title={`${agent.id} · ${isActive ? "ACTIVE" : "IDLE"} · ★${rep.toFixed(1)}`}
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: "50%",
                      background: agent.color,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 8,
                      fontFamily: "monospace",
                      fontWeight: 700,
                      color: "#000",
                      opacity: isActive ? 1 : opacity,
                      animation: isActive
                        ? "ks-dot-pulse 1.5s ease-in-out infinite"
                        : "none",
                      boxShadow: isActive
                        ? `0 0 10px ${agent.color}99`
                        : "none",
                      cursor: "default",
                    }}
                  >
                    {agent.initial}
                  </div>
                );
              })}
            </div>
            <span
              style={{
                fontFamily: "monospace",
                fontSize: "0.5rem",
                color: "#333",
                letterSpacing: "0.08em",
              }}
            >
              {totalAgents} TOTAL · REGIS GOVERNING
            </span>
          </div>
        </div>

        {/* ── Bottom marquee ── */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 28,
            background: "#0a0a0f",
            borderTop: "1px solid #1a1a2e",
            overflow: "hidden",
            display: "flex",
            alignItems: "center",
          }}
        >
          <div
            style={{
              display: "flex",
              whiteSpace: "nowrap",
              animation: "ks-marquee 20s linear infinite",
            }}
          >
            {/* Double the text so it loops seamlessly */}
            {[0, 1].map((k) => (
              <span
                key={k}
                style={{
                  fontFamily: "monospace",
                  fontSize: "0.6rem",
                  color: "#444",
                  letterSpacing: "0.1em",
                  paddingRight: 60,
                }}
              >
                {marqueeText}
              </span>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
