"use client";

import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface ModeInfo {
  mode: "dry_run" | "live";
  live: boolean;
  description: string;
}

export default function DryRunBadge() {
  const [modeInfo, setModeInfo] = useState<ModeInfo | null>(null);
  const [toggling, setToggling] = useState(false);

  const fetchMode = useCallback(async () => {
    try {
      const r = await fetch(`${API}/mode`);
      if (r.ok) setModeInfo(await r.json());
    } catch {
      // Backend may not be running — show nothing
    }
  }, []);

  useEffect(() => {
    fetchMode();
    const interval = setInterval(fetchMode, 15000);
    return () => clearInterval(interval);
  }, [fetchMode]);

  const toggle = async () => {
    if (toggling) return;
    setToggling(true);
    try {
      const r = await fetch(`${API}/mode/toggle`, { method: "POST" });
      if (r.ok) setModeInfo(await r.json());
    } catch {
      // ignore
    } finally {
      setToggling(false);
    }
  };

  if (!modeInfo) return null;

  const isLive = modeInfo.live;

  return (
    <motion.button
      onClick={toggle}
      disabled={toggling}
      whileTap={{ scale: 0.95 }}
      title={modeInfo.description}
      className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-jb transition-all"
      style={{
        background: isLive ? "rgba(34,197,94,0.1)" : "rgba(245,158,11,0.1)",
        border: `1px solid ${isLive ? "rgba(34,197,94,0.3)" : "rgba(245,158,11,0.3)"}`,
        color: isLive ? "#22c55e" : "#f59e0b",
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: isLive ? "#22c55e" : "#f59e0b" }}
      />
      {toggling ? "…" : isLive ? "LIVE" : "DRY RUN"}
    </motion.button>
  );
}
