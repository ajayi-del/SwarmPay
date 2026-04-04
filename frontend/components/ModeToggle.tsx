"use client";

import { motion } from "framer-motion";
import { useModeStore } from "@/lib/modeStore";

export default function ModeToggle() {
  const { mode, toggle } = useModeStore();
  const isOffice = mode === "office";

  return (
    <motion.button
      onClick={toggle}
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold font-jb select-none"
      style={{
        background: isOffice ? "rgba(37,99,235,0.12)" : "rgba(255,215,0,0.08)",
        border: isOffice
          ? "1px solid rgba(37,99,235,0.35)"
          : "1px solid rgba(255,215,0,0.25)",
        color: isOffice ? "#60a5fa" : "#FFD700",
        transition: "background 0.3s, border-color 0.3s, color 0.3s",
      }}
      title={isOffice ? "Switch to Kingdom mode" : "Switch to Office mode"}
    >
      <span>{isOffice ? "⚔️" : "🏢"}</span>
      <span>{isOffice ? "Kingdom" : "Office"}</span>
    </motion.button>
  );
}
