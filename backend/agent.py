"""Collaborative investment agent inspired by Collaborative Gym patterns.

Implements the paper's collaboration model:
- Task action: analyze portfolio + propose a plan
- Collaboration acts: explain (message), ask questions, request confirmation
- Controlled autonomy: nothing is "final" until the human approves
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic

from portfolio import project_allocation_after_trades

try:
    from dotenv import load_dotenv

    # Always load backend/.env even if uvicorn is started from the repo root.
    load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:  # pragma: no cover - dotenv optional
    pass

SYSTEM_PROMPT = """You are a collaborative personal investment copilot inspired by Stanford's Collaborative Gym framework.

Rules:
- You analyze portfolio data and PROPOSE changes, but NEVER assume trades are executed.
- Always explain rationale in plain English for a non-expert investor.
- Respect user constraints absolutely (e.g., "cannot sell employer stock").
- Propose conservative, educational suggestions — not licensed financial advice.
- When revising, incorporate user feedback and explain what changed.

Respond with ONLY a single valid JSON object and nothing else — no prose, no markdown, no code fences. Match this schema:
{
  "message": "Plain English summary for the user",
  "findings": ["finding 1", "finding 2"],
  "proposed_trades": [
    {"action": "buy|sell|hold", "ticker": "SYMBOL", "shares": 0, "rationale": "why"}
  ],
  "target_allocation": {"stock": 0, "bond": 0, "cash": 0, "etf": 0},
  "questions_for_user": ["optional question"],
  "needs_approval": true
}
"""


def _client() -> "anthropic.Anthropic":
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("Set ANTHROPIC_API_KEY in your environment or .env file.")
    # Reads ANTHROPIC_API_KEY from the environment automatically.
    return anthropic.Anthropic()


def _parse_response(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
        if text.startswith("json"):
            text = text[4:]
    # Extract the first complete JSON object from the response.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def propose_plan(
    portfolio_context: Dict[str, Any],
    user_goal: str = "Balanced long-term growth with moderate risk",
    user_constraints: Optional[List[str]] = None,
    feedback: Optional[str] = None,
    prior_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    user_constraints = user_constraints or []
    user_payload = json.dumps(
        {
            "task": "Analyze portfolio and propose a collaborative rebalance plan.",
            "user_goal": user_goal,
            "user_constraints": user_constraints,
            "portfolio": portfolio_context,
            "prior_plan": prior_plan,
            "user_feedback": feedback,
        },
        indent=2,
    )

    model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    response = _client().messages.create(
        model=model,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": user_payload},
        ],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return _parse_response(text)


def fallback_plan(
    portfolio_context: Dict[str, Any],
    feedback: Optional[str] = None,
    user_constraints: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Rule-based plan when the LLM is unavailable (keeps the demo alive)."""
    user_constraints = user_constraints or []
    flags = portfolio_context.get("flags", [])
    holdings = portfolio_context.get("holdings", [])

    protected = set()
    for c in user_constraints + ([feedback] if feedback else []):
        for h in holdings:
            if h.get("ticker") and h["ticker"] in (c or "").upper():
                protected.add(h["ticker"])

    trades: List[Dict[str, Any]] = []
    for h in holdings:
        ticker = h.get("ticker")
        if ticker in protected or ticker == "CASH":
            continue
        if h.get("weight_pct", 0) > 35:
            sell_shares = max(1, int(h.get("shares", 0) * 0.1))
            trades.append(
                {
                    "action": "sell",
                    "ticker": ticker,
                    "shares": sell_shares,
                    "rationale": "Reduce concentration in largest holding.",
                }
            )

    if not any(t["action"] == "buy" for t in trades):
        trades.append(
            {
                "action": "buy",
                "ticker": "BND",
                "shares": 5,
                "rationale": "Add defensive bond exposure to balance equity risk.",
            }
        )

    message = "Rule-based analysis (LLM unavailable): portfolio looks concentrated; consider trimming the largest position and adding bonds."
    if protected:
        message += f" Respecting your constraint — keeping {', '.join(sorted(protected))}."

    target = project_allocation_after_trades(
        portfolio_context.get("holdings", []),
        float(portfolio_context.get("cash_balance", 0)),
        trades,
    )
    if not target:
        target = dict(portfolio_context.get("allocation_by_class", {}))

    return {
        "message": message,
        "findings": flags or ["Review allocation across asset classes."],
        "proposed_trades": trades,
        "target_allocation": target,
        "questions_for_user": ["Are there any holdings you cannot sell?"],
        "needs_approval": True,
    }


def _apply_projected_allocation(
    plan: Dict[str, Any],
    portfolio_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Derive target allocation from trades so comparison reflects real changes."""
    trades = plan.get("proposed_trades") or []
    if not trades:
        return plan
    projected = project_allocation_after_trades(
        portfolio_context.get("holdings", []),
        float(portfolio_context.get("cash_balance", 0)),
        trades,
    )
    if projected:
        plan["target_allocation"] = projected
    return plan


def generate_plan(
    portfolio_context: Dict[str, Any],
    user_goal: str = "Balanced long-term growth with moderate risk",
    user_constraints: Optional[List[str]] = None,
    feedback: Optional[str] = None,
    prior_plan: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Try the LLM agent; fall back to rules so the demo never breaks."""
    try:
        plan = propose_plan(
            portfolio_context,
            user_goal=user_goal,
            user_constraints=user_constraints,
            feedback=feedback,
            prior_plan=prior_plan,
        )
        plan["source"] = "llm"
        return _apply_projected_allocation(plan, portfolio_context)
    except Exception as exc:  # noqa: BLE001
        plan = fallback_plan(
            portfolio_context, feedback=feedback, user_constraints=user_constraints
        )
        plan["source"] = "fallback"
        plan["fallback_reason"] = str(exc)
        return plan
