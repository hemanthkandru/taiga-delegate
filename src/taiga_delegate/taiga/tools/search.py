"""Search and ref resolution."""

from __future__ import annotations

from typing import Any

from taiga_delegate.taiga.client import TaigaClient

DEFINITIONS = [
    {
        "name": "taiga_search",
        "description": "Search across stories, tasks, issues, wiki in a project.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "query": {"type": "string"},
            },
            "required": ["project_id", "query"],
        },
    },
    {
        "name": "taiga_resolve_ref",
        "description": "Convert a display reference number (e.g. #12 shown in the UI) to the internal ID. ALWAYS use this before commenting on or updating a story/task/issue by its # number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "ref": {"type": "integer", "description": "The # reference number shown in Taiga UI"},
                "object_type": {"type": "string", "enum": ["userstory", "task", "issue", "epic"], "description": "Type of object"},
            },
            "required": ["project_id", "ref", "object_type"],
        },
    },
]


def search(client: TaigaClient, args: dict) -> Any:
    result = client.api.search(args["project_id"], args["query"])
    return {
        "user_stories": [str(s) for s in (result.user_stories or [])],
        "tasks": [str(t) for t in (result.tasks or [])],
        "issues": [str(i) for i in (result.issues or [])],
    }


def resolve_ref(client: TaigaClient, args: dict) -> Any:
    api = client.api
    resources = {
        "userstory": api.user_stories,
        "task": api.tasks,
        "issue": api.issues,
        "epic": api.epics,
    }
    try:
        resource = resources[args["object_type"]]
    except KeyError:
        return {"error": f"Invalid type: {args['object_type']}"}
    for item in resource.list(project=args["project_id"]):
        if getattr(item, "ref", None) == args["ref"]:
            return {
                "ref": args["ref"],
                "internal_id": item.id,
                "subject": getattr(item, "subject", None),
                "object_type": args["object_type"],
            }
    return {"error": f"No {args['object_type']} with ref #{args['ref']} found in project {args['project_id']}"}


HANDLERS = {
    "taiga_search": search,
    "taiga_resolve_ref": resolve_ref,
}
