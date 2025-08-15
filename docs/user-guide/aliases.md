# Command Aliases

Command aliases allow you to create shortcuts for frequently used commands, improving your productivity when working with pltr-cli.

## Overview

Aliases are custom shortcuts that expand to full commands. They help you:
- Save time by reducing typing for common operations
- Create personalized workflows
- Simplify complex command sequences
- Build reusable command templates

## Creating Aliases

### Basic Alias

Create a simple alias with the `add` command:

```bash
# Create an alias 'ds' for 'dataset get'
pltr alias add ds "dataset get"

# Now you can use:
pltr ds ri.foundry.main.dataset.123
# Instead of:
pltr dataset get ri.foundry.main.dataset.123
```

### Complex Aliases

Aliases can include options and arguments:

```bash
# Create an alias for SQL queries with JSON output
pltr alias add jsonsql "sql execute --format json"

# Usage:
pltr jsonsql "SELECT * FROM table LIMIT 10"
```

### Overwriting Existing Aliases

Use the `--force` flag to overwrite an existing alias:

```bash
pltr alias add ds "dataset list" --force
```

## Managing Aliases

### List All Aliases

View all configured aliases:

```bash
pltr alias list
```

Output:
```
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Alias   ┃ Command                     ┃
┡━━━━━━━━━┩━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ ds      │ dataset get                 │
│ jsonsql │ sql execute --format json   │
│ onto    │ ontology object-list        │
└─────────┴─────────────────────────────┘
```

### Show Specific Alias

Display details of a single alias:

```bash
pltr alias show ds
# Output: ds → dataset get
```

### Edit an Alias

Modify an existing alias:

```bash
pltr alias edit ds "dataset create"
```

### Remove an Alias

Delete an alias you no longer need:

```bash
pltr alias remove ds
# Or skip confirmation:
pltr alias remove ds --no-confirm
```

### Clear All Aliases

Remove all aliases at once:

```bash
pltr alias clear
# Or skip confirmation:
pltr alias clear --no-confirm
```

## Advanced Features

### Resolve Aliases

See what command an alias expands to:

```bash
pltr alias resolve ds
# Output: ds → dataset get
```

### Export and Import

Export aliases to share with teammates or backup:

```bash
# Export to file
pltr alias export --output my-aliases.json

# Export to stdout
pltr alias export
```

Import aliases from a file:

```bash
# Replace existing aliases
pltr alias import aliases.json

# Merge with existing aliases
pltr alias import aliases.json --merge
```

### Nested Aliases

Aliases can reference other aliases:

```bash
pltr alias add d "dataset"
pltr alias add dg "d get"
# 'dg' expands to 'dataset get'
```

## Common Alias Examples

Here are some useful aliases to get you started:

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

# Combined operations
pltr alias add quicksql "sql execute --format table --limit 100"
pltr alias add mydata "dataset get ri.foundry.main.dataset.my-favorite-dataset"
```

## Shell Integration

Aliases work seamlessly with shell completion and interactive mode:

### Tab Completion

After installing shell completions, alias names are available for tab completion:

```bash
pltr d<TAB>
# Shows: ds, dsc, dsg
```

### Interactive Shell

Aliases are available in the interactive shell:

```bash
pltr shell
pltr> ds ri.foundry.main.dataset.123
# Expands to: dataset get ri.foundry.main.dataset.123
```

## Best Practices

1. **Use meaningful names**: Choose alias names that are easy to remember
2. **Keep it simple**: Avoid overly complex aliases that are hard to understand
3. **Document your aliases**: Export and share team-standard aliases
4. **Avoid conflicts**: Don't use names that conflict with existing commands
5. **Test before sharing**: Verify aliases work correctly before distribution

## Limitations

- Aliases cannot use reserved command names (configure, verify, dataset, etc.)
- Circular references are not allowed and will be detected
- Aliases are expanded only once (no recursive expansion)
- Maximum alias chain depth is 10 to prevent infinite loops

## Configuration Storage

Aliases are stored in `~/.config/pltr/aliases.json` and persist across sessions. The file uses standard JSON format and can be manually edited if needed.

## Troubleshooting

### Alias Not Working

1. Check if the alias exists:
   ```bash
   pltr alias show myalias
   ```

2. Verify the alias syntax:
   ```bash
   pltr alias resolve myalias
   ```

3. Test the expanded command directly:
   ```bash
   pltr <expanded command>
   ```

### Circular Reference Error

If you see a circular reference error, check your alias chain:

```bash
# Example of circular reference (not allowed):
pltr alias add a "b"
pltr alias add b "a"  # Error: would create circular reference
```

### Import Errors

When importing fails, check:
- File exists and is readable
- JSON format is valid
- No circular references in imported aliases
- No conflicts with reserved command names
