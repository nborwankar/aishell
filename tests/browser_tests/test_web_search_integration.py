"""Tier 3: Playwright integration tests for web search HTML parsing.

These tests use a real browser against local HTML fixtures to validate
that BeautifulSoup selectors match the expected DOM structure.
"""

import pytest
from bs4 import BeautifulSoup

pytestmark = pytest.mark.playwright


class TestGoogleParsing:
    """Test Google search result parsing against the fixture HTML."""

    def test_finds_all_results(self, page, mock_server):
        page.goto(f"{mock_server}/google_results.html")
        content = page.content()
        soup = BeautifulSoup(content, "lxml")
        results = soup.find_all("div", class_="g")
        assert len(results) == 3

    def test_extracts_title(self, page, mock_server):
        page.goto(f"{mock_server}/google_results.html")
        content = page.content()
        soup = BeautifulSoup(content, "lxml")
        first = soup.find_all("div", class_="g")[0]
        title = first.find("h3").text
        assert title == "Python Documentation"

    def test_extracts_url(self, page, mock_server):
        page.goto(f"{mock_server}/google_results.html")
        content = page.content()
        soup = BeautifulSoup(content, "lxml")
        first = soup.find_all("div", class_="g")[0]
        url = first.find("a").get("href")
        assert url == "https://docs.python.org/"

    def test_extracts_snippet(self, page, mock_server):
        page.goto(f"{mock_server}/google_results.html")
        content = page.content()
        soup = BeautifulSoup(content, "lxml")
        first = soup.find_all("div", class_="g")[0]
        snippet = first.find("div", attrs={"data-sncf": "1"})
        assert snippet is not None
        assert "Python documentation" in snippet.text

    def test_empty_results_page(self, page, mock_server):
        page.goto(f"{mock_server}/google_empty.html")
        content = page.content()
        soup = BeautifulSoup(content, "lxml")
        results = soup.find_all("div", class_="g")
        assert len(results) == 0


class TestDuckDuckGoParsing:
    """Test DuckDuckGo result parsing against the fixture HTML."""

    def test_finds_all_results(self, page, mock_server):
        page.goto(f"{mock_server}/duckduckgo_results.html")
        content = page.content()
        soup = BeautifulSoup(content, "lxml")
        results = soup.find_all("article", attrs={"data-testid": "result"})
        assert len(results) == 2

    def test_extracts_title_and_url(self, page, mock_server):
        page.goto(f"{mock_server}/duckduckgo_results.html")
        content = page.content()
        soup = BeautifulSoup(content, "lxml")
        first = soup.find_all("article", attrs={"data-testid": "result"})[0]

        title = first.find("h2").text
        assert title == "DuckDuckGo Privacy Browser"

        link = first.find("a", attrs={"data-testid": "result-title-a"})
        assert link.get("href") == "https://duckduckgo.com/app"

    def test_extracts_snippet(self, page, mock_server):
        page.goto(f"{mock_server}/duckduckgo_results.html")
        content = page.content()
        soup = BeautifulSoup(content, "lxml")
        first = soup.find_all("article", attrs={"data-testid": "result"})[0]
        snippet = first.find("div", attrs={"data-result": "snippet"})
        assert "privacy" in snippet.text.lower()


class TestHackerNewsParsing:
    """Test Hacker News Algolia parsing against the fixture HTML."""

    def test_finds_all_stories(self, page, mock_server):
        page.goto(f"{mock_server}/hackernews_results.html")
        content = page.content()
        soup = BeautifulSoup(content, "html.parser")
        stories = soup.find_all("div", class_="Story_container")
        assert len(stories) == 3

    def test_extracts_title_and_url(self, page, mock_server):
        page.goto(f"{mock_server}/hackernews_results.html")
        content = page.content()
        soup = BeautifulSoup(content, "html.parser")
        first = soup.find_all("div", class_="Story_container")[0]

        title_div = first.find("div", class_="Story_title")
        link = title_div.find("a")
        assert link.text == "Show HN: My Cool Project"
        assert "ycombinator" in link.get("href")

    def test_extracts_meta(self, page, mock_server):
        page.goto(f"{mock_server}/hackernews_results.html")
        content = page.content()
        soup = BeautifulSoup(content, "html.parser")
        first = soup.find_all("div", class_="Story_container")[0]
        meta = first.find("div", class_="Story_meta")
        assert "120 points" in meta.text
