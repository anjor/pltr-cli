# Command Aliases

Command aliases are shortcuts for pltr command lines you type often.

## Overview

An alias replaces the first word of a pltr command line. Anything you type
after the alias is appended to the command it stands for:

```bash
# Create an alias 'ds' for 'dataset get'
pltr alias add ds "dataset get"

# Now this:
pltr ds ri.foundry.main.dataset.123
# runs:
pltr dataset get ri.foundry.main.dataset.123
```

Aliases are local: they live in `aliases.json` in pltr's configuration
directory (`~/.config/pltr/`, or `$XDG_CONFIG_HOME/pltr/`), and the alias
commands never call Foundry.

## Creating Aliases

### Basic Alias

```bash
pltr alias add ds "dataset get"
```

### Aliases with Options

The command can include options and arguments:

```bash
# SQL queries with JSON output
pltr alias add jsonsql "sql execute --format json"

# Usage:
pltr jsonsql "SELECT * FROM table LIMIT 10"
```

### Replacing an Existing Alias

`add` refuses to replace an alias of the same name unless you pass
`--force` (`-f`):

```bash
pltr alias add ds "dataset create" --force
```

### Names You Can't Use

An alias can't take the name of a pltr command (`dataset`, `folder`, `api`,
`configure`, ... any top-level command) or `help`, so it can never hide a
real command.

## Managing Aliases

### List All Aliases

```bash
pltr alias list
```

```
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Alias   ┃ Command                   ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ds      │ dataset get               │
│ jsonsql │ sql execute --format json │
│ onto    │ ontology object-list      │
└─────────┴───────────────────────────┘
```

`--format json` prints `{"data": [{"name": "ds", "command": "dataset get"}, ...]}`
and `--format csv` prints `Alias,Command` rows.

### Show One Alias

```bash
pltr alias show ds
pltr alias show ds --format json   # {"name": "ds", "command": "dataset get"}
```

### Edit an Alias

```bash
pltr alias edit ds "dataset create"
```

### Remove an Alias

`remove` asks for confirmation; `--yes` (`-y`) skips it:

```bash
pltr alias remove ds
pltr alias remove ds --yes
```

### Clear All Aliases

```bash
pltr alias clear
pltr alias clear --yes
```

When stdin is not a terminal (scripts, CI, agents), nothing is prompted:
`remove` and `clear` fail with exit code 2 unless you pass `--yes`. The old
`--no-confirm` flag still works for now but is deprecated; use `--yes`.

## Advanced Features

### Resolve Aliases

See the command an alias finally runs:

```bash
pltr alias resolve ds
pltr alias resolve ds --format json   # {"name": "ds", "command": "dataset get"}
```

### Aliases of Aliases

An alias can stand for another alias when its command is exactly that
alias's name:

```bash
pltr alias add dg "dataset get"
pltr alias add d dg
# 'd' runs 'dataset get'
```

Only the whole command is looked up again: an alias such as `"dg --format json"`
runs `dg --format json`, and `dg` is not expanded there. Chains are followed
up to 10 levels, and circular references are rejected.

### Export and Import

Export aliases to share them or back them up. The export is a JSON object of
alias names to commands, the format `import` reads:

```bash
# Export to a file
pltr alias export --output my-aliases.json

# Export to stdout
pltr alias export
```

Import aliases from a file:

```bash
# Replace all existing aliases (asks first; --yes skips)
pltr alias import aliases.json

# Keep existing aliases; imported ones of the same name win
pltr alias import aliases.json --merge
```

Imported aliases that would create a circular reference are skipped with a
warning. A file that isn't a JSON object of names to commands, or that uses
a pltr command name, is rejected before anything changes.

## Common Alias Examples

```bash
# Dataset operations
pltr alias add dsg "dataset get"
pltr alias add dsc "dataset create"

# SQL shortcuts
pltr alias add sq "sql execute"
pltr alias add sqj "sql execute --format json"
pltr alias add sqc "sql execute --format csv"
pltr alias add sqx "sql export"

# Ontology shortcuts
pltr alias add ol "ontology list"
pltr alias add oo "ontology object-list"
pltr alias add oget "ontology object-get"

# Admin shortcuts
pltr alias add ul "admin user list"
pltr alias add uc "admin user current"
pltr alias add gl "admin group list"

# A fixed resource
pltr alias add mydata "dataset get ri.foundry.main.dataset.my-favorite-dataset"
```

## Shell Integration

### Tab Completion

With shell completion installed (`pltr completion install`), alias names
complete as arguments of `pltr alias show`, `edit`, `remove` and `resolve`.

### Interactive Shell

Aliases expand in the interactive shell, and alias names complete there:

```bash
pltr shell
pltr> ds ri.foundry.main.dataset.123
# runs: dataset get ri.foundry.main.dataset.123
```

## Errors and Exit Codes

The alias commands follow pltr's error contract (`--format json` gives a
structured error on stderr):

| Situation | Exit code |
|---|---|
| Unknown alias (`show`, `edit`, `remove`, `resolve`) | 5 (`not_found`) |
| Name clash without `--force`, a pltr command name, a circular reference, an unreadable or invalid import file | 2 (`usage_error`) |
| `remove`, `clear` or a replacing `import` without `--yes` when stdin is not a terminal | 2 (`confirmation_required`) |
| "No" at a confirmation prompt | 1 (`aborted`) |

## Best Practices

1. **Use meaningful names**: Choose alias names that are easy to remember
2. **Keep it simple**: Avoid overly complex aliases that are hard to understand
3. **Document your aliases**: Export and share team-standard aliases
4. **Test before sharing**: Verify aliases work correctly before distribution

## Troubleshooting

### Alias Not Working

1. Check that the alias exists and what it runs:
   ```bash
   pltr alias resolve myalias
   ```

2. Run the resolved command directly:
   ```bash
   pltr <resolved command>
   ```

3. If `pltr myalias` reports "No such command", run it through
   `python -m pltr myalias` or inside `pltr shell`: in this release the
   `pltr` executable itself doesn't expand aliases yet.

### Circular Reference Error

```bash
pltr alias add a "b"
pltr alias add b "a"  # Error: would create a circular reference
```
