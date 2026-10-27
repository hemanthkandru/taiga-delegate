"""Epic tools: list, get, create, update, delete, link/unlink stories."""

from __future__ import annotations

from typing import Any

from taiga_delegate.taiga.client import TaigaClient
from taiga_delegate.taiga.serialization import epic_summary, story_summary
from taiga_delegate.taiga.tools._matching import match_id

DEFINITIONS = [
    {
        "name": "taiga_list_epics",
        "description": "List all epics in a project with their status, assignee, and story count.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "assigned_to": {"type": "string"},
                "status": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "taiga_get_epic",
        "description": "Get full epic details including description and linked user stories.",
        "input_schema": {
            "type": "object",
            "properties": {"epic_id": {"type": "integer"}},
            "required": ["epic_id"],
        },
    },
    {
        "name": "taiga_create_epic",
        "description": "Create an epic to group related user stories under a high-level goal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "assigned_to": {"type": "string"},
                "color": {"type": "string", "description": "Hex color code, e.g. #3498db"},
            },
            "required": ["project_id", "subject"],
        },
    },
    {
        "name": "taiga_update_epic",
        "description": "Update epic fields: subject, description, status (by name), assigned_to, tags, color. Pass 'comment' to post a comment in the same call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "epic_id": {"type": "integer"},
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "status": {"type": "string"},
                "assigned_to": {"type": "string", "description": "Username to assign; empty string to unassign"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "color": {"type": "string"},
                "comment": {"type": "string", "description": "Optional comment posted atomically with this update."},
            },
            "required": ["epic_id"],
        },
    },
    {
        "name": "taiga_delete_epic",
        "description": "Permanently delete an epic (its stories survive, unlinked). Irreversible.",
        "input_schema": {
            "type": "object",
            "properties": {"epic_id": {"type": "integer", "description": "Internal epic ID (not ref #)"}},
            "required": ["epic_id"],
        },
    },
    {
        "name": "taiga_link_story_to_epic",
        "description": "Link an existing user story to an epic. Both epic_id and story_id must be internal IDs (not ref #s). Use taiga_resolve_ref to convert ref numbers first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "epic_id": {"type": "integer", "description": "Internal epic ID (not ref #)"},
                "story_id": {"type": "integer", "description": "Internal story ID (not ref #)"},
            },
            "required": ["epic_id", "story_id"],
        },
    },
    {
        "name": "taiga_unlink_story_from_epic",
        "description": "Remove a user story from an epic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "epic_id": {"type": "integer"},
                "story_id": {"type": "integer"},
            },
            "required": ["epic_id", "story_id"],
        },
    },
]


def list_epics(client: TaigaClient, args: dict) -> Any:
    results = []
    for epic in client.api.epics.list(project=args["project_id"]):
        info = epic_summary(epic)
        if args.get("status") and (info.get("status") or "").lower() != args["status"].lower():
            continue
        if args.get("assigned_to") and (info.get("assigned_to") or "").lower() != args["assigned_to"].lower():
            continue
        results.append(info)
    return results


def get_epic(client: TaigaClient, args: dict) -> Any:
    epic = client.api.epics.get(args["epic_id"])
    data = epic_summary(epic)
    data["description"] = getattr(epic, "description", "")
    try:
        related = client.api.epic_related_userstories.list(epic=args["epic_id"])
        data["related_stories"] = [
            {"id": getattr(r, "user_story", None), "epic_order": getattr(r, "epic_order", None)}
            for r in related
        ]
    except Exception:  # noqa: BLE001 — older Taiga lacks this endpoint; fall back to a filtered list
        try:
            stories = client.api.user_stories.list(epic=args["epic_id"])
            data["related_stories"] = [story_summary(s) for s in stories]
        except Exception:  # noqa: BLE001 — the epic itself is still a useful answer
            data["related_stories"] = []
    return data


def create_epic(client: TaigaClient, args: dict) -> Any:
    project = client.api.projects.get(args["project_id"])
    kw: dict[str, Any] = {"description": args.get("description", "")}
    if args.get("tags"):
        kw["tags"] = args["tags"]
    if args.get("color"):
        kw["color"] = args["color"]
    epic = project.add_epic(args["subject"], **kw)
    # Taiga rejects assigned_to at creation time; patch it on afterwards.
    if args.get("assigned_to"):
        uid = client.resolve_user_id(project, args["assigned_to"])
        if uid:
            client.patch_object("epics", epic.id, {"assigned_to": uid})
    return {
        "created": True,
        "id": epic.id,
        "ref": getattr(epic, "ref", None),
        "subject": epic.subject,
        "assigned_to": args.get("assigned_to"),
    }


def update_epic(client: TaigaClient, args: dict) -> Any:
    epic = client.api.epics.get(args["epic_id"])
    project = client.api.projects.get(epic.project)
    payload: dict[str, Any] = {}
    if args.get("subject"):
        payload["subject"] = args["subject"]
    if args.get("description") is not None:
        payload["description"] = args["description"]
    if args.get("tags") is not None:
        payload["tags"] = args["tags"]
    if args.get("color"):
        payload["color"] = args["color"]
    if args.get("status"):
        status_id = match_id(getattr(project, "epic_statuses", None) or [], args["status"])
        if status_id is not None:
            payload["status"] = status_id
    if "assigned_to" in args:
        if args["assigned_to"]:
            uid = client.resolve_user_id(project, args["assigned_to"])
            if uid:
                payload["assigned_to"] = uid
        else:
            payload["assigned_to"] = None  # explicit empty string/null = unassign
    if args.get("comment"):
        payload["comment"] = args["comment"]
    if payload:
        client.patch_object("epics", args["epic_id"], payload)
    return {"updated": True, "id": epic.id}


def delete_epic(client: TaigaClient, args: dict) -> Any:
    client.api.epics.get(args["epic_id"]).delete()
    return {"deleted": True, "epic_id": args["epic_id"]}


def link_story(client: TaigaClient, args: dict) -> Any:
    client.link_story_to_epic(args["epic_id"], args["story_id"])
    return {"linked": True, "epic_id": args["epic_id"], "story_id": args["story_id"]}


def unlink_story(client: TaigaClient, args: dict) -> Any:
    client.unlink_story_from_epic(args["epic_id"], args["story_id"])
    return {"unlinked": True, "epic_id": args["epic_id"], "story_id": args["story_id"]}


HANDLERS = {
    "taiga_list_epics": list_epics,
    "taiga_get_epic": get_epic,
    "taiga_create_epic": create_epic,
    "taiga_update_epic": update_epic,
    "taiga_delete_epic": delete_epic,
    "taiga_link_story_to_epic": link_story,
    "taiga_unlink_story_from_epic": unlink_story,
}
