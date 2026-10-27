import pytest

from taiga_delegate.scope.model import Scope, parse_scoped_tokens, sanitize_display


def test_parse_single():
    scopes = parse_scoped_tokens("alex:deadbeef:2:117")
    assert scopes == {"deadbeef": Scope(label="alex", project_id=2, epic_ids=frozenset({117}))}


def test_parse_multiple_and_whitespace():
    scopes = parse_scoped_tokens(" alex:t1:2:117 ; vendor:t2:3:99 ;")
    assert scopes["t1"].epic_ids == {117}
    assert scopes["t2"].project_id == 3


def test_parse_multi_epic_token():
    scopes = parse_scoped_tokens("alex:t1:2:117,118,120")
    assert scopes["t1"].epic_ids == {117, 118, 120}
    assert scopes["t1"].sole_epic_id is None
    assert scopes["t1"].epics_text == "epics 117, 118, 120"


def test_parse_empty():
    assert parse_scoped_tokens("") == {}
    assert parse_scoped_tokens(None) == {}


def test_parse_malformed_raises_without_leaking_token():
    with pytest.raises(ValueError) as exc:
        parse_scoped_tokens("alex:secret-token:2")  # missing epic ids
    assert "secret-token" not in str(exc.value)
    assert "alex" in str(exc.value)
    with pytest.raises(ValueError):
        parse_scoped_tokens("alex:secret-token:2:117,abc")  # non-numeric epic id


def test_who_prefers_display():
    scope = Scope(label="alex", project_id=2, epic_ids=frozenset({117}))
    assert scope.who == "alex"
    named = Scope(label="alex", project_id=2, epic_ids=frozenset({117}), display="Alex Smith")
    assert named.who == "Alex Smith"
    assert named.who_tag == "by-alex-smith"


def test_tags_and_sole_epic():
    single = Scope(label="x", project_id=1, epic_ids=frozenset({42}))
    assert single.tags == {"epic-42"}
    assert single.sole_epic_id == 42
    assert single.epics_text == "epic 42"
    multi = Scope(label="x", project_id=1, epic_ids=frozenset({42, 43}))
    assert multi.tags == {"epic-42", "epic-43"}
    assert multi.sole_epic_id is None


def test_sanitize_display_passes_normal_names():
    assert sanitize_display("Alex Smith") == "Alex Smith"
    assert sanitize_display("José") == "José"


def test_sanitize_display_strips_signature_markup():
    # A name like this could otherwise forge the **[name]** comment signature.
    assert sanitize_display("Alex]** approved by owner **[") == "Alex approved by owner"
    assert sanitize_display("`rm -rf`*") == "rm -rf"


def test_sanitize_display_drops_control_chars_and_caps_length():
    assert sanitize_display("Alex\r\nNew line\tx") == "Alex New line x"
    assert len(sanitize_display("x" * 500)) == 64
    assert sanitize_display("\x00\x1b") == ""
