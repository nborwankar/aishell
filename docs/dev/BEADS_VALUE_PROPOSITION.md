# Beads Value Proposition: Why and When It Matters

**Date**: 2026-02-26
**Context**: Evaluating whether beads (Steve Yegge's git-backed issue tracker) justifies its overhead for a solo developer managing 10+ research/tool projects with Claude Code

---

## Current Workflow (Without Beads)

```
Start session:
  → read CLAUDE.md, DONE.md, TODO.md, NEXT_SESSION.md
  → "what's next?"

During work:
  → write code
  → "update tracking files and commit"
      → edit TODO.md (check things off, add new items)
      → edit DONE.md (log what was accomplished)
      → git commit

End session:
  → write NEXT_SESSION.md (handoff notes)
  → final commit
```

## With Beads Replacing the Task Layer

```
Start session:
  → bd ready                              # replaces reading TODO.md
  → bd show <id>                          # replaces reading NEXT_SESSION.md
  → read CLAUDE.md, DONE.md              # these stay

During work:
  → bd update <id> --status=in_progress   # claim task
  → write code
  → bd close <id>                         # replaces checking off TODO.md
  → bd create "found a bug" -t bug -p 1   # replaces adding to TODO.md
  → edit DONE.md (milestones)             # stays — narrative log
  → git commit                            # hooks auto-export .beads/

End session:
  → bd create "wire up search" -t task    # replaces NEXT_SESSION.md
  → git commit                            # open issues ARE the handoff
```

### What Beads Replaces vs What Stays

| File | With Beads | Without Beads |
|------|-----------|---------------|
| **DONE.md** | Keep — narrative milestone logs | Keep |
| **TODO.md** | Replaced by `bd list`/`bd ready` | Keep |
| **NEXT_SESSION.md** | Replaced — open issues persist automatically | Keep |
| **CLAUDE.md** | Keep — project instructions | Keep |

---

## Honest Assessment: Current Solo Workflow

For a solo developer using Claude Code sessions with "update tracking files and commit" as the primary pattern, **beads is mostly lateral**. You trade editing markdown for typing `bd` commands. Not turbo-charging anything.

### What Actually Costs Time Today

**Session startup tax.** Every new Claude session burns tokens and minutes reading DONE.md (can grow to 60KB+), TODO.md, NEXT_SESSION.md, CLAUDE.md to figure out "where was I?" Across 10+ projects, this is significant.

**Cross-project blindness.** Working on embedding_tools and vaguely remembering aishell and n2 need updates when you ship. That knowledge lives in your head or scattered across markdown files in different repos.

**Handoff decay.** NEXT_SESSION.md quality depends on how tired you were when you wrote it. Sometimes it's great, sometimes it's "continue working on search." The next session's agent has to guess.

---

## Where Beads Actually Changes Things

Not for tracking tasks in one project. For **making projects machine-readable across agents and sessions.**

### 1. Agent Cold-Start: Minutes → Seconds

```bash
# Current: agent reads 4 files, interprets prose, guesses priorities
# ~2000-5000 tokens just to orient

# With beads:
bd ready --json
# Returns structured: [{id, title, priority, type, dependencies}]
# Agent knows exactly what's unblocked and what to work on
```

This matters x10 when running scatter-gather or Ralph loops — those agents don't have you to interpret ambiguous markdown.

### 2. Cross-Project Dependencies Become Queryable

Right now "embedding_tools v0.1.3 needs to ship before aishell can update" lives nowhere durable. With beads in both projects:

```bash
# In embedding_tools:
bd create "Ship v0.1.3 with new batch API" -t task -p 1
# → embtools-abc

# In aishell:
bd create "Update to embedding_tools v0.1.3" -t task -p 2
# → aishell-xyz
# Structured tasks are grep-able, json-queryable across repos
```

### 3. Ralph Loops Can Self-Direct

A Ralph loop needs to know "what's next" without human guidance:

```bash
# ralph.sh (simplified)
while :; do
  NEXT=$(bd ready --json | jq -r '.[0].id')
  [ -z "$NEXT" ] && echo "All done" && break
  bd update $NEXT --status=in_progress
  cat PROMPT_TEMPLATE.md | sed "s/{{TASK}}/$(bd show $NEXT)/" | claude-code
  bd close $NEXT
done
```

TODO.md can't drive that loop. Beads can.

### 4. Scatter-Gather Gets a Task Queue

```toml
# Instead of hardcoding prompts in TOML:
[[instances]]
name = "aishell"
prompt = "Run bd ready, pick the highest-priority task, do it."
cwd = "~/Projects/github/aishell"
```

Each agent pulls from its own project's task queue, works it, closes it. The gather phase reads `bd list --status=closed` across repos to see what got done.

---

## The Decision Framework

```
Current workflow (solo + Claude Code)
  └─ beads ≈ TODO.md with extra steps (marginal benefit)

Future workflow (scatter-gather + Ralph loops + multi-agent)
  └─ beads = machine-readable task queue that agents
     can consume and update autonomously (significant benefit)
```

Beads isn't about making *you* faster at tracking tasks. It's about making your projects **legible to autonomous agents** — which is the direction of the ccli/scatter-gather work. The infrastructure investment pays off when agents outnumber you.

---

## Which Projects Should Get Beads

### Strong candidates

| Project | Why |
|---------|-----|
| **n2** | Most complex, most components (search, indexing, TUI), most likely to lose context between sessions |
| **embedding_tools** | Cross-project dependency hub — aishell, n2, strictRAG all consume it |
| **strictRAG** | Language implementation with natural task ordering (parse → execute → optimize) |
| **ccli** | Multi-phase feature work (scatter-gather) with clear task decomposition |

### Skip

| Project | Why |
|---------|-----|
| **sharpattention** | Pure research — experiments are exploratory, not task-shaped |
| **manopt** | Same — "what to do next" changes based on yesterday's results |
| **kurt** | Creative flow state, not structured task work |

### Criteria for opting in

- Multi-component with dependencies between parts
- Work spans many Claude Code sessions
- Tasks are definable ahead of time (not purely exploratory)
- Cross-project integration needs (other projects depend on it)
- Heading toward autonomous agent execution (Ralph loops, scatter-gather)

---

## Initialization (When Ready)

```bash
cd ~/Projects/github/n2 && bd init --prefix n2
cd ~/Projects/github/embedding_tools && bd init --prefix embtools
cd ~/Projects/github/strictRAG && bd init --prefix strictrag
cd ~/Projects/github/claudetools/ccli && bd init --prefix ccli
```

---

## References

- [Scatter-Gather & Ralph Loop Patterns](SCATTER_GATHER_AND_RALPH_LOOP.md) — companion doc
- [Beads Practical Reference](../beads/BEADS_PRACTICAL_REFERENCE.md) — command reference
- [Beads Cheatsheet](../beads/BEADS_CHEATSHEET.md) — quick reference
