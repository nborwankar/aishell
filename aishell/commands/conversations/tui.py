"""Textual TUI for browsing and searching conversations."""

import psycopg2
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)
from textual.message import Message
from rich.markup import escape
from rich.text import Text

from .db import (
    DB_NAME,
    list_conversations,
    get_conversation_turns,
    search_conversations_by_keyword,
)


class TurnViewer(Static):
    """Scrollable viewer for conversation turns."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._turns = []
        self._title = ""

    def show_conversation(self, title, turns):
        self._title = title
        self._turns = turns
        self._render_turns()

    def clear(self):
        self._turns = []
        self._title = ""
        self.update("[dim]Select a conversation to view[/dim]")

    def _render_turns(self):
        if not self._turns:
            self.update("[dim]Select a conversation to view[/dim]")
            return

        text = Text()
        text.append(self._title, style="bold blue")
        text.append(f"\n{len(self._turns)} turns\n\n", style="dim")

        for turn_number, role, content in self._turns:
            if role == "user":
                role_style = "bold cyan"
            elif role == "assistant":
                role_style = "bold green"
            else:
                role_style = "bold yellow"

            text.append(f"── {role} (turn {turn_number}) ──\n", style=role_style)
            # Use Text.append (no markup parsing) so raw content with
            # brackets like [Download JSON] doesn't cause MarkupError
            if len(content) > 3000:
                text.append(content[:3000])
                text.append("\n... (truncated)\n\n", style="dim")
            else:
                text.append(content)
                text.append("\n\n")

        self.update(text)


class ConversationBrowser(App):
    """Browse and search conversations from all LLM providers."""

    TITLE = "AIShell Conversation Browser"

    CSS = """
    #main {
        height: 1fr;
    }
    #sidebar {
        width: 40;
        border-right: solid $accent;
    }
    #sidebar-label {
        padding: 0 1;
        background: $accent;
        color: $text;
        text-style: bold;
    }
    #conv-list {
        height: 1fr;
    }
    #viewer-container {
        width: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }
    #turn-viewer {
        width: 1fr;
    }
    #search-bar {
        dock: bottom;
        height: 3;
        padding: 0 1;
    }
    #stats {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("slash", "open_search", "Search", key_display="/"),
        Binding("escape", "clear_search", "Clear", show=False),
        Binding("1", "filter_gemini", "Gemini", key_display="1"),
        Binding("2", "filter_chatgpt", "ChatGPT", key_display="2"),
        Binding("3", "filter_claude", "Claude", key_display="3"),
        Binding("0", "filter_all", "All", key_display="0"),
    ]

    def __init__(self, db_name=DB_NAME, source_filter=None):
        super().__init__()
        self.db_name = db_name
        self.source_filter = source_filter
        self._conversations = []
        self._search_query = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            with Vertical(id="sidebar"):
                yield Label("Conversations", id="sidebar-label")
                yield ListView(id="conv-list")
            with Vertical(id="viewer-container"):
                yield TurnViewer(id="turn-viewer")
        yield Label("", id="stats")
        yield Input(placeholder="Search conversations...", id="search-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search-bar", Input).display = False
        self._load_conversations()

    def _get_conn(self):
        return psycopg2.connect(dbname=self.db_name)

    def _load_conversations(self):
        conn = self._get_conn()
        try:
            self._conversations = list_conversations(conn, source=self.source_filter)
        finally:
            conn.close()
        self._populate_list(self._conversations)

    def _search_conversations(self, query):
        conn = self._get_conn()
        try:
            rows = search_conversations_by_keyword(
                conn, query, source=self.source_filter, limit=100
            )
        finally:
            conn.close()
        # Convert to same format as list_conversations:
        # (source, source_id, title, model, created_at, turn_count)
        # from search result: (title, source, source_id, hits, turn_count)
        conv_rows = [
            (src, sid, title, None, None, turn_count)
            for title, src, sid, hits, turn_count in rows
        ]
        self._conversations = conv_rows
        self._populate_list(
            conv_rows,
            search_query=query,
            hit_data={(src, sid): hits for title, src, sid, hits, turn_count in rows},
        )

    def _populate_list(self, conversations, search_query=None, hit_data=None):
        list_view = self.query_one("#conv-list", ListView)
        list_view.clear()

        source_counts = {"gemini": 0, "chatgpt": 0, "claude": 0}
        for row in conversations:
            source = row[0]
            source_counts[source] = source_counts.get(source, 0) + 1

        for i, row in enumerate(conversations):
            source, source_id, title, model, created_at, turn_count = row
            src_badge = {
                "gemini": "[magenta]gem[/magenta]",
                "chatgpt": "[green]gpt[/green]",
                "claude": "[cyan]cld[/cyan]",
            }.get(source, source)
            display_title = title or "Untitled"
            if len(display_title) > 30:
                display_title = display_title[:28] + ".."

            label = f"{src_badge} {display_title} [dim]({turn_count}t)[/dim]"
            if hit_data and (source, source_id) in hit_data:
                hits = hit_data[(source, source_id)]
                label += f" [yellow]{hits}h[/yellow]"

            list_view.append(ListItem(Label(label), name=f"{i}"))

        # Update stats
        total = len(conversations)
        filter_text = f"[{self.source_filter}]" if self.source_filter else "all"
        search_text = f' matching "{search_query}"' if search_query else ""
        stats = f" {total} conversations ({filter_text}){search_text}"
        stats += f"  |  gem:{source_counts['gemini']} gpt:{source_counts['chatgpt']} cld:{source_counts['claude']}"
        self.query_one("#stats", Label).update(stats)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        idx = int(event.item.name)
        if idx < len(self._conversations):
            row = self._conversations[idx]
            source, source_id, title = row[0], row[1], row[2]
            conn = self._get_conn()
            try:
                turns = get_conversation_turns(conn, source, source_id)
            finally:
                conn.close()
            viewer = self.query_one("#turn-viewer", TurnViewer)
            viewer.show_conversation(title or "Untitled", turns)

    def action_open_search(self) -> None:
        search_bar = self.query_one("#search-bar", Input)
        search_bar.display = True
        search_bar.value = ""
        search_bar.focus()

    def action_clear_search(self) -> None:
        search_bar = self.query_one("#search-bar", Input)
        if search_bar.display:
            search_bar.display = False
            self._search_query = None
            self._load_conversations()
            return
        # If search is not visible, escape should unfocus
        self.query_one("#conv-list", ListView).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        search_bar = self.query_one("#search-bar", Input)
        search_bar.display = False
        if query:
            self._search_query = query
            self._search_conversations(query)
        else:
            self._search_query = None
            self._load_conversations()
        self.query_one("#conv-list", ListView).focus()

    def action_filter_gemini(self) -> None:
        self.source_filter = "gemini"
        self._reload()

    def action_filter_chatgpt(self) -> None:
        self.source_filter = "chatgpt"
        self._reload()

    def action_filter_claude(self) -> None:
        self.source_filter = "claude"
        self._reload()

    def action_filter_all(self) -> None:
        self.source_filter = None
        self._reload()

    def _reload(self):
        if self._search_query:
            self._search_conversations(self._search_query)
        else:
            self._load_conversations()
        viewer = self.query_one("#turn-viewer", TurnViewer)
        viewer.clear()
