"use client";

/**
 * TokenEconomy — LLM usage panel for the left audit sidebar.
 * Shows pie chart + per-agent token breakdown.
 * Polls /analytics/tokens?task_id=xxx every 8 seconds.
 */

import { useQuery } from "@tanstack/react-query";
import { useSwarmStore } from "@/lib/store";

import { API_BASE } from "@/lib/api";

// Provider display config
const PROVIDER_CONFIG: Record<string, { label: string; color: string; free: boolean }> = {
  deepseek:  { label: "DeepSeek",  color: "#9945FF", free: false },
  groq:      { label: "Groq",      color: "#3B82F6", free: true  },
  anthropic: { label: "Anthropic", color: "#F97316", free: false },
  other:     { label: "Other",     color: "#444",    free: true  },
};

const AGENT_FLAGS: Record<string, string> = {
  ATLAS: "🇩🇪", CIPHER: "🇯🇵", FORGE: "🇳🇬", BISHOP: "🇻🇦", "SØN": "🇸🇪", REGIS: "🏴",
};

interface TokenSummary {
  total_tokens: number;
  total_cost_usd: number;
  total_cost_sol: number;
  by_provider: Record<string, { tokens: number; cost_usd: number; free: boolean }>;
  by_agent: { agent: string; model: string; tokens: number; cost_usd: number; cost_sol: number }[];
}

// ── Simple SVG donut chart ─────────────────────────────────────────────────────
function DonutChart({ data, total }: { data: { value: number; color: string }[]; total: number }) {
  const R = 32;
  const cx = 40;
  const cy = 40;
  let cumAngle = -Math.PI / 2;

  const slices = data.map((d) => {
    const fraction = total > 0 ? d.value / total : 0;
    const start = cumAngle;
    cumAngle += fraction * Math.PI * 2;
    const end = cumAngle;
    return { ...d, fraction, start, end };
  });

  return (
    <svg width={80} height={80} viewBox="0 0 80 80" style={{ flexShrink: 0 }}>
      {slices.map((s, i) => {
        if (s.fraction <= 0.001) return null;
        if (s.fraction >= 0.999) {
          return (
            <circle key={i} cx={cx} cy={cy} r={R}
              fill="none" stroke={s.color} strokeWidth={14} opacity={0.85} />
          );
        }
        const x1 = cx + R * Math.cos(s.start);
        const y1 = cy + R * Math.sin(s.start);
        const x2 = cx + R * Math.cos(s.end);
        const y2 = cy + R * Math.sin(s.end);
        const largeArc = s.fraction > 0.5 ? 1 : 0;
        // Stroke-based arc (simpler than path fill)
        return (
          <path
            key={i}
            d={`M ${x1} ${y1} A ${R} ${R} 0 ${largeArc} 1 ${x2} ${y2}`}
            fill="none"
            stroke={s.color}
            strokeWidth={14}
            opacity={0.85}
          />
        );
      })}
      {/* Center */}
      <circle cx={cx} cy={cy} r={R - 7} fill="#080808" />
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize={7} fill="#555" fontFamily="monospace">TOKENS</text>
      <text x={cx} y={cy + 6} textAnchor="middle" fontSize={9} fill="#aaa" fontFamily="monospace" fontWeight="bold">
        {total >= 1000 ? `${(total / 1000).toFixed(1)}k` : String(total)}
      </text>
    </svg>
  );
}

// ── Provider badge ─────────────────────────────────────────────────────────────
function ProviderBadge({ model }: { model: string }) {
  let provider = "other";
  if (model.startsWith("llama") || model.startsWith("gemma") || model.startsWith("mixtral")) provider = "groq";
  else if (model.startsWith("deepseek")) provider = "deepseek";
  else if (model.startsWith("claude")) provider = "anthropic";
  const cfg = PROVIDER_CONFIG[provider] ?? PROVIDER_CONFIG.other;
  const short = provider === "deepseek" ? "DS" : provider === "groq" ? "GQ" : provider === "anthropic" ? "AN" : "??";
  return (
    <span
      style={{
        fontFamily: "monospace",
        fontSize: 7,
        padding: "1px 4px",
        borderRadius: 3,
        background: `${cfg.color}18`,
        color: cfg.color,
        border: `1px solid ${cfg.color}30`,
        flexShrink: 0,
      }}
    >
      {short}
    </span>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function TokenEconomy() {
  const { taskId } = useSwarmStore();

  const { data } = useQuery<TokenSummary>({
    queryKey: ["token-economy", taskId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/analytics/tokens?task_id=${taskId ?? ""}`);
      if (!r.ok) throw new Error("token analytics unavailable");
      return r.json();
    },
    enabled: !!taskId,
    refetchInterval: 8_000,
    staleTime: 6_000,
  });

  if (!taskId || !data || data.total_tokens === 0) {
    return (
      <div
        style={{
          padding: "10px 14px",
          borderTop: "1px solid #111",
          fontFamily: "monospace",
          fontSize: 8,
          color: "#2a2a2a",
          letterSpacing: "0.1em",
        }}
      >
        🧠 LLM USAGE — Awaiting task…
      </div>
    );
  }

  const providerEntries = Object.entries(data.by_provider ?? {}).filter(([, v]) => v.tokens > 0);
  const chartData = providerEntries.map(([key, v]) => ({
    value: v.tokens,
    color: (PROVIDER_CONFIG[key] ?? PROVIDER_CONFIG.other).color,
  }));

  const maxAgentTokens = Math.max(...(data.by_agent ?? []).map((a) => a.tokens), 1);

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
      {/* Section header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontFamily: "monospace", fontSize: 8, color: "#555", letterSpacing: "0.2em" }}>
          🧠 LLM USAGE — THIS SESSION
        </span>
        <span style={{ fontFamily: "monospace", fontSize: 7, color: "#333" }}>
          ${data.total_cost_usd.toFixed(5)}
        </span>
      </div>

      {/* Pie chart + legend row */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <DonutChart data={chartData} total={data.total_tokens} />
        {/* Legend */}
        <div style={{ display: "flex", flexDirection: "column", gap: 4, flex: 1 }}>
          {providerEntries.map(([key, v]) => {
            const cfg = PROVIDER_CONFIG[key] ?? PROVIDER_CONFIG.other;
            return (
              <div key={key} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: cfg.color, flexShrink: 0 }} />
                <span style={{ fontFamily: "monospace", fontSize: 8, color: cfg.color, flex: 1 }}>
                  {cfg.label}
                </span>
                <span style={{ fontFamily: "monospace", fontSize: 8, color: "#555" }}>
                  {v.tokens.toLocaleString()}
                </span>
                <span style={{ fontFamily: "monospace", fontSize: 7, color: cfg.free ? "#22c55e" : "#888" }}>
                  {cfg.free ? "FREE" : `$${v.cost_usd.toFixed(5)}`}
                </span>
              </div>
            );
          })}
          {/* Total */}
          <div style={{ borderTop: "1px solid #111", paddingTop: 4, display: "flex", justifyContent: "space-between" }}>
            <span style={{ fontFamily: "monospace", fontSize: 7, color: "#444" }}>
              {data.total_tokens.toLocaleString()} tokens
            </span>
            <span style={{ fontFamily: "monospace", fontSize: 7, color: data.total_cost_usd > 0 ? "#9945FF" : "#333" }}>
              {data.total_cost_sol > 0 ? `◎${data.total_cost_sol.toFixed(7)}` : "FREE"}
            </span>
          </div>
        </div>
      </div>

      {/* Per-agent breakdown */}
      {(data.by_agent ?? []).length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
          {data.by_agent.map((entry) => {
            const barWidth = Math.round((entry.tokens / maxAgentTokens) * 100);
            const providerKey = entry.model.startsWith("llama") || entry.model.startsWith("gemma")
              ? "groq" : entry.model.startsWith("deepseek") ? "deepseek"
              : entry.model.startsWith("claude") ? "anthropic" : "other";
            const color = (PROVIDER_CONFIG[providerKey] ?? PROVIDER_CONFIG.other).color;

            return (
              <div key={entry.agent} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ fontFamily: "monospace", fontSize: 7, color: "#555", width: 12, flexShrink: 0 }}>
                  {AGENT_FLAGS[entry.agent] ?? "🤖"}
                </span>
                <span style={{ fontFamily: "monospace", fontSize: 8, color: "#666", width: 46, flexShrink: 0 }}>
                  {entry.agent}
                </span>
                <ProviderBadge model={entry.model} />
                {/* Token bar */}
                <div style={{ flex: 1, height: 4, background: "#111", borderRadius: 2, overflow: "hidden" }}>
                  <div style={{ width: `${barWidth}%`, height: "100%", background: color, borderRadius: 2 }} />
                </div>
                <span style={{ fontFamily: "monospace", fontSize: 7, color: "#444", flexShrink: 0, textAlign: "right", minWidth: 36 }}>
                  {entry.tokens.toLocaleString()}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
