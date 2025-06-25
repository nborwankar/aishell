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