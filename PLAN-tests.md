# aishell Test Suite Plan

## Current State

Existing tests cover LLM providers, MCP client/translator, env manager, shell enhancements, and CLI integration — all using `unittest.mock` and `click.testing.CliRunner`. There are **no tests** for:

- Web search (`aishell/search/web_search.py`) — uses Playwright
- File search (`aishell/search/file_search.py`) — uses macOS system tools
- Conversation export commands (`gemini.py`, `chatgpt.py`, `claude_export.py`) — use Playwright + Chrome CDP
- Browser helpers (`conversations/browser.py`) — Chrome lifecycle, `fetch_json()`
- Schema/manifest utilities (`schema.py`, `manifest.py`)
- Database + embeddings (`db.py`, `embeddings.py`)
- Conversation CLI (`conversations/cli.py`)

---

## Test Tiers

### Tier 1: Pure Unit Tests (no external dependencies)

Fast, deterministic, run everywhere. These should be written first.

| Module | What to Test |
|---|---|
| `schema.py` | `slugify()` edge cases (unicode, long strings, collisions), `generate_conv_id()` determinism, `convert_to_schema()` with various turn shapes, role normalization via `ROLE_MAP` |
| `manifest.py` | `load_manifest()` from file / missing file / corrupt JSON, `save_manifest()` round-trip, `already_exported()` with various directory states |
| `gemini._clean_turn_text()` | Prefix stripping for user/assistant roles |
| `gemini._convert_raw()` | Schema conversion from raw extraction data, empty turns, missing fields |
| `chatgpt` conversion helpers | ZIP parsing, raw JSON → schema conversion |
| `claude_export` conversion helpers | ZIP parsing, raw JSON → schema conversion |
| `browser.check_auth()` | URL matching against auth indicators |
| `env_manager.py` | .env parsing, reload, get/set (already partially covered) |
| `nl_converter.py` | Input parsing, provider selection logic |
| `display_results()` | Output formatting (capture Rich console output) |

### Tier 2: Async / Mocked-IO Tests

Use `pytest-asyncio`, `unittest.mock.AsyncMock`, and `pytest-mock`. Mock Playwright, network, and filesystem calls.

| Module | What to Test | What to Mock |
|---|---|---|
| `web_search.WebSearcher` | Browser lifecycle (`__aenter__`/`__aexit__`), `search_google()`, `search_duckduckgo()`, `search_hackernews()` | `async_playwright()`, `browser.new_context()`, `page.goto()`, `page.content()`, `page.wait_for_selector()`, `page.close()` |
| `browser.fetch_json()` | Success path, 401/403 auth error, 429 rate limit, generic HTTP error, JS exception | `page.evaluate()` return values |
| `browser.chrome_launch()` | Port already open, Chrome not running, Chrome running without debug port | `socket.connect_ex()`, `subprocess.Popen`, `subprocess.run` |
| `conversations/cli.py` | `load` and `search` commands | Database connection, embedding model |

### Tier 3: Playwright Integration Tests (the "Playwright tests")

These use **real Playwright browsers** but against **local mock servers** or **static HTML fixtures**, not live websites. This is the key design decision — you never hit Google/DuckDuckGo/Gemini in CI.

#### Architecture

```
tests/
├── playwright/
│   ├── conftest.py              # Shared fixtures: browser, page, local HTTP server
│   ├── fixtures/                # Static HTML files served by the mock server
│   │   ├── google_results.html
│   │   ├── duckduckgo_results.html
│   │   ├── hackernews_results.html
│   │   ├── gemini_app.html      # Sidebar + conversation page
│   │   ├── gemini_conv_1.html   # Individual conversation with web-components
│   │   ├── gemini_conv_2.html   # Individual conversation with data-message-id
│   │   └── chatgpt_api/         # Mock JSON API responses
│   │       ├── conversations.json
│   │       └── conversation_detail.json
│   ├── test_web_search.py
│   ├── test_gemini_pull.py
│   ├── test_chatgpt_pull.py
│   └── test_browser_helpers.py
```

#### `conftest.py` — Shared Fixtures

```python
import pytest
import asyncio
from aiohttp import web
from playwright.async_api import async_playwright

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def mock_server():
    """Start a local aiohttp server that serves HTML fixtures and mock APIs."""
    app = web.Application()

    # Static file routes for search result pages
    app.router.add_static('/fixtures/', path='tests/playwright/fixtures/')

    # Dynamic routes for mock APIs (ChatGPT, Claude)
    async def chatgpt_conversations(request):
        return web.json_response({...})  # paginated list

    async def chatgpt_conversation_detail(request):
        conv_id = request.match_info['id']
        return web.json_response({...})  # single conversation

    app.router.add_get('/backend-api/conversations', chatgpt_conversations)
    app.router.add_get('/backend-api/conversation/{id}', chatgpt_conversation_detail)

    runner = web.AppRunner(app)
    await runner.setup()
    site = await web.TCPSite(runner, 'localhost', 0)  # random port
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    yield f"http://localhost:{port}"
    await runner.cleanup()

@pytest.fixture
async def browser_context():
    """Provide a fresh Playwright browser context for each test."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        yield context
        await context.close()
        await browser.close()

@pytest.fixture
async def page(browser_context):
    page = await browser_context.new_page()
    yield page
    await page.close()
```

#### `test_web_search.py` — What Tests Look Like

```python
import pytest
from aishell.search.web_search import WebSearcher

@pytest.mark.asyncio
class TestGoogleSearch:
    async def test_parses_results_from_html(self, mock_server, page):
        """WebSearcher extracts title, URL, snippet from Google-shaped HTML."""
        # Navigate to our local fixture that mimics Google's result page structure
        await page.goto(f"{mock_server}/fixtures/google_results.html")

        # Instead of calling search_google() which hardcodes the URL,
        # we test the parsing logic by injecting the page content
        content = await page.content()
        # ... parse with BeautifulSoup, assert expected results

    async def test_search_google_end_to_end(self, mock_server, monkeypatch):
        """Full search_google() flow with URL redirected to local fixture."""
        # Monkeypatch the search URL to point at our mock server
        async with WebSearcher(headless=True) as searcher:
            # Override the URL construction within search_google
            original_goto = searcher.context.new_page

            # ... or more cleanly, refactor WebSearcher to accept a base_url

            results = await searcher.search_google("test query", limit=5)
            assert len(results) == 5
            assert all('title' in r and 'url' in r for r in results)

    async def test_handles_no_results(self, mock_server):
        """Returns empty list when no results found."""
        # Fixture: empty Google results page
        ...

    async def test_handles_timeout(self, mock_server, monkeypatch):
        """Returns empty list and prints error on timeout."""
        # Mock page.wait_for_selector to raise TimeoutError
        ...

@pytest.mark.asyncio
class TestDuckDuckGoSearch:
    async def test_parses_ddg_results(self, mock_server, page):
        """Extracts results from DuckDuckGo HTML structure."""
        ...

    async def test_handles_different_snippet_selectors(self, mock_server, page):
        """Falls back to alternative snippet selectors."""
        ...

@pytest.mark.asyncio
class TestHackerNewsSearch:
    async def test_parses_algolia_results(self, mock_server, page):
        """Extracts story titles and metadata from HN Algolia HTML."""
        ...
```

#### `test_gemini_pull.py` — What CDP/Export Tests Look Like

```python
import pytest

@pytest.mark.asyncio
class TestGeminiExtraction:
    async def test_enumerate_conversations(self, page, mock_server):
        """_enumerate_conversations() finds sidebar links."""
        await page.goto(f"{mock_server}/fixtures/gemini_app.html")
        from aishell.commands.gemini import _enumerate_conversations
        convos = _enumerate_conversations(page)
        assert len(convos) == 3  # fixture has 3 sidebar links
        assert all('source_id' in c for c in convos)

    async def test_extract_web_components_strategy(self, page, mock_server):
        """_extract_conversation() uses web-components strategy."""
        await page.goto(f"{mock_server}/fixtures/gemini_conv_1.html")
        from aishell.commands.gemini import _extract_conversation
        result = _extract_conversation(page)
        assert result['strategy'] == 'web-components'
        assert result['count'] > 0

    async def test_extract_data_message_id_strategy(self, page, mock_server):
        """Falls back to data-message-id strategy."""
        await page.goto(f"{mock_server}/fixtures/gemini_conv_2.html")
        from aishell.commands.gemini import _extract_conversation
        result = _extract_conversation(page)
        assert result['strategy'] == 'data-message-id'

    async def test_expand_sidebar(self, page, mock_server):
        """_expand_sidebar() clicks the menu button."""
        await page.goto(f"{mock_server}/fixtures/gemini_app.html")
        from aishell.commands.gemini import _expand_sidebar
        found = _expand_sidebar(page)
        assert found is True

    async def test_scroll_to_load_all(self, page, mock_server):
        """_scroll_to_load_all() scrolls until height stabilizes."""
        # Fixture with enough content to scroll
        ...
```

#### `test_browser_helpers.py` — Testing `fetch_json()`

```python
import pytest

@pytest.mark.asyncio
class TestFetchJson:
    async def test_success(self, page, mock_server):
        """fetch_json() returns parsed JSON on 200."""
        await page.goto(f"{mock_server}/fixtures/google_results.html")
        # The mock_server has /backend-api/conversations returning JSON
        from aishell.commands.conversations.browser import fetch_json
        data = fetch_json(page, f"{mock_server}/backend-api/conversations")
        assert isinstance(data, dict)

    async def test_auth_error_raises(self, page, mock_server):
        """fetch_json() raises RuntimeError on 401."""
        # Mock server route that returns 401
        ...

    async def test_rate_limit_raises(self, page, mock_server):
        """fetch_json() raises RuntimeError on 429."""
        ...
```

### Tier 4: CLI Integration Tests (Click CliRunner)

Extend the existing `test_integration.py` pattern to cover the new commands:

```python
class TestConversationExportCLI:
    def test_gemini_help(self):
        result = runner.invoke(main, ["gemini", "--help"])
        assert "login" in result.output
        assert "pull" in result.output

    def test_gemini_pull_dry_run(self, tmp_path, monkeypatch):
        """gemini pull --dry-run lists conversations without extracting."""
        # Mock Playwright, chrome_launch, etc.
        ...

    def test_chatgpt_import_zip(self, tmp_path):
        """chatgpt import processes a ZIP file."""
        # Create a minimal ZIP fixture
        ...

    def test_conversations_search_requires_query(self):
        result = runner.invoke(main, ["conversations", "search"])
        assert result.exit_code != 0
```

### Tier 5: Database Tests (optional, requires PostgreSQL)

```python
@pytest.mark.skipif(not PG_AVAILABLE, reason="PostgreSQL not configured")
class TestConversationDB:
    def test_load_conversations(self, pg_connection, tmp_conversations):
        ...
    def test_semantic_search(self, pg_connection, loaded_db):
        ...
```

---

## HTML Fixture Design (for Tier 3)

The fixtures are minimal HTML files that reproduce the **exact DOM structure** that the scrapers expect:

**`google_results.html`** — Must contain:
- `<div id="search">` wrapper
- `<div class="g">` result containers with `<h3>` titles, `<a>` links, `<div data-sncf="1">` snippets

**`duckduckgo_results.html`** — Must contain:
- `<div class="results">` wrapper
- `<article data-testid="result">` with `<h2>` titles, `<a data-testid="result-title-a">`, `<div data-result="snippet">`

**`hackernews_results.html`** — Must contain:
- `<div class="Story_container">` with `<div class="Story_title">`, `<div class="Story_meta">`

**`gemini_app.html`** — Must contain:
- Sidebar with `<a href="/app/{hex_id}">` links
- A `<button aria-label="menu">` for sidebar expansion

**`gemini_conv_1.html`** — Must contain:
- `<user-query>` and `<model-response>` custom elements with text content

**`gemini_conv_2.html`** — Must contain:
- `<div data-message-id="..." data-role="user|model">` elements

---

## Refactoring Suggestions (to improve testability)

1. **`WebSearcher` base URL injection**: Add an optional `base_url` parameter so tests can redirect searches to the mock server without monkeypatching. Alternatively, extract the URL-building into a method that tests can override.

2. **Extract `_parse_google_results(html) -> list`**: Separate the HTML parsing from the Playwright page interaction. This lets Tier 1 unit tests validate parsing with just a string, no browser needed.

3. **Extract `_parse_duckduckgo_results(html) -> list`** and **`_parse_hackernews_results(html) -> list`**: Same pattern.

4. **Make `fetch_json` async-compatible**: It currently uses sync Playwright. Consider offering an async variant, or at minimum make sure tests can call it with sync Playwright fixtures.

5. **Parameterize Chrome paths**: `CHROME_PATH` and `CHROME_USER_DATA_DIR` are hardcoded constants. Accept them as parameters or environment variables so tests don't depend on macOS Chrome being installed.

---

## Test Configuration

**`pytest.ini` or `pyproject.toml` section:**
```ini
[tool.pytest.ini_options]
markers = [
    "playwright: tests that require a Playwright browser",
    "database: tests that require PostgreSQL",
    "slow: tests that take >5s",
]
asyncio_mode = "auto"
```

**New dev dependencies:**
```
pytest-asyncio
pytest-mock
aiohttp          # for mock HTTP server in Playwright tests
pytest-playwright # optional, for managed browser fixtures
```

**CI marker filtering:**
```bash
# Fast CI (Tier 1 + 2 only, no browser)
pytest -m "not playwright and not database"

# Full CI (includes Playwright, needs chromium installed)
pytest

# Database tests (needs PG)
pytest -m database
```

---

## Execution Order

1. **Tier 1** first — pure unit tests for `schema.py`, `manifest.py`, helper functions. Fast wins, high coverage of data transformation logic.
2. **Tier 2** — mocked async tests for `WebSearcher`, `fetch_json`, `chrome_launch`. Validates the control flow without needing a browser.
3. **Refactoring** — extract parsing functions from `WebSearcher` methods to enable Tier 1 tests of HTML parsing.
4. **Tier 3** — build HTML fixtures and Playwright integration tests. Validates that JS `page.evaluate()` calls and DOM selectors actually work against realistic HTML.
5. **Tier 4** — CLI integration tests with CliRunner.
6. **Tier 5** — database tests (optional, only if PG is available in CI).
