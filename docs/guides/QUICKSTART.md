# 🚀 AIShell Quick Start

## Installation (2 minutes)

```bash
cd /Users/nitin/Projects/github/aishell

# Setup
python -m venv venv
source venv/bin/activate
pip install -e .

# Install browsers for web search
python -m playwright install chromium
```

## Test It Now!

```bash
# Activate environment
source venv/bin/activate

# Test file search
aishell find "*.py" --limit 5

# Test intelligent shell
aishell shell --nl-provider mock
# Try: help, ll, pwd, exit

# Test Spotlight search  
aishell spotlight "python" --limit 3

# Test web search (may timeout)
aishell search "python tutorial" --limit 3
```

## Quick Commands

```bash
# File operations
aishell find "*.md" --content "tutorial"
aishell find "*" --type image --limit 5
aishell find "*" --size ">1MB" --date today

# Web search
aishell search "claude ai" --engine google
aishell search "playwright" --engine duckduckgo

# Spotlight
aishell spotlight "kind:image"
aishell spotlight "config"

# Shell with natural language
aishell shell  # Use ? prefix for NL commands
```

## Features Working ✅

- ✅ File search with Spotlight/find
- ✅ Intelligent shell with aliases
- ✅ Natural language commands (mock mode)
- ✅ Rich formatted output
- ⚠️ Web search (may have timeout issues)

## Next Steps

1. See `TUTORIAL.md` for complete guide
2. Run `python quick_test.py` for automated tests
3. Set `ANTHROPIC_API_KEY` for real NL support

Ready for Phase 2! 🎉