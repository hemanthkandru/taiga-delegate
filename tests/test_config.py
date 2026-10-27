import pytest

from taiga_delegate.config import Settings


def test_from_env_minimal_token():
    s = Settings.from_env({"TAIGA_URL": "https://api.taiga.io", "TAIGA_TOKEN": "abc"})
    assert s.taiga_url == "https://api.taiga.io"
    assert s.transport == "stdio"


def test_trailing_slash_stripped_from_url():
    s = Settings.from_env({"TAIGA_URL": "https://taiga.example.com/", "TAIGA_TOKEN": "abc"})
    assert s.taiga_url == "https://taiga.example.com"


def test_from_env_username_password():
    s = Settings.from_env({
        "TAIGA_URL": "https://t.example.com",
        "TAIGA_USERNAME": "agent",
        "TAIGA_PASSWORD": "pw",
    })
    assert s.taiga_username == "agent"


def test_missing_credentials_rejected():
    with pytest.raises(ValueError, match="credentials missing"):
        Settings.from_env({"TAIGA_URL": "https://t.example.com"})


def test_http_requires_auth_token():
    with pytest.raises(ValueError, match="MCP_AUTH_TOKEN"):
        Settings.from_env({
            "TAIGA_URL": "https://t.example.com",
            "TAIGA_TOKEN": "abc",
            "MCP_TRANSPORT": "http",
        })


def test_http_with_auth_token_and_scoped():
    s = Settings.from_env({
        "TAIGA_URL": "https://t.example.com",
        "TAIGA_TOKEN": "abc",
        "MCP_TRANSPORT": "http",
        "MCP_AUTH_TOKEN": "owner-token",
        "MCP_SCOPED_TOKENS": "alex:tok1:2:117",
        "MCP_PORT": "9001",
    })
    assert s.http_port == 9001
    assert s.scoped_tokens["tok1"].label == "alex"


def test_bad_transport_rejected():
    with pytest.raises(ValueError, match="MCP_TRANSPORT"):
        Settings.from_env({
            "TAIGA_URL": "https://t.example.com",
            "TAIGA_TOKEN": "abc",
            "MCP_TRANSPORT": "websocket",
        })
