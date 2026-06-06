"""Co-Gym task environments.

Importing this package registers all environments with the ``EnvFactory``.
"""

from collaborative_gym.envs.config import EnvArgs, EnvConfig
from collaborative_gym.envs.investment import CoInvestmentEnv
from collaborative_gym.envs.registry import EnvFactory

__all__ = ["CoInvestmentEnv", "EnvFactory", "EnvConfig", "EnvArgs"]
