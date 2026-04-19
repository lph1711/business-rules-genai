from __future__ import annotations

import re


def fn_name_to_pretty_label(name: str) -> str:
    """Convert snake_case or camelCase names into human readable labels."""
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    spaced = re.sub(r"[_\-\s]+", " ", spaced).strip()
    words = spaced.split()
    return " ".join(word if word.isupper() else word.capitalize() for word in words)


__all__ = ["fn_name_to_pretty_label"]
