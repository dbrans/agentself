# Skills

Each skill lives in its own folder under `skills/` and includes a `SKILL.md` file.
Skill metadata is stored in the YAML frontmatter at the top of `SKILL.md`.

In the REPL (safe profile):
- `skills.list()` for metadata
- `skills.path("<name>")` for the skill directory
- `skills.files("<name>")` to list files
- `skills.show("<name>")` to show `SKILL.md`
- `skills.fs` / `skills.cmd` for read-only access to `skills/`

Tip: use `rg`/`grep` on this folder to search for specific terms.
Set `AGENTSELF_SKILLS_DIRS` (path-separated) to add more roots.
