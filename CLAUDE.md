# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**aishell** is an intelligent command line tool built in Python that provides web search, intelligent shell capabilities, and file system search using macOS native tools.

## Development Commands

```bash
# Setup
python -m venv venv
source venv/bin/activate
pip install -e .
python -m playwright install  # For web search

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
├── search/              # Search functionality
│   ├── __init__.py
│   ├── web_search.py    # Playwright-based web search (Google, DuckDuckGo)
│   └── file_search.py   # macOS native file search (Spotlight, find)
├── shell/               # Intelligent shell
│   ├── __init__.py
│   ├── intelligent_shell.py  # Main shell with history, aliases, git awareness
│   └── nl_converter.py  # Natural language to command conversion
└── utils/               # Utility functions
    └── __init__.py

config/                  # Configuration templates
scripts/                 # Helper scripts
```

## Key Features Implemented (Phase 1)

1. **Web Search**: Playwright-based search with Google/DuckDuckGo backends
2. **Intelligent Shell**: Enhanced shell with NL conversion, aliases, history
3. **File Search**: macOS Spotlight and BSD find integration
4. **Natural Language**: Convert NL to commands using Claude API or Ollama

## Important Implementation Notes

- **macOS Focused**: File search optimized for macOS using `mdfind`, `find`, `grep`, `mdls`
- **Async Architecture**: Web search uses async/await with Playwright
- **Rich UI**: All output uses Rich library for formatting
- **Pluggable NL**: Support for Claude, Ollama, and mock NL providers
- **Native Tools**: Leverages system tools rather than pure Python for performance

## Development Workflow

- Use `git commit` frequently, especially after completing features
- Update `DONE.md` with detailed progress logs
- Update `TODO.md` to track completion status
- Test commands manually before committing

## Dependencies

- **Core**: click, rich, requests
- **Web**: playwright, beautifulsoup4, lxml  
- **NL (Optional)**: anthropic, requests (for Ollama)
- **Dev**: pytest, black, flake8, mypy