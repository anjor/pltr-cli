### Added

- **`pltr commands`: the command manifest.** A machine-readable description of
  every command, curated and generated (`pltr api`), so agents can find the
  right command without reading every `--help` page. These commands make no
  Foundry call.
  - `pltr commands list [PATH...]` lists every command (or those under a
    path, such as `api datasets`). With `--format json` it prints the whole
    manifest, `{"pltrVersion", "sdkVersion", "groups", "commands"}`. The
    output is deterministic: sorted by path, no timestamps, and the same on
    every OS, terminal and Python version. `sdkVersion` is the
    foundry-platform-sdk version the `pltr api` tree was generated from (the
    locked version), not the installed one.
  - `pltr commands search <text...>` ranks commands by path, SDK method,
    description and help (plurals, a few verb synonyms such as run/execute,
    and SDK paths such as `Dataset.Branch.list` work). Curated commands rank
    above generated ones that match as well. `--limit/-n` (default 10). JSON:
    `{"data": [...], "totalCount": N}`, each item a summary of a manifest
    entry.
  - `pltr commands show <command path...>` prints one command's entry. It
    accepts `dataset get`, `"dataset get"` or `"pltr dataset get"`. An
    unknown path is a usage error (exit code 2) with suggestions.
  - Each entry has camelCase keys: `path`, `usage`, `description`, `beta`,
    `destructive`, `paged`, `generated`, `local`, `hidden`, `outputFormats`
    (`["binary"]` for generated commands that write raw bytes), `sdkMethods`
    (relative to `FoundryClient`), `httpEndpoints` (labeled direct-HTTP
    commands only), `arguments` and `options` (name, flags, type, required,
    multiple, choices, default, envvar, help; hidden deprecated aliases are
    left out) and `help`. A command without `@pltr_command` metadata has no
    `beta`, `destructive`, `paged` or `sdkMethods` keys (unknown, not false).
- **The agent skill's command reference is generated from the manifest**
  (`claude_skill/reference/`) by `scripts/generate_skill_reference.py`: an
  index, one file per curated group and one per `pltr api` namespace
  (namespaces with more than 50 commands get one file per resource). Run the
  script after any command change; it is the only step. A test fails in CI
  when the committed reference is stale, or when a hand-written skill file
  (`SKILL.md`, the skill README, workflows, `docs/user-guide/claude-skill.md`,
  the README's "Using pltr from agents") mentions a command or option that
  doesn't exist. `--check` runs the same checks locally.
- For developers: `pltr.manifest` (`build_manifest`, `search`,
  `find_command`, ...) and `scripts/check_command_metadata.py`, which
  cross-checks curated commands' `sdk=` metadata against the SDK methods
  their service calls reach.
- README: a "Using pltr from agents" section (headless auth, search, show,
  run with `--format json`, exit codes, `--yes`).

### Changed

- **`claude_skill/` was rewritten.** `SKILL.md` is a short hand-written guide:
  headless authentication and its precedence, the JSON/stdout/stderr
  contract and exit codes, safety rules for destructive commands and
  `--yes`, beta labels, RIDs, finding commands with `pltr commands`, curated
  commands vs `pltr api`, and common workflows. The reference moved to
  `reference/index.md`, `reference/curated/<group>.md` and
  `reference/api/<namespace>.md` (or `reference/api/<namespace>/<resource>.md`).
  If you copied the skill to `~/.claude/skills/`, copy the directory again.
- `docs/user-guide/claude-skill.md` describes the new skill and how to
  regenerate it.

### Removed

- The hand-written skill reference files (`claude_skill/reference/quick-start.md`
  and `claude_skill/reference/*-commands.md`) and workflows
  (`data-analysis.md`, `data-pipeline.md`, `permission-management.md`). They
  documented commands and flags that don't exist, such as
  `resource-role bulk-grant`, `resource-role available-roles`,
  `resource-role get-principal-roles` and `resource get-metadata`. The new
  workflows are `workflows/explore-data.md`, `workflows/builds-and-schedules.md`
  and `workflows/permissions.md`.

### Docs to update

- `docs/user-guide/commands.md`: add the `pltr commands` group (list, search,
  show).
- README "Quick Command Overview": list `pltr commands search`.
- `docs/development/command-contract.md` says `LOCAL` lives only in
  `tests/test_contract/cases/local.py`; this branch defines the three
  `pltr commands` entries in `tests/test_contract/cases/manifest.py` (one
  case module per command module, as for the other keys). Either relax the
  sentence or move the entries.
- After every merge that changes commands (help texts, options, metadata),
  run `uv run python scripts/generate_skill_reference.py` and commit
  `claude_skill/reference/`; the staleness test fails until then. Commands
  that still lack metadata show "SDK: not recorded yet" in the reference.

### Not verified live

- `pltr commands` makes no Foundry call, so there is nothing to verify live.
- The skill's workflow commands and flags are checked mechanically against
  the CLI, but their payloads were not run against a live stack: the
  ontology search filter (`{"type": "eq", "field": ..., "value": ...}`,
  `and`/`gt`, shapes taken from the SDK models), the build target JSON
  (taken from `orchestration builds create --help`), SQL referencing a
  dataset by RID in backticks (the SDK docs say datasets can be referenced
  by path or RID), and role IDs such as `compass:manage`.
