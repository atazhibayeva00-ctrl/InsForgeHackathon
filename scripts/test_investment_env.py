#!/usr/bin/env python3
"""Smoke test for the Co-Gym investment task environment."""

from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from collaborative_gym.envs import EnvFactory  # noqa: E402


def main() -> None:
    env = EnvFactory.make(
        name="investment",
        team_members=["agent", "human"],
        env_id="env_smoke_test",
        query="Balanced long-term growth with moderate risk",
    )

    obs, _, _, _, info = env.step(role="agent", action="ANALYZE_PORTFOLIO()")
    assert not info.get("action_error"), info.get("action_error")
    flags = obs["public"]["portfolio"]["flags"]
    print(f"ANALYZE_PORTFOLIO: {len(flags)} risk flag(s)")
    for flag in flags:
        print(f"  - {flag}")

    plan_action = (
        'PROPOSE_PLAN(message="Trim NVDA and add bonds.", '
        'findings=["High concentration in NVDA."], '
        'proposed_trades=[{"action": "sell", "ticker": "NVDA", "shares": 4, '
        '"rationale": "Reduce concentration."}], '
        'target_allocation={"stock": 60, "bond": 25, "etf": 10, "cash": 5}, '
        'questions=["Any holdings you cannot sell?"])'
    )
    obs, _, _, _, info = env.step(role="agent", action=plan_action)
    assert not info.get("action_error"), info.get("action_error")
    assert obs["public"]["plan_status"] == "proposed"
    print("PROPOSE_PLAN: plan_status=proposed")

    obs, _, _, _, info = env.step(role="human", action="APPROVE_PLAN()")
    assert not info.get("action_error"), info.get("action_error")
    assert obs["public"]["plan_status"] == "cycle_complete"
    assert len(obs["public"]["cycles"]) == 1
    print("APPROVE_PLAN: plan_status=cycle_complete; cycle recorded")

    obs, _, _, _, info = env.step(role="human", action="START_NEXT_CYCLE()")
    assert not info.get("action_error"), info.get("action_error")
    assert obs["public"]["plan_status"] == "none"
    assert obs["public"]["cycle_index"] == 2
    print("START_NEXT_CYCLE: cycle_index=2")

    score = env.evaluate_task_performance()
    print("Collab score:", json.dumps(score, indent=2))

    guarded_env = EnvFactory.make(
        name="investment",
        team_members=["agent", "human"],
        env_id="env_guardrail_test",
        query="Balanced long-term growth with moderate risk",
        cash_balance=100.0,
    )
    expensive_buy = (
        'PROPOSE_PLAN(message="Buy too much BND.", '
        'findings=[], '
        'proposed_trades=[{"action": "buy", "ticker": "BND", "shares": 5, '
        '"rationale": "Test cash cap."}], '
        'target_allocation={"bond": 100}, '
        'questions=[])'
    )
    obs, _, _, _, info = guarded_env.step(role="agent", action=expensive_buy)
    assert not info.get("action_error"), info.get("action_error")
    obs, _, _, _, info = guarded_env.step(role="human", action="APPROVE_PLAN()")
    assert not info.get("action_error"), info.get("action_error")
    applied = obs["public"]["cycles"][0]["applied_trades"][0]
    assert applied["shares"] < 5
    print("BUY cap: unaffordable buy was partially applied")

    constrained_env = EnvFactory.make(
        name="investment",
        team_members=["agent", "human"],
        env_id="env_constraint_test",
        query="Balanced long-term growth with moderate risk",
    )
    constrained_env.step(role="human", action='ADD_CONSTRAINT(constraint="cannot sell NVDA")')
    constrained_env.step(role="agent", action=plan_action)
    _, _, _, _, info = constrained_env.step(role="human", action="APPROVE_PLAN()")
    assert info.get("action_error")
    print("Constraint guard: blocked sell that violated standing constraint")

    print("OK — CoInvestmentEnv is working.")


if __name__ == "__main__":
    main()
