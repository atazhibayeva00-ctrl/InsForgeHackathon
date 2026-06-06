import json

import toml
import typer
from aact.cli.launch.launch import _sync_run_node
from aact.cli.reader import NodeConfig
from aact.cli.reader.dataflow_reader import NodeArgs

from collaborative_gym.envs import EnvConfig
import collaborative_gym.nodes.task_env  # noqa: F401 — register task_env with aact

app = typer.Typer()


@app.command()
def start_env_node(
    node_name: str = typer.Option(),
    env_config_toml: str = typer.Option(),
    env_uuid: str = typer.Option(),
    team_members: str = typer.Option(),  # List of team members dumped as a string
    disable_collaboration: bool = typer.Option(False),
    max_steps: int = typer.Option(),
    tick_interval: float = typer.Option(),
    max_tick_cnt: int = typer.Option(),
    result_dir: str = typer.Option(),
    redis_url: str = typer.Option(),
) -> None:
    env_config = toml.load(env_config_toml)
    print("Starting env node with config")
    env_config = EnvConfig(**env_config)
    _sync_run_node(
        NodeConfig(
            node_name=node_name,
            node_class="task_env",
            node_args=NodeArgs(
                env_config=env_config,
                env_uuid=env_uuid,
                team_members=json.loads(team_members),
                disable_collaboration=disable_collaboration,
                max_steps=max_steps,
                tick_interval=tick_interval,
                max_tick_cnt=max_tick_cnt,
                result_dir=result_dir,
            ),
        ),
        redis_url,
    )


@app.command()
def start_cmd_user_node(
    node_name: str = typer.Option(),
    env_uuid: str = typer.Option(),
    redis_url: str = typer.Option(),
) -> None:
    _sync_run_node(
        NodeConfig(
            node_name=node_name,
            node_class="cmd_user",
            node_args=NodeArgs(env_uuid=env_uuid, node_name=node_name),
        ),
        redis_url,
    )


@app.command()
def start_simulated_user_node(
    node_name: str = typer.Option(),
    env_uuid: str = typer.Option(),
    randomize_persona: bool = typer.Option(False),
    proactive_feedback: bool = typer.Option(False),
    proactive_action: bool = typer.Option(False),
    redis_url: str = typer.Option(),
) -> None:
    _sync_run_node(
        NodeConfig(
            node_name=node_name,
            node_class="simulated_user",
            node_args=NodeArgs(
                env_uuid=env_uuid,
                node_name=node_name,
                randomize_persona=randomize_persona,
                proactive_feedback=proactive_feedback,
                proactive_action=proactive_action,
            ),
        ),
        redis_url,
    )


@app.command()
def start_env_tick_node(
    env_node_name: str = typer.Option(),
    env_uuid: str = typer.Option(),
    redis_url: str = typer.Option(),
) -> None:
    _sync_run_node(
        NodeConfig(
            node_name=env_node_name + "_tick",
            node_class="env_tick",
            node_args=NodeArgs(
                env_uuid=env_uuid,
            ),
        ),
        redis_url,
    )


if __name__ == "__main__":
    app()
