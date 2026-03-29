"""Tier 4: CLI integration tests for conversation export commands."""

import json
import os
import zipfile

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from aishell.cli import main


class TestGeminiCLI:
    def test_gemini_group_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["gemini", "--help"])
        assert result.exit_code == 0
        assert "login" in result.output
        assert "pull" in result.output
        assert "import" in result.output

    def test_gemini_login_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["gemini", "login", "--help"])
        assert result.exit_code == 0
        assert "Chrome" in result.output or "sign-in" in result.output.lower()

    def test_gemini_pull_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["gemini", "pull", "--help"])
        assert result.exit_code == 0
        assert "--max" in result.output
        assert "--resume" in result.output
        assert "--dry-run" in result.output
        assert "--delay" in result.output

    def test_gemini_import_no_args(self):
        """Import without args defaults to ~/.aishell/gemini/raw/."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(main, ["gemini", "import"])
            # Should handle gracefully (empty dir or not found)
            assert result.exit_code == 0


class TestChatGPTCLI:
    def test_chatgpt_group_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["chatgpt", "--help"])
        assert result.exit_code == 0
        assert "login" in result.output
        assert "pull" in result.output
        assert "import" in result.output

    def test_chatgpt_import_with_zip(self, tmp_path):
        """Import command processes a ZIP file with conversations.json."""
        # Create a minimal ChatGPT export ZIP
        conversations = [
            {
                "id": "conv-001",
                "title": "Test Conversation",
                "create_time": 1704067200.0,
                "mapping": {
                    "root": {"message": None, "parent": None, "children": ["n1"]},
                    "n1": {
                        "message": {
                            "author": {"role": "user"},
                            "content": {"parts": ["Hello"]},
                            "create_time": 1704067200.0,
                        },
                        "parent": "root",
                        "children": ["n2"],
                    },
                    "n2": {
                        "message": {
                            "author": {"role": "assistant"},
                            "content": {"parts": ["Hi there!"]},
                            "create_time": 1704067201.0,
                        },
                        "parent": "n1",
                        "children": [],
                    },
                },
            }
        ]

        zip_path = tmp_path / "chatgpt-export.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("conversations.json", json.dumps(conversations))

        runner = CliRunner()
        # Patch the data directories to use tmp_path
        with patch("aishell.commands.chatgpt.CONVERSATIONS_DIR", str(tmp_path / "conv")), \
             patch("aishell.commands.chatgpt.MANIFEST_PATH", str(tmp_path / "conv" / "manifest.json")):
            result = runner.invoke(main, ["chatgpt", "import", str(zip_path)])

        assert result.exit_code == 0
        assert "Imported" in result.output or "OK" in result.output

    def test_chatgpt_import_no_conversations_json(self, tmp_path):
        """Import fails gracefully when ZIP has no conversations.json."""
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("readme.txt", "not a conversation")

        runner = CliRunner()
        result = runner.invoke(main, ["chatgpt", "import", str(zip_path)])
        assert result.exit_code == 0
        assert "No conversations.json" in result.output


class TestClaudeCLI:
    def test_claude_group_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["claude", "--help"])
        assert result.exit_code == 0
        assert "login" in result.output
        assert "pull" in result.output
        assert "import" in result.output

    def test_claude_import_with_zip(self, tmp_path):
        """Import command processes a Claude export ZIP."""
        conversations = [
            {
                "uuid": "conv-uuid-001",
                "name": "Test Claude Chat",
                "created_at": "2024-01-01T00:00:00Z",
                "chat_messages": [
                    {"sender": "human", "text": "Hello Claude"},
                    {"sender": "assistant", "text": "Hello! How can I help?"},
                ],
            }
        ]

        zip_path = tmp_path / "claude-export.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("conversations.json", json.dumps(conversations))

        runner = CliRunner()
        with patch("aishell.commands.claude_export.CONVERSATIONS_DIR", str(tmp_path / "conv")), \
             patch("aishell.commands.claude_export.MANIFEST_PATH", str(tmp_path / "conv" / "manifest.json")):
            result = runner.invoke(main, ["claude", "import", str(zip_path)])

        assert result.exit_code == 0
        assert "Imported" in result.output or "OK" in result.output

    def test_claude_import_individual_json_files(self, tmp_path):
        """Import finds individual conversation JSON files in ZIP."""
        conv = {
            "uuid": "conv-002",
            "name": "Individual Chat",
            "chat_messages": [
                {"sender": "human", "text": "Hi"},
                {"sender": "assistant", "text": "Hello!"},
            ],
        }

        zip_path = tmp_path / "claude-export.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("chats/conv-002.json", json.dumps(conv))

        runner = CliRunner()
        with patch("aishell.commands.claude_export.CONVERSATIONS_DIR", str(tmp_path / "conv")), \
             patch("aishell.commands.claude_export.MANIFEST_PATH", str(tmp_path / "conv" / "manifest.json")):
            result = runner.invoke(main, ["claude", "import", str(zip_path)])

        assert result.exit_code == 0

    def test_claude_import_empty_zip(self, tmp_path):
        """Import fails gracefully for a ZIP with no conversation data."""
        zip_path = tmp_path / "empty.zip"
        with zipfile.ZipFile(str(zip_path), "w") as zf:
            zf.writestr("readme.txt", "nothing here")

        runner = CliRunner()
        result = runner.invoke(main, ["claude", "import", str(zip_path)])
        assert result.exit_code == 0
        assert "No conversation data" in result.output


class TestConversationsCLI:
    def test_conversations_group_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["conversations", "--help"])
        assert result.exit_code == 0
        assert "load" in result.output
        assert "search" in result.output

    def test_search_requires_query(self):
        runner = CliRunner()
        result = runner.invoke(main, ["conversations", "search"])
        assert result.exit_code != 0
