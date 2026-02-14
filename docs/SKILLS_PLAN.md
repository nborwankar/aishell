# Skills: Command Plugin Extension Mechanism — Plan

**Status**: Implemented (2026-02-13)
**Created**: 2026-02-13

## Context

aishell now has **module scanning** (`commands/__init__.py`) that auto-discovers
Click groups dropped into `aishell/commands/`. This gives us zero-config CLI
command registration.

The next step is **skills** — a richer plugin convention that makes each command
self-describing, introspectable, and callable by an agent loop. A skill is a
command plugin that knows what it does, what it accepts, and what it returns.

### What we have today

```
aishell/commands/
├── __init__.py          # discover_commands() — module scanner
├── gemini.py            # Click group: gemini (login, pull, import)
├── chatgpt.py           # Click group: chatgpt (login, pull, import)
├── claude_export.py     # Click group: claude (login, pull, import)
└── conversations/
    └── cli.py           # Click group: conversations (load, browse, search)
```

Scanner finds Click groups automatically. But it knows nothing _about_ them
beyond the Click name and help string.

### What we want

```
aishell/commands/
├── __init__.py          # discover_commands() + discover_skills()
├── gemini.py            # Click group + SKILL metadata
├── chatgpt.py           # Click group + SKILL metadata
├── claude_export.py     # Click group + SKILL metadata
└── conversations/
    └── cli.py           # Click group + SKILL metadata
```

Each module exports a `SKILL` dict alongside its Click group. The scanner
collects both. `aishell skills` lists all available skills with descriptions
and examples.

## Design

### Skill Convention

Each command module MAY export a `SKILL` dict. If absent, the scanner still
registers the Click group (backward compatible). If present, the skill is
discoverable via `aishell skills`.

```python
# aishell/commands/conversations/cli.py

SKILL = {
    "name": "conversations",
    "description": "Load, browse, and search exported LLM conversations",
    "capabilities": [
        "Hybrid search (semantic + keyword) across 1764+ conversations",
        "Conversation-level keyword search with hit counts",
        "Interactive TUI browser with source filtering",
        "Load raw exports from Gemini, ChatGPT, Claude into PostgreSQL",
    ],
    "examples": [
        'aisearch "manifold geometry"',
        'aisearch "flatoon" -c',
        'aisearch "FDL" -s gemini -l 5',
        "aishell conversations browse",
        "aishell conversations load --provider gemini",
    ],
    "tools": [
        {
            "name": "search_conversations",
            "description": "Hybrid semantic + keyword search across exported LLM conversations",
            "parameters": {
                "query": {"type": "string", "required": True, "description": "Search query"},
                "source": {"type": "string", "enum": ["gemini", "chatgpt", "claude"], "description": "Filter by provider"},
                "limit": {"type": "integer", "default": 10, "description": "Max results"},
                "conversations": {"type": "boolean", "default": False, "description": "Conversation-level search (-c flag)"},
            },
        },
        {
            "name": "browse_conversations",
            "description": "Launch interactive TUI for browsing conversations",
            "parameters": {
                "source": {"type": "string", "enum": ["gemini", "chatgpt", "claude"], "description": "Pre-filter by provider"},
            },
        },
    ],
}
```

### Skill Registry

Extend `commands/__init__.py` with a registry that collects both Click groups
and SKILL metadata:

```
┌─────────────────────────────────────────────────┐
│  discover_commands(parent_group)                │
│                                                 │
│  for each module in commands/:                  │
│    1. Find Click group → add_command()    [CLI] │
│    2. Find SKILL dict  → _registry[]   [skill]  │
│                                                 │
│  _registry = {                                  │
│    "conversations": { SKILL dict },             │
│    "gemini": { SKILL dict },                    │
│    ...                                          │
│  }                                              │
└─────────────────────────────────────────────────┘
         │
         ▼
   aishell <cmd>
   (Click dispatch)
```

### Design Decision: Internal Registry Only

Skills are NOT exposed as a user-facing command. There is no `aishell skills`
command. The registry is internal infrastructure used by:

- The shell/agent to route queries to the right command
- Future agent loops to discover available tools
- Programmatic introspection (`list_skills()`, `get_skill()`)

The user should not need to know which commands are "skills" — every command
plugin is a skill automatically. It's an extension mechanism, not a syntax
element.

### Auto-Extraction Fallback

Modules without a `SKILL` dict still get a basic skill entry auto-generated
from Click metadata:

```python
def _skill_from_click_group(group):
    """Generate minimal SKILL dict from Click group introspection."""
    return {
        "name": group.name,
        "description": group.help or f"{group.name} commands",
        "capabilities": [cmd.help for cmd in group.commands.values() if cmd.help],
        "examples": [],
        "tools": [],
    }
```

This means every command plugin is a skill automatically — explicit `SKILL`
dicts just provide richer metadata.

### Tool Definitions (Future Agent Integration)

The `tools` list in `SKILL` defines what an agent can call. Each tool maps to
a Click subcommand. The execution bridge:

```python
def invoke_skill_tool(skill_name, tool_name, params):
    """Invoke a skill's tool programmatically.

    Translates tool params to Click CLI args and invokes the command.
    Returns structured output (text or dict).
    """
    # Example: invoke_skill_tool("conversations", "search_conversations",
    #            {"query": "manifold", "limit": 5})
    # → equivalent to: aishell conversations search "manifold" -l 5
```

This is NOT MCP. It's a thin bridge that lets a Python agent loop call aishell
commands without shelling out. The agent loop (future work) would:

1. Collect all tool definitions from registered skills
2. Pass them to Anthropic's `tools` parameter in `messages.create()`
3. When Claude returns a `tool_use` block, route to `invoke_skill_tool()`
4. Feed the result back as a `tool_result` message
5. Repeat until Claude returns text-only

```
┌──────────────┐     tools list      ┌──────────────┐
│  Agent Loop  │ ──────────────────► │   Claude API │
│              │ ◄────────────────── │  (tool_use)  │
│              │     tool_use block  └──────────────┘
│              │
│  invoke_skill_tool()
│      │
│      ▼
│  ┌──────────────────┐
│  │  Skill Registry   │
│  │  conversations:   │
│  │    search_conv... │──► Click command
│  │    browse_conv... │──► Click command
│  │  gemini:          │
│  │    pull...        │──► Click command
│  └──────────────────┘
```

## Files to Modify/Create

| File | Change |
|------|--------|
| `aishell/commands/__init__.py` | Add `_registry`, `discover_skills()`, `get_skill()`, `list_skills()` |
| `aishell/cli.py` | Add `aishell skills` and `aishell skills <name>` commands |
| `aishell/commands/conversations/cli.py` | Add `SKILL` dict |
| `aishell/commands/gemini.py` | Add `SKILL` dict |
| `aishell/commands/chatgpt.py` | Add `SKILL` dict |
| `aishell/commands/claude_export.py` | Add `SKILL` dict |

## Implementation Order

1. **Extend scanner** — add `_registry` and skill collection to `__init__.py`
2. **Add SKILL dicts** — to all 4 command modules
3. **`aishell skills` command** — list and detail views
4. **Auto-extraction fallback** — generate basic SKILL from Click metadata
5. **Verify** — `aishell skills`, `aishell skills conversations`, all commands still work

## Future Extensions (Not in This Phase)

- **`invoke_skill_tool()`** — programmatic bridge for agent loops
- **`aishell agent "query"`** — native agent loop using skill tools
- **Third-party skills** — entry_points-based discovery for pip-installed plugins
- **Skill config** — `~/.aishell/skills.toml` for enabling/disabling skills
- **Tool schemas** — auto-generate JSON Schema from Click params (no manual `tools` dict)

## Verification

1. `aishell skills` → lists 4 skills with descriptions
2. `aishell skills conversations` → shows capabilities, examples, tools
3. `aishell conversations search "flatoon"` → still works (no regression)
4. `aishell --help` → still shows all commands
5. Drop a new `.py` file in `commands/` → auto-discovered as skill
