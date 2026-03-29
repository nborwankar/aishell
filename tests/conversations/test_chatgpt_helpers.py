"""Tier 1: Unit tests for ChatGPT parsing helpers."""

import pytest

from aishell.commands.chatgpt import (
    _find_root_id,
    _traverse_tree,
    _parse_chatgpt_conversation,
)


def _make_node(message=None, parent=None, children=None):
    """Helper to build a ChatGPT mapping node."""
    return {
        "message": message,
        "parent": parent,
        "children": children or [],
    }


def _make_message(role, text, create_time=None):
    """Helper to build a ChatGPT message."""
    return {
        "author": {"role": role},
        "content": {"parts": [text]},
        "create_time": create_time,
    }


class TestFindRootId:
    def test_finds_root(self):
        mapping = {
            "root": _make_node(parent=None, children=["child1"]),
            "child1": _make_node(parent="root"),
        }
        assert _find_root_id(mapping) == "root"

    def test_returns_none_for_empty(self):
        assert _find_root_id({}) is None

    def test_no_root_node(self):
        mapping = {
            "a": _make_node(parent="b"),
            "b": _make_node(parent="a"),
        }
        assert _find_root_id(mapping) is None


class TestTraverseTree:
    def test_linear_conversation(self):
        mapping = {
            "root": _make_node(parent=None, children=["n1"]),
            "n1": _make_node(
                message=_make_message("user", "Hello"),
                parent="root",
                children=["n2"],
            ),
            "n2": _make_node(
                message=_make_message("assistant", "Hi there"),
                parent="n1",
                children=[],
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 2
        assert turns[0]["role"] == "user"
        assert turns[0]["content"] == "Hello"
        assert turns[1]["role"] == "assistant"

    def test_skips_system_messages(self):
        mapping = {
            "root": _make_node(parent=None, children=["n1"]),
            "n1": _make_node(
                message=_make_message("system", "You are a helpful assistant"),
                parent="root",
                children=["n2"],
            ),
            "n2": _make_node(
                message=_make_message("user", "Hello"),
                parent="n1",
                children=[],
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert turns[0]["role"] == "user"

    def test_skips_null_messages(self):
        mapping = {
            "root": _make_node(message=None, parent=None, children=["n1"]),
            "n1": _make_node(
                message=_make_message("user", "Hello"),
                parent="root",
                children=[],
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1

    def test_follows_last_child(self):
        """At branches, follows the last child (canonical path)."""
        mapping = {
            "root": _make_node(parent=None, children=["n1"]),
            "n1": _make_node(
                message=_make_message("user", "Hello"),
                parent="root",
                children=["branch_a", "branch_b"],
            ),
            "branch_a": _make_node(
                message=_make_message("assistant", "Response A"),
                parent="n1",
                children=[],
            ),
            "branch_b": _make_node(
                message=_make_message("assistant", "Response B"),
                parent="n1",
                children=[],
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 2
        assert turns[1]["content"] == "Response B"  # last child

    def test_skips_empty_content(self):
        mapping = {
            "root": _make_node(parent=None, children=["n1"]),
            "n1": _make_node(
                message=_make_message("user", ""),
                parent="root",
                children=["n2"],
            ),
            "n2": _make_node(
                message=_make_message("assistant", "Hi"),
                parent="n1",
                children=[],
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert turns[0]["role"] == "assistant"

    def test_timestamp_conversion(self):
        mapping = {
            "root": _make_node(parent=None, children=["n1"]),
            "n1": _make_node(
                message=_make_message("user", "Hello", create_time=1704067200.0),
                parent="root",
                children=[],
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert turns[0]["timestamp"] == "2024-01-01T00:00:00Z"

    def test_non_string_parts_skipped(self):
        """Non-string parts (like image dicts) are filtered out."""
        mapping = {
            "root": _make_node(parent=None, children=["n1"]),
            "n1": _make_node(
                message={
                    "author": {"role": "user"},
                    "content": {
                        "parts": [
                            "Hello",
                            {"type": "image", "url": "..."},
                            "World",
                        ]
                    },
                    "create_time": None,
                },
                parent="root",
                children=[],
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert turns[0]["content"] == "Hello\nWorld"


class TestParseChatgptConversation:
    def test_full_conversation(self):
        conv_raw = {
            "mapping": {
                "root": _make_node(parent=None, children=["n1"]),
                "n1": _make_node(
                    message=_make_message("user", "Hello"),
                    parent="root",
                    children=["n2"],
                ),
                "n2": _make_node(
                    message=_make_message("assistant", "Hi"),
                    parent="n1",
                    children=[],
                ),
            }
        }
        turns = _parse_chatgpt_conversation(conv_raw)
        assert len(turns) == 2

    def test_empty_mapping(self):
        assert _parse_chatgpt_conversation({"mapping": {}}) == []

    def test_missing_mapping(self):
        assert _parse_chatgpt_conversation({}) == []
