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

## Project Directory Structure

```
aishell/                          # Project root
├── CLAUDE.md                     # Project instructions (this file)
├── DONE.md                       # Completed work log
├── TODO.md                       # Ongoing task list
├── NEXT_SESSION.md               # Session handoff notes
├── README.md                     # Project documentation
├── CHANGELOG.md                  # Release history
├── LICENSE                       # License
├── requirements.txt              # Dependencies
├── setup.py                      # Package config
│
├── aishell/                      # Source code
│   ├── __init__.py               # Package metadata
│   ├── cli.py                    # Main CLI entry point with Click commands
│   ├── commands/                 # Command plugins (auto-discovered)
│   │   ├── __init__.py           # discover_commands() + skill registry
│   │   ├── gemini.py             # Gemini: login, pull, import
│   │   ├── chatgpt.py            # ChatGPT: login, pull, import, reimport
│   │   ├── claude_export.py      # Claude: login, pull, import
│   │   ├── webscraping/          # LLM-assisted web scraping
│   │   │   ├── cli.py            # Click group: navigate, configs
│   │   │   ├── navigator.py      # Playwright navigation engine
│   │   │   ├── llm_navigator.py  # LLM task-to-action translation
│   │   │   ├── actions.py        # Action type definitions
│   │   │   ├── extractors.py     # Data extraction utilities
│   │   │   ├── config.py         # YAML config management
│   │   │   └── examples/         # Example YAML configs (gitignored)
│   │   └── conversations/        # Shared export infrastructure
│   │       ├── browser.py        # Chrome/CDP helpers, fetch_json
│   │       ├── schema.py         # slugify, ROLE_MAP, convert_to_schema
│   │       ├── manifest.py       # load/save manifest, already_exported
│   │       ├── db.py             # PostgreSQL + pgvector setup + queries
│   │       ├── embeddings.py     # nomic-embed-text-v1.5 wrapper
│   │       ├── cli.py            # conversations load, browse, search
│   │       └── tui.py            # Textual TUI conversation browser
│   ├── search/                   # Search functionality
│   │   ├── web_search.py         # Playwright-based (Google, DuckDuckGo)
│   │   └── file_search.py        # macOS native (Spotlight, find)
│   ├── shell/                    # Intelligent shell
│   │   ├── intelligent_shell.py  # History, aliases, git awareness
│   │   └── nl_converter.py       # Natural language to command
│   └── utils/                    # Utility functions
│       ├── transcript.py         # LLM interaction logging → outputs/
│       └── env_manager.py        # Environment variable management
│
├── tests/                        # Test suite (pytest)
├── scripts/                      # Helper scripts (quick_test.py)
├── config/                       # Configuration templates
├── docs/                         # All documentation
│   ├── guides/                   # User-facing tutorials and guides
│   │   ├── TUTORIAL.md           # User tutorial
│   │   ├── QUICKSTART.md         # Quick start guide
│   │   ├── CONVAIX_GUIDE.md      # ConvAIx getting started
│   │   └── EXAMPLE_SEARCH.md     # Search examples
│   ├── plans/                    # Implementation plans
│   │   ├── SKILLS_PLAN.md        # Skills extension design
│   │   ├── JSONB_PLAN.md         # Database schema evolution
│   │   ├── PARAGRAPH_CHUNKING_PLAN.md
│   │   └── ...
│   ├── beads/                    # Beads task tracker reference
│   │   ├── BEADS_PRACTICAL_REFERENCE.md
│   │   └── ...
│   ├── dev/                      # Developer reference
│   │   ├── DEVELOPMENT_NOTES.md  # Dev reference
│   │   ├── TESTING_GUIDE.md      # Test reference
│   │   ├── MLX_BUG_FIX.md       # MLX SEQ_LENS monkey-patch
│   │   └── VERSIONING.md        # Version policy
│   └── archive/                  # Historical / stale docs
├── outputs/                      # Generated artifacts (gitignored)
│   ├── LLMTranscript.md          # Runtime LLM interaction logs
│   ├── LLMErrors.md              # Runtime LLM error logs
│   └── ...                       # Search results, test outputs
│
└── ~/.aishell/{gemini,chatgpt,claude}/  # Per-provider data (runtime)
    ├── raw/                      # Raw API/DOM extraction JSONs
    ├── conversations/            # Schema-compliant JSONs + manifest.json
    └── scan.json                 # Latest dry-run scan results
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
aisearch "query"                             # Hybrid search (semantic + keyword)
aisearch "flatoon" -s gemini -l 5            # With source filter and limit
aisearch "flatoon" -c                        # Conversation-level search with hit counts
aishell conversations browse                 # Interactive TUI browser
aishell conversations browse -s gemini       # TUI pre-filtered by source
```

**Hybrid Search**: Combines semantic similarity (nomic-embed-text-v1.5) with keyword matching (ILIKE on `chunk_text` and `title`). Keyword fallback catches novel terms, acronyms, and coined words that embeddings miss. Results show a `Match` column: `sem`, `kw`, or `both`.

**Shortcut**: `aisearch` is a top-level CLI command — equivalent to `aishell conversations search` but faster to type. Flags: `-l/--limit`, `-s/--source [gemini|chatgpt|claude]`, `-c/--conversations`, `--db`.

**TUI Browser**: Two-panel Textual app — conversation list (left) + turn viewer (right). Keybindings: `/` search, `1`/`2`/`3`/`0` source filter, `q` quit.

### Plugin Architecture (2026-02)
Commands are auto-discovered via module scanning — drop a `.py` file (or package with `cli.py`) into `aishell/commands/` and it registers automatically. Each module MAY export a `SKILL` dict with description, capabilities, examples, and agent-callable tool definitions. The registry is internal (`list_skills()`, `get_skill()`) — not user-facing. See `docs/plans/SKILLS_PLAN.md`.

**Approach**: ChatGPT and Claude use `fetch_json()` (page.evaluate + fetch with inherited cookies) to call internal APIs. Gemini uses DOM scraping. All produce the same schema.

**Scale**: 1,764 conversations pulled (Gemini 33, ChatGPT 811, Claude 920), zero failures.

### Task Planner Skill (2026-03)
Managed task layer that abstracts beads infrastructure:
- `/plan "feature"` — decompose into epic + tasks with dependencies
- `/track` — sync git changes to beads (transparent, evidence-based)
- `/propagate` — find downstream consumers when shipping libraries
Learning logs saved to `.beads/plans/`. See `docs/plans/2026-03-03-task-planner-design.md`.

## Important Implementation Notes

- **macOS Focused**: File search optimized for macOS using `mdfind`, `find`, `grep`, `mdls`
- **Async Architecture**: Web search and LLM calls use async/await with proper concurrency
- **Rich UI**: All output uses Rich library for formatting and tables
- **Plugin Architecture**: Module scanning auto-discovers command groups + skill metadata
- **Pluggable Architecture**: Support for multiple LLM providers and NL converters
- **Environment Configuration**: .env file loading on startup with reload capability
- **Transcript Logging**: All LLM interactions logged to `outputs/LLMTranscript.md` with errors in `outputs/LLMErrors.md`
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
- **Embedding Backend**: MLX via `mlx-embedding-models` (taylorai) — native Apple Silicon GPU
- **MLX SEQ_LENS Bug**: Library hardcodes max 512 tokens but nomic supports 2048. Monkey-patched in `embeddings.py`. See `docs/dev/MLX_BUG_FIX.md`
- **Chunking**: Paragraph-level (`\n\n` split, merge <50 chars). Context prefix `[title] role:` for embedding. See `docs/plans/PARAGRAPH_CHUNKING_PLAN.md`
- **Schema**: V1 (conversations+turns) → V2 (conversations_raw+turn_embeddings) → V3 (chunk_embeddings with paragraph text stored)

## Development Workflow

- Use `git commit` frequently, especially after completing features
- Update `DONE.md` with detailed progress logs
- Update `TODO.md` to track completion status
- Test commands manually before committing

## Dependencies

- **Core**: click, rich, requests
- **Web**: playwright, beautifulsoup4, lxml
- **TUI**: textual (Textual terminal UI framework)
- **NL (Optional)**: anthropic, requests (for Ollama)
- **Embeddings**: mlx-embedding-models, psycopg2-binary
- **Dev**: pytest, black, flake8, mypy