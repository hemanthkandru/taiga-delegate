"""MCP protocol handlers: tools/list and tools/call.

This is where the layers meet: the tool registry executes against Taiga, the
scope policy constrains collaborator sessions, and every call is usage-logged.
"""

from __future__ import annotations

import asyncio
import json
import logging

from mcp.server import Server
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)

from taiga_delegate.scope.policy import ALLOWED_TOOLS, ScopeError, apply_scope, filter_result
from taiga_delegate.server.context import current_scope
from taiga_delegate.taiga.client import BoardInspectorImpl, TaigaClient
from taiga_delegate.taiga.tools import TOOL_DEFINITIONS, exec_tool
from taiga_delegate.usage.tracking import UsageLog

logger = logging.getLogger("taiga_delegate.server")

# Owner-only tool: not in scope.policy.ALLOWED_TOOLS, so scoped sessions
# neither see nor may call it.
USAGE_STATS_TOOL = {
    "name": "mcp_usage_stats",
    "description": "Per-token MCP usage stats: total calls, denials, top tools, first/last seen for each token label. Owner (full token) only.",
    "input_schema": {
        "type": "object",
        "properties": {
            "days": {"type": "integer", "description": "Look-back window in days; omit or 0 for all time."},
        },
        "required": [],
    },
}


def build_server(client: TaigaClient, usage: UsageLog) -> Server:
    """Wire the MCP server with its dependencies injected."""
    board = BoardInspectorImpl(client)
    server = Server("taiga-delegate")

    async def handle_list_tools(ctx, params: PaginatedRequestParams) -> ListToolsResult:
        scope = current_scope.get()
        if scope is None:
            tools = TOOL_DEFINITIONS + [USAGE_STATS_TOOL]
        else:
            tools = [t for t in TOOL_DEFINITIONS if t["name"] in ALLOWED_TOOLS]
        return ListToolsResult(
            tools=[
                Tool(name=t["name"], description=t["description"], input_schema=t["input_schema"])
                for t in tools
            ]
        )

    async def handle_call_tool(ctx, params: CallToolRequestParams) -> CallToolResult:
        # Tool execution is synchronous (python-taiga + httpx sync clients);
        # run it off the event loop so long Taiga calls don't block protocol
        # heartbeats.
        scope = current_scope.get()
        label = scope.label if scope is not None else "full"
        ok = False
        try:
            args = params.arguments or {}
            postfilter = None
            if scope is not None:
                logger.info("[scope:%s] tool %s", scope.label, params.name)
                args, postfilter = await asyncio.to_thread(
                    apply_scope, scope, params.name, args, board
                )
            if params.name == "mcp_usage_stats":
                # Reached only with the full token: scoped calls are rejected
                # by apply_scope above (not in ALLOWED_TOOLS).
                result = json.dumps(
                    usage.stats(int(args.get("days") or 0)), separators=(",", ":")
                )
            else:
                result = await asyncio.to_thread(exec_tool, client, params.name, args)
                result = filter_result(result, postfilter)
            ok = '"error"' not in result[:12]
            return CallToolResult(content=[TextContent(type="text", text=result)])
        except ScopeError as exc:
            return CallToolResult(
                content=[TextContent(type="text", text=str(exc))], is_error=True
            )
        except Exception as exc:  # noqa: BLE001 — protocol errors must become tool errors
            return CallToolResult(
                content=[TextContent(type="text", text=f"{type(exc).__name__}: {exc}")],
                is_error=True,
            )
        finally:
            await asyncio.to_thread(usage.record, label, params.name, ok)

    server.add_request_handler("tools/list", PaginatedRequestParams, handle_list_tools)
    server.add_request_handler("tools/call", CallToolRequestParams, handle_call_tool)
    return server
