# Agent Configuration Guide

This repository supports multiple AI coding agents: **Codex**, **Gemini CLI**, **Claude Code**, and **Antigravity**. Configuration is centralized in `.agent/` with provider-specific directories for each agent.

## Directory Structure

```
.
├── AGENTS.md              # Shared rules (industry standard, read by all agents)
├── CLAUDE.md              # Symlink → AGENTS.md (Claude Code compatibility)
├── CODEX.md               # Symlink → AGENTS.md (Codex compatibility)
├── .agent/                # Canonical shared configuration
│   ├── commands/          # Shared commands (Markdown format)
│   ├── rules/             # Shared rules (Markdown format)
│   └── workflows/         # Symlink → commands/ (Antigravity compatibility)
├── .claude/               # Claude Code configuration
│   ├── commands/          # Symlink → ../.agent/commands
│   ├── rules/             # Symlink → ../.agent/rules
│   └── settings.json      # Claude-specific settings (permissions)
├── .gemini/               # Gemini CLI configuration
│   ├── commands/          # TOML commands (generated from .agent/commands)
│   ├── hooks/             # Lifecycle hooks
│   └── settings.json      # Gemini-specific settings
└── scripts/
    └── sync-agent-commands.sh  # Syncs MD commands → TOML for Gemini
```

---

## Shared Configuration (`.agent/`)

The `.agent/` directory is the **canonical source of truth** for commands and rules that work across all agents.

### Commands (`.agent/commands/*.md`)

Commands are reusable prompts invoked via slash commands. Format:

```markdown
---
description: Short description of what the command does
---

Detailed instructions for the agent.
Use $ARGUMENTS to reference user-provided arguments.

Steps:
1. First step
2. Second step
```

**Example**: [.agent/commands/deploy.md](file:///Users/dbrans/Code/omni3/.agent/commands/deploy.md)

### Rules (`.agent/rules/*.md`)

Rules provide context-specific instructions. They can be scoped to specific file paths:

```markdown
---
paths:
  - "**/*.test.ts"
  - "**/*.spec.ts"
---

# Rule Title

- Instruction 1
- Instruction 2
```

**Example**: [.agent/rules/testing.md](file:///Users/dbrans/Code/omni3/.agent/rules/testing.md)

---

## Claude Code Configuration (`.claude/`)

Claude Code reads from:
- `CLAUDE.md` (symlink to `AGENTS.md`) - Global rules
- `.claude/commands/` (symlink to `.agent/commands/`) - Slash commands
- `.claude/rules/` (symlink to `.agent/rules/`) - Contextual rules
- `.claude/settings.json` - Permissions and Claude-specific settings

### Settings File

```json
{
    "permissions": {
        "allowedTools": ["read", "write", "execute"]
    }
}
```

### Adding Configuration for Claude

1. **New command**: Create `.agent/commands/mycommand.md`
2. **New rule**: Create `.agent/rules/myrule.md`  
3. **Claude-specific settings**: Edit `.claude/settings.json`

> [!NOTE]
> Claude Code will automatically pick up new files in `.agent/` via the symlinks.

---

## Gemini CLI Configuration (`.gemini/`)

Gemini CLI reads from:
- `AGENTS.md` (via `settings.json` context reference)
- `.gemini/commands/*.toml` - Slash commands in TOML format
- `.gemini/hooks/` - Lifecycle hooks
- `.gemini/settings.json` - Gemini-specific settings

### Settings File

```json
{
    "context": {
        "fileName": "AGENTS.md"
    }
}
```

### Command Format (TOML)

Gemini uses TOML format for commands:

```toml
description = "Short description"
prompt = """

Detailed instructions for the agent.
Use $ARGUMENTS to reference user-provided arguments.
"""
```

### Syncing Commands

Gemini requires TOML format, so commands must be synced from the shared Markdown source:

```bash
./scripts/sync-agent-commands.sh
```

This converts `.agent/commands/*.md` → `.gemini/commands/*.toml`

> [!IMPORTANT]
> Run this script after adding or modifying commands in `.agent/commands/`.

### Adding Configuration for Gemini

1. **New command**: Create `.agent/commands/mycommand.md`, then run sync script
2. **Gemini-specific settings**: Edit `.gemini/settings.json`
3. **Lifecycle hooks**: Add scripts to `.gemini/hooks/`

---

## Antigravity Configuration

Antigravity (Google's IDE-based agent) reads from:
- `AGENTS.md` - Global rules
- `.agent/workflows/` (symlink to `.agent/commands/`) - Slash commands
- `.agent/rules/` - Contextual rules

### Adding Configuration for Antigravity

1. **New command/workflow**: Create `.agent/commands/mycommand.md`
2. **New rule**: Create `.agent/rules/myrule.md`

> [!NOTE]
> Antigravity uses the term "workflows" for what other agents call "commands". The symlink ensures compatibility.

---

## Codex Configuration

Codex CLI reads from:
- `CODEX.md` (symlink to `AGENTS.md`) - Global rules
- `AGENTS.md` - Fallback global rules

### Adding Configuration for Codex

1. **Global rules**: Edit `AGENTS.md` (Codex reads `CODEX.md` via symlink)

---

## Quick Reference

| Task | Location | Format | Notes |
|------|----------|--------|-------|
| Add shared rule | `AGENTS.md` | Markdown | Read by all agents |
| Codex rules | `CODEX.md` | Markdown | Symlink to `AGENTS.md` |
| Add command | `.agent/commands/` | Markdown | Run sync script for Gemini |
| Add path-scoped rule | `.agent/rules/` | Markdown | Use `paths:` frontmatter |
| Claude permissions | `.claude/settings.json` | JSON | Claude-only |
| Gemini context | `.gemini/settings.json` | JSON | Gemini-only |
| Gemini hooks | `.gemini/hooks/` | Scripts | Gemini-only |

## Workflow: Adding a New Shared Command

1. Create `.agent/commands/my-command.md` with frontmatter:
   ```markdown
   ---
   description: What this command does
   ---
   
   Instructions for the agent...
   ```

2. Run the sync script:
   ```bash
   ./scripts/sync-agent-commands.sh
   ```

3. Verify the command works:
   - Claude Code: `/my-command`
   - Gemini CLI: `/my-command`
   - Antigravity: `/my-command`
