"""Project tools: list, inspect, create, invite members."""

from __future__ import annotations

from typing import Any

from taiga_delegate.taiga.client import TaigaClient
from taiga_delegate.taiga.tools._matching import attribute_name, match_id

DEFINITIONS = [
    {
        "name": "taiga_list_projects",
        "description": "List all accessible Taiga projects with ID, name, slug.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "taiga_get_project",
        "description": "Get project details: members, statuses, roles, priorities, issue types.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "integer"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "taiga_create_project",
        "description": "Create a new Taiga project (owned by the connected account). Returns id and slug.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "is_private": {"type": "boolean", "description": "Default true."},
            },
            "required": ["name"],
        },
    },
    {
        "name": "taiga_add_project_member",
        "description": "Invite a user to a project by email with a role (e.g. 'Product Owner', 'Back'). Existing Taiga users are added; unknown emails get an invitation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "email": {"type": "string"},
                "role_name": {"type": "string", "description": "Role name in that project; default 'Product Owner'."},
            },
            "required": ["project_id", "email"],
        },
    },
]


def list_projects(client: TaigaClient, args: dict) -> Any:
    return [
        {"id": p.id, "name": p.name, "slug": getattr(p, "slug", "")}
        for p in client.api.projects.list()
    ]


def get_project(client: TaigaClient, args: dict) -> Any:
    p = client.api.projects.get(args["project_id"])
    return {
        "id": p.id,
        "name": p.name,
        "slug": getattr(p, "slug", ""),
        "description": getattr(p, "description", ""),
        "members": [
            {
                "id": getattr(m, "id", None),
                "username": getattr(m, "username", None),
                "full_name": getattr(m, "full_name", str(m)),
                "role_name": getattr(m, "role_name", None),
            }
            for m in (getattr(p, "members", None) or [])
        ],
        "us_statuses": [{"id": s.id, "name": s.name} for s in (getattr(p, "us_statuses", None) or [])],
        "priorities": [{"id": x.id, "name": x.name} for x in (getattr(p, "priorities", None) or [])],
        "issue_types": [{"id": x.id, "name": x.name} for x in (getattr(p, "issue_types", None) or [])],
        "severities": [{"id": x.id, "name": x.name} for x in (getattr(p, "severities", None) or [])],
    }


def create_project(client: TaigaClient, args: dict) -> Any:
    p = client.api.projects.create(
        args["name"],
        args.get("description", args["name"]),
        is_private=args.get("is_private", True),
    )
    return {"created": True, "id": p.id, "slug": getattr(p, "slug", None), "name": p.name}


def add_project_member(client: TaigaClient, args: dict) -> Any:
    project = client.api.projects.get(args["project_id"])
    roles = getattr(project, "roles", None) or []
    role_id = match_id(roles, args.get("role_name") or "Product Owner")
    if role_id is None:
        available = [attribute_name(r) for r in roles]
        return {"error": f"Role '{args.get('role_name')}' not found. Available: {available}"}
    membership = project.add_membership(args["email"], role_id)
    return {"added": True, "membership_id": getattr(membership, "id", None), "email": args["email"]}


HANDLERS = {
    "taiga_list_projects": list_projects,
    "taiga_get_project": get_project,
    "taiga_create_project": create_project,
    "taiga_add_project_member": add_project_member,
}
