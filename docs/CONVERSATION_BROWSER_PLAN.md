# Conversation Browser TUI + `-c` Flag — Plan

**Status**: Planned (not yet implemented)
**Created**: 2026-02-13

## Context

Two features requested:
1. **`-c` flag on `aisearch`** — conversation-level keyword search (list conversations containing a term, not individual chunks)
2. **Textual TUI conversation browser** — interactive terminal app for browsing and searching conversations

Current state: `aisearch` does chunk-level hybrid search (semantic + keyword). User wants to also find *which conversations* contain a term, and browse them interactively.

## Part 1: `-c` Flag (Simple, No New Dependencies)

Add `-c` / `--conversations` flag to `aisearch`. Returns conversation-level results grouped by (source, source_id, title) with hit count.

### SQL

```sql
SELECT c.title, c.source, c.source_id, COUNT(*) AS hits
FROM chunk_embeddings ce
JOIN conversations_raw c ON ce.source = c.source AND ce.source_id = c.source_id
WHERE ce.chunk_text ILIKE %s OR c.title ILIKE %s
  [AND c.source = %s]
GROUP BY c.title, c.source, c.source_id
ORDER BY hits DESC
LIMIT %s
```

### Output

```
aisearch "flatoon" -c

Conversations containing "flatoon": 1

Title                              Src     Hits
Neural Network Diffusion Expla     gemini  47
```

### Files
- `commands/conversations/cli.py` — add `-c` flag + conversation-level query branch

## Part 2: Textual TUI Browser

### Dependencies
- `textual>=0.50.0` (built on Rich, which is already installed)

### Entry Point

```bash
aishell conversations browse              # launch TUI
aishell conversations browse -s gemini    # pre-filter by source
```

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│  AIShell Conversation Browser           [/] Search  [q] Quit │
├──────────────────────┬───────────────────────────────────────┤
│ Conversations (1764) │ Turn 3/47  [assistant]                │
│ ─────────────────── │                                       │
│ > Boids Flocking S.. │ I'll create a boids simulation for    │
│   Calculus on Manif. │ you. Boids is a classic artificial    │
│   Flatoon Engine D.. │ life program that simulates flocking  │
│   Format document s. │ behavior.                             │
│   Fourier Transform. │                                       │
│   Grassmann manifol. │ Here's what I've created:             │
│   Grassmannians and. │ - A fully interactive boids           │
│   Hyperbolic Geomet. │   simulation with adjustable          │
│   Hyperbolic Geomet. │   parameters                          │
│   IEEE to PandaPowe. │ - The simulation implements the       │
│                      │   three classic boid rules:            │
│ [gemini] 33          │   cohesion, alignment, separation     │
│ [chatgpt] 811        │                                       │
│ [claude] 920         │                                       │
├──────────────────────┴───────────────────────────────────────┤
│ Search: boids                                     3 matches  │
└──────────────────────────────────────────────────────────────┘
```

### Screens / Modes

1. **Conversation List** (left panel, default focus)
   - Sorted alphabetically by title (default)
   - Sortable by: title, source, date, turn count
   - Filterable by source (gemini/chatgpt/claude)
   - Shows: title (truncated), source badge, turn count

2. **Turn Viewer** (right panel)
   - Shows turns for selected conversation
   - Role-colored (user=cyan, assistant=white)
   - Scrollable with j/k or arrow keys
   - Markdown rendering for assistant responses

3. **Search Mode** (bottom bar, activated by `/`)
   - Type query -> runs conversation-level keyword search (same SQL as `-c`)
   - Results replace conversation list (filtered view)
   - Enter on result -> opens that conversation in turn viewer
   - Esc -> back to full list

### Keyboard Shortcuts

```
Navigation:
  j/down      Next conversation / scroll down
  k/up        Previous conversation / scroll up
  Enter       Open conversation in turn viewer
  Esc/q       Back / quit
  Tab         Switch focus between panels

Search:
  /           Open search bar
  Enter       Execute search
  Esc         Cancel search, return to list

Filtering:
  1           Filter: gemini only
  2           Filter: chatgpt only
  3           Filter: claude only
  0           Clear filter (show all)

View:
  t           Sort by title
  d           Sort by date
  n           Sort by turn count
```

### DB Helpers Needed (add to db.py)

```python
def list_conversations(conn, source=None, limit=None):
    """Return (source, source_id, title, model, created_at, turn_count)."""

def get_conversation_turns(conn, source, source_id):
    """Return ordered turns from JSONB."""

def search_conversations_by_keyword(conn, query, source=None, limit=20):
    """Return conversations containing keyword, with hit count."""
```

### Files to Create/Modify

| File | Change |
|------|--------|
| `commands/conversations/tui.py` | **NEW** -- Textual App, ConversationList, TurnViewer, SearchBar |
| `commands/conversations/db.py` | Add 3 query helpers above |
| `commands/conversations/cli.py` | Add `browse` subcommand, add `-c` flag to `search` |
| `setup.py` | Add `textual>=0.50.0` |
| `requirements.txt` | Add `textual>=0.50.0` |

### Implementation Order

1. `-c` flag on `aisearch` (standalone, no Textual needed)
2. DB helper functions in `db.py`
3. Basic TUI with conversation list + turn viewer
4. Search integration in TUI
5. Keyboard shortcuts and polish

### Verification

1. `aisearch "flatoon" -c` -> shows 1 conversation with hit count
2. `aisearch "Riemannian" -c` -> multiple conversations across providers
3. `aishell conversations browse` -> TUI launches, lists 1764 conversations
4. `/flatoon` in TUI -> filters to matching conversations
5. Enter on conversation -> shows turns in right panel
6. `1`/`2`/`3` -> source filtering works
7. `q` -> clean exit
