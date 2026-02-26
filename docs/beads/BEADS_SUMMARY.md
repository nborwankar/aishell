# Steve Yegge's Beads Framework — Summary

**Date**: 2026-02-20
**Source**: github.com/steveyegge/beads (v0.52.0, ~225k lines of Go)

## What Is It?

Beads (`bd`) is a **git-backed issue tracker and persistent memory system** designed specifically for AI coding agents. Created by Steve Yegge, it solves the "50 First Dates" problem: AI agents have no memory between sessions.

Without Beads, agents create conflicting markdown files — competing, obsolete TODO lists that cause "agent dementia." Beads externalizes task state into a structured, dependency-aware, git-backed graph that survives session boundaries.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Your Project Repo                  │
│                                                      │
│  .beads/                                             │
│  ├── issues.jsonl   ← git-tracked, one line/issue   │
│  └── db/            ← Dolt SQL database (local)     │
│                                                      │
│  bd ready --json  → structured work items for agent  │
│  bd sync          → export → git commit → push       │
└─────────────────────────────────────────────────────┘
```

### Dual Storage
- **Dolt database** (version-controlled SQL): Source of truth, fast local queries, cell-level merge
- **JSONL file** (`.beads/issues.jsonl`): Git-tracked sync layer, clean diffs, human-readable

### Key Concepts
- **Hash-based IDs** (e.g., `bd-a1b2`) — no collisions across branches/agents
- **Hierarchical epics**: `bd-a3f8` → `bd-a3f8.1` → `bd-a3f8.1.1` (arbitrary nesting)
- **4 dependency types**: blocks, parent-child, related, discovered-from
- **Memory compaction**: Semantic decay summarizes old closed tasks to save context
- **Modes**: Standard, Stealth (local-only), Contributor (separate planning repo)

## Key Commands

| Command | Purpose |
|---------|---------|
| `bd init` | Initialize in a project |
| `bd setup claude` | Configure for Claude Code |
| `bd create "Title" -p 0 -t task` | Create a task |
| `bd create "System" -t epic -p 1` | Create an epic |
| `bd ready` | List unblocked tasks |
| `bd ready --json` | JSON output for agents |
| `bd update <id> --claim` | Assign + mark in-progress |
| `bd close <id> --reason "Done"` | Close an issue |
| `bd dep add <child> <parent>` | Create dependency |
| `bd dep tree <id>` | View dependency tree |
| `bd sync` | Export/import/commit/push |
| `bd doctor --fix` | Health check + auto-fix |
| `bd blocked` | Show blocked issues |
| `bd stats` | Progress statistics |

## Agent Integration

Beads provides structured JSON output so agents don't parse markdown:
```bash
bd ready --json    # Definitive list of unblocked work
```

### Supported Agents
- **Claude Code** (primary — via `bd setup claude` or MCP plugin)
- Cursor IDE, Aider, Codex CLI, AMP, any file-reading agent

### Claude Code Integration
- Slash commands: `/beads:init`, `/beads:create`, `/beads:ready`, `/beads:update`
- MCP server exposes ~10 primary tools
- Install: `bd setup claude`

## Recommended Workflow (Hybrid)

1. **Brainstorm** to understand scope
2. **Create structured issues** with acceptance criteria
3. **Execute** via `bd ready` loop
4. **Land the plane** at session end:
   - File remaining work as Beads issues
   - Run quality gates (tests, lints, builds)
   - Update Beads issues (close finished, update status)
   - `git pull --rebase && bd sync && git push`
   - Clean git state

## Why It Matters for This Workflow

Current system uses CLAUDE.md + DONE.md + NEXT_SESSION.md + TODO.md for session continuity.
Beads replaces/augments this with:
- **Structured task tracking** with dependencies (vs flat markdown)
- **Cross-session memory** that agents query programmatically (`bd ready --json`)
- **Git-native** — tasks live in the repo, travel with branches
- **Multi-agent safe** — hash IDs prevent collision

## Related: Gas Town (Advanced)

Yegge's multi-agent orchestration framework built on Beads. Enables 20-30 parallel AI agents
with structured hierarchy (Mayor, Crew, Polecats, Witness). For future exploration.

## References

- GitHub: https://github.com/steveyegge/beads
- Blog: https://steve-yegge.medium.com/ (search "beads")
- Best practices: https://steve-yegge.medium.com/beads-best-practices-2db636b9760c
- Gas Town: https://github.com/steveyegge/gastown
