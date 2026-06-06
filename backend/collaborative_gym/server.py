"""Investment-focused Co-Gym distributed server.

This is the Phase 2 bridge between a frontend and the Redis-backed Co-Gym
runtime:

- ``POST /api/init_env`` creates an ``investment`` session and starts Runner.
- ``POST /api/post_action/{session_id}/{user_id}`` publishes human actions.
- ``WS /ws/{session_id}/{user_id}`` streams observations/chat updates.

The older ``backend/main.py`` remains as the synchronous demo API. Run this app
when testing the distributed stack:

    uvicorn collaborative_gym.server:app --reload --port 8000
"""

from __future__ import annotations

import atexit
import asyncio
import json
import os
import signal
import sys
import uuid
from pathlib import Path
from threading import Thread
from typing import Any

import redis
import toml
from aact import Message
from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware

from collaborative_gym.core import TeamMemberConfig
from collaborative_gym.nodes.commons import JsonObj
from collaborative_gym.nodes.gui_user import GUIUserListenNode
from collaborative_gym.runner import Runner
from collaborative_gym.utils.utils import load_api_key

BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORKDIR = BACKEND_ROOT / "workdir" / "server_local_storage"
WORKDIR.mkdir(parents=True, exist_ok=True)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
AGENT_NAME = "agent"
DISABLE_AGENT = os.getenv("DISABLE_AGENT", "false").lower() == "true"

load_api_key(str(BACKEND_ROOT / "secrets.toml"))

app = FastAPI(title="Collaborative Investment Copilot - Distributed Co-Gym")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_client = redis.Redis.from_url(REDIS_URL)
redis_async_client = redis.asyncio.from_url(REDIS_URL)
runner = Runner(result_dir=str(WORKDIR), redis_url=REDIS_URL)


def _require_redis() -> None:
    try:
        redis_client.ping()
    except redis.exceptions.ConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Redis is not running. Start it with `brew services start redis` "
                "or run Docker Desktop and `docker compose up -d`."
            ),
        ) from exc


def _member_name(user_id: str) -> str:
    """Map frontend user IDs to the actual Co-Gym team member name."""
    if user_id == "human" or user_id.startswith("user_"):
        return user_id
    return f"user_{user_id}"


def _agent_command() -> str:
    return (
        f"{sys.executable} -m demo_agent.investment_collaborative_agent.agent "
        "--wait-time 1 --enhance-user-control"
    )


def _default_env_args() -> dict[str, Any]:
    return {
        "query": "Balanced long-term growth with moderate risk",
        "cash_balance": 5000.0,
    }


async def _parse_init_request(
    request: Request,
    user_id: str | None,
    env_class: str | None,
    env_args: str | None,
    file: UploadFile | None,
) -> tuple[str, str, dict[str, Any]]:
    """Accept both Co-Gym form posts and JSON requests from the Vite app."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        parsed_user_id = body.get("user_id", user_id or "human")
        parsed_env_class = body.get("env_class", env_class or "investment")
        parsed_env_args = body.get("env_args", _default_env_args())
        if isinstance(parsed_env_args, str):
            parsed_env_args = json.loads(parsed_env_args)
        return parsed_user_id, parsed_env_class, parsed_env_args

    parsed_user_id = user_id or "human"
    parsed_env_class = env_class or "investment"
    parsed_env_args = json.loads(env_args) if env_args else _default_env_args()
    if file is not None:
        raw = await file.read()
        parsed_env_args["portfolio_csv"] = raw.decode("utf-8")
    return parsed_user_id, parsed_env_class, parsed_env_args


@app.get("/api/health")
def health() -> dict[str, str]:
    _require_redis()
    return {"status": "ok", "redis": "ok"}


@app.post("/api/init_env")
async def init_environment(
    request: Request,
    user_id: str | None = Form(None),
    env_class: str | None = Form(None),
    env_args: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    _require_redis()
    try:
        raw_user_id, env_class_name, parsed_env_args = await _parse_init_request(
            request=request,
            user_id=user_id,
            env_class=env_class,
            env_args=env_args,
            file=file,
        )
        if env_class_name != "investment":
            raise HTTPException(status_code=400, detail="Only investment env is enabled")

        session_uuid = uuid.uuid4().hex[:12]
        user_member = _member_name(raw_user_id)
        env_config_path = WORKDIR / f"env_{session_uuid}_config.toml"
        env_config_path.write_text(
            toml.dumps({"env_class": "investment", "env_args": parsed_env_args})
        )

        members = [TeamMemberConfig(name=user_member, type="gui_user")]
        if not DISABLE_AGENT:
            members.append(
                TeamMemberConfig(
                    name=AGENT_NAME,
                    type="agent",
                    start_node_base_command=_agent_command(),
                )
            )

        thread = Thread(
            target=runner.start_session,
            args=(
                session_uuid,
                str(env_config_path),
                members,
                100,
                False,
                False,
                120,
                30,
            ),
            daemon=True,
        )
        thread.start()

        return {
            "message": "Environment initialized",
            "session_id": session_uuid,
            "user_id": user_member,
            "env_class": env_class_name,
        }
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/post_action/{session_id}/{user_id}")
async def post_user_action(request: Request, session_id: str, user_id: str):
    _require_redis()
    if not runner.check_session_exists(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    data = await request.json()
    action_str = data["action"]
    payload = {"action": action_str, "role": _member_name(user_id)}
    await redis_async_client.publish(
        f"env_{session_id}/step",
        Message[JsonObj](data=JsonObj(object=payload)).model_dump_json(),
    )
    return {"status": "success", "message": f"Received action: {action_str}"}


@app.websocket("/ws/{session_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str, user_id: str):
    await websocket.accept()
    if not runner.check_session_exists(session_id):
        await websocket.close(code=4000, reason="Session not found")
        return

    try:
        async with GUIUserListenNode(
            env_uuid=f"env_{session_id}",
            node_name=_member_name(user_id),
            team_members=[AGENT_NAME],
            websocket=websocket,
            redis_url=REDIS_URL,
        ) as user_listen_node:
            await user_listen_node.event_loop()
    except (WebSocketDisconnect, asyncio.CancelledError):
        return
    except RuntimeError as exc:
        if "websocket" in str(exc).lower():
            return
        raise


@app.get("/api/result/{session_id}")
def get_result(session_id: str) -> dict[str, Any]:
    session_dir = WORKDIR / f"env_{session_id}"
    event_log_path = session_dir / "event_log.jsonl"
    perf_path = session_dir / "task_performance.json"
    if not event_log_path.exists():
        raise HTTPException(status_code=404, detail="Result not found")

    event_log = [
        json.loads(line) for line in event_log_path.read_text().splitlines() if line
    ]
    task_performance = (
        json.loads(perf_path.read_text()) if perf_path.exists() else None
    )
    return {"event_log": event_log, "task_performance": task_performance}


def _cleanup() -> None:
    runner.cleanup_subprocesses()


def _handle_exit_signal(signum, frame):  # noqa: ANN001
    _cleanup()
    sys.exit(0)


atexit.register(_cleanup)
signal.signal(signal.SIGINT, _handle_exit_signal)
signal.signal(signal.SIGTERM, _handle_exit_signal)
