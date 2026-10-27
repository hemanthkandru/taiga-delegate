"""Wiki tools: list, get, create, update (upsert), delete."""

from __future__ import annotations

from typing import Any

from taiga_delegate.taiga.client import TaigaClient

DEFINITIONS = [
    {
        "name": "taiga_list_wiki_pages",
        "description": "List all wiki pages in a project (slug and title).",
        "input_schema": {
            "type": "object",
            "properties": {"project_id": {"type": "integer"}},
            "required": ["project_id"],
        },
    },
    {
        "name": "taiga_get_wiki_page",
        "description": "Get the full content of a wiki page by its slug.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "slug": {"type": "string", "description": "The URL-friendly slug of the wiki page (e.g. 'home', 'sprint-notes')."},
            },
            "required": ["project_id", "slug"],
        },
    },
    {
        "name": "taiga_create_wiki_page",
        "description": "Create a new wiki page. Slug should be lowercase with hyphens (e.g. 'sprint-retrospective').",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "slug": {"type": "string", "description": "URL-friendly slug, lowercase with hyphens."},
                "content": {"type": "string", "description": "Markdown content of the wiki page."},
            },
            "required": ["project_id", "slug", "content"],
        },
    },
    {
        "name": "taiga_update_wiki_page",
        "description": "Update the content of an existing wiki page by slug. Creates it if it doesn't exist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "slug": {"type": "string"},
                "content": {"type": "string", "description": "New Markdown content."},
            },
            "required": ["project_id", "slug", "content"],
        },
    },
    {
        "name": "taiga_delete_wiki_page",
        "description": "Permanently delete a wiki page by slug. Irreversible.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer"},
                "slug": {"type": "string"},
            },
            "required": ["project_id", "slug"],
        },
    },
]


def _find_by_slug(client: TaigaClient, project_id: int, slug: str) -> Any:
    """Wiki pages are addressed by slug in the UI but by id in the API."""
    for page in client.api.wikipages.list(project=project_id):
        if getattr(page, "slug", "") == slug:
            return page
    return None


def list_wiki_pages(client: TaigaClient, args: dict) -> Any:
    return [
        {
            "id": p.id,
            "slug": getattr(p, "slug", None),
            "modified_date": str(getattr(p, "modified_date", "")),
        }
        for p in client.api.wikipages.list(project=args["project_id"])
    ]


def get_wiki_page(client: TaigaClient, args: dict) -> Any:
    page = _find_by_slug(client, args["project_id"], args["slug"])
    if page is None:
        return {"error": f"Wiki page '{args['slug']}' not found in project {args['project_id']}"}
    full = client.api.wikipages.get(page.id)
    return {
        "id": full.id,
        "slug": getattr(full, "slug", None),
        "content": getattr(full, "content", ""),
        "version": getattr(full, "version", None),
        "modified_date": str(getattr(full, "modified_date", "")),
    }


def create_wiki_page(client: TaigaClient, args: dict) -> Any:
    page = client.api.wikipages.create(
        project=args["project_id"], slug=args["slug"], content=args["content"]
    )
    return {"created": True, "id": page.id, "slug": getattr(page, "slug", args["slug"])}


def update_wiki_page(client: TaigaClient, args: dict) -> Any:
    page = _find_by_slug(client, args["project_id"], args["slug"])
    if page is None:
        return create_wiki_page(client, args)
    client.patch_object("wiki", page.id, {"content": args["content"]})
    return {"updated": True, "id": page.id, "slug": args["slug"]}


def delete_wiki_page(client: TaigaClient, args: dict) -> Any:
    page = _find_by_slug(client, args["project_id"], args["slug"])
    if page is None:
        return {"error": f"Wiki page '{args['slug']}' not found in project {args['project_id']}"}
    client.api.wikipages.get(page.id).delete()
    return {"deleted": True, "slug": args["slug"]}


HANDLERS = {
    "taiga_list_wiki_pages": list_wiki_pages,
    "taiga_get_wiki_page": get_wiki_page,
    "taiga_create_wiki_page": create_wiki_page,
    "taiga_update_wiki_page": update_wiki_page,
    "taiga_delete_wiki_page": delete_wiki_page,
}
