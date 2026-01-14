# Capabilities

## FileSystemCapability (fs)
- Scoped by `allowed_paths`.
- `read_only=True` blocks write/mkdir.
- Contract exposes reads/writes patterns based on allowed paths.

## CommandLineCapability (cmd)
- Optional `allowed_commands` allowlist.
- `allowed_cwd` restricts working directory.
- `allowed_paths` validates **path-like arguments** against allowed roots.
- `deny_shell_operators=True` blocks `&&`, `||`, `;`, `|`, backticks, `$(`, redirects.

## SkillsCapability (skills)
- Read-only lens over skills roots.
- `skills.list()` → metadata (includes `kind` and `skill_file`)
- `skills.path(name)` → directory path or single-file path
- `skills.files(name)` → file list
- `skills.show(name)` → skill contents
- `skills.fs` / `skills.cmd` → read-only access to skills roots

## Safe Profile Defaults
- `fs`: read-only, scoped to safe root.
- `cmd`: allowlisted commands + path-arg guardrails.
- `skills`: read-only and scoped to `skills/` roots.
