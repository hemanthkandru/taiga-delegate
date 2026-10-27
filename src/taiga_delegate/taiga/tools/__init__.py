"""Tool registry and executor.

Each domain module (stories, epics, ...) exports DEFINITIONS (MCP tool specs)
and HANDLERS (name -> callable(client, args) -> plain data). Adding a tool is
adding an entry to its domain module — nothing here changes.
"""

from __future__ import annotations

import logging
from typing import Any

from taiga_delegate.taiga.client import TaigaClient
from taiga_delegate.taiga.serialization import to_json
from taiga_delegate.taiga.tools import (
    comments,
    epics,
    issues,
    projects,
    search,
    sprints,
    stories,
    tasks,
    wiki,
)

logger = logging.getLogger("taiga_delegate.tools")

_DOMAINS = (projects, stories, epics, issues, sprints, tasks, wiki, comments, search)

TOOL_DEFINITIONS: list[dict] = [d for module in _DOMAINS for d in module.DEFINITIONS]

_HANDLERS: dict[str, Any] = {
    name: handler for module in _DOMAINS for name, handler in module.HANDLERS.items()
}

_EXPIRY_MARKERS = ("token_not_valid", "Token is invalid or expired", "401 Unauthorized")


def exec_tool(client: TaigaClient, name: str, args: dict[str, Any]) -> str:
    """Execute a tool; on an expired Taiga token, re-authenticate and retry once."""
    result = _exec_once(client, name, args)
    if any(marker in result for marker in _EXPIRY_MARKERS):
        logger.info("Taiga token expired — re-authenticating and retrying %s", name)
        client.reset()
        result = _exec_once(client, name, args)
    return result


def _exec_once(client: TaigaClient, name: str, args: dict[str, Any]) -> str:
    try:
        handler = _HANDLERS[name]
    except KeyError:
        return to_json({"error": f"Unknown tool: {name}"})
    try:
        return to_json(handler(client, args))
    except Exception as exc:  # noqa: BLE001 — every failure becomes an {"error": ...} tool result
        logger.exception("Tool execution error in %s", name)
        return to_json({"error": f"{type(exc).__name__}: {exc}"})
