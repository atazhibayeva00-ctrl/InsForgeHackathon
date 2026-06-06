"""
Base node implementation for asynchronous communication in Collaborative Gym.

This module extends https://github.com/ProKil/aact/blob/main/src/aact/nodes/base.py
"""

import os
import sys
import time
from abc import abstractmethod
from asyncio import CancelledError
from typing import Any, AsyncIterator, Generic, Type, TypeVar

from aact.messages import Message
from aact.messages.base import DataModel
from pydantic import BaseModel, ConfigDict
from redis.asyncio import Redis

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

InputType = TypeVar("InputType", covariant=True, bound=DataModel)
OutputType = TypeVar("OutputType", covariant=True, bound=DataModel)

LAST_ACTIVE_TIME_KEY = "pid_to_last_active_time"


class NodeExitSignal(CancelledError):
    """Signal for graceful node termination."""


class BaseNode(BaseModel, Generic[InputType, OutputType]):
    """Redis pub/sub node base class."""

    input_channel_types: dict[str, Type[InputType]]
    output_channel_types: dict[str, Type[OutputType]]
    redis_url: str
    model_config = ConfigDict(extra="allow")

    def __init__(
        self,
        input_channel_types: list[tuple[str, Type[InputType]]],
        output_channel_types: list[tuple[str, Type[OutputType]]],
        redis_url: str = "redis://localhost:6379/0",
    ):
        super().__init__(
            input_channel_types=dict(input_channel_types),
            output_channel_types=dict(output_channel_types),
            redis_url=redis_url,
        )
        self.r: Redis = Redis.from_url(redis_url, socket_timeout=300)
        self.pubsub = self.r.pubsub()
        self.pid = os.getpid()

    async def update_last_active_time(self):
        await self.r.hset(LAST_ACTIVE_TIME_KEY, str(self.pid), str(time.time()))

    async def delete_process_record(self):
        await self.r.hdel(LAST_ACTIVE_TIME_KEY, str(self.pid))

    async def __aenter__(self) -> Self:
        try:
            await self.r.ping()
        except ConnectionError as exc:
            raise ValueError(
                f"Could not connect to Redis with the provided url. {self.redis_url}"
            ) from exc
        await self.pubsub.subscribe(*self.input_channel_types.keys())
        await self.update_last_active_time()
        return self

    async def __aexit__(self, _: Any, __: Any, ___: Any) -> None:
        await self.delete_process_record()
        await self.pubsub.unsubscribe()
        await self.r.aclose()

    async def _wait_for_input(
        self,
    ) -> AsyncIterator[tuple[str, Message[InputType]]]:
        async for message in self.pubsub.listen():
            channel = message["channel"].decode("utf-8")
            if message["type"] == "message" and channel in self.input_channel_types:
                data = Message[self.input_channel_types[channel]].model_validate_json(  # type: ignore
                    message["data"]
                )
                yield channel, data
        raise Exception("Input channel closed unexpectedly")

    async def event_loop(self) -> None:
        try:
            async for input_channel, input_message in self._wait_for_input():
                async for output_channel, output_message in self.event_handler(
                    input_channel, input_message
                ):
                    await self.r.publish(
                        output_channel, output_message.model_dump_json()
                    )
        except NodeExitSignal as e:
            logger_msg = getattr(self, "logger", None)
            if logger_msg:
                logger_msg.info(f"Event loop cancelled: {e}. Exiting gracefully.")
        except Exception as e:
            raise e

    @abstractmethod
    async def event_handler(
        self, _: str, __: Message[InputType]
    ) -> AsyncIterator[tuple[str, Message[OutputType]]]:
        raise NotImplementedError("event_handler must be implemented in a subclass.")
        yield "", self.output_type()  # type: ignore[misc]
