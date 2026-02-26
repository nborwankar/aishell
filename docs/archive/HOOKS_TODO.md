# Claude Code Hooks TODO

Reference for implementing workflow automation hooks in Claude Code.

## Hook Events Available

| Event | When It Fires |
|-------|---------------|
| `PreToolUse` | Before Claude executes a tool |
| `PostToolUse` | After a tool completes |
| `UserPromptSubmit` | When you submit a prompt |
| `Stop` | When Claude finishes responding |
| `SubagentStop` | When a Task subagent completes |
| `SessionStart` | At session start |
| `SessionEnd` | At session end |
| `Notification` | When Claude sends notifications |
| `PreCompact` | Before context compaction |

## Standard Workflow Hooks

### 1. Auto-format Python files after edits

Great for aishell development:

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Edit|Write",
      "hooks": [{
        "type": "command",
        "command": "black \"$CC_EDIT_FILE_PATH\" 2>/dev/null || true"
      }]
    }]
  }
}
```

### 2. Prevent edits to sensitive files

```bash
#!/bin/bash
# ~/.claude/hooks/protect-files.sh
if [[ "$CC_TOOL_NAME" =~ ^(Edit|Write)$ ]]; then
  if [[ "$CC_EDIT_FILE_PATH" == *".env"* ]] || [[ "$CC_EDIT_FILE_PATH" == *"credentials"* ]]; then
    echo "Blocked: Cannot modify sensitive file"
    exit 2  # Exit 2 = blocking error
  fi
fi
exit 0
```

### 3. Log all Bash commands for audit

```bash
#!/bin/bash
# ~/.claude/hooks/audit-bash.sh
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $CC_BASH_COMMAND" >> ~/.claude/audit.log
```

### 4. Run tests before stopping (Stop hook)

```bash
#!/bin/bash
# Ensure tests pass before Claude considers work done
if ! pytest -q 2>/dev/null; then
  echo '{"continue": true}'  # Tell Claude to keep working
fi
```

### 5. Git status reminder on session end

```bash
#!/bin/bash
# Remind about uncommitted changes
if [[ -n $(git status --porcelain 2>/dev/null) ]]; then
  echo "Warning: You have uncommitted changes"
fi
```

## Configuration Location

Add hooks to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit",
        "hooks": [{"type": "command", "command": "~/.claude/hooks/format.sh"}]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{"type": "command", "command": "~/.claude/hooks/audit-bash.sh"}]
      }
    ]
  }
}
```

## Hook Input/Output

Hooks receive JSON via stdin with:
- `session_id`: Unique session identifier
- `transcript_path`: Path to session transcript
- `cwd`: Current working directory
- `hook_event_name`: Which hook triggered
- Event-specific fields (tool names, file paths, etc.)

Exit codes:
- `0`: Success
- `2`: Blocking error (prevents action)
- Other: Non-blocking error (warning)

## Recommended for aishell

- [ ] Auto-formatting with `black` on Python edits
- [ ] Protecting `.env` files from accidental modification
- [ ] Running `pytest` or `flake8` checks on edits
- [ ] Audit logging for Bash commands

## Commands

- `/hooks` - View registered hooks in Claude Code
- `claude --debug` - Debug hook execution
