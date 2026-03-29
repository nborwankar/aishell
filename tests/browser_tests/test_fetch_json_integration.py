"""Tier 3: Playwright integration tests for fetch_json() against a local mock server.

Uses a local HTTP server with JSON API endpoints to test that fetch_json's
JS evaluation actually performs the fetch and handles responses correctly.
"""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest

from aishell.commands.conversations.browser import fetch_json

pytestmark = pytest.mark.playwright


class MockAPIHandler(BaseHTTPRequestHandler):
    """Mock API server returning various HTTP responses."""

    def do_GET(self):
        if self.path == "/api/success":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"items": [1, 2, 3]}).encode())

        elif self.path == "/api/auth-fail":
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"error": "unauthorized"}')

        elif self.path == "/api/rate-limit":
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"error": "rate limited"}')

        elif self.path == "/api/server-error":
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"error": "internal server error"}')

        elif self.path == "/api/empty":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"[]")

        elif self.path == "/api/nested":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"conversations": [{"id": "c1"}, {"id": "c2"}], "total": 2}
                ).encode()
            )

        else:
            self.send_response(404)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"not found")

    def log_message(self, format, *args):
        pass


@pytest.fixture(scope="module")
def api_server():
    """Start a mock API server."""
    server = HTTPServer(("localhost", 0), MockAPIHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{port}"
    server.shutdown()


class TestFetchJsonIntegration:
    def test_success(self, page, api_server):
        # Navigate to the API server origin so fetch has same-origin cookies
        page.goto(f"{api_server}/api/success")
        result = fetch_json(page, f"{api_server}/api/success")
        assert result == {"items": [1, 2, 3]}

    def test_empty_array(self, page, api_server):
        page.goto(f"{api_server}/api/empty")
        result = fetch_json(page, f"{api_server}/api/empty")
        assert result == []

    def test_nested_response(self, page, api_server):
        page.goto(f"{api_server}/api/nested")
        result = fetch_json(page, f"{api_server}/api/nested")
        assert result["total"] == 2
        assert len(result["conversations"]) == 2

    def test_auth_failure_raises(self, page, api_server):
        page.goto(f"{api_server}/api/success")
        with pytest.raises(RuntimeError, match="Authentication failed"):
            fetch_json(page, f"{api_server}/api/auth-fail")

    def test_rate_limit_raises(self, page, api_server):
        page.goto(f"{api_server}/api/success")
        with pytest.raises(RuntimeError, match="Rate limited"):
            fetch_json(page, f"{api_server}/api/rate-limit")

    def test_server_error_raises(self, page, api_server):
        page.goto(f"{api_server}/api/success")
        with pytest.raises(RuntimeError, match="API error: 500"):
            fetch_json(page, f"{api_server}/api/server-error")
