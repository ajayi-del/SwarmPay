"use client";

/**
 * StatusBar — compact system health indicator for the top bar.
 * Polls /health every 60s. Green dot = ok, red = error/degraded, amber = no key.
 * Shows: PB · ANT · SOL · TG
 */

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { API_BASE } from "@/lib/api";

interface HealthResponse {
  status: string;
  pocketbase?: string;
  anthropic?: string;
  deepseek?: string;
  solana?: string;
  telegram?: string;
  moonpay?: string;
}

const CHECKS: { key: keyof HealthResponse; label: string }[] = [
  { key: "pocketbase", label: "PB" },
  { key: "anthropic",  label: "ANT" },
  { key: "solana",     label: "SOL" },
  { key: "telegram",   label: "TG" },
];

function dotColor(val: string | undefined): string {
  if (!val) return "#F59E0B"; // Amber when offline/unreachable
  if (val === "ok") return "#22c55e";
  if (val === "no_key" || val === "no_token") return "#F59E0B";
  return "#ef4444";
}

export default function StatusBar() {
  const { data, isError } = useQuery<HealthResponse>({
    queryKey: ["health"],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/health`);
      if (!r.ok) throw new Error("health check failed");
      return r.json();
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });

  const overall = isError ? "error" : data?.status ?? "unknown";
  const overallColor = overall === "healthy" ? "#22c55e" : overall === "degraded" ? "#F59E0B" : "#ef4444";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        fontFamily: "monospace",
        fontSize: 9,
        letterSpacing: "0.08em",
      }}
    >
      {/* Overall pulse */}
      <motion.span
        animate={overall === "healthy" ? { opacity: [1, 0.3, 1] } : { opacity: 1 }}
        transition={{ duration: 2, repeat: Infinity }}
        style={{
          width: 5,
          height: 5,
          borderRadius: "50%",
          background: overallColor,
          display: "inline-block",
          flexShrink: 0,
        }}
      />

      {/* Individual service dots */}
      {CHECKS.map(({ key, label }) => {
        const val = data?.[key];
        const color = dotColor(val);
        const tip = val ?? (isError ? "offline" : "unknown");
        const isOffline = !val && isError;
        return (
          <span
            key={key}
            title={`${label}: ${tip}`}
            style={{ display: "flex", alignItems: "center", gap: 3, color: "#444", cursor: "default" }}
          >
            <span
              style={{
                width: 4,
                height: 4,
                borderRadius: "50%",
                background: color,
                display: "inline-block",
                flexShrink: 0,
              }}
            />
            <span style={{ color: val === "ok" ? "#555" : (isOffline ? color : (val ? color : "#333")) }}>
              {isOffline ? `${label}/OFF` : label}
            </span>
          </span>
        );
      })}
    </div>
  );
}
