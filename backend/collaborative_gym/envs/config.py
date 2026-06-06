from pydantic import BaseModel, ConfigDict, Field


class EnvArgs(BaseModel):
    """Flexible container for environment-specific arguments."""

    model_config = ConfigDict(extra="allow")


class EnvConfig(BaseModel):
    """Which environment class to instantiate and its init arguments."""

    env_class: str
    env_args: EnvArgs = Field(default_factory=EnvArgs)
