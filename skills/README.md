# Skills

Each skill lives in its own folder under `skills/` with a `SKILL.md` file, or as a single
`skills/<name>.md` file.
Skill metadata is stored in YAML frontmatter at the top of the skill file.

In the REPL (safe profile):
- `skills.list()` for metadata
- `skills.path("<name>")` for the skill directory
- `skills.files("<name>")` to list files
- `skills.show("<name>")` to show the skill file
- `skills.fs` / `skills.cmd` for read-only access to `skills/`

Tip: use `rg`/`grep` on this folder to search for specific terms.
Set `AGENTSELF_SKILLS_DIRS` (path-separated) to add more roots.
