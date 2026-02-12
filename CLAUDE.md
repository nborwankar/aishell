# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**aishell** is an intelligent command line tool built in Python that provides web search, intelligent shell capabilities, file system search using macOS native tools, and conversation export/search from LLM providers (Gemini, ChatGPT, Claude).

## Development Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -e .
python -m playwright install  # For web search

# Configuration
cp .env.example .env  # Copy and configure environment variables
# Edit .env with your API keys and settings

# Testing
pytest

# Code formatting
black aishell/
flake8 aishell/

# Run the tool
aishell --help
```

## Architecture & Structure

```
aishell/
├── __init__.py           # Package metadata
├── cli.py               # Main CLI entry point with Click commands
├── commands/            # Command group modules
│   ├── __init__.py
│   ├── gemini.py        # Gemini: login, pull, import (DOM scraping)
│   ├── chatgpt.py       # ChatGPT: login, pull, import (API + ZIP)
│   ├── claude_export.py # Claude: login, pull, import (API + ZIP)
│   └── conversations/   # Shared export infrastructure
│       ├── __init__.py
│       ├── browser.py   # Chrome/CDP helpers, fetch_json, chrome_login
│       ├── schema.py    # slugify, ROLE_MAP, convert_to_schema
│       ├── manifest.py  # load/save manifest, already_exported
│       ├── db.py        # PostgreSQL + pgvector setup
│       ├── embeddings.py # nomic-embed-text-v1.5 wrapper
│       └── cli.py       # conversations load + search commands
├── search/              # Search functionality
│   ├── __init__.py
│   ├── web_search.py    # Playwright-based web search (Google, DuckDuckGo)
│   └── file_search.py   # macOS native file search (Spotlight, find)
├── shell/               # Intelligent shell
│   ├── __init__.py
│   ├── intelligent_shell.py  # Main shell with history, aliases, git awareness
│   └── nl_converter.py  # Natural language to command conversion
└── utils/               # Utility functions
    ├── __init__.py
    ├── transcript.py    # LLM interaction logging
    └── env_manager.py   # Environment variable management

config/                  # Configuration templates
scripts/                 # Helper scripts
docs/                    # Design docs (JSONB_PLAN.md, etc.)

~/.aishell/{gemini,chatgpt,claude}/  # Per-provider data (created at runtime)
├── raw/                 # Raw API/DOM extraction JSONs
├── conversations/       # Schema-compliant JSONs + manifest.json
└── scan.json            # Latest dry-run scan results
```

## Key Features Implemented

### Phase 1
1. **Web Search**: Playwright-based search with Google/DuckDuckGo backends
2. **Intelligent Shell**: Enhanced shell with NL conversion, aliases, history
3. **File Search**: macOS Spotlight and BSD find integration
4. **Natural Language**: Convert NL to commands using Claude API or Ollama

### Phase 2
1. **LLM Integration**: Support for Claude, OpenAI, Gemini, and Ollama providers
2. **Multi-LLM Queries**: Collate responses from multiple providers simultaneously
3. **MCP Support**: Interact with Model Context Protocol servers
4. **Shell Commands**: Built-in LLM/MCP commands within interactive shell
5. **Environment Management**: .env file loading and management with `env` command
6. **Transcript Logging**: Persistent logging of all LLM interactions

### Multi-Provider Conversation Export (2026-02)
All three providers have a consistent `login` / `pull` / `import` interface:
```bash
aishell {gemini,chatgpt,claude} login       # Browser sign-in via Chrome CDP
aishell {gemini,chatgpt,claude} pull        # Download conversations (browser API)
aishell {gemini,chatgpt,claude} import      # Re-process from local files
aishell conversations load                   # Load all providers into PostgreSQL
aishell conversations search "query"         # Semantic search across all providers
```

**Approach**: ChatGPT and Claude use `fetch_json()` (page.evaluate + fetch with inherited cookies) to call internal APIs. Gemini uses DOM scraping. All produce the same schema.

**Scale**: 1,764 conversations pulled (Gemini 33, ChatGPT 811, Claude 920), zero failures.

**Next**: JSONB migration to unify storage in PostgreSQL (see `docs/JSONB_PLAN.md`).

## Important Implementation Notes

- **macOS Focused**: File search optimized for macOS using `mdfind`, `find`, `grep`, `mdls`
- **Async Architecture**: Web search and LLM calls use async/await with proper concurrency
- **Rich UI**: All output uses Rich library for formatting and tables
- **Pluggable Architecture**: Support for multiple LLM providers and NL converters
- **Environment Configuration**: .env file loading on startup with reload capability
- **Transcript Logging**: All LLM interactions logged to LLMTranscript.md with errors in LLMErrors.md
- **Native Tools**: Leverages system tools rather than pure Python for performance

### Conversation Export Notes
- **Chrome**: Requires `~/chromeuserdata` profile dir and port 9222 for CDP
- **Shared browser.py**: Chrome lifecycle, `fetch_json()`, `chrome_login()`, `check_auth()`
- **ChatGPT auth**: Requires Bearer token from `/api/auth/session` (cookies alone insufficient)
- **ChatGPT API**: `/backend-api/conversations` (paginated) + `/backend-api/conversation/{id}`
- **Claude API**: `/api/organizations` (org_id) + `/api/organizations/{org_id}/chat_conversations`
- **Gemini**: DOM scraping with 4 strategies (web-components → conversation-turn → data-message-id → fallback)
- **Wait Strategy**: Uses `domcontentloaded` (not `networkidle` — Gemini keeps WebSocket open)
- **Slug Collisions**: Duplicate titles get source_id[:8] suffix appended
- **Embedding Prefixes**: nomic model requires `search_document:` for storage, `search_query:` for queries
- **Database**: PostgreSQL `conversation_export` with pgvector HNSW index, auto-provisioned by `load`

## Development Workflow

- Use `git commit` frequently, especially after completing features
- Update `DONE.md` with detailed progress logs
- Update `TODO.md` to track completion status
- Test commands manually before committing

## Dependencies

- **Core**: click, rich, requests
- **Web**: playwright, beautifulsoup4, lxml
- **NL (Optional)**: anthropic, requests (for Ollama)
- **Gemini Export**: psycopg2-binary, sentence-transformers
- **Dev**: pytest, black, flake8, mypy