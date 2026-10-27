"""Commenting on stories, tasks, issues, and epics."""

from __future__ import annotations

from typing import Any

from taiga_delegate.taiga.client import TaigaClient

# Tool object_type -> Taiga REST endpoint. Epics are commentable too — easy to
# miss because python-taiga's own comment helpers don't cover them.
_ENDPOINTS = {
    "userstory": "userstories",
    "task": "tasks",
    "issue": "issues",
    "epic": "epics",
}

DEFINITIONS = [
    {
        "name": "taiga_add_comment",
        "description": "Add a comment to a userstory, task, issue, or epic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "object_type": {"type": "string", "enum": ["userstory", "task", "issue", "epic"]},
                "object_id": {"type": "integer"},
                "comment": {"type": "string"},
            },
            "required": ["object_type", "object_id", "comment"],
        },
    },
]


def add_comment(client: TaigaClient, args: dict) -> Any:
    try:
        endpoint = _ENDPOINTS[args["object_type"]]
    except KeyError:
        return {"error": f"Invalid object_type: {args['object_type']}"}
    client.patch_object(endpoint, args["object_id"], {"comment": args["comment"]})
    return {"commented": True, "object_type": args["object_type"], "object_id": args["object_id"]}


HANDLERS = {
    "taiga_add_comment": add_comment,
}
