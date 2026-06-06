"""FastAPI backend for the Collaborative Investment Copilot.

The shared workspace is now a real Collaborative Gym task environment
(``CoInvestmentEnv``, registered as ``"investment"``). The REST endpoints are
thin adapters that translate human/agent intents into Co-Gym actions and call
``env.step(role, action)`` — so the backend follows the Co-Gym ``CoEnv`` setup
while keeping the existing frontend contract intact.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import generate_plan
from collaborative_gym.envs import EnvFactory  # noqa: F401  (registers envs)

DATA_DIR = Path(__file__).parent / "data"
SAMPLE_CSV = DATA_DIR / "sample_portfolio.csv"

TEAM_MEMBERS = ["agent", "human"]

app = FastAPI(title="Collaborative Investment Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory sessions. Each holds a live CoEnv plus the collaboration event log
# and the most recent plan metadata (LLM vs. fallback) for the UI.
SESSIONS: Dict[str, Dict[str, Any]] = {}


class CollabMetrics(BaseModel):
    delivered: int
    task_performance: float
    collab_score: float
    plan_status: str
    constraints_respected: List[str]


class SessionState(BaseModel):
    session_id: str
    total_value: float
    cash_balance: float
    summary: str
    flags: List[str]
    allocation_by_ticker: Dict[str, float]
    allocation_by_class: Dict[str, float]
    allocation_before: Optional[Dict[str, float]]
    holdings: List[Dict[str, Any]]
    user_goal: str
    constraints: List[str]
    plan: Optional[Dict[str, Any]]
    prior_plan: Optional[Dict[str, Any]]
    approved: bool
    collab_metrics: CollabMetrics
    log: List[Dict[str, Any]]


class ProposeRequest(BaseModel):
    session_id: str
    user_goal: Optional[str] = None


class ReviseRequest(BaseModel):
    session_id: str
    feedback: str


class ApproveRequest(BaseModel):
    session_id: str


class ConstraintRequest(BaseModel):
    session_id: str
    constraint: str


def _propose_action_string(plan: Dict[str, Any]) -> str:
    """Render an agent-generated plan dict as a PROPOSE_PLAN Co-Gym action."""
    return (
        f"PROPOSE_PLAN(message={plan.get('message', '')}, "
        f"findings={json.dumps(plan.get('findings', []))}, "
        f"proposed_trades={json.dumps(plan.get('proposed_trades', []))}, "
        f"target_allocation={json.dumps(plan.get('target_allocation', {}))}, "
        f"questions={json.dumps(plan.get('questions_for_user', []))})"
    )


def _build_session(csv_text: str, cash_balance: float, user_goal: str) -> Dict[str, Any]:
    session_id = uuid.uuid4().hex[:12]
    env = EnvFactory.make(
        name="investment",
        team_members=TEAM_MEMBERS,
        env_id=f"env_{session_id}",
        query=user_goal,
        portfolio_csv=csv_text,
        cash_balance=cash_balance,
    )
    state = {
        "session_id": session_id,
        "env": env,
        "log": [],
        "plan_meta": {},
        "prior_plan": None,
        "allocation_before": None,
    }
    SESSIONS[session_id] = state
    return state


def _log_append(
    state: Dict[str, Any],
    role: str,
    content: str,
    initiative: Optional[str] = None,
) -> None:
    entry: Dict[str, Any] = {"role": role, "content": content}
    if initiative:
        entry["initiative"] = initiative
    state["log"].append(entry)


def _serialize(state: Dict[str, Any]) -> SessionState:
    env = state["env"]
    pub = env.get_obs()["public"]
    ctx = pub["portfolio"]

    plan = pub["plan"]
    if plan is not None and state.get("plan_meta"):
        # Re-attach LLM/fallback provenance the env doesn't track.
        plan = {**plan, **state["plan_meta"]}

    metrics = env.evaluate_task_performance()

    return SessionState(
        session_id=state["session_id"],
        total_value=ctx["total_value"],
        cash_balance=ctx["cash_balance"],
        summary=ctx["summary"],
        flags=ctx["flags"],
        allocation_by_ticker=ctx["allocation_by_ticker"],
        allocation_by_class=ctx["allocation_by_class"],
        allocation_before=state.get("allocation_before"),
        holdings=ctx["holdings"],
        user_goal=pub["user_goal"],
        constraints=pub["constraints"],
        plan=plan,
        prior_plan=state.get("prior_plan"),
        approved=pub["plan_status"] == "approved",
        collab_metrics=CollabMetrics(
            delivered=int(metrics.get("delivered", 0)),
            task_performance=float(metrics.get("task_performance", 0)),
            collab_score=float(metrics.get("collab_score", 0)),
            plan_status=str(metrics.get("plan_status", "none")),
            constraints_respected=list(metrics.get("constraints_respected", [])),
        ),
        log=state["log"],
    )


def _get(session_id: str) -> Dict[str, Any]:
    state = SESSIONS.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


def _step(state: Dict[str, Any], role: str, action: str) -> None:
    """Apply a Co-Gym action and raise on environment-level action errors."""
    _, _, _, _, info = state["env"].step(role=role, action=action)
    if info.get("action_error"):
        raise HTTPException(status_code=400, detail=info["action_error"])


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/sample", response_model=SessionState)
def load_sample(
    cash_balance: float = 5000.0,
    user_goal: str = "Balanced long-term growth with moderate risk",
) -> SessionState:
    state = _build_session(SAMPLE_CSV.read_text(), cash_balance, user_goal)
    return _serialize(state)


@app.post("/api/upload", response_model=SessionState)
async def upload(
    file: UploadFile,
    cash_balance: float = 5000.0,
    user_goal: str = "Balanced long-term growth with moderate risk",
) -> SessionState:
    raw = await file.read()
    try:
        state = _build_session(raw.decode("utf-8"), cash_balance, user_goal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize(state)


@app.post("/api/constraint", response_model=SessionState)
def add_constraint(req: ConstraintRequest) -> SessionState:
    state = _get(req.session_id)
    constraint = req.constraint.strip()
    if constraint:
        _step(state, "human", f"ADD_CONSTRAINT(constraint={constraint})")
        _log_append(
            state,
            "user",
            f"Added constraint: {constraint}",
            initiative="human_constraint",
        )
    return _serialize(state)


@app.post("/api/propose", response_model=SessionState)
def propose(req: ProposeRequest) -> SessionState:
    state = _get(req.session_id)
    env = state["env"]
    if req.user_goal:
        env.user_goal = req.user_goal

    portfolio = env.get_obs()["public"]["portfolio"]
    if state.get("allocation_before") is None:
        state["allocation_before"] = dict(portfolio.get("allocation_by_class", {}))

    # Agent takes the analysis task action, then proposes a plan.
    _step(state, "agent", "ANALYZE_PORTFOLIO()")
    plan = generate_plan(
        portfolio,
        user_goal=env.user_goal,
        user_constraints=env.constraints,
    )
    state["plan_meta"] = {
        k: plan[k] for k in ("source", "fallback_reason") if k in plan
    }
    _step(state, "agent", _propose_action_string(plan))
    _log_append(
        state,
        "agent",
        plan.get("message", ""),
        initiative="agent_initiative",
    )
    questions = plan.get("questions_for_user") or []
    if questions:
        _log_append(
            state,
            "agent",
            f"Waiting for your input on {len(questions)} question(s).",
            initiative="waiting_for_user",
        )
    return _serialize(state)


@app.post("/api/revise", response_model=SessionState)
def revise(req: ReviseRequest) -> SessionState:
    state = _get(req.session_id)
    env = state["env"]
    if env.plan:
        state["prior_plan"] = dict(env.plan)
    _log_append(state, "user", req.feedback, initiative="human_override")
    plan = generate_plan(
        env.get_obs()["public"]["portfolio"],
        user_goal=env.user_goal,
        user_constraints=env.constraints,
        feedback=req.feedback,
        prior_plan=env.plan,
    )
    state["plan_meta"] = {
        k: plan[k] for k in ("source", "fallback_reason") if k in plan
    }
    _step(state, "agent", _propose_action_string(plan))
    _log_append(
        state,
        "agent",
        plan.get("message", ""),
        initiative="agent_initiative",
    )
    return _serialize(state)


class AnswerRequest(BaseModel):
    session_id: str
    question: str
    answer: str


@app.post("/api/answer", response_model=SessionState)
def answer_question(req: AnswerRequest) -> SessionState:
    """Record a direct answer to an agent question and revise the plan."""
    feedback = f"Regarding '{req.question.strip()}': {req.answer.strip()}"
    return revise(ReviseRequest(session_id=req.session_id, feedback=feedback))


@app.post("/api/approve", response_model=SessionState)
def approve(req: ApproveRequest) -> SessionState:
    state = _get(req.session_id)
    _step(state, "human", "APPROVE_PLAN()")
    _log_append(state, "user", "Approved the plan.", initiative="human_approve")
    return _serialize(state)


@app.post("/api/reject", response_model=SessionState)
def reject(req: ApproveRequest) -> SessionState:
    state = _get(req.session_id)
    state["plan_meta"] = {}
    state["prior_plan"] = None
    _step(state, "human", "REJECT_PLAN()")
    _log_append(state, "user", "Rejected the plan.", initiative="human_override")
    return _serialize(state)
