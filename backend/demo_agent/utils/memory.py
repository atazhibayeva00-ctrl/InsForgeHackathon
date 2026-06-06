import logging
import re

from collaborative_gym.spaces import (
    MultiSpace,
    UnicodeWithRegexPattern,
    MAX_UNICODE_LENGTH,
)
from collaborative_gym.utils.string import post_process_parsed_function_arg

logging.basicConfig(
    level=logging.INFO, format="%(name)s : %(levelname)-8s : %(message)s"
)
logger = logging.getLogger(__name__)


class Scratchpad:
    """In-session memory for the agent to store notes using dict format.

    The Scratchpad can be updated using the following actions:
    - ADD_NOTE: Add a note to the scratchpad with the provided note_id and note.
    - DELETE_NOTE: Delete a note from the scratchpad with the provided note_id.
    - EDIT_NOTE: Edit a note in the scratchpad with the provided note_id.
    - DO_NOTHING: Choose this action if there is no need to update the scratchpad.
    """

    def __init__(self):
        self.notes = {}
        self.action_space = MultiSpace(
            (
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(
                        r"^ADD_NOTE\(note_id=(.*), note=(.*)\)$", re.DOTALL
                    ),
                    params=["note_id", "note"],
                    machine_readable_identifier="ADD_NOTE",
                    human_readable_name="Add a note to the scratchpad",
                    human_readable_description="Add a note to the scratchpad with the provided note_id and note.",
                ),
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(
                        r"^DELETE_NOTE\(note_id=(.*)\)$", re.DOTALL
                    ),
                    params=["note_id"],
                    machine_readable_identifier="DELETE_NOTE",
                    human_readable_name="Delete a note from the scratchpad",
                    human_readable_description="Delete a note from the scratchpad with the provided note_id.",
                ),
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(
                        r"^EDIT_NOTE\(note_id=(.*), note=(.*)\)$", re.DOTALL
                    ),
                    params=["note_id", "note"],
                    machine_readable_identifier="EDIT_NOTE",
                    human_readable_name="Edit a note in the scratchpad",
                    human_readable_description="Edit a note in the scratchpad with the provided note_id.",
                ),
                UnicodeWithRegexPattern(
                    min_length=0,
                    max_length=MAX_UNICODE_LENGTH,
                    regex_pattern=re.compile(r"^DO_NOTHING\(\)$", re.DOTALL),
                    params=[],
                    machine_readable_identifier="DO_NOTHING",
                    human_readable_name="Do nothing",
                    human_readable_description="Choose this action if there is no need to update the scratchpad. "
                    "Do not spam the scratchpad with unnecessary updates.",
                ),
            )
        )

    def add_note(self, note_id: str, note: str):
        self.notes[note_id] = note

    def delete_note(self, note_id: str):
        self.notes.pop(note_id, None)

    def edit_note(self, note_id: str, new_note: str):
        self.notes[note_id] = new_note

    def to_str(self):
        if len(self.notes) == 0:
            return "No notes in the scratchpad."
        s = "\n-----\n".join(
            [
                f"Note ID: {note_id}\nNote: {note}"
                for note_id, note in self.notes.items()
            ]
        )
        return s

    def get_action_space_description(self):
        action_space_description = []
        for space in self.action_space:
            action_desc_str = (
                f"{space.human_readable_name} (Parameters: {space.params})"
            )
            action_desc_str += f"\n- Description: {space.human_readable_description}"
            action_desc_str += (
                f"\n- Regex pattern for the action "
                f"(your output needs to follow this if you take this action): {space.pattern}"
            )
            action_space_description.append(action_desc_str)
        return "\n\n".join(action_space_description)

    def execute_action(self, action: str):
        # Hacky post-processing:
        # Assume the action is in a function call format and the function name starts with a capital letter.
        match = re.search(r"[A-Z]", action)
        if match:
            action = action[match.start() :]
        if action[-1] != ")":
            action = action[: action.rfind(")") + 1]
        action = action.replace("\(", "(").replace("\)", ")")
        if not self.action_space.contains(action):
            err_msg = f"Scratchpad: {action!r} invalid. Please strictly follow the action space specifications."
            logger.error(err_msg)
        parsed_action = None
        for subspace in self.action_space:
            parsed_action = subspace.parse(action)
            if parsed_action is not None:
                action = subspace.machine_readable_identifier
                for k in parsed_action:
                    parsed_action[k] = post_process_parsed_function_arg(
                        parsed_action[k]
                    )
                break
        if action == "ADD_NOTE":
            self.add_note(parsed_action["note_id"], parsed_action["note"])
        elif action == "DELETE_NOTE":
            self.delete_note(parsed_action["note_id"])
        elif action == "EDIT_NOTE":
            self.edit_note(parsed_action["note_id"], parsed_action["note"])
        elif action == "DO_NOTHING":
            pass
