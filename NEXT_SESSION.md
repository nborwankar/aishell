# NEXT_SESSION — aishell

**Date**: 2026-04-11
**Branch**: main
**Last commit**: 6ea94d9

## What Was Done This Session

1. **Directory cleanup**: Removed cruft dirs, moved webscraping from `usecases/` into `aishell/commands/webscraping/` as proper auto-discovered CLI plugin
2. **ChatGPT Projects API exploration**: Built CDP probe script, mapped the internal API for ChatGPT Projects (gizmos with `g-p-` prefix), discovered 5 projects with 24 conversations

## Current State

- Webscraping command works: `aishell webscraping navigate`
- Probe script at `scripts/probe_chatgpt_projects.py` (untracked, ready to commit)
- Playwright node driver is broken in base conda env — existing pull commands still work (they bypass it) but raw `sync_playwright()` fails
- API findings saved to memory (`reference_chatgpt_project_api.md`)

## Open Beads Issues (priority order)

```bash
bd ready   # See unblocked work
```

**P1:**
- `aishell-enr` — Fix Playwright node driver (broken in base conda env)

**P2:**
- `aishell-nav` — Add project field to conversation schema (blocks h05)
- `aishell-h05` — Add ChatGPT project metadata to pull command

**Existing epics:**
- `aishell-024` — Conversation Browser TUI + -c flag
- `aishell-zvi` — Unified aisearch CLI (-f file, -w web)

## Immediate Next Steps

1. Fix Playwright: `python -m playwright install` in base conda env
2. Implement `aishell-nav`: extend `convert_to_schema()` in `aishell/commands/conversations/schema.py` to include optional `project: {id, name}` field
3. Implement `aishell-h05`: after regular pull, scrape `g-p-*` IDs from sidebar HTML, fetch project metadata via `/backend-api/gizmos/{id}`, annotate matching conversations
4. Investigate Claude Projects API (same pattern — Claude conversations already have `project_uuid` + `project: {uuid, name}` in raw data)

## Key Files

- `aishell/commands/chatgpt.py` — ChatGPT pull command
- `aishell/commands/conversations/schema.py` — conversation JSON schema
- `aishell/commands/conversations/browser.py` — Chrome CDP helpers
- `scripts/probe_chatgpt_projects.py` — ChatGPT API probe script
- `aishell/commands/webscraping/cli.py` — new webscraping plugin

## Session Handoff

> Resume aishell — check NEXT_SESSION.md. Priority: fix Playwright driver (`aishell-enr`), then extend schema for project metadata (`aishell-nav`), then implement ChatGPT project pull (`aishell-h05`). API findings are in memory and in `scripts/probe_chatgpt_projects.py`.
