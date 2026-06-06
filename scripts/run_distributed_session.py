#!/usr/bin/env python3
"""Headless smoke test for the distributed Co-Gym investment stack.

Requires Redis running:  docker compose up -d

Usage (from repo root):
  source backend/.venv/bin/activate
  pip install -r backend/requirements.txt
  python scripts/run_distributed_session.py
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path

import redis
import toml
from aact import Message

import os

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from collaborative_gym.core import TeamMemberConfig  # noqa: E402
from collaborative_gym.envs import EnvFactory  # noqa: E402, registers investment
from collaborative_gym.nodes import agent_interface, task_env  # noqa: E402, F401
from collaborative_gym.nodes.commons import JsonObj  # noqa: E402
from collaborative_gym.runner import Runner  # noqa: E402

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
RESULT_DIR = str(BACKEND / "workdir" / "results")
TEAM_CONFIG = BACKEND / "configs" / "teams" / "investment_headless.toml"
PYTHON = sys.executable


def _write_env_config(session_id: str) -> Path:
    env_uuid = f"env_{session_id}"
    env = EnvFactory.make(
        name="investment",
        team_members=["agent", "human"],
        env_id=env_uuid,
        query="Balanced long-term growth with moderate risk",
    )
    _ = env  # ensure registration side effects
    config_path = BACKEND / "workdir" / f"{env_uuid}_config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        toml.dumps(
            {
                "env_class": "investment",
                "env_args": {
                    "query": "Balanced long-term growth with moderate risk",
                    "cash_balance": 5000.0,
                },
            }
        )
    )
    return config_path


def _post_action(r: redis.Redis, env_uuid: str, role: str, action: str) -> None:
    channel = f"{env_uuid}/step"
    payload = Message[JsonObj](data=JsonObj(object={"action": action, "role": role}))
    r.publish(channel, payload.model_dump_json())
    print(f"  -> {role}: {action}")


def _read_latest_plan_status(env_uuid: str) -> str | None:
    log_path = Path(RESULT_DIR) / env_uuid / "event_log.jsonl"
    if not log_path.exists():
        return None
    last = None
    for line in log_path.read_text().splitlines():
        if line.strip():
            last = json.loads(line)
    if not last:
        return None
    return last.get("current_observation", {}).get("public", {}).get("plan_status")


def _wait_for_plan_status(env_uuid: str, status: str, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _read_latest_plan_status(env_uuid) == status:
            return True
        perf_path = Path(RESULT_DIR) / env_uuid / "task_performance.json"
        if perf_path.exists():
            data = json.loads(perf_path.read_text())
            if data.get("plan_status") == status:
                return True
        time.sleep(2)
    return False


def main() -> None:
    print("Checking Redis...")
    r = redis.Redis.from_url(REDIS_URL)
    try:
        r.ping()
    except redis.exceptions.ConnectionError as exc:
        print("\nRedis is not running.", file=sys.stderr)
        print(f"  ({exc})", file=sys.stderr)
        print(
            "\nStart Redis using ONE of these options:\n"
            "  A) Docker Desktop running, then:  docker compose up -d\n"
            "  B) Homebrew:  brew install redis && brew services start redis\n"
            "  C) Foreground:  redis-server   (after brew install redis)\n",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Redis OK")

    session_id = uuid.uuid4().hex[:12]
    env_uuid = f"env_{session_id}"
    env_config_path = _write_env_config(session_id)

    team_cfg = toml.load(TEAM_CONFIG)
    members = [TeamMemberConfig(**m) for m in team_cfg["team_member"]]

    # Point agent subprocess at this venv's Python.
    for member in members:
        if member.type == "agent":
            member.start_node_base_command = (
                f"{PYTHON} -m demo_agent.investment_collaborative_agent.agent --wait-time 1"
            )

    runner = Runner(result_dir=RESULT_DIR, redis_url=REDIS_URL)
    print(f"Starting session {session_id} ...")
    runner.start_session(
        session_uuid=session_id,
        env_config_path=str(env_config_path),
        members=members,
        max_steps=50,
        disable_collaboration=False,
    )

    try:
        print("Waiting for agent to propose a plan (up to 120s)...")
        if not _wait_for_plan_status(env_uuid, "proposed", timeout=120):
            print("TIMEOUT — agent never proposed a plan. Check event_log.jsonl")
            sys.exit(1)
        print("Cycle 1 proposed. Human approving...")
        _post_action(r, env_uuid, "human", "APPROVE_PLAN()")
        print("Waiting for cycle 1 to be mock-applied...")
        if not _wait_for_plan_status(env_uuid, "cycle_complete", timeout=60):
            print("TIMEOUT — check workdir/results for event_log.jsonl")
            sys.exit(1)

        print("Starting cycle 2...")
        _post_action(r, env_uuid, "human", "START_NEXT_CYCLE()")
        if not _wait_for_plan_status(env_uuid, "proposed", timeout=120):
            print("TIMEOUT — agent never proposed cycle 2. Check event_log.jsonl")
            sys.exit(1)
        print("Cycle 2 proposed. Human approving...")
        _post_action(r, env_uuid, "human", "APPROVE_PLAN()")
        if not _wait_for_plan_status(env_uuid, "cycle_complete", timeout=60):
            print("TIMEOUT — cycle 2 was not mock-applied")
            sys.exit(1)

        print("Two cycles approved. Ending session...")
        _post_action(r, env_uuid, "human", "FINISH()")
        time.sleep(3)
        perf_path = Path(RESULT_DIR) / env_uuid / "task_performance.json"
        if perf_path.exists():
            perf = json.loads(perf_path.read_text())
        else:
            perf = {"plan_status": "approved", "note": "see event_log.jsonl"}
        print("SUCCESS — distributed session completed.")
        print(json.dumps(perf, indent=2))
        print(f"Event log: {RESULT_DIR}/{env_uuid}/event_log.jsonl")
    finally:
        runner.cleanup_subprocesses()


if __name__ == "__main__":
    main()
