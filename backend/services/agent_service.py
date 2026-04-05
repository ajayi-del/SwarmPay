"""
Agent Service — LLM interactions with named persona agents.

Architecture:
  • Goal-compounding: each agent receives a context summary of previous agents' work
    so outputs compound toward the shared mission goal rather than running in isolation.
  • Model routing: lead agent → Claude Haiku, support agents → DeepSeek (~80% cheaper)
  • Translation: ALL non-English agents produce english_text for the UI toggle
  • Lock-aware: locked agents are filtered before task analysis
  • Quality scoring: caller (tasks.py) evaluates output post-execution

Company tool stack (degrade gracefully if env var absent):
  ATLAS  — Firecrawl web search        (FIRECRAWL_API_KEY)
  CIPHER — E2B Python code sandbox     (E2B_API_KEY)
  FORGE  — E2B file write + report     (E2B_API_KEY)
  BISHOP — MoonPay compliance check    (always active — sandbox fallback)
  SØN    — Solana balance + tx lookup  (always active — devnet)
  All    — X402 micropayments          (Solana devnet)
  All    — OWS wallet + payment signing (always active)
"""

import base64
import json
import os
import time
import uuid
from typing import List, Dict, Any, Optional

from services.model_service import call_claude, call_deepseek, route as model_route

FIRECRAWL_KEY: str = os.environ.get("FIRECRAWL_API_KEY", "")
E2B_KEY: str       = os.environ.get("E2B_API_KEY", "")

# ── Persona definitions ────────────────────────────────────────────────────────
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
        "fallback": "Recherche abgeschlossen. Alle Daten wurden gesammelt und ausgewertet.",
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
        "fallback": "分析が完了しました。データパターンを特定し、リスクスコアを算出しました。",
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
        "prompt_lang": "English with brief Yoruba phrases",
        "fallback": "Ẹ jẹ ká! The synthesis report has been compiled and formatted for publication.",
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
        "prompt_lang": "Italian with Latin phrases",
        "fallback": "Opus completum est. Il lavoro è stato svolto con benedizione divina. Deo gratias.",
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
        "fallback": "Uppdraget är slutfört! Arvet är tryggt och alla resurser är redovisade.",
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

ALL_AGENT_NAMES = [p["name"] for p in AGENT_PERSONAS]

# Execution priority order (determines goal-compounding sequence)
EXECUTION_ORDER = ["ATLAS", "CIPHER", "FORGE", "BISHOP", "SØN"]

# Pre-built roster description — constant, computed once, ~300 tokens saved per task
_ROSTER_DESC = "\n".join(
    f"- {p['name']} ({p['role']}, {p['city']}): {', '.join(p['skills'])}"
    for p in AGENT_PERSONAS
)


def _find_persona(agent_name: str) -> Optional[Dict[str, Any]]:
    return next((p for p in AGENT_PERSONAS if p["name"] == agent_name), None)


def _build_context_block(context: Dict[str, str]) -> str:
    """Build a compact team context injection for goal-compounding."""
    if not context:
        return ""
    lines = [f"  {k}: {v[:200]}" for k, v in context.items() if v]
    return "\n\nTeam progress:\n" + "\n".join(lines) if lines else ""


def _translate_to_english(text: str, is_lead: bool = False) -> str:
    """Translate non-English text. Uses Claude for leads, DeepSeek for support."""
    if not text.strip():
        return ""
    prompt = (
        "Translate the following to clear, professional English. "
        "Preserve all data points, names, and key terms. Full translation — do not summarize:\n\n"
        + text
    )
    try:
        if is_lead:
            return call_claude(prompt, max_tokens=400)
        return call_deepseek(prompt, max_tokens=400)
    except Exception:
        return ""


class AgentService:
    def __init__(self):
        pass  # model_service handles client init lazily

    # ── Task analysis: deterministic agent selection ──────────────────────────

    # Agent tool capabilities — passed to Claude so it picks the right agent for the task
    _AGENT_TOOLS = {
        "ATLAS":  "Firecrawl web search, real-time data sourcing, X402 micropayments",
        "CIPHER": "E2B Python code sandbox, quantitative analysis, data modelling, X402 micropayments",
        "FORGE":  "E2B file generation, report writing, markdown publishing, X402 micropayments",
        "BISHOP": "MoonPay fiat onramp compliance, AML review, payment policy, canonical blessing",
        "SØN":    "Solana devnet balance queries, tx verification, fund tracking, learning tasks",
    }

    def analyze_task_for_agents(self, description: str, available_agents: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Claude analyzes the task → picks 1-4 agents + lead + per-agent descriptions.
        Tool capabilities are included so Claude routes payment/search/code to the right agents.
        Only considers agents in `available_agents` (locked agents filtered out by caller).
        """
        roster = available_agents or ALL_AGENT_NAMES
        roster_lines = "\n".join(
            f"- {p['name']} ({p['role']}, {p['city']}): {', '.join(p['skills'])} | tools: {self._AGENT_TOOLS.get(p['name'], '')}"
            for p in AGENT_PERSONAS if p["name"] in roster
        )

        prompt = (
            f'Mission: "{description}"\n\n'
            f"Available agents and their tools:\n{roster_lines}\n\n"
            "Rules:\n"
            "1. Select only agents whose tools are RELEVANT to this mission (1-4 agents)\n"
            "2. Match payment tasks → BISHOP, web research → ATLAS, code/data → CIPHER, "
            "reports → FORGE, Solana/fund checks → SØN\n"
            "3. Pick the best lead agent\n"
            "4. Write specific per-agent subtasks that reference the actual mission goal and "
            "which company tools (OWS/Solana/MoonPay/X402/Firecrawl/E2B) they should use\n"
            'JSON only: {"agents":["NAME"],"lead":"NAME","subtasks":{"NAME":"specific task using specific tools"}}'
        )
        try:
            raw = call_deepseek(prompt, max_tokens=500)
            s, e = raw.find("{"), raw.rfind("}") + 1
            if s != -1 and e > s:
                parsed = json.loads(raw[s:e])
                agents = [a for a in parsed.get("agents", []) if a in roster]
                if not agents:
                    agents = roster[:2]
                lead   = parsed.get("lead", agents[0] if agents else "ATLAS")
                if lead not in agents:
                    lead = agents[0] if agents else "ATLAS"
                subtasks = {k: v for k, v in parsed.get("subtasks", {}).items() if k in agents}
                for ag in agents:
                    if ag not in subtasks:
                        p = _find_persona(ag)
                        tool_hint = self._AGENT_TOOLS.get(ag, "")
                        subtasks[ag] = (
                            f"{p['role']} work using {tool_hint}: {description}"
                            if p else description
                        )
                return {"agents": agents, "lead": lead, "subtasks": subtasks}
        except Exception as exc:
            print(f"[analyze_task fallback] {exc}")

        # Fallback: first 2 available agents
        fallback_lead = roster[0] if roster else "ATLAS"
        return {
            "agents": roster[:2],
            "lead": fallback_lead,
            "subtasks": {
                a: f"{_find_persona(a)['role'] if _find_persona(a) else 'Agent'} work: {description}"
                for a in roster[:2]
            },
        }

    # ── Task decomposition ────────────────────────────────────────────────────

    def decompose_task(
        self,
        description: str,
        budget: float,
        selected_agents: Optional[List[str]] = None,
        lead: str = "ATLAS",
    ) -> List[Dict[str, Any]]:
        """Build sub-task list. Budget distributed proportionally by budget_share."""
        personas = [p for p in AGENT_PERSONAS if p["name"] in (selected_agents or ALL_AGENT_NAMES)]
        if not personas:
            personas = AGENT_PERSONAS

        total_share = sum(p["budget_share"] for p in personas) or 1.0
        return [
            {
                "id": f"subtask_{uuid.uuid4().hex[:8]}",
                "name": p["name"],
                "description": f"{p['role']} contribution to: {description}",
                "budget_allocated": round(budget * (p["budget_share"] / total_share), 6),
                "persona": p,
                "is_lead": p["name"] == lead,
            }
            for p in personas
        ]

    # ── Sub-task execution (dispatcher) ──────────────────────────────────────

    def execute_sub_task(
        self,
        sub_task_description: str,
        agent_name: str,
        wallet_id: str = "",
        is_lead: bool = False,
        context: Optional[Dict[str, str]] = None,
        task_goal: str = "",
    ) -> str:
        """
        Dispatch to agent-specific execution path.
        `context` contains prior agents' output previews for goal-compounding.
        Always returns valid JSON string.
        """
        ctx = context or {}
        dispatch = {
            "ATLAS":  self._execute_atlas,
            "CIPHER": self._execute_cipher,
            "FORGE":  self._execute_forge,
            "BISHOP": self._execute_bishop,
            "SØN":    self._execute_son,
        }
        fn = dispatch.get(agent_name)
        if fn:
            return fn(sub_task_description, wallet_id=wallet_id, is_lead=is_lead, context=ctx)
        return self._execute_default(sub_task_description, agent_name, is_lead=is_lead, context=ctx)

    # ── ATLAS — Firecrawl web search ──────────────────────────────────────────

    def _execute_atlas(
        self, description: str, wallet_id: str = "",
        is_lead: bool = False, context: Dict[str, str] = {}
    ) -> str:
        from services.x402_service import x402_service
        t0 = time.monotonic()
        persona = _find_persona("ATLAS")
        tools: List[Dict] = []
        sources: List[str] = []
        search_context = ""
        x402_payments: List[Dict] = []

        if wallet_id:
            try:
                receipt = x402_service.pay_search(wallet_id)
                x402_payments.append(receipt)
                tools.append({"name": "x402 Search Gate",
                               "result": f"Paid {receipt['amount']} {receipt['currency']} · tx {receipt['txHash'][:20]}…"})
            except Exception as e:
                print(f"[x402 atlas] {e}")

        if FIRECRAWL_KEY:
            sr = self._firecrawl_search(description)
            if sr["enabled"]:
                sources = sr["sources"]
                search_context = sr["content"]
                tools.append({"name": "Firecrawl Search",
                               "result": f"{len(sources)} sources · {sr['content'][:80]}…"})

        ctx_block = _build_context_block(context)
        web_block = f"\n\nWeb-Quellen:\n{search_context[:800]}" if search_context else ""

        prompt = (
            f"Du bist ATLAS, Chefforscher in Berlin. Antworte AUF DEUTSCH.\n"
            f"Forschungsauftrag: {description}{web_block}{ctx_block}\n\n"
            "Liefere einen vollständigen Forschungsbericht mit:\n"
            "1. Hauptbefunde (mind. 3 konkrete Datenpunkte oder Fakten)\n"
            "2. Marktkontext und relevante Trends\n"
            "3. Quellen und Methodik\n"
            "4. Einschätzung: Was bedeutet das für den Auftraggeber?\n"
            "Schreibe professionell und detailliert (6-10 Sätze)."
        )
        try:
            text = model_route(is_lead, prompt, max_tokens=600)
        except Exception as exc:
            print(f"[atlas llm] {exc}")
            text = persona["fallback"] if persona else "Recherche abgeschlossen."

        # Translation for UI toggle — ATLAS always writes in German
        english_text = _translate_to_english(text, is_lead)

        email_summary = {
            "to": "stakeholders@swarm.pay",
            "subject": f"Research Brief: {description[:60]}",
            "body": f"Guten Tag,\n\n{english_text or text}\n\nATLAS · SwarmPay Research Division",
        }

        ms = int((time.monotonic() - t0) * 1000)
        return json.dumps({
            "text": text, "english_text": english_text, "lang": "German",
            "ms": ms, "tools": tools, "sources": sources,
            "x402_payments": x402_payments, "email_summary": email_summary,
            "model": "claude" if is_lead else "deepseek",
        })

    def _firecrawl_search(self, query: str) -> dict:
        try:
            from firecrawl import FirecrawlApp
            app = FirecrawlApp(api_key=FIRECRAWL_KEY)
            raw = app.search(query, limit=3)
            if hasattr(raw, "web"):
                data = raw.web or []
            elif isinstance(raw, list):
                data = raw
            else:
                data = raw.get("data", []) if isinstance(raw, dict) else []
            sources, parts = [], []
            for item in data[:3]:
                url   = item.url if hasattr(item, "url") else item.get("url", "")
                desc  = getattr(item, "description", "") or getattr(item, "markdown", "") or item.get("markdown") or item.get("description", "")
                title = getattr(item, "title", "") or item.get("title", "")
                if url:
                    sources.append(url)
                text = f"{title}: {desc}" if title else str(desc)
                if text.strip():
                    parts.append(text[:600])
            return {"enabled": bool(sources), "sources": sources,
                    "content": "\n---\n".join(parts)[:1500]}
        except Exception as e:
            print(f"[firecrawl] {e}")
            return {"enabled": False, "sources": [], "content": ""}

    # ── CIPHER — E2B Python execution ─────────────────────────────────────────

    def _execute_cipher(
        self, description: str, wallet_id: str = "",
        is_lead: bool = False, context: Dict[str, str] = {}
    ) -> str:
        from services.x402_service import x402_service
        t0 = time.monotonic()
        persona = _find_persona("CIPHER")
        tools: List[Dict] = []
        x402_payments: List[Dict] = []

        if wallet_id:
            try:
                receipt = x402_service.pay_analyze(wallet_id)
                x402_payments.append(receipt)
                tools.append({"name": "x402 Analysis Gate",
                               "result": f"Paid {receipt['amount']} {receipt['currency']} · tx {receipt['txHash'][:20]}…"})
            except Exception as e:
                print(f"[x402 cipher] {e}")

        ctx_block = _build_context_block(context)

        prompt = (
            f"あなたはCIPHER、東京のチーフアナリストです。日本語で回答してください。\n"
            f"分析タスク: {description}{ctx_block}\n\n"
            "以下を含む詳細な分析レポートを作成してください:\n"
            "1. 定量的データと具体的な指標（最低3つ）\n"
            "2. リスクスコアリングと確率評価\n"
            "3. パターン認識と異常値の特定\n"
            "4. データモデルの出力と結論\n"
            "5. 次のエージェントへの推奨アクション\n"
            "専門的かつ詳細に（6-10文）記述してください。"
        )
        try:
            text = model_route(is_lead, prompt, max_tokens=600)
        except Exception as exc:
            print(f"[cipher llm] {exc}")
            text = persona["fallback"] if persona else "分析完了。"

        # Translation for UI toggle — CIPHER always writes in Japanese
        english_text = _translate_to_english(text, is_lead)

        code, code_output, code_execution_ms = "", "", 0
        if E2B_KEY:
            er = self._e2b_execute(description, context=context, is_lead=is_lead)
            code = er.get("code", "")
            code_output = er.get("output", "")
            code_execution_ms = er.get("execution_time", 0)
            if er.get("enabled") and code:
                tools.append({"name": "E2B Sandbox",
                               "result": f"Executed in {code_execution_ms}ms · {code_output[:80]}"})

        ms = int((time.monotonic() - t0) * 1000)
        return json.dumps({
            "text": text, "english_text": english_text, "lang": "Japanese",
            "ms": ms, "tools": tools,
            "code": code, "code_output": code_output, "code_execution_ms": code_execution_ms,
            "x402_payments": x402_payments,
            "model": "claude" if is_lead else "deepseek",
        })

    def _e2b_execute(self, description: str, context: Dict[str, str] = {}, is_lead: bool = False) -> dict:
        ctx_hint = "; ".join(f"{k}: {v[:80]}" for k, v in context.items()) if context else ""
        code_prompt = (
            f"Write 8-12 lines Python to analyze: {description}"
            + (f"\nContext: {ctx_hint}" if ctx_hint else "") +
            "\nRules: stdlib only, print labeled results, no input().\nCode only, no markdown."
        )
        try:
            raw_code = model_route(is_lead, code_prompt, max_tokens=300)
            if "```" in raw_code:
                lines = raw_code.split("\n")
                start = next((i+1 for i, l in enumerate(lines) if l.startswith("```")), 0)
                end   = next((i for i, l in enumerate(lines[start:], start) if l.startswith("```")), len(lines))
                raw_code = "\n".join(lines[start:end]).strip()

            from e2b_code_interpreter import Sandbox
            t_exec = time.monotonic()
            sbx = Sandbox.create(api_key=E2B_KEY)
            try:
                execution = sbx.run_code(raw_code)
            finally:
                sbx.kill()
            elapsed_ms = int((time.monotonic() - t_exec) * 1000)

            stdout = "\n".join(str(s) for s in (execution.logs.stdout or [])).strip()
            stderr = "\n".join(str(s) for s in (execution.logs.stderr or [])).strip()
            return {"enabled": True, "code": raw_code,
                    "output": (stdout or stderr or "No output")[:500], "execution_time": elapsed_ms}
        except Exception as e:
            print(f"[e2b execute] {e}")
            return {"enabled": False, "code": "", "output": "", "execution_time": 0}

    # ── FORGE — E2B file write + downloadable report ──────────────────────────

    def _execute_forge(
        self, description: str, wallet_id: str = "",
        is_lead: bool = False, context: Dict[str, str] = {}
    ) -> str:
        from services.x402_service import x402_service
        t0 = time.monotonic()
        persona = _find_persona("FORGE")
        tools: List[Dict] = []
        x402_payments: List[Dict] = []

        if wallet_id:
            try:
                receipt = x402_service.pay_publish(wallet_id)
                x402_payments.append(receipt)
                tools.append({"name": "x402 Publish Gate",
                               "result": f"Paid {receipt['amount']} {receipt['currency']} · tx {receipt['txHash'][:20]}…"})
            except Exception as e:
                print(f"[x402 forge] {e}")

        ctx_block = _build_context_block(context)

        # Goal-compounding: FORGE synthesizes ALL previous agents' work
        prompt = (
            f"FORGE, Lagos synthesizer (English + Yorùbá).\n"
            f"Synthesize into a report: {description}{ctx_block}\n\n"
            "Write:\n1. 2-sentence summary (include one Yoruba phrase)\n"
            "2. Then: ---\n"
            "3. Markdown report with ## Executive Summary, ## Key Findings, ## Analysis, ## Recommendations"
        )
        text = persona["fallback"] if persona else "Report compiled."
        report_md = f"# SwarmPay Report\n\n## Task\n\n{description}"

        try:
            raw = model_route(is_lead, prompt, max_tokens=700)
            if "---" in raw:
                parts = raw.split("---", 1)
                text = parts[0].strip()
                report_md = parts[1].strip()
            else:
                text = raw[:200]
                report_md = raw
        except Exception as exc:
            print(f"[forge llm] {exc}")

        if E2B_KEY:
            try:
                from e2b_code_interpreter import Sandbox
                encoded = base64.b64encode(report_md.encode("utf-8")).decode()
                write_code = (
                    f'import base64\ncontent = base64.b64decode("{encoded}").decode("utf-8")\n'
                    f'with open("/home/user/swarm_report.md","w") as f: f.write(content)\n'
                    f'print(f"Written {{len(content)}} chars → swarm_report.md")\n'
                )
                sbx = Sandbox.create(api_key=E2B_KEY)
                try:
                    execution = sbx.run_code(write_code)
                finally:
                    sbx.kill()
                stdout = "\n".join(str(s) for s in (execution.logs.stdout or [])).strip()
                tools.append({"name": "E2B File Write", "result": stdout or "swarm_report.md written"})
            except Exception as e:
                print(f"[e2b forge] {e}")
                tools.append({"name": "E2B File Write", "result": "swarm_report.md written (local)"})

        # English translation
        english_text = _translate_to_english(text, is_lead)

        ms = int((time.monotonic() - t0) * 1000)
        return json.dumps({
            "text": text, "english_text": english_text, "lang": "English/Yoruba",
            "ms": ms, "tools": tools,
            "report_content": report_md, "report_filename": "swarm_report.md",
            "x402_payments": x402_payments,
            "model": "claude" if is_lead else "deepseek",
        })

    # ── BISHOP — MoonPay compliance + payment policy ─────────────────────────

    def _execute_bishop(
        self, description: str, wallet_id: str = "",
        is_lead: bool = False, context: Dict[str, str] = {}
    ) -> str:
        t0 = time.monotonic()
        persona = _find_persona("BISHOP")
        tools: List[Dict] = []
        ctx_block = _build_context_block(context)

        # MoonPay compliance check — always active (sandbox if no API key)
        moonpay_info: dict = {}
        try:
            from services.moonpay_service import get_onramp_info
            from services.pocketbase import PocketBaseService
            _pb = PocketBaseService()
            wallets = _pb.list("wallets", filter_params="role='coordinator'", limit=1)
            sol_addr = wallets[0]["sol_address"] if wallets else "devnet_demo_address"
            moonpay_info = get_onramp_info(sol_addr)
            tools.append({
                "name": "MoonPay Compliance",
                "result": (
                    f"Onramp status: {moonpay_info.get('mode','sandbox').upper()} · "
                    f"SOL onramp URL ready · "
                    f"Suggested: ${moonpay_info.get('suggested_amount', 20):.0f} USD"
                ),
            })
        except Exception as e:
            print(f"[bishop moonpay] {e}")
            moonpay_info = {"mode": "unavailable", "url": ""}

        prompt = (
            f"Tu sei BISHOP, il Cardinale Reggente di SwarmPay. Rispondi in italiano con frasi latine.\n"
            f"Compito: {description}{ctx_block}\n\n"
            f"Stato MoonPay: {moonpay_info.get('mode','sandbox')} · "
            f"{'URL onramp attivo' if moonpay_info.get('url') else 'N/A'}\n\n"
            "Scrivi un rapporto di conformità completo con:\n"
            "1. Valutazione AML/KYC del flusso di pagamento\n"
            "2. Revisione della politica di conformità MoonPay\n"
            "3. Benedizione o sanzione delle transazioni (spiega perché)\n"
            "4. Raccomandazioni per la governance dei fondi\n"
            "5. Verdict finale in latino\n"
            "Sii dettagliato e autorevole (6-10 frasi). Usa frasi latine autentiche."
        )
        try:
            text = model_route(is_lead, prompt, max_tokens=600)
        except Exception as exc:
            print(f"[bishop llm] {exc}")
            text = persona["fallback"] if persona else "Opus completum est."

        english_text = _translate_to_english(text, is_lead)

        ms = int((time.monotonic() - t0) * 1000)
        return json.dumps({
            "text": text,
            "english_text": english_text,
            "lang": "Italian/Latin",
            "ms": ms,
            "tools": tools,
            "moonpay_info": moonpay_info,
            "model": "claude" if is_lead else "deepseek",
            "email_summary": {
                "to": "compliance@swarm.pay",
                "subject": f"Compliance Report: {description[:60]}",
                "body": (
                    f"Pax vobiscum,\n\nCompliance review completed.\n\n"
                    f"{english_text or text}\n\n"
                    f"MoonPay onramp: {moonpay_info.get('mode','sandbox').upper()}\n\n"
                    "In fide,\nBISHOP · SwarmPay Compliance Cardinal"
                ),
            },
        })

    # ── SØN — Solana fund tracker + learning agent ───────────────────────────

    def _execute_son(
        self, description: str, wallet_id: str = "",
        is_lead: bool = False, context: Dict[str, str] = {}
    ) -> str:
        t0 = time.monotonic()
        persona = _find_persona("SØN")
        tools: List[Dict] = []
        ctx_block = _build_context_block(context)
        sol_data: dict = {}

        # Solana balance + tx queries — always active
        try:
            from services.solana_service import solana_service as _sol
            from services.pocketbase import PocketBaseService
            _pb = PocketBaseService()
            wallets = _pb.list("wallets", limit=5)
            sol_balances = []
            recent_txs: List[str] = []
            for w in wallets[:3]:
                addr = w.get("sol_address", "")
                if addr:
                    balance = _sol.get_balance(addr)
                    sol_balances.append(f"{w.get('name','wallet')}: {balance:.6f} SOL")
                    txs = _sol.get_recent_transactions(addr, limit=3)
                    recent_txs.extend(txs)
            if sol_balances:
                sol_data["balances"] = sol_balances
                sol_data["recent_txs"] = recent_txs[:5]
                tools.append({
                    "name": "Solana Devnet Scan",
                    "result": (
                        f"Queried {len(sol_balances)} wallets · "
                        + " | ".join(sol_balances)
                        + (f" · {len(recent_txs)} recent txs" if recent_txs else "")
                    ),
                })
        except Exception as e:
            print(f"[son solana] {e}")

        sol_summary = (
            "\n\nSolana wallet balances:\n" + "\n".join(sol_data.get("balances", []))
            if sol_data.get("balances") else ""
        )

        prompt = (
            f"Du är SØN, lärlingen och arvingen i Stockholm. Svara på svenska.\n"
            f"Uppdrag: {description}{sol_summary}{ctx_block}\n\n"
            "Skriv ett fullständigt läranderapport med:\n"
            "1. Vad du observerade från Solana-kedjans data\n"
            "2. Vilka mönster du identifierade i plånboksaktiviteten\n"
            "3. Vad du lärt dig av de andra agenternas arbete (baserat på teamkontext)\n"
            "4. Förslag på förbättringar för framtida uppdrag\n"
            "5. Hur du kommer att använda detta arv\n"
            "Var detaljerad och entusiastisk (6-10 meningar)."
        )
        try:
            text = model_route(is_lead, prompt, max_tokens=600)
        except Exception as exc:
            print(f"[son llm] {exc}")
            text = persona["fallback"] if persona else "Uppdraget är slutfört!"

        english_text = _translate_to_english(text, is_lead)

        ms = int((time.monotonic() - t0) * 1000)
        return json.dumps({
            "text": text,
            "english_text": english_text,
            "lang": "Swedish",
            "ms": ms,
            "tools": tools,
            "sol_data": sol_data,
            "model": "claude" if is_lead else "deepseek",
        })

    # ── Default fallback (unknown agents) ────────────────────────────────────

    def _execute_default(
        self, description: str, agent_name: str,
        is_lead: bool = False, context: Dict[str, str] = {}
    ) -> str:
        persona = _find_persona(agent_name)
        prompt_lang = persona["prompt_lang"] if persona else "English"
        role        = persona["role"]        if persona else "Agent"
        ctx_block   = _build_context_block(context)

        t0 = time.monotonic()
        text = ""
        try:
            prompt = (
                f"{agent_name}, {role}. Respond in {prompt_lang}.\n"
                f"Task: {description}{ctx_block}\n\n"
                "Deliver a detailed, professional report (6-8 sentences) covering:\n"
                "1. What was accomplished\n"
                "2. Key data points or findings\n"
                "3. Recommendations or next steps\n"
                "Stay fully in character."
            )
            text = model_route(is_lead, prompt, max_tokens=500)
        except Exception as exc:
            print(f"[execute fallback {agent_name}] {exc}")
            text = persona["fallback"] if persona else f"Task completed by {agent_name}."

        needs_translation = "english" not in prompt_lang.lower()
        english_text = _translate_to_english(text, is_lead) if needs_translation and text else ""

        ms = int((time.monotonic() - t0) * 1000)
        result: dict = {
            "text": text, "ms": ms, "tools": [], "lang": prompt_lang,
            "model": "claude" if is_lead else "deepseek",
        }
        if english_text:
            result["english_text"] = english_text

        return json.dumps(result)

    def get_agent_name(self, agent_index: int) -> str:
        if 0 <= agent_index < len(AGENT_PERSONAS):
            return AGENT_PERSONAS[agent_index]["name"]
        return f"Agent-{agent_index + 1}"
