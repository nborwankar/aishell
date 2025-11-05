# TODO - Command Line Tool Development

## Phase 1 ✅ COMPLETED
- [x] Set up Python project structure
- [x] Web search from the command line (with Playwright and headless Chrome)
- [x] Intelligent shell functionality (with NL support via Claude/Ollama)
- [x] File system search capabilities (with macOS Spotlight integration)

--

## Phase 2 ✅ COMPLETED
- [x] Send queries to one LLM (local or remote)
- [x] Send queries to multiple LLMs
- [x] Interact via JSON messages with local and remote MCP servers
- [x] Generate MCP messages from natural language queries
- [x] Enhance interactive shell with LLM built-in commands
- [x] Add MCP built-in commands to shell
- [x] Implement magic commands for multi-queries (renamed to "collate")
- [x] Add code generation commands within shell
- [x] Environment variable management system (.env loading)
- [x] LLM interaction transcript logging (LLMTranscript.md + LLMErrors.md)
- [x] Configurable default LLM provider system
- [x] Enhanced shell with env management commands
- [x] **MCP Awareness System**: LLMs automatically know about available MCP capabilities
- [x] **Default MCP Server Configurations**: 16 popular MCP servers pre-configured
- [x] **Configurable Model Selection**: Environment-based model configuration for all providers
- [x] **Model Updates**: Updated to latest models (Claude 3.5 Sonnet, GPT-4o-mini, Gemini 1.5 Flash, Llama 3.2)
- [x] **MIT License**: Added proper open source licensing
- [x] **LLM Dependencies**: Added all LLM provider packages as required dependencies
- [x] **CLI Parameter Fix**: Fixed Click warning for duplicate -t parameter usage
- [x] **CLI Command Refactoring**: New intuitive syntax - `aishell llm [provider] "query"` and `aishell collate <p1> <p2> "query"`
- [x] **Base URL Configuration**: All LLM providers now support configurable base URLs for custom endpoints
- [x] **OpenRouter Integration (Part A)**: Created OpenRouter provider class with full LLM subsystem integration

--

## Pending - OpenRouter Integration (Part B)
- [ ] Add "openrouter" to the list of valid providers in CLI
- [ ] Update llm command to accept openrouter as a provider
- [ ] Update collate command to accept openrouter as a provider  
- [ ] Update shell built-in commands to support openrouter
- [ ] Update help text and documentation with openrouter examples
- [ ] Test openrouter in both CLI and shell modes

--

## Phase 3
*Phase 3 features have been moved to FORLATER.md to keep the project focused on core functionality.*

--

## Potential Improvements (Identified 2025-11-04)

### Quick Wins (1-2 days)

#### Code Quality & Type Safety
- [ ] **Complete Type Hint Coverage** (2-3 hours)
  - Add missing return type hints in `search/web_search.py`
  - Run `mypy` and resolve any type checking issues
  - Add type stubs for external libraries where needed
  - Impact: Better IDE support, catch bugs at development time

- [ ] **Pre-commit Hooks** (2-3 hours)
  - Add automatic formatting (black, isort)
  - Add linting checks (flake8, pylint)
  - Add type checking (mypy)
  - Add test execution for changed files
  - Impact: Enforce code quality before commits

#### Logging & Observability
- [ ] **Structured Logging** (4-6 hours)
  - Add Python `logging` module integration
  - Implement log levels (DEBUG, INFO, WARNING, ERROR)
  - Add optional JSON logging for easier parsing
  - Include correlation IDs for multi-LLM queries
  - Impact: Better debugging and monitoring

#### Security & Input Validation
- [ ] **Input Sanitization** (6-8 hours)
  - Add validation for query length limits (prevent excessive API costs)
  - Add file path validation (prevent directory traversal)
  - Add command injection prevention in shell
  - Add model name validation
  - Impact: Prevent security vulnerabilities

### High Impact Improvements (1 week)

#### Testing & Reliability
- [ ] **Expand Test Coverage** (8-12 hours)
  - Add integration tests for web search with actual browser interactions
  - Add integration tests for file search on different directory structures
  - Add shell interactive mode edge case tests
  - Add multi-LLM query collation tests
  - Add error scenario tests (network failures, invalid API keys, malformed responses)
  - Add performance/load tests for concurrent operations
  - Impact: Higher reliability, catch edge case bugs

- [ ] **Refine Exception Handling** (4-6 hours)
  - Replace broad `except Exception` with specific exceptions in:
    - `web_search.py`: Use `aiohttp.ClientError`, `playwright.errors.*`
    - `intelligent_shell.py`: Use `FileNotFoundError`, `PermissionError`, etc.
    - `mcp/client.py`: Use `json.JSONDecodeError`, `asyncio.TimeoutError`
  - Add exception chaining (`raise NewException from e`)
  - Impact: Better error diagnosis and debugging

#### Performance Optimization
- [ ] **Connection Pooling & Resource Management** (6-8 hours)
  - Implement connection pooling for `aiohttp.ClientSession`
  - Reuse Playwright browser contexts across searches
  - Add configurable timeouts for all network operations
  - Implement connection retry logic with exponential backoff
  - Impact: Faster responses, lower resource usage

#### User Experience
- [ ] **Configuration Management** (6-8 hours)
  - Add interactive configuration wizard
  - Support multiple profiles (work, personal, etc.)
  - Add config validation with helpful error messages
  - Implement config migration for version updates
  - Impact: Easier setup and configuration

### Strategic Improvements (2+ weeks)

#### Performance Optimization
- [ ] **Caching Layer** (8-10 hours)
  - Cache web search results (with TTL)
  - Cache LLM responses for identical queries
  - Cache file search results for frequently accessed paths
  - Add cache invalidation strategies
  - Impact: Significantly faster repeated operations

- [ ] **Async Optimization** (4-6 hours)
  - Review and optimize concurrent task limits
  - Add rate limiting for API calls
  - Implement request batching where applicable
  - Impact: Better resource utilization, avoid API rate limits

#### Security & Input Validation
- [ ] **Shell Command Sandboxing** (10-12 hours)
  - Implement command allowlist/blocklist
  - Add permission prompts for dangerous operations
  - Consider using restricted shell environments
  - Impact: Safer command execution

- [ ] **API Key Security** (4-6 hours)
  - Add API key rotation support
  - Implement key expiry checks
  - Add support for credential managers (keyring)
  - Impact: Better security practices

#### Logging & Observability
- [ ] **Metrics & Telemetry** (8-10 hours)
  - Add performance metrics (response times, token usage)
  - Track error rates by provider
  - Add optional anonymous usage analytics
  - Implement cost tracking for LLM API calls
  - Impact: Better understanding of usage patterns

#### User Experience Enhancements
- [ ] **Shell Enhancements** (8-12 hours)
  - Add syntax highlighting for commands
  - Implement tab completion for built-in commands
  - Add command suggestions based on typos (fuzzy matching)
  - Improve history search (reverse-i-search like bash)
  - Impact: Better interactive experience

- [ ] **Output Formatting Options** (4-6 hours)
  - Add JSON output mode for scripting
  - Support markdown, plain text, and HTML formats
  - Add color theme customization
  - Implement pagination for long outputs
  - Impact: Better integration with other tools

#### Feature Additions
- [ ] **Plugin System** (12-16 hours)
  - Design plugin API for custom providers
  - Support third-party LLM providers via plugins
  - Add plugin discovery and management
  - Impact: Easier extensibility

- [ ] **Context Management** (8-10 hours)
  - Implement conversation history across sessions
  - Add context window management
  - Support context import/export
  - Impact: Better multi-turn conversations

- [ ] **Advanced Search Features** (12-16 hours)
  - Add semantic search using embeddings
  - Implement search result ranking
  - Support search filters (date, type, size)
  - Add search result export (CSV, JSON)
  - Impact: More powerful search capabilities

#### Cross-Platform Support
- [ ] **Windows & Linux Compatibility** (16-20 hours)
  - Abstract platform-specific file search (alternative to `mdfind`)
  - Add Windows PowerShell integration
  - Test and fix Linux compatibility issues
  - Impact: Broader user base

- [ ] **Platform-Agnostic Search** (8-12 hours)
  - Implement pure Python file search fallback
  - Add support for Windows indexing service
  - Support Linux `locate` and `find` alternatives
  - Impact: Works on all platforms

#### Documentation Improvements
- [ ] **API Documentation** (8-10 hours)
  - Generate Sphinx documentation from docstrings
  - Add architecture diagrams (mermaid)
  - Create video tutorials or GIFs
  - Impact: Easier for contributors and users

- [ ] **Docstring Enhancement** (4-6 hours)
  - Add examples to all public methods
  - Include type examples for complex parameters
  - Add "See Also" sections for related functions
  - Impact: Better developer experience

#### CI/CD & Development Workflow
- [ ] **GitHub Actions Improvements** (4-6 hours)
  - Add automated type checking (mypy)
  - Add code coverage reporting
  - Implement automated releases
  - Add performance regression tests
  - Impact: Better code quality automation

#### Testing & Reliability
- [ ] **Property-Based Testing** (4-6 hours)
  - Use `hypothesis` for input validation testing
  - Test LLM provider responses with generated data
  - Impact: Find edge cases automatically

---

**Current Code Quality Score: 8.5/10**

**Notes:**
- Codebase is already in excellent shape
- These improvements would bring it to production-grade enterprise level
- Maintain clean architecture and ease of use during improvements
- Prioritize quick wins and high-impact items first