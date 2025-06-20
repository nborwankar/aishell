# aishell

An intelligent command line tool that combines web search, shell capabilities, and AI integration.

## Features

### Phase 1 (In Development)
- Web search from the command line
- Intelligent shell functionality
- File system search capabilities

### Phase 2 (Planned)
- LLM integration (local and remote)
- Multi-LLM query support
- MCP server communication
- Natural language to MCP message generation

### Phase 3 (Planned)
- Code generation for multiple languages
- Database operations (SQLite, PostgreSQL)
- RAG instance integration
- Map search
- Hardware control (camera, microphone)

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/aishell.git
cd aishell

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Install Playwright browsers (required for web search)
python scripts/install_playwright.py
# OR directly:
python -m playwright install
```

## Usage

```bash
# Run the tool
aishell

# Web search (Google by default)
aishell search "python tutorials"

# Web search with options
aishell search "machine learning" --limit 5 --engine duckduckgo

# Show browser window (disable headless mode)
aishell search "openai gpt-4" --show-browser

# File search
aishell find "*.py" --content "import requests"

# Interactive shell
aishell shell
```

## Development

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
pytest

# Format code
black aishell/

# Lint code
flake8 aishell/
```

## License

MIT License