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

# Optional: Install dependencies for natural language support
pip install anthropic  # For Claude support
# For Ollama, install from https://ollama.ai
```

### Natural Language Setup

#### Claude (Default)
```bash
# Set your Anthropic API key
export ANTHROPIC_API_KEY="your-api-key-here"

# Install the SDK
pip install anthropic
```

#### Ollama (Local LLM)
```bash
# Install Ollama from https://ollama.ai
# Pull a model
ollama pull llama2

# Start Ollama server (usually runs automatically)
# The shell will connect to http://localhost:11434
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

# File search (uses macOS Spotlight by default)
aishell find "*.py"                    # Find all Python files
aishell find "config" --content "api"  # Find files named 'config' containing 'api'
aishell find "*" --type image          # Find all images using Spotlight
aishell find "*" --size ">1MB"         # Find files larger than 1MB
aishell find "*" --date today          # Find files modified today
aishell find "*.js" --no-spotlight     # Use BSD find instead of Spotlight

# Quick Spotlight search
aishell spotlight "machine learning"   # Search everything with Spotlight
aishell spotlight kind:image          # Use Spotlight query syntax

# Interactive shell
aishell shell

# Interactive shell with natural language support
aishell shell  # Uses Claude by default (requires ANTHROPIC_API_KEY)
aishell shell --nl-provider ollama  # Use local Ollama
aishell shell --nl-provider mock    # Use mock converter for testing
aishell shell --nl-provider none    # Disable NL conversion

# Natural language examples in shell (prefix with ?)
# ?list all python files
# ?show disk usage
# ?find large files over 100MB
# ?create a backup of the config directory
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