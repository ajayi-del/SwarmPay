"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { SubTask, Payment } from "@/lib/api";
import { useModeStore } from "@/lib/modeStore";

/* ── Helpers ─────────────────────────────────────────────────────────── */

function owsKeyId(walletId: string): string {
  if (!walletId) return "OWS-????-????????";
  const raw = walletId.replace(/-/g, "");
  const a = raw.slice(0, 4).toUpperCase();
  const b = raw.slice(4, 12).toUpperCase();
  return `OWS-${a}-${b}`;
}

function signHash(payment: Payment | undefined, subTaskId: string): string {
  if (payment?.tx_hash) return payment.tx_hash.slice(0, 32);
  // deterministic-looking hash from IDs
  const src = (payment?.id ?? subTaskId).replace(/-/g, "");
  return `0x${src.slice(0, 6)}…${src.slice(-6)}`;
}

type RuleStatus = "pass" | "fail" | "skip";

interface Rule {
  label: string;
  status: RuleStatus;
  detail?: string;
}

function buildRules(payment: Payment | undefined): Rule[] {
  const rules: Rule[] = [
    { label: "REP GATE", status: "skip" },
    { label: "BUDGET CAP", status: "skip" },
    { label: "COORD AUTH", status: "skip" },
    { label: "DOUBLE PAY", status: "skip" },
  ];

  if (!payment) return rules;

  const reason = payment.policy_reason ?? "";

  if (payment.status === "signed") {
    return rules.map(r => ({ ...r, status: "pass" as RuleStatus }));
  }

  // Blocked — mark rules up-to-and-including the failing one
  if (reason.startsWith("REP BLOCK")) {
    rules[0] = { ...rules[0], status: "fail", detail: reason };
  } else if (reason.startsWith("BUDGET BLOCK")) {
    rules[0].status = "pass";
    rules[1] = { ...rules[1], status: "fail", detail: reason };
  } else if (reason.startsWith("AUTH BLOCK")) {
    rules[0].status = "pass";
    rules[1].status = "pass";
    rules[2] = { ...rules[2], status: "fail", detail: reason };
  } else if (reason.startsWith("DOUBLE PAY BLOCK")) {
    rules[0].status = "pass";
    rules[1].status = "pass";
    rules[2].status = "pass";
    rules[3] = { ...rules[3], status: "fail", detail: reason };
  }

  return rules;
}

/* ── Status icon ─────────────────────────────────────────────────────── */

function RuleIcon({ status }: { status: RuleStatus }) {
  if (status === "pass") return <span style={{ color: "#22c55e" }}>✓</span>;
  if (status === "fail") return <span style={{ color: "#ef4444" }}>✗</span>;
  return <span style={{ color: "#444455" }}>·</span>;
}

/* ── Main ─────────────────────────────────────────────────────────────── */

/* ── Parse revocation from sub_task output ───────────────────────────── */

function parseRevocation(output: string): { revoked: boolean; revokedAt?: string } {
  if (!output) return { revoked: false };
  try {
    const p = JSON.parse(output);
    if (p.key_revoked) return { revoked: true, revokedAt: p.key_revoked_at };
  } catch { /* ignore */ }
  return { revoked: false };
}

interface Props {
  subTask: SubTask;
  payment?: Payment;
}

export default function OWSProofPanel({ subTask, payment }: Props) {
  const [open, setOpen] = useState(false);
  const { mode } = useModeStore();
  const isOffice = mode === "office";

  const rules = buildRules(payment);
  const keyId = owsKeyId(subTask.wallet_id ?? "");
  const hash = signHash(payment, subTask.id);

  const isBlocked = payment?.status === "blocked";
  const isSigned = payment?.status === "signed";

  // Dead Man's Switch revocation takes precedence
  const { revoked: dmsRevoked, revokedAt } = parseRevocation(subTask.output ?? "");
  const keyRevoked = dmsRevoked || isBlocked;

  const accentColor = keyRevoked ? "#ef4444" : isSigned ? "#22c55e" : "#6c63ff";
  const keyStatus = dmsRevoked
    ? "REVOKED"
    : isBlocked
    ? (isOffice ? "REVOKED" : "SUSPENDED")
    : "ACTIVE";
  const keyStatusColor = keyRevoked ? "#ef4444" : "#22c55e";

  const panelLabel = isOffice ? "COMPLIANCE PROOF" : "OWS PROOF";

  return (
    <div>
      {/* Toggle */}
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 text-xs font-jb w-full text-left"
        style={{ color: "var(--text-dim)" }}
      >
        <motion.span
          animate={{ rotate: open ? 90 : 0 }}
          transition={{ duration: 0.2 }}
          className="inline-block"
        >
          ▶
        </motion.span>
        <span style={{ color: accentColor, opacity: 0.8 }}>{panelLabel}</span>
        <span className="ml-auto" style={{ color: "var(--text-dim)" }}>
          {isSigned ? "VERIFIED" : isBlocked ? "REJECTED" : "PENDING"}
        </span>
      </button>

      {/* Collapsible panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            key="proof"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div
              className="mt-2 rounded-lg p-3 space-y-2.5 font-jb text-xs"
              style={{
                background: "var(--surface-2)",
                border: `1px solid ${accentColor}22`,
              }}
            >
              {/* Header label */}
              <div
                className="flex items-center justify-between pb-1.5 border-b"
                style={{ borderColor: "var(--border)" }}
              >
                <span style={{ color: accentColor, letterSpacing: "0.08em" }}>
                  {isOffice ? "OWS COMPLIANCE AUDIT" : "OPEN WALLET STANDARD · CAT-04"}
                </span>
                <span
                  className="px-1.5 py-0.5 rounded text-xs"
                  style={{
                    background: `${keyStatusColor}18`,
                    color: keyStatusColor,
                    border: `1px solid ${keyStatusColor}33`,
                  }}
                >
                  KEY {keyStatus}
                </span>
              </div>

              {/* Identifiers */}
              <div className="space-y-1" style={{ color: "var(--text-muted)" }}>
                <div className="flex gap-2">
                  <span style={{ color: "var(--text-dim)", minWidth: 80 }}>wallet_id</span>
                  <span className="truncate" style={{ color: "var(--text)" }}>
                    {subTask.wallet_id
                      ? `${subTask.wallet_id.slice(0, 8)}…${subTask.wallet_id.slice(-8)}`
                      : "—"}
                  </span>
                </div>
                <div className="flex gap-2">
                  <span style={{ color: "var(--text-dim)", minWidth: 80 }}>api_key_id</span>
                  <span style={{ color: "var(--text)" }}>{keyId}</span>
                </div>
                {(isSigned || isBlocked) && (
                  <div className="flex gap-2">
                    <span style={{ color: "var(--text-dim)", minWidth: 80 }}>sign_hash</span>
                    <span className="truncate" style={{ color: isSigned ? "#22c55e" : "var(--text-muted)" }}>
                      {hash}
                    </span>
                  </div>
                )}
                {revokedAt && (
                  <div className="flex gap-2">
                    <span style={{ color: "var(--text-dim)", minWidth: 80 }}>revoked_at</span>
                    <span className="truncate" style={{ color: "#ef4444" }}>
                      {new Date(revokedAt).toLocaleTimeString()}
                    </span>
                  </div>
                )}
              </div>

              {/* Policy rule chain */}
              <div
                className="pt-2 border-t space-y-1"
                style={{ borderColor: "var(--border)" }}
              >
                <div style={{ color: "var(--text-dim)", marginBottom: 4 }}>
                  {isOffice ? "compliance chain" : "policy chain"}
                </div>
                {rules.map((rule, i) => (
                  <div key={rule.label} className="flex items-start gap-2">
                    <span className="shrink-0 w-3 text-center">
                      <RuleIcon status={rule.status} />
                    </span>
                    <span
                      style={{
                        color:
                          rule.status === "pass"
                            ? "var(--text-muted)"
                            : rule.status === "fail"
                            ? "#ef4444"
                            : "var(--text-dim)",
                      }}
                    >
                      {`${i + 1}. ${rule.label}`}
                      {rule.status === "fail" && rule.detail && (
                        <span
                          className="block mt-0.5 leading-relaxed"
                          style={{ color: "#ef4444", opacity: 0.75, fontSize: "0.62rem" }}
                        >
                          {rule.detail}
                        </span>
                      )}
                    </span>
                  </div>
                ))}
              </div>

              {/* Key wipe notice */}
              {isBlocked && (
                <div
                  className="pt-2 border-t text-xs leading-relaxed"
                  style={{ borderColor: "#ef444422", color: "#ef4444", opacity: 0.8 }}
                >
                  {isOffice
                    ? "⚠ API credentials suspended pending compliance review"
                    : "⚠ OWS key revoked · budget swept to coordinator vault"}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
