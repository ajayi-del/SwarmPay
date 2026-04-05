/**
 * Agent Skills Registry — SwarmPay
 *
 * Each agent has a typed skill set with tier, cost, and tool bindings.
 * Skills map directly to live tools (Firecrawl, E2B, x402, Solana).
 */

export type SkillTier = "core" | "financial" | "advanced" | "business";

export interface Skill {
  id: string;
  name: string;
  tier: SkillTier;
  description: string;
  tool?: string;           // live tool backing this skill
  cost?: number;           // USDC micropayment cost via x402
  active: boolean;         // wired up in current build
}

export interface AgentSkillSet {
  agentId: string;
  role: string;
  skills: Skill[];
}

const TIER_COLORS: Record<SkillTier, string> = {
  core:      "#3b82f6",
  financial: "#22c55e",
  advanced:  "#f59e0b",
  business:  "#a78bfa",
};

export { TIER_COLORS };

export const AGENT_SKILLS: Record<string, AgentSkillSet> = {
  ATLAS: {
    agentId: "ATLAS",
    role: "Research Agent",
    skills: [
      {
        id: "web-search",
        name: "Web Search",
        tier: "core",
        description: "Live web search via Firecrawl — extract structured content from any URL",
        tool: "Firecrawl",
        cost: 0.001,
        active: true,
      },
      {
        id: "x402-search-gate",
        name: "x402 Search Gate",
        tier: "financial",
        description: "Pay-per-query micropayment gate on Solana devnet before search executes",
        tool: "x402 / Solana devnet",
        cost: 0.001,
        active: true,
      },
      {
        id: "market-research",
        name: "Market Research",
        tier: "business",
        description: "Synthesise live web data into structured market intelligence reports",
        active: true,
      },
      {
        id: "email-brief",
        name: "Email Brief",
        tier: "core",
        description: "Auto-draft stakeholder email summaries from research output",
        active: true,
      },
      {
        id: "competitive-analysis",
        name: "Competitive Analysis",
        tier: "business",
        description: "Cross-source competitive intelligence extraction",
        active: false,
      },
      {
        id: "webhook-feed",
        name: "Live Data Feeds",
        tier: "advanced",
        description: "Real-time webhook ingestion from external data providers",
        active: false,
      },
    ],
  },

  CIPHER: {
    agentId: "CIPHER",
    role: "Analytics Agent",
    skills: [
      {
        id: "e2b-sandbox",
        name: "E2B Python Sandbox",
        tier: "advanced",
        description: "Execute arbitrary Python in an isolated cloud sandbox — statistics, modeling, charting",
        tool: "E2B Code Interpreter",
        active: true,
      },
      {
        id: "x402-analyze-gate",
        name: "x402 Analysis Gate",
        tier: "financial",
        description: "0.002 USDC micropayment on Solana devnet per analysis run",
        tool: "x402 / Solana devnet",
        cost: 0.002,
        active: true,
      },
      {
        id: "statistical-analysis",
        name: "Statistical Analysis",
        tier: "core",
        description: "Automated statistical summaries — mean, std-dev, correlation, regression",
        active: true,
      },
      {
        id: "anomaly-detection",
        name: "Anomaly Detection",
        tier: "advanced",
        description: "Flag outliers and unusual patterns in structured datasets",
        active: false,
      },
      {
        id: "predictive-modeling",
        name: "Predictive Modeling",
        tier: "advanced",
        description: "Train lightweight ML models in sandbox — scikit-learn, statsmodels",
        active: false,
      },
      {
        id: "data-visualization",
        name: "Data Visualization",
        tier: "business",
        description: "Generate charts and dashboards from analysis results",
        active: false,
      },
    ],
  },

  FORGE: {
    agentId: "FORGE",
    role: "Publishing Agent",
    skills: [
      {
        id: "e2b-file-write",
        name: "E2B File Write",
        tier: "advanced",
        description: "Write final reports to persistent sandbox filesystem as downloadable Markdown",
        tool: "E2B Code Interpreter",
        active: true,
      },
      {
        id: "x402-publish-gate",
        name: "x402 Publish Gate",
        tier: "financial",
        description: "0.001 USDC micropayment gate before publishing to any endpoint",
        tool: "x402 / Solana devnet",
        cost: 0.001,
        active: true,
      },
      {
        id: "report-generation",
        name: "Report Generation",
        tier: "core",
        description: "Synthesise all upstream agent outputs into a structured Markdown deliverable",
        active: true,
      },
      {
        id: "content-publishing",
        name: "Content Publishing",
        tier: "business",
        description: "Push final reports to external platforms via REST API",
        active: false,
      },
      {
        id: "seo-optimization",
        name: "SEO Optimization",
        tier: "business",
        description: "Score and improve content for search discoverability",
        active: false,
      },
    ],
  },

  BISHOP: {
    agentId: "BISHOP",
    role: "Compliance Agent",
    skills: [
      {
        id: "compliance-review",
        name: "Compliance Review",
        tier: "core",
        description: "Cross-reference all agent outputs against governance and policy rules",
        active: true,
      },
      {
        id: "email-compliance",
        name: "Compliance Email Draft",
        tier: "core",
        description: "Auto-generate formal compliance reports formatted as stakeholder emails",
        active: true,
      },
      {
        id: "peer-payment-receive",
        name: "Peer Payment Receive",
        tier: "financial",
        description: "Receive 0.002 ETH compliance review fee from FORGE via peer payment chain",
        active: true,
      },
      {
        id: "audit-logging",
        name: "Audit Trail Validation",
        tier: "advanced",
        description: "Verify that every agent action is recorded in the immutable audit log",
        active: true,
      },
      {
        id: "risk-assessment",
        name: "Risk Assessment",
        tier: "business",
        description: "Score agent outputs for compliance risk and flag anomalies to REGIS",
        active: false,
      },
      {
        id: "kyc-verification",
        name: "KYC / AML Screening",
        tier: "advanced",
        description: "Identity and anti-money-laundering checks for wallet counterparties",
        active: false,
      },
    ],
  },

  "SØN": {
    agentId: "SØN",
    role: "Junior Agent",
    skills: [
      {
        id: "task-execution",
        name: "Task Execution",
        tier: "core",
        description: "Execute assigned sub-tasks under senior agent guidance",
        active: true,
      },
      {
        id: "learning",
        name: "Adaptive Learning",
        tier: "core",
        description: "Reputation score improves with each successful task — unlocks higher spend limits",
        active: true,
      },
      {
        id: "form-filling",
        name: "Form Automation",
        tier: "core",
        description: "Automate structured data entry and form submissions",
        active: false,
      },
      {
        id: "api-integration",
        name: "API Integration",
        tier: "advanced",
        description: "Connect to REST APIs for data retrieval — learned skill, not yet unlocked",
        active: false,
      },
    ],
  },
};

export function getAgentSkills(agentId: string): Skill[] {
  return AGENT_SKILLS[agentId]?.skills ?? [];
}

export function getActiveSkills(agentId: string): Skill[] {
  return getAgentSkills(agentId).filter((s) => s.active);
}

export function getSkillsByTier(agentId: string, tier: SkillTier): Skill[] {
  return getAgentSkills(agentId).filter((s) => s.tier === tier);
}
