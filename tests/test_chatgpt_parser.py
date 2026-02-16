"""Tests for ChatGPT conversation tree parser content-type handling."""

from aishell.commands.chatgpt import _traverse_tree, _find_root_id, _extract_timestamp


def _make_node(node_id, parent_id, children_ids, message=None):
    """Helper to build a mapping node."""
    node = {"id": node_id, "parent": parent_id, "children": children_ids}
    if message is not None:
        node["message"] = message
    return node


def _make_message(role, content_type="text", parts=None, create_time=None, **extra):
    """Helper to build a message dict inside a node."""
    msg = {
        "author": {"role": role},
        "content": {"content_type": content_type},
    }
    if parts is not None:
        msg["content"]["parts"] = parts
    if create_time is not None:
        msg["create_time"] = create_time
    # Merge extra keys into content or metadata
    for k, v in extra.items():
        if k == "metadata":
            msg["metadata"] = v
        elif k == "thoughts":
            msg["content"]["thoughts"] = v
        elif k == "result":
            msg["content"]["result"] = v
        elif k == "summary":
            msg["content"]["summary"] = v
        elif k == "text":
            msg["content"]["text"] = v
    return msg


# ── _extract_timestamp ──────────────────────────────────────────────


class TestExtractTimestamp:
    def test_valid_timestamp(self):
        msg = {"create_time": 1700000000}
        assert _extract_timestamp(msg) == "2023-11-14T22:13:20Z"

    def test_none_create_time(self):
        assert _extract_timestamp({}) is None
        assert _extract_timestamp({"create_time": None}) is None

    def test_invalid_create_time(self):
        assert _extract_timestamp({"create_time": -1e20}) is None


# ── Basic text content_type ─────────────────────────────────────────


class TestTraverseTreeText:
    def test_basic_user_assistant(self):
        mapping = {
            "root": _make_node("root", None, ["u1"]),
            "u1": _make_node(
                "u1",
                "root",
                ["a1"],
                _make_message("user", parts=["Hello"]),
            ),
            "a1": _make_node(
                "a1",
                "u1",
                [],
                _make_message("assistant", parts=["Hi there!"]),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 2
        assert turns[0]["role"] == "user"
        assert turns[0]["content"] == "Hello"
        assert turns[1]["role"] == "assistant"
        assert turns[1]["content"] == "Hi there!"

    def test_skips_system_messages(self):
        mapping = {
            "root": _make_node("root", None, ["sys"]),
            "sys": _make_node(
                "sys",
                "root",
                ["u1"],
                _make_message("system", parts=["You are helpful"]),
            ),
            "u1": _make_node(
                "u1",
                "sys",
                [],
                _make_message("user", parts=["Hello"]),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert turns[0]["role"] == "user"

    def test_empty_parts_skipped(self):
        mapping = {
            "root": _make_node("root", None, ["u1"]),
            "u1": _make_node(
                "u1",
                "root",
                [],
                _make_message("user", parts=["", "  "]),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 0


# ── Image placeholders (multimodal_text and dict parts) ─────────────


class TestTraverseTreeImages:
    def test_dict_parts_become_image_placeholder(self):
        mapping = {
            "root": _make_node("root", None, ["u1"]),
            "u1": _make_node(
                "u1",
                "root",
                [],
                _make_message(
                    "user",
                    content_type="multimodal_text",
                    parts=[
                        "Look at this image:",
                        {"content_type": "image_asset_pointer", "asset_id": "abc"},
                    ],
                ),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert "[image]" in turns[0]["content"]
        assert "Look at this image:" in turns[0]["content"]

    def test_only_image_parts(self):
        mapping = {
            "root": _make_node("root", None, ["u1"]),
            "u1": _make_node(
                "u1",
                "root",
                [],
                _make_message(
                    "user",
                    content_type="multimodal_text",
                    parts=[{"content_type": "image_asset_pointer", "asset_id": "x"}],
                ),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert turns[0]["content"] == "[image]"


# ── Code Interpreter (execution_output) ─────────────────────────────


class TestTraverseTreeCodeInterpreter:
    def test_execution_output_with_code_and_text(self):
        mapping = {
            "root": _make_node("root", None, ["t1"]),
            "t1": _make_node(
                "t1",
                "root",
                [],
                _make_message(
                    "tool",
                    content_type="execution_output",
                    text="42\n",
                    metadata={
                        "aggregate_result": {"code": "print(6 * 7)"},
                    },
                ),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert turns[0]["role"] == "tool"
        assert "```python" in turns[0]["content"]
        assert "print(6 * 7)" in turns[0]["content"]
        assert "Output:" in turns[0]["content"]
        assert "42" in turns[0]["content"]

    def test_execution_output_code_only(self):
        mapping = {
            "root": _make_node("root", None, ["t1"]),
            "t1": _make_node(
                "t1",
                "root",
                [],
                _make_message(
                    "tool",
                    content_type="execution_output",
                    text="",
                    metadata={"aggregate_result": {"code": "x = 1"}},
                ),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert "```python" in turns[0]["content"]
        assert "Output:" not in turns[0]["content"]

    def test_execution_output_output_only(self):
        mapping = {
            "root": _make_node("root", None, ["t1"]),
            "t1": _make_node(
                "t1",
                "root",
                [],
                _make_message(
                    "tool",
                    content_type="execution_output",
                    text="result: 99",
                    metadata={},
                ),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert "Output:" in turns[0]["content"]
        assert "result: 99" in turns[0]["content"]

    def test_execution_output_empty_skipped(self):
        mapping = {
            "root": _make_node("root", None, ["t1"]),
            "t1": _make_node(
                "t1",
                "root",
                [],
                _make_message(
                    "tool",
                    content_type="execution_output",
                    text="",
                    metadata={},
                ),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 0


# ── Browsing results (tether_browsing_display) ──────────────────────


class TestTraverseTreeBrowsing:
    def test_browsing_with_result(self):
        mapping = {
            "root": _make_node("root", None, ["t1"]),
            "t1": _make_node(
                "t1",
                "root",
                [],
                _make_message(
                    "tool",
                    content_type="tether_browsing_display",
                    result="Here is the web page content...",
                ),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert turns[0]["role"] == "tool"
        assert turns[0]["content"] == "Here is the web page content..."

    def test_browsing_falls_back_to_summary(self):
        mapping = {
            "root": _make_node("root", None, ["t1"]),
            "t1": _make_node(
                "t1",
                "root",
                [],
                _make_message(
                    "tool",
                    content_type="tether_browsing_display",
                    result="",
                    summary="Summary of browsing results",
                ),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert turns[0]["content"] == "Summary of browsing results"

    def test_browsing_empty_skipped(self):
        mapping = {
            "root": _make_node("root", None, ["t1"]),
            "t1": _make_node(
                "t1",
                "root",
                [],
                _make_message(
                    "tool",
                    content_type="tether_browsing_display",
                    result="",
                    summary="",
                ),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 0


# ── Thoughts / reasoning ────────────────────────────────────────────


class TestTraverseTreeThoughts:
    def test_thoughts_attached_to_next_assistant_turn(self):
        mapping = {
            "root": _make_node("root", None, ["u1"]),
            "u1": _make_node(
                "u1",
                "root",
                ["th1"],
                _make_message("user", parts=["Explain X"]),
            ),
            "th1": _make_node(
                "th1",
                "u1",
                ["a1"],
                _make_message(
                    "assistant",
                    content_type="thoughts",
                    thoughts=["Let me think about this...", "X involves Y and Z"],
                ),
            ),
            "a1": _make_node(
                "a1",
                "th1",
                [],
                _make_message("assistant", parts=["X is ..."]),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 2  # user + assistant (thoughts not a separate turn)
        assert turns[1]["role"] == "assistant"
        assert "metadata" in turns[1]
        assert turns[1]["metadata"]["thoughts"] == [
            "Let me think about this...",
            "X involves Y and Z",
        ]

    def test_empty_thoughts_not_stashed(self):
        mapping = {
            "root": _make_node("root", None, ["th1"]),
            "th1": _make_node(
                "th1",
                "root",
                ["a1"],
                _make_message("assistant", content_type="thoughts", thoughts=[]),
            ),
            "a1": _make_node(
                "a1",
                "th1",
                [],
                _make_message("assistant", parts=["Answer"]),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert "metadata" not in turns[0]


# ── Skipped content types ───────────────────────────────────────────


class TestTraverseTreeSkips:
    def test_reasoning_recap_skipped(self):
        mapping = {
            "root": _make_node("root", None, ["rc"]),
            "rc": _make_node(
                "rc",
                "root",
                ["a1"],
                _make_message(
                    "assistant",
                    content_type="reasoning_recap",
                    parts=["Thought for 5s"],
                ),
            ),
            "a1": _make_node(
                "a1",
                "rc",
                [],
                _make_message("assistant", parts=["Real answer"]),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert turns[0]["content"] == "Real answer"

    def test_model_editable_context_skipped(self):
        mapping = {
            "root": _make_node("root", None, ["mc"]),
            "mc": _make_node(
                "mc",
                "root",
                ["u1"],
                _make_message(
                    "assistant",
                    content_type="model_editable_context",
                    parts=["memory update"],
                ),
            ),
            "u1": _make_node(
                "u1",
                "mc",
                [],
                _make_message("user", parts=["Hello"]),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert turns[0]["content"] == "Hello"


# ── Tool role acceptance ────────────────────────────────────────────


class TestTraverseTreeToolRole:
    def test_tool_role_text_parts_accepted(self):
        """Tool messages with regular text parts (e.g. browsing cite) pass through."""
        mapping = {
            "root": _make_node("root", None, ["t1"]),
            "t1": _make_node(
                "t1",
                "root",
                [],
                _make_message("tool", parts=["Some tool output text"]),
            ),
        }
        turns = _traverse_tree(mapping, "root")
        assert len(turns) == 1
        assert turns[0]["role"] == "tool"
        assert turns[0]["content"] == "Some tool output text"


# ── Mixed conversation (integration-style) ──────────────────────────


class TestTraverseTreeIntegration:
    def test_mixed_content_types(self):
        """Full conversation with text, code interpreter, image, thoughts, browsing."""
        mapping = {
            "root": _make_node("root", None, ["sys"]),
            "sys": _make_node(
                "sys",
                "root",
                ["u1"],
                _make_message("system", parts=["System prompt"]),
            ),
            "u1": _make_node(
                "u1",
                "sys",
                ["a1"],
                _make_message(
                    "user",
                    parts=[
                        "Analyze this image:",
                        {"content_type": "image_asset_pointer", "asset_id": "img1"},
                    ],
                    create_time=1700000000,
                ),
            ),
            "a1": _make_node(
                "a1",
                "u1",
                ["ci1"],
                _make_message(
                    "assistant", parts=["Let me run some code."], create_time=1700000010
                ),
            ),
            "ci1": _make_node(
                "ci1",
                "a1",
                ["ci_out"],
                _make_message(
                    "tool",
                    content_type="execution_output",
                    text="[1, 2, 3]",
                    metadata={
                        "aggregate_result": {
                            "code": "import json\nprint(json.loads('[1,2,3]'))"
                        }
                    },
                    create_time=1700000020,
                ),
            ),
            "ci_out": _make_node(
                "ci_out",
                "ci1",
                ["th1"],
                _make_message(
                    "assistant",
                    parts=["The code returned a list."],
                    create_time=1700000030,
                ),
            ),
            "th1": _make_node(
                "th1",
                "ci_out",
                ["a2"],
                _make_message(
                    "assistant",
                    content_type="thoughts",
                    thoughts=["Summarizing findings..."],
                ),
            ),
            "a2": _make_node(
                "a2",
                "th1",
                [],
                _make_message(
                    "assistant",
                    parts=["In summary, the image shows..."],
                    create_time=1700000040,
                ),
            ),
        }
        turns = _traverse_tree(mapping, "root")

        # Expected: user, assistant, tool(code), assistant, assistant(with thoughts)
        assert len(turns) == 5

        assert turns[0]["role"] == "user"
        assert "[image]" in turns[0]["content"]

        assert turns[1]["role"] == "assistant"
        assert turns[1]["content"] == "Let me run some code."

        assert turns[2]["role"] == "tool"
        assert "```python" in turns[2]["content"]

        assert turns[3]["role"] == "assistant"
        assert turns[3]["content"] == "The code returned a list."

        assert turns[4]["role"] == "assistant"
        assert turns[4]["metadata"]["thoughts"] == ["Summarizing findings..."]
        assert "summary" in turns[4]["content"].lower()
