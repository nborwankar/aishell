# Scatter-Gather & Ralph Wiggum Loop: Agent Orchestration Patterns

**Date**: 2026-02-25
**Context**: Research into agent orchestration models for multi-project research workflows

---

## Background

This doc captures two complementary agent orchestration patterns explored during a review of `ccli` (Claude Code CLI orchestrator) and how it could better support research-oriented, multi-project workflows.

The current `ccli` model assumes **N agents, 1 codebase, independent tasks** — good for enterprise code review but insufficient for open-ended research that spans multiple projects and converges into tools/frameworks.

---

## Pattern 1: Scatter-Gather

### The Problem

Research workflows follow a cycle:

```
Research exploration (papers, experiments, manifolds)
    ↓ insight
Prototype in one project (manopt, hypHNSW)
    ↓ pattern recognition
Extract into reusable tool (embedding_tools, aishell)
    ↓ integration
Propagate back into other projects (n2, strictRAG)
```

Agents working on different projects aren't independent — findings in one inform what happens in another.

### The Model

```
Scatter                    Gather                   Re-scatter
┌──────────┐              ┌──────────┐              ┌──────────┐
│ aishell   │──findings──→│          │              │ aishell   │
│ n2        │──findings──→│ synthesize│──plan──────→│ n2        │
│ strictRAG │──findings──→│          │              │ strictRAG │
└──────────┘              └──────────┘              └──────────┘
  read-only                 one agent                 write mode
  parallel                  sequential                parallel
```

**Key properties:**
- **Scatter** agents are read-only and produce structured artifacts
- **Gather** agent consumes all scatter outputs, has the full cross-project picture
- **Re-scatter** is optional — only when gather produces actionable work
- Each phase has different tool permissions and turn budgets
- The gather step is where human judgment enters (approve/modify before re-scatter)

### Example TOML Configs

#### Cross-project audit ("what do I have?")

```toml
[defaults]
model = "opus"
max_turns = 15
allowed_tools = ["Read", "Glob", "Grep"]  # read-only

[[instances]]
name = "embeddings"
prompt = "Survey all embedding-related code: models used, dimensions, distance metrics, backends (MLX/PyTorch/numpy). Output a structured comparison table."
cwd = "~/Projects/github/embedding_tools"

[[instances]]
name = "search"
prompt = "Survey search implementations: vector search, hybrid search, indexing strategies. What embedding models and dimensions does each use?"
cwd = "~/Projects/github/aishell"

[[instances]]
name = "hyperbolic"
prompt = "Survey manifold types implemented, distance functions, and embedding pipelines. What's production-ready vs experimental?"
cwd = "~/Projects/github/n2-research/hyperbolic"
```

#### Framework extraction ("what's the common pattern?")

```toml
[defaults]
model = "opus"
max_turns = 15
allowed_tools = ["Read", "Glob", "Grep"]

[[instances]]
name = "aishell-emb"
prompt = "Document the embedding pipeline: how embeddings are generated, stored, queried, and what chunking/prefixing is used. Focus on the interface boundaries."
cwd = "~/Projects/github/aishell"

[[instances]]
name = "n2-emb"
prompt = "Document the embedding pipeline: generation, storage, indexing, query. What's the interface between embedding code and search code?"
cwd = "~/Projects/github/n2"

[[instances]]
name = "strictrag-emb"
prompt = "Document how embeddings are consumed: what format, dimensions, distance metric, and query interface does VQL expect?"
cwd = "~/Projects/github/strictRAG"
```

#### Integration propagation ("push this change everywhere")

```toml
[defaults]
model = "sonnet"
max_turns = 10

[[instances]]
name = "aishell"
prompt = "Read aishell/commands/conversations/embeddings.py. Identify what would need to change to use embedding_tools instead of mlx-embedding-models directly. List specific imports, function calls, and config. Do NOT edit files."
cwd = "~/Projects/github/aishell"

[[instances]]
name = "n2"
prompt = "Find all embedding-related code. What currently handles model loading, encoding, and dimension config? What would change to use embedding_tools? Do NOT edit files."
cwd = "~/Projects/github/n2"
```

### Proposed TOML Extension for Phased Execution

```toml
[defaults]
model = "opus"

[phases.scatter]
allowed_tools = ["Read", "Glob", "Grep"]
max_turns = 15

[phases.gather]
allowed_tools = ["Read", "Glob", "Grep", "Bash"]
max_turns = 25
pause_before = true   # wait for user approval before proceeding

[[instances]]
phase = "scatter"
name = "aishell"
prompt = "Survey embedding pipeline..."
cwd = "~/Projects/github/aishell"
output = "findings.md"

[[instances]]
phase = "scatter"
name = "n2"
prompt = "Survey embedding pipeline..."
cwd = "~/Projects/github/n2"
output = "findings.md"

[[instances]]
phase = "gather"
name = "synthesis"
prompt = "Compare the findings. Identify the common interface."
cwd = "/tmp/ccli-scratch"
inputs = ["aishell/findings.md", "n2/findings.md"]
```

### What's Missing from ccli for Scatter-Gather

1. **No synthesis step** — instances can't consume each other's outputs
2. **No shared context** — no scratch space for structured findings
3. **No dynamic spawning** — can't branch from discoveries
4. **Per-instance tool permissions** — survey vs implementation phases need different tools
5. **Output format control** — need structured (JSON, markdown tables) for machine parsing

---

## Pattern 2: Ralph Wiggum Loop

### Origin

Named after the lovably persistent Simpsons character. Went viral late 2025. The core insight: **naive persistence beats sophisticated complexity**.

### The Canonical Implementation

```bash
while :; do cat PROMPT.md | claude-code ; done
```

Each iteration is a **fresh Claude instance** with no memory of prior runs. State persists through the filesystem, not the context window.

### State Persistence Mechanisms

| Mechanism | Purpose |
|-----------|---------|
| **Git history** | Completed work survives as commits |
| **progress.txt** | Append-only learnings file (avoids repeating mistakes) |
| **prd.json** | Structured task list with `passes: true/false` per story |
| **AGENTS.md** | Discovered patterns and gotchas |

### The Loop

1. Pick next incomplete task from spec (`passes: false` in prd.json)
2. Spawn fresh agent with project context
3. Agent works, runs tests/typechecks
4. If passes → commit, mark done, update progress
5. If fails → feedback goes into progress.txt for next iteration
6. Loop until all tasks pass or max iterations hit

### Structured Version (snarktank/ralph)

```bash
./scripts/ralph/ralph.sh --tool claude 10   # max 10 iterations
```

Key rule: stories must be **"small enough to complete in one context window"** — add a DB column, create a component, update business logic. Not "build the dashboard."

### Real-World Results

- One engineer completed a $50K contract for $297 in API costs running overnight
- A YC hackathon team ran it overnight → 1,000+ commits across 6 ported codebases
- Works best for **mechanical, well-defined tasks** with automatic verification
- Struggles with judgment calls or ambiguous requirements

---

## Composing the Two Patterns

Ralph is **single-agent, single-project, sequential**. Scatter-gather is **multi-agent, multi-project, parallel with synthesis**. They compose:

```
Scatter phase:  N Ralph loops running overnight on N projects
                (each with its own prd.json and test suite)

Gather phase:   Morning — synthesis agent reads all N repos'
                progress.txt + git logs, produces cross-project report
```

### The Research Gap

Ralph needs a **concrete verification signal** (tests pass, typecheck clean). Research tasks often don't have that — "explore manifold embeddings" has no boolean pass/fail.

Proxy success criteria for research:
- "Produce results.json with Spearman > 0.40"
- "Generate comparison table with ≥ 3 manifold types"
- "Run all experiment configs and log results without errors"
- "Document findings in RESULTS.md with at least 3 quantitative comparisons"

---

## References

- [snarktank/ralph — GitHub](https://github.com/snarktank/ralph)
- [Ralph Wiggum Loop — beuke.org](https://beuke.org/ralph-wiggum-loop/)
- [2026 - The Year of the Ralph Loop Agent — DEV Community](https://dev.to/alexandergekov/2026-the-year-of-the-ralph-loop-agent-1gkj)
- [Ralph Wiggum AI Agents — leanware.co](https://www.leanware.co/insights/ralph-wiggum-ai-coding)
- [Vercel Labs ralph-loop-agent — GitHub](https://github.com/vercel-labs/ralph-loop-agent)
- [From ReAct to Ralph Loop — Alibaba Cloud](https://www.alibabacloud.com/blog/from-react-to-ralph-loop-a-continuous-iteration-paradigm-for-ai-agents_602799)
