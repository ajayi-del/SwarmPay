const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

export interface TaskState {
  task: Task;
  coordinator_wallet: Wallet;
  sub_tasks: SubTask[];
  payments: Payment[];
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

export async function submitTask(description: string, budget: number) {
  const res = await fetch(`${API}/task/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description, budget }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json() as Promise<{ task_id: string; coordinator_wallet: Wallet }>;
}

export async function decomposeTask(task_id: string) {
  const res = await fetch(`${API}/task/decompose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function executeTask(task_id: string) {
  const res = await fetch(`${API}/task/execute`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getTaskStatus(task_id: string): Promise<TaskState> {
  const res = await fetch(`${API}/task/${task_id}/status`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getAuditLogs(): Promise<{ logs: AuditEntry[] }> {
  const res = await fetch(`${API}/audit`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
  const res = await fetch(`${API}/swarm/stats`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── REGIS ─────────────────────────────────────────────────────────────────

export interface ProbeResponse {
  response: string;
  audio_b64?: string | null;  // base64 MP3 from ElevenLabs — null when key not set
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
  const res = await fetch(`${API}/regis/probe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function auditRegis(): Promise<AuditResult> {
  const res = await fetch(`${API}/regis/audit`, {
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
  const res = await fetch(`${API}/regis/punish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ punishment_type, coordinator_wallet_id }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getRegisBrain(): Promise<{ content: string; last_updated: string | null }> {
  const res = await fetch(`${API}/regis/brain`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface MeteoraRate {
  rate: number | null;
  source: string;
  pair_name: string;
  tvl: number;
  available: boolean;
}

export async function getMeteoraRate(): Promise<MeteoraRate> {
  const res = await fetch(`${API}/regis/meteora`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
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
  const res = await fetch(`${API}/regis/moonpay?wallet=${encodeURIComponent(walletAddress)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface ClarifyResponse {
  questions: string[];
  needs_clarification: boolean;
  suggested_budget: number;
}

export async function clarifyTask(description: string): Promise<ClarifyResponse> {
  const res = await fetch(`${API}/task/clarify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ description }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
