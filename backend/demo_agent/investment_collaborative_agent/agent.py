"""Collaborative investment agent for the distributed Co-Gym stack.

Implements the AgentNode contract: start / get_action / end.
Uses the existing LLM planner in backend/agent.py with a rule-based fallback.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import toml
from aact.cli.launch.launch import _sync_run_node
from aact.cli.reader import NodeConfig
from aact.cli.reader.dataflow_reader import NodeArgs

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from agent import generate_plan  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(name)s : %(levelname)-8s : %(message)s")
logger = logging.getLogger(__name__)


def _propose_action_string(plan: Dict[str, Any]) -> str:
    return (
        f"PROPOSE_PLAN(message={plan.get('message', '')}, "
        f"findings={json.dumps(plan.get('findings', []))}, "
        f"proposed_trades={json.dumps(plan.get('proposed_trades', []))}, "
        f"target_allocation={json.dumps(plan.get('target_allocation', {}))}, "
        f"questions={json.dumps(plan.get('questions_for_user', []))})"
    )


class InvestmentCollaborativeAgent:
    """Event-driven agent: analyze, propose, then wait for the human."""

    def __init__(self, enhance_user_control: bool = True):
        self.name: str | None = None
        self.team_members: List[str] = []
        self.task_description: str = ""
        self.action_space: list = []
        self.example_question: str = ""
        self.example_trajectory: list = []
        self.enhance_user_control = enhance_user_control
        self._analyzed = False
        self._last_cycle_index = 1
        self._constraints: list[str] = []
        self._user_goal = ""

    def start(
        self,
        name: str,
        team_members: List[str],
        task_description: str,
        action_space: list,
        example_question: str,
        example_trajectory: list,
    ) -> None:
        self.name = name
        self.team_members = team_members
        self.task_description = task_description
        self.action_space = action_space
        self.example_question = example_question
        self.example_trajectory = example_trajectory
        logger.info("Investment agent started as %s", name)

    def get_action(self, observation: dict, chat_history: List[dict]) -> str:
        plan_status = observation.get("plan_status", "none")
        cycle_index = int(observation.get("cycle_index", 1))
        constraints = observation.get("constraints", [])
        user_goal = observation.get("user_goal", self._user_goal)
        self._constraints = constraints
        self._user_goal = user_goal

        if cycle_index != self._last_cycle_index:
            self._last_cycle_index = cycle_index
            self._analyzed = False

        if not self._analyzed:
            self._analyzed = True
            return "ANALYZE_PORTFOLIO()"

        if plan_status in ("proposed", "cycle_complete"):
            return "WAIT_TEAMMATE_CONTINUE()"

        portfolio = observation.get("portfolio", {})
        feedback = _latest_human_feedback(chat_history)
        prior_plan = observation.get("plan") or observation.get("last_approved_plan")
        cycle_context = {
            "cycle_index": cycle_index,
            "previous_cycles": observation.get("cycles", []),
            "last_approved_plan": observation.get("last_approved_plan"),
        }

        plan = generate_plan(
            {**portfolio, "cycle_context": cycle_context},
            user_goal=user_goal,
            user_constraints=constraints,
            feedback=feedback,
            prior_plan=prior_plan,
        )
        return _propose_action_string(plan)

    def end(self, result_dir: str) -> None:
        out = Path(result_dir) / (self.name or "agent")
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "info.json", "w") as f:
            json.dump({"agent": "investment_collaborative_agent"}, f, indent=2)
        logger.info("Investment agent ended; results in %s", out)


def _latest_human_feedback(chat_history: List[dict]) -> str | None:
    for entry in reversed(chat_history):
        role = entry.get("role", "")
        if role == "human" or "user" in role:
            return entry.get("message")
    return None


def _load_secrets(path: str) -> None:
    secret_path = Path(path)
    if not secret_path.exists():
        return
    secrets = toml.load(secret_path)
    for key, value in secrets.items():
        if isinstance(value, str):
            os.environ[key] = value


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wait-time", type=int, default=1)
    parser.add_argument("--node-name", type=str, required=True)
    parser.add_argument("--env-uuid", type=str, required=True)
    parser.add_argument("--redis-url", type=str, default="redis://localhost:6379/0")
    parser.add_argument("--secret-path", type=str, default="secrets.toml")
    parser.add_argument("--enhance-user-control", action="store_true", default=True)
    args = parser.parse_args()

    os.chdir(BACKEND_ROOT)
    _load_secrets(args.secret_path)

    import collaborative_gym.nodes.agent_interface  # noqa: F401 — register agent node

    _sync_run_node(
        NodeConfig(
            node_name=args.node_name,
            node_class="agent",
            node_args=NodeArgs(
                env_uuid=args.env_uuid,
                node_name=args.node_name,
                agent=InvestmentCollaborativeAgent(
                    enhance_user_control=args.enhance_user_control
                ),
                wait_time=args.wait_time,
            ),
        ),
        args.redis_url,
    )
