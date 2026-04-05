"use client";

import { AGENT_SKILLS, TIER_COLORS, type SkillTier } from "@/lib/skills";
import { AGENT_PERSONAS } from "@/lib/personas";

const AGENT_ORDER = ["ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"];

export default function SkillsCompact() {
  return (
    <div
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: "12px 14px",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 200,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 8,
          color: "#555",
          letterSpacing: "0.25em",
          textTransform: "uppercase",
          marginBottom: 10,
          paddingBottom: 6,
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}
      >
        Skills Registry
      </div>

      {/* Agent skill rows — scrollable */}
      <div style={{ overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
        {AGENT_ORDER.map((id) => {
          const set = AGENT_SKILLS[id];
          const persona = AGENT_PERSONAS[id];
          if (!set || !persona) return null;
          return (
            <div key={id}>
              {/* Agent header */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 5,
                  marginBottom: 4,
                }}
              >
                <span style={{ fontSize: 10 }}>{persona.flag}</span>
                <span
                  style={{
                    fontFamily: "monospace",
                    fontSize: 9,
                    fontWeight: 700,
                    color: persona.roleColor,
                    letterSpacing: "0.04em",
                  }}
                >
                  {id}
                </span>
              </div>
              {/* Skills pills */}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 3, paddingLeft: 2 }}>
                {set.skills.map((skill) => {
                  const color = TIER_COLORS[skill.tier as SkillTier];
                  return (
                    <span
                      key={skill.id}
                      title={skill.description}
                      style={{
                        fontSize: 8,
                        fontFamily: "monospace",
                        padding: "1px 5px",
                        borderRadius: 4,
                        background: skill.active ? `${color}18` : "#ffffff05",
                        color: skill.active ? color : "#333",
                        border: `1px solid ${skill.active ? color + "30" : "#ffffff08"}`,
                        opacity: skill.active ? 1 : 0.35,
                        cursor: "default",
                      }}
                    >
                      {skill.name}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div
        style={{
          borderTop: "1px solid var(--border)",
          marginTop: 8,
          paddingTop: 6,
          flexShrink: 0,
        }}
      >
        {(() => {
          const totalActive = AGENT_ORDER.reduce(
            (s, id) => s + (AGENT_SKILLS[id]?.skills.filter((sk) => sk.active).length ?? 0),
            0
          );
          const totalAll = AGENT_ORDER.reduce(
            (s, id) => s + (AGENT_SKILLS[id]?.skills.length ?? 0),
            0
          );
          return (
            <span style={{ fontFamily: "monospace", fontSize: 8, color: "#444" }}>
              {totalActive}/{totalAll} skills active
            </span>
          );
        })()}
      </div>
    </div>
  );
}
