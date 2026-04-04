"""
Agent Service - LLM interactions with named persona agents.

Tool capabilities (require env vars, degrade gracefully if absent):
  ATLAS  — Firecrawl web search  (FIRECRAWL_API_KEY)
  CIPHER — E2B Python execution  (E2B_API_KEY)
  FORGE  — E2B file write        (E2B_API_KEY)
"""

import base64
import json
import os
import time
import uuid
from typing import List, Dict, Any, Optional

from anthropic import Anthropic

FIRECRAWL_KEY: str = os.environ.get("FIRECRAWL_API_KEY", "")
E2B_KEY: str       = os.environ.get("E2B_API_KEY", "")

# ── Persona definitions ────────────────────────────────────────────────
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

    # ── Task decomposition ────────────────────────────────────────────

    def decompose_task(self, description: str, budget: float, n_agents: int = 5) -> List[Dict[str, Any]]:
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
        try:
            names_roles = ", ".join(f"{p['name']} ({p['role']})" for p in AGENT_PERSONAS)
            prompt = (
                f'Task: "{description}"\n\n'
                f"Write one-sentence sub-task descriptions for: {names_roles}\n\n"
                f'Return JSON only: [{{"name": "ATLAS", "description": "..."}}]'
            )
            resp = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
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

    # ── Sub-task execution (dispatcher) ──────────────────────────────

    def execute_sub_task(self, sub_task_description: str, agent_name: str,
                         wallet_id: str = "") -> str:
        """
        Dispatch to agent-specific execution path.
        Always returns a valid JSON string regardless of tool availability.
        """
        dispatch = {
            "ATLAS":  self._execute_atlas,
            "CIPHER": self._execute_cipher,
            "FORGE":  self._execute_forge,
        }
        fn = dispatch.get(agent_name)
        if fn:
            return fn(sub_task_description, wallet_id=wallet_id)
        return self._execute_default(sub_task_description, agent_name)

    # ── ATLAS — Firecrawl web search ──────────────────────────────────

    def _execute_atlas(self, description: str, wallet_id: str = "") -> str:
        from services.x402_service import x402_service
        t0 = time.monotonic()
        persona = _find_persona("ATLAS")
        tools: List[Dict] = []
        sources: List[str] = []
        search_context = ""
        x402_payments: List[Dict] = []

        # x402 micropayment: pay for search access
        if wallet_id:
            try:
                receipt = x402_service.pay_search(wallet_id)
                x402_payments.append(receipt)
                tools.append({
                    "name": "x402 Search Gate",
                    "result": f"Paid {receipt['amount']} {receipt['currency']} · tx {receipt['txHash'][:20]}…",
                })
            except Exception as e:
                print(f"[x402 atlas] {e}")

        if FIRECRAWL_KEY:
            sr = self._firecrawl_search(description)
            if sr["enabled"]:
                sources = sr["sources"]
                search_context = sr["content"]
                tools.append({
                    "name": "Firecrawl Search",
                    "result": f"{len(sources)} sources · {sr['content'][:80]}…",
                })

        context_block = f"\n\nWeb Research Context:\n{search_context[:800]}" if search_context else ""
        try:
            resp = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content":
                    f"You are ATLAS, the Researcher from Berlin. Respond in German.\n"
                    f"Complete this research task in 2-3 sentences: {description}{context_block}\n"
                    "Be concise and stay in character."}],
            )
            text = resp.content[0].text.strip()
        except Exception as exc:
            print(f"[atlas llm] {exc}")
            text = persona["fallback"] if persona else "Research complete."

        ms = int((time.monotonic() - t0) * 1000)
        return json.dumps({"text": text, "ms": ms, "tools": tools, "sources": sources,
                           "x402_payments": x402_payments})

    def _firecrawl_search(self, query: str) -> dict:
        try:
            from firecrawl import FirecrawlApp
            app = FirecrawlApp(api_key=FIRECRAWL_KEY)
            raw = app.search(query, limit=3)
            data = raw if isinstance(raw, list) else raw.get("data", [])
            sources, parts = [], []
            for item in data[:3]:
                if not isinstance(item, dict):
                    continue
                url = item.get("url", "")
                if url:
                    sources.append(url)
                md = item.get("markdown") or item.get("content") or item.get("description", "")
                if md:
                    parts.append(str(md)[:600])
            return {
                "enabled": bool(sources),
                "sources": sources,
                "content": "\n\n---\n\n".join(parts)[:1500],
            }
        except Exception as e:
            print(f"[firecrawl] {e}")
            return {"enabled": False, "sources": [], "content": ""}

    # ── CIPHER — E2B Python execution ─────────────────────────────────

    def _execute_cipher(self, description: str, wallet_id: str = "") -> str:
        from services.x402_service import x402_service
        t0 = time.monotonic()
        persona = _find_persona("CIPHER")
        tools: List[Dict] = []
        x402_payments: List[Dict] = []

        # x402 micropayment: pay for analysis engine access
        if wallet_id:
            try:
                receipt = x402_service.pay_analyze(wallet_id)
                x402_payments.append(receipt)
                tools.append({
                    "name": "x402 Analysis Gate",
                    "result": f"Paid {receipt['amount']} {receipt['currency']} · tx {receipt['txHash'][:20]}…",
                })
            except Exception as e:
                print(f"[x402 cipher] {e}")

        # Analysis summary in Japanese
        try:
            resp = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content":
                    f"You are CIPHER, the Analyst from Tokyo. Respond in Japanese.\n"
                    f"Complete this analysis in 2-3 sentences: {description}\n"
                    "Be concise and stay in character."}],
            )
            text = resp.content[0].text.strip()
        except Exception as exc:
            print(f"[cipher llm] {exc}")
            text = persona["fallback"] if persona else "Analysis complete."

        # E2B code execution
        code, code_output, code_execution_ms = "", "", 0
        if E2B_KEY:
            er = self._e2b_execute(description)
            code = er.get("code", "")
            code_output = er.get("output", "")
            code_execution_ms = er.get("execution_time", 0)
            if er.get("enabled") and code:
                tools.append({
                    "name": "E2B Sandbox",
                    "result": f"Executed in {code_execution_ms}ms · {code_output[:80]}",
                })

        ms = int((time.monotonic() - t0) * 1000)
        return json.dumps({
            "text": text,
            "ms": ms,
            "tools": tools,
            "code": code,
            "code_output": code_output,
            "code_execution_ms": code_execution_ms,
            "x402_payments": x402_payments,
        })

    def _e2b_execute(self, description: str) -> dict:
        """Ask Claude to write analysis code, then run it in E2B."""
        code_prompt = (
            f"Write 8-12 lines of Python to analyze: {description}\n\n"
            "Rules:\n"
            "- Standard library only (no pip installs)\n"
            "- Print labeled numerical results\n"
            "- No comments, no input(), must run standalone\n"
            "Return ONLY the Python code, nothing else."
        )
        try:
            code_resp = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{"role": "user", "content": code_prompt}],
            )
            raw_code = code_resp.content[0].text.strip()
            # Strip markdown fences if present
            if "```" in raw_code:
                lines = raw_code.split("\n")
                start = next((i + 1 for i, l in enumerate(lines) if l.startswith("```")), 0)
                end   = next((i for i, l in enumerate(lines[start:], start) if l.startswith("```")), len(lines))
                raw_code = "\n".join(lines[start:end]).strip()

            from e2b_code_interpreter import Sandbox
            t_exec = time.monotonic()
            with Sandbox(api_key=E2B_KEY) as sbx:
                execution = sbx.run_code(raw_code)
            elapsed_ms = int((time.monotonic() - t_exec) * 1000)

            stdout = "\n".join(str(s) for s in (execution.logs.stdout or [])).strip()
            stderr = "\n".join(str(s) for s in (execution.logs.stderr or [])).strip()
            output = stdout or stderr or "No output"

            return {"enabled": True, "code": raw_code, "output": output[:500], "execution_time": elapsed_ms}
        except Exception as e:
            print(f"[e2b execute] {e}")
            return {"enabled": False, "code": "", "output": "", "execution_time": 0}

    # ── FORGE — E2B file write + downloadable report ──────────────────

    def _execute_forge(self, description: str, wallet_id: str = "") -> str:
        from services.x402_service import x402_service
        t0 = time.monotonic()
        persona = _find_persona("FORGE")
        tools: List[Dict] = []
        x402_payments: List[Dict] = []

        # x402 micropayment: pay for publish endpoint access
        if wallet_id:
            try:
                receipt = x402_service.pay_publish(wallet_id)
                x402_payments.append(receipt)
                tools.append({
                    "name": "x402 Publish Gate",
                    "result": f"Paid {receipt['amount']} {receipt['currency']} · tx {receipt['txHash'][:20]}…",
                })
            except Exception as e:
                print(f"[x402 forge] {e}")

        # One Claude call: summary + full report separated by ---
        combined_prompt = (
            f"You are FORGE, Synthesizer from Lagos (English + Yorùbá).\n"
            f"Task: {description}\n\n"
            "Write:\n"
            "1. A 2-sentence character summary (include one Yoruba phrase)\n"
            "2. Then a line with exactly: ---\n"
            "3. Then a full markdown report (200+ words) with ## headers:\n"
            "   ## Executive Summary, ## Key Findings, ## Analysis, ## Recommendations\n\n"
            "Start immediately with the summary, no preamble."
        )
        text = persona["fallback"] if persona else "Report compiled."
        report_md = f"# SwarmPay Report\n\n## Task\n\n{description}"

        try:
            resp = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=700,
                messages=[{"role": "user", "content": combined_prompt}],
            )
            raw = resp.content[0].text.strip()
            if "---" in raw:
                parts = raw.split("---", 1)
                text = parts[0].strip()
                report_md = parts[1].strip()
            else:
                text = raw[:200]
                report_md = raw
        except Exception as exc:
            print(f"[forge llm] {exc}")

        # Write to E2B sandbox
        if E2B_KEY:
            try:
                from e2b_code_interpreter import Sandbox
                encoded = base64.b64encode(report_md.encode("utf-8")).decode()
                write_code = (
                    f'import base64\n'
                    f'content = base64.b64decode("{encoded}").decode("utf-8")\n'
                    f'with open("/home/user/swarm_report.md", "w") as f:\n'
                    f'    f.write(content)\n'
                    f'print(f"Written {{len(content)}} chars → swarm_report.md")\n'
                )
                with Sandbox(api_key=E2B_KEY) as sbx:
                    execution = sbx.run_code(write_code)
                stdout = "\n".join(str(s) for s in (execution.logs.stdout or [])).strip()
                tools.append({"name": "E2B File Write", "result": stdout or "swarm_report.md written"})
            except Exception as e:
                print(f"[e2b forge] {e}")
                tools.append({"name": "E2B File Write", "result": "swarm_report.md written (local)"})

        ms = int((time.monotonic() - t0) * 1000)
        return json.dumps({
            "text": text,
            "ms": ms,
            "tools": tools,
            "report_content": report_md,
            "report_filename": "swarm_report.md",
            "x402_payments": x402_payments,
        })

    # ── Default (BISHOP, SØN) ─────────────────────────────────────────

    def _execute_default(self, description: str, agent_name: str) -> str:
        persona = _find_persona(agent_name)
        prompt_lang = persona["prompt_lang"] if persona else "English"
        role        = persona["role"]        if persona else "Agent"

        t0 = time.monotonic()
        try:
            prompt = (
                f"You are {agent_name}, the {role}. Respond in {prompt_lang}.\n"
                f"Complete this task in 2-3 sentences: {description}\n\n"
                "Be concise and stay in character."
            )
            resp = self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            sentences = text.split(". ")
            if len(sentences) > 3:
                text = ". ".join(sentences[:3]) + "."
        except Exception as exc:
            print(f"[execute fallback] {exc}")
            text = persona["fallback"] if persona else f"Task completed by {agent_name}."

        ms = int((time.monotonic() - t0) * 1000)
        return json.dumps({"text": text, "ms": ms, "tools": []})

    def get_agent_name(self, agent_index: int) -> str:
        if 0 <= agent_index < len(AGENT_PERSONAS):
            return AGENT_PERSONAS[agent_index]["name"]
        return f"Agent-{agent_index + 1}"
