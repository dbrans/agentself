# Skills

## Layout
```
skills/
  <name>/
    SKILL.md
    ...
```

`SKILL.md` should include YAML frontmatter with `name` and `description`.

## Roots
- Default skills root: `./skills`.
- Override/add roots with `AGENTSELF_SKILLS_DIRS` (path-separated).
- First root wins on name collisions.

## REPL Access
- `skills.list()`
- `skills.path("<name>")`
- `skills.files("<name>")`
- `skills.show("<name>")`
- `skills.fs` / `skills.cmd` for read-only access

## Unix ergonomics
- Use `rg`/`grep` on `skills/` (or on each root).
