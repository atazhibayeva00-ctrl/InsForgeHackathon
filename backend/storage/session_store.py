"""Persist collaborative investment sessions to SQLite."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from collaborative_gym.envs import EnvFactory  # noqa: F401  (registers envs)

from storage.database import init_db

TEAM_MEMBERS = ["agent", "human"]
DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "sessions.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _portfolio_csv_from_env(env: Any) -> str:
    return env.portfolio_df.to_csv(index=False)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def _json_loads(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


class SessionStore:
    """SQLite-backed session store with an in-process env cache."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or os.getenv("SESSION_DB_PATH", DEFAULT_DB))
        init_db(self.db_path)
        self._cache: Dict[str, Dict[str, Any]] = {}

    def create(
        self,
        csv_text: str,
        cash_balance: float,
        user_goal: str,
    ) -> Dict[str, Any]:
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
            "created_at": _now_iso(),
        }
        self._cache[session_id] = state
        self.save(state)
        return state

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        if session_id in self._cache:
            return self._cache[session_id]

        row = self._fetch_row(session_id)
        if row is None:
            return None

        state = self._hydrate(row)
        self._cache[session_id] = state
        return state

    def save(self, state: Dict[str, Any]) -> None:
        env = state["env"]
        pub = env.get_obs()["public"]
        session_id = state["session_id"]
        created_at = state.get("created_at") or _now_iso()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions (
                    session_id, portfolio_csv, cash_balance, user_goal,
                    constraints_json, plan_json, plan_status, plan_meta_json,
                    prior_plan_json, allocation_before_json,
                    last_approved_plan_json, cycles_json, log_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    portfolio_csv = excluded.portfolio_csv,
                    cash_balance = excluded.cash_balance,
                    user_goal = excluded.user_goal,
                    constraints_json = excluded.constraints_json,
                    plan_json = excluded.plan_json,
                    plan_status = excluded.plan_status,
                    plan_meta_json = excluded.plan_meta_json,
                    prior_plan_json = excluded.prior_plan_json,
                    allocation_before_json = excluded.allocation_before_json,
                    last_approved_plan_json = excluded.last_approved_plan_json,
                    cycles_json = excluded.cycles_json,
                    log_json = excluded.log_json,
                    updated_at = excluded.updated_at
                """,
                (
                    session_id,
                    _portfolio_csv_from_env(env),
                    float(env.cash_balance),
                    env.user_goal,
                    _json_dumps(pub["constraints"]),
                    _json_dumps(pub["plan"]),
                    pub["plan_status"],
                    _json_dumps(state.get("plan_meta") or {}),
                    _json_dumps(state.get("prior_plan")),
                    _json_dumps(state.get("allocation_before")),
                    _json_dumps(pub.get("last_approved_plan")),
                    _json_dumps(pub.get("cycles") or []),
                    _json_dumps(state.get("log") or []),
                    created_at,
                    _now_iso(),
                ),
            )
            conn.commit()

        state["created_at"] = created_at
        self._cache[session_id] = state

    def list_session_ids(self, limit: int = 50) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [str(row["session_id"]) for row in rows]

    def _connect(self):
        from storage.database import connect

        return connect(self.db_path)

    def _fetch_row(self, session_id: str):
        with self._connect() as conn:
            return conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()

    def _hydrate(self, row: Any) -> Dict[str, Any]:
        session_id = row["session_id"]
        env = EnvFactory.make(
            name="investment",
            team_members=TEAM_MEMBERS,
            env_id=f"env_{session_id}",
            query=row["user_goal"],
            portfolio_csv=row["portfolio_csv"],
            cash_balance=float(row["cash_balance"]),
        )

        env.constraints = list(_json_loads(row["constraints_json"], []))
        env.plan = _json_loads(row["plan_json"], None)
        env.plan_status = row["plan_status"] or "none"
        env.last_approved_plan = _json_loads(row["last_approved_plan_json"], None)
        env.cycles = list(_json_loads(row["cycles_json"], []))
        env._compute_context()

        return {
            "session_id": session_id,
            "env": env,
            "log": list(_json_loads(row["log_json"], [])),
            "plan_meta": dict(_json_loads(row["plan_meta_json"], {})),
            "prior_plan": _json_loads(row["prior_plan_json"], None),
            "allocation_before": _json_loads(row["allocation_before_json"], None),
            "created_at": row["created_at"],
        }


_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
