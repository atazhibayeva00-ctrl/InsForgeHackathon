import asyncio
import json
import re
import signal
import sys
from typing import AsyncIterator, Self

from aact import NodeFactory, Message
from websocket import WebSocket

from collaborative_gym.core import ObservationTypes, logger
from collaborative_gym.nodes.agent_interface import AGENT_TO_PID_KEY
from collaborative_gym.nodes.base_node import BaseNode
from collaborative_gym.nodes.commons import JsonObj
from collaborative_gym.utils.code_executor import JupyterManager


def reformat_observation(raw_observation, obs_type):
    """
    Format raw observations into a structured format for GUI display.

    Processes different types of observations (Jupyter notebook, distance matrix,
    travel search results) into a consistent format for the frontend display.

    Args:
        raw_observation: Dictionary containing raw observation data
        obs_type: Dictionary mapping observation keys to their types

    Returns:
        list: List of formatted observation spaces with name, content, and type
    """
    observation_space = []
    for k in obs_type:
        if k not in raw_observation:
            continue
        # Ensure the content matches the type
        if obs_type[k] == ObservationTypes.JUPYTER_NOTEBOOK:
            content = JupyterManager.str_to_execution_history(raw_observation[k])
        elif obs_type[k] == ObservationTypes.DISTANCE_MATRIX:
            if "query" not in raw_observation[k] or "output" not in raw_observation[k]:
                continue
            match = re.search(r"mode:\s*([\w\s]+)\)", raw_observation[k]["query"])
            if match:
                mode = match.group(1).strip()
            else:
                mode = "unknown"
            content = {
                "mode": mode,
                "origins": raw_observation[k]["output"]["origin_addresses"],
                "destinations": raw_observation[k]["output"]["destination_addresses"],
                "distances": [
                    [col["distance"] for col in row]
                    for row in raw_observation[k]["output"]["matrix"]
                ],
                "durations": [
                    [col["duration"] for col in row]
                    for row in raw_observation[k]["output"]["matrix"]
                ],
            }
        elif obs_type[k] == ObservationTypes.TRAVEL_SEARCH:
            if "query" not in raw_observation[k] or "output" not in raw_observation[k]:
                continue
            query = raw_observation[k]["query"]
            output = raw_observation[k]["output"]
            location = ""
            if raw_observation[k]["query"].startswith("Internet Search"):
                match = re.search(r"query:\s*([^)]+)\)", query)
                query = match.group(1).strip() if match else ""
                content = {
                    "mode": "web",
                    "query": query,
                    "location": location,
                    "results": [
                        {
                            "title": r["title"],
                            "url": r["url"],
                            "snippet": r["snippets"][0],
                        }
                        for r in output
                    ],
                }
            elif raw_observation[k]["query"].startswith("Business Search"):
                term_match = re.search(r"term:\s*([^,]+)", query)
                location_match = re.search(r"location:\s*([^,]+)", query)
                query = term_match.group(1).strip() if term_match else ""
                location = location_match.group(1).strip() if location_match else ""

                content = {
                    "mode": "places",
                    "query": query,
                    "location": location,
                    "results": [
                        {
                            "title": r["name"],
                            "url": r["url"],
                            "address": r["address"],
                            **{
                                k: r[k]
                                for k in ["rating", "price"]
                                if r[k] != "No information"
                            },
                        }
                        for r in output
                    ],
                }
            else:
                continue  # Unknown query type
        elif obs_type[k] == ObservationTypes.NO_RENDER:
            continue
        else:
            content = raw_observation[k]
        observation_space.append(
            {
                "name": k.replace("_", " ").capitalize(),
                "content": content,
                "type": str(obs_type[k]),
            }
        )
    return observation_space


def reformat_confirmations(confirmations):
    """Format confirmations into a structured format for GUI display.

    Args:
        confirmations: dict, request_id -> {requester, timestamp, pending_action}

    Returns:
        list: List of formatted confirmations, sorted by timestamp in ascending order
    """
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
        key=lambda x: x["timestamp"],
    )


@NodeFactory.register("gui_user_listen")
class GUIUserListenNode(BaseNode[JsonObj, JsonObj]):
    """
    Asynchronous node for managing GUI-based user interactions via WebSocket.

    Handles bidirectional communication between the frontend GUI and the environment
    through WebSocket and Redis channels. Manages real-time updates of team member
    states, observation processing, and event handling.

    Type Parameters:
        JsonObj: Both input and output message types use JSON-serializable objects

    Attributes:
        env_uuid: Unique identifier for the environment instance
        node_name: Name/role of this GUI user interface
        team_member_state: Dict tracking status and actions of team members
        team_member_finished: Flag indicating task completion
        websocket: WebSocket connection to the frontend
        is_websocket_open: Flag indicating WebSocket connection status
        listener_task: Background task for WebSocket message listening
    """

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
                (
                    f"{env_uuid}/step",
                    JsonObj,
                ),  # For monitoring team members' activities
                (
                    f"{env_uuid}/{node_name}/answer_state",
                    JsonObj,
                ),  # For frontend update
            ],
            output_channel_types=[
                (
                    f"{env_uuid}/{node_name}/request_state",
                    JsonObj,
                ),  # For frontend update
            ],
            redis_url=redis_url,
        )
        self.env_uuid = env_uuid
        self.node_name = node_name
        self.team_member_state = {
            team_member: {
                "status": "working",
                "action": "Agent starts working on the task...",
            }
            for team_member in team_members
        }
        self.team_member_finished = False
        self.websocket = websocket
        self.is_websocket_open = True

        # Register the signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    async def __aenter__(self) -> Self:
        self.listener_task = asyncio.create_task(self.websocket_listener())
        return await super().__aenter__()

    async def websocket_listener(self):
        """
        Background listener for WebSocket messages from the frontend.

        Continuously listens for incoming messages from the WebSocket connection
        and handles specific message types like state requests. Runs as a
        background task to maintain real-time communication.

        Raises:
            asyncio.CancelledError: When the listener task is cancelled
        """
        try:
            while True:
                data = await self.websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "request_state":
                    logger.info(
                        f"GUIUserListenNode ({self.node_name}): received request_state message from GUI"
                    )
                    await self.r.publish(
                        f"{self.env_uuid}/{self.node_name}/request_state",
                        Message[JsonObj](data=JsonObj(object={})).model_dump_json(),
                    )

        except asyncio.CancelledError:
            logger.info(
                "GUIUserListenNode ({self.node_name}): WebSocket listener task cancelled."
            )
        except Exception as e:
            pass

    async def close_websocket(self):
        """
        Close the WebSocket connection gracefully.

        Attempts to close the WebSocket connection and updates the connection
        status flag. Handles any exceptions during closure to ensure clean
        shutdown.
        """
        try:
            await self.websocket.close()
        except Exception as e:
            pass
        finally:
            self.is_websocket_open = False

    def handle_signal(self, signal, frame):
        """
        Handle system termination signals.

        Sets up signal handlers for SIGINT and SIGTERM to ensure graceful
        shutdown of the WebSocket connection when the process is terminated.

        Args:
            signal: The signal number received
            frame: Current stack frame
        """
        asyncio.create_task(self.close_websocket())
        sys.exit(0)

    async def websocket_send_message(self, payload: dict):
        """
        Send a message through the WebSocket connection.

        Safely sends JSON messages to the frontend, handling connection status
        and closure scenarios appropriately.

        Args:
            payload: Dictionary containing the message to send
        """
        if self.is_websocket_open:
            try:
                await self.websocket.send_json(payload)
            except Exception as e:
                logger.debug(
                    f"GUIUserListenNode ({self.node_name}): Error in sending message to GUI: {e}"
                )
                # Handle WebSocket closing here if needed
                await self.close_websocket()

    async def check_team_member_process(self):
        """
        Verify the status of team member processes.

        Checks if each team member's process is still running by verifying
        their PID in Redis. Updates team member state if a process has failed.
        """
        for team_member in self.team_member_state:
            if self.team_member_state[team_member]["status"] == "failed":
                continue
            team_member_pid_exist = await self.r.exists(AGENT_TO_PID_KEY)
            if team_member_pid_exist:
                team_member_pid_exist = await self.r.hexists(
                    AGENT_TO_PID_KEY, f"{self.env_uuid}_{team_member}"
                )
            if not team_member_pid_exist:
                self.team_member_state[team_member]["status"] = "failed"
                self.team_member_state[team_member][
                    "action"
                ] = "The agent process terminates. Please finish the session and try again."

    async def event_handler(
        self, input_channel: str, input_message: Message[JsonObj]
    ) -> AsyncIterator[tuple[str, Message[JsonObj]]]:
        """
        Process incoming messages and update GUI state.

        Handles various message types:
        1. Start: Initialize the GUI interface
        2. Observation: Update display with new observations
        3. Answer State: Update team member states and observations
        4. Step: Track team member actions and status
        5. End: Handle task completion and cleanup

        Args:
            input_channel: The Redis channel receiving the message
            input_message: The received message containing task data

        Returns:
            AsyncIterator yielding (channel, message) pairs for responses
        """
        if input_channel == f"{self.env_uuid}/start":
            payload = {
                "type": "start",
                "team_member_state": self.team_member_state,
            }
            await self.websocket_send_message(payload)
        elif input_channel == f"{self.env_uuid}/{self.node_name}/observation":
            # await asyncio.sleep(5)
            observation = input_message.data.object["observation"]
            obs_type = input_message.data.object["observation_type"]
            pending_confirmations = input_message.data.object["pending_confirmations"]
            payload = {
                "type": "observation",
                "observation_space": reformat_observation(
                    raw_observation=observation, obs_type=obs_type
                ),
                "chat_history": input_message.data.object["chat_history"],
                "pending_confirmations": reformat_confirmations(pending_confirmations),
                "agent_asleep": input_message.data.object["agent_asleep"],
            }
            await self.update_last_active_time()
            await self.websocket_send_message(payload)
        elif input_channel == f"{self.env_uuid}/{self.node_name}/answer_state":
            observation = input_message.data.object["observation"]
            obs_type = input_message.data.object["observation_type"]
            pending_confirmations = input_message.data.object["pending_confirmations"]
            await self.check_team_member_process()
            payload = {
                "type": "answer_state",
                "is_env_started": True,  # FIXME: unsafe
                "observation_space": reformat_observation(
                    raw_observation=observation, obs_type=obs_type
                ),
                "chat_history": input_message.data.object["chat_history"],
                "pending_confirmations": reformat_confirmations(pending_confirmations),
                "team_member_state": self.team_member_state,
                "agent_asleep": input_message.data.object["agent_asleep"],
            }
            await self.update_last_active_time()
            await self.websocket_send_message(payload)
        elif input_channel == f"{self.env_uuid}/step":
            role = input_message.data.object["role"]
            if role in self.team_member_state:
                action_str = input_message.data.object["action"]
                if action_str.startswith("WAIT_TEAMMATE_CONTINUE"):
                    self.team_member_state[role]["status"] = "idle"
                    self.team_member_state[role][
                        "action"
                    ] = "Agent is waiting for your message/action..."
                elif action_str.startswith("FINISH"):
                    self.team_member_finished = True
                    self.team_member_state[role]["status"] = "idle"
                    self.team_member_state[role]["action"] = ""
                else:
                    self.team_member_state[role]["status"] = "working"
                    # FIXME: This is a temporary solution to display the current action of the team member
                    if action_str.startswith("EXECUTE_JUPYTER_CELL"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is writing code in Jupyter Notebook..."
                    elif action_str.startswith(
                        "EDITOR_UPDATE"
                    ) or action_str.startswith("POLISH_DRAFT_WITH_LIBRARY"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is updating the editor..."
                    elif action_str.startswith("ADD_PAPER_TO_LIBRARY"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is adding papers to the library..."
                    elif action_str.startswith("DROP_PAPER_FROM_LIBRARY"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is dropping papers from the library..."
                    elif action_str.startswith("LIBRARY_TO_DRAFT"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is writing draft based on the current library..."
                    elif action_str.startswith("SEARCH_ARXIV"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is searching papers on arXiv..."
                    elif action_str.startswith("FLIGHT_SEARCH"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is searching for flights..."
                    elif action_str.startswith("ACCOMMODATION_SEARCH"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is searching for accommodations..."
                    elif action_str.startswith("RESTAURANT_SEARCH"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is searching for restaurants..."
                    elif action_str.startswith("ATTRACTION_SEARCH"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is searching for attractions..."
                    elif action_str.startswith("DISTANCE_MATRIX"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is calculating distance matrix..."
                    elif action_str.startswith("BUSINESS_SEARCH"):
                        self.team_member_state[role][
                            "action"
                        ] = "Agent is searching for places/businesses..."
                    elif action_str.startswith("INTERNET_SEARCH"):
                        self.team_member_state[role]["action"] = "Searching the web..."
                await self.check_team_member_process()
                payload = {
                    "type": "update_team_member_state",
                    "team_member_state": self.team_member_state,
                }
                await self.update_last_active_time()
                await self.websocket_send_message(payload)
        elif input_channel == f"{self.env_uuid}/end":
            if self.team_member_finished:
                # Notify the GUI that the team member has finished the task
                payload = {
                    "type": "team_member_finished",
                }
                await self.websocket_send_message(payload)
            if not self.listener_task.done():
                self.listener_task.cancel()
                await self.listener_task  # Await the task to finish gracefully

            await self.close_websocket()
            logger.info(f"GUIUserListenNode ({self.node_name}) shutdown gracefully.")
        else:
            yield input_channel, Message[JsonObj](
                data=JsonObj(
                    object={"error": "GUIUserListenNode should not send message."}
                )
            ).model_dump_json()

    async def event_loop(
        self,
    ) -> None:
        """
        Main event processing loop for handling GUI interactions.

        Continuously processes incoming messages from Redis channels and
        routes them to appropriate handlers. This node primarily listens
        and updates the GUI, avoiding direct message publishing.

        Returns:
            None

        Raises:
            Exception: If the event loop exits unexpectedly
        """
        async for input_channel, input_message in self._wait_for_input():
            async for output_channel, output_message in self.event_handler(
                input_channel, input_message
            ):
                # await self.r.publish(output_channel, output_message.model_dump_json())
                pass  # GUI User Listen Node should not send messages
        raise Exception("Event loop exited unexpectedly")
