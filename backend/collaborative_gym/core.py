"""Core Co-Gym API: the ``CoEnv`` base class and collaborative-act primitives.

Vendored (with light trimming) from collaborative_gym/core.py. The key contract
is ``step(role, action) -> (obs, reward, terminated, private, info)`` where
``private`` decides whether a change is broadcast to all team members or only
the action taker.
"""

from __future__ import annotations

import logging
import re
from enum import Enum
from typing import Any, Dict, Optional, SupportsFloat, Tuple

from pydantic import BaseModel

from collaborative_gym.spaces import (
    MAX_UNICODE_LENGTH,
    MultiSpace,
    UnicodeWithRegexPattern,
)

logging.basicConfig(
    level=logging.INFO, format="%(name)s : %(levelname)-8s : %(message)s"
)
logger = logging.getLogger(__name__)

ActType = str
ObsType = Dict[str, Any]


class ObservationTypes(Enum):
    """How each observation field should be rendered by a GUI."""

    NO_RENDER = "NoRender"
    TEXT_EDITOR = "TextEditor"
    PORTFOLIO_TABLE = "PortfolioTable"
    ALLOCATION_CHART = "AllocationChart"
    PLAN_PANEL = "PlanPanel"

    def __str__(self):
        return self.value

    def __eq__(self, other):
        if isinstance(other, ObservationTypes):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False

    def __hash__(self):
        return hash(self.value)


class CoEnv:
    """Base environment class for human-agent collaboration tasks.

    Subclasses define a ``task_description``, an ``action_space`` (changes that
    affect the shared workspace) and a ``private_action_space`` (changes only the
    acting member sees), then implement ``step`` and ``get_obs``.
    """

    task_description: str
    team_members: list[str]
    action_space: MultiSpace
    private_action_space: MultiSpace
    additional_task_info: dict[str, Any] = {}
    example_question: str = ""
    example_trajectory: list[Tuple[str, ActType, ObsType]] = []
    env_id: str

    def __init__(self, team_members: list[str], env_id: str):
        self.team_members = team_members
        self.env_id = env_id

    def step(
        self, role: str, action: ActType
    ) -> tuple[ObsType, SupportsFloat, bool, bool, dict[str, Any]]:
        """Run one timestep of the environment's dynamics.

        Returns ``(observation, reward, terminated, private, info)``.
        """
        raise NotImplementedError

    def handle_action_error(
        self, error_msg: str, private: bool = True
    ) -> tuple[ObsType, SupportsFloat, bool, bool, dict[str, Any]]:
        """Return a consistent error tuple from ``step``."""
        logger.error(error_msg)
        return self.get_obs(), -1, False, private, {"action_error": error_msg}

    def parse_and_validate_action(
        self, role: str, action: ActType
    ) -> tuple[dict[str, Any], bool, Optional[str], Optional[str]]:
        """Parse/validate an action string against the (private) action spaces.

        Returns ``(parsed_action, private, action_id, error_message)``.
        """
        if role not in self.team_members:
            return {}, True, None, f"{role!r} is not a valid team member."

        private = False
        sanitized = action.strip()
        if self.private_action_space.contains(sanitized):
            private = True
        elif not self.action_space.contains(sanitized):
            # Defensive sanitation: pull the first ALL_CAPS(...) call out of any
            # surrounding prose the LM may have added.
            try:
                candidate = sanitized
                m = re.search(r"[A-Z][A-Z_]+\(", candidate)
                if m:
                    start = m.start()
                    end = candidate.rfind(")")
                    candidate = (
                        candidate[start : end + 1]
                        if end != -1 and end > start
                        else candidate[start:]
                    )
                    t_idx = candidate.find("\nThought:")
                    if t_idx != -1:
                        candidate = candidate[:t_idx].strip()
                    candidate = candidate.replace("\\(", "(").replace("\\)", ")")

                if self.private_action_space.contains(candidate):
                    private = True
                    sanitized = candidate
                elif self.action_space.contains(candidate):
                    sanitized = candidate
                else:
                    return (
                        {},
                        True,
                        None,
                        f"{action!r} invalid. Please strictly follow the action space specifications.",
                    )
            except Exception:
                return (
                    {},
                    True,
                    None,
                    f"{action!r} invalid. Please strictly follow the action space specifications.",
                )

        action_space = self.private_action_space if private else self.action_space
        for space in action_space:
            parsed_action = space.parse(sanitized)
            if parsed_action is not None:
                return parsed_action, private, space.machine_readable_identifier, None

        return {}, True, None, f"Failed to parse parameters from {action!r}"

    def reset(
        self, options: dict[str, Any] | None = None
    ) -> tuple[ObsType, dict[str, Any]]:
        raise NotImplementedError

    def close(self):
        pass

    def get_obs(self) -> ObsType:
        raise NotImplementedError

    def obs_type(self) -> Dict[str, ObservationTypes]:
        raise NotImplementedError

    def evaluate_task_performance(self) -> Dict:
        pass

    def dump_action_space(self):
        """Serialize all actions so an agent can learn the available action space."""
        return [action.dump_json() for action in self.action_space] + [
            action.dump_json() for action in self.private_action_space
        ]

    def action_space_to_description(self) -> str:
        """Render the action space as a human/LM-readable description."""
        lines = []
        for action in list(self.action_space) + list(self.private_action_space):
            info = action.dump_json()
            lines.append(
                f"- {info['human_readable_name']}\n"
                f"  pattern: {info['pattern']}\n"
                f"  params: {info['params']}"
            )
        return "\n".join(lines)

    def __str__(self):
        return f"<{type(self).__name__} instance>"

    def __enter__(self):
        return self

    def __exit__(self, *args: Any):
        self.close()
        return False


class TeamMemberConfig(BaseModel):
    """Configuration for a team member (human or agent) in a session."""

    name: str
    type: str
    start_node_base_command: str = ""


# ---------------------------------------------------------------------------
# Collaborative-act primitives (shared across all environments).
#
# These are the team-coordination actions from the Co-Gym paper. In the full
# framework they are injected by the node layer; here they are exposed so the
# environment/agent can reference the same vocabulary.
# ---------------------------------------------------------------------------


class SendTeammateMessage(UnicodeWithRegexPattern):
    def __init__(self):
        super().__init__(
            min_length=0,
            max_length=MAX_UNICODE_LENGTH,
            regex_pattern=re.compile(
                r"^SEND_TEAMMATE_MESSAGE\(message=(.*)\)$", re.DOTALL
            ),
            params=["message"],
            machine_readable_identifier="SEND_TEAMMATE_MESSAGE",
            human_readable_name="Send a message to your teammate(s).",
            human_readable_description="Send a message to your teammate(s) to provide information, ask for "
            "feedback, allocate task, etc. This action is useful for collaboration.",
        )


class WaitTeammateContinue(UnicodeWithRegexPattern):
    def __init__(self):
        super().__init__(
            min_length=0,
            max_length=MAX_UNICODE_LENGTH,
            regex_pattern=re.compile(r"^WAIT_TEAMMATE_CONTINUE\(\)$", re.DOTALL),
            params=[],
            machine_readable_identifier="WAIT_TEAMMATE_CONTINUE",
            human_readable_name="Wait for your teammate(s) to continue.",
            human_readable_description="Skip your turn and wait for your teammate(s) to continue.",
        )


class RequestTeammateConfirm(UnicodeWithRegexPattern):
    def __init__(self):
        super().__init__(
            min_length=0,
            max_length=MAX_UNICODE_LENGTH,
            regex_pattern=re.compile(
                r"^REQUEST_TEAMMATE_CONFIRM\(request_id=(.*), pending_action=(.*)\)$",
                re.DOTALL,
            ),
            params=["request_id", "pending_action"],
            machine_readable_identifier="REQUEST_TEAMMATE_CONFIRM",
            human_readable_name="Request confirmation from your teammate(s).",
            human_readable_description="For the pending action, request confirmation from your teammate(s) "
            "before executing the action.",
        )


class AcceptConfirmation(UnicodeWithRegexPattern):
    def __init__(self):
        super().__init__(
            min_length=0,
            max_length=MAX_UNICODE_LENGTH,
            regex_pattern=re.compile(
                r"^ACCEPT_CONFIRMATION\(request_id=(.*)\)$", re.DOTALL
            ),
            params=["request_id"],
            machine_readable_identifier="ACCEPT_CONFIRMATION",
            human_readable_name="Accept the confirmation request from your teammate(s).",
            human_readable_description="Accept the confirmation request for the pending action.",
        )


class RejectConfirmation(UnicodeWithRegexPattern):
    def __init__(self):
        super().__init__(
            min_length=0,
            max_length=MAX_UNICODE_LENGTH,
            regex_pattern=re.compile(
                r"^REJECT_CONFIRMATION\(request_id=(.*)\)$", re.DOTALL
            ),
            params=["request_id"],
            machine_readable_identifier="REJECT_CONFIRMATION",
            human_readable_name="Reject the confirmation request from your teammate(s).",
            human_readable_description="Reject the confirmation request for the pending action.",
        )


class PutAgentAsleep(UnicodeWithRegexPattern):
    def __init__(self):
        super().__init__(
            min_length=0,
            max_length=MAX_UNICODE_LENGTH,
            regex_pattern=re.compile(r"^PUT_AGENT_ASLEEP\(\)$", re.DOTALL),
            params=[],
            machine_readable_identifier="PUT_AGENT_ASLEEP",
            human_readable_name="Put the agent to sleep.",
            human_readable_description="Put the agent to sleep until it is woken up.",
        )


class WakeAgentUp(UnicodeWithRegexPattern):
    def __init__(self):
        super().__init__(
            min_length=0,
            max_length=MAX_UNICODE_LENGTH,
            regex_pattern=re.compile(r"^WAKE_AGENT_UP\(\)$", re.DOTALL),
            params=[],
            machine_readable_identifier="WAKE_AGENT_UP",
            human_readable_name="Wake the agent up.",
            human_readable_description="Wake the agent so it receives notifications again.",
        )
