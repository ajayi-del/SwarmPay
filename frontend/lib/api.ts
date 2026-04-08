// ── Single source of truth for API base URL ──────────────────────────────────
// Every component MUST import API_BASE from here. No inline definitions.

const isProd = typeof window !== "undefined" && window.location.protocol === "https:";
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || (isProd ? "" : "http://localhost:8000");

// ── Safe fetch wrapper — returns null instead of throwing on network errors ──
async function safeFetch<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(url, init);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface Wallet {
  id: string;
  name: string;
  role: "coordinator" | "sub-agent";
  eth_address: string;
  sol_address?: string;
  budget_cap: number;
  balance: number;
}

export interface SubTask {
  id: string;
  task_id: string;
  agent_id: string;
  wallet_id: string;
  description: string;
  budget_allocated: number;
  status: "spawned" | "working" | "complete" | "paid" | "blocked" | "failed" | "timed_out";
  output: string;
  created: string;
  is_lead?: boolean;
}

export interface Payment {
  id: string;
  from_wallet_id: string;
  to_wallet_id: string;
  amount: number;
  chain_id: string;
  status: "signed" | "blocked";
  policy_reason: string;
  tx_hash: string;
  created: string;
}

export interface Task {
  id: string;
  description: string;
  total_budget: number;
  status: "pending" | "decomposed" | "in_progress" | "complete" | "failed";
  coordinator_wallet_id: string;
  created: string;
}

export interface X402Call {
  id: string;
  task_id: string;
  agent_id: string;
  service_name: string;
  tx_hash: string;
  status: "pending" | "confirmed" | "failed" | "not_found" | "invalid";
  amount_sol: number;
  created: string;
  verified_at?: string;
}

export interface TaskState {
  task: Task;
  coordinator_wallet: Wallet;
  sub_tasks: SubTask[];
  payments: Payment[];
  x402_calls: X402Call[];
  reputations: Record<string, number>;
}

export interface AuditEntry {
  id: string;
  event_type: string;
  entity_id: string;
  message: string;
  metadata: Record<string, unknown>;
  created: string;
}

// ── API Functions ─────────────────────────────────────────────────────────────

export async function submitTask(description: string, budget: number) {
  const res = await fetch(`${API_BASE}/task/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description, budget }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{ task_id: string; coordinator_wallet: Wallet }>;
}

export async function decomposeTask(task_id: string) {
  const res = await fetch(`${API_BASE}/task/decompose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function executeTask(task_id: string) {
  const res = await fetch(`${API_BASE}/task/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getTaskStatus(task_id: string): Promise<TaskState> {
  const res = await fetch(`${API_BASE}/task/${task_id}/status`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAuditLogs(): Promise<{ logs: AuditEntry[] }> {
  const result = await safeFetch<{ logs: AuditEntry[] }>(`${API_BASE}/audit`);
  return result ?? { logs: [] };
}

export interface SwarmStats {
  health_score: number;
  total_tasks: number;
  total_signed: number;
  total_blocked: number;
  eth_processed: number;
  eth_held: number;
  peer_count: number;
  eth_peer: number;
  avg_reputation: number;
  agent_rankings: { agent_id: string; reputation: number }[];
}

export async function getSwarmStats(): Promise<SwarmStats> {
  const result = await safeFetch<SwarmStats>(`${API_BASE}/swarm/stats`);
  return result ?? {
    health_score: 0, total_tasks: 0, total_signed: 0, total_blocked: 0,
    eth_processed: 0, eth_held: 0, peer_count: 0, eth_peer: 0,
    avg_reputation: 0, agent_rankings: [],
  };
}

// ── REGIS ─────────────────────────────────────────────────────────────────

export interface ProbeResponse {
  response: string;
  audio_b64?: string | null;
}

export interface AuditResult {
  score: number;
  verdict: "PASSED" | "MARGINAL" | "FAILED";
  reason: string;
  improvement: string;
  rep_delta: number;
}

export interface PunishResult {
  punishment_type: string;
  response: string;
  new_budget_cap?: number;
  new_reputation?: number;
  report?: string;
}

export async function probeRegis(question: string): Promise<ProbeResponse> {
  const res = await fetch(`${API_BASE}/regis/probe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function auditRegis(): Promise<AuditResult> {
  const res = await fetch(`${API_BASE}/regis/audit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function punishRegis(
  punishment_type: string,
  coordinator_wallet_id?: string
): Promise<PunishResult> {
  const res = await fetch(`${API_BASE}/regis/punish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ punishment_type, coordinator_wallet_id }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRegisBrain(): Promise<{ content: string; last_updated: string | null }> {
  const result = await safeFetch<{ content: string; last_updated: string | null }>(`${API_BASE}/regis/brain`);
  return result ?? { content: "", last_updated: null };
}

export interface MeteoraRate {
  rate: number | null;
  source: string;
  pair_name: string;
  tvl: number;
  available: boolean;
}

export async function getMeteoraRate(): Promise<MeteoraRate> {
  const result = await safeFetch<MeteoraRate>(`${API_BASE}/regis/meteora`);
  return result ?? { rate: null, source: "unavailable", pair_name: "", tvl: 0, available: false };
}

export interface MoonpayOnramp {
  url: string | null;
  currency: string;
  fiat: string;
  suggested_amount: number;
  note: string;
  wallet: string;
}

export async function getMoonpayOnramp(walletAddress: string): Promise<MoonpayOnramp> {
  const result = await safeFetch<MoonpayOnramp>(`${API_BASE}/regis/moonpay?wallet=${encodeURIComponent(walletAddress)}`);
  return result ?? { url: null, currency: "SOL", fiat: "USD", suggested_amount: 25, note: "unavailable", wallet: walletAddress };
}

export interface ClarifyResponse {
  questions: string[];
  needs_clarification: boolean;
  suggested_budget: number;
}

export async function clarifyTask(description: string): Promise<ClarifyResponse> {
  const result = await safeFetch<ClarifyResponse>(`${API_BASE}/task/clarify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  });
  return result ?? { questions: [], needs_clarification: false, suggested_budget: 0 };
}
