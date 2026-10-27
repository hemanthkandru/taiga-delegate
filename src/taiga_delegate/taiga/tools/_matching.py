"""Shared name→id matching for Taiga attribute collections.

Taiga returns attribute collections (statuses, priorities, roles, ...) as
either dicts or objects depending on the endpoint; this is the one place that
knows how to read both.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def attribute_name(item: Any) -> str:
    if isinstance(item, dict):
        return item.get("name") or ""
    return getattr(item, "name", "") or ""


def attribute_id(item: Any) -> int | None:
    if isinstance(item, dict):
        return item.get("id")
    return getattr(item, "id", None)


def match_id(candidates: Iterable[Any], name: str) -> int | None:
    """Case-insensitive name match over a Taiga attribute collection."""
    wanted = (name or "").lower()
    for item in candidates or []:
        if attribute_name(item).lower() == wanted:
            return attribute_id(item)
    return None
