"""Scope enforcement policy: which tools a scoped session may call, with what
arguments, and how results are filtered.

This module is pure domain logic. Ownership checks that need live board data
(is this story in one of the scope's epics? does this issue carry an epic tag?)
go through the injected `BoardInspector` abstraction — the policy never talks
to Taiga directly, which keeps it fully unit-testable.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from taiga_delegate.scope.model import Scope

PostFilter = Callable[[list], list]


class ScopeError(Exception):
    """A scoped session attempted something outside its scope."""


class BoardInspector(Protocol):
    """The two live lookups the policy needs, abstracted away from the client."""

    def story_epic_ids(self, story_id: int) -> set[int]: ...

    def issue_tags(self, issue_id: int) -> set[str]: ...


# Tools a scoped session may use at all. Fail closed: anything not listed —
# including tools added to the server later — is denied and hidden.
ALLOWED_TOOLS = frozenset({
    "taiga_list_projects",
    "taiga_list_epics",
    "taiga_get_epic",
    "taiga_list_user_stories",
    "taiga_get_user_story",
    "taiga_create_user_story",
    "taiga_bulk_create_stories",
    "taiga_update_user_story",
    "taiga_list_issues",
    "taiga_get_issue",
    "taiga_create_issue",
    "taiga_update_issue",
    "taiga_add_comment",
    "taiga_resolve_ref",
})


def apply_scope(
    scope: Scope, name: str, args: dict[str, Any], board: BoardInspector
) -> tuple[dict[str, Any], PostFilter | None]:
    """Validate and rewrite a scoped tool call.

    Returns (possibly rewritten args, optional post-filter for list results).
    Raises ScopeError when the call is out of scope.
    """
    if name not in ALLOWED_TOOLS:
        raise ScopeError(_denial(scope, f"The tool '{name}' is not available with a scoped token."))

    handler = _RULES.get(name)
    if handler is None:
        # In ALLOWED_TOOLS but without a rule — a programming error; fail closed.
        raise ScopeError(_denial(scope, f"The tool '{name}' is not available with a scoped token."))
    return handler(scope, dict(args or {}), board)


def filter_result(result: str, postfilter: PostFilter | None) -> str:
    """Apply a post-filter to a JSON list result; pass everything else through."""
    if postfilter is None:
        return result
    try:
        data = json.loads(result)
    except ValueError:
        return result
    if isinstance(data, list):
        return json.dumps(postfilter(data), separators=(",", ":"), default=str)
    return result


# ---------------------------------------------------------------------------
# Per-tool rules
# ---------------------------------------------------------------------------

def _denial(scope: Scope, detail: str) -> str:
    return (
        f"{detail} Your token is scoped to {scope.epics_text} in project "
        f"{scope.project_id}: those epics, their linked stories, their bugs "
        f"(issues tagged 'epic-<id>'), and comments on those. Ask the project "
        f"owner for broader access if needed."
    )


def _signed(scope: Scope, comment: str) -> str:
    """All scoped users share the agent's Taiga identity, so the comment text
    itself carries the attribution."""
    return f"**[{scope.who}]** {comment}"


def _with_tag(tags: list | None, tag: str) -> list:
    tags = list(tags or [])
    if tag not in tags:
        tags.append(tag)
    return tags


def _require_story_in_scope(scope: Scope, story_id: int, board: BoardInspector) -> None:
    if not (scope.epic_ids & board.story_epic_ids(story_id)):
        raise ScopeError(_denial(scope, f"Story {story_id} is not linked to your epics."))


def _require_issue_in_scope(scope: Scope, issue_id: int, board: BoardInspector) -> None:
    if not (scope.tags & board.issue_tags(issue_id)):
        raise ScopeError(_denial(scope, f"Issue {issue_id} is not one of your epics' bugs."))


def _require_target_epic(scope: Scope, args: dict) -> int:
    """The epic a create/list call targets: the one given (if in scope), or the
    scope's only epic. A multi-epic scope must say which epic it means."""
    epic_id = args.get("epic_id")
    if epic_id is not None:
        if epic_id not in scope.epic_ids:
            raise ScopeError(_denial(scope, f"Epic {epic_id} is not one of your epics."))
        return epic_id
    sole = scope.sole_epic_id
    if sole is None:
        raise ScopeError(_denial(
            scope, f"Pass epic_id to say which of your epics this targets ({scope.epics_text})."
        ))
    return sole


def _list_projects(scope, args, board):
    return args, lambda data: [p for p in data if p.get("id") == scope.project_id]


def _list_epics(scope, args, board):
    args["project_id"] = scope.project_id
    return args, lambda data: [e for e in data if e.get("id") in scope.epic_ids]


def _get_epic(scope, args, board):
    if args.get("epic_id") not in scope.epic_ids:
        raise ScopeError(_denial(scope, f"Epic {args.get('epic_id')} is not one of your epics."))
    return args, None


def _list_stories(scope, args, board):
    args["project_id"] = scope.project_id
    epic_id = args.get("epic_id")
    if epic_id is not None:
        if epic_id not in scope.epic_ids:
            raise ScopeError(_denial(scope, f"Epic {epic_id} is not one of your epics."))
        return args, None
    sole = scope.sole_epic_id
    if sole is not None:
        args["epic_id"] = sole
        return args, None
    # Multi-epic scope, no epic filter: list the project once and keep only
    # stories whose epic is in scope.
    return args, lambda data: [
        s for s in data if (s.get("epic") or {}).get("id") in scope.epic_ids
    ]


def _get_or_update_story(scope, args, board):
    _require_story_in_scope(scope, args.get("story_id"), board)
    if args.get("comment"):
        args["comment"] = _signed(scope, args["comment"])
    return args, None


def _create_story(scope, args, board):
    args["project_id"] = scope.project_id
    args["epic_id"] = _require_target_epic(scope, args)
    args["tags"] = _with_tag(args.get("tags"), scope.who_tag)
    return args, None


def _bulk_create_stories(scope, args, board):
    args["project_id"] = scope.project_id
    args["epic_id"] = _require_target_epic(scope, args)
    for story in args.get("stories") or []:
        story["tags"] = _with_tag(story.get("tags"), scope.who_tag)
    return args, None


def _list_issues(scope, args, board):
    args["project_id"] = scope.project_id
    return args, lambda data: [i for i in data if scope.tags & set(i.get("tags") or [])]


def _get_or_update_issue(scope, args, board):
    _require_issue_in_scope(scope, args.get("issue_id"), board)
    if args.get("comment"):
        args["comment"] = _signed(scope, args["comment"])
    return args, None


def _create_issue(scope, args, board):
    args["project_id"] = scope.project_id
    # The epic tag is what ties a bug to an epic; a multi-epic scope picks the
    # epic with an `epic_id` argument (accepted here, not forwarded to Taiga).
    epic_id = _require_target_epic(scope, args)
    args.pop("epic_id", None)
    args["tags"] = _with_tag(_with_tag(args.get("tags"), f"epic-{epic_id}"), scope.who_tag)
    return args, None


def _add_comment(scope, args, board):
    object_type, object_id = args.get("object_type"), args.get("object_id")
    if object_type == "epic":
        if object_id not in scope.epic_ids:
            raise ScopeError(_denial(scope, f"Epic {object_id} is not one of your epics."))
    elif object_type == "userstory":
        _require_story_in_scope(scope, object_id, board)
    elif object_type == "issue":
        _require_issue_in_scope(scope, object_id, board)
    else:
        raise ScopeError(_denial(scope, f"Comments on '{object_type}' objects are not available."))
    args["comment"] = _signed(scope, args.get("comment") or "")
    return args, None


def _resolve_ref(scope, args, board):
    args["project_id"] = scope.project_id
    if args.get("object_type") not in ("userstory", "issue", "epic"):
        raise ScopeError(_denial(scope, "Only story/issue/epic refs can be resolved."))
    return args, None


_RULES: dict[str, Callable] = {
    "taiga_list_projects": _list_projects,
    "taiga_list_epics": _list_epics,
    "taiga_get_epic": _get_epic,
    "taiga_list_user_stories": _list_stories,
    "taiga_get_user_story": _get_or_update_story,
    "taiga_update_user_story": _get_or_update_story,
    "taiga_create_user_story": _create_story,
    "taiga_bulk_create_stories": _bulk_create_stories,
    "taiga_list_issues": _list_issues,
    "taiga_get_issue": _get_or_update_issue,
    "taiga_update_issue": _get_or_update_issue,
    "taiga_create_issue": _create_issue,
    "taiga_add_comment": _add_comment,
    "taiga_resolve_ref": _resolve_ref,
}
