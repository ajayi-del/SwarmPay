"use client";

/**
 * BetsPanel — Myriad Prediction Markets
 *
 * Shows active agent prediction markets:
 *   CIPHER vs ATLAS vs SØN — who's right about yield?
 * Auto-polls /integrations/myriad/markets every 15s.
 */

import { useQuery } from "@tanstack/react-query";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Bet {
  agent: string;
  outcome: "YES" | "NO";
  amount_sol: number;
  placed_at?: string;
}

interface Market {
  id: string;
  question: string;
  resolution_date: string;
  status: "open" | "resolved";
  bets: Bet[];
  mock?: boolean;
}

const AGENT_COLORS: Record<string, string> = {
  CIPHER: "#a855f7",
  ATLAS:  "#3b82f6",
  "SØN":  "#22c55e",
  FORGE:  "#f59e0b",
  BISHOP: "#ef4444",
  REGIS:  "#F59E0B",
};

function AgentBet({ bet }: { bet: Bet }) {
  const color = AGENT_COLORS[bet.agent] ?? "#888";
  const isYes = bet.outcome === "YES";
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 0",
      }}
    >
      <span style={{ fontFamily: "monospace", fontSize: 9, color, minWidth: 52 }}>
        {bet.agent}
      </span>
      <span
        style={{
          fontFamily: "monospace",
          fontSize: 8,
          color: isYes ? "#22c55e" : "#ef4444",
          background: isYes ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
          border: `1px solid ${isYes ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
          borderRadius: 3,
          padding: "1px 5px",
          minWidth: 26,
          textAlign: "center",
        }}
      >
        {bet.outcome}
      </span>
      <span style={{ fontFamily: "monospace", fontSize: 8, color: "#9945FF" }}>
        ◎{bet.amount_sol.toFixed(5)}
      </span>
    </div>
  );
}

function MarketCard({ market }: { market: Market }) {
  const now = Date.now();
  const resDate = new Date(market.resolution_date).getTime();
  const hoursLeft = Math.max(0, Math.floor((resDate - now) / 3_600_000));
  const bets = market.bets ?? [];

  return (
    <div
      style={{
        background: "rgba(108,99,255,0.06)",
        border: "1px solid rgba(108,99,255,0.18)",
        borderRadius: 8,
        padding: "10px 12px",
        marginBottom: 8,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 8, marginBottom: 6 }}>
        <div>
          <span
            style={{
              display: "inline-block",
              fontFamily: "monospace",
              fontSize: 8,
              color: "#F97316",
              background: "rgba(249,115,22,0.1)",
              border: "1px solid rgba(249,115,22,0.25)",
              borderRadius: 3,
              padding: "1px 5px",
              letterSpacing: "0.08em",
              marginBottom: 4,
            }}
          >
            ⚔ OPEN{market.mock ? " · MOCK" : ""}
          </span>
          <p
            style={{
              fontFamily: "monospace",
              fontSize: 9,
              color: "#ddd",
              margin: 0,
              lineHeight: 1.5,
            }}
          >
            {market.question}
          </p>
        </div>
      </div>

      {/* Agent bets */}
      {bets.length > 0 ? (
        <div style={{ marginBottom: 6 }}>
          {bets.map((b, i) => <AgentBet key={i} bet={b} />)}
        </div>
      ) : (
        <p style={{ fontFamily: "monospace", fontSize: 8, color: "#444", margin: "4px 0" }}>
          No bets placed yet
        </p>
      )}

      {/* Footer */}
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <span style={{ fontFamily: "monospace", fontSize: 7, color: "#555" }}>
          Resolves: {new Date(market.resolution_date).toLocaleDateString("en-GB")}
        </span>
        {hoursLeft > 0 && (
          <span style={{ fontFamily: "monospace", fontSize: 7, color: "#444" }}>
            · {hoursLeft}hr remaining
          </span>
        )}
      </div>
    </div>
  );
}

export default function BetsPanel() {
  const { data, isLoading } = useQuery({
    queryKey: ["myriad-markets"],
    queryFn: async (): Promise<{ markets: Market[]; total: number; mode: string }> => {
      const r = await fetch(`${API}/integrations/myriad/markets`);
      if (!r.ok) return { markets: [], total: 0, mode: "mock" };
      return r.json();
    },
    refetchInterval: 15_000,
    staleTime: 10_000,
  });

  const markets = data?.markets ?? [];
  const isLive  = data?.mode === "live";

  if (isLoading) {
    return (
      <div style={{ padding: "16px 14px", fontFamily: "monospace", fontSize: 9, color: "#333" }}>
        Loading prediction markets…
      </div>
    );
  }

  return (
    <div style={{ padding: "12px 14px", height: "100%", overflowY: "auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <span style={{ fontFamily: "monospace", fontSize: 8, color: "#F97316", letterSpacing: "0.2em" }}>
          ⚔ PREDICTION MARKETS
        </span>
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 7,
            color: isLive ? "#22c55e" : "#555",
            background: isLive ? "rgba(34,197,94,0.1)" : "transparent",
            border: `1px solid ${isLive ? "rgba(34,197,94,0.3)" : "#222"}`,
            borderRadius: 3,
            padding: "1px 5px",
          }}
        >
          {isLive ? "● LIVE API" : "● MOCK"}
        </span>
      </div>

      <p style={{ fontFamily: "monospace", fontSize: 7, color: "#444", marginBottom: 10 }}>
        Agents bet on their own intelligence · CIPHER opens · ATLAS + SØN position
      </p>

      {markets.length === 0 ? (
        <div
          style={{
            padding: "20px 0",
            textAlign: "center",
            fontFamily: "monospace",
            fontSize: 9,
            color: "#333",
            letterSpacing: "0.06em",
          }}
        >
          No active markets · CIPHER scans every 15min
          <br />
          <span style={{ fontSize: 8, color: "#222", display: "block", marginTop: 6 }}>
            Markets open when yield score &gt; 7.0/10
          </span>
        </div>
      ) : (
        markets.map((m) => <MarketCard key={m.id} market={m} />)
      )}
    </div>
  );
}
