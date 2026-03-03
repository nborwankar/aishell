# Task Planner Skill — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a Claude Code skill that abstracts beads into invisible infrastructure, letting the user think in features/outcomes while the agent manages task decomposition and lifecycle.

**Architecture:** A single SKILL.md file at `~/.claude/skills/task-planner/SKILL.md` with three modes (/plan, /track, /propagate). Each mode reads project state, proposes beads operations, gets user approval, then executes `bd` commands. A `.beads/plans/` directory stores learning logs.

**Tech Stack:** Claude Code skill (markdown), `bd` CLI, git, bash

---

### Task 1: Create skill directory and skeleton SKILL.md

**Files:**
- Create: `~/.claude/skills/task-planner/SKILL.md`

**Step 1: Create directory**

```bash
mkdir -p ~/.claude/skills/task-planner
```

**Step 2: Write SKILL.md with frontmatter and structure**

Write the complete skill file. The frontmatter description must follow CSO rules: triggering conditions only, starts with "Use when", max 500 chars, no workflow summary.

```markdown
---
name: task-planner
description: Use when starting a new feature or experiment (/plan), syncing progress to tracking (/track), or shipping a library with downstream consumers (/propagate). Also use when the user says "update tracking files", "what should I build", or "break this down into tasks". Requires .beads/ directory.
---

# Task Planner

Managed layer between you and beads. You think in features and outcomes. This skill handles decomposition into epics, tasks, and subtasks — creating, closing, and linking beads without you touching `bd` directly.

## Pre-flight

```bash
ls .beads/ 2>/dev/null || echo "NO_BEADS"
which bd 2>/dev/null || echo "NO_BD"
```

If no `.beads/`: offer `bd init --prefix <dirname>`.
If no `bd`: stop — skill requires beads CLI.

## Mode Detection

| Invocation | Mode | Purpose |
|---|---|---|
| `/plan "feature description"` | A — Decompose | Break big idea into epic + tasks |
| `/track` or "update tracking files" | C — Transparent sync | Match git changes to open beads |
| `/propagate` or shipping a library | B — Cross-project | Find downstream consumers, create integration tasks |

---

## Mode A: /plan — Decompose

1. **Read context**: CLAUDE.md, `bd ready`, `git log --oneline -10`
2. **Ask 1-2 questions**: scope, success criteria, constraints
3. **Propose decomposition**:

```
Epic: "{feature name}"
├─ Task 1: {concrete action} (P{n})
│  done-when: {testable condition}
├─ Task 2: {concrete action} (P{n})
│  done-when: {testable condition}
└─ Task 3: {concrete action} (P{n})
   done-when: {testable condition}
Deps: T2 blocked by T1
```

4. **User approves or adjusts**
5. **Execute** (user never sees these):

```bash
bd create "{epic}" -t epic -p {n}                    # → epic-id
bd create "{task1}" -t task -p {n} --description "done-when: {condition}"  # → t1-id
bd create "{task2}" -t task -p {n} --description "done-when: {condition}"  # → t2-id
bd dep add {t1-id} {epic-id}
bd dep add {t2-id} {epic-id}
bd dep add {t2-id} {t1-id}                           # if T2 blocked by T1
```

6. **Save plan** to `.beads/plans/YYYY-MM-DD-{slug}.md`

### Research variant

For exploratory work (experiments, research):
- Tasks phrased as questions: "Can X achieve Y?"
- Done-when is a proxy: "results.json exists with ≥ N configs"
- Fewer tasks (2-3), lighter structure

---

## Mode C: /track — Transparent Sync

1. **Gather evidence**:

```bash
git diff --stat                          # What files changed
git log --oneline $(git describe --tags --abbrev=0 2>/dev/null || echo HEAD~5)..HEAD  # Recent commits
bd list --status=in_progress             # What's claimed
bd list --status=open                    # What's available
```

2. **Match changes to open beads**: For each in-progress or open bead, check if the git diff or conversation context shows the done-when condition is met.

3. **Propose updates** (ALWAYS propose, never auto-execute):

```
Close:
  ✓ {id} "{title}" — evidence: {specific file change or conversation reference}

New:
  + "{discovered work}" (P{n}, {type}) — reason: {why it was discovered}

No action:
  ○ {id} "{title}" — not started / still in progress
```

4. **User approves** (yes to batch, or line-item edits)
5. **Execute** approved changes via `bd close` / `bd create`
6. **Update DONE.md** if milestone-worthy (call update-done skill)
7. **Git commit** with descriptive message

### Key constraint

Evidence-based only. Every proposed close must cite a specific file change, test result, or conversation excerpt. Never guess.

---

## Mode B: /propagate — Cross-Project

1. **Detect source project**: Check for `setup.py`, `pyproject.toml` with package name
2. **Find consumers**:

```bash
# Grep across known project directories for imports
grep -rl "import {package}" ~/Projects/github/*/  2>/dev/null
grep -rl "from {package}" ~/Projects/github/*/  2>/dev/null
```

3. **For each consumer**, propose integration task:

```
Source: {project} — "{what's shipping}"
Downstream:
  ├─ {consumer1}: "Update to {project} {version}" (P2)
  │  done-when: imports updated, tests pass
  └─ {consumer2}: "Evaluate {new feature}" (P3)
      done-when: comparison doc written
```

4. **User approves / prunes**
5. **Execute**: Create beads in each consumer that has `.beads/`. Log reminder for others.
6. **Save propagation map** to `.beads/plans/YYYY-MM-DD-propagate-{slug}.md`

### Constraints

- Only grep for real imports — no guesswork
- Only create beads in `.beads/`-enabled projects
- Plan doc is the cross-project linkage (beads can't cross repos)

---

## Learning Log

All modes save to `.beads/plans/`:

```
.beads/plans/
├── YYYY-MM-DD-{feature}.md       # Mode A decomposition
├── YYYY-MM-DD-propagate-{pkg}.md # Mode B propagation map
└── YYYY-MM-DD-track-{n}.md       # Mode C inference log
```

Format for each:
```markdown
# {Mode} — {date}
## Input: {what the user said}
## Proposed: {what the skill suggested}
## Approved: {what the user accepted}
## Executed: {bd commands run}
```

---

## Safety Rules

- **Never auto-close beads** — always propose and wait for approval
- **Never run bare `bd sync`** — use `bd sync --no-push` or `--force` only with explicit permission
- **Never run `bd edit`** — use `bd update <id> --description "text"`
- **Show bd commands in learning log only** — user sees the human-readable proposal, not the commands
- **Pre-flight every time** — check `.beads/` exists before any operation
```

**Step 3: Verify skill is discoverable**

```bash
ls ~/.claude/skills/task-planner/SKILL.md
```

Expected: file exists

**Step 4: Commit**

```bash
cd ~/.claude/skills/task-planner
# Not a git repo — skill files live outside project repos
# Just verify the file is in place
cat ~/.claude/skills/task-planner/SKILL.md | head -5
```

Expected output:
```
---
name: task-planner
description: Use when starting a new feature or experiment (/plan), syncing progress to tracking (/track), or shipping a library with downstream consumers (/propagate). Also use when the user says "update tracking files", "what should I build", or "break this down into tasks". Requires .beads/ directory.
---
```

---

### Task 2: Create .beads/plans/ directory for learning logs

**Files:**
- Create: `/Users/nitin/Projects/github/aishell/.beads/plans/.gitkeep`

**Step 1: Create the plans directory**

```bash
mkdir -p /Users/nitin/Projects/github/aishell/.beads/plans
touch /Users/nitin/Projects/github/aishell/.beads/plans/.gitkeep
```

**Step 2: Check .beads/.gitignore doesn't exclude plans/**

```bash
cat /Users/nitin/Projects/github/aishell/.beads/.gitignore
```

If `plans/` is excluded, remove that line. Plans should be git-tracked (they're the learning log).

**Step 3: Commit**

```bash
cd /Users/nitin/Projects/github/aishell
git add .beads/plans/.gitkeep
git commit -m "chore: Add .beads/plans/ directory for task-planner learning logs"
```

---

### Task 3: Test Mode A — /plan decomposition

**Files:**
- Verify: `~/.claude/skills/task-planner/SKILL.md`
- Output: `/Users/nitin/Projects/github/aishell/.beads/plans/` (new plan file)

**Step 1: Start a new Claude Code session in aishell**

In the session, invoke:
```
/task-planner
```

Then say:
```
/plan "add paragraph-level chunking to the conversation search"
```

**Step 2: Verify skill behavior**

Check that the skill:
- [ ] Runs pre-flight (checks .beads/ and bd)
- [ ] Reads project context (CLAUDE.md, bd ready)
- [ ] Asks 1-2 clarifying questions
- [ ] Proposes an epic + tasks with done-when conditions
- [ ] Waits for approval before creating beads
- [ ] Creates beads via `bd create` + `bd dep add` after approval
- [ ] Saves plan to `.beads/plans/YYYY-MM-DD-paragraph-chunking.md`

**Step 3: Verify beads were created**

```bash
bd list --status=open
```

Expected: new epic + tasks visible with correct dependencies

**Step 4: Verify learning log**

```bash
ls /Users/nitin/Projects/github/aishell/.beads/plans/
cat /Users/nitin/Projects/github/aishell/.beads/plans/*paragraph*
```

Expected: plan file with Input/Proposed/Approved/Executed sections

---

### Task 4: Test Mode C — /track transparent sync

**Files:**
- Verify: `~/.claude/skills/task-planner/SKILL.md`
- Output: `/Users/nitin/Projects/github/aishell/.beads/plans/` (new track file)

**Step 1: Make some code changes in aishell (any small edit)**

```bash
# Example: add a comment to a file, edit something minor
```

**Step 2: Invoke /track**

In a Claude Code session:
```
/track
```

Or say: "update tracking files and commit"

**Step 3: Verify skill behavior**

Check that the skill:
- [ ] Reads git diff and recent commits
- [ ] Reads bd list --status=in_progress
- [ ] Proposes closes with evidence (specific file changes)
- [ ] Proposes new beads for discovered work
- [ ] Waits for approval
- [ ] Executes only approved changes
- [ ] Commits with descriptive message

**Step 4: Verify learning log**

```bash
ls /Users/nitin/Projects/github/aishell/.beads/plans/*track*
```

Expected: track log with evidence → decision mapping

---

### Task 5: Test Mode B — /propagate (deferred)

**Prerequisite**: At least 2 projects with `.beads/` initialized. Currently only aishell has it.

**When ready** (after initializing beads in n2 or embedding_tools):

**Step 1: Navigate to embedding_tools and invoke**

```
/propagate
```

Or say: "ship embedding_tools v0.1.3"

**Step 2: Verify skill behavior**

Check that the skill:
- [ ] Detects setup.py/pyproject.toml as library indicator
- [ ] Greps across ~/Projects/github/ for actual imports
- [ ] Proposes integration tasks per consumer
- [ ] Only creates beads in .beads/-enabled projects
- [ ] Saves propagation map

**Note**: This task is deferred until more projects have beads. Log it as a bead:

```bash
bd create "Test /propagate mode after initializing beads in 2+ projects" -t task -p 3
```

---

### Task 6: Iterate on skill text based on testing

**Files:**
- Modify: `~/.claude/skills/task-planner/SKILL.md`

After Tasks 3-4, review what worked and what didn't:

**Step 1: Check for common failure modes**

- Did the skill trigger correctly on "/plan" and "/track"?
- Did mode detection work (right mode for right invocation)?
- Were proposals well-structured and evidence-based?
- Was the approve step lightweight enough?
- Did `bd` commands execute correctly?

**Step 2: Adjust skill text**

Common adjustments:
- Sharpen description triggers if skill didn't fire
- Add/remove steps if flow was too heavy or too light
- Fix bd command patterns if syntax was wrong
- Adjust proposal format if approval was confusing

**Step 3: Commit adjusted skill**

```bash
cp ~/.claude/skills/task-planner/SKILL.md /Users/nitin/Projects/github/aishell/docs/plans/task-planner-skill-snapshot.md
cd /Users/nitin/Projects/github/aishell
git add docs/plans/task-planner-skill-snapshot.md
git commit -m "docs: Snapshot task-planner skill after initial testing"
```

---

### Task 7: Document in project CLAUDE.md

**Files:**
- Modify: `/Users/nitin/Projects/github/aishell/CLAUDE.md`

**Step 1: Add task-planner reference to CLAUDE.md**

Add to the "Key Features Implemented" or similar section:

```markdown
### Task Planner Skill (2026-03)
Managed task layer that abstracts beads infrastructure:
- `/plan "feature"` — decompose into epic + tasks with dependencies
- `/track` — sync git changes to beads (transparent, evidence-based)
- `/propagate` — find downstream consumers when shipping libraries
Learning logs saved to `.beads/plans/`. See `docs/plans/2026-03-03-task-planner-design.md`.
```

**Step 2: Commit**

```bash
cd /Users/nitin/Projects/github/aishell
git add CLAUDE.md
git commit -m "docs: Add task-planner skill reference to CLAUDE.md"
```

---

## Task Dependency Graph

```
Task 1 (create skill) ──→ Task 3 (test /plan)
         │                        │
         └──→ Task 2 (plans dir) ─┤
                                  ├──→ Task 6 (iterate)
Task 1 ──→ Task 4 (test /track) ─┘         │
                                            └──→ Task 7 (document)
Task 1 ──→ Task 5 (test /propagate — deferred)
```

Tasks 1 and 2 are independent and can run in parallel.
Tasks 3 and 4 depend on Task 1, can run in parallel with each other.
Task 5 is deferred (needs multi-project beads).
Task 6 depends on 3 and 4.
Task 7 depends on 6.

---

## Estimated Scope

- **Tasks 1-2**: Skill creation + directory setup (one session)
- **Tasks 3-4**: Testing both modes (same or next session)
- **Task 5**: Deferred
- **Tasks 6-7**: Iteration + documentation (after testing)

Total: 2-3 sessions for MVP (Modes A + C working). Mode B deferred until more projects have beads.
