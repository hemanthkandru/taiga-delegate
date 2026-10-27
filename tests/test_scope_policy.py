import json

import pytest

from taiga_delegate.scope.model import Scope
from taiga_delegate.scope.policy import ScopeError, apply_scope, filter_result

SCOPE = Scope(label="alex", project_id=2, epic_ids=frozenset({117}))
MULTI = Scope(label="alex", project_id=2, epic_ids=frozenset({117, 118}))


class FakeBoard:
    """BoardInspector stub: story 10 is in the epic, issue 20 carries the tag."""

    def story_epic_ids(self, story_id):
        return {117} if story_id == 10 else {5}

    def issue_tags(self, issue_id):
        return {"epic-117", "bug"} if issue_id == 20 else {"bug"}


BOARD = FakeBoard()


def test_unlisted_tool_denied():
    with pytest.raises(ScopeError, match="not available"):
        apply_scope(SCOPE, "taiga_delete_user_story", {"story_id": 10}, BOARD)


def test_list_projects_postfiltered():
    _, postfilter = apply_scope(SCOPE, "taiga_list_projects", {}, BOARD)
    data = [{"id": 1}, {"id": 2}, {"id": 3}]
    assert postfilter(data) == [{"id": 2}]


def test_list_epics_forced_and_filtered():
    args, postfilter = apply_scope(SCOPE, "taiga_list_epics", {"project_id": 99}, BOARD)
    assert args["project_id"] == 2
    assert postfilter([{"id": 117}, {"id": 118}]) == [{"id": 117}]


def test_get_epic_own_vs_foreign():
    args, _ = apply_scope(SCOPE, "taiga_get_epic", {"epic_id": 117}, BOARD)
    assert args["epic_id"] == 117
    with pytest.raises(ScopeError, match="not one of your epics"):
        apply_scope(SCOPE, "taiga_get_epic", {"epic_id": 118}, BOARD)


def test_list_stories_forced_to_epic():
    args, _ = apply_scope(SCOPE, "taiga_list_user_stories", {"project_id": 3}, BOARD)
    assert args == {"project_id": 2, "epic_id": 117}


def test_story_ownership_checked():
    apply_scope(SCOPE, "taiga_get_user_story", {"story_id": 10}, BOARD)
    with pytest.raises(ScopeError, match="not linked to your epic"):
        apply_scope(SCOPE, "taiga_get_user_story", {"story_id": 11}, BOARD)


def test_multi_epic_scope_sees_both_epics():
    args, _ = apply_scope(MULTI, "taiga_get_epic", {"epic_id": 118}, BOARD)
    assert args["epic_id"] == 118
    _, postfilter = apply_scope(MULTI, "taiga_list_epics", {}, BOARD)
    assert postfilter([{"id": 117}, {"id": 118}, {"id": 119}]) == [{"id": 117}, {"id": 118}]


def test_multi_epic_list_stories_filters_by_epic_membership():
    # Explicit in-scope epic passes through; out-of-scope epic is denied.
    args, _ = apply_scope(MULTI, "taiga_list_user_stories", {"epic_id": 118}, BOARD)
    assert args["epic_id"] == 118
    with pytest.raises(ScopeError):
        apply_scope(MULTI, "taiga_list_user_stories", {"epic_id": 119}, BOARD)
    # No epic given: post-filter keeps only stories under the scope's epics.
    _, postfilter = apply_scope(MULTI, "taiga_list_user_stories", {}, BOARD)
    data = [{"id": 1, "epic": {"id": 117}}, {"id": 2, "epic": {"id": 5}}, {"id": 3}]
    assert postfilter(data) == [{"id": 1, "epic": {"id": 117}}]


def test_multi_epic_create_requires_target_epic():
    with pytest.raises(ScopeError, match="Pass epic_id"):
        apply_scope(MULTI, "taiga_create_user_story", {"subject": "s"}, BOARD)
    args, _ = apply_scope(MULTI, "taiga_create_user_story", {"subject": "s", "epic_id": 118}, BOARD)
    assert args["epic_id"] == 118
    with pytest.raises(ScopeError, match="not one of your epics"):
        apply_scope(MULTI, "taiga_create_user_story", {"subject": "s", "epic_id": 119}, BOARD)


def test_multi_epic_create_issue_tags_chosen_epic():
    args, _ = apply_scope(MULTI, "taiga_create_issue", {"subject": "b", "epic_id": 118}, BOARD)
    assert "epic-118" in args["tags"] and "by-alex" in args["tags"]
    assert "epic_id" not in args  # not a real taiga_create_issue parameter
    with pytest.raises(ScopeError, match="Pass epic_id"):
        apply_scope(MULTI, "taiga_create_issue", {"subject": "b"}, BOARD)


def test_update_story_comment_signed():
    args, _ = apply_scope(
        SCOPE, "taiga_update_user_story", {"story_id": 10, "comment": "done"}, BOARD
    )
    assert args["comment"] == "**[alex]** done"


def test_create_story_forced_and_tagged():
    args, _ = apply_scope(
        SCOPE, "taiga_create_user_story", {"project_id": 9, "subject": "s"}, BOARD
    )
    assert args["project_id"] == 2
    assert args["epic_id"] == 117
    assert "by-alex" in args["tags"]


def test_bulk_create_tags_each_story():
    args, _ = apply_scope(
        SCOPE,
        "taiga_bulk_create_stories",
        {"stories": [{"subject": "a"}, {"subject": "b", "tags": ["x"]}]},
        BOARD,
    )
    assert all("by-alex" in s["tags"] for s in args["stories"])
    assert "x" in args["stories"][1]["tags"]


def test_issue_ownership_and_tagging():
    apply_scope(SCOPE, "taiga_get_issue", {"issue_id": 20}, BOARD)
    with pytest.raises(ScopeError, match="not one of your epics' bugs"):
        apply_scope(SCOPE, "taiga_get_issue", {"issue_id": 21}, BOARD)
    args, _ = apply_scope(SCOPE, "taiga_create_issue", {"subject": "bug"}, BOARD)
    assert "epic-117" in args["tags"] and "by-alex" in args["tags"]


def test_list_issues_postfilter_by_tag():
    _, postfilter = apply_scope(SCOPE, "taiga_list_issues", {}, BOARD)
    data = [{"id": 1, "tags": ["epic-117"]}, {"id": 2, "tags": ["epic-5"]}, {"id": 3}]
    assert postfilter(data) == [{"id": 1, "tags": ["epic-117"]}]


def test_add_comment_routes_by_type():
    args, _ = apply_scope(
        SCOPE, "taiga_add_comment",
        {"object_type": "epic", "object_id": 117, "comment": "hi"}, BOARD,
    )
    assert args["comment"] == "**[alex]** hi"
    with pytest.raises(ScopeError):
        apply_scope(
            SCOPE, "taiga_add_comment",
            {"object_type": "task", "object_id": 1, "comment": "hi"}, BOARD,
        )


def test_resolve_ref_limited_types():
    args, _ = apply_scope(
        SCOPE, "taiga_resolve_ref",
        {"project_id": 9, "ref": 5, "object_type": "userstory"}, BOARD,
    )
    assert args["project_id"] == 2
    with pytest.raises(ScopeError):
        apply_scope(
            SCOPE, "taiga_resolve_ref",
            {"project_id": 2, "ref": 5, "object_type": "task"}, BOARD,
        )


def test_display_name_flows_into_signature():
    named = Scope(label="alex", project_id=2, epic_ids=frozenset({117}), display="Alex")
    args, _ = apply_scope(
        named, "taiga_update_user_story", {"story_id": 10, "comment": "ok"}, BOARD
    )
    assert args["comment"] == "**[Alex]** ok"


def test_filter_result_only_touches_lists():
    postfilter = lambda data: [d for d in data if d.get("id") == 1]  # noqa: E731
    filtered = filter_result('[{"id":1},{"id":2}]', postfilter)
    assert json.loads(filtered) == [{"id": 1}]
    assert filter_result('{"error":"x"}', postfilter) == '{"error":"x"}'
    assert filter_result("not json", postfilter) == "not json"
    assert filter_result("[1]", None) == "[1]"
