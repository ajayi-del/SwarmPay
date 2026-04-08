"use client";

/**
 * X402Panel — dedicated panel showing x402 payment-rail transactions.
 *
 * Shows: agent, service inferred from policy_reason, amount in ◎ SOL,
 * Solana tx hash linking to Solscan devnet, and relative latency.
 */

import { motion } from "framer-motion";
import type { Payment, SubTask, X402Call } from "@/lib/api";
import { useSolRate } from "@/lib/useSolRate";

interface Props {
  payments: Payment[];
  subTasks: SubTask[];
  x402Calls?: X402Call[];
}

const SOLSCAN_BASE = "https://solscan.io/tx";

function agentName(walletId: string, subTasks: SubTask[]): string {
  const st = subTasks.find((s) => s.wallet_id === walletId);
  return st?.agent_id ?? walletId.slice(0, 6) + "…";
}

function inferService(policyReason: string): string {
  const r = policyReason.toLowerCase();
  if (r.includes("oracle") || r.includes("price")) return "Price Oracle";
  if (r.includes("ipfs") || r.includes("storage")) return "IPFS Storage";
  if (r.includes("rpc") || r.includes("solana")) return "Solana RPC";
  if (r.includes("compute") || r.includes("llm") || r.includes("inference")) return "LLM Inference";
  if (r.includes("search") || r.includes("serp")) return "Web Search";
  if (r.includes("data") || r.includes("feed")) return "Data Feed";
  if (r.includes("x402") || r.includes("X402")) return "x402 Service";
  return "Paid Service";
}

function relativeTime(isoDate: string): string {
  const diffMs = Date.now() - new Date(isoDate).getTime();
  const s = Math.floor(diffMs / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

export default function X402Panel({ payments, subTasks, x402Calls = [] }: Props) {
  const { toSol } = useSolRate();

  // Filter ONLY true on-chain signatures (no mocks)
  const x402Payments = payments.filter(
    (p) =>
      p.status === "signed" &&
      p.tx_hash &&
      p.tx_hash.length >= 80 // Base58 solana signatures are ~87-88 chars
  );

  if (x402Payments.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{
        background: "#07070d",
        border: "1px solid rgba(153,69,255,0.25)",
        borderRadius: 10,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "8px 14px",
          borderBottom: "1px solid rgba(153,69,255,0.15)",
          background: "rgba(153,69,255,0.06)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: "#9945FF",
              display: "inline-block",
              boxShadow: "0 0 6px rgba(153,69,255,0.6)",
            }}
          />
          <span
            style={{
              fontFamily: "monospace",
              fontSize: 10,
              color: "#9945FF",
              letterSpacing: "0.2em",
              fontWeight: 700,
            }}
          >
            x402 PAYMENT RAIL
          </span>
        </div>
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 9,
            color: "#555",
            letterSpacing: "0.08em",
          }}
        >
          {x402Payments.length} tx · SOLANA DEVNET
        </span>
      </div>

      {/* Transaction rows */}
      <div style={{ padding: "6px 0" }}>
        {x402Payments.map((p, i) => {
          const agent = agentName(p.to_wallet_id, subTasks);
          const service = inferService(p.policy_reason ?? "");
          const solscanUrl = `${SOLSCAN_BASE}/${p.tx_hash}?cluster=devnet`;
          
          // Check verification status
          const xCall = x402Calls.find((x) => x.tx_hash === p.tx_hash);
          const verifyStatus = xCall?.status || "pending";
          let badgeColor = "#555";
          let badgeBg = "rgba(85,85,85,0.08)";
          let badgeBorder = "rgba(85,85,85,0.2)";
          let badgeLabel = "PENDING";
          
          if (verifyStatus === "confirmed") {
            badgeColor = "#22c55e";
            badgeBg = "rgba(34,197,94,0.08)";
            badgeBorder = "rgba(34,197,94,0.2)";
            badgeLabel = "VERIFIED";
          } else if (verifyStatus === "failed" || verifyStatus === "invalid") {
            badgeColor = "#ef4444";
            badgeBg = "rgba(239,68,68,0.08)";
            badgeBorder = "rgba(239,68,68,0.2)";
            badgeLabel = verifyStatus.toUpperCase();
          }

          return (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.04 }}
              style={{
                display: "grid",
                gridTemplateColumns: "52px 1fr 72px 80px 52px",
                alignItems: "center",
                gap: 8,
                padding: "5px 14px",
                borderBottom: i < x402Payments.length - 1 ? "1px solid #0f0f18" : "none",
              }}
            >
              {/* Agent */}
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: 9,
                  color: "#9945FF",
                  letterSpacing: "0.08em",
                  fontWeight: 600,
                }}
              >
                {agent}
              </span>

              {/* Service + tx hash */}
              <span style={{ minWidth: 0 }}>
                <span
                  style={{
                    fontFamily: "monospace",
                    fontSize: 9,
                    color: "#555",
                    display: "block",
                    letterSpacing: "0.04em",
                  }}
                >
                  {service}
                </span>
                <a
                  href={solscanUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontFamily: "monospace",
                    fontSize: 8,
                    color: "#9945FF",
                    textDecoration: "underline",
                    textDecorationColor: "rgba(153,69,255,0.35)",
                    letterSpacing: "0.02em",
                    display: "block",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    opacity: 0.85,
                  }}
                  title={`View on Solscan devnet: ${p.tx_hash}`}
                >
                  {p.tx_hash.slice(0, 8)}…{p.tx_hash.slice(-6)} ↗
                </a>
              </span>

              {/* Amount */}
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: 10,
                  color: "#9945FF",
                  fontWeight: 700,
                  textAlign: "right",
                  letterSpacing: "0.02em",
                }}
              >
                {toSol(p.amount, 4)}
              </span>

              {/* Status badge */}
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: 7,
                  color: badgeColor,
                  background: badgeBg,
                  border: `1px solid ${badgeBorder}`,
                  borderRadius: 4,
                  padding: "2px 4px",
                  textAlign: "center",
                  letterSpacing: "0.06em",
                }}
              >
                {badgeLabel}
              </span>

              {/* Time */}
              <span
                style={{
                  fontFamily: "monospace",
                  fontSize: 8,
                  color: "#333",
                  textAlign: "right",
                  letterSpacing: "0.02em",
                }}
              >
                {relativeTime(p.created)}
              </span>
            </motion.div>
          );
        })}
      </div>

      {/* Footer */}
      <div
        style={{
          padding: "5px 14px",
          borderTop: "1px solid rgba(153,69,255,0.1)",
          fontFamily: "monospace",
          fontSize: 8,
          color: "#2a2a3a",
          letterSpacing: "0.06em",
        }}
      >
        HTTP 402 Payment Required · ERC-7682 · Solana SPL · OWS CAT-04
      </div>
    </motion.div>
  );
}
