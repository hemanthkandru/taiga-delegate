"""Bearer-token authentication for the HTTP transport.

Two kinds of credentials:
  * the full-access token (MCP_AUTH_TOKEN) — owner session, no scope
  * a scoped collaborator token (MCP_SCOPED_TOKENS) — binds that token's
    Scope to the request; an optional X-Collaborator-Name header sets the
    display name used in comment signatures and by-tags

Anything else is rejected with 401 before it reaches the MCP app.

Clients are untrusted by design — a collaborator may connect with any MCP
client or plain HTTP calls — so header values are decoded defensively, the
display name is sanitized before it can reach board content, and token
comparisons are constant-time.
"""

from __future__ import annotations

import secrets
from dataclasses import replace

from taiga_delegate.scope.model import Scope, sanitize_display
from taiga_delegate.server.context import current_scope


class BearerAuthMiddleware:
    """ASGI middleware: authenticate and bind the request's scope."""

    def __init__(self, app, token: str, scoped_tokens: dict[str, Scope] | None = None):
        self.app = app
        self.expected = f"Bearer {token}".encode()
        self.scoped = scoped_tokens or {}

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"")
            if secrets.compare_digest(auth, self.expected):
                current_scope.set(None)
            else:
                decoded = auth.decode("utf-8", errors="replace")
                bearer = decoded[7:] if decoded.startswith("Bearer ") else ""
                token_scope = self._match_scoped(bearer)
                if token_scope is None:
                    await _reject(send)
                    return
                display = sanitize_display(
                    headers.get(b"x-collaborator-name", b"").decode("utf-8", errors="replace")
                )
                if display:
                    token_scope = replace(token_scope, display=display)
                current_scope.set(token_scope)
        await self.app(scope, receive, send)

    def _match_scoped(self, bearer: str) -> Scope | None:
        # Compare against every configured token so lookup time doesn't leak
        # which prefix matched.
        match = None
        for token, token_scope in self.scoped.items():
            if secrets.compare_digest(token.encode(), bearer.encode()):
                match = token_scope
        return match


async def _reject(send) -> None:
    await send({
        "type": "http.response.start",
        "status": 401,
        "headers": [(b"content-type", b"application/json")],
    })
    await send({"type": "http.response.body", "body": b'{"error": "unauthorized"}'})
