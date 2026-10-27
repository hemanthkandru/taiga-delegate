"""Scope domain model: what a scoped collaborator token is allowed to touch.

A scope confines one token to one or more epics in ONE project: those epics,
their linked stories, their bugs (issues tagged ``epic-<id>``), and comments
on those.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Scope:
    """One collaborator token's boundary."""

    label: str
    project_id: int
    epic_ids: frozenset[int] = field(default_factory=frozenset)
    # Optional self-set display name (X-Collaborator-Name header). The label
    # stays authoritative in logs; `who` is what appears in comments and tags.
    display: str = ""

    @property
    def tags(self) -> frozenset[str]:
        """The issue tags that mark a bug as belonging to this scope's epics."""
        return frozenset(f"epic-{epic_id}" for epic_id in self.epic_ids)

    @property
    def sole_epic_id(self) -> int | None:
        """The epic id when the scope covers exactly one epic, else None.

        Single-epic scopes keep the frictionless behavior (creates and lists
        are forced onto the epic automatically); multi-epic scopes need the
        caller to say which epic it means.
        """
        if len(self.epic_ids) == 1:
            return next(iter(self.epic_ids))
        return None

    @property
    def epics_text(self) -> str:
        """Human-readable epic list for denial messages."""
        ids = ", ".join(str(epic_id) for epic_id in sorted(self.epic_ids))
        return f"epic {ids}" if len(self.epic_ids) == 1 else f"epics {ids}"

    @property
    def who(self) -> str:
        return self.display or self.label

    @property
    def who_tag(self) -> str:
        """Attribution tag added to items this collaborator creates."""
        slug = "".join(c if c.isalnum() else "-" for c in self.who.lower()).strip("-")
        return f"by-{slug or self.label.lower()}"


def sanitize_display(raw: str) -> str:
    """Normalize a self-set display name arriving from an untrusted client.

    Display names end up inside comment signatures (``**[name]**``) and tags,
    so characters that could forge or break that markup are dropped, along
    with anything non-printable; whitespace is collapsed.
    """
    cleaned = "".join(ch if ch.isprintable() else " " for ch in raw if ch not in "[]*`")
    return " ".join(cleaned.split())[:64]


def parse_scoped_tokens(raw: str) -> dict[str, Scope]:
    """Parse ``label:token:project_id:epic_id[,epic_id...][;...]`` into ``{token: Scope}``.

    Raises ValueError on a malformed entry (fail fast at startup, never at
    request time).
    """
    scopes: dict[str, Scope] = {}
    for entry in (raw or "").split(";"):
        entry = entry.strip()
        if not entry:
            continue
        try:
            label, token, project_id, epics = entry.split(":")
            epic_ids = frozenset(int(epic_id) for epic_id in epics.split(","))
            if not epic_ids:
                raise ValueError("no epic ids")
            scopes[token] = Scope(label=label, project_id=int(project_id), epic_ids=epic_ids)
        except ValueError as exc:
            visible = entry.split(":")[0]
            raise ValueError(
                f"Bad MCP_SCOPED_TOKENS entry (want label:token:project_id:epic_id[,epic_id...]): {visible}"
            ) from exc
    return scopes
