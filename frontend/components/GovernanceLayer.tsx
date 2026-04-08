"use client";

/**
 * GovernanceLayer — the three pillars of SwarmPay governance.
 *
 * OWS (Vault Keeper)    — secure, unified custody
 * MoonPay (Fiat Bridge)  — capital access + human-in-the-loop
 * x402 (Universal Meter) — atomic, granular micropayments
 *
 * Shows live metrics when task data is available, ambient animation otherwise.
 */

import { motion } from "framer-motion";
import { useSolRate } from "@/lib/useSolRate";
import type { TaskState } from "@/lib/api";

interface Props {
  taskState?: TaskState | null;
}

/* ── Animated pulse ring ─────────────────────────────────────────────── */

function PulseRing({ color, active }: { color: string; active: boolean }) {
  return (
    <div style={{ position: "relative", width: 44, height: 44 }}>
      {active && (
        <motion.div
          animate={{ scale: [1, 1.5], opacity: [0.5, 0] }}
          transition={{ duration: 1.8, repeat: Infinity }}
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "50%",
            border: `2px solid ${color}`,
          }}
        />
      )}
      <div
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          border: `2px solid ${color}40`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: color,
            boxShadow: `0 0 10px ${color}80`,
          }}
        />
      </div>
    </div>
  );
}

/* ── Pillar card ──────────────────────────────────────────────────────── */

function PillarCard({
  icon,
  title,
  subtitle,
  color,
  metric,
  metricLabel,
  detail,
  active,
}: {
  icon: string;
  title: string;
  subtitle: string;
  color: string;
  metric: string;
  metricLabel: string;
  detail: string;
  active: boolean;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      style={{
        background: "#0c0c14",
        border: `1px solid ${color}25`,
        borderRadius: 14,
        padding: "14px 16px",
        flex: 1,
        minWidth: 160,
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <PulseRing color={color} active={active} />
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontSize: 14 }}>{icon}</span>
            <span
              style={{
                fontFamily: "monospace",
                fontSize: 10,
                fontWeight: 700,
                color,
                letterSpacing: "0.12em",
              }}
            >
              {title}
            </span>
          </div>
          <span
            style={{
              fontFamily: "monospace",
              fontSize: 8,
              color: "#555",
              letterSpacing: "0.06em",
            }}
          >
            {subtitle}
          </span>
        </div>
      </div>

      {/* Metric */}
      <div>
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 18,
            fontWeight: 700,
            color,
            letterSpacing: "-0.02em",
          }}
        >
          {metric}
        </span>
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 9,
            color: "#666",
            marginLeft: 6,
            letterSpacing: "0.04em",
          }}
        >
          {metricLabel}
        </span>
      </div>

      {/* Detail line */}
      <div
        style={{
          fontFamily: "monospace",
          fontSize: 8,
          color: "#444",
          borderTop: `1px solid ${color}15`,
          paddingTop: 8,
          letterSpacing: "0.04em",
          lineHeight: 1.5,
        }}
      >
        {detail}
      </div>
    </motion.div>
  );
}

/* ── Main component ───────────────────────────────────────────────────── */

export default function GovernanceLayer({ taskState }: Props) {
  const { toSol } = useSolRate();

  // Extract live metrics from task state
  const walletCount = taskState
    ? new Set([
        taskState.coordinator_wallet?.id,
        ...taskState.sub_tasks.map((st) => st.wallet_id),
      ]).size
    : 0;

  const x402Count = taskState?.x402_calls?.length ?? 0;
  const x402Total = taskState?.x402_calls?.reduce(
    (sum, c) => sum + (c.amount_sol ?? 0),
    0
  ) ?? 0;

  const totalPayments = taskState?.payments?.length ?? 0;
  const signedPayments =
    taskState?.payments?.filter((p) => p.status === "signed").length ?? 0;
  const blockedPayments =
    taskState?.payments?.filter((p) => p.status === "blocked").length ?? 0;

  const peerPayments =
    taskState?.payments?.filter((p) =>
      p.policy_reason?.startsWith("PEER:")
    ) ?? [];

  const policyCompliance =
    totalPayments > 0
      ? Math.round((signedPayments / totalPayments) * 100)
      : 100;

  const treasuryBalance = taskState?.coordinator_wallet?.balance ?? 0;
  const isActive = !!taskState?.task;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {/* Section header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 9,
            color: "#555",
            letterSpacing: "0.2em",
            fontWeight: 700,
          }}
        >
          GOVERNANCE LAYER
        </span>
        <span
          style={{
            fontFamily: "monospace",
            fontSize: 8,
            color: policyCompliance >= 80 ? "#22c55e" : "#f59e0b",
            letterSpacing: "0.06em",
          }}
        >
          {policyCompliance}% POLICY COMPLIANCE
        </span>
      </div>

      {/* Three pillars */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {/* OWS — Vault Keeper */}
        <PillarCard
          icon="🔐"
          title="OWS"
          subtitle="VAULT KEEPER"
          color="#9945FF"
          metric={walletCount > 0 ? String(walletCount) : "—"}
          metricLabel={walletCount > 0 ? "wallets secured" : "awaiting agents"}
          detail={
            walletCount > 0
              ? `Non-custodial · DID-bound · ${blockedPayments > 0 ? `${blockedPayments} policy block${blockedPayments !== 1 ? "s" : ""}` : "0 violations"}`
              : "Portable identity · Key-isolated enclave · Policy & hardware checks"
          }
          active={isActive}
        />

        {/* MoonPay — Fiat Bridge */}
        <PillarCard
          icon="💰"
          title="MOONPAY"
          subtitle="FIAT BRIDGE"
          color="#F59E0B"
          metric={
            treasuryBalance > 0
              ? toSol(treasuryBalance, 4)
              : "—"
          }
          metricLabel={
            treasuryBalance > 0 ? "treasury" : "awaiting funding"
          }
          detail={
            isActive
              ? `Human veto active · ${peerPayments.length} peer transfer${peerPayments.length !== 1 ? "s" : ""} · AML/KYC compliant`
              : "Fiat onramp · Ledger hardware approval · Human-in-the-loop oversight"
          }
          active={isActive}
        />

        {/* x402 — Universal Meter */}
        <PillarCard
          icon="⚡"
          title="x402"
          subtitle="UNIVERSAL METER"
          color="#22C55E"
          metric={x402Count > 0 ? String(x402Count) : "—"}
          metricLabel={
            x402Count > 0
              ? `txs · ${toSol(x402Total, 6)}`
              : "awaiting transactions"
          }
          detail={
            x402Count > 0
              ? `Atomic pay-per-request · No API keys · ${signedPayments} signed on-chain`
              : "Pay-as-you-go · No account creation · Per-request micropayments"
          }
          active={isActive}
        />
      </div>
    </div>
  );
}
