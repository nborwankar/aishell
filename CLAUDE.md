# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**aishell** is an intelligent command line tool built in Python that provides web search, intelligent shell capabilities, file system search using macOS native tools, and conversation export/search from LLM providers (Gemini).

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
│   └── gemini.py        # Gemini export: login, pull, load, search (~900 lines)
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

~/.aishell/gemini/       # Gemini export data (created at runtime)
├── raw/                 # Raw DOM extraction JSONs
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

### Gemini Export (2026-02)
1. **Login**: Launch Chrome with debug profile for Google sign-in
2. **Pull**: Batch-extract conversations via Playwright + CDP with sidebar expansion
3. **Load**: Auto-provision PostgreSQL + pgvector, embed with nomic-embed-text-v1.5 (768-dim)
4. **Search**: Semantic search across all turns via cosine similarity
5. **Scan Export**: `pull --dry-run` saves scan.json for sizing assessment

## Important Implementation Notes

- **macOS Focused**: File search optimized for macOS using `mdfind`, `find`, `grep`, `mdls`
- **Async Architecture**: Web search and LLM calls use async/await with proper concurrency
- **Rich UI**: All output uses Rich library for formatting and tables
- **Pluggable Architecture**: Support for multiple LLM providers and NL converters
- **Environment Configuration**: .env file loading on startup with reload capability
- **Transcript Logging**: All LLM interactions logged to LLMTranscript.md with errors in LLMErrors.md
- **Native Tools**: Leverages system tools rather than pure Python for performance

### Gemini Export Notes
- **Chrome**: Requires `~/chromeuserdata` profile dir and port 9222 for CDP
- **Wait Strategy**: Uses `domcontentloaded` (not `networkidle` — Gemini keeps WebSocket open)
- **Sidebar**: Auto-expands collapsed sidebar via "Main menu" button click before enumeration
- **DOM Extraction**: 4 strategies (web-components → conversation-turn → data-message-id → fallback)
- **Text Cleanup**: Strips "You said\n" / "Gemini said\n" prefixes from scraped content
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