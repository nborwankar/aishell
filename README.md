# AIShell - Intelligent Command Line Tool

An intelligent command line tool built in Python that provides web search, intelligent shell capabilities, file system search, and comprehensive LLM integration with MCP support.

## Features

### 🔍 Web Search
- Playwright-based web search with Google and DuckDuckGo backends
- Beautiful Rich-formatted output with tables and panels
- Headless Chrome by default with debugging mode available

### 🐚 Intelligent Shell
- Enhanced shell with command history, aliases, and tab completion
- Git branch awareness in prompt
- Safety warnings for dangerous commands
- Natural language to command conversion (with `?` prefix)
- Built-in LLM/MCP commands without leaving shell

### 📁 File System Search (macOS Optimized)
- Primary search using macOS Spotlight (`mdfind`) for fast indexed results
- Fallback to BSD `find` with advanced filtering
- Content search within files using `grep`
- File type, size, and date filtering
- Tree view display option

### 🤖 LLM Integration
- **4 LLM Providers**: Claude (Anthropic), OpenAI, Gemini (Google), Ollama (local)
- **Configurable Models**: Each provider's model configurable via environment variables
- **Latest Defaults**: Claude 3.5 Sonnet, GPT-4o-mini, Gemini 1.5 Flash, Llama 3.2
- **Single Queries**: Query any provider with streaming support
- **Multi-LLM Collation**: Compare responses across providers simultaneously
- **Environment Integration**: Automatic API key and model loading from `.env`

### 🔌 MCP (Model Context Protocol) Support
- Full JSON-RPC client for MCP server communication
- Natural language to MCP message translation
- Support for tools, resources, prompts, and server management
- Built-in shell commands for MCP interaction

### 🔧 Environment Management
- Automatic `.env` file loading on startup
- Dynamic environment reloading without restart
- Secure display with API key masking
- Per-provider configuration management

### 📝 Interaction Logging
- Persistent transcript logging to `LLMTranscript.md`
- Separate error logging to `LLMErrors.md` with detailed information
- Thread-safe concurrent access
- Multi-LLM collation logging

## Installation

### Prerequisites
- Python 3.8+
- macOS (for optimized file search features)

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd aishell

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies (includes all LLM providers)
pip install -e .

# Install Playwright browsers (for web search)
python -m playwright install

# Setup configuration
cp .env.example .env
# Edit .env with your API keys and preferences
```

### Configuration (.env file)
```bash
# LLM Provider API Keys
ANTHROPIC_API_KEY=your-claude-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
GOOGLE_API_KEY=your-gemini-api-key-here

# Default LLM Settings
DEFAULT_LLM_PROVIDER=claude
DEFAULT_TEMPERATURE=0.7

# Provider-Specific Models (easily configurable)
CLAUDE_MODEL=claude-3-5-sonnet-20241022
OPENAI_MODEL=gpt-4o-mini
GEMINI_MODEL=gemini-1.5-flash
OLLAMA_MODEL=llama3.2

# Provider URLs
OLLAMA_URL=http://localhost:11434
OPENAI_BASE_URL=https://api.openai.com/v1

# Other configuration options available in .env.example
```

## Usage

### Web Search
```bash
# Basic web search
aishell search "Python async programming"

# Specify search engine
aishell search "machine learning" --engine duckduckgo

# Show browser for debugging
aishell search "news" --show-browser --limit 5
```

### File System Search
```bash
# Basic file search
aishell find "*.py"

# Content search
aishell find "config" --content "database"

# Advanced filtering
aishell find "*" --type image --size ">1MB" --date "last week"

# Quick Spotlight search
aishell spotlight "python tutorial"
```

### LLM Queries
```bash
# Single LLM query (uses DEFAULT_LLM_PROVIDER from .env)
aishell query "Explain quantum computing"

# Specify provider
aishell query "Write a Python function" --provider openai --model gpt-4

# Streaming response
aishell query "Tell me a story" --provider claude --stream

# Multi-LLM collation
aishell collate "What is the capital of France?" --providers claude openai gemini
```

### MCP Server Interaction
```bash
# Connect to MCP server
aishell mcp http://localhost:8000 ping

# List available tools
aishell mcp http://localhost:8000 --method tools/list

# Natural language to MCP conversion
aishell mcp-convert "list all available tools"
aishell mcp-convert "use the search tool to find Python tutorials" --provider claude
```

### Interactive Shell
```bash
# Start intelligent shell
aishell shell

# In shell - all commands available:
llm "Hello world"                    # LLM query using default provider
collate "Compare these approaches"   # Multi-LLM collation
mcp http://localhost:8000 ping      # MCP interaction
generate python "fibonacci function" # Code generation
env default openai                  # Change default provider
env reload                          # Reload .env file
?list all python files              # Natural language conversion
```

### Environment Management
```bash
# In shell or CLI:
env show                    # Show all environment variables
env show API               # Show variables containing "API"
env get ANTHROPIC_API_KEY  # Get specific variable
env set TEMP_VAR value     # Set runtime variable
env llm claude             # Show Claude configuration
env default gemini         # Set default LLM provider
env reload                 # Reload .env file
```

## Command Reference

### CLI Commands
- `aishell search "query"` - Web search with multiple engines
- `aishell find "pattern"` - File system search with advanced filters
- `aishell spotlight "query"` - Quick Spotlight search
- `aishell query "text"` - Single LLM query
- `aishell collate "text"` - Multi-LLM comparison
- `aishell mcp <server> <command>` - MCP server interaction
- `aishell mcp-convert "text"` - Natural language to MCP translation
- `aishell shell` - Start interactive shell

### Shell Built-in Commands
- `llm "query" [options]` - LLM queries
- `collate "query" [options]` - Multi-LLM collation
- `mcp <server> <command>` - MCP interaction
- `generate <lang> <desc>` - Code generation
- `env <subcommand>` - Environment management
- `cd`, `pwd`, `export`, `alias` - Standard shell commands
- `help` - Show available commands
- `?<request>` - Natural language to command conversion

### Environment Commands
- `env reload` - Reload .env file
- `env show [filter]` - Display environment variables
- `env get <key>` - Get environment variable
- `env set <key> <value>` - Set runtime variable
- `env llm <provider>` - Show provider configuration
- `env default <provider>` - Set default LLM provider
- `env mcp` - Show configured MCP servers
- `env mcp-list` - List all available MCP server types

## LLM Providers

### Supported Providers
1. **Claude (Anthropic)**
   - Default Model: `claude-3-5-sonnet-20241022` (configurable via `CLAUDE_MODEL`)
   - Requires: `ANTHROPIC_API_KEY`
   - Available Models: claude-3-5-sonnet, claude-3-opus, claude-3-haiku, etc.

2. **OpenAI**
   - Default Model: `gpt-4o-mini` (configurable via `OPENAI_MODEL`)
   - Requires: `OPENAI_API_KEY`
   - Available Models: gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo, etc.
   - Optional: `OPENAI_BASE_URL` for custom endpoints

3. **Gemini (Google)**
   - Default Model: `gemini-1.5-flash` (configurable via `GEMINI_MODEL`)
   - Requires: `GOOGLE_API_KEY`
   - Available Models: gemini-1.5-pro, gemini-1.5-flash, gemini-pro, etc.

4. **Ollama (Local)**
   - Default Model: `llama3.2` (configurable via `OLLAMA_MODEL`)
   - Requires: Local Ollama installation
   - Available Models: Any locally installed models (llama3.2, llama3.1, mistral, etc.)
   - Optional: `OLLAMA_URL` (default: http://localhost:11434)

### Updating Models
To use newer models as they become available:

1. **Edit your `.env` file**:
   ```bash
   # Update to latest models
   CLAUDE_MODEL=claude-3-5-sonnet-20241022
   OPENAI_MODEL=gpt-4o
   GEMINI_MODEL=gemini-1.5-pro
   OLLAMA_MODEL=llama3.2
   ```

2. **Reload environment** (in shell):
   ```bash
   env reload
   ```

3. **Or restart the application** to pick up changes

## MCP Servers

### Supported MCP Server Types

#### Database Servers
- **PostgreSQL**: `@modelcontextprotocol/server-postgres` - Full PostgreSQL database access
- **SQLite**: `@modelcontextprotocol/server-sqlite` - Local SQLite database operations
- **MySQL**: `dbhub-mcp-server` - MySQL database connectivity

#### Version Control
- **GitHub**: `@modelcontextprotocol/server-github` - Repository management and GitHub API
- **GitLab**: `@modelcontextprotocol/server-gitlab` - GitLab project and CI/CD operations

#### Atlassian/JIRA
- **JIRA**: `mcp-jira` - JIRA project management and issue tracking
- **Atlassian**: `mcp-atlassian` - Full Atlassian suite (Confluence, JIRA)

#### File System & Web
- **File System**: `@modelcontextprotocol/server-filesystem` - Secure file operations
- **Web Fetch**: `@modelcontextprotocol/server-fetch` - Web content fetching
- **Memory**: `@modelcontextprotocol/server-memory` - Persistent knowledge graph

#### Development Tools
- **Docker**: `docker-mcp-server` - Docker container management
- **Kubernetes**: `mcp-kubernetes` - Kubernetes cluster operations

#### Cloud Services
- **AWS S3**: `mcp-aws-s3` - Amazon S3 storage operations
- **Google Cloud**: `mcp-gcp-storage` - Google Cloud storage

### MCP Server Configuration
Configure MCP servers in your `.env` file:
```bash
# Database servers
MCP_POSTGRES_SERVER=npx -y @modelcontextprotocol/server-postgres postgresql://localhost/mydb
MCP_SQLITE_SERVER=npx -y @modelcontextprotocol/server-sqlite /path/to/database.db

# Version control
MCP_GITHUB_SERVER=npx -y @modelcontextprotocol/server-github
MCP_GITLAB_SERVER=npx -y @modelcontextprotocol/server-gitlab

# Atlassian tools
MCP_JIRA_SERVER=npx -y mcp-jira
MCP_ATLASSIAN_SERVER=npx -y mcp-atlassian

# View configured servers
env mcp                    # Show configured MCP servers
env mcp-list              # List all available server types
```

## Files Generated
- `LLMTranscript.md` - All LLM interaction history with timestamps
- `LLMErrors.md` - Detailed error logs with timestamps
- `~/.aishell_history` - Shell command history
- `~/.aishell_aliases` - Custom aliases (JSON format)

## Architecture

### Project Structure
```
aishell/
├── cli.py               # Main CLI entry point
├── llm/                 # LLM provider system
│   ├── base.py          # Abstract base classes
│   └── providers/       # Individual provider implementations
├── mcp/                 # Model Context Protocol support
├── search/              # Web and file search
├── shell/               # Intelligent shell
└── utils/               # Transcript logging and environment management
```

### Key Features
- **Async Architecture**: All LLM and web operations use async/await
- **Rich UI**: Beautiful terminal output with tables, panels, and progress bars
- **Environment Configuration**: Comprehensive .env support with secure display
- **Transcript Logging**: Complete interaction history with error separation
- **Pluggable Providers**: Easy to add new LLM providers
- **Thread Safety**: Safe concurrent operations

## Development

### Testing
```bash
# Run all tests
pytest

# Run specific test files
pytest tests/test_shell_enhancements.py
pytest tests/test_env_manager.py

# Code formatting
black aishell/
flake8 aishell/
```

### Adding New LLM Providers
1. Create new provider in `aishell/llm/providers/`
2. Inherit from `LLMProvider` base class
3. Implement `query()` and `stream_query()` methods
4. Add to provider imports and mappings
5. Add configuration to `env_manager.py`

## Troubleshooting

### Common Issues
1. **Playwright Installation**: Run `python -m playwright install` for web search
2. **API Keys**: Ensure API keys are set in `.env` file
3. **Ollama**: Start local Ollama service for local LLM support
4. **macOS Spotlight**: File search optimized for macOS, limited on other platforms

### Getting Help
- Use `aishell --help` for CLI help
- Use `help` command in interactive shell
- Check transcript files for interaction history
- Verify environment with `env show` command

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.