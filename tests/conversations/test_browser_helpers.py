"""Tier 1 + Tier 2: Tests for browser.py helpers — check_auth, fetch_json, chrome_launch."""

import socket
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from aishell.commands.conversations.browser import (
    check_auth,
    fetch_json,
    is_debug_port_open,
)


# ── check_auth (Tier 1, pure logic) ────────────────────────────────


class TestCheckAuth:
    def test_authenticated_url(self):
        page = MagicMock()
        page.url = "https://chatgpt.com/chat"
        assert check_auth(page, ["auth0.com", "login.openai.com"]) is True

    def test_redirected_to_auth(self):
        page = MagicMock()
        page.url = "https://auth0.com/login?redirect=chatgpt.com"
        assert check_auth(page, ["auth0.com", "login.openai.com"]) is False

    def test_case_insensitive(self):
        page = MagicMock()
        page.url = "https://AUTH0.COM/login"
        assert check_auth(page, ["auth0.com"]) is False

    def test_empty_indicators(self):
        page = MagicMock()
        page.url = "https://anything.com"
        assert check_auth(page, []) is True

    def test_multiple_indicators(self):
        page = MagicMock()
        page.url = "https://example.com/oauth/callback"
        assert check_auth(page, ["login", "/auth/", "/oauth/"]) is False


# ── fetch_json (Tier 2, mocked page.evaluate) ──────────────────────


class TestFetchJson:
    def test_success_returns_data(self):
        page = MagicMock()
        page.evaluate.return_value = {
            "__error": False,
            "data": {"items": [1, 2, 3]},
        }
        result = fetch_json(page, "https://api.example.com/data")
        assert result == {"items": [1, 2, 3]}

    def test_401_raises_auth_error(self):
        page = MagicMock()
        page.evaluate.return_value = {
            "__error": True,
            "status": 401,
            "statusText": "Unauthorized",
            "body": "",
        }
        with pytest.raises(RuntimeError, match="Authentication failed"):
            fetch_json(page, "https://api.example.com/data")

    def test_403_raises_auth_error(self):
        page = MagicMock()
        page.evaluate.return_value = {
            "__error": True,
            "status": 403,
            "statusText": "Forbidden",
            "body": "",
        }
        with pytest.raises(RuntimeError, match="Authentication failed"):
            fetch_json(page, "https://api.example.com/data")

    def test_429_raises_rate_limit(self):
        page = MagicMock()
        page.evaluate.return_value = {
            "__error": True,
            "status": 429,
            "statusText": "Too Many Requests",
            "body": "",
        }
        with pytest.raises(RuntimeError, match="Rate limited"):
            fetch_json(page, "https://api.example.com/data")

    def test_500_raises_generic_error(self):
        page = MagicMock()
        page.evaluate.return_value = {
            "__error": True,
            "status": 500,
            "statusText": "Internal Server Error",
            "body": "something broke",
        }
        with pytest.raises(RuntimeError, match="API error: 500"):
            fetch_json(page, "https://api.example.com/data")

    def test_js_exception_raises(self):
        page = MagicMock()
        page.evaluate.return_value = {
            "__error": True,
            "status": 0,
            "statusText": "TypeError: failed to fetch",
            "body": "",
        }
        with pytest.raises(RuntimeError, match="API error: 0"):
            fetch_json(page, "https://api.example.com/data")

    def test_passes_headers(self):
        page = MagicMock()
        page.evaluate.return_value = {"__error": False, "data": {}}
        fetch_json(
            page,
            "https://api.example.com/data",
            headers={"Authorization": "Bearer token123"},
        )
        call_args = page.evaluate.call_args[0]
        assert "token123" in str(call_args)


# ── is_debug_port_open (Tier 2, mocked socket) ─────────────────────


class TestIsDebugPortOpen:
    @patch("aishell.commands.conversations.browser.socket.socket")
    def test_port_open(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value.__enter__ = MagicMock(return_value=mock_sock)
        mock_socket_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_sock.connect_ex.return_value = 0

        assert is_debug_port_open(9222) is True

    @patch("aishell.commands.conversations.browser.socket.socket")
    def test_port_closed(self, mock_socket_class):
        mock_sock = MagicMock()
        mock_socket_class.return_value.__enter__ = MagicMock(return_value=mock_sock)
        mock_socket_class.return_value.__exit__ = MagicMock(return_value=False)
        mock_sock.connect_ex.return_value = 1

        assert is_debug_port_open(9222) is False
