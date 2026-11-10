# pltr-cli agent skill

A Claude Code skill (it works with other agents that read `SKILL.md` skills)
for working with Palantir Foundry through the pltr CLI.

## Install

Inside this repository the skill is available to Claude Code as is. To use it
everywhere, copy it to your skills directory:

```bash
cp -r claude_skill ~/.claude/skills/pltr
```

The skill needs a pltr release that has `pltr commands` (check with
`pltr commands --help`), installed for example with `uv tool install pltr-cli`.

## Layout

```
claude_skill/
├── SKILL.md            # hand-written: auth, output contract, safety, RIDs, workflows
├── README.md           # this file
├── workflows/          # hand-written, longer workflows
│   ├── explore-data.md
│   ├── builds-and-schedules.md
│   ├── permissions.md
│   └── osdk-react-app.md
└── reference/          # GENERATED from the command manifest; don't edit
    ├── index.md        # what's where, and how to read an entry
    ├── curated/        # one file per curated group: dataset.md, sql.md, ...
    └── api/            # one file per `pltr api` namespace (large ones per resource)
```

`SKILL.md` is short and always loaded. An agent finds commands with
`pltr commands search` and reads one command's details with
`pltr commands show`, so it loads a `reference/` file only when it needs to
browse a whole area.

## Keeping it current

`reference/` is generated from the command manifest
(`pltr commands list --format json`). After changing commands (converting a
module, regenerating `pltr api` after an SDK bump), run:

```bash
uv run python scripts/generate_skill_reference.py
```

That's the only step. The test `tests/test_manifest/test_skill_reference.py`
fails in CI when the committed reference is stale, and also when `SKILL.md`,
this README or a workflow mentions a `pltr` command or option that doesn't
exist. `uv run python scripts/generate_skill_reference.py --check` runs the
same checks locally.

See [docs/user-guide/claude-skill.md](../docs/user-guide/claude-skill.md) for
more.
