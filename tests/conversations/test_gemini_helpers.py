"""Tier 1: Unit tests for Gemini helper functions."""

import pytest

from aishell.commands.gemini import _clean_turn_text, _convert_raw


class TestCleanTurnText:
    def test_strips_user_prefix(self):
        assert _clean_turn_text("You said\nHello there", "user") == "Hello there"

    def test_strips_assistant_prefix(self):
        assert (
            _clean_turn_text("Gemini said\nHere is the answer", "assistant")
            == "Here is the answer"
        )

    def test_no_prefix_unchanged(self):
        assert _clean_turn_text("Just some text", "user") == "Just some text"

    def test_wrong_role_no_strip(self):
        # "You said\n" should NOT be stripped for assistant role
        assert _clean_turn_text("You said\nHello", "assistant") == "You said\nHello"

    def test_empty_string(self):
        assert _clean_turn_text("", "user") == ""

    def test_whitespace_stripped(self):
        assert _clean_turn_text("  hello  ", "user") == "hello"


class TestConvertRaw:
    def test_basic_conversion(self):
        raw_data = {
            "strategy": "web-components",
            "count": 2,
            "turns": [
                {"role": "user", "text": "Hello"},
                {"role": "model", "text": "Hi there"},
            ],
        }
        result = _convert_raw(raw_data, title="Test Chat", source_id="abc123")

        assert result["conversation"]["source"] == "gemini"
        assert result["conversation"]["title"] == "Test Chat"
        assert len(result["turns"]) == 2
        assert result["turns"][0]["role"] == "user"
        assert result["turns"][1]["role"] == "assistant"  # model -> assistant

    def test_source_url_default(self):
        raw_data = {"strategy": "web-components", "count": 0, "turns": []}
        result = _convert_raw(raw_data, title="T", source_id="abc123")
        assert result["conversation"]["source_url"] == "https://gemini.google.com/app/abc123"

    def test_source_url_override(self):
        raw_data = {"strategy": "web-components", "count": 0, "turns": []}
        result = _convert_raw(
            raw_data, title="T", source_id="abc", source_url="https://custom.url"
        )
        assert result["conversation"]["source_url"] == "https://custom.url"

    def test_metadata_includes_strategy(self):
        raw_data = {"strategy": "data-message-id", "count": 3, "turns": []}
        result = _convert_raw(raw_data, title="T", source_id="abc")
        meta = result["conversation"]["metadata"]
        assert meta["extraction_strategy"] == "data-message-id"
        assert meta["raw_turn_count"] == 3

    def test_empty_turns(self):
        raw_data = {"strategy": "none", "count": 0, "turns": []}
        result = _convert_raw(raw_data, title="T", source_id="abc")
        assert result["statistics"]["turn_count"] == 0

    def test_cleans_turn_prefixes(self):
        raw_data = {
            "strategy": "web-components",
            "count": 2,
            "turns": [
                {"role": "user", "text": "You said\nHello"},
                {"role": "model", "text": "Gemini said\nHi"},
            ],
        }
        result = _convert_raw(raw_data, title="T", source_id="abc")
        assert result["turns"][0]["content"] == "Hello"
        assert result["turns"][1]["content"] == "Hi"
