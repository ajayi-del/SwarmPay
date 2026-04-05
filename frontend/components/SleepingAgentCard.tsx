"use client";

import { motion } from "framer-motion";
import { AGENT_PERSONAS } from "@/lib/personas";
import AgentAvatar from "@/components/AgentAvatar";

interface Props {
  agentId: string;
}

export default function SleepingAgentCard({ agentId }: Props) {
  const persona = AGENT_PERSONAS[agentId];
  if (!persona) return null;

  const rc = persona.roleColor;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="relative rounded-xl border border-white/5 bg-[#0d0d14]/60 p-4 overflow-hidden"
      style={{ borderColor: `${rc}18` }}
    >
      {/* Dim overlay to signal inactive */}
      <div className="absolute inset-0 bg-[#08080f]/50 rounded-xl pointer-events-none" />

      <div className="relative flex items-center gap-3 opacity-40">
        {/* Avatar — slow breathing pulse when sleeping */}
        <motion.div
          animate={{ opacity: [0.5, 0.8, 0.5] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        >
          <AgentAvatar agentName={agentId} status="sleeping" color={rc} size={40} />
        </motion.div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-white/70 tracking-wide">
              {persona.flag} {agentId}
            </span>
            <span
              className="text-[10px] px-1.5 py-0.5 rounded font-medium"
              style={{ backgroundColor: `${rc}18`, color: rc }}
            >
              {persona.role}
            </span>
          </div>
          <p className="text-[11px] text-white/30 mt-0.5">{persona.city}</p>
        </div>

        {/* Sleeping indicator */}
        <motion.div
          animate={{ opacity: [0.3, 0.7, 0.3] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
          className="text-[11px] text-white/30 font-mono"
        >
          zzz
        </motion.div>
      </div>

      {/* Subtle bottom rule with role color */}
      <div
        className="absolute bottom-0 left-0 right-0 h-[1px] opacity-10"
        style={{ background: rc }}
      />
    </motion.div>
  );
}
