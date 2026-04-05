"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { AGENT_SKILLS, TIER_COLORS, type SkillTier } from "@/lib/skills";
import { AGENT_PERSONAS } from "@/lib/personas";

const AGENT_ORDER = ["ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"];

export default function SkillsCompact() {
  const [collapsed, setCollapsed] = useState(false);

  const totalActive = AGENT_ORDER.reduce(
    (s, id) => s + (AGENT_SKILLS[id]?.skills.filter((sk) => sk.active).length ?? 0),
    0
  );
  const totalAll = AGENT_ORDER.reduce(
    (s, id) => s + (AGENT_SKILLS[id]?.skills.length ?? 0),
    0
  );

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
        minHeight: collapsed ? 0 : 200,
        overflow: "hidden",
        transition: "min-height 0.2s",
      }}
    >
      {/* Header — always visible, clickable to toggle */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: "none",
          border: "none",
          cursor: "pointer",
          padding: 0,
          marginBottom: collapsed ? 0 : 10,
          paddingBottom: collapsed ? 0 : 6,
          borderBottom: collapsed ? "none" : "1px solid var(--border)",
          width: "100%",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 8,
            color: "#555",
            letterSpacing: "0.25em",
            textTransform: "uppercase",
          }}
        >
          Skills {totalActive}/{totalAll}
        </span>
        <motion.span
          animate={{ rotate: collapsed ? 0 : 180 }}
          transition={{ duration: 0.2 }}
          style={{ fontSize: 9, color: "#444", lineHeight: 1 }}
        >
          ▲
        </motion.span>
      </button>

      {/* Collapsible content */}
      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            key="skills-content"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            style={{ overflow: "hidden", flex: 1, display: "flex", flexDirection: "column" }}
          >
            {/* Agent skill rows */}
            <div style={{ overflowY: "auto", flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
              {AGENT_ORDER.map((id) => {
                const set = AGENT_SKILLS[id];
                const persona = AGENT_PERSONAS[id];
                if (!set || !persona) return null;
                return (
                  <div key={id}>
                    {/* Agent header */}
                    <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 4 }}>
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
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
