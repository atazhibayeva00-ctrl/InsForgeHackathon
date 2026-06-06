"""Action/observation spaces for Co-Gym environments.

Vendored (with light trimming) from collaborative_gym/spaces.py in
SALT-NLP/collaborative-gym. ``UnicodeWithRegexPattern`` is the workhorse used
to declare LM-generatable string actions, and ``MultiSpace`` lets an
environment accept any one of several such actions.
"""

from __future__ import annotations

import re
import typing
from typing import Any, Dict, List, Optional

import numpy as np
import rstr
from gymnasium.spaces import Space, Text
from numpy.typing import NDArray

from collaborative_gym.utils.string import reconstruct_string_from_regex_pattern

MAX_UNICODE_CODEPOINT = 0x10FFFF
MAX_UNICODE_LENGTH = 2**32 - 1


class MultiSpace(Space[Any]):
    """A Space that accepts multiple sub-spaces.

    A sample is considered valid if it is valid in at least one of the
    sub-spaces. Used to express "the action must match one of these patterns".
    """

    def __init__(
        self,
        spaces: typing.Iterable[Space[Any]],
        seed: int | typing.Sequence[int] | np.random.Generator | None = None,
    ):
        assert isinstance(spaces, typing.Iterable), f"{spaces} is not an iterable"
        self.spaces = tuple(spaces)
        for space in self.spaces:
            assert isinstance(
                space, Space
            ), f"{space} does not inherit from `gymnasium.Space`. Actual Type: {type(space)}"
        super().__init__(None, None, seed)

    @property
    def is_np_flattenable(self):
        return all(space.is_np_flattenable for space in self.spaces)

    def sample(self, mask: tuple[Any | None, ...] | None = None) -> tuple[int, Any]:
        chosen_space = int(np.random.choice(len(self.spaces)))
        subspace = self.spaces[chosen_space]
        if mask is not None:
            assert isinstance(mask, tuple)
            assert len(mask) == len(self.spaces)
            mask = mask[chosen_space]
        return chosen_space, subspace.sample(mask=mask)

    def contains(self, x: Any) -> bool:
        return any(space.contains(x) for space in self.spaces)

    def __repr__(self) -> str:
        return "MultiSpace(" + ", ".join([str(s) for s in self.spaces]) + ")"

    def __getitem__(self, index: int) -> Space[Any]:
        return self.spaces[index]

    def __len__(self) -> int:
        return len(self.spaces)

    def __iter__(self):
        return iter(self.spaces)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, MultiSpace) and self.spaces == other.spaces


class Unicode(Text):
    """A space representing an arbitrary unicode string of bounded length."""

    def contains(self, x: Any) -> bool:
        return isinstance(x, str) and self.min_length <= len(x) <= self.max_length

    def __repr__(self) -> str:
        return f"Unicode({self.min_length}, {self.max_length})"

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, Unicode)
            and self.min_length == other.min_length
            and self.max_length == other.max_length
        )


class UnicodeWithRegexPattern(Text):
    """A unicode-string action that must satisfy a regex pattern.

    This is how actions are declared so language models can both read the
    expected format (``pattern`` / ``params``) and emit a matching string.
    """

    def __init__(
        self,
        max_length: int,
        regex_pattern: re.Pattern,
        params: List[str],
        machine_readable_identifier: Any,
        *,
        min_length: int = 1,
        human_readable_name: Optional[str] = None,
        human_readable_description: Optional[str] = None,
    ):
        super().__init__(max_length=max_length, min_length=min_length)
        self.pattern = regex_pattern
        self.params = params
        self.machine_readable_identifier = machine_readable_identifier
        self.human_readable_name = human_readable_name
        self.human_readable_description = human_readable_description

    def contains(self, x: Any) -> bool:
        if not isinstance(x, str) or not self.min_length <= len(x) <= self.max_length:
            return False
        return self.pattern.fullmatch(x) is not None

    def __repr__(self) -> str:
        return (
            f"UnicodeWithRegexPattern({self.min_length}, {self.max_length}, "
            f"regex_pattern={self.pattern.pattern}, "
            f"human_readable_name={self.human_readable_name})"
        )

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, UnicodeWithRegexPattern)
            and self.min_length == other.min_length
            and self.max_length == other.max_length
            and self.pattern.pattern == other.pattern.pattern
        )

    def sample(
        self,
        mask: None | (tuple[int | None, NDArray[np.int8] | None]) = None,
    ) -> str:
        return rstr.xeger(self.pattern)

    def parse(self, x: Any) -> Dict[str, str] | None:
        """Parse a matching action string into its named parameters."""
        match = self.pattern.fullmatch(x)
        if match:
            return {param: val for param, val in zip(self.params, match.groups())}
        return None

    def construct_action_string_from_params(self, **kwargs):
        """Build a valid action string from named parameters."""
        try:
            param_values = [kwargs[param] for param in self.params]
        except KeyError as e:
            raise ValueError(f"Missing parameter: {e}")
        return reconstruct_string_from_regex_pattern(self.pattern, param_values)

    def dump_json(self):
        """Serialize the space so an agent can learn the action format."""
        return {
            "max_length": self.max_length,
            "pattern": self.pattern.pattern,
            "params": self.params,
            "machine_readable_identifier": str(self.machine_readable_identifier),
            "min_length": self.min_length,
            "human_readable_name": self.human_readable_name,
            "human_readable_description": self.human_readable_description,
        }

    @classmethod
    def from_json(cls, json_obj: dict):
        return cls(
            max_length=json_obj["max_length"],
            regex_pattern=re.compile(json_obj["pattern"]),
            params=json_obj["params"],
            machine_readable_identifier=json_obj["machine_readable_identifier"],
            min_length=json_obj["min_length"],
            human_readable_name=json_obj["human_readable_name"],
            human_readable_description=json_obj["human_readable_description"],
        )
