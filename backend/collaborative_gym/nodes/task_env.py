import asyncio
import json
import os
import sys
import time
from typing import AsyncIterator, Literal, Union

from aact import NodeFactory, Node, Message

from collaborative_gym.core import (
    SendTeammateMessage,
    WaitTeammateContinue,
    logger,
    RequestTeammateConfirm,
    AcceptConfirmation,
    RejectConfirmation,
    PutAgentAsleep,
    WakeAgentUp,
)
from collaborative_gym.envs.config import EnvConfig
from collaborative_gym.envs import EnvFactory
from collaborative_gym.nodes.base_node import BaseNode
from collaborative_gym.nodes.commons import JsonObj
from collaborative_gym.utils.time import get_formatted_local_time

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


@NodeFactory.register("task_env")
class TaskEnvNode(BaseNode[JsonObj, JsonObj]):
    """
    Asynchronous node for managing collaborative task environments and team interactions.

    This node handles the core environment functionality, including state management,
    action processing, and team communication. It supports both environment-specific
    actions and collaborative actions between team members.

    Type Parameters:
        JsonObj: Both input and output message types use JSON-serializable objects

    Attributes:
        env_uuid: Unique identifier for this environment instance
        env: The actual environment instance being managed
        team_members: List of team member names/roles
        event_log: List of action records with timestamps and outcomes
        chat_history: List of communication messages between team members
        pending_confirmations: Dictionary of pending confirmation requests
        result_dir: Directory for storing task results and logs
        collaboration_acts: Available collaboration actions (message, wait)
        disable_collaboration: Flag to disable collaboration features
        task_completed: Flag indicating if the task is finished
        tick_interval: Time between activity checks in seconds
        tick_cnt: Number of ticks since last activity
        max_tick_cnt: Maximum allowed ticks before timeout
        last_step_timestamp: Time of last environment step
        max_steps: Maximum allowed steps per agent type
    """

    def __init__(
        self,
        env_config: Union[EnvConfig, dict],
        env_uuid: str,
        team_members: list[str],
        disable_collaboration: bool = False,
        max_steps: int = 100,
        tick_interval: float = 60,
        max_tick_cnt: int = 5,
        result_dir: str = "./workdir/results",
        redis_url: str = "redis://localhost:6379/0",
    ):
        super().__init__(
            input_channel_types=[
                (f"{env_uuid}/step", JsonObj),
                (f"{env_uuid}/tick", JsonObj),
            ]
            + [
                (f"{env_uuid}/{node_name}/request_state", JsonObj)
                for node_name in team_members
                # For frontend update
            ],
            output_channel_types=[
                # (f"{env_uuid}/observation", JsonObj),
                (f"{env_uuid}/start", JsonObj),
                (f"{env_uuid}/end", JsonObj),
            ]
            + [
                (f"{env_uuid}/{node_name}/observation", JsonObj)
                for node_name in team_members
            ]
            + [
                (f"{env_uuid}/{node_name}/answer_state", JsonObj)
                for node_name in team_members
                # For frontend update
            ],
            redis_url=redis_url,
        )
        if type(env_config) is dict:
            env_config = EnvConfig(**env_config)
        self.env_uuid = env_uuid
        self.env = EnvFactory.make(
            name=env_config.env_class,
            team_members=team_members,
            env_id=env_uuid,
            **env_config.env_args.model_dump(),
        )
        self.team_members = team_members
        # [{'role': ..., 'timestamp': ..., 'action': ..., 'action_status': ..., 'action_type': ...}, ...]
        self.event_log = []
        # [{'role': ..., 'timestamp': ..., 'message': ...}, ...]
        self.chat_history = []
        # request_id -> {requester, timestamp, pending_action}
        self.pending_confirmations: dict[str, dict] = {}
        self.result_dir = result_dir
        os.makedirs(os.path.join(self.result_dir, self.env_uuid), exist_ok=True)
        with open(
            os.path.join(self.result_dir, self.env_uuid, "event_log.jsonl"), "w"
        ) as f:
            f.write("")

        self.collaboration_acts = {
            "send_teammate_message": SendTeammateMessage(),
            "wait_teammate_continue": WaitTeammateContinue(),
            "request_teammate_confirm": RequestTeammateConfirm(),
            "accept_confirmation": AcceptConfirmation(),
            "reject_confirmation": RejectConfirmation(),
            "put_agent_asleep": PutAgentAsleep(),
            "wake_agent_up": WakeAgentUp(),
        }
        self.disable_collaboration = disable_collaboration
        self.agent_asleep = False

        self.task_completed = False

        self.tick_interval = tick_interval
        self.tick_cnt = 0
        self.max_tick_cnt = max_tick_cnt
        self.last_step_timestamp = time.time()
        self.max_steps = max_steps

    def add_record_to_event_log(
        self,
        role: str,
        action: str,
        action_status: str,
        action_type: Literal["collaborative", "environment"],
    ):
        self.event_log.append(
            {
                "role": role,
                "timestamp": get_formatted_local_time(),
                "action": action,
                "action_status": action_status,
                "action_type": action_type,
                "current_chat_history": self.chat_history,
                "current_observation": self.env.get_obs(),
            }
        )
        with open(
            os.path.join(self.result_dir, self.env_uuid, "event_log.jsonl"), "a"
        ) as f:
            f.write(json.dumps(self.event_log[-1]) + "\n")

    def count_agent_action(self):
        agent_action_cnt = 0
        for e in self.event_log:
            if "agent" in e["role"]:
                agent_action_cnt += 1
        return agent_action_cnt

    def count_user_action(self):
        user_action_cnt = 0
        for e in self.event_log:
            if "user" in e["role"] or e["role"] == "human":
                user_action_cnt += 1
        return user_action_cnt

    def add_message_to_chat_history(self, role: str, message: str):
        self.chat_history.append(
            {"role": role, "timestamp": get_formatted_local_time(), "message": message}
        )

    def event_log_to_str(self) -> str:
        """(Deprecated) Convert the event log to a string."""
        history = "\n----------\n".join(
            [
                f'[{e["role"]}] takes an action: {e["action"]}\n[environment] {e["action_status"]}'
                for e in self.event_log
            ]
        )

        return history

    def add_pending_confirmation(
        self, request_id: str, requester: str, pending_action: str
    ):
        self.pending_confirmations[request_id] = {
            "requester": requester,
            "timestamp": get_formatted_local_time(),
            "pending_action": pending_action,
        }

    def remove_pending_confirmation(self, request_id: str):
        if request_id in self.pending_confirmations:
            return self.pending_confirmations.pop(request_id)
        return None

    def process_observation(self, obs: dict) -> dict[str, dict]:
        """
        Process raw environment observations into per-team-member observations.

        Takes the raw observation dictionary containing public and private information
        and creates personalized observation dictionaries for each team member.

        Args:
            obs: Raw observation dictionary with 'public' and 'private' sections

        Returns:
            Dictionary mapping team member roles to their personalized observations
        """
        return {
            role: {
                **obs["public"],
                **obs["private"][role],
            }
            for role in self.team_members
        }

    async def end(self):
        self.task_completed = True
        task_performance = self.env.evaluate_task_performance()
        os.makedirs(os.path.join(self.result_dir, self.env_uuid), exist_ok=True)
        with open(
            os.path.join(self.result_dir, self.env_uuid, "task_performance.json"), "w"
        ) as f:
            json.dump(task_performance, f, indent=4)
        self.env.close()
        await self.delete_process_record()

    async def event_loop(
        self,
    ) -> None:
        """
        Main event loop that initializes the environment and handles ongoing interactions.

        Overrides BaseNode's event_loop to add environment initialization. Resets the
        environment, broadcasts initial observations to all team members, and then
        processes incoming messages. Manages concurrent task processing and timeouts.

        Returns:
            None
        """
        # Reset the environment
        obs, info = self.env.reset()
        action_space = self.env.dump_action_space()
        if not self.disable_collaboration:
            # Add two core collaboration actions to the action space
            action_space += [
                self.collaboration_acts["send_teammate_message"].dump_json(),
                self.collaboration_acts["wait_teammate_continue"].dump_json(),
            ]

        # Indicate the start of the task
        payload = {
            "task_description": self.env.task_description,
            "action_space": action_space,
            "team_members": self.team_members,
            "example_question": self.env.example_question,  # For agent
            "example_trajectory": self.env.example_trajectory,  # For agent
            "additional_task_info": self.env.additional_task_info,  # For simulated user
        }
        try:
            query = getattr(self.env, "query", None) or getattr(self.env, "user_goal", "")
            start_action = f"START(task_description={self.env.task_description}, query={query})"
            for role in self.team_members:
                if "user" in role or role == "human":
                    self.add_message_to_chat_history(role=role, message=query)
                    break
        except Exception as e:
            start_action = f"START(task_description={self.env.task_description})"
        self.add_record_to_event_log(
            role="environment",
            action=start_action,
            action_status="succeeded",
            action_type="environment",
        )
        await self.r.publish(
            f"{self.env_uuid}/start",
            Message[JsonObj](data=JsonObj(object=payload)).model_dump_json(),
        )

        # Broadcast the initial observation
        processed_obs = self.process_observation(obs)
        for role in self.team_members:
            payload = {
                "observation": processed_obs[role],
                "observation_type": self.env.obs_type(),
                "reward": 0,
                "info": info,
                "chat_history": self.chat_history,
                "pending_confirmations": self.pending_confirmations,
                "agent_asleep": self.agent_asleep,
            }
            await self.r.publish(
                f"{self.env_uuid}/{role}/observation",
                Message[JsonObj](data=JsonObj(object=payload)).model_dump_json(),
            )

        await asyncio.sleep(1)
        self.last_step_timestamp = time.time()
        await super().event_loop()

    async def event_handler(
        self, input_channel: str, input_message: Message[JsonObj]
    ) -> AsyncIterator[tuple[str, Message[JsonObj]]]:
        """
        Process incoming messages and generate appropriate responses.

        Handles three types of messages:
        1. Step: Process actions from team members, update environment state
        2. Tick: Check for timeouts and send notifications
        3. Request State: Respond to frontend state queries

        Args:
            input_channel: The Redis channel receiving the message
            input_message: The received message containing action or request data

        Returns:
            AsyncIterator yielding (channel, message) pairs for responses

        Raises:
            asyncio.CancelledError: When task completes or times out
        """
        try:
            if input_channel == f"{self.env_uuid}/step":
                terminated = False
                reward = 0
                info = {}
                action_str = input_message.data.object["action"]
                role = input_message.data.object["role"]
                notify_others_only = False

                # Process collaborative actions
                if not self.disable_collaboration and self.collaboration_acts[
                    "send_teammate_message"
                ].contains(action_str):
                    self.add_record_to_event_log(
                        role=role,
                        action=action_str,
                        action_status="succeeded",
                        action_type="collaborative",
                    )
                    message = self.collaboration_acts["send_teammate_message"].parse(
                        action_str
                    )["message"]
                    self.add_message_to_chat_history(role=role, message=message)
                    obs = self.env.get_obs()
                    private = False
                    notify_others_only = True  # Only notify recipients of the message
                elif not self.disable_collaboration and self.collaboration_acts[
                    "wait_teammate_continue"
                ].contains(action_str):
                    return
                elif not self.disable_collaboration and self.collaboration_acts[
                    "request_teammate_confirm"
                ].contains(action_str):
                    parsed_action = self.collaboration_acts[
                        "request_teammate_confirm"
                    ].parse(action_str)
                    self.add_pending_confirmation(
                        request_id=parsed_action["request_id"],
                        requester=role,
                        pending_action=parsed_action["pending_action"],
                    )
                    self.add_record_to_event_log(
                        role=role,
                        action=action_str,
                        action_status="succeeded",
                        action_type="collaborative",
                    )
                    obs = self.env.get_obs()
                    private = False
                    notify_others_only = (
                        True  # The requester shall wait for the confirmation response
                    )
                elif not self.disable_collaboration and self.collaboration_acts[
                    "accept_confirmation"
                ].contains(action_str):
                    parsed_action = self.collaboration_acts[
                        "accept_confirmation"
                    ].parse(action_str)
                    confirmation = self.remove_pending_confirmation(
                        request_id=parsed_action["request_id"]
                    )
                    self.add_record_to_event_log(
                        role=role,
                        action=action_str,
                        action_status="succeeded",
                        action_type="collaborative",
                    )
                    # Execute the pending action
                    obs, reward, terminated, private, info = self.env.step(
                        role=confirmation["requester"],
                        action=confirmation["pending_action"],
                    )
                    self.add_record_to_event_log(
                        role=confirmation["requester"],
                        action=confirmation["pending_action"],
                        action_status="succeeded",
                        action_type="environment",
                    )
                elif not self.disable_collaboration and self.collaboration_acts[
                    "reject_confirmation"
                ].contains(action_str):
                    parsed_action = self.collaboration_acts[
                        "reject_confirmation"
                    ].parse(action_str)
                    self.remove_pending_confirmation(
                        request_id=parsed_action["request_id"]
                    )
                    self.add_record_to_event_log(
                        role=role,
                        action=action_str,
                        action_status="succeeded",
                        action_type="collaborative",
                    )
                    obs = self.env.get_obs()
                    private = False
                elif not self.disable_collaboration and self.collaboration_acts[
                    "put_agent_asleep"
                ].contains(action_str):
                    if self.agent_asleep:  # Already asleep
                        return
                    self.agent_asleep = True
                    self.add_record_to_event_log(
                        role=role,
                        action=action_str,
                        action_status="succeeded",
                        action_type="collaborative",
                    )
                    obs = self.env.get_obs()
                    private = False
                elif not self.disable_collaboration and self.collaboration_acts[
                    "wake_agent_up"
                ].contains(action_str):
                    if not self.agent_asleep:  # Already awake
                        return
                    self.agent_asleep = False
                    self.add_record_to_event_log(
                        role=role,
                        action=action_str,
                        action_status="succeeded",
                        action_type="collaborative",
                    )
                    obs = self.env.get_obs()
                    private = False
                    print("Agent is awake now.")
                else:
                    # Process environment actions
                    obs, reward, terminated, private, info = self.env.step(
                        role=role, action=action_str
                    )
                    action_status = "succeeded" if reward >= 0 else "failed"
                    if reward < 0 and "action_error" in info:
                        action_status += f' (action_error: {info["action_error"]})'
                        self.add_message_to_chat_history(
                            role="environment",
                            message=f'[{role}] takes an action but fails: {info["action_error"]}',
                        )
                    self.add_record_to_event_log(
                        role=role,
                        action=action_str,
                        action_status=action_status,
                        action_type="environment",
                    )

                if (
                    self.count_agent_action() >= self.max_steps
                    or self.count_user_action() >= self.max_steps
                ):
                    terminated = True

                if terminated:
                    await self.end()
                    yield f"{self.env_uuid}/end", Message[JsonObj](
                        data=JsonObj(
                            object={
                                "result_dir": os.path.join(
                                    self.result_dir, self.env_uuid
                                ),
                            }
                        )
                    )
                    raise asyncio.CancelledError
                else:
                    processed_obs = self.process_observation(obs)
                    if not private:
                        for team_member in self.team_members:
                            if (notify_others_only and team_member == role) or (
                                self.agent_asleep and "agent" in team_member
                            ):
                                continue
                            payload = {
                                "observation": processed_obs[team_member],
                                "observation_type": self.env.obs_type(),
                                "reward": reward,
                                "info": info,
                                "chat_history": self.chat_history,
                                "pending_confirmations": self.pending_confirmations,
                                "agent_asleep": self.agent_asleep,
                            }
                            logger.info(
                                f"EnvNode ({self.env_uuid}): sending notification to {team_member} with new observation"
                            )
                            yield f"{self.env_uuid}/{team_member}/observation", Message[
                                JsonObj
                            ](data=JsonObj(object=payload))
                    else:
                        payload = {
                            "observation": processed_obs[role],
                            "observation_type": self.env.obs_type(),
                            "reward": reward,
                            "info": info,
                            "chat_history": self.chat_history,
                            "pending_confirmations": self.pending_confirmations,
                            "agent_asleep": self.agent_asleep,
                        }
                        logger.info(
                            f"EnvNode ({self.env_uuid}): sending observation to {role} with new observation"
                        )
                        yield f"{self.env_uuid}/{role}/observation", Message[JsonObj](
                            data=JsonObj(object=payload)
                        )
                self.last_step_timestamp = time.time()
                await self.update_last_active_time()
            elif input_channel == f"{self.env_uuid}/tick":
                if time.time() - self.last_step_timestamp > self.tick_interval:
                    self.tick_cnt += 1
                    if self.tick_cnt > self.max_tick_cnt:
                        # Terminate the task environment if no action is taken for a long time
                        await self.end()
                        yield f"{self.env_uuid}/end", Message[JsonObj](
                            data=JsonObj(
                                object={
                                    "result_dir": os.path.join(
                                        self.result_dir, self.env_uuid
                                    ),
                                }
                            )
                        )
                        raise asyncio.CancelledError
                    logger.info(
                        f"EnvNode ({self.env_uuid}): notifying team members due to inactivity"
                    )
                    self.add_message_to_chat_history(
                        role="environment",
                        message="Idle for a long time. The agent should take an action. The user can also send a message.",
                    )
                    # If no action is taken for a long time, send a tick message
                    processed_obs = self.process_observation(self.env.get_obs())
                    for team_member in self.team_members:
                        if self.agent_asleep and "agent" in team_member:
                            continue
                        payload = {
                            "observation": processed_obs[team_member],
                            "observation_type": self.env.obs_type(),
                            "reward": 0,
                            "info": {},
                            "chat_history": self.chat_history,
                            "pending_confirmations": self.pending_confirmations,
                            "agent_asleep": self.agent_asleep,
                        }
                        yield f"{self.env_uuid}/{team_member}/observation", Message[
                            JsonObj
                        ](data=JsonObj(object=payload))
                    self.last_step_timestamp = time.time()
                    await self.update_last_active_time()
            elif "request_state" in input_channel:  # For frontend update
                role = input_channel.split("/")[-2]
                action_space = self.env.dump_action_space()
                if not self.disable_collaboration:
                    action_space += [
                        action.dump_json()
                        for action in self.collaboration_acts.values()
                    ]
                payload = {
                    "observation": self.process_observation(self.env.get_obs())[role],
                    "observation_type": self.env.obs_type(),
                    "task_description": self.env.task_description,
                    "action_space": action_space,
                    "chat_history": self.chat_history,
                    "pending_confirmations": self.pending_confirmations,
                    "agent_asleep": self.agent_asleep,
                }
                await self.update_last_active_time()
                yield f"{self.env_uuid}/{role}/answer_state", Message[JsonObj](
                    data=JsonObj(object=payload)
                )
        except Exception as e:
            logger.error(f"Error in EnvNode ({self.env_uuid}): {e}")


@NodeFactory.register("env_tick")
class TaskEnvTickNode(Node[JsonObj, JsonObj]):
    """
    Auxiliary node that manages timeouts and deadlock prevention in collaborative tasks.

    This node sends periodic tick messages to the task environment to check for
    inactivity and prevent deadlocks in simulated experiments where multiple agents
    might be waiting for each other.

    Type Parameters:
        JsonObj: Both input and output message types use JSON-serializable objects

    Attributes:
        env_uuid: Unique identifier for the associated environment
        tick_interval: Time between tick messages in seconds
    """

    def __init__(
        self,
        env_uuid: str,
        tick_interval: float = 30,
        redis_url: str = "redis://localhost:6379/0",
    ):
        super().__init__(
            input_channel_types=[(f"{env_uuid}/end", JsonObj)],
            output_channel_types=[(f"{env_uuid}/tick", JsonObj)],
            redis_url=redis_url,
        )
        self.env_uuid = env_uuid
        self.tick_interval = tick_interval

    async def tick_at_given_interval(self, channel: str, interval: float) -> None:
        """
        Send periodic tick messages with adaptive timing.

        Maintains consistent intervals between ticks by adjusting sleep duration
        based on actual elapsed time, compensating for processing delays.

        Args:
            channel: Redis channel to publish tick messages to
            interval: Target time between ticks in seconds

        Returns:
            None
        """
        tick_count = 0
        last: float | None = None
        last_sleep = interval
        while True:
            await self.r.publish(
                channel, Message[JsonObj](data=JsonObj(object={})).model_dump_json()
            )
            tick_count += 1
            now = time.time()
            if last is not None:
                last_sleep = last_sleep - (now - last - interval)
            await asyncio.sleep(last_sleep)
            last = now

    async def event_loop(self) -> None:
        end_channel = f"{self.env_uuid}/end"
        tick_channel = f"{self.env_uuid}/tick"

        async def listen_for_end():
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    if message["channel"].decode("utf-8") == end_channel:
                        raise asyncio.CancelledError

        async def tick_loop():
            await self.tick_at_given_interval(tick_channel, self.tick_interval)

        await asyncio.gather(listen_for_end(), tick_loop())

    async def __aenter__(self) -> Self:
        return await super().__aenter__()

    async def event_handler(
        self, _: str, __: Message[JsonObj]
    ) -> AsyncIterator[tuple[str, Message[JsonObj]]]:
        raise NotImplementedError("TickNode does not have an event handler.")
        yield "", Message[JsonObj](data=JsonObj(object={}))
