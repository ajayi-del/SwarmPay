"use client";

/**
 * AgentAvatar — Framer Motion SVG identity for each agent.
 *
 * Each agent has a UNIQUE GEOMETRIC FORM that reflects their role:
 *   ATLAS   → Star hexagon  (researcher radiating outward)
 *   CIPHER  → Diamond       (analytical precision, sharp edges)
 *   FORGE   → Torus knot    (creator weaving outputs together)
 *   BISHOP  → Shield cross  (compliance guardian)
 *   SØN     → Orb           (heir growing, learning)
 *   REGIS   → Crown         (sovereign, above all)
 *
 * Animation state is driven by real-time sub-task status:
 *   spawned   → idle drift
 *   working   → energetic spin + glow pulse
 *   complete  → calm rotation, green flash
 *   paid      → calm rotation, gold flash
 *   blocked   → red glow + stutter
 *   failed    → dim, stopped
 *   timed_out → dark + swept indicator
 *
 * Lead agent gets a crown overlay (⟡) and brighter emission.
 */

import { motion } from "framer-motion";

export type AgentStatus =
  | "spawned"
  | "working"
  | "complete"
  | "paid"
  | "blocked"
  | "failed"
  | "timed_out"
  | "sleeping";

interface Props {
  agentName: string;
  status: AgentStatus;
  color: string;
  size?: number;
  isLead?: boolean;
  reputation?: number;
}

// ── Per-agent SVG path definitions ────────────────────────────────────────────

function AtlasShape({ color, glow }: { color: string; glow: string }) {
  // Six-pointed star — researcher radiating outward
  return (
    <g>
      <polygon
        points="50,6 61,35 93,35 68,54 78,83 50,65 22,83 32,54 7,35 39,35"
        fill="none"
        stroke={color}
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      <polygon
        points="50,18 57,38 79,38 62,50 68,70 50,58 32,70 38,50 21,38 43,38"
        fill={glow}
        stroke={color}
        strokeWidth="1"
        strokeOpacity="0.5"
        strokeLinejoin="round"
      />
      {/* Central dot — data core */}
      <circle cx="50" cy="50" r="4" fill={color} />
    </g>
  );
}

function CipherShape({ color, glow }: { color: string; glow: string }) {
  // Diamond + concentric rings — analytical precision
  return (
    <g>
      <polygon
        points="50,8 86,50 50,92 14,50"
        fill={glow}
        stroke={color}
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      {/* Outer scan ring */}
      <polygon
        points="50,2 92,50 50,98 8,50"
        fill="none"
        stroke={color}
        strokeWidth="1"
        strokeOpacity="0.4"
        strokeDasharray="4 4"
        strokeLinejoin="round"
      />
      {/* Inner cross — analysis axes */}
      <line x1="50" y1="20" x2="50" y2="80" stroke={color} strokeWidth="1" strokeOpacity="0.6" />
      <line x1="20" y1="50" x2="80" y2="50" stroke={color} strokeWidth="1" strokeOpacity="0.6" />
    </g>
  );
}

function ForgeShape({ color, glow }: { color: string; glow: string }) {
  // Interlocked circles — synthesizer weaving outputs
  return (
    <g>
      {/* Three overlapping circles in triangle formation */}
      <circle cx="50" cy="30" r="22" fill={glow} stroke={color} strokeWidth="2.2" />
      <circle cx="34" cy="62" r="22" fill={glow} stroke={color} strokeWidth="2.2" />
      <circle cx="66" cy="62" r="22" fill={glow} stroke={color} strokeWidth="2.2" />
      {/* Connecting triangle outline */}
      <polygon
        points="50,14 17,68 83,68"
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeOpacity="0.5"
        strokeLinejoin="round"
      />
    </g>
  );
}

function BishopShape({ color, glow }: { color: string; glow: string }) {
  // Shield with internal cross — compliance guardian
  return (
    <g>
      {/* Shield body */}
      <path
        d="M50,8 L88,22 L88,58 L50,92 L12,58 L12,22 Z"
        fill={glow}
        stroke={color}
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      {/* Cross — compliance authority */}
      <line x1="50" y1="25" x2="50" y2="75" stroke={color} strokeWidth="3" strokeOpacity="0.8" />
      <line x1="28" y1="46" x2="72" y2="46" stroke={color} strokeWidth="3" strokeOpacity="0.8" />
    </g>
  );
}

function SonShape({ color, glow }: { color: string; glow: string }) {
  // Growing orb with rings — heir learning and expanding
  return (
    <g>
      {/* Outer growth ring */}
      <circle cx="50" cy="50" r="43" fill="none" stroke={color} strokeWidth="1.5" strokeOpacity="0.35" strokeDasharray="6 3" />
      {/* Middle learning ring */}
      <circle cx="50" cy="50" r="32" fill="none" stroke={color} strokeWidth="1.5" strokeOpacity="0.55" strokeDasharray="4 4" />
      {/* Core sphere */}
      <circle cx="50" cy="50" r="20" fill={glow} stroke={color} strokeWidth="2.5" />
    </g>
  );
}

function RegisShape({ color, glow }: { color: string; glow: string }) {
  // Crown — sovereign monarch, above all agents
  return (
    <g>
      {/* Crown base */}
      <rect x="12" y="62" width="76" height="20" rx="4" fill={glow} stroke={color} strokeWidth="2" />
      {/* Crown spikes */}
      <path
        d="M12,62 L12,30 L28,50 L50,18 L72,50 L88,30 L88,62 Z"
        fill={glow}
        stroke={color}
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      {/* Jewels */}
      <circle cx="50" cy="42" r="5" fill={color} />
      <circle cx="28" cy="55" r="3.5" fill={color} fillOpacity="0.7" />
      <circle cx="72" cy="55" r="3.5" fill={color} fillOpacity="0.7" />
    </g>
  );
}

// ── Animation presets per status ───────────────────────────────────────────────

function getAnimationProps(status: AgentStatus, isLead: boolean) {
  switch (status) {
    case "working":
      return {
        rotate: [0, 360],
        scale: [1, 1.06, 1],
        transition: {
          rotate: { duration: isLead ? 1.8 : 2.8, repeat: Infinity, ease: "linear" },
          scale:  { duration: 0.9, repeat: Infinity, ease: "easeInOut" },
        },
      };
    case "spawned":
      return {
        rotate: [0, 360],
        scale: 1,
        transition: {
          rotate: { duration: 8, repeat: Infinity, ease: "linear" },
        },
      };
    case "complete":
    case "paid":
      return {
        rotate: [0, 360],
        scale: 1,
        transition: {
          rotate: { duration: 6, repeat: Infinity, ease: "linear" },
        },
      };
    case "blocked":
      return {
        rotate: [-8, 8, -8],
        scale: [1, 0.96, 1],
        transition: {
          rotate: { duration: 0.25, repeat: Infinity, repeatType: "mirror" as const },
          scale:  { duration: 0.5,  repeat: Infinity, ease: "easeInOut" },
        },
      };
    case "failed":
    case "timed_out":
      return {
        rotate: 0,
        scale: 0.88,
        transition: { duration: 0.5 },
      };
    default:
      return { rotate: 0, scale: 1 };
  }
}

function getGlowColor(status: AgentStatus, baseColor: string): string {
  switch (status) {
    case "working":   return `${baseColor}28`;
    case "paid":      return "rgba(34,197,94,0.18)";
    case "complete":  return "rgba(34,197,94,0.12)";
    case "blocked":   return "rgba(239,68,68,0.18)";
    case "failed":
    case "timed_out": return "rgba(80,80,80,0.12)";
    default:          return `${baseColor}12`;
  }
}

function getStrokeColor(status: AgentStatus, baseColor: string): string {
  switch (status) {
    case "blocked":   return "#ef4444";
    case "failed":
    case "timed_out": return "#444";
    default:          return baseColor;
  }
}

function getOuterGlow(status: AgentStatus, baseColor: string, isLead: boolean): string {
  if (status === "working" && isLead) return `0 0 18px ${baseColor}90, 0 0 6px ${baseColor}60`;
  if (status === "working")           return `0 0 12px ${baseColor}60`;
  if (status === "blocked")           return `0 0 12px rgba(239,68,68,0.5)`;
  if (status === "paid")              return `0 0 10px rgba(34,197,94,0.4)`;
  return `0 0 6px ${baseColor}30`;
}

// ── Shape router ───────────────────────────────────────────────────────────────

function AgentShape({ agentName, color, glow }: { agentName: string; color: string; glow: string }) {
  switch (agentName) {
    case "ATLAS":  return <AtlasShape  color={color} glow={glow} />;
    case "CIPHER": return <CipherShape color={color} glow={glow} />;
    case "FORGE":  return <ForgeShape  color={color} glow={glow} />;
    case "BISHOP": return <BishopShape color={color} glow={glow} />;
    case "SØN":    return <SonShape    color={color} glow={glow} />;
    case "REGIS":  return <RegisShape  color={color} glow={glow} />;
    default:
      // Generic: octagon for unknown agents
      return (
        <polygon
          points="30,8 70,8 92,30 92,70 70,92 30,92 8,70 8,30"
          fill={glow}
          stroke={color}
          strokeWidth="2.5"
          strokeLinejoin="round"
        />
      );
  }
}

// ── Public component ───────────────────────────────────────────────────────────

export default function AgentAvatar({ agentName, status, color, size = 72, isLead = false, reputation = 3 }: Props) {
  const strokeColor = getStrokeColor(status, color);
  const glowFill    = getGlowColor(status, color);
  const outerGlow   = getOuterGlow(status, color, isLead);
  const anim        = getAnimationProps(status, isLead);

  // Reputation-scaled opacity: low rep → slightly dimmer
  const repOpacity  = 0.6 + (reputation / 5) * 0.4;

  return (
    <div
      style={{
        width: size,
        height: size,
        position: "relative",
        flexShrink: 0,
      }}
    >
      {/* Outer glow ring */}
      <div
        style={{
          position: "absolute",
          inset: -3,
          borderRadius: "50%",
          boxShadow: outerGlow,
          pointerEvents: "none",
        }}
      />

      {/* Animated SVG shape */}
      <motion.svg
        viewBox="0 0 100 100"
        width={size}
        height={size}
        style={{ opacity: repOpacity, overflow: "visible" }}
        animate={anim}
      >
        <AgentShape agentName={agentName} color={strokeColor} glow={glowFill} />
      </motion.svg>

      {/* Lead agent crown badge */}
      {isLead && (
        <div
          style={{
            position: "absolute",
            top: -8,
            right: -8,
            fontSize: 11,
            lineHeight: 1,
            background: "rgba(255,215,0,0.15)",
            border: "1px solid rgba(255,215,0,0.4)",
            borderRadius: 4,
            padding: "1px 3px",
            color: "#FFD700",
            fontFamily: "monospace",
            fontWeight: "bold",
          }}
          title="Lead agent — uses Claude"
        >
          ★
        </div>
      )}

      {/* Working pulse ring */}
      {status === "working" && (
        <motion.div
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "50%",
            border: `1px solid ${color}`,
            opacity: 0,
          }}
          animate={{ scale: [1, 1.6], opacity: [0.5, 0] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeOut" }}
        />
      )}
    </div>
  );
}
