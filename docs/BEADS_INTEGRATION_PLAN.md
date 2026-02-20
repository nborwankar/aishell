# Beads Integration Plan

**Date**: 2026-02-20
**Goal**: Install Beads and integrate into existing dev workflow

## Phase 1: Install & Verify -- DONE

- [x] Install `bd` via Go with CGO_ENABLED=1 + ICU flags (v0.55.3)
- [x] Verify `bd --version` works
- [x] Run `bd doctor` to check health
- Note: Pre-built binary lacked CGO; built from source with ICU flags

## Phase 2: Configure for Claude Code -- DONE

- [x] Run `bd setup claude` — installed SessionStart + PreCompact hooks
- [ ] Verify Claude Code can access Beads tools (need session restart)

## Phase 3: Initialize in a Pilot Project -- DONE

Pilot project: **aishell**

- [x] `bd init --prefix aishell` in aishell project (Dolt backend)
- [x] Created 2 epics from existing plans:
  - `aishell-024` Conversation Browser TUI (P1)
  - `aishell-zvi` Unified aisearch CLI (P2)
- [x] Created 7 tasks with parent-child + sequential dependencies
- [x] Tested `bd ready` / `bd list` / `bd stats` / `bd dep tree`

## Phase 4: Workflow Integration -- DONE

- [x] Added Beads section to `~/.claude/CLAUDE.md` with session start/during/end rituals
- [x] Documented replacement table: TODO.md and NEXT_SESSION.md replaced by Beads; DONE.md and CLAUDE.md kept
- [x] Decision: NEXT_SESSION.md replaced — open Beads issues persist across sessions automatically
- [x] Added `bd sync` safety warning (it pushes to remote) and `bd edit` warning (interactive)

## Phase 5: Expand to Other Projects (Future)

- Initialize Beads in other hot projects (strictRAG, n2, etc.)
- Explore Gas Town for multi-agent workflows
- Evaluate Contributor mode for open-source repos

## Decision: Modes

For personal projects → **Standard mode** (tasks in repo)
For third-party/forked repos → **Contributor mode** (tasks in `~/.beads-planning`)

## Risks

- Learning curve for Beads CLI
- Overlap with existing markdown-based tracking (transition period)
- Beads is still alpha (API may change before 1.0)
