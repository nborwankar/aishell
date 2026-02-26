# AIShell Testing Guide - October 31, 2025

Complete guide to testing aishell functionality with working examples.

## Quick Setup (2 minutes)

```bash
cd /Users/nitin/Projects/github/aishell

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install package
pip install -e .

# Install browsers for web search
python -m playwright install chromium

# Verify installation
aishell --help
```

---

## ✅ Working Features (Ready to Test)

### 1. 🔍 File Search

**Test file search with Spotlight (fast, indexed):**

```bash
# Find Python files
aishell find "*.py" --limit 5

# Find markdown files
aishell find "*.md" --limit 5

# Find files by size
aishell find "*" --size ">1MB" --limit 3

# Find files modified today
aishell find "*" --date today --limit 5

# Find files with specific content
aishell find "*.md" --content "tutorial" --limit 3
```

**Expected Output**: Table with file paths, sizes, and modification dates

---

### 2. 🔎 Spotlight Search (macOS Optimized)

Fast search using macOS Spotlight index:

```bash
# Search for anything
aishell spotlight "python" --limit 5

# Search for images
aishell spotlight "kind:image" --limit 5

# Search for recent documents
aishell spotlight "recent:today" --limit 5

# Search for specific file types
aishell spotlight "kind:document" --limit 3
```

**Expected Output**: Quick results from Spotlight index

---

### 3. 🌐 Web Search

**Test web search (note: may have timeout issues):**

```bash
# Search with Google (default)
aishell search "python tutorial" --limit 3

# Search with DuckDuckGo
aishell search "machine learning" --engine duckduckgo --limit 3

# Show browser window (for debugging)
aishell search "claude ai" --show-browser --limit 2
```

**Note**: Web search may timeout occasionally - this is a known issue. Use Spotlight/file search for most operations.

---

### 4. 🐚 Intelligent Shell

**Start the shell:**

```bash
aishell shell --nl-provider mock
```

**Inside the shell, try:**

```bash
# Basic commands
pwd
ls
cd ~
ls -la
git status

# Aliases (predefined shortcuts)
ll          # ls -la
la          # ls -a
..          # cd ..
cls         # clear
gs          # git status

# Get help
help
help find
help search

# Exit
exit
quit
Ctrl+D
```

**With Claude NL support** (requires ANTHROPIC_API_KEY):

```bash
export ANTHROPIC_API_KEY="your-api-key"
aishell shell --nl-provider claude

# Inside shell, use ? prefix for natural language
? what's in this directory
? list all python files
? show me recent git commits
? find large files
```

---

## 🧪 Automated Testing

### Run Quick Test Script

```bash
# From aishell directory
python quick_test.py
```

This will test:
- ✅ Command help system
- ✅ File search
- ✅ Spotlight search
- ✅ File search with content filtering
- ✅ Shell basics

---

### Run Full Test Suite

```bash
# Run all pytest tests
pytest -v

# Run specific test files
pytest tests/test_integration.py -v
pytest tests/test_shell_enhancements.py -v
pytest tests/test_env_manager.py -v

# Run LLM tests (requires API keys)
pytest tests/llm/ -v
```

---

## 🔧 LLM Testing (Optional - Requires API Keys)

### Setup .env File

```bash
# Copy example config
cp .env.example .env

# Edit .env with your API keys
export ANTHROPIC_API_KEY="your-claude-key"
export OPENAI_API_KEY="your-openai-key"
export GOOGLE_API_KEY="your-gemini-key"
```

### Test Claude LLM

```bash
# Basic query
aishell llm claude "Explain quantum computing in one sentence"

# With streaming
aishell llm claude "Write a Python function to calculate factorial" --stream

# Collate responses from multiple providers
aishell collate claude openai "What is 2+2?" --table
```

---

## 📋 Feature Checklist

Test each feature and mark as complete:

### File Search Features
- [ ] `aishell find "*.py"` - Python file search
- [ ] `aishell find "*.md" --content "tutorial"` - Content filtering
- [ ] `aishell find "*" --size ">1MB"` - Size filtering
- [ ] `aishell find "*" --date today` - Date filtering
- [ ] `aishell find "*.json" --path ~/Documents` - Path filtering

### Spotlight Features
- [ ] `aishell spotlight "python"` - Basic search
- [ ] `aishell spotlight "kind:image"` - Type filtering
- [ ] `aishell spotlight "recent:today"` - Recent files

### Web Search Features
- [ ] `aishell search "test query"` - Basic search
- [ ] `aishell search "test" --engine duckduckgo` - DuckDuckGo
- [ ] `aishell search "test" --limit 3` - Limit results

### Shell Features
- [ ] `aishell shell` - Start shell
- [ ] Basic commands (pwd, ls, cd)
- [ ] Aliases (ll, la, .., cls)
- [ ] `help` command in shell
- [ ] Natural language with mock provider

### LLM Features (Optional)
- [ ] `aishell llm claude "test"`
- [ ] `aishell llm openai "test"`
- [ ] `aishell collate claude openai "test"`

---

## 🐛 Troubleshooting

### Virtual Environment Issues

```bash
# If python -m venv fails
python3 -m venv venv
source venv/bin/activate

# Update pip
pip install --upgrade pip
```

### Playwright Browser Issues

```bash
# Reinstall browsers
python -m playwright install chromium

# Check browser installation
python -m playwright install-deps
```

### LLM Provider Issues

```bash
# Test API key is set
echo $ANTHROPIC_API_KEY

# Test Claude directly
python -c "
import os
from anthropic import Anthropic
client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
print('Claude connected successfully!')
"
```

### Shell Command Issues

```bash
# If aishell command not found
pip install -e .

# If still not working
python -m aishell.cli shell
```

---

## 📊 Example Test Session

```bash
# 1. Setup (one-time)
cd /Users/nitin/Projects/github/aishell
python -m venv venv
source venv/bin/activate
pip install -e .
python -m playwright install chromium

# 2. Run automated tests
python quick_test.py

# 3. Manual file search testing
aishell find "*.py" --limit 5
aishell spotlight "tutorial" --limit 3

# 4. Test intelligent shell
aishell shell --nl-provider mock
# Inside shell: pwd, ls, ll, help, exit

# 5. Run full test suite
pytest tests/ -v

# 6. Test with LLM (if API key set)
export ANTHROPIC_API_KEY="your-key"
aishell llm claude "Explain AIShell in one sentence"
```

---

## 🎯 Testing Priorities

### Critical (Must Work)
1. ✅ File search with `find` command
2. ✅ Spotlight search on macOS
3. ✅ Shell startup and basic commands
4. ✅ Aliases in shell
5. ✅ Help system

### Important (Should Work)
1. ⚠️ Web search (known timeout issues)
2. ⚠️ Natural language conversion (mock mode)
3. ✅ Environment variable loading
4. ✅ Transcript logging

### Nice-to-Have (Optional)
1. LLM provider integration
2. MCP support
3. Multi-provider collation

---

## 📝 Current Status

**Phase 1**: ✅ Complete
- ✅ File system search (Spotlight + find)
- ✅ Intelligent shell with aliases
- ✅ Natural language support (mock mode)
- ✅ Rich formatted output

**Phase 2**: ✅ Complete
- ✅ Multi-LLM provider support (Claude, OpenAI, Gemini, Ollama, OpenRouter)
- ✅ LLM collation across providers
- ✅ Environment configuration system
- ✅ Transcript logging
- ✅ MCP support infrastructure

**Phase 3**: 📋 Ready to explore
- [ ] Advanced MCP interactions
- [ ] Custom NL converters
- [ ] Extended shell features
- [ ] Performance optimizations

---

## 🚀 Getting Started Right Now

```bash
# Start here - 3 minutes to first working test
cd /Users/nitin/Projects/github/aishell
source venv/bin/activate  # If venv already exists

# Quick test
aishell find "*.py" --limit 3

# Interactive shell
aishell shell --nl-provider mock
```

Try the `help` command inside the shell to see all available features!

---

**Last Updated**: October 31, 2025
**Status**: Ready for comprehensive testing
