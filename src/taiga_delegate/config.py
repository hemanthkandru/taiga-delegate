"""Configuration boundary: every environment variable is parsed exactly once, here.

The rest of the codebase receives a `Settings` value and never touches `os.environ`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from taiga_delegate.scope.model import Scope, parse_scoped_tokens


@dataclass(frozen=True)
class Settings:
    """Validated runtime configuration for the server."""

    taiga_url: str
    taiga_username: str = ""
    taiga_password: str = ""
    taiga_token: str = ""
    taiga_auth_type: str = "normal"

    transport: str = "stdio"  # "stdio" | "http"
    http_port: int = 8765
    auth_token: str = ""  # full-access bearer token (required for http)
    scoped_tokens: dict[str, Scope] = field(default_factory=dict)
    usage_log_path: str = "usage.jsonl"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        """Parse settings from the environment. Raises ValueError on bad config."""
        e = os.environ if env is None else env
        settings = cls(
            taiga_url=e.get("TAIGA_URL", "http://localhost:9000").rstrip("/"),
            taiga_username=e.get("TAIGA_USERNAME", ""),
            taiga_password=e.get("TAIGA_PASSWORD", ""),
            taiga_token=e.get("TAIGA_TOKEN", ""),
            taiga_auth_type=e.get("TAIGA_AUTH_TYPE", "normal"),
            transport=e.get("MCP_TRANSPORT", "stdio").lower(),
            http_port=int(e.get("MCP_PORT", "8765")),
            auth_token=e.get("MCP_AUTH_TOKEN", ""),
            scoped_tokens=parse_scoped_tokens(e.get("MCP_SCOPED_TOKENS", "")),
            usage_log_path=e.get("MCP_USAGE_LOG", "usage.jsonl"),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.taiga_token and not (self.taiga_username and self.taiga_password):
            raise ValueError(
                "Taiga credentials missing: set TAIGA_TOKEN, or TAIGA_USERNAME and TAIGA_PASSWORD"
            )
        if self.transport == "http" and not self.auth_token:
            raise ValueError("MCP_TRANSPORT=http requires MCP_AUTH_TOKEN")
        if self.transport not in ("stdio", "http"):
            raise ValueError(f"MCP_TRANSPORT must be 'stdio' or 'http', got {self.transport!r}")
