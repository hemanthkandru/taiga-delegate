"""Per-request scope binding.

The auth layer sets this contextvar when a request authenticates; the MCP
handlers read it. ``None`` means full (owner) access.
"""

from __future__ import annotations

import contextvars

from taiga_delegate.scope.model import Scope

current_scope: contextvars.ContextVar[Scope | None] = contextvars.ContextVar(
    "taiga_delegate_scope", default=None
)
