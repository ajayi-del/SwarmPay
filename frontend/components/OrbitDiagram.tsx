"use client";

/**
 * OrbitDiagram — CSS-only agent orbital diagram.
 * No canvas, no WebGL, no Three.js — pure CSS keyframe animations.
 * Each agent orbits REGIS at a unique speed.
 */

import type { SubTask } from "@/lib/api";
import { AGENT_PERSONAS } from "@/lib/personas";

const STATUS_COLOR: Record<string, string> = {
  working:   "#f59e0b",
  spawned:   "#6c63ff",
  complete:  "#22c55e",
  paid:      "#22c55e",
  blocked:   "#ef4444",
  failed:    "#555",
  timed_out: "#333",
};

// Orbital period in seconds per agent (personality-matched)
const AGENT_PERIOD: Record<string, number> = {
  FORGE:  6,   // industrial, fast
  ATLAS:  8,   // methodical
  CIPHER: 12,  // cryptic, medium
  "SØN":  15,  // nordic, slow
  BISHOP: 20,  // regal, stately
};

// Orbit radii in px — spread agents across rings
const ORBIT_RADII = [44, 58, 72, 86, 100];

interface Props {
  subTasks: SubTask[];
}

export default function OrbitDiagram({ subTasks }: Props) {
  if (!subTasks.length) return null;

  const SIZE = 240;
  const C = SIZE / 2; // center

  return (
    <div style={{ position: "relative", width: SIZE, height: SIZE }}>
      <style>{`
        @keyframes sp-orbit-cw  { to { transform: rotate( 360deg); } }
        @keyframes sp-orbit-ccw { to { transform: rotate(-360deg); } }
      `}</style>

      {/* Orbit ring for each agent */}
      {subTasks.map((_, i) => {
        const r = ORBIT_RADII[Math.min(i, ORBIT_RADII.length - 1)];
        return (
          <div
            key={`ring-${i}`}
            style={{
              position: "absolute",
              borderRadius: "50%",
              border: "1px dashed #ffffff07",
              width: r * 2,
              height: r * 2,
              top: C - r,
              left: C - r,
              pointerEvents: "none",
            }}
          />
        );
      })}

      {/* REGIS core */}
      <div
        style={{
          position: "absolute",
          width: 30,
          height: 30,
          top: C - 15,
          left: C - 15,
          borderRadius: "50%",
          background: "#110e00",
          border: "1.5px solid #F59E0B",
          boxShadow: "0 0 8px rgba(245,158,11,0.25)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "monospace",
          fontSize: 7,
          color: "#F59E0B",
          letterSpacing: "0.05em",
          zIndex: 10,
        }}
      >
        REG
      </div>

      {/* Agent dots — double-rotation orbit trick */}
      {subTasks.map((st, i) => {
        const persona = AGENT_PERSONAS[st.agent_id];
        const dotColor = persona?.roleColor ?? "#6c63ff";
        const statusColor = STATUS_COLOR[st.status] ?? dotColor;
        const period = AGENT_PERIOD[st.agent_id] ?? 10;
        const radius = ORBIT_RADII[Math.min(i, ORBIT_RADII.length - 1)];
        const DOT = 14;
        const isActive = st.status === "working" || st.status === "spawned";

        return (
          // Outer wrapper: sits at center, rotates clockwise
          <div
            key={st.id}
            title={`${st.agent_id} · ${st.status}`}
            style={{
              position: "absolute",
              top: C,
              left: C,
              width: 0,
              height: 0,
              animation: `sp-orbit-cw ${period}s linear infinite`,
            }}
          >
            {/* Inner wrapper: counter-rotates to keep dot upright, translated out to radius */}
            <div
              style={{
                position: "absolute",
                top: -DOT / 2,
                left: radius - DOT / 2,
                width: DOT,
                height: DOT,
                animation: `sp-orbit-ccw ${period}s linear infinite`,
              }}
            >
              {/* Pulse ring for active agents */}
              {isActive && (
                <div
                  style={{
                    position: "absolute",
                    inset: -4,
                    borderRadius: "50%",
                    border: `1px solid ${statusColor}`,
                    opacity: 0.4,
                    animation: "animate-status-pulse 1.5s ease-in-out infinite",
                  }}
                />
              )}
              {/* Agent dot */}
              <div
                style={{
                  width: DOT,
                  height: DOT,
                  borderRadius: "50%",
                  background: dotColor + "20",
                  border: `1.5px solid ${statusColor}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: "monospace",
                  fontSize: 6,
                  fontWeight: 700,
                  color: dotColor,
                }}
              >
                {st.agent_id.slice(0, 2)}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
