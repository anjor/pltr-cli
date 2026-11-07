### Added

- For maintainers: `scripts/smoke.py`, a live smoke test of the pltr CLI
  (#189). Run against a real stack, it prints a pass/fail/skip table (Markdown
  with `--markdown`) to paste into a PR:
  `uv run python scripts/smoke.py [--profile P] [--allow-writes --scratch-folder RID]
  [--only GROUP...] [--include-admin] [--markdown] [--list]`.
  - Each check runs the real `pltr` in a subprocess with stdin closed and
    `--format json` (one with `--format csv`), and checks the output contract
    as well as the result: exit code, exactly one JSON document on stdout,
    JSON Lines on stderr, and a failure's structured error (`type`,
    `errorName`, `exitCode`), which the report shows.
  - Read-only checks: datasets (get, branches, files list/info/download,
    transactions, schema, reading a table as JSON and CSV, schedules, jobs),
    SQL (execute, submit, status, wait, results), ontology objects (list
    ontologies, object types, list, get, search with a typed `--where`,
    aggregate, count, linked objects), actions (validate only), builds and
    schedules (search with filters, get, get-batch, jobs, schedules, runs),
    filesystem reads, one generated `pltr api` command per namespace,
    `pltr verify`, the error contract (404, invalid RID, a destructive command
    without `--yes`), environment-variable auth with a rejected token and
    rejected OAuth client credentials (exit 3), and optional checks for
    functions, media sets, AIP Agents, widgets, third-party applications,
    connectivity, data health, models, streams and language models.
  - Inputs come from `./smoke.toml` or `--config FILE` (TOML or JSON; example:
    `scripts/smoke.example.toml`), `--<input>` flags or `--set KEY=VALUE`.
    Many are found by earlier checks (the ontology, object type, object, link
    type, a recent build, its jobs, a schedule, ...). A check without its
    input is skipped, not failed.
  - `--allow-writes --scratch-folder RID` adds a write pass in a folder it
    creates inside the scratch folder: a dataset, uploads (a file, into an open
    transaction, with `--transaction-type`, a directory), downloads compared
    byte for byte, commit and abort, schema apply and set, reading the
    uploaded CSV files back, a branch, `pltr cp`, trash and restore, a
    streaming dataset and a published record, and (with `writes.space_rid`) a
    project moved to the trash. Everything it creates goes to the trash at the
    end, also after a failure or Ctrl-C; leftovers are reported. It refuses to
    run without a folder RID.
  - `--include-admin` adds checks that need admin permissions (users, groups,
    markings, organizations, roles, audit logs) and, with `--allow-writes`,
    replaces a space, organization or marking you name with its current values
    and checks that nothing changed. Nothing is ever permanently deleted.
- `docs/development/live-verification.md`: how to run the smoke test, and a
  checklist of every "Not verified live" assumption in `changelog.d/`, each
  with the smoke check that covers it or the manual check it needs.
- Tests: `tests/test_smoke_script.py` (the script's logic with a fake runner,
  and every check's command line parsed against the real CLI) and
  `tests/test_smoke_script_stubbed.py` (every check except `auth` run through
  the real CLI against a stateful fake Foundry on `stub_foundry_http`).
- `.gitignore`: `/smoke.toml` and `/smoke.json`, the smoke test's inputs.

### Docs to update

- `RELEASE.md`: add "run `uv run python scripts/smoke.py --markdown` against a
  stack and paste the table into the PR" to the release steps and to the
  SDK-bump checklist (after "Run the full test suite").
- `README.md` "Development"/"Contributing": link
  `docs/development/live-verification.md`, and say that a PR states what was
  verified live (the smoke table) and which assumptions it couldn't check.
- `CHANGELOG.md`: fold this fragment in. When later fragments add "Not
  verified live" items (d1, e1, ...), add them to the checklist in
  `docs/development/live-verification.md`.

### Not verified live

- The smoke script itself has only run against fakes: a fake runner, and the
  real CLI in-process against a stateful fake Foundry. Its expectations of a
  real stack may be wrong, so a failing check can be the script's fault. In
  particular it assumes that:
  - a made-up folder RID answers 404 (403 is accepted too), a made-up token
    401, and made-up OAuth client credentials fail the token request;
  - `resource get`, `folder get` and `project get` return trashed resources
    with their `trashStatus` (`DIRECTLY_TRASHED`), rather than 404;
  - uploaded CSV files with a schema set by `schema set --from-csv
    --dataframe-reader CSV` read back as rows with the CSV's columns;
  - `pltr cp` of the scratch dataset prints the copy as `data[0]`;
  - a streaming dataset can be created in the scratch folder (streaming may
    not be enabled on every stack);
  - `builds search --started-after <30 days ago>` finds a build on an active
    stack (otherwise the build checks skip unless `orchestration.build_rid` is
    set);
  - `admin user search <your username>` finds you (prefix search).
