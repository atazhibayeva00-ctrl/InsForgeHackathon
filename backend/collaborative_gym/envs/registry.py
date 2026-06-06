"""Environment registry/factory.

Vendored from collaborative_gym/envs/registry.py. Environments register
themselves with ``@EnvFactory.register("id")`` and are instantiated with
``EnvFactory.make("id", team_members=..., env_id=...)``.
"""

from __future__ import annotations

import logging
from typing import Callable, List

from collaborative_gym.core import CoEnv

logger = logging.getLogger(__name__)


class EnvFactory:
    registry: dict[str, type[CoEnv]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[type[CoEnv]], type[CoEnv]]:
        def inner_wrapper(wrapped_class: type[CoEnv]) -> type[CoEnv]:
            if name in cls.registry:
                logger.warning("Environment %s already exists. Will replace it", name)
            cls.registry[name] = wrapped_class
            return wrapped_class

        return inner_wrapper

    @classmethod
    def make(cls, name: str, team_members: List[str], env_id: str, **kwargs) -> CoEnv:
        if name not in cls.registry:
            raise ValueError(f"Environment {name} not found in registry")
        return cls.registry[name](team_members=team_members, env_id=env_id, **kwargs)
