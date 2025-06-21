#!/usr/bin/env python3
"""Quick test script for AIShell Phase 1 functionality."""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run a command and display results."""
    print(f"\n🧪 {description}")
    print(f"Command: {' '.join(cmd)}")
    print("=" * 50)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"Error: {result.stderr}")
        if result.returncode != 0:
            print(f"Exit code: {result.returncode}")
    except subprocess.TimeoutExpired:
        print("Command timed out after 30 seconds")
    except Exception as e:
        print(f"Error running command: {e}")

def main():
    """Run quick tests for all Phase 1 features."""
    print("🚀 AIShell Phase 1 Quick Test")
    print("=" * 50)
    
    # Check if in virtual environment
    venv_path = Path("venv/bin/activate")
    if not venv_path.exists():
        print("❌ Virtual environment not found. Please run:")
        print("python -m venv venv")
        print("source venv/bin/activate")
        print("pip install -e .")
        return
    
    # Base command with venv activation
    base_cmd = ["bash", "-c", "source venv/bin/activate && "]
    
    # Test 1: Basic help
    run_command(
        ["bash", "-c", "source venv/bin/activate && aishell --help"],
        "Testing basic command help"
    )
    
    # Test 2: File search
    run_command(
        ["bash", "-c", "source venv/bin/activate && aishell find '*.py' --limit 3"],
        "Testing file search for Python files"
    )
    
    # Test 3: File search with content
    run_command(
        ["bash", "-c", "source venv/bin/activate && aishell find '*.md' --content 'tutorial' --limit 2"],
        "Testing file search with content filtering"
    )
    
    # Test 4: Spotlight search
    run_command(
        ["bash", "-c", "source venv/bin/activate && aishell spotlight 'config' --limit 2"],
        "Testing Spotlight search"
    )
    
    # Test 5: Web search (might timeout)
    print(f"\n🧪 Testing web search (may timeout)")
    print(f"Command: aishell search 'test' --limit 2")
    print("=" * 50)
    print("Skipping web search test to avoid timeout issues.")
    print("To test manually: aishell search 'python tutorial' --limit 2")
    
    # Test 6: Shell help
    run_command(
        ["bash", "-c", "source venv/bin/activate && echo 'help\nexit' | aishell shell --nl-provider mock"],
        "Testing shell help command"
    )
    
    print("\n✅ Quick tests completed!")
    print("\n📖 For full tutorial, see TUTORIAL.md")
    print("\n🔧 Manual testing commands:")
    print("source venv/bin/activate")
    print("aishell find '*.py' --limit 5")
    print("aishell spotlight 'python'")
    print("aishell shell --nl-provider mock")

if __name__ == "__main__":
    main()