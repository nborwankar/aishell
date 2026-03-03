# Task Planner Skill — Design Document

**Date**: 2026-03-03
**Status**: Approved
**Context**: Claude Code skill that abstracts beads infrastructure behind a managed task layer, mapping features and outcomes to atomic subtasks without requiring direct `bd` commands.

---

## Problem

Beads (`bd`) is a powerful git-backed issue tracker, but it's **leaky infrastructure** — the user has to manually create, close, and manage issues. This is like manual memory management: it works, but it's overhead that should be handled by the runtime.

The user thinks in **features and outcomes**. The agent should handle the decomposition into tasks and atomic subtasks (beads), just like Java's GC handles malloc/free.

## Design Principle

```
┌─────────────────────────────────────────────────────┐
│              You (features & outcomes)               │
├─────────────┬─────────────────┬─────────────────────┤
│  Mode A     │  Mode B         │  Mode C             │
│  /plan      │  /propagate     │  /track             │
│  Decompose  │  Cross-project  │  Transparent sync   │
├─────────────┴─────────────────┴─────────────────────┤
│              Beads (invisible infrastructure)         │
│              bd create, bd close, bd dep             │
└─────────────────────────────────────────────────────┘
```

The three modes are not alternatives — they're different interaction patterns used depending on the nature and size of the work. The agent adapts, or the user can nudge with an explicit command.

## Hierarchy

```
Session (time-bounded frame)
  ├─ resume-work    ← reads context, shows what's available
  └─ end-session    ← saves state, commits

Task (what you're working on)                    ← THIS SKILL
  ├─ Feature/Outcome  →  Epic in beads
  ├─ TODO             →  Task in beads
  └─ Subtask          →  Task with dependency in beads

Beads (invisible infrastructure)
  └─ bd create, bd close, bd dep — never touched directly
```

Session skills stay separate. The existing `beads` skill stays as a raw escape hatch. This skill owns the managed layer in between.

---

## Mode A: `/plan` — Decompose

**Trigger**: `/plan "hybrid search for aishell"` or any big-picture feature/experiment description.

### Flow

```
You: /plan "hybrid search for aishell"
          │
Skill:    ├─ 1. Read project context (CLAUDE.md, bd ready, recent commits)
          ├─ 2. Ask 1-2 clarifying questions (scope, success criteria)
          ├─ 3. Propose decomposition:
          │
          │    Epic: "Hybrid search for aishell"
          │    ├─ Task 1: Add keyword ILIKE fallback to search query (P1)
          │    ├─ Task 2: Merge semantic + keyword results with dedup (P1)
          │    ├─ Task 3: Add Match column to output table (P2)
          │    └─ Task 4: Update aisearch CLI flags (P2)
          │    Deps: T2 blocked by T1, T3 blocked by T2
          │
          ├─ 4. You approve / adjust
          └─ 5. Skill runs bd create + bd dep add (you never see these)
```

### Rules

- Tasks must be **one-context-window sized** (Ralph-loop compatible)
- Each task gets a concrete **done-when** in its description (testable where possible)
- Decomposition is saved to `.beads/plans/YYYY-MM-DD-<topic>.md`
- If the project doesn't have `.beads/`, skill offers `bd init` first

### Research/Experiment Variant

When the work is exploratory (no clear task list up front):

- Skill creates a lighter structure: one epic + 2-3 exploration tasks
- Tasks are phrased as questions: "Can Spearman exceed 0.40 with sphere manifold?"
- Done-when is a proxy signal: "results.json exists with ≥ 3 configs tested"

---

## Mode B: `/propagate` — Cross-Project

**Trigger**: Explicitly via `/propagate`, or auto-triggered when the skill detects you're building a tool/library with downstream consumers.

### Auto-Detection Signals

- Project has `setup.py` or `pyproject.toml` with a package name
- Version number is being bumped
- Conversation mentions other projects needing this work

### Flow

```
You: /propagate
  or: "ship embedding_tools v0.1.3 with the new batch API"
          │
Skill:    ├─ 1. Identify current project as source (embedding_tools)
          ├─ 2. Scan consumer projects for imports/usage:
          │     grep across ~/Projects/github/{aishell,n2,strictRAG,...}
          │     for "import embedding_tools" or "from embedding_tools"
          │
          ├─ 3. Propose integration tasks per consumer:
          │
          │     Source: embedding_tools
          │     ├─ Task: "Ship v0.1.3 with batch API" (P1)
          │     │
          │     Downstream:
          │     ├─ aishell: "Update to embedding_tools v0.1.3" (P2)
          │     │   done-when: imports updated, tests pass
          │     ├─ n2: "Update to embedding_tools v0.1.3" (P2)
          │     │   done-when: imports updated, search still works
          │     └─ strictRAG: "Evaluate new batch API for VQL" (P3)
          │         done-when: comparison doc written
          │
          ├─ 4. You approve / prune
          └─ 5. Creates beads in each project that has .beads/
                For non-beads projects, logs a reminder instead
```

### Rules

- Only creates beads in projects that have `.beads/` initialized
- Consumer discovery uses grep on actual imports — no guesswork
- Propagation map saved to `.beads/plans/YYYY-MM-DD-propagate-<topic>.md`
- Cross-project beads can't formally depend on each other (beads is per-repo), so the plan doc is the linkage

### Scatter-Gather Connection

Mode B's output is essentially a scatter-gather config. The propagation map could feed directly into a ccli TOML for parallel execution — but that's future work, not MVP.

---

## Mode C: `/track` — Transparent Sync

**Trigger**: `/track`, or "update tracking files", or "commit this" at a natural stopping point.

### Flow

```
You: /track
  or: "update tracking files and commit"
          │
Skill:    ├─ 1. Gather what happened:
          │     - git diff --staged + git diff (what changed)
          │     - git log since last /track (recent commits)
          │     - Conversation context (what was discussed)
          │     - bd list --status=in_progress (what's claimed)
          │
          ├─ 2. Propose beads updates:
          │
          │     Close:
          │       ✓ aishell-4bq "Add -c flag to aisearch"
          │         evidence: cli.py now has --conversations flag
          │       ✓ aishell-rco "DB helpers for TUI"
          │         evidence: db.py has new query functions
          │
          │     New:
          │       + "Fix pagination bug in search results" (P1, bug)
          │         discovered during implementation
          │       + "Add tests for -c flag" (P2, task)
          │
          │     Still open (no action):
          │       ○ aishell-6xa "Build Textual TUI" — not started
          │
          ├─ 3. You approve / adjust
          ├─ 4. Skill runs bd close / bd create (invisible)
          ├─ 5. Updates DONE.md if milestone-worthy
          └─ 6. Git commit with descriptive message
```

### Rules

- **Always proposes, never auto-closes.** Every beads mutation needs user approval. This is managed GC — it collects, you approve the sweep.
- **Evidence-based**: skill must point to specific file changes or conversation context that justify closing a bead. No guessing.
- Creates new beads for work discovered during implementation (bugs, missing tests, ideas).
- Keeps DONE.md for milestone narrative — beads tracks atomic tasks, DONE.md tracks the story.
- Approve step is lightweight — yes/no on the batch, or line-item edits.

### Evolution Path

Once the user trusts the inference (after N sessions of approving proposals), Mode C could become a git hook that fires on commit. But that's opt-in later, not default.

---

## The Learning Log

All three modes write to `.beads/plans/`:

```
.beads/plans/
├── 2026-03-03-hybrid-search.md          # Mode A decomposition
├── 2026-03-04-propagate-embtools.md     # Mode B propagation map
└── 2026-03-04-track-session.md          # Mode C inference log
```

### What Gets Logged

- Feature → tasks → beads mapping (Mode A)
- Source → consumer → integration tasks (Mode B)
- Evidence → close/create decisions (Mode C)

### Why This Matters for Contribution

- Logs become training data for better decomposition heuristics
- "How did similar features get broken down?" is answerable
- Other developers adopting the skill get a library of decomposition patterns
- Logs are git-tracked — they travel with the project

---

## Prerequisites

- `bd` binary on PATH (`~/.local/bin/bd`)
- `.beads/` initialized in the project (`bd init --prefix <name>`)
- Skill auto-checks both and offers setup if missing

## Relationship to Existing Skills

| Skill | Status | Relationship |
|-------|--------|-------------|
| `beads` | Stays | Raw escape hatch — direct `bd` commands |
| `resume-work` | Stays | Session framing, reads context |
| `end-session` | Stays | Session framing, saves state |
| `update-done` | Stays | DONE.md narrative (Mode C calls this for milestones) |
| `task-planner` | **New** | Managed layer between user and beads |

## Future Evolution

1. **MVP (now)**: Claude Code skill with three modes
2. **Phase 2**: Standalone CLI wrapper (Mode C as a hook, scriptable)
3. **Phase 3**: ccli integration (Mode B feeds scatter-gather TOML configs)

---

## References

- [Beads Value Proposition](../dev/BEADS_VALUE_PROPOSITION.md)
- [Scatter-Gather & Ralph Loop Patterns](../dev/SCATTER_GATHER_AND_RALPH_LOOP.md)
- [Beads Practical Reference](../beads/BEADS_PRACTICAL_REFERENCE.md)
