"""Taiga session management and the raw REST operations python-taiga lacks.

One responsibility: hold an authenticated connection to Taiga (self-hosted or
taiga.io cloud) and expose the low-level operations the tool layer needs.
Everything here speaks Taiga's wire shapes; nothing above this module does.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from taiga import TaigaAPI

from taiga_delegate.config import Settings

logger = logging.getLogger("taiga_delegate.client")


class TaigaClient:
    """Lazily-authenticated Taiga session with expiry recovery.

    Taiga access tokens expire (typically daily). `reset()` drops the session
    so the next `api` access re-authenticates; the tool executor retries once
    on an expired-token error.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._api: TaigaAPI | None = None

    @property
    def api(self) -> TaigaAPI:
        if self._api is None:
            self._api = self._authenticate()
        return self._api

    def reset(self) -> None:
        """Force re-auth on next use (e.g. after token expiry)."""
        self._api = None

    def _authenticate(self) -> TaigaAPI:
        s = self._settings
        api = TaigaAPI(host=s.taiga_url, auth_type=s.taiga_auth_type)
        if s.taiga_token:
            api.token = s.taiga_token
        else:
            api.auth(username=s.taiga_username, password=s.taiga_password)
        return api

    # -- Raw REST operations (python-taiga gaps) ----------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api.token}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self._settings.taiga_url}/api/v1/{path}"

    def patch_object(self, endpoint: str, obj_id: int, payload: dict[str, Any]) -> dict:
        """PATCH only the given fields (plus version) so untouched fields —
        assignee, sprint, points — are never wiped, unlike python-taiga's
        full-object PUT in ``model.update()``."""
        url = self._url(f"{endpoint}/{obj_id}")
        with httpx.Client(timeout=30) as http:
            current = http.get(url, headers=self._headers())
            current.raise_for_status()
            version = current.json().get("version", 1)
            resp = http.patch(url, headers=self._headers(), json={**payload, "version": version})
            resp.raise_for_status()
            return resp.json()

    def link_story_to_epic(self, epic_id: int, story_id: int) -> dict:
        url = self._url(f"epics/{epic_id}/related_userstories")
        with httpx.Client(timeout=30) as http:
            resp = http.post(
                url, headers=self._headers(), json={"epic": epic_id, "user_story": story_id}
            )
            resp.raise_for_status()
            return resp.json()

    def unlink_story_from_epic(self, epic_id: int, story_id: int) -> None:
        url = self._url(f"epics/{epic_id}/related_userstories/{story_id}")
        with httpx.Client(timeout=30) as http:
            resp = http.delete(url, headers=self._headers())
            resp.raise_for_status()

    def fetch_comments(self, object_type: str, object_id: int) -> list[dict]:
        """Comments for an issue/story/task, oldest first.

        Taiga does not carry comments on the object — they live in the history
        endpoint, mixed with field-change entries that have an empty comment.
        Never raises: a failed fetch degrades the reply, not the tool call.
        """
        comments: list[dict] = []
        try:
            url = self._url(f"history/{object_type}/{object_id}")
            with httpx.Client(timeout=30) as http:
                resp = http.get(url, headers=self._headers())
                resp.raise_for_status()
                for h in resp.json():
                    text = (h.get("comment") or "").strip()
                    if text:
                        comments.append({
                            "user": (h.get("user") or {}).get("username"),
                            "created": h.get("created_at"),
                            "comment": text,
                        })
        except Exception as exc:  # noqa: BLE001 — degrade, never fail the call
            comments.append({"user": None, "created": None,
                             "comment": f"[comment fetch failed: {str(exc)[:120]}]"})
        comments.reverse()  # history is newest-first; reading order is oldest-first
        return comments

    def resolve_user_id(self, project: Any, username: str) -> int | None:
        """Username -> user id, trying project members first, then global users."""
        if not username:
            return None
        for member in getattr(project, "members", None) or []:
            m_name = member.get("username") if isinstance(member, dict) else getattr(member, "username", None)
            m_id = member.get("id") if isinstance(member, dict) else getattr(member, "id", None)
            if m_name == username:
                return m_id
        try:
            for user in self.api.users.list():
                if user.username == username:
                    return user.id
        except Exception:  # noqa: BLE001 — a failed global lookup just means "not found"
            pass
        return None


class BoardInspectorImpl:
    """Live-board lookups for scope enforcement (scope.policy.BoardInspector)."""

    def __init__(self, client: TaigaClient):
        self._client = client

    def story_epic_ids(self, story_id: int) -> set[int]:
        def lookup() -> set[int]:
            story = self._client.api.user_stories.get(story_id)
            ids: set[int] = set()
            for epic in getattr(story, "epics", None) or []:
                epic_id = epic.get("id") if isinstance(epic, dict) else getattr(epic, "id", None)
                if epic_id is not None:
                    ids.add(epic_id)
            extra = getattr(story, "epic_extra_info", None)
            if extra:
                epic_id = extra.get("id") if isinstance(extra, dict) else getattr(extra, "id", None)
                if epic_id is not None:
                    ids.add(epic_id)
            return ids

        return self._retry_expired(lookup)

    def issue_tags(self, issue_id: int) -> set[str]:
        def lookup() -> set[str]:
            issue = self._client.api.issues.get(issue_id)
            return {
                tag[0] if isinstance(tag, (list, tuple)) else tag
                for tag in (getattr(issue, "tags", None) or [])
            }

        return self._retry_expired(lookup)

    def _retry_expired(self, fn):
        try:
            return fn()
        except Exception as exc:
            message = str(exc).lower()
            if "token" in message or "401" in message:
                self._client.reset()
                return fn()
            raise
