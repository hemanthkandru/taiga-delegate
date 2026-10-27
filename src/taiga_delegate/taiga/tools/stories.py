"""User-story tools: list, get, create, bulk-create, update, delete."""

from __future__ import annotations

from typing import Any

from taiga_delegate.taiga.client import TaigaClient
from taiga_delegate.taiga.serialization import story_summary, task_summary
from taiga_delegate.taiga.tools._matching import match_id

DEFINITIONS = [
    {
        "name": "taiga_list_user_stories",
        "description": "List user stories. Filter by status, sprint_id, epic_id, or assigned_to username.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "status": {"type": "string"},
                "sprint_id": {"type": "integer"},
                "epic_id": {"type": "integer"},
                "assigned_to": {"type": "string"},
            },
            "required": ["project_id"],
        },
    },
    {
        "name": "taiga_get_user_story",
        "description": "Get full story details including description, tasks, and comments.",
        "input_schema": {
            "type": "object",
            "properties": {"story_id": {"type": "integer"}},
            "required": ["story_id"],
        },
    },
    {
        "name": "taiga_create_user_story",
        "description": "Create a user story with subject, description (acceptance criteria), tags, sprint, assignee, and optional epic. IMPORTANT: epic_id must be the internal numeric ID, NOT the ref # shown in the UI — call taiga_list_epics or taiga_resolve_ref first to get the internal ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "sprint_id": {"type": "integer"},
                "assigned_to": {"type": "string"},
                "epic_id": {"type": "integer", "description": "Internal epic ID (not ref #). Get it from taiga_list_epics or taiga_resolve_ref."},
            },
            "required": ["project_id", "subject"],
        },
    },
    {
        "name": "taiga_bulk_create_stories",
        "description": "Create multiple user stories. Each needs 'subject', optionally 'description', 'tags'. IMPORTANT: epic_id must be the internal numeric ID (not ref #) — call taiga_list_epics first to get it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "stories": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "subject": {"type": "string"},
                            "description": {"type": "string"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["subject"],
                    },
                },
                "sprint_id": {"type": "integer"},
                "epic_id": {"type": "integer", "description": "Internal epic ID (not ref #). Get it from taiga_list_epics."},
            },
            "required": ["project_id", "stories"],
        },
    },
    {
        "name": "taiga_update_user_story",
        "description": "Update story fields: subject, description, status (by name), sprint_id, assigned_to, tags. Pass 'comment' to post a comment in the same call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "story_id": {"type": "integer"},
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "status": {"type": "string"},
                "sprint_id": {"type": "integer"},
                "assigned_to": {"type": "string", "description": "Username to assign; empty string to unassign"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "comment": {"type": "string", "description": "Optional comment posted atomically with this update."},
            },
            "required": ["story_id"],
        },
    },
    {
        "name": "taiga_delete_user_story",
        "description": "Permanently delete a user story. Irreversible — confirm with the user before bulk deletions.",
        "input_schema": {
            "type": "object",
            "properties": {"story_id": {"type": "integer", "description": "Internal story ID (not ref #)"}},
            "required": ["story_id"],
        },
    },
]


def list_user_stories(client: TaigaClient, args: dict) -> Any:
    kw: dict[str, Any] = {"project": args["project_id"]}
    if args.get("sprint_id"):
        kw["milestone"] = args["sprint_id"]
    if args.get("epic_id"):
        kw["epic"] = args["epic_id"]
    results = []
    for story in client.api.user_stories.list(**kw):
        info = story_summary(story)
        if args.get("status") and (info.get("status") or "").lower() != args["status"].lower():
            continue
        if args.get("assigned_to") and (info.get("assigned_to") or "").lower() != args["assigned_to"].lower():
            continue
        results.append(info)
    return results


def get_user_story(client: TaigaClient, args: dict) -> Any:
    story = client.api.user_stories.get(args["story_id"])
    data = story_summary(story)
    data["description"] = getattr(story, "description", "")
    data["comments"] = client.fetch_comments("userstory", args["story_id"])
    try:
        tasks = client.api.tasks.list(user_story=args["story_id"])
        data["tasks"] = [task_summary(t) for t in tasks]
    except Exception:  # noqa: BLE001 — tasks are optional detail; the story itself is the answer
        data["tasks"] = []
    return data


def create_user_story(client: TaigaClient, args: dict) -> Any:
    project = client.api.projects.get(args["project_id"])
    kw: dict[str, Any] = {"description": args.get("description", "")}
    if args.get("tags"):
        kw["tags"] = args["tags"]
    if args.get("sprint_id"):
        kw["milestone"] = args["sprint_id"]
    if args.get("assigned_to"):
        uid = client.resolve_user_id(project, args["assigned_to"])
        if uid:
            kw["assigned_to"] = uid
    story = project.add_user_story(args["subject"], **kw)
    epic_link_status = None
    if args.get("epic_id"):
        try:
            client.link_story_to_epic(args["epic_id"], story.id)
            epic_link_status = "linked"
        except Exception as exc:  # noqa: BLE001 — story exists; report the failed link, don't lose it
            epic_link_status = f"FAILED: {exc}"
    return {
        "created": True,
        "id": story.id,
        "ref": getattr(story, "ref", None),
        "subject": story.subject,
        "epic_id": args.get("epic_id"),
        "epic_link": epic_link_status,
    }


def bulk_create_stories(client: TaigaClient, args: dict) -> Any:
    project = client.api.projects.get(args["project_id"])
    epic_id = args.get("epic_id")
    created, errors = [], []
    for idx, spec in enumerate(args["stories"]):
        try:
            kw: dict[str, Any] = {"description": spec.get("description", "")}
            if spec.get("tags"):
                kw["tags"] = spec["tags"]
            if args.get("sprint_id"):
                kw["milestone"] = args["sprint_id"]
            story = project.add_user_story(spec["subject"], **kw)
            link_status = None
            if epic_id:
                try:
                    client.link_story_to_epic(epic_id, story.id)
                    link_status = "linked"
                except Exception as link_err:  # noqa: BLE001 — same rationale as create_user_story
                    link_status = f"FAILED: {link_err}"
            created.append({
                "id": story.id,
                "ref": getattr(story, "ref", None),
                "subject": story.subject,
                "epic_id": epic_id,
                "epic_link": link_status,
            })
        except Exception as exc:  # noqa: BLE001 — one bad story must not abort the batch
            errors.append({"index": idx, "error": str(exc)})
    return {"created": created, "errors": errors}


def update_user_story(client: TaigaClient, args: dict) -> Any:
    story = client.api.user_stories.get(args["story_id"])
    project = client.api.projects.get(story.project)
    payload: dict[str, Any] = {}
    if args.get("subject"):
        payload["subject"] = args["subject"]
    if args.get("description") is not None:
        payload["description"] = args["description"]
    if args.get("tags") is not None:
        payload["tags"] = args["tags"]
    if args.get("sprint_id") is not None:
        payload["milestone"] = args["sprint_id"]
    if args.get("status"):
        status_id = match_id(getattr(project, "us_statuses", None) or [], args["status"])
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
        client.patch_object("userstories", args["story_id"], payload)
    return {"updated": True, "id": story.id}


def delete_user_story(client: TaigaClient, args: dict) -> Any:
    client.api.user_stories.get(args["story_id"]).delete()
    return {"deleted": True, "story_id": args["story_id"]}


HANDLERS = {
    "taiga_list_user_stories": list_user_stories,
    "taiga_get_user_story": get_user_story,
    "taiga_create_user_story": create_user_story,
    "taiga_bulk_create_stories": bulk_create_stories,
    "taiga_update_user_story": update_user_story,
    "taiga_delete_user_story": delete_user_story,
}
