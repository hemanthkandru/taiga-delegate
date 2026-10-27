"""Entrypoint: parse settings, wire dependencies, run the chosen transport.

stdio (default) — Claude Code spawns the process:
    taiga-delegate
    # or: python -m taiga_delegate

HTTP — for a server deployment behind a reverse proxy; serves the MCP
streamable-HTTP protocol at /mcp. MCP_AUTH_TOKEN is required in this mode.
"""

from __future__ import annotations

import asyncio
import logging
import sys

from taiga_delegate.config import Settings
from taiga_delegate.server.auth import BearerAuthMiddleware
from taiga_delegate.server.handlers import build_server
from taiga_delegate.taiga.client import TaigaClient
from taiga_delegate.usage.tracking import UsageLog

logger = logging.getLogger("taiga_delegate")


async def run_stdio(server) -> None:
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run_http(server, settings: Settings) -> None:
    import uvicorn
    from mcp.server.transport_security import TransportSecuritySettings

    if settings.scoped_tokens:
        logger.info(
            "Scoped tokens loaded: %s",
            ", ".join(
                f"{s.label}→p{s.project_id}/e{','.join(str(e) for e in sorted(s.epic_ids))}"
                for s in settings.scoped_tokens.values()
            ),
        )
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        # We sit behind a reverse proxy (the Host header varies between
        # internal and external requests) and enforce our own bearer auth,
        # so host-header pinning is disabled.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    logger.info("Starting MCP streamable-HTTP server on :%d/mcp", settings.http_port)
    uvicorn.run(
        BearerAuthMiddleware(app, settings.auth_token, settings.scoped_tokens),
        host="0.0.0.0",
        port=settings.http_port,
    )


def main() -> None:
    # stdio uses stdout for the protocol — logs must go to stderr.
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    try:
        settings = Settings.from_env()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        sys.exit(1)

    client = TaigaClient(settings)
    usage = UsageLog(settings.usage_log_path)
    server = build_server(client, usage)

    if settings.transport == "http":
        run_http(server, settings)
    else:
        asyncio.run(run_stdio(server))


if __name__ == "__main__":
    main()
