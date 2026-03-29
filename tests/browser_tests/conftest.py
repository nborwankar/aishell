"""Shared fixtures for Playwright integration tests.

Provides a local HTTP server serving HTML fixtures, plus browser/page fixtures.
"""

import asyncio
import os
import threading

import pytest
from http.server import HTTPServer, SimpleHTTPRequestHandler

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


class FixtureHandler(SimpleHTTPRequestHandler):
    """Serve HTML fixtures from the fixtures/ directory."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FIXTURES_DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # Suppress request logging in test output


@pytest.fixture(scope="session")
def mock_server():
    """Start a local HTTP server serving HTML fixture files.

    Yields the base URL (e.g. 'http://localhost:PORT').
    """
    server = HTTPServer(("localhost", 0), FixtureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://localhost:{port}"
    server.shutdown()


@pytest.fixture(scope="session")
def browser_sync():
    """Provide a sync Playwright browser for the test session."""
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    yield browser
    browser.close()
    pw.stop()


@pytest.fixture
def page(browser_sync):
    """Provide a fresh page for each test."""
    page = browser_sync.new_page()
    yield page
    page.close()
