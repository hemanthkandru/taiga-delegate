"""Sprint (milestone) tools: list, get, create."""

from __future__ import annotations

from typing import Any

from taiga_delegate.taiga.client import TaigaClient
from taiga_delegate.taiga.serialization import sprint_summary, story_summary

DEFINITIONS = [
    {
        "name": "taiga_list_sprints",
        "description": "List all sprints/milestones for a project.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "integer"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "taiga_get_sprint",
        "description": "Get sprint details with all stories in the sprint.",
        "input_schema": {
            "type": "object",
            "properties": {"sprint_id": {"type": "integer"}},
            "required": ["sprint_id"],
        },
    },
    {
        "name": "taiga_create_sprint",
        "description": "Create a new sprint. Dates in YYYY-MM-DD format.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "name": {"type": "string"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
            },
            "required": ["project_id", "name", "start_date", "end_date"],
        },
    },
]


def list_sprints(client: TaigaClient, args: dict) -> Any:
    return [sprint_summary(m) for m in client.api.milestones.list(project=args["project_id"])]


def get_sprint(client: TaigaClient, args: dict) -> Any:
    milestone = client.api.milestones.get(args["sprint_id"])
    data = sprint_summary(milestone)
    stories = client.api.user_stories.list(milestone=args["sprint_id"])
    data["user_stories"] = [story_summary(s) for s in stories]
    return data


def create_sprint(client: TaigaClient, args: dict) -> Any:
    project = client.api.projects.get(args["project_id"])
    milestone = project.add_milestone(args["name"], args["start_date"], args["end_date"])
    return {"created": True, "id": milestone.id, "name": milestone.name}


HANDLERS = {
    "taiga_list_sprints": list_sprints,
    "taiga_get_sprint": get_sprint,
    "taiga_create_sprint": create_sprint,
}
