"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { AGENT_SKILLS, TIER_COLORS, type Skill, type SkillTier } from "@/lib/skills";

const TIER_LABELS: Record<SkillTier, string> = {
  core:      "Core",
  financial: "Financial",
  advanced:  "Advanced",
  business:  "Business",
};

const AGENT_ORDER = ["ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"];

function SkillBadge({ skill }: { skill: Skill }) {
  const [open, setOpen] = useState(false);
  const color = TIER_COLORS[skill.tier];

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-md px-2 py-0.5 text-[10px] font-jb transition-all"
        style={{
          background: skill.active ? `${color}18` : "#ffffff06",
          color: skill.active ? color : "#444",
          border: `1px solid ${skill.active ? color + "35" : "#ffffff10"}`,
          opacity: skill.active ? 1 : 0.5,
          cursor: "pointer",
        }}
      >
        <span style={{ fontSize: 7 }}>●</span>
        {skill.name}
        {skill.cost !== undefined && (
          <span style={{ color: "#22c55e", fontSize: 9 }}>
            ${skill.cost}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.96 }}
            transition={{ duration: 0.15 }}
            className="absolute bottom-full left-0 mb-1.5 z-50 rounded-lg p-2.5 text-[10px] font-jb w-52"
            style={{
              background: "var(--surface)",
              border: `1px solid ${color}35`,
              boxShadow: `0 8px 24px rgba(0,0,0,0.4), 0 0 0 1px ${color}15`,
            }}
          >
            <p className="font-semibold mb-1" style={{ color }}>
              {skill.name}
            </p>
            <p style={{ color: "var(--text-muted)", lineHeight: 1.5 }}>
              {skill.description}
            </p>
            {skill.tool && (
              <p className="mt-1.5" style={{ color: "#555" }}>
                Tool: <span style={{ color: "#888" }}>{skill.tool}</span>
              </p>
            )}
            <div className="flex items-center gap-1.5 mt-1.5">
              <span
                className="px-1.5 py-0.5 rounded text-[9px]"
                style={{ background: `${color}18`, color }}
              >
                {TIER_LABELS[skill.tier]}
              </span>
              <span
                className="px-1.5 py-0.5 rounded text-[9px]"
                style={{
                  background: skill.active ? "#22c55e18" : "#ef444418",
                  color: skill.active ? "#22c55e" : "#ef4444",
                }}
              >
                {skill.active ? "Active" : "Locked"}
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function AgentSkillRow({ agentId }: { agentId: string }) {
  const set = AGENT_SKILLS[agentId];
  if (!set) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-xs font-bold font-jb" style={{ color: "var(--text)", minWidth: 52 }}>
          {agentId}
        </span>
        <span className="text-[10px]" style={{ color: "var(--text-dim)" }}>
          {set.role}
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5 pl-1">
        {set.skills.map((skill) => (
          <SkillBadge key={skill.id} skill={skill} />
        ))}
      </div>
    </div>
  );
}

export default function SkillsPanel() {
  const [expanded, setExpanded] = useState(false);

  const totalActive = AGENT_ORDER.reduce(
    (sum, id) => sum + (AGENT_SKILLS[id]?.skills.filter((s) => s.active).length ?? 0),
    0
  );
  const totalSkills = AGENT_ORDER.reduce(
    (sum, id) => sum + (AGENT_SKILLS[id]?.skills.length ?? 0),
    0
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-2xl"
      style={{
        background: "var(--surface)",
        border: "1px solid #a78bfa22",
        boxShadow: "0 0 24px rgba(167,139,250,0.04)",
      }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3.5"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold" style={{ color: "#a78bfa" }}>
            Agent Skills Registry
          </span>
          <span
            className="text-[10px] px-2 py-0.5 rounded-full font-jb"
            style={{ background: "#a78bfa18", color: "#a78bfa", border: "1px solid #a78bfa30" }}
            title="Skills unlock as agents complete tasks"
          >
            {totalActive}/{totalSkills} active
          </span>
          <span
            className="text-[9px] font-jb hidden sm:inline"
            style={{ color: "#444" }}
          >
            Skills unlock as agents complete tasks
          </span>
        </div>
        <div className="flex items-center gap-3">
          {/* Tier legend */}
          <div className="hidden sm:flex items-center gap-2">
            {(Object.entries(TIER_COLORS) as [SkillTier, string][]).map(([tier, color]) => (
              <span key={tier} className="flex items-center gap-1 text-[9px] font-jb" style={{ color: "#555" }}>
                <span style={{ color, fontSize: 7 }}>●</span>
                {TIER_LABELS[tier]}
              </span>
            ))}
          </div>
          <span className="text-xs" style={{ color: "#555" }}>
            {expanded ? "▲" : "▼"}
          </span>
        </div>
      </button>

      {/* Skills grid */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            style={{ overflow: "hidden" }}
          >
            <div
              className="px-5 pb-4 space-y-4 border-t"
              style={{ borderColor: "#a78bfa18" }}
            >
              <p className="text-[10px] pt-3" style={{ color: "var(--text-dim)" }}>
                Click any skill badge to inspect its binding. Active skills are wired to live tools.
                Locked skills are roadmap items.
              </p>
              {AGENT_ORDER.map((id) => (
                <AgentSkillRow key={id} agentId={id} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
