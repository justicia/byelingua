from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


REPLACEMENT_CHARACTER = "\ufffd"


class UnicodeIntegrityError(ValueError):
    code = "UNICODE_REPLACEMENT_CHARACTER"

    def __init__(self, field: str, value: object):
        self.field = field
        self.value = str(value)
        super().__init__(f"{self.code}: replacement character in {field}")


def find_replacement_characters(value: Any, path: str = "root") -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if isinstance(value, str):
        if REPLACEMENT_CHARACTER in value:
            found.append({"field": path, "value": value})
    elif isinstance(value, Mapping):
        for key, child in value.items():
            found.extend(find_replacement_characters(child, f"{path}.{key}"))
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for index, child in enumerate(value):
            found.extend(find_replacement_characters(child, f"{path}[{index}]"))
    return found


def validate_unicode_integrity(value: Any, *, fields: Sequence[str] | None = None) -> None:
    found = find_replacement_characters(value)
    if fields is not None:
        found = [item for item in found if any(item["field"].endswith(field) for field in fields)]
    if found:
        raise UnicodeIntegrityError(found[0]["field"], found[0]["value"])


def replacement_character_count(value: Any) -> int:
    return sum(item["value"].count(REPLACEMENT_CHARACTER) for item in find_replacement_characters(value))
