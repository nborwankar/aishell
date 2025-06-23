# Changelog

All notable changes to AIShell will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2025-06-23

### Breaking Changes
- **CLI Syntax Changed**: `aishell query` is now `aishell llm [provider] "query"`
- **Collate Syntax Changed**: Now requires two providers: `aishell collate <provider1> <provider2> "query"`
- **Model Parameter Removed**: `--model` parameter removed from CLI (use environment variables)

### Added
- Environment-based model configuration for all LLM providers
- MCP awareness system - LLMs automatically know about available MCP capabilities
- Pre-configured MCP server definitions for 16 popular services
- Provider validation with helpful error messages
- Default provider info messages
- MIT License file
- Comprehensive versioning guidelines

### Changed
- Updated default models to latest versions:
  - Claude: claude-3-5-sonnet-20241022 → claude-3-7-sonnet-20250219
  - OpenAI: gpt-3.5-turbo → gpt-4o-mini
  - Gemini: gemini-pro → gemini-2.5-flash
  - Ollama: llama2 → llama3.2
- Shell built-in commands updated to match new CLI syntax
- Improved command help text with examples
- Click parameter conflict resolved (collate -t → -T)

### Fixed
- LLM provider package dependencies now properly included
- Click warning about duplicate parameter usage
- Test assertions updated for new model names

## [0.2.0] - 2025-06-21

### Added
- **Phase 2 Complete**: Full LLM integration with 4 providers
  - Claude (Anthropic)
  - OpenAI
  - Gemini (Google)
  - Ollama (local)
- Multi-LLM collation - compare responses across providers
- MCP (Model Context Protocol) support with JSON-RPC client
- Natural language to MCP message translation
- Interactive transcript logging (LLMTranscript.md)
- Separate error logging (LLMErrors.md)
- Environment variable management system
- Dynamic .env file reloading
- Shell built-in commands: `llm`, `collate`, `mcp`, `generate`, `env`
- Streaming support for LLM responses
- Thread-safe logging for concurrent operations

### Changed
- Enhanced shell with LLM-aware commands
- Rich formatting for LLM responses
- Comprehensive error handling with detailed logging

## [0.1.0] - 2025-06-20

### Added
- **Phase 1 Complete**: Core command-line functionality
- Web search using Playwright and headless Chrome
  - Google search backend
  - DuckDuckGo search backend
  - Rich formatted output
- Intelligent shell with enhanced features
  - Command history persistence
  - Aliases support
  - Git branch awareness
  - Safety warnings for dangerous commands
  - Natural language to command conversion (? prefix)
- File system search optimized for macOS
  - Spotlight (mdfind) integration
  - BSD find fallback
  - Content search within files
  - Advanced filters (type, size, date)
  - Tree view display option
- Rich terminal UI throughout
- Comprehensive test suite
- Development documentation

### Technical Details
- Python 3.8+ support
- Async/await architecture
- Click framework for CLI
- Rich library for terminal formatting
- Playwright for web automation

## [0.0.1] - 2025-06-19

### Added
- Initial project setup
- Basic project structure
- Core dependencies