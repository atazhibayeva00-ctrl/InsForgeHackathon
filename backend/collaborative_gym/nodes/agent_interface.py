import asyncio
from typing import AsyncIterator, Self

from aact import Message, NodeFactory

from collaborative_gym.core import logger
from collaborative_gym.nodes.base_node import BaseNode
from collaborative_gym.nodes.commons import JsonObj

AGENT_TO_PID_KEY = "agent_to_pid"


@NodeFactory.register("agent")
class AgentNode(BaseNode[JsonObj, JsonObj]):
    """Wraps a collaborative agent; listens on Redis and publishes actions."""

    def __init__(
        self,
        env_uuid: str,
        node_name: str,
        agent,
        wait_time: int = 20,
        redis_url: str = "redis://localhost:6379/0",
    ):
        super().__init__(
            input_channel_types=[
                (f"{env_uuid}/{node_name}/observation", JsonObj),
                (f"{env_uuid}/start", JsonObj),
                (f"{env_uuid}/end", JsonObj),
            ],
            output_channel_types=[(f"{env_uuid}/step", JsonObj)],
            redis_url=redis_url,
        )
        self.env_uuid = env_uuid
        self.node_name = node_name
        self.wait_time = wait_time
        self.agent = agent
        self.tasks = []
        self.is_processing_observation = False
        self.is_processing_observation_lock = asyncio.Lock()
        self.pending_observation: tuple[str, Message[JsonObj]] | None = None

    async def __aenter__(self) -> Self:
        await super().__aenter__()
        await self.r.hset(
            AGENT_TO_PID_KEY, f"{self.env_uuid}_{self.node_name}", self.pid
        )
        return self

    async def delete_process_record(self):
        await super().delete_process_record()
        await self.r.hdel(AGENT_TO_PID_KEY, f"{self.env_uuid}_{self.node_name}")

    async def event_loop(self) -> None:
        self.tasks = []
        async for input_channel, input_message in self._wait_for_input():
            if input_channel == f"{self.env_uuid}/{self.node_name}/observation":
                async with self.is_processing_observation_lock:
                    if self.is_processing_observation:
                        self.pending_observation = (input_channel, input_message)
                        continue
                    self.is_processing_observation = True
                task = asyncio.create_task(
                    self.handle_observation(input_channel, input_message)
                )
                self.tasks.append(task)
            else:
                await self.handle_event(input_channel, input_message)
        await asyncio.gather(*self.tasks)

    async def handle_event(self, input_channel: str, input_message: Message[JsonObj]):
        async for output_channel, output_message in self.event_handler(
            input_channel, input_message
        ):
            await self.r.publish(output_channel, output_message.model_dump_json())

    async def handle_observation(
        self, input_channel: str, input_message: Message[JsonObj]
    ) -> None:
        current: tuple[str, Message[JsonObj]] | None = (input_channel, input_message)
        while current is not None:
            channel, message = current
            await self.handle_event(channel, message)
            async with self.is_processing_observation_lock:
                current = self.pending_observation
                self.pending_observation = None
                if current is None:
                    self.is_processing_observation = False

    async def event_handler(
        self, input_channel: str, input_message: Message[JsonObj]
    ) -> AsyncIterator[tuple[str, Message[JsonObj]]]:
        if input_channel == f"{self.env_uuid}/start":
            logger.info("AgentNode (%s): received start message", self.node_name)
            self.agent.start(
                name=self.node_name,
                team_members=input_message.data.object["team_members"],
                task_description=input_message.data.object["task_description"],
                action_space=input_message.data.object["action_space"],
                example_question=input_message.data.object["example_question"],
                example_trajectory=input_message.data.object["example_trajectory"],
            )
        elif input_channel == f"{self.env_uuid}/{self.node_name}/observation":
            logger.info("AgentNode (%s): received observation message", self.node_name)
            observation = input_message.data.object["observation"]
            chat_history = input_message.data.object["chat_history"]
            # LLM planning can take tens of seconds; run off the event loop so
            # the Redis pub/sub connection does not time out.
            action = await asyncio.to_thread(
                self.agent.get_action,
                observation=observation,
                chat_history=chat_history,
            )
            payload = {"action": action, "role": self.node_name}
            await asyncio.sleep(self.wait_time)
            await self.update_last_active_time()
            yield f"{self.env_uuid}/step", Message[JsonObj](data=JsonObj(object=payload))
        elif input_channel == f"{self.env_uuid}/end":
            logger.info("AgentNode (%s): received end message", self.node_name)
            self.agent.end(result_dir=input_message.data.object["result_dir"])
            for task in self.tasks:
                task.cancel()
            await self.delete_process_record()
            raise asyncio.CancelledError
