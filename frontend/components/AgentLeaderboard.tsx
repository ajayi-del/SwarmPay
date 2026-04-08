"use client";

import { useQuery } from "@tanstack/react-query";
import { AGENT_PERSONAS } from "@/lib/personas";

import { API_BASE } from "@/lib/api";

export default function AgentLeaderboard() {
  const { data: reputations } = useQuery<Record<string, number>>({
    queryKey: ["reputations"],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/analytics/reputation`);
      if (!r.ok) return {};
      return r.json();
    },
    refetchInterval: 5000,
  });

  if (!reputations || Object.keys(reputations).length === 0) return null;

  // Filter out any error responses
  if ("error" in reputations) return null;

  // Sort agents by reputation descending
  const sortedAgents = Object.entries(reputations)
    .filter(([name]) => name !== "REGIS") // Regis isn't a worker
    .sort(([, a], [, b]) => b - a);

  // Highest rep sets the max width for the bar chart
  const maxRep = Math.max(5.0, ...sortedAgents.map(([, r]) => r));

  return (
    <div
      style={{
        borderTop: "1px solid #111",
        background: "#050508",
        padding: "10px 14px",
        display: "flex",
        flexDirection: "column",
        gap: 10,
        flexShrink: 0,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontFamily: "monospace", fontSize: 8, color: "#eab308", letterSpacing: "0.2em" }}>
          👑 SOVEREIGNTY LEADERBOARD
        </span>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {sortedAgents.map(([name, rep], idx) => {
          const persona = AGENT_PERSONAS[name];
          if (!persona) return null;
          
          const barWidth = Math.min(100, (rep / maxRep) * 100);
          const color = rep >= 4.0 ? "#FFD700" : rep >= 3.0 ? "#f59e0b" : "#ef4444";

          return (
            <div key={name} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontFamily: "monospace", fontSize: 9, color: "#ccc" }}>
                  {idx === 0 && "🏆 "}{persona.flag} {name}
                </span>
                <span style={{ fontFamily: "monospace", fontSize: 9, color, fontWeight: 700 }}>
                  {rep.toFixed(1)} ★
                </span>
              </div>
              
              <div style={{ height: 4, background: "#111", borderRadius: 2, overflow: "hidden" }}>
                <div
                  style={{
                    width: `${barWidth}%`,
                    height: "100%",
                    background: color,
                    borderRadius: 2,
                    boxShadow: `0 0 6px ${color}80`,
                    transition: "width 0.5s ease-out"
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
      
      <div style={{ fontFamily: "monospace", fontSize: 7, color: "#444", textAlign: "right" }}>
        Dynamic Reputation Matrix · OWS Layer
      </div>
    </div>
  );
}
