"""Durable per-token usage tracking.

Every tool call is appended as one JSONL line::

    {"ts": "2026-09-25T04:12:03Z", "label": "ravi", "tool": "taiga_list_user_stories", "ok": true}

``label`` is the scoped token's label, or ``"full"`` for the owner token.
``ok`` is false for scope denials and execution errors.

Recording is best-effort by design: a failure to write is logged once and
never breaks the tool call itself.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import defaultdict
from datetime import UTC, datetime, timedelta

logger = logging.getLogger("taiga_delegate.usage")

_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class UsageLog:
    """Append-only JSONL usage log with per-label aggregation."""

    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        self._write_warned = False

    def record(self, label: str, tool: str, ok: bool) -> None:
        """Append one usage line. Never raises."""
        line = json.dumps(
            {
                "ts": datetime.now(UTC).strftime(_TS_FORMAT),
                "label": label,
                "tool": tool,
                "ok": ok,
            },
            separators=(",", ":"),
        )
        try:
            with self._lock, open(self._path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as exc:
            if not self._write_warned:
                logger.warning("usage log unavailable (%s): %s — recording disabled", self._path, exc)
                self._write_warned = True

    def stats(self, days: int = 0) -> dict:
        """Aggregate the log per label. ``days=0`` means all time."""
        cutoff = None
        if days > 0:
            cutoff = datetime.now(UTC) - timedelta(days=days)

        buckets: dict[str, dict] = defaultdict(
            lambda: {"total": 0, "failed": 0, "tools": defaultdict(int),
                     "first_seen": None, "last_seen": None}
        )
        try:
            with open(self._path, encoding="utf-8") as f:
                for raw in f:
                    entry = _parse_entry(raw)
                    if entry is None:
                        continue
                    if cutoff and entry["when"] and entry["when"] < cutoff:
                        continue
                    b = buckets[entry["label"]]
                    b["total"] += 1
                    if not entry["ok"]:
                        b["failed"] += 1
                    b["tools"][entry["tool"]] += 1
                    b["first_seen"] = b["first_seen"] or entry["ts"]
                    b["last_seen"] = entry["ts"]
        except FileNotFoundError:
            return {"note": f"no usage recorded yet (log: {self._path})", "labels": {}}

        labels = {
            label: {
                "total_calls": b["total"],
                "denied_or_failed": b["failed"],
                "first_seen": b["first_seen"],
                "last_seen": b["last_seen"],
                "top_tools": [
                    {"tool": tool, "calls": count}
                    for tool, count in sorted(b["tools"].items(), key=lambda kv: -kv[1])[:10]
                ],
            }
            for label, b in buckets.items()
        }
        return {"window_days": days or "all", "labels": labels}


def _parse_entry(raw: str) -> dict | None:
    """One JSONL line -> normalized entry, or None if unparseable."""
    try:
        e = json.loads(raw)
        when = datetime.strptime(e["ts"], _TS_FORMAT).replace(tzinfo=UTC)
    except (ValueError, KeyError, TypeError):
        try:
            e = json.loads(raw)
            when = None
        except ValueError:
            return None
    return {
        "ts": e.get("ts"),
        "when": when,
        "label": e.get("label", "?"),
        "tool": e.get("tool", "?"),
        "ok": e.get("ok", True),
    }
