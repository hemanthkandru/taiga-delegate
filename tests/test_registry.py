"""The tool registry must stay coherent as domains are added."""

from taiga_delegate.scope.policy import _RULES, ALLOWED_TOOLS
from taiga_delegate.taiga.tools import _HANDLERS, TOOL_DEFINITIONS


def test_every_definition_has_a_handler_and_vice_versa():
    defined = {t["name"] for t in TOOL_DEFINITIONS}
    assert defined == set(_HANDLERS)


def test_no_duplicate_tool_names():
    names = [t["name"] for t in TOOL_DEFINITIONS]
    assert len(names) == len(set(names))


def test_definitions_are_well_formed():
    for tool in TOOL_DEFINITIONS:
        assert tool["description"], tool["name"]
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        for required in schema.get("required", []):
            assert required in schema["properties"], (tool["name"], required)


def test_scope_allowlist_names_real_tools():
    defined = {t["name"] for t in TOOL_DEFINITIONS}
    assert ALLOWED_TOOLS <= defined


def test_every_allowed_tool_has_a_scope_rule():
    assert set(_RULES) == set(ALLOWED_TOOLS)


def test_scoped_sessions_cannot_delete_anything():
    assert not any("delete" in name for name in ALLOWED_TOOLS)
