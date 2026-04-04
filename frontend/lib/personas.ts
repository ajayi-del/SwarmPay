export interface AgentPersona {
  name: string;
  flag: string;
  city: string;
  language: string;
  role: string;
  roleColor: string;
  skills: [string, string, string];
  reputation: number; // 1-5
  stats: {
    tasks: number;
    successRate: number;
    avgSpeed: number;
    sparkline: number[];
  };
}

export const AGENT_PERSONAS: Record<string, AgentPersona> = {
  ATLAS: {
    name: "ATLAS",
    flag: "🇩🇪",
    city: "Berlin",
    language: "Deutsch",
    role: "Researcher",
    roleColor: "#3b82f6",
    skills: ["Web Search", "Synthesis", "Sourcing"],
    reputation: 4,
    stats: { tasks: 12, successRate: 94, avgSpeed: 1.2, sparkline: [1.5, 1.2, 0.9, 1.4, 1.0, 1.2, 0.8] },
  },
  CIPHER: {
    name: "CIPHER",
    flag: "🇯🇵",
    city: "Tokyo",
    language: "日本語",
    role: "Analyst",
    roleColor: "#a855f7",
    skills: ["Data Models", "Pattern Rec.", "Risk Scoring"],
    reputation: 5,
    stats: { tasks: 8, successRate: 100, avgSpeed: 0.8, sparkline: [1.0, 0.8, 0.7, 0.9, 0.6, 0.8, 0.7] },
  },
  FORGE: {
    name: "FORGE",
    flag: "🇳🇬",
    city: "Lagos",
    language: "English/Yorùbá",
    role: "Synthesizer",
    roleColor: "#f97316",
    skills: ["Writing", "Publishing", "Formatting"],
    reputation: 4,
    stats: { tasks: 15, successRate: 87, avgSpeed: 1.5, sparkline: [2.0, 1.8, 1.2, 1.6, 1.5, 1.4, 1.5] },
  },
  BISHOP: {
    name: "BISHOP",
    flag: "🇻🇦",
    city: "Vatican",
    language: "Latin/Italiano",
    role: "Bishop",
    roleColor: "#e8e8f0",
    skills: ["Blessings", "Censorship", "Alms"],
    reputation: 4,
    stats: { tasks: 18, successRate: 89, avgSpeed: 1.1, sparkline: [1.3, 1.0, 1.2, 0.9, 1.1, 1.0, 1.1] },
  },
  "SØN": {
    name: "SØN",
    flag: "🇸🇪",
    city: "Stockholm",
    language: "Svenska",
    role: "Heir",
    roleColor: "#00ffff",
    skills: ["Learning", "Fetch Quests", "Inheritance"],
    reputation: 3,
    stats: { tasks: 5, successRate: 80, avgSpeed: 2.0, sparkline: [2.5, 3.0, 2.0, 2.2, 1.8, 2.0, 2.1] },
  },
};

export const COORDINATOR_PERSONA: AgentPersona = {
  name: "REGIS",
  flag: "🇬🇧",
  city: "London",
  language: "English",
  role: "Monarch",
  roleColor: "#FFD700",
  skills: ["Budgeting", "Governance", "Veto Power"],
  reputation: 5,
  stats: { tasks: 42, successRate: 98, avgSpeed: 0.6, sparkline: [0.7, 0.5, 0.6, 0.6, 0.5, 0.7, 0.6] },
};

/** Character-specific status labels per agent */
export interface StatusDisplay {
  label: string;
  color: string;
  animate?: "pulse" | "blink";
}

const DEFAULT_STATUS: Record<string, StatusDisplay> = {
  spawned: { label: "IDLE", color: "#6c63ff" },
  working: { label: "WORKING", color: "#f59e0b", animate: "pulse" },
  complete: { label: "COMPLETE", color: "#22c55e" },
  paid: { label: "PAID ✓", color: "#22c55e" },
  blocked: { label: "BLOCKED ✗", color: "#ef4444" },
  failed: { label: "FAILED", color: "#555" },
};

const PERSONA_STATUS: Record<string, Record<string, StatusDisplay>> = {
  ATLAS: {
    ...DEFAULT_STATUS,
    working: { label: "WORKING", color: "#f59e0b", animate: "pulse" },
  },
  CIPHER: {
    ...DEFAULT_STATUS,
    working: { label: "ANALYZING", color: "#a855f7", animate: "pulse" },
    paid: { label: "SOLVED ✓", color: "#22c55e" },
  },
  FORGE: {
    ...DEFAULT_STATUS,
    working: { label: "FORGING", color: "#f97316", animate: "pulse" },
    complete: { label: "SMITHED", color: "#22c55e" },
    blocked: { label: "POLICY BLOCK ✗", color: "#ef4444" },
  },
  BISHOP: {
    spawned: { label: "PRAYING", color: "#3b82f6" },
    working: { label: "PRAYING", color: "#3b82f6" },
    complete: { label: "BLESSED ✓", color: "#22c55e" },
    paid: { label: "TITHED ✓", color: "#22c55e" },
    blocked: { label: "EXCOMMUNICATED", color: "#ef4444" },
    failed: { label: "LAPSED", color: "#555" },
  },
  "SØN": {
    spawned: { label: "TRAINING", color: "#888", animate: "blink" },
    working: { label: "TRAINING", color: "#888", animate: "blink" },
    complete: { label: "LEVELED UP", color: "#00ffff" },
    paid: { label: "REWARDED ✓", color: "#00ffff" },
    blocked: { label: "GROUNDED", color: "#ef4444" },
    failed: { label: "QUEST FAILED", color: "#555" },
  },
};

export function getStatusDisplay(agentName: string, status: string): StatusDisplay {
  return (
    PERSONA_STATUS[agentName]?.[status] ??
    DEFAULT_STATUS[status] ?? { label: status.toUpperCase(), color: "#888" }
  );
}
