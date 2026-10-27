"""Boundary serialization: Taiga wire objects -> compact, token-cheap JSON.

Two concerns live here, and only here:
  * turning python-taiga objects into plain dicts with stable field names
  * rendering those dicts as compact JSON (no whitespace, no empty fields)

The compactness is deliberate: tool results are read by LLMs, where every
byte is billed. Empty fields carry no information — drop them.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


def to_json(data: Any) -> str:
    """Render any tool result as compact JSON with empty fields stripped."""
    return json.dumps(strip_empty(serialize(data)), separators=(",", ":"), default=str)


def serialize(obj: Any) -> Any:
    """Recursively convert wire objects (python-taiga models, dates) to plain data."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return {k: serialize(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    return obj


def strip_empty(value: Any) -> Any:
    """Recursively drop None / empty-string / empty-list dict values.

    Keeps False and 0 — those carry information.
    """
    if isinstance(value, dict):
        return {
            k: strip_empty(v)
            for k, v in value.items()
            if v is not None and v != "" and v != []
        }
    if isinstance(value, list):
        return [strip_empty(v) for v in value]
    return value


def tag_names(raw_tags: Any) -> list[str]:
    """Taiga tags arrive as [name, color] pairs; only names matter here."""
    return [t[0] if isinstance(t, (list, tuple)) else t for t in (raw_tags or [])]


def _extra_name(obj: Any, attr: str, key: str = "name") -> str | None:
    """Read `key` out of one of Taiga's `*_extra_info` members, which may be a
    dict or an object depending on the endpoint."""
    extra = getattr(obj, attr, None)
    if extra is None:
        return None
    if isinstance(extra, dict):
        return extra.get(key)
    return getattr(extra, key, None)


def story_summary(story: Any) -> dict:
    epic = getattr(story, "epic_extra_info", None)
    epic_info = None
    if epic:
        epic_info = {
            "id": epic.get("id") if isinstance(epic, dict) else getattr(epic, "id", None),
            "subject": epic.get("subject") if isinstance(epic, dict) else getattr(epic, "subject", None),
        }
    return {
        "id": story.id,
        "ref": getattr(story, "ref", None),
        "subject": story.subject,
        "status": _extra_name(story, "status_extra_info"),
        "assigned_to": _extra_name(story, "assigned_to_extra_info", "username"),
        "points": getattr(story, "total_points", None),
        "tags": tag_names(getattr(story, "tags", None)),
        "milestone": getattr(story, "milestone", None),
        "epic": epic_info,
        "modified_date": str(getattr(story, "modified_date", "") or ""),
    }


def task_summary(task: Any) -> dict:
    return {
        "id": task.id,
        "ref": getattr(task, "ref", None),
        "subject": task.subject,
        "status": _extra_name(task, "status_extra_info"),
        "assigned_to": _extra_name(task, "assigned_to_extra_info", "username"),
    }


def epic_summary(epic: Any) -> dict:
    return {
        "id": epic.id,
        "ref": getattr(epic, "ref", None),
        "subject": epic.subject,
        "status": _extra_name(epic, "status_extra_info"),
        "assigned_to": _extra_name(epic, "assigned_to_extra_info", "username"),
        "color": getattr(epic, "color", None),
        "tags": tag_names(getattr(epic, "tags", None)),
        "project": getattr(epic, "project", None),
        "modified_date": str(getattr(epic, "modified_date", "") or ""),
    }


def issue_summary(issue: Any) -> dict:
    return {
        "id": issue.id,
        "ref": getattr(issue, "ref", None),
        "subject": issue.subject,
        "status": _extra_name(issue, "status_extra_info"),
        "priority": _extra_name(issue, "priority_extra_info"),
        "severity": _extra_name(issue, "severity_extra_info"),
        "assigned_to": _extra_name(issue, "assigned_to_extra_info", "username"),
        "tags": tag_names(getattr(issue, "tags", None)),
    }


def sprint_summary(sprint: Any) -> dict:
    return {
        "id": sprint.id,
        "name": sprint.name,
        "estimated_start": str(getattr(sprint, "estimated_start", "") or ""),
        "estimated_finish": str(getattr(sprint, "estimated_finish", "") or ""),
        "closed": getattr(sprint, "closed", False),
    }
