# Next Session — aishell

**Date**: 2026-02-20
**Branch**: main
**Last commit**: 588de81 (docs: Expand Dolt explainer with architecture, MySQL fork Q&A, and SQLite alternative analysis)

## What Was Done This Session

1. **Beads framework installed** — `bd` v0.55.3 built from source with CGO+ICU. Binary at `~/.local/bin/bd`.
2. **Claude Code integration** — `bd setup claude` hooks (SessionStart + PreCompact), global CLAUDE.md updated with Beads workflow.
3. **aishell initialized as Beads pilot** — `bd init --prefix aishell`, 2 epics + 7 tasks with dependencies.
4. **Beads skill created** — `~/.claude/skills/beads/SKILL.md` for English → `bd` command translation.
5. **Safety hook** — `bd sync` blocked by PreToolUse hook; `--no-push` and `--force` allowed.
6. **5 Beads docs** — summary, practical reference, Dolt deep-dive, cheatsheet, integration plan.

## Key Commits (this session)

- `1dbeee3` — docs: Add Beads framework integration and reference docs
- `588de81` — docs: Expand Dolt explainer with architecture, MySQL fork Q&A, and SQLite alternative analysis

## Beads State

Run `bd ready` to see what's actionable. Current issues:

```
aishell-024 [epic P1] Conversation Browser TUI + -c flag
  ├── aishell-4bq [P0] Add -c flag to aisearch          ← READY
  ├── aishell-rco [P0] DB helpers for TUI                ← READY (after epic unblocked)
  ├── aishell-6xa [P1] Build Textual TUI                 ← blocked by rco
  ├── aishell-lu8 [P1] Search integration in TUI         ← blocked by 6xa
  └── aishell-p9o [P2] Keyboard shortcuts + filters      ← blocked by 6xa

aishell-zvi [epic P2] Unified aisearch CLI
  ├── aishell-e2v [P1] -f file search flag               ← blocked by epic
  └── aishell-bii [P1] -w web search flag                ← blocked by epic
```

## What's Next

### Immediate — Beads Phase 5
- Initialize Beads in other hot projects (strictRAG, n2, etc.)
- Use `bd init --stealth` for repos where you don't want .beads/ committed

### Immediate — ChatGPT Reimport (from previous session)
- Run `aishell chatgpt reimport` on full 811 conversations
- Delete chatgpt rows from PostgreSQL, re-run `aishell conversations load`

### Planned — aishell features (now tracked in Beads)
- Claim `aishell-024` epic, start with `aishell-4bq` (-c flag)
- All feature work now tracked via `bd ready` / `bd close`

## Key Files
- `~/.claude/skills/beads/SKILL.md` — Beads skill (not in git, lives in Claude config)
- `~/.claude/settings.json` — hooks including bd sync blocker
- `docs/BEADS_*.md` — all Beads documentation (5 files)
- `.beads/` — Beads database and config
