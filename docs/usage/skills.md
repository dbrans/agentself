# Skills

## Layout
```
skills/
  <name>/
    SKILL.md
    ...
  <name>.md
```

`SKILL.md` (or a single-file `<name>.md`) should include YAML frontmatter with `name` and `description`.

## Roots
- Default skills root: `./skills`.
- No overrides for now.

## REPL Access
- `skills.list()`
- `skills.path("<name>")`
- `skills.files("<name>")`
- `skills.show("<name>")`
- `skills.fs` / `skills.cmd` for read-only access

Notes:
- `skills.path()` returns a directory for folder skills and a file path for single-file skills.
- `skills.list()` includes `skill_file` and `kind` metadata.

## Unix ergonomics
- Use `rg`/`grep` on `skills/`.
