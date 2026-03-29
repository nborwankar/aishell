"""Tier 1: Unit tests for Claude export parsing helpers."""

import pytest

from aishell.commands.claude_export import _parse_claude_conversation


class TestParseClaudeConversation:
    def test_basic_conversation(self):
        conv_raw = {
            "chat_messages": [
                {"sender": "human", "text": "Hello"},
                {"sender": "assistant", "text": "Hi there"},
            ]
        }
        turns = _parse_claude_conversation(conv_raw)
        assert len(turns) == 2
        assert turns[0]["role"] == "user"
        assert turns[0]["content"] == "Hello"
        assert turns[1]["role"] == "assistant"
        assert turns[1]["content"] == "Hi there"

    def test_skips_empty_messages(self):
        conv_raw = {
            "chat_messages": [
                {"sender": "human", "text": "Hello"},
                {"sender": "assistant", "text": ""},
                {"sender": "human", "text": "Still here?"},
            ]
        }
        turns = _parse_claude_conversation(conv_raw)
        assert len(turns) == 2

    def test_skips_whitespace_only(self):
        conv_raw = {
            "chat_messages": [
                {"sender": "human", "text": "   "},
                {"sender": "assistant", "text": "Hi"},
            ]
        }
        turns = _parse_claude_conversation(conv_raw)
        assert len(turns) == 1
        assert turns[0]["role"] == "assistant"

    def test_skips_unknown_sender(self):
        conv_raw = {
            "chat_messages": [
                {"sender": "system", "text": "System prompt"},
                {"sender": "human", "text": "Hello"},
            ]
        }
        turns = _parse_claude_conversation(conv_raw)
        assert len(turns) == 1
        assert turns[0]["role"] == "user"

    def test_preserves_timestamps(self):
        conv_raw = {
            "chat_messages": [
                {
                    "sender": "human",
                    "text": "Hello",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ]
        }
        turns = _parse_claude_conversation(conv_raw)
        assert turns[0]["timestamp"] == "2024-01-01T00:00:00Z"

    def test_empty_messages_list(self):
        assert _parse_claude_conversation({"chat_messages": []}) == []

    def test_missing_messages_key(self):
        assert _parse_claude_conversation({}) == []

    def test_strips_whitespace_from_content(self):
        conv_raw = {
            "chat_messages": [
                {"sender": "human", "text": "  Hello  "},
            ]
        }
        turns = _parse_claude_conversation(conv_raw)
        assert turns[0]["content"] == "Hello"
