import json
from datetime import datetime

from taiga_delegate.taiga.serialization import (
    story_summary,
    strip_empty,
    tag_names,
    to_json,
)


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_strip_empty_keeps_falsy_information():
    data = {"a": None, "b": "", "c": [], "d": False, "e": 0, "f": "x"}
    assert strip_empty(data) == {"d": False, "e": 0, "f": "x"}


def test_strip_empty_recurses():
    assert strip_empty({"outer": {"gone": None, "kept": 1}}) == {"outer": {"kept": 1}}


def test_to_json_compact_and_dates():
    out = to_json({"when": datetime(2026, 1, 2, 3, 4, 5), "empty": ""})
    assert out == '{"when":"2026-01-02T03:04:05"}'
    assert ": " not in out


def test_tag_names_handles_pairs_and_strings():
    assert tag_names([["bug", "#ff0000"], "plain"]) == ["bug", "plain"]
    assert tag_names(None) == []


def test_story_summary_reads_dict_extra_info():
    story = Obj(
        id=1,
        ref=12,
        subject="s",
        status_extra_info={"name": "Done"},
        assigned_to_extra_info={"username": "alex"},
        total_points=3,
        tags=[["by-alex", None]],
        milestone=7,
        epic_extra_info={"id": 117, "subject": "Epic"},
        modified_date="2026-01-01",
    )
    data = story_summary(story)
    assert data["status"] == "Done"
    assert data["assigned_to"] == "alex"
    assert data["epic"] == {"id": 117, "subject": "Epic"}
    assert data["tags"] == ["by-alex"]
    json.dumps(data)  # must be plain data
