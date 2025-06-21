# AIShell Phase 1 Tutorial

This tutorial will walk you through setting up and testing all Phase 1 features of AIShell.

## 🚀 Quick Start

### 1. Installation

```bash
# Navigate to the project directory
cd /Users/nitin/Projects/github/aishell

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install the package in development mode
pip install -e .

# Install Playwright browsers for web search
python scripts/install_playwright.py
# OR directly:
python -m playwright install chromium

# Verify installation
aishell --help
```

### 2. Test Basic Functionality

```bash
# Check if everything is working
aishell --version
```

## 📊 Feature Testing Guide

### 🌐 Web Search Testing

The web search feature uses Playwright with headless Chrome to search Google and DuckDuckGo.

```bash
# Basic web search (Google)
aishell search "python tutorials"

# Search with DuckDuckGo
aishell search "machine learning" --engine duckduckgo

# Limit results
aishell search "openai gpt" --limit 5

# Show browser window (for debugging)
aishell search "claude ai" --show-browser

# Search with different engines
aishell search "playwright python" --engine google --limit 3
```

**Expected Output**: Formatted table with search results showing titles, URLs, and snippets.

### 🔍 File System Search Testing

The file search uses macOS Spotlight (mdfind) and BSD find commands.

```bash
# Find Python files
aishell find "*.py"

# Find files with specific content
aishell find "*.md" --content "tutorial"

# Find by file type
aishell find "*" --type image --limit 10

# Find large files
aishell find "*" --size ">1MB" --limit 5

# Find recent files
aishell find "*" --date today

# Search in specific directory
aishell find "*.json" --path ~/Documents

# Use tree view
aishell find "*.py" --tree --limit 10

# Force use of find instead of Spotlight
aishell find "*.txt" --no-spotlight
```

**Expected Output**: Table with file paths, sizes, and modification dates. Content matches shown in panels if `--content` is used.

### ⚡ Quick Spotlight Search

```bash
# Quick search for anything
aishell spotlight "machine learning"

# Search for images
aishell spotlight "kind:image"

# Search recent documents
aishell spotlight "python tutorial"
```

### 🐚 Intelligent Shell Testing

The intelligent shell provides enhanced features with natural language support.

```bash
# Start the shell
aishell shell
```

**Inside the shell, try these commands:**

#### Basic Shell Commands
```bash
# Basic navigation
pwd
ls
cd ~/Desktop
cd ..

# Git commands (if in a git repo)
git status
gs  # alias for git status

# Use aliases
ll    # ls -la
la    # ls -a
..    # cd ..
cls   # clear
```

#### Natural Language Commands (requires API key)

First, set up your API key:
```bash
# For Claude (recommended)
export ANTHROPIC_API_KEY="your-key-here"

# Then start shell with Claude
aishell shell --nl-provider claude

# Or use Ollama (requires Ollama installed)
aishell shell --nl-provider ollama

# Or use mock for testing
aishell shell --nl-provider mock
```

**Natural Language Examples** (prefix with `?`):
```bash
?list all python files
?show disk usage
?find large files
?check running processes
?create a backup folder
?show network connections
?find files modified today
```

#### Built-in Shell Features
```bash
# Show help
help

# Show aliases
alias

# Set environment variable
export MY_VAR=test_value

# Show command history
history

# Exit
exit
```

## 🧪 Testing Scenarios

### Scenario 1: Research Workflow
```bash
# Search for information online
aishell search "python best practices 2024" --limit 5

# Find related files on your system
aishell find "*python*" --content "best practice"

# Use shell to explore
aishell shell
# Inside shell: ?show me all python files in this project
```

### Scenario 2: File Management
```bash
# Find all images larger than 1MB
aishell find "*" --type image --size ">1MB"

# Search for configuration files
aishell spotlight "config"

# Use shell for detailed exploration
aishell shell
# Inside shell: ?find all config files modified this week
```

### Scenario 3: Development Workflow
```bash
# Search for documentation online
aishell search "playwright python documentation" --engine duckduckgo

# Find similar code in your projects
aishell find "*.py" --content "playwright"

# Use enhanced shell
aishell shell --nl-provider mock
# Inside shell: ?show git status
# Inside shell: ll
# Inside shell: ?find all test files
```

## 🐛 Troubleshooting

### Common Issues and Solutions

#### 1. Playwright Browser Not Found
```bash
# Install browsers
python -m playwright install

# Or use the helper script
python scripts/install_playwright.py
```

#### 2. Web Search Not Working
```bash
# Test with browser visible
aishell search "test" --show-browser

# Try different engine
aishell search "test" --engine duckduckgo
```

#### 3. File Search Issues
```bash
# Test Spotlight availability
aishell find "test" --no-spotlight

# Check if mdfind works
mdfind test

# Fallback to find
find . -name "*test*"
```

#### 4. Natural Language Not Working
```bash
# Test with mock provider
aishell shell --nl-provider mock

# Check API key
echo $ANTHROPIC_API_KEY

# Use without NL
aishell shell --nl-provider none
```

#### 5. Permission Issues
```bash
# Make sure Spotlight indexing is enabled
sudo mdutil -i on /

# Check file permissions
ls -la aishell/
```

## 📊 Performance Notes

- **Web Search**: First search may be slower due to browser startup
- **File Search**: Spotlight is much faster than find for large directories
- **Shell**: Natural language conversion adds ~1-2 second delay
- **Results**: Limited by default for performance (adjustable with `--limit`)

## 🔧 Advanced Configuration

### Custom Aliases
Create `~/.aishell_aliases` with custom aliases:
```json
{
  "gst": "git status",
  "ll": "ls -la",
  "myproject": "cd ~/Projects/myproject"
}
```

### Environment Variables
```bash
# For Claude API
export ANTHROPIC_API_KEY="your-key"

# For custom Ollama endpoint
export OLLAMA_BASE_URL="http://localhost:11434"
```

## ✅ Verification Checklist

Test each feature to ensure everything works:

- [ ] `aishell --help` shows command help
- [ ] `aishell search "test"` returns web results
- [ ] `aishell find "*.py"` finds Python files
- [ ] `aishell spotlight "test"` shows Spotlight results
- [ ] `aishell shell` starts interactive shell
- [ ] Shell aliases work (`ll`, `gs`, etc.)
- [ ] Natural language works with `?` prefix (if API key set)
- [ ] File search with content filtering works
- [ ] Tree view displays properly
- [ ] Different search engines work

## 🎯 Next Steps

Once Phase 1 is working, you're ready for Phase 2 which will add:
- LLM integration (single and multiple)
- MCP server communication
- JSON message generation from natural language

## 💡 Tips

1. **Start Simple**: Begin with basic commands before trying advanced features
2. **Check Logs**: If something fails, the error messages are usually helpful
3. **Use Help**: Each command has detailed help with `--help`
4. **Test Incrementally**: Test one feature at a time
5. **API Keys**: Natural language features require API keys but everything else works without them

## 🔗 Useful Commands Summary

```bash
# Quick tests
aishell search "python" --limit 3
aishell find "*.py" --limit 5
aishell spotlight "config" --limit 5
aishell shell --nl-provider mock

# Advanced usage
aishell find "*" --type image --size ">1MB" --tree
aishell search "tutorial" --engine duckduckgo --show-browser
aishell shell --nl-provider claude  # requires ANTHROPIC_API_KEY
```

Happy exploring! 🚀