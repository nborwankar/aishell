"""Tier 2: Async/mocked tests for WebSearcher."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aishell.search.web_search import WebSearcher, display_results


# ── WebSearcher lifecycle ───────────────────────────────────────────


class TestWebSearcherLifecycle:
    @pytest.mark.asyncio
    @patch("aishell.search.web_search.async_playwright")
    async def test_aenter_launches_browser(self, mock_pw):
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.start = AsyncMock(return_value=mock_p)

        searcher = WebSearcher(headless=True)
        result = await searcher.__aenter__()

        assert result is searcher
        mock_p.chromium.launch.assert_called_once_with(headless=True)

    @pytest.mark.asyncio
    @patch("aishell.search.web_search.async_playwright")
    async def test_aexit_closes_resources(self, mock_pw):
        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.start = AsyncMock(return_value=mock_p)

        searcher = WebSearcher(headless=True)
        await searcher.__aenter__()
        await searcher.__aexit__(None, None, None)

        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_p.stop.assert_called_once()


# ── search_google ───────────────────────────────────────────────────


class TestSearchGoogle:
    @pytest.mark.asyncio
    @patch("aishell.search.web_search.async_playwright")
    async def test_returns_parsed_results(self, mock_pw):
        html = """
        <html><body>
        <div id="search">
            <div class="g">
                <h3>Result Title</h3>
                <a href="https://example.com">Link</a>
                <div data-sncf="1">A snippet here</div>
            </div>
        </div>
        </body></html>
        """
        mock_page = AsyncMock()
        mock_page.content.return_value = html
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page

        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.start = AsyncMock(return_value=mock_p)

        async with WebSearcher(headless=True) as searcher:
            results = await searcher.search_google("test", limit=5)

        assert len(results) == 1
        assert results[0]["title"] == "Result Title"
        assert results[0]["url"] == "https://example.com"
        assert results[0]["snippet"] == "A snippet here"

    @pytest.mark.asyncio
    @patch("aishell.search.web_search.async_playwright")
    async def test_handles_empty_results(self, mock_pw):
        html = '<html><body><div id="search"></div></body></html>'
        mock_page = AsyncMock()
        mock_page.content.return_value = html
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page

        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.start = AsyncMock(return_value=mock_p)

        async with WebSearcher(headless=True) as searcher:
            results = await searcher.search_google("test")

        assert results == []

    @pytest.mark.asyncio
    @patch("aishell.search.web_search.async_playwright")
    async def test_handles_timeout(self, mock_pw):
        mock_page = AsyncMock()
        mock_page.goto.side_effect = Exception("Timeout")
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page

        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.start = AsyncMock(return_value=mock_p)

        async with WebSearcher(headless=True) as searcher:
            results = await searcher.search_google("test")

        assert results == []


# ── search_duckduckgo ───────────────────────────────────────────────


class TestSearchDuckDuckGo:
    @pytest.mark.asyncio
    @patch("aishell.search.web_search.async_playwright")
    async def test_parses_ddg_results(self, mock_pw):
        html = """
        <html><body>
        <div class="results">
            <article data-testid="result">
                <h2>DDG Result</h2>
                <a data-testid="result-title-a" href="https://ddg.example.com">Link</a>
                <div data-result="snippet">DDG snippet text</div>
            </article>
        </div>
        </body></html>
        """
        mock_page = AsyncMock()
        mock_page.content.return_value = html
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page

        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.start = AsyncMock(return_value=mock_p)

        async with WebSearcher(headless=True) as searcher:
            results = await searcher.search_duckduckgo("test", limit=5)

        assert len(results) == 1
        assert results[0]["title"] == "DDG Result"
        assert results[0]["url"] == "https://ddg.example.com"


# ── search_hackernews ───────────────────────────────────────────────


class TestSearchHackerNews:
    @pytest.mark.asyncio
    @patch("aishell.search.web_search.async_playwright")
    async def test_parses_hn_results(self, mock_pw):
        html = """
        <html><body>
        <div class="Story_container">
            <div class="Story_title"><a href="https://hn.example.com">HN Story</a></div>
            <div class="Story_meta">42 points by user 3 hours ago</div>
        </div>
        </body></html>
        """
        mock_page = AsyncMock()
        mock_page.content.return_value = html
        mock_page.close = AsyncMock()

        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page

        mock_p = AsyncMock()
        mock_browser = AsyncMock()
        mock_p.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_pw.return_value.start = AsyncMock(return_value=mock_p)

        async with WebSearcher(headless=True) as searcher:
            results = await searcher.search_hackernews("test", limit=5)

        assert len(results) == 1
        assert results[0]["title"] == "HN Story"
        assert results[0]["url"] == "https://hn.example.com"


# ── display_results ─────────────────────────────────────────────────


class TestDisplayResults:
    def test_empty_results(self, capsys):
        display_results([], "test query")
        # Should not raise, just prints no-results message

    def test_with_results(self, capsys):
        results = [
            {"title": "Test", "url": "https://test.com", "snippet": "A snippet"},
        ]
        display_results(results, "query")
        # Should not raise
