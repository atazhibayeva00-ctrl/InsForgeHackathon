import argparse
import atexit
import json
import logging
import os
import signal
import sys
import time
import uuid
from subprocess import Popen
from typing import List

import toml

from collaborative_gym.core import TeamMemberConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Runner:
    """
    Manages human-agent collaboration sessions.

    This class handles the lifecycle of human-agent collaboration sessions, including
    launching task environment and team members (agents, users, etc.), managing their
    processes, and ensuring proper cleanup on exit.
    It uses Redis for inter-process communication and maintains session state.

    Attributes:
        result_dir: Directory for storing session results
        redis_url: URL for Redis connection used by team members
        subprocesses: List of active subprocess handles
        sessions: List of active session UUIDs
    """

    def __init__(
        self,
        result_dir: str = "./workdir/results",
        redis_url: str = "redis://localhost:6379/0",
    ):
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)
        self.result_dir = result_dir
        self.redis_url = redis_url
        self.subprocesses: List[Popen[bytes]] = []
        self.sessions = []

    def check_session_exists(self, session_uuid: str) -> bool:
        """
        Check if a session with the given UUID exists.

        Args:
            session_uuid: Unique identifier for the session to check

        Returns:
            bool: True if the session exists, False otherwise
        """
        return session_uuid in self.sessions

    def launch_team_member(self, env_uuid: str, member: TeamMemberConfig):
        """
        Launch a team member process with the specified configuration.

        Creates and starts a subprocess for the team member, configuring it with
        the appropriate environment UUID and Redis connection. Handles different
        member types (cmd_user, simulated_user, agent, gui_user) appropriately.

        Args:
            env_uuid: Unique identifier for the environment
            member: Configuration for the team member to launch
        """
        if member.type == "cmd_user":
            start_member_command = (
                f"{member.start_node_base_command} "
                f"--node-name {member.name} --env-uuid {env_uuid} --redis-url {self.redis_url}"
            )
        elif member.type == "simulated_user":
            start_member_command = (
                f"{member.start_node_base_command} "
                f"--node-name {member.name} --env-uuid {env_uuid} --redis-url {self.redis_url}"
            )
        elif member.type == "agent":
            start_member_command = (
                f"{member.start_node_base_command} "
                f"--node-name {member.name} --env-uuid {env_uuid} "
                f"--redis-url {self.redis_url}"
            )
        elif member.type == "gui_user":
            return

        backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        agent_process = Popen(
            [start_member_command],
            shell=True,
            cwd=backend_root,
            preexec_fn=os.setsid,
        )
        self.subprocesses.append(agent_process)
        time.sleep(5)  # Wait for the node to start

    def start_session(
        self,
        session_uuid: str,
        env_config_path: str,
        members: List[TeamMemberConfig],
        max_steps: int,
        disable_collaboration: bool = False,
        add_tick: bool = False,
        tick_interval: float = 60,
        max_tick_cnt: int = 5,
    ):
        """
        Start a new human-agent collaboration session.

        Creates and launches all necessary processes for a collaborative session,
        including team members and the environment itself. Optionally adds a tick
        process for managing timeouts.

        Args:
            session_uuid: Unique identifier for the new session
            env_config_path: Path to the environment configuration file
            members: List of team member configurations
            max_steps: Maximum number of steps allowed in the session
            disable_collaboration: If True, only task actions are allowed
            add_tick: If True, adds a process to handle timeouts
            tick_interval: Time in seconds between tick checks
            max_tick_cnt: Maximum number of ticks before timeout
        """
        if session_uuid in self.sessions:
            print(f"Session {session_uuid} already started")
            return
        self.sessions.append(session_uuid)
        env_uuid = f"env_{session_uuid}"

        for member in members:
            self.launch_team_member(env_uuid, member)

        team_member_names = [member.name for member in members]

        python = sys.executable
        start_env_command = (
            f"{python} -m collaborative_gym.command start-env-node "
            f"--node-name task_env --env-config-toml {env_config_path} --env-uuid {env_uuid} "
            f"--team-members '{json.dumps(team_member_names)}' --max-steps {max_steps} "
            f"--tick-interval {tick_interval} --max-tick-cnt {max_tick_cnt} "
            f"--result-dir {self.result_dir} --redis-url {self.redis_url}"
        )
        print(start_env_command)
        if disable_collaboration:
            start_env_command += " --disable-collaboration"
        backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_process = Popen(
            [start_env_command],
            shell=True,
            cwd=backend_root,
            preexec_fn=os.setsid,
        )
        self.subprocesses.append(env_process)

        if add_tick:
            start_tick_command = (
                f"{sys.executable} -m collaborative_gym.command start-env-tick-node --env-node-name task_env "
                f"--env-uuid {env_uuid} --redis-url {self.redis_url}"
            )
            tick_process = Popen(
                [start_tick_command],
                shell=True,
                preexec_fn=os.setsid,  # Start the subprocess in a new process group
            )
            self.subprocesses.append(tick_process)

    def cleanup_subprocesses(self):
        """
        Terminate all managed subprocesses gracefully.

        Sends SIGTERM to each subprocess group and waits for them to exit.
        This ensures all child processes are properly cleaned up.
        """
        for proc in self.subprocesses:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait()
                print(f"Terminated process group {proc.pid}")
            except Exception as e:
                print(f"Failed to terminate {proc.pid}: {e}")

    def reset(self):
        """
        Reset the runner to its initial state.

        Terminates all running processes and clears session records.
        """
        self.cleanup_subprocesses()
        self.subprocesses = []
        self.sessions = []


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-config-path", type=str, required=True)
    parser.add_argument("--team-member-config-path", type=str, required=True)
    parser.add_argument(
        "--disable-collaboration",
        action="store_true",
        help="When set, the environment will only support task actions and not collaboration actions.",
    )
    parser.add_argument(
        "--add-tick",
        action="store_true",
        help="When set, the environment will send messages to remind the agents when there is no "
        "activity for too long.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=100,
        help="The maximum number of steps the environment",
    )
    parser.add_argument("--secret-path", type=str, default="secrets.toml")
    parser.add_argument("--redis-url", type=str, default="redis://localhost:6379/0")
    args = parser.parse_args()

    secrets = toml.load(args.secret_path)
    for k in secrets:
        os.environ[k] = secrets[k]

    runner = Runner()

    def handle_exit_signal(signum, frame):
        runner.cleanup_subprocesses()
        sys.exit(0)

    atexit.register(runner.cleanup_subprocesses)
    signal.signal(signal.SIGINT, handle_exit_signal)
    signal.signal(signal.SIGTERM, handle_exit_signal)

    team_member_config = toml.load(args.team_member_config_path)

    runner.start_session(
        session_uuid=str(uuid.uuid4()),
        env_config_path=args.env_config_path,
        members=[
            TeamMemberConfig(**member) for member in team_member_config["team_member"]
        ],
        max_steps=args.max_steps,
        disable_collaboration=args.disable_collaboration,
        add_tick=args.add_tick,
    )

    for node_process in runner.subprocesses:
        node_process.wait()
