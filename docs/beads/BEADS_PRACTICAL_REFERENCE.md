# Beads (`bd`) — Practical Command Reference

**Date**: 2026-02-20
**Version**: v0.55.3 (built from source with CGO+ICU)
**Install location**: `~/.local/bin/bd`

## What it is underneath

A **local SQL database** (Dolt) living in `.beads/` inside your project, plus a `.beads/issues.jsonl` file that gets committed to git. The database is your fast local query engine; the JSONL is how tasks travel with your repo.

## Commands you'll use daily

### See what needs doing

```bash
bd ready              # Tasks with zero blockers — your "what's next" list
bd ready --json       # Same but structured JSON (for agents)
bd list               # ALL issues, with status and dependency info
bd list --status=open # Just open ones
```

### Create work items

```bash
bd create "Fix the search bug" -t bug -p 0          # Bug, critical priority
bd create "Add export feature" -t task -p 1          # Task, high priority
bd create "Auth system redesign" -t epic -p 1        # Epic (container for sub-tasks)
```

- Types: `bug`, `task`, `feature`, `epic`, `chore`
- Priorities: `0` critical → `4` backlog (default is `2`)
- Add `--description "details here"` for longer context

### Work on something

```bash
bd update aishell-4bq --status in_progress   # Claim it
bd update aishell-4bq --claim                # Shorthand for same thing
```

### Finish something

```bash
bd close aishell-4bq                         # Mark done
bd close aishell-4bq --reason "Implemented in commit abc123"  # With context
```

### Dependencies (the killer feature)

```bash
bd dep add CHILD PARENT              # CHILD is blocked until PARENT closes
bd dep tree aishell-024              # Show the dependency tree
bd blocked                           # List everything that's stuck
```

### Sync with git

```bash
bd sync                              # Export DB → JSONL, git commit, push
bd sync --no-push                    # Export + commit but NO push
```

## Things that might surprise you

1. **`bd sync` will `git push`** — it commits `.beads/` and pushes. Use `bd sync --no-push` or commit `.beads/` manually if you don't want auto-push.

2. **IDs are hashes, not numbers** — `aishell-4bq` not `#1`. Prevents collisions across branches.

3. **`bd prime` dumps a wall of text** — meant for agents to consume, not humans. The Claude Code hooks run this silently.

4. **`bd edit` opens an interactive editor** — fine for humans, agents can't use it. Use `bd update <id> --description "new text"` for programmatic edits.

5. **Closing an epic doesn't auto-close children** — close tasks individually.

6. **`.beads/` directory gets committed to git** — JSONL goes into your repo. Use `bd init --stealth` to gitignore it instead.

7. **No undo** — writes are immediate. You can reopen (`bd update <id> --status open`) but there's no `bd undo`.

## Commands you probably won't need yet

| Command | What it does |
|---------|-------------|
| `bd doctor --fix` | Diagnose/repair DB issues |
| `bd hooks install` | Git hooks for auto-sync on commit/merge |
| `bd todo` | Lightweight scratch tasks (separate from issues) |
| `bd promote` | Promote a `bd todo` into a full issue |
| `bd config` | View/set config keys |

## Issue Types

- `bug` — Something broken
- `feature` — New functionality
- `task` — Work item (tests, docs, refactoring)
- `epic` — Large feature with subtasks
- `chore` — Maintenance (dependencies, tooling)

## Priorities

- `0` — Critical (security, data loss, broken builds)
- `1` — High (major features, important bugs)
- `2` — Medium (default, nice-to-have)
- `3` — Low (polish, optimization)
- `4` — Backlog (future ideas)

## Init modes

```bash
bd init                    # Standard — .beads/ tracked in git
bd init --stealth          # Local-only — .beads/ gitignored
bd init --contributor      # Separate planning repo (~/.beads-planning)
bd init --prefix myproject # Custom issue prefix (default: dir name)
```

## Current state (aishell pilot)

```
bd ready   → 2 epics ready to start
bd list    → 9 total issues (2 epics, 7 tasks)
bd stats   → 0 closed, 9 open, 7 blocked
```
