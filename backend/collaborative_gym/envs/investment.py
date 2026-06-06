"""Collaborative investment task environment.

``CoInvestmentEnv`` models a shared portfolio-rebalancing workspace where a human
and an agent collaborate: the agent analyzes holdings and *proposes* a rebalance
plan, and nothing becomes final until the human approves it. This instantiates
the Collaborative Gym collaboration model (controlled autonomy / enhanced user
control) for a high-stakes personal-finance task.

## Action Space (shared / public)
- ANALYZE_PORTFOLIO(): recompute analysis and surface risk flags.
- PROPOSE_PLAN(message, findings, proposed_trades, target_allocation, questions):
  the agent writes a full rebalance proposal into the shared workspace.
- UPDATE_RATIONALE(text): edit the free-form rationale note.
- ADD_CONSTRAINT(constraint): add a standing constraint (e.g. "cannot sell AAPL").
- APPROVE_PLAN(): the human accepts the current proposal (controlled autonomy).
- REJECT_PLAN(): the human discards the current proposal.
- START_NEXT_CYCLE(): start another review cycle after an approval.
- FINISH(): complete the session.

## Action Space (private)
- LOOKUP_QUOTE(ticker): look up a holding's stats into the caller's private window.

## Observation Space
- public: portfolio context, current plan, plan_status, constraints, rationale.
- private: per-member research window (last quote lookup).
"""

from __future__ import annotations

import json
import re
import time
from enum import Enum
from typing import Any, Optional

from portfolio import analysis_to_context, analyze_portfolio, load_portfolio

from collaborative_gym.core import CoEnv, ObservationTypes, logger
from collaborative_gym.envs.registry import EnvFactory
from collaborative_gym.spaces import (
    MAX_UNICODE_LENGTH,
    MultiSpace,
    UnicodeWithRegexPattern,
)
from collaborative_gym.utils.string import post_process_parsed_function_arg
from collaborative_gym.utils.text_editor import TextEditor

DEFAULT_SAMPLE_CSV = (
    "ticker,shares,cost_basis,current_price,asset_class\n"
    "NVDA,40,400,950,stock\n"
    "AAPL,120,150,220,stock\n"
    "VOO,20,380,520,etf\n"
    "BND,20,72,72,bond\n"
)


class InvestmentActions(Enum):
    ANALYZE_PORTFOLIO = "ANALYZE_PORTFOLIO"
    PROPOSE_PLAN = "PROPOSE_PLAN"
    UPDATE_RATIONALE = "UPDATE_RATIONALE"
    ADD_CONSTRAINT = "ADD_CONSTRAINT"
    APPROVE_PLAN = "APPROVE_PLAN"
    REJECT_PLAN = "REJECT_PLAN"
    START_NEXT_CYCLE = "START_NEXT_CYCLE"
    LOOKUP_QUOTE = "LOOKUP_QUOTE"
    FINISH = "FINISH"

    def __str__(self):
        return self.value


@EnvFactory.register("investment")
class CoInvestmentEnv(CoEnv):
    """Collaborative environment for human-in-the-loop portfolio rebalancing."""

    def __init__(
        self,
        team_members: list[str],
        env_id: str,
        query: str = "Balanced long-term growth with moderate risk",
        portfolio_csv: Optional[str] = None,
        cash_balance: float = 5000.0,
        use_simulated_dataset: bool = False,
    ):
        super().__init__(team_members=team_members, env_id=env_id)

        self.use_simulated_dataset = use_simulated_dataset
        self.user_goal = query
        self.query = query  # TaskEnvNode expects env.query
        self.cash_balance = float(cash_balance)
        self._initial_csv = portfolio_csv or DEFAULT_SAMPLE_CSV

        # Shared (public) workspace state.
        self.portfolio_df = load_portfolio(self._initial_csv)
        self._context: dict[str, Any] = {}
        self.constraints: list[str] = []
        self.plan: Optional[dict[str, Any]] = None
        self.plan_status: str = "none"  # none | proposed | cycle_complete | rejected
        self.cycles: list[dict[str, Any]] = []
        self.cycle_index = 1
        self.last_approved_plan: Optional[dict[str, Any]] = None
        self.portfolio_history: list[dict[str, Any]] = []
        self.rationale_editor = TextEditor()

        # Private (per-member) workspace state.
        self.research_window = {
            member: {"ticker": "", "result": None} for member in team_members
        }

        self.task_description = (
            "You are a collaborative personal investment copilot. Work WITH the user to "
            "analyze their portfolio and PROPOSE a rebalance plan that matches their "
            f'stated goal: "{self.user_goal}".\n'
            "You take initiative to analyze holdings and draft proposals, but you NEVER "
            "treat a plan as final on your own. The human reviews every proposal and must "
            "explicitly APPROVE_PLAN() before it is considered accepted; they may instead "
            "REJECT_PLAN() or add a constraint and have you revise. Respect all standing "
            "constraints absolutely (e.g. 'cannot sell employer stock'). Provide educational "
            "rationale, not licensed financial advice. Output FINISH() once the user is "
            "satisfied with an approved plan."
        )

        self._compute_context()

        self.action_space = MultiSpace(
            (
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(r"^ANALYZE_PORTFOLIO\(\)$", re.DOTALL),
                    params=[],
                    machine_readable_identifier=InvestmentActions.ANALYZE_PORTFOLIO,
                    human_readable_name="Analyze the shared portfolio.",
                    human_readable_description="Recompute allocation, concentration, and risk flags for the "
                    "current portfolio and surface them in the shared workspace.",
                ),
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(
                        r"^PROPOSE_PLAN\(message=(.*), findings=(.*), proposed_trades=(.*), "
                        r"target_allocation=(.*), questions=(.*)\)$",
                        re.DOTALL,
                    ),
                    params=[
                        "message",
                        "findings",
                        "proposed_trades",
                        "target_allocation",
                        "questions",
                    ],
                    machine_readable_identifier=InvestmentActions.PROPOSE_PLAN,
                    human_readable_name="Propose a rebalance plan for the user to review.",
                    human_readable_description="Write a full rebalance proposal into the shared workspace. "
                    "`message` is a plain-English summary; `findings` is a JSON list of strings; "
                    "`proposed_trades` is a JSON list of {action, ticker, shares, rationale}; "
                    "`target_allocation` is a JSON object of asset_class -> percent; `questions` is a "
                    "JSON list of clarifying questions. The plan is only a PROPOSAL and requires human "
                    "approval before it is final.",
                ),
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(
                        r"^UPDATE_RATIONALE\(text=(.*)\)$", re.DOTALL
                    ),
                    params=["text"],
                    machine_readable_identifier=InvestmentActions.UPDATE_RATIONALE,
                    human_readable_name="Update the shared rationale note.",
                    human_readable_description="Replace the free-form rationale note in the shared workspace.",
                ),
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(
                        r"^ADD_CONSTRAINT\(constraint=(.*)\)$", re.DOTALL
                    ),
                    params=["constraint"],
                    machine_readable_identifier=InvestmentActions.ADD_CONSTRAINT,
                    human_readable_name="Add a standing constraint.",
                    human_readable_description="Record a standing constraint that all future proposals must "
                    "respect (e.g. 'Do not sell NVDA', 'Keep at least 10% cash').",
                ),
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(r"^APPROVE_PLAN\(\)$", re.DOTALL),
                    params=[],
                    machine_readable_identifier=InvestmentActions.APPROVE_PLAN,
                    human_readable_name="Approve the current proposed plan.",
                    human_readable_description="Human-only control action: accept the current proposal. Only "
                    "after this is the plan considered final. No trades are executed by this demo.",
                ),
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(r"^REJECT_PLAN\(\)$", re.DOTALL),
                    params=[],
                    machine_readable_identifier=InvestmentActions.REJECT_PLAN,
                    human_readable_name="Reject the current proposed plan.",
                    human_readable_description="Human-only control action: discard the current proposal.",
                ),
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(r"^START_NEXT_CYCLE\(\)$", re.DOTALL),
                    params=[],
                    machine_readable_identifier=InvestmentActions.START_NEXT_CYCLE,
                    human_readable_name="Start the next portfolio review cycle.",
                    human_readable_description="After an approved plan has been mock-applied, start another "
                    "analysis/proposal cycle in the same session.",
                ),
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(r"^FINISH\(\)$", re.DOTALL),
                    params=[],
                    machine_readable_identifier=InvestmentActions.FINISH,
                    human_readable_name="Finish the collaboration session.",
                    human_readable_description="Complete the session once the user is satisfied with an "
                    "approved plan.",
                ),
            )
        )

        self.private_action_space = MultiSpace(
            (
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(r"^LOOKUP_QUOTE\(ticker=(.*)\)$", re.DOTALL),
                    params=["ticker"],
                    machine_readable_identifier=InvestmentActions.LOOKUP_QUOTE,
                    human_readable_name="Look up a holding's stats privately.",
                    human_readable_description="Look up the current weight, value, and unrealized gain for a "
                    "ticker in the portfolio. The result is stored in your private research window and is "
                    "not broadcast to teammates.",
                ),
            )
        )

        self.example_question = (
            "Help me rebalance my portfolio. It feels too concentrated in tech."
        )
        self.example_trajectory = [
            (
                "First, analyze the shared portfolio to understand concentration and risk.",
                "ANALYZE_PORTFOLIO()",
                {
                    "portfolio": {
                        "flags": ["High concentration: NVDA is 41.2% of portfolio."]
                    }
                },
            ),
            (
                "NVDA is heavily concentrated. I'll propose trimming it and adding bonds, "
                "then ask the user before anything is final.",
                'PROPOSE_PLAN(message="I suggest trimming NVDA and adding bonds.", '
                'findings=["NVDA is 41% of the portfolio."], '
                'proposed_trades=[{"action": "sell", "ticker": "NVDA", "shares": 4, '
                '"rationale": "Reduce concentration."}], '
                'target_allocation={"stock": 60, "bond": 25, "etf": 10, "cash": 5}, '
                'questions=["Are there any holdings you cannot sell?"])',
                {"plan_status": "proposed"},
            ),
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _compute_context(self) -> None:
        analysis = analyze_portfolio(self.portfolio_df, cash_balance=self.cash_balance)
        self._context = analysis_to_context(analysis, cash_balance=self.cash_balance)

    def load_portfolio_csv(self, csv_text: str, cash_balance: Optional[float] = None) -> None:
        """Load a new portfolio into the shared workspace (resets any plan)."""
        if cash_balance is not None:
            self.cash_balance = float(cash_balance)
        self.portfolio_df = load_portfolio(csv_text)
        self._compute_context()
        self.plan = None
        self.plan_status = "none"
        self.cycles = []
        self.cycle_index = 1
        self.last_approved_plan = None
        self.portfolio_history = []

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------
    def _propose_plan(
        self,
        message: str,
        findings: str,
        proposed_trades: str,
        target_allocation: str,
        questions: str,
    ) -> None:
        self.plan = {
            "message": message,
            "findings": _loads_list(findings),
            "proposed_trades": _loads_list(proposed_trades),
            "target_allocation": _loads_dict(target_allocation),
            "questions_for_user": _loads_list(questions),
            "needs_approval": True,
        }
        self.plan_status = "proposed"

    def _lookup_quote(self, role: str, ticker: str) -> None:
        ticker = ticker.upper().strip()
        match = next(
            (h for h in self._context.get("holdings", []) if h.get("ticker") == ticker),
            None,
        )
        self.research_window[role] = {"ticker": ticker, "result": match}

    def _evaluate_plan(self, plan: Optional[dict[str, Any]]) -> dict[str, Any]:
        delivered = 1 if plan is not None else 0
        flags = self._context.get("flags", [])
        if not plan or not flags:
            performance = 1.0 if plan and not flags else 0.0
        else:
            traded_tickers = {
                str(t.get("ticker", "")).upper()
                for t in plan.get("proposed_trades", [])
            }
            addressed = sum(
                1 for f in flags if any(tk and tk in f.upper() for tk in traded_tickers)
            )
            performance = addressed / len(flags) if flags else 1.0
        return {
            "delivered": delivered,
            "task_performance": round(performance, 3),
            "collab_score": round(delivered * performance, 3),
            "plan_status": "approved" if delivered else self.plan_status,
            "constraints_respected": list(self.constraints),
        }

    def _asset_class_for_ticker(self, ticker: str) -> str:
        ticker = ticker.upper()
        if ticker in {"BND", "AGG", "TLT", "IEF"}:
            return "bond"
        if ticker in {"CASH", "MMF"}:
            return "cash"
        if ticker in {"VOO", "VTI", "VXUS", "QQQ", "SPY", "SCHD"}:
            return "etf"
        return "stock"

    def _constraint_violations(self, plan: dict[str, Any]) -> list[str]:
        violations = []
        constraints = [str(c).lower() for c in self.constraints]
        for trade in plan.get("proposed_trades", []):
            action = str(trade.get("action", "")).lower()
            ticker = str(trade.get("ticker", "")).upper().strip()
            if not action or not ticker:
                continue
            for constraint in constraints:
                mentions_ticker = ticker.lower() in constraint
                blocks_sell = action == "sell" and (
                    "cannot sell" in constraint
                    or "can't sell" in constraint
                    or "do not sell" in constraint
                    or "dont sell" in constraint
                    or "no sell" in constraint
                )
                blocks_buy = action == "buy" and (
                    "cannot buy" in constraint
                    or "can't buy" in constraint
                    or "do not buy" in constraint
                    or "dont buy" in constraint
                    or "no buy" in constraint
                )
                if mentions_ticker and (blocks_sell or blocks_buy):
                    violations.append(f"{action.upper()} {ticker} violates constraint: {constraint}")
        return violations

    def _apply_mock_trades(self, plan: dict[str, Any]) -> dict[str, Any]:
        before = self._context
        applied_trades = []
        self.portfolio_df["shares"] = self.portfolio_df["shares"].astype(float)

        for trade in plan.get("proposed_trades", []):
            action = str(trade.get("action", "")).lower()
            ticker = str(trade.get("ticker", "")).upper().strip()
            shares = float(trade.get("shares") or 0)
            if not ticker or shares <= 0 or action == "hold":
                continue

            match = self.portfolio_df["ticker"] == ticker
            if match.any():
                idx = self.portfolio_df.index[match][0]
                price = float(self.portfolio_df.at[idx, "current_price"])
                if action == "sell":
                    current_shares = float(self.portfolio_df.at[idx, "shares"])
                    executed_shares = min(shares, current_shares)
                    self.portfolio_df.at[idx, "shares"] = current_shares - executed_shares
                    self.cash_balance += executed_shares * price
                    applied_trades.append({**trade, "shares": executed_shares})
                elif action == "buy":
                    executed_shares = min(shares, self.cash_balance / price)
                    if executed_shares <= 0:
                        continue
                    self.portfolio_df.at[idx, "shares"] = (
                        float(self.portfolio_df.at[idx, "shares"]) + executed_shares
                    )
                    self.cash_balance -= executed_shares * price
                    applied_trades.append({**trade, "shares": executed_shares})
            elif action == "buy":
                price = float(trade.get("price") or 100.0)
                executed_shares = min(shares, self.cash_balance / price)
                if executed_shares <= 0:
                    continue
                self.portfolio_df.loc[len(self.portfolio_df)] = {
                    "ticker": ticker,
                    "shares": executed_shares,
                    "cost_basis": price,
                    "current_price": price,
                    "asset_class": self._asset_class_for_ticker(ticker),
                    "market_value": executed_shares * price,
                }
                self.cash_balance -= executed_shares * price
                applied_trades.append({**trade, "shares": executed_shares})

        self.portfolio_df["shares"] = self.portfolio_df["shares"].clip(lower=0)
        self.portfolio_df["market_value"] = (
            self.portfolio_df["shares"] * self.portfolio_df["current_price"]
        )
        self.portfolio_df = self.portfolio_df[self.portfolio_df["shares"] > 0].reset_index(
            drop=True
        )
        self._compute_context()

        return {
            "before": before,
            "after": self._context,
            "applied_trades": applied_trades,
        }

    def _approve_current_plan(self) -> None:
        if self.plan is None:
            raise ValueError("There is no proposed plan to approve.")

        plan_snapshot = json.loads(json.dumps(self.plan))
        violations = self._constraint_violations(plan_snapshot)
        if violations:
            raise ValueError("; ".join(violations))
        metrics = self._evaluate_plan(plan_snapshot)
        portfolio_transition = self._apply_mock_trades(plan_snapshot)
        cycle = {
            "cycle_index": self.cycle_index,
            "approved_plan": plan_snapshot,
            "metrics": metrics,
            "portfolio_before": portfolio_transition["before"],
            "portfolio_after": portfolio_transition["after"],
            "applied_trades": portfolio_transition["applied_trades"],
            "constraints": list(self.constraints),
            "approved_at": time.time(),
        }
        self.cycles.append(cycle)
        self.portfolio_history.append(
            {
                "cycle_index": self.cycle_index,
                "before": portfolio_transition["before"],
                "after": portfolio_transition["after"],
            }
        )
        self.last_approved_plan = plan_snapshot
        self.plan = None
        self.plan_status = "cycle_complete"

    def _start_next_cycle(self) -> None:
        if self.plan_status != "cycle_complete":
            return
        self.cycle_index += 1
        self.plan = None
        self.plan_status = "none"

    # ------------------------------------------------------------------
    # CoEnv API
    # ------------------------------------------------------------------
    def get_obs(self):
        return {
            "public": {
                "portfolio": self._context,
                "plan": self.plan,
                "plan_status": self.plan_status,
                "constraints": list(self.constraints),
                "rationale": self.rationale_editor.get_text(),
                "user_goal": self.user_goal,
                "cycles": self.cycles,
                "cycle_index": self.cycle_index,
                "last_approved_plan": self.last_approved_plan,
                "portfolio_history": self.portfolio_history,
            },
            "private": {
                member: {"research_window": self.research_window[member]}
                for member in self.team_members
            },
        }

    def obs_type(self) -> dict[str, ObservationTypes]:
        return {
            "portfolio": ObservationTypes.PORTFOLIO_TABLE,
            "plan": ObservationTypes.PLAN_PANEL,
            "rationale": ObservationTypes.TEXT_EDITOR,
            "research_window": ObservationTypes.NO_RENDER,
        }

    def reset(self, options: dict[str, Any] | None = None):
        options = options or {}
        if "user_goal" in options and options["user_goal"]:
            self.user_goal = options["user_goal"]
        if "cash_balance" in options and options["cash_balance"] is not None:
            self.cash_balance = float(options["cash_balance"])
        csv_text = options.get("portfolio_csv", self._initial_csv)
        self.portfolio_df = load_portfolio(csv_text)
        self._compute_context()
        self.constraints = []
        self.plan = None
        self.plan_status = "none"
        self.cycles = []
        self.cycle_index = 1
        self.last_approved_plan = None
        self.portfolio_history = []
        self.rationale_editor.update_text("")
        self.research_window = {
            member: {"ticker": "", "result": None} for member in self.team_members
        }
        return self.get_obs(), {}

    def step(self, role: str, action: str):
        info: dict[str, Any] = {"action_start_time": time.time()}

        parsed_action, private, action_id, err_msg = self.parse_and_validate_action(
            role, action
        )
        if err_msg:
            return self.handle_action_error(err_msg, private)

        for k in parsed_action:
            parsed_action[k] = post_process_parsed_function_arg(parsed_action[k])

        info["action"] = str(action_id)
        info["action_error"] = None
        terminated = False
        reward = 0

        try:
            if action_id == InvestmentActions.ANALYZE_PORTFOLIO:
                self._compute_context()
            elif action_id == InvestmentActions.PROPOSE_PLAN:
                self._propose_plan(
                    message=parsed_action["message"],
                    findings=parsed_action["findings"],
                    proposed_trades=parsed_action["proposed_trades"],
                    target_allocation=parsed_action["target_allocation"],
                    questions=parsed_action["questions"],
                )
            elif action_id == InvestmentActions.UPDATE_RATIONALE:
                self.rationale_editor.update_text(parsed_action["text"])
            elif action_id == InvestmentActions.ADD_CONSTRAINT:
                constraint = parsed_action["constraint"].strip()
                if constraint and constraint not in self.constraints:
                    self.constraints.append(constraint)
            elif action_id == InvestmentActions.APPROVE_PLAN:
                if self.plan is None:
                    return self.handle_action_error(
                        "There is no proposed plan to approve.", private=False
                    )
                self._approve_current_plan()
            elif action_id == InvestmentActions.REJECT_PLAN:
                self.plan = None
                self.plan_status = "rejected"
            elif action_id == InvestmentActions.START_NEXT_CYCLE:
                self._start_next_cycle()
            elif action_id == InvestmentActions.LOOKUP_QUOTE:
                self._lookup_quote(role=role, ticker=parsed_action["ticker"])
            elif action_id == InvestmentActions.FINISH:
                terminated = True
        except Exception as e:  # noqa: BLE001
            return self.handle_action_error(
                f"Error executing action {action!r}. Error: {e}", private
            )
        finally:
            info["action_end_time"] = time.time()

        return self.get_obs(), reward, terminated, private, info

    def evaluate_task_performance(self):
        """Co-Gym Collab Score = delivered * task_performance.

        A plan is "delivered" only if the human approved it. Task performance is
        a simple heuristic: the fraction of analysis risk flags that the approved
        plan's proposed trades plausibly address.
        """
        if not self.cycles:
            return self._evaluate_plan(self.plan)

        avg_performance = sum(c["metrics"]["task_performance"] for c in self.cycles) / len(
            self.cycles
        )
        delivered = 1
        return {
            "delivered": delivered,
            "task_performance": round(avg_performance, 3),
            "collab_score": round(delivered * avg_performance, 3),
            "plan_status": "approved",
            "constraints_respected": list(self.constraints),
            "cycles": self.cycles,
        }

    def __repr__(self):
        return (
            f"CoInvestmentEnv(env_id={self.env_id}, plan_status={self.plan_status}, "
            f"constraints={len(self.constraints)})"
        )


def _loads_list(raw: str) -> list:
    if raw is None:
        return []
    raw = raw.strip()
    if not raw or raw.lower() in {"none", "null"}:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else [value]
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse list param: %r", raw)
        return []


def _loads_dict(raw: str) -> dict:
    if raw is None:
        return {}
    raw = raw.strip()
    if not raw or raw.lower() in {"none", "null"}:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        logger.warning("Could not parse dict param: %r", raw)
        return {}
