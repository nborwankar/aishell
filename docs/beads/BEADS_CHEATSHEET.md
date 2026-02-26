# Beads Cheatsheet

## Setup

### Existing project
```bash
cd ~/Projects/github/myproject
bd init
```

### New project
```bash
git init
bd init
```

That's it. You now have Beads.

## Daily Use — 4 Commands

```bash
bd ready                        # "What should I work on?"
bd update <id> --claim          # "I'm starting this one"
bd close <id>                   # "Done with this one"
bd create "new thing" -t task   # "Oh, I also need to do this"
```

## Creating Work Items

```bash
bd create "Fix login bug" -t bug -p 0              # Critical bug
bd create "Add export feature" -t task -p 1         # High priority task
bd create "Auth system redesign" -t epic -p 1       # Big feature (has sub-tasks)
bd create "Update deps" -t chore -p 3               # Low priority maintenance
bd create "Dark mode" -t feature -p 2               # Medium priority feature
```

Add details:
```bash
bd create "Fix login bug" -t bug -p 0 --description "Crashes on empty password"
```

### Types
- `bug` — something broken
- `task` — work item
- `feature` — new functionality
- `epic` — big thing with sub-tasks
- `chore` — maintenance

### Priorities
- `0` — critical (fix now)
- `1` — high (do soon)
- `2` — medium (default)
- `3` — low (when you get to it)
- `4` — backlog (someday)

## Seeing Your Work

```bash
bd ready              # Only unblocked tasks (your "what's next")
bd list               # Everything with status and dependencies
bd list --status=open # Just open items
bd stats              # Summary counts
bd blocked            # What's stuck and why
```

## Dependencies

```bash
bd create "Build the API" -t task -p 1       # → abc-123
bd create "Build the UI" -t task -p 1        # → abc-456
bd dep add abc-456 abc-123                   # UI blocked until API done

bd ready                                      # Only shows API
# ... finish API ...
bd close abc-123
bd ready                                      # Now UI shows up

bd dep tree abc-123                           # See the dependency tree
```

## Updating Issues

```bash
bd update <id> --claim                        # Claim + mark in_progress
bd update <id> --status in_progress           # Just change status
bd update <id> --status open                  # Reopen something
bd update <id> --description "new details"    # Change description
bd update <id> -p 0                           # Escalate priority
```

## Closing Issues

```bash
bd close <id>                                 # Done
bd close <id> --reason "Fixed in commit abc"  # Done with context
```

## What You DON'T Need To Do

- Don't run `bd sync` (it pushes to remote)
- Don't maintain TODO.md (Beads replaces it)
- Don't write NEXT_SESSION.md (open issues carry over)
- Don't memorize all the flags (`bd create --help` when you forget)
- Don't use `bd edit` (opens interactive editor — use `bd update` instead)

## Quick Reference Card

```
┌─────────────────────────────────────────────┐
│            BEADS WORKFLOW                    │
│                                             │
│  Start session:   bd ready                  │
│  Claim work:      bd update <id> --claim    │
│  Do the work:     ...                       │
│  Finish:          bd close <id>             │
│  New task found:  bd create "..." -t task   │
│  End session:     bd ready  (check nothing  │
│                    fell through the cracks)  │
└─────────────────────────────────────────────┘
```
