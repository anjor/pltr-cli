# Quick Start Guide

From installation to your first Foundry commands.

## Install

An isolated install keeps pltr with the foundry-platform-sdk version it was
tested with (recommended):

```bash
uv tool install pltr-cli    # or: pipx install pltr-cli
```

Or install it into the current environment with `pip install pltr-cli`.
Check the installation:

```bash
pltr --version
```

If the shell can't find `pltr`, the directory your installer puts commands in
isn't on your `PATH` (`uv tool update-shell` fixes that for uv).

## Authenticate

### With a profile

If you have a Foundry API token:

```bash
pltr configure configure
```

pltr asks for the Foundry hostname (for example `foundry.company.com`), the
authentication type (`token` or `oauth`) and the token or client
credentials. The credentials are stored in the system keyring. The profile
is called `default` unless you pass `--profile NAME`, and the first profile
you create becomes the default.

### With environment variables

In CI, containers and agents, skip `configure` and export the credentials:

```bash
export FOUNDRY_HOST="foundry.company.com"
export FOUNDRY_TOKEN="your-token-here"
```

These are used only when no profile is selected, so on a machine that also
has a default profile, the profile wins. See
[Authentication](authentication.md).

### Check it

```bash
pltr verify
```

`verify` prints your user, and "Authentication successful" on stderr.
`pltr verify --format json` also shows which credentials were used.

## First Commands

```bash
# Who am I?
pltr admin user current

# The ontologies you can see
pltr ontology list

# Builds that failed on master
pltr orchestration builds search --status FAILED --branch master

# A SQL query
pltr sql execute "SELECT 1 AS test"

# A dataset's metadata and its first rows (datasets are addressed by RID)
pltr dataset get <dataset-rid>
pltr dataset preview <dataset-rid>
```

Most commands take RIDs (Resource Identifiers) such as
`ri.foundry.main.dataset.<uuid>`. Copy them from Foundry's web interface, or
look them up: `pltr resource get-by-path "/Space/Project/name"`,
`pltr folder list <folder-rid>`.

## Output Formats

```bash
pltr admin user list                    # a table (the default)
pltr admin user list --format json      # JSON, in the API's own field names
pltr admin user list --format csv       # CSV
pltr admin user list --format csv --output users.csv
```

Set `PLTR_FORMAT=json` to make JSON the default. Data goes to stdout;
messages, warnings and errors go to stderr.

## Interactive Mode

```bash
pltr shell
```

In the shell, run commands without the `pltr` prefix:

```
pltr> admin user current
pltr> ontology list
pltr> exit
```

## Shell Completion

```bash
pltr completion install                 # detects your shell
pltr completion install --shell zsh     # or name it: bash, zsh, fish
```

## What's Next?

- [Command Reference](commands.md): every command, with examples, for
  [SQL](commands.md#sql-pltr-sql),
  [datasets](commands.md#datasets-pltr-dataset),
  [orchestration](commands.md#orchestration-pltr-orchestration),
  [ontologies](commands.md#ontology-pltr-ontology),
  [admin](commands.md#admin-pltr-admin) and more
- [Common Workflows](workflows.md): multi-step tasks and scripts
- [Multiple profiles](authentication.md#multiple-profiles): several Foundry
  instances
- [`pltr api`](../api-commands.md): a command for every Foundry Platform SDK
  method
- [Troubleshooting](troubleshooting.md): common problems

Run `pltr --help` for the command groups and `pltr <command> --help` for a
command's options.
