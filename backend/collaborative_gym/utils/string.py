"""String helpers for parsing/reconstructing action strings.

Trimmed from collaborative_gym/utils/string.py (the terminal-coloring helpers
that depended on prompt_toolkit are intentionally dropped).
"""

from __future__ import annotations

import re
from typing import List


def post_process_parsed_function_arg(s: str) -> str:
    """Remove surrounding quotes/spaces from a parsed argument and unescape it."""
    s = s.strip().strip('"').strip("'").strip()
    s = (
        s.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace("\\'", "'")
        .replace('\\"', '"')
    )
    if r"\u" in s or r"\x" in s:
        # raw_unicode_escape helps interpret \uXXXX sequences in the original string
        try:
            s = s.encode("raw_unicode_escape").decode("unicode_escape")
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
    return s


def reconstruct_string_from_regex_pattern(
    pattern: re.Pattern, replacements: List[str]
) -> str:
    """Reconstruct a concrete action string from a pattern and ordered values."""
    trimmed_pattern = pattern.pattern.strip("^$")
    parts = re.split(r"(\(\.\*\))", trimmed_pattern)

    filled_parts = []
    replacement_index = 0
    for part in parts:
        if part == "(.*)":
            if replacement_index >= len(replacements):
                raise ValueError("Not enough replacement values provided.")
            filled_parts.append(str(replacements[replacement_index]))
            replacement_index += 1
        else:
            cleaned_part = re.sub(r"[^\w\s=\(\),]", "", part)
            filled_parts.append(cleaned_part)

    return "".join(filled_parts)
