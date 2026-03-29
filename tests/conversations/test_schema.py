"""Tier 1: Unit tests for schema.py — slugify, generate_conv_id, convert_to_schema."""

import pytest

from aishell.commands.conversations.schema import (
    slugify,
    generate_conv_id,
    convert_to_schema,
    ROLE_MAP,
)


# ── slugify ─────────────────────────────────────────────────────────


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_characters(self):
        assert slugify("What's up? (test)") == "whats-up-test"

    def test_leading_trailing_hyphens(self):
        assert slugify("  --hello--  ") == "hello"

    def test_unicode(self):
        result = slugify("café résumé")
        assert "caf" in result  # accented chars kept by \w

    def test_max_length(self):
        long_title = "a" * 100
        assert len(slugify(long_title)) == 60

    def test_custom_max_length(self):
        assert len(slugify("hello world", max_len=5)) == 5

    def test_empty_string(self):
        assert slugify("") == ""

    def test_only_special_chars(self):
        assert slugify("!@#$%^&*()") == ""

    def test_multiple_spaces_and_underscores(self):
        assert slugify("hello   world__test") == "hello-world-test"

    def test_consecutive_hyphens_collapsed(self):
        assert slugify("hello---world") == "hello-world"


# ── generate_conv_id ────────────────────────────────────────────────


class TestGenerateConvId:
    def test_prefix(self):
        assert generate_conv_id("gemini", "abc123").startswith("conv_")

    def test_deterministic(self):
        a = generate_conv_id("gemini", "abc123")
        b = generate_conv_id("gemini", "abc123")
        assert a == b

    def test_different_source_different_id(self):
        a = generate_conv_id("gemini", "abc123")
        b = generate_conv_id("chatgpt", "abc123")
        assert a != b

    def test_length(self):
        # "conv_" + 12 hex chars = 17 chars
        result = generate_conv_id("test", "id")
        assert len(result) == 17


# ── ROLE_MAP ────────────────────────────────────────────────────────


class TestRoleMap:
    def test_model_maps_to_assistant(self):
        assert ROLE_MAP["model"] == "assistant"

    def test_human_maps_to_user(self):
        assert ROLE_MAP["human"] == "user"

    def test_user_identity(self):
        assert ROLE_MAP["user"] == "user"

    def test_assistant_identity(self):
        assert ROLE_MAP["assistant"] == "assistant"

    def test_system_identity(self):
        assert ROLE_MAP["system"] == "system"


# ── convert_to_schema ──────────────────────────────────────────────


class TestConvertToSchema:
    def test_basic_conversion(self):
        turns = [
            {"role": "user", "content": "Hello"},
            {"role": "model", "content": "Hi there"},
        ]
        result = convert_to_schema(
            source="gemini",
            source_id="abc123",
            title="Test Conversation",
            turns=turns,
        )

        assert result["schema_version"] == "1.0"
        assert result["conversation"]["source"] == "gemini"
        assert result["conversation"]["title"] == "Test Conversation"
        assert result["conversation"]["id"].startswith("conv_")
        assert len(result["turns"]) == 2

    def test_role_normalization(self):
        turns = [
            {"role": "human", "content": "Hello"},
            {"role": "model", "content": "Hi"},
        ]
        result = convert_to_schema(
            source="test", source_id="id1", title="T", turns=turns
        )
        assert result["turns"][0]["role"] == "user"
        assert result["turns"][1]["role"] == "assistant"

    def test_statistics(self):
        turns = [
            {"role": "user", "content": "abc"},
            {"role": "assistant", "content": "defgh"},
            {"role": "user", "content": "ij"},
        ]
        result = convert_to_schema(
            source="test", source_id="id1", title="T", turns=turns
        )
        stats = result["statistics"]
        assert stats["turn_count"] == 3
        assert stats["user_turns"] == 2
        assert stats["assistant_turns"] == 1
        assert stats["total_chars"] == 10  # 3 + 5 + 2

    def test_turn_numbers_one_indexed(self):
        turns = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
        ]
        result = convert_to_schema(
            source="test", source_id="id1", title="T", turns=turns
        )
        assert result["turns"][0]["turn_number"] == 1
        assert result["turns"][1]["turn_number"] == 2

    def test_empty_turns(self):
        result = convert_to_schema(
            source="test", source_id="id1", title="T", turns=[]
        )
        assert result["statistics"]["turn_count"] == 0
        assert result["turns"] == []

    def test_optional_fields(self):
        result = convert_to_schema(
            source="test",
            source_id="id1",
            title="T",
            turns=[],
            source_url="https://example.com",
            model="gpt-4",
            created_at="2024-01-01T00:00:00Z",
            extra_metadata={"key": "value"},
        )
        conv = result["conversation"]
        assert conv["source_url"] == "https://example.com"
        assert conv["model"] == "gpt-4"
        assert conv["created_at"] == "2024-01-01T00:00:00Z"
        assert conv["metadata"]["key"] == "value"

    def test_turn_with_timestamp_and_attachments(self):
        turns = [
            {
                "role": "user",
                "content": "Look at this",
                "timestamp": "2024-01-01T00:00:00Z",
                "attachments": [{"type": "image", "url": "img.png"}],
                "metadata": {"source": "web"},
            }
        ]
        result = convert_to_schema(
            source="test", source_id="id1", title="T", turns=turns
        )
        turn = result["turns"][0]
        assert turn["timestamp"] == "2024-01-01T00:00:00Z"
        assert len(turn["attachments"]) == 1
        assert turn["metadata"]["source"] == "web"

    def test_unknown_role_passed_through(self):
        turns = [{"role": "tool", "content": "result"}]
        result = convert_to_schema(
            source="test", source_id="id1", title="T", turns=turns
        )
        assert result["turns"][0]["role"] == "tool"

    def test_source_id_none_fallback(self):
        result = convert_to_schema(
            source="test", source_id=None, title="My Title", turns=[]
        )
        # Should still generate an id from the title hash
        assert result["conversation"]["id"].startswith("conv_")
