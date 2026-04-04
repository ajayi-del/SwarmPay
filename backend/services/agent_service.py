"""
Agent Service - LLM interactions with named persona agents
"""

import json
import os
import time
import uuid
from typing import List, Dict, Any, Optional
from anthropic import Anthropic

# 5 named agent personas — hardcoded for demo fidelity
AGENT_PERSONAS: List[Dict[str, Any]] = [
    {
        "name": "ATLAS",
        "flag": "🇩🇪",
        "city": "Berlin",
        "language": "Deutsch",
        "role": "Researcher",
        "role_color": "#3b82f6",
        "skills": ["Web Search", "Synthesis", "Sourcing"],
        "reputation": 4,
        "stats": {"tasks": 12, "success_rate": 94, "avg_speed": 1.2,
                  "sparkline": [1.5, 1.2, 0.9, 1.4, 1.0, 1.2, 0.8]},
        "budget_share": 0.1031,
        "prompt_lang": "German",
        "fallback": "Recherche abgeschlossen. Alle Daten wurden systematisch gesammelt und ausgewertet. Die Erkenntnisse wurden erfolgreich dokumentiert.",
    },
    {
        "name": "CIPHER",
        "flag": "🇯🇵",
        "city": "Tokyo",
        "language": "日本語",
        "role": "Analyst",
        "role_color": "#a855f7",
        "skills": ["Data Models", "Pattern Rec.", "Risk Scoring"],
        "reputation": 5,
        "stats": {"tasks": 8, "success_rate": 100, "avg_speed": 0.8,
                  "sparkline": [1.0, 0.8, 0.7, 0.9, 0.6, 0.8, 0.7]},
        "budget_share": 0.1031,
        "prompt_lang": "Japanese",
        "fallback": "分析が完了しました。データパターンを特定し、リスクスコアを算出しました。統計モデルは良好な結果を示しています。",
    },
    {
        "name": "FORGE",
        "flag": "🇳🇬",
        "city": "Lagos",
        "language": "English/Yorùbá",
        "role": "Synthesizer",
        "role_color": "#f97316",
        "skills": ["Writing", "Publishing", "Formatting"],
        "reputation": 4,
        "stats": {"tasks": 15, "success_rate": 87, "avg_speed": 1.5,
                  "sparkline": [2.0, 1.8, 1.2, 1.6, 1.5, 1.4, 1.5]},
        "budget_share": 0.1031,
        "prompt_lang": "English with brief Yoruba phrases like E kaaro (good morning) or Ẹ jẹ ká (let us go)",
        "fallback": "Ẹ jẹ ká! The synthesis report has been compiled and formatted for publication. All findings have been structured with precision.",
    },
    {
        "name": "BISHOP",
        "flag": "🇻🇦",
        "city": "Vatican",
        "language": "Latin/Italiano",
        "role": "Bishop",
        "role_color": "#e8e8f0",
        "skills": ["Blessings", "Censorship", "Alms"],
        "reputation": 4,
        "stats": {"tasks": 18, "success_rate": 89, "avg_speed": 1.1,
                  "sparkline": [1.3, 1.0, 1.2, 0.9, 1.1, 1.0, 1.1]},
        "budget_share": 0.1237,
        "prompt_lang": "Italian with Latin phrases like 'Opus completum est' (the work is complete) or 'Deo gratias' (thanks be to God)",
        "fallback": "Opus completum est. Il lavoro è stato svolto con benedizione divina. Deo gratias — la tithe è stata raccolta.",
    },
    {
        "name": "SØN",
        "flag": "🇸🇪",
        "city": "Stockholm",
        "language": "Svenska",
        "role": "Heir",
        "role_color": "#00ffff",
        "skills": ["Learning", "Fetch Quests", "Inheritance"],
        "reputation": 3,
        "stats": {"tasks": 5, "success_rate": 80, "avg_speed": 2.0,
                  "sparkline": [2.5, 3.0, 2.0, 2.2, 1.8, 2.0, 2.1]},
        "budget_share": 0.0515,
        "prompt_lang": "Swedish",
        "fallback": "Uppdraget är slutfört! Jag har lärt mig mycket av denna uppgift. Arvet är tryggt och alla resurser är redovisade.",
    },
]

# Coordinator persona (display only — not a sub-agent)
COORDINATOR_PERSONA: Dict[str, Any] = {
    "name": "REGIS",
    "flag": "🇬🇧",
    "city": "London",
    "language": "English",
    "role": "Monarch",
    "role_color": "#FFD700",
    "skills": ["Budgeting", "Governance", "Veto Power"],
    "reputation": 5,
    "stats": {"tasks": 42, "success_rate": 98, "avg_speed": 0.6,
              "sparkline": [0.7, 0.5, 0.6, 0.6, 0.5, 0.7, 0.6]},
}


def _find_persona(agent_name: str) -> Optional[Dict[str, Any]]:
    return next((p for p in AGENT_PERSONAS if p["name"] == agent_name), None)


class AgentService:
    def __init__(self):
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    def decompose_task(self, description: str, budget: float, n_agents: int = 5) -> List[Dict[str, Any]]:
        """
        Build 5 sub-tasks — one per named persona.
        Tries Claude Haiku for tailored descriptions; falls back to generic defaults.
        """
        # Base sub-tasks from persona config
        sub_tasks = [
            {
                "id": f"subtask_{uuid.uuid4().hex[:8]}",
                "name": p["name"],
                "description": f"{p['role']} analysis of: {description}",
                "budget_allocated": round(budget * p["budget_share"], 6),
                "persona": p,
            }
            for p in AGENT_PERSONAS
        ]

        # Attempt richer descriptions via Haiku
        try:
            names_roles = ", ".join(f"{p['name']} ({p['role']})" for p in AGENT_PERSONAS)
            prompt = (
                f'Task: "{description}"\n\n'
                f"Write one-sentence sub-task descriptions for these agents: {names_roles}\n\n"
                f'Return JSON only: [{{"name": "ATLAS", "description": "..."}}]'
            )
            resp = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text
            s, e = raw.find("["), raw.rfind("]") + 1
            if s != -1 and e > s:
                parsed = json.loads(raw[s:e])
                by_name = {item["name"]: item["description"] for item in parsed}
                for st in sub_tasks:
                    if st["name"] in by_name:
                        st["description"] = by_name[st["name"]]
        except Exception as exc:
            print(f"[decompose fallback] {exc}")

        return sub_tasks

    def execute_sub_task(self, sub_task_description: str, agent_name: str) -> str:
        """
        Run sub-task via Claude Haiku in agent's native language.
        Returns JSON string: {"text": "...", "ms": 1234}
        """
        persona = _find_persona(agent_name)
        prompt_lang = persona["prompt_lang"] if persona else "English"
        role = persona["role"] if persona else "Agent"

        t0 = time.monotonic()
        try:
            prompt = (
                f"You are {agent_name}, the {role}. Respond in {prompt_lang}.\n"
                f"Complete this task in 2-3 sentences: {sub_task_description}\n\n"
                "Be concise and stay in character."
            )
            resp = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            # Cap at 3 sentences
            sentences = text.split(". ")
            if len(sentences) > 3:
                text = ". ".join(sentences[:3]) + "."
        except Exception as exc:
            print(f"[execute fallback] {exc}")
            text = persona["fallback"] if persona else f"Task completed by {agent_name}."

        ms = int((time.monotonic() - t0) * 1000)
        return json.dumps({"text": text, "ms": ms})

    def get_agent_name(self, agent_index: int) -> str:
        """Return persona name for given 0-based index."""
        if 0 <= agent_index < len(AGENT_PERSONAS):
            return AGENT_PERSONAS[agent_index]["name"]
        return f"Agent-{agent_index + 1}"
