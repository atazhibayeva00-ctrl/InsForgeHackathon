#!/usr/bin/env python3
"""Smoke test for the Phase 2 distributed Co-Gym server.

Requires:
  brew services start redis
  cd backend && uvicorn collaborative_gym.server:app --port 8000

The test uses the server API and WebSocket path, not direct Runner access.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Any

import httpx
import websockets

HTTP_BASE = os.getenv("COGYM_HTTP_BASE", "http://127.0.0.1:8000")
WS_BASE = os.getenv("COGYM_WS_BASE", "ws://127.0.0.1:8000")
USER_ID = "human"


async def _wait_for_plan_status(ws, status: str, timeout: int = 120) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        raw = await asyncio.wait_for(ws.recv(), timeout=max(1, deadline - time.time()))
        message = json.loads(raw)
        observation = message.get("observation") or {}
        if observation.get("plan_status") == status:
            return message
    raise TimeoutError(f"Timed out waiting for plan_status={status!r}")


async def main() -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        health = await client.get(f"{HTTP_BASE}/api/health")
        health.raise_for_status()

        init = await client.post(
            f"{HTTP_BASE}/api/init_env",
            json={
                "user_id": USER_ID,
                "env_class": "investment",
                "env_args": {
                    "query": "Balanced long-term growth with moderate risk",
                    "cash_balance": 5000.0,
                },
            },
        )
        init.raise_for_status()
        payload = init.json()
        session_id = payload["session_id"]
        user_id = payload["user_id"]
        print(f"Session started: {session_id} ({user_id})")

        async with websockets.connect(f"{WS_BASE}/ws/{session_id}/{user_id}") as ws:
            await ws.send(json.dumps({"type": "request_state"}))
            proposed = await _wait_for_plan_status(ws, "proposed")
            plan = proposed["observation"]["plan"]
            print("Cycle 1 proposed:", plan["message"][:100].replace("\n", " "), "...")

            approve = await client.post(
                f"{HTTP_BASE}/api/post_action/{session_id}/{user_id}",
                json={"action": "APPROVE_PLAN()"},
            )
            approve.raise_for_status()
            await _wait_for_plan_status(ws, "cycle_complete", timeout=60)
            print("Cycle 1 approved and mock-applied")

            next_cycle = await client.post(
                f"{HTTP_BASE}/api/post_action/{session_id}/{user_id}",
                json={"action": "START_NEXT_CYCLE()"},
            )
            next_cycle.raise_for_status()
            proposed = await _wait_for_plan_status(ws, "proposed")
            plan = proposed["observation"]["plan"]
            print("Cycle 2 proposed:", plan["message"][:100].replace("\n", " "), "...")

            approve = await client.post(
                f"{HTTP_BASE}/api/post_action/{session_id}/{user_id}",
                json={"action": "APPROVE_PLAN()"},
            )
            approve.raise_for_status()
            await _wait_for_plan_status(ws, "cycle_complete", timeout=60)
            print("Cycle 2 approved and mock-applied")

            finish = await client.post(
                f"{HTTP_BASE}/api/post_action/{session_id}/{user_id}",
                json={"action": "FINISH()"},
            )
            finish.raise_for_status()

        result = await client.get(f"{HTTP_BASE}/api/result/{session_id}")
        result.raise_for_status()
        data = result.json()
        print("Events:", len(data["event_log"]))
        print("Task performance:", data["task_performance"])


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
