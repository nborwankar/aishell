"""Tier 3: Playwright integration tests for Gemini page.evaluate() extraction.

These tests run real Playwright JS evaluation against local HTML fixtures
to validate that the extraction functions work against realistic DOM.
"""

import pytest

pytestmark = pytest.mark.playwright


class TestEnumerateConversations:
    def test_finds_sidebar_links(self, page, mock_server):
        page.goto(f"{mock_server}/gemini_app.html")
        from aishell.commands.gemini import _enumerate_conversations

        convos = _enumerate_conversations(page)
        assert len(convos) == 3
        assert all("source_id" in c for c in convos)
        assert all("title" in c for c in convos)
        assert all("href" in c for c in convos)

    def test_source_ids_are_hex(self, page, mock_server):
        page.goto(f"{mock_server}/gemini_app.html")
        from aishell.commands.gemini import _enumerate_conversations

        convos = _enumerate_conversations(page)
        for c in convos:
            # source_id should be the hex part from the URL
            assert len(c["source_id"]) >= 10

    def test_titles_extracted(self, page, mock_server):
        page.goto(f"{mock_server}/gemini_app.html")
        from aishell.commands.gemini import _enumerate_conversations

        convos = _enumerate_conversations(page)
        titles = [c["title"] for c in convos]
        assert "Python Help" in titles
        assert "Math Questions" in titles
        assert "Travel Planning" in titles

    def test_deduplicates(self, page, mock_server):
        """Each source_id should appear only once."""
        page.goto(f"{mock_server}/gemini_app.html")
        from aishell.commands.gemini import _enumerate_conversations

        convos = _enumerate_conversations(page)
        ids = [c["source_id"] for c in convos]
        assert len(ids) == len(set(ids))


class TestExtractConversation:
    def test_web_components_strategy(self, page, mock_server):
        page.goto(f"{mock_server}/gemini_conv_webcomponents.html")
        from aishell.commands.gemini import _extract_conversation

        result = _extract_conversation(page)
        assert result["strategy"] == "web-components"
        assert result["count"] == 4
        assert len(result["turns"]) == 4

    def test_web_components_roles(self, page, mock_server):
        page.goto(f"{mock_server}/gemini_conv_webcomponents.html")
        from aishell.commands.gemini import _extract_conversation

        result = _extract_conversation(page)
        roles = [t["role"] for t in result["turns"]]
        assert roles == ["user", "model", "user", "model"]

    def test_web_components_text(self, page, mock_server):
        page.goto(f"{mock_server}/gemini_conv_webcomponents.html")
        from aishell.commands.gemini import _extract_conversation

        result = _extract_conversation(page)
        assert "capital of France" in result["turns"][0]["text"]
        assert "Paris" in result["turns"][1]["text"]

    def test_data_message_id_strategy(self, page, mock_server):
        page.goto(f"{mock_server}/gemini_conv_datamessageid.html")
        from aishell.commands.gemini import _extract_conversation

        result = _extract_conversation(page)
        assert result["strategy"] == "data-message-id"
        assert result["count"] == 4

    def test_data_message_id_roles(self, page, mock_server):
        page.goto(f"{mock_server}/gemini_conv_datamessageid.html")
        from aishell.commands.gemini import _extract_conversation

        result = _extract_conversation(page)
        roles = [t["role"] for t in result["turns"]]
        assert roles == ["user", "model", "user", "model"]

    def test_fallback_strategy_for_empty_page(self, page, mock_server):
        """Pages with no recognized elements fall back to main content."""
        page.goto(f"{mock_server}/gemini_conv_empty.html")
        from aishell.commands.gemini import _extract_conversation

        result = _extract_conversation(page)
        # Should use fallback-main strategy
        assert result["strategy"] == "fallback-main"
        assert result["count"] == 1


class TestExpandSidebar:
    def test_finds_menu_button(self, page, mock_server):
        page.goto(f"{mock_server}/gemini_app.html")
        from aishell.commands.gemini import _expand_sidebar

        found = _expand_sidebar(page)
        assert found is True
