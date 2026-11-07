# The pltr agent skill (Claude Code)

The `claude_skill/` directory is a Claude Code skill that teaches an agent to
work with Palantir Foundry through pltr: how to authenticate without a
terminal, how to find the right command among more than 600, how to read
pltr's JSON output and exit codes, and which rules to follow before changing
anything. Other agents that read `SKILL.md` skills can use it too.

## Install

Inside this repository Claude Code picks the skill up as is. To use it in
every project, copy it to your personal skills directory:

```bash
cp -r claude_skill ~/.claude/skills/pltr
```

You also need:

1. **pltr**, a release that has `pltr commands` (check with
   `pltr commands --help`). An isolated install keeps the Foundry SDK at the
   version pltr was tested with:

   ```bash
   uv tool install pltr-cli    # or: pipx install pltr-cli
   ```

2. **Authentication.** Either a profile (`pltr configure configure`), or,
   for headless agents and CI, environment variables:

   ```bash
   export FOUNDRY_HOST="foundry.company.com"
   export FOUNDRY_TOKEN="your-api-token"
   pltr verify --format json
   ```

   See the README's "Authentication" section for the precedence rules and
   OAuth2 client credentials.

## How the agent uses it

The skill is built around the **command manifest**, a machine-readable
description of every pltr command:

```bash
pltr commands search list dataset branches      # find commands, best match first
pltr commands show dataset branches list --format json   # one command's entry
pltr commands list --format json                # the whole manifest
```

A typical session:

1. **Search** for the task: `pltr commands search download dataset file`.
2. **Show** the best match: arguments, options, whether it's beta,
   destructive or paged, and the SDK method it calls.
3. **Run** it with `--format json`, read the single JSON document on stdout,
   and use the exit code and the JSON error on stderr when it fails.
4. For a destructive command (a delete, revoke, cancel, replace, ...), pass
   `--yes` only when you asked for that change: without a terminal pltr
   refuses to run it otherwise (exit code 2).

Example prompts:

- "Which datasets are in the Flights project? Show their schemas."
- "Count the rows of ri.foundry.main.dataset.… by origin with SQL."
- "Start a build of this dataset on master and tell me when it finishes."
- "Who has access to this project? Give Jane viewer access."
- "Search the Aircraft objects that are ACTIVE and have more than 100 seats."

## What's in it

```
claude_skill/
├── SKILL.md            # hand-written guide, always loaded
├── README.md
├── workflows/          # hand-written, longer workflows
└── reference/          # generated from the manifest
    ├── index.md
    ├── curated/<group>.md
    └── api/<namespace>.md (large namespaces: api/<namespace>/<resource>.md)
```

- **`SKILL.md`** is short and hand-written: authentication (including the
  headless environment variables and their precedence), the JSON, stdout and
  stderr contract and the exit codes, the safety rules for destructive
  commands and `--yes`, beta labels, RIDs, discovering commands with
  `pltr commands`, when to use curated commands or `pltr api`, and a few
  common workflows.
- **`workflows/`** has longer hand-written workflows: exploring data,
  builds and schedules, and permissions.
- **`reference/`** is generated: one file per curated command group and per
  `pltr api` namespace, each entry with the command's usage, description,
  arguments, options, labels (beta, destructive, paged) and SDK method. The
  agent loads a file only when it needs to browse a whole area; `index.md`
  says which file covers what.

## Keeping the skill current (maintainers)

The reference is generated from the manifest, which is read from the CLI
itself, so it can't drift from the commands:

```bash
uv run python scripts/generate_skill_reference.py           # regenerate
uv run python scripts/generate_skill_reference.py --check   # verify only
```

Run the script after any change to commands: a converted or new command, a
changed option or help text, or a regenerated `pltr api` tree after an SDK
bump. It's the only step. The output is deterministic (the same on every
OS, terminal and Python version), and `tests/test_manifest/` fails in CI
when:

- the committed `reference/` differs from what the script generates, or
- `SKILL.md`, `claude_skill/README.md`, a workflow, this page or the
  README's "Using pltr from agents" section mentions a `pltr` command or
  option that doesn't exist.

Edit `SKILL.md` and the workflows by hand; never edit `reference/`.

## Troubleshooting

- **The skill doesn't activate.** Check that the skill directory is in
  `~/.claude/skills/` (or that you're in this repository), and mention
  Foundry, pltr or a RID in your request.
- **`pltr commands` doesn't exist.** Your pltr is older than the skill:
  upgrade it (`uv tool upgrade pltr-cli`).
- **A command fails with exit code 3.** pltr found no usable credentials;
  run `pltr verify` to see which source it tried.

## Related documentation

- [Quick Start Guide](./quick-start.md)
- [Authentication Guide](./authentication.md)
- [Command Reference](./commands.md)
- [The `pltr api` commands](../api-commands.md)
