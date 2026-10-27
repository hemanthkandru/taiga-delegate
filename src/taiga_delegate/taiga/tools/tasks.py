"""Task tools: create (tasks are read through their parent story)."""

from __future__ import annotations

from typing import Any

from taiga_delegate.taiga.client import TaigaClient
from taiga_delegate.taiga.tools._matching import attribute_id

DEFINITIONS = [
    {
        "name": "taiga_create_task",
        "description": "Create a task, optionally linked to a user story or sprint.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "user_story_id": {"type": "integer"},
                "sprint_id": {"type": "integer"},
                "assigned_to": {"type": "string"},
            },
            "required": ["project_id", "subject"],
        },
    },
]


def create_task(client: TaigaClient, args: dict) -> Any:
    project = client.api.projects.get(args["project_id"])
    kw: dict[str, Any] = {"description": args.get("description", "")}
    if args.get("user_story_id"):
        kw["user_story"] = args["user_story_id"]
    if args.get("sprint_id"):
        kw["milestone"] = args["sprint_id"]
    if args.get("assigned_to"):
        uid = client.resolve_user_id(project, args["assigned_to"])
        if uid:
            kw["assigned_to"] = uid
    task = project.add_task(args["subject"], attribute_id(project.task_statuses[0]), **kw)
    return {"created": True, "id": task.id, "ref": getattr(task, "ref", None)}


HANDLERS = {
    "taiga_create_task": create_task,
}
