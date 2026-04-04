const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Wallet {
  id: string;
  name: string;
  role: "coordinator" | "sub-agent";
  eth_address: string;
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
  status: "spawned" | "working" | "complete" | "paid" | "blocked" | "failed";
  output: string;
  created: string;
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
