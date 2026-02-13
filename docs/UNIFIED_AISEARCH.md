# Unified `aisearch` CLI — Design Plan

**Status**: Planned (not yet implemented)
**Created**: 2026-02-12

## Overview

Extend `aisearch` from a conversations-only shortcut into a unified search
entry point. The search mode is determined by flags; conversations (hybrid
semantic + keyword) remains the default.

## CLI Design

```
aisearch "query"                        # conversations (default)
aisearch "query" -s gemini -l 5         # conversations with source filter
aisearch "query" -f                     # file search (Spotlight, cwd)
aisearch "query" -f ~/Projects          # file search in specific dir
aisearch "query" -w                     # web search (default engine)
aisearch "query" -w duckduckgo          # web search (specific engine)
```

## Flag Matrix

```
Flag          Meaning                   Default Value
──────────────────────────────────────────────────────
(none)        Conversation search       hybrid semantic+keyword
-s SOURCE     Conversation source       all providers
-l LIMIT      Max results               10
-f [DIR]      File search mode          cwd if no dir given
-w [ENGINE]   Web search mode           google
--db NAME     Database name             conversation_export
```

## Mode Resolution

```
┌──────────────────────────────────┐
│         aisearch "query"         │
└──────────┬───────────────────────┘
           │
     ┌─────▼─────┐
     │  -f flag?  │──yes──► File search (Spotlight/find)
     └─────┬─────┘         in DIR or cwd
           │ no
     ┌─────▼─────┐
     │  -w flag?  │──yes──► Web search (Google/DDG/HN)
     └─────┬─────┘         via ENGINE
           │ no
     ┌─────▼─────┐
     │  Default   │──────► Conversation search
     └───────────┘         hybrid semantic + keyword
```

Flags `-f` and `-w` are mutually exclusive. If both are passed, error out
with a clear message.

## Implementation Notes

### -f (File Search)

Delegates to existing `MacOSFileSearcher` from `aishell/search/file_search.py`.

- `-f` with no value → search cwd
- `-f ~/Projects` → search specified directory
- `-l` reused for max results
- Could add `--content` flag for grep-style content search within matched files

### -w (Web Search)

Delegates to existing `perform_web_search` from `aishell/search/web_search.py`.

- `-w` with no value → default engine (google or hackernews based on config)
- `-w duckduckgo` → specific engine
- `-l` reused for max results
- `--show-browser` could be carried over for debugging

### Default (Conversation Search)

Current implementation — no changes needed. Already supports `-s`, `-l`, `--db`.

## Click Implementation Sketch

```python
@click.command()
@click.argument("query", nargs=-1, required=True)
@click.option("-l", "--limit", type=int, default=10, help="Max results")
@click.option("-s", "--source", type=click.Choice(["gemini", "chatgpt", "claude"]),
              help="Filter conversations by provider")
@click.option("-f", "--file", "file_dir", is_flag=False, flag_value=".",
              default=None, help="File search mode (optional: dir path)")
@click.option("-w", "--web", "web_engine", is_flag=False, flag_value="google",
              default=None, help="Web search mode (optional: engine name)")
@click.option("--db", default="conversation_export", help="Database name")
def aisearch(query, limit, source, file_dir, web_engine, db):
    query_str = " ".join(query)

    if file_dir and web_engine:
        click.echo("Error: -f and -w are mutually exclusive", err=True)
        raise SystemExit(1)

    if file_dir:
        _file_search(query_str, file_dir, limit)
    elif web_engine:
        _web_search(query_str, web_engine, limit)
    else:
        _conversation_search(query_str, limit, source, db)
```

## Files to Modify

| File | Change |
|------|--------|
| `cli.py` | Replace `aisearch_main()` passthrough with unified dispatch |
| `setup.py` | Entry point unchanged (`aisearch=aishell.cli:aisearch_main`) |

No changes to search backends — they're already implemented.

## What We Keep

- `aishell search` → web search (existing, unchanged)
- `aishell find` → file search (existing, unchanged)
- `aishell spotlight` → Spotlight search (existing, unchanged)
- `aishell conversations search` → conversation search (existing, unchanged)
- `aisearch` → unified shortcut dispatching to all three
