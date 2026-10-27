"""Issue tools: list, get, create, update, delete."""

from __future__ import annotations

from typing import Any

from taiga_delegate.taiga.client import TaigaClient
from taiga_delegate.taiga.serialization import issue_summary, tag_names
from taiga_delegate.taiga.tools._matching import attribute_id, match_id

DEFINITIONS = [
    {
        "name": "taiga_list_issues",
        "description": "List all issues in a project. Returns summary fields only — use taiga_get_issue for the description and comments.",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "integer"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "taiga_get_issue",
        "description": (
            "Get full issue details including description AND comments. "
            "taiga_list_issues returns only subject/status/assignee, so this is the "
            "only way to read what an issue actually says. Takes the internal id — "
            "use taiga_resolve_ref to convert a # ref first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"issue_id": {"type": "integer"}},
            "required": ["issue_id"],
        },
    },
    {
        "name": "taiga_create_issue",
        "description": "Create an issue with type, priority, severity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "issue_type": {"type": "string"},
                "priority": {"type": "string"},
                "severity": {"type": "string"},
                "assigned_to": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["project_id", "subject"],
        },
    },
    {
        "name": "taiga_update_issue",
        "description": "Update an issue: subject, description, status (e.g. 'Closed' to resolve), priority, severity, assignee, tags. Pass 'comment' to post a comment in the same call.",
        "input_schema": {
            "type": "object",
            "properties": {
                "issue_id": {"type": "integer"},
                "subject": {"type": "string"},
                "description": {"type": "string"},
                "status": {"type": "string", "description": "Status name, e.g. 'In progress', 'Closed'"},
                "priority": {"type": "string"},
                "severity": {"type": "string"},
                "assigned_to": {"type": "string", "description": "Username to assign; empty string to unassign"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "comment": {"type": "string", "description": "Optional comment posted atomically with this update."},
            },
            "required": ["issue_id"],
        },
    },
    {
        "name": "taiga_delete_issue",
        "description": "Permanently delete an issue. Irreversible.",
        "input_schema": {
            "type": "object",
            "properties": {"issue_id": {"type": "integer", "description": "Internal issue ID (not ref #)"}},
            "required": ["issue_id"],
        },
    },
]


def list_issues(client: TaigaClient, args: dict) -> Any:
    return [issue_summary(i) for i in client.api.issues.list(project=args["project_id"])]


def get_issue(client: TaigaClient, args: dict) -> Any:
    issue = client.api.issues.get(args["issue_id"])
    data = issue_summary(issue)
    data["description"] = getattr(issue, "description", "") or ""
    data["type"] = (getattr(issue, "type_extra_info", None) or {}).get("name")
    data["tags"] = tag_names(getattr(issue, "tags", None))
    data["is_blocked"] = getattr(issue, "is_blocked", False)
    data["created_date"] = str(getattr(issue, "created_date", "") or "")
    data["comments"] = client.fetch_comments("issue", args["issue_id"])
    return data


def _pick(collection: Any, wanted: str | None) -> int:
    """Attribute id matching `wanted` by name, or the project default (first)."""
    if wanted:
        matched = match_id(collection, wanted)
        if matched is not None:
            return matched
    return attribute_id(collection[0])


def create_issue(client: TaigaClient, args: dict) -> Any:
    project = client.api.projects.get(args["project_id"])
    priority = _pick(project.priorities, args.get("priority"))
    status = attribute_id(project.issue_statuses[0])
    issue_type = _pick(project.issue_types, args.get("issue_type"))
    severity = _pick(project.severities, args.get("severity"))
    kw: dict[str, Any] = {"description": args.get("description", "")}
    if args.get("tags"):
        kw["tags"] = args["tags"]
    if args.get("assigned_to"):
        uid = client.resolve_user_id(project, args["assigned_to"])
        if uid:
            kw["assigned_to"] = uid
    issue = project.add_issue(args["subject"], priority, status, issue_type, severity, **kw)
    return {"created": True, "id": issue.id, "ref": getattr(issue, "ref", None)}


def update_issue(client: TaigaClient, args: dict) -> Any:
    issue = client.api.issues.get(args["issue_id"])
    project = client.api.projects.get(issue.project)
    payload: dict[str, Any] = {}
    if args.get("subject"):
        payload["subject"] = args["subject"]
    if args.get("description") is not None:
        payload["description"] = args["description"]
    if args.get("tags") is not None:
        payload["tags"] = args["tags"]
    for field, collection in (
        ("status", project.issue_statuses),
        ("priority", project.priorities),
        ("severity", project.severities),
    ):
        if args.get(field):
            matched = match_id(collection, args[field])
            if matched is not None:
                payload[field] = matched
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
        client.patch_object("issues", args["issue_id"], payload)
    return {"updated": True, "id": issue.id}


def delete_issue(client: TaigaClient, args: dict) -> Any:
    client.api.issues.get(args["issue_id"]).delete()
    return {"deleted": True, "issue_id": args["issue_id"]}


HANDLERS = {
    "taiga_list_issues": list_issues,
    "taiga_get_issue": get_issue,
    "taiga_create_issue": create_issue,
    "taiga_update_issue": update_issue,
    "taiga_delete_issue": delete_issue,
}
