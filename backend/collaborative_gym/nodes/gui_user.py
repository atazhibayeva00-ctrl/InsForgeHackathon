"""GUI user node for the investment Co-Gym server.

This node bridges Redis observations from ``TaskEnvNode`` to a FastAPI
WebSocket. It intentionally keeps the payload simple so the existing Vite app
can adapt it without adopting the full upstream Co-Gym workbench.
"""

from __future__ import annotations

import asyncio
import json
import signal
from typing import Any, AsyncIterator

from aact import Message
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from collaborative_gym.core import ObservationTypes, logger
from collaborative_gym.nodes.base_node import BaseNode
from collaborative_gym.nodes.commons import JsonObj


def reformat_observation(
    raw_observation: dict[str, Any], obs_type: dict[str, ObservationTypes]
) -> list[dict[str, Any]]:
    observation_space = []
    for key, render_type in obs_type.items():
        if key not in raw_observation or render_type == ObservationTypes.NO_RENDER:
            continue
        observation_space.append(
            {
                "name": key.replace("_", " ").capitalize(),
                "content": raw_observation[key],
                "type": str(render_type),
            }
        )
    return observation_space


def reformat_confirmations(confirmations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "id": request_id,
                "requester": confirmation["requester"],
                "timestamp": confirmation["timestamp"],
                "action": confirmation["pending_action"],
            }
            for request_id, confirmation in confirmations.items()
        ],
        key=lambda item: item["timestamp"],
    )


class GUIUserListenNode(BaseNode[JsonObj, JsonObj]):
    """Listen for a GUI user's observation stream and push it over WebSocket."""

    def __init__(
        self,
        env_uuid: str,
        node_name: str,
        team_members: list[str],
        websocket: WebSocket,
        redis_url: str = "redis://localhost:6379/0",
    ):
        super().__init__(
            input_channel_types=[
                (f"{env_uuid}/{node_name}/observation", JsonObj),
                (f"{env_uuid}/start", JsonObj),
                (f"{env_uuid}/end", JsonObj),
                (f"{env_uuid}/step", JsonObj),
                (f"{env_uuid}/{node_name}/answer_state", JsonObj),
            ],
            output_channel_types=[(f"{env_uuid}/{node_name}/request_state", JsonObj)],
            redis_url=redis_url,
        )
        self.env_uuid = env_uuid
        self.node_name = node_name
        self.websocket = websocket
        self.team_member_state = {
            team_member: {
                "status": "working",
                "action": "Agent starts working on the task...",
            }
            for team_member in team_members
        }
        self.team_member_finished = False
        self.listener_task: asyncio.Task | None = None
        self.is_websocket_open = True

        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    async def __aenter__(self):
        self.listener_task = asyncio.create_task(self.websocket_listener())
        return await super().__aenter__()

    async def __aexit__(self, *args: Any) -> None:
        if self.listener_task:
            self.listener_task.cancel()
        await super().__aexit__(*args)

    def handle_signal(self, signum, frame):  # noqa: ANN001
        if self.listener_task:
            self.listener_task.cancel()

    async def websocket_listener(self) -> None:
        try:
            while True:
                raw = await self.websocket.receive_text()
                message = json.loads(raw)
                if message.get("type") == "request_state":
                    await self.r.publish(
                        f"{self.env_uuid}/{self.node_name}/request_state",
                        Message[JsonObj](data=JsonObj(object={})).model_dump_json(),
                    )
        except asyncio.CancelledError:
            logger.info("GUIUserListenNode (%s): listener cancelled", self.node_name)
        except WebSocketDisconnect:
            self.is_websocket_open = False
            logger.info("GUIUserListenNode (%s): websocket disconnected", self.node_name)
        except Exception as exc:  # noqa: BLE001
            self.is_websocket_open = False
            logger.info("GUIUserListenNode (%s): listener closed: %s", self.node_name, exc)

    async def _safe_send_json(self, payload: dict[str, Any]) -> bool:
        if (
            not self.is_websocket_open
            or self.websocket.client_state != WebSocketState.CONNECTED
        ):
            return False
        try:
            await self.websocket.send_json(payload)
            return True
        except (RuntimeError, WebSocketDisconnect):
            self.is_websocket_open = False
            return False

    async def event_handler(
        self, input_channel: str, input_message: Message[JsonObj]
    ) -> AsyncIterator[tuple[str, Message[JsonObj]]]:
        data = input_message.data.object

        if input_channel == f"{self.env_uuid}/start":
            await self._safe_send_json(
                {
                    "type": "start",
                    "task_description": data["task_description"],
                    "action_space": data["action_space"],
                    "team_members": data["team_members"],
                }
            )

        elif input_channel == f"{self.env_uuid}/{self.node_name}/observation":
            await self._send_observation("observation", data)

        elif input_channel == f"{self.env_uuid}/{self.node_name}/answer_state":
            await self._send_observation("state", data)

        elif input_channel == f"{self.env_uuid}/step":
            actor = data.get("role")
            action = data.get("action", "")
            if actor in self.team_member_state:
                self.team_member_state[actor] = {"status": "working", "action": action}
            await self._safe_send_json(
                {
                    "type": "team_member_action",
                    "role": actor,
                    "action": action,
                    "team_member_state": self.team_member_state,
                }
            )

        elif input_channel == f"{self.env_uuid}/end":
            self.team_member_finished = True
            await self._safe_send_json({"type": "end", "result_dir": data.get("result_dir")})
            raise asyncio.CancelledError

        if False:
            yield "", Message[JsonObj](data=JsonObj(object={}))

    async def _send_observation(self, message_type: str, data: dict[str, Any]) -> None:
        observation = data["observation"]
        payload = {
            "type": message_type,
            "observation": observation,
            "observation_space": reformat_observation(
                observation, data.get("observation_type", {})
            ),
            "observation_type": {
                key: str(value) for key, value in data.get("observation_type", {}).items()
            },
            "reward": data.get("reward", 0),
            "info": data.get("info", {}),
            "chat_history": data.get("chat_history", []),
            "pending_confirmations": reformat_confirmations(
                data.get("pending_confirmations", {})
            ),
            "agent_asleep": data.get("agent_asleep", False),
            "team_member_state": self.team_member_state,
        }
        await self._safe_send_json(payload)
