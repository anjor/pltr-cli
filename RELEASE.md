# Release Process

This document describes how to create releases for pltr-cli using the automated release script.

## Overview

The release script (`scripts/release.py`) supports both interactive and non-interactive modes to accommodate different use cases:
- **Interactive mode**: For human developers who want to review and confirm each step
- **Non-interactive mode**: For AI agents and automated systems that need to create releases programmatically

## Quick Start

### For Humans (Interactive Mode)

```bash
# Patch release (0.5.1 → 0.5.2)
python scripts/release.py --type patch

# Minor release (0.5.1 → 0.6.0)
python scripts/release.py --type minor

# Major release (0.5.1 → 1.0.0)
python scripts/release.py --type major

# Specific version
python scripts/release.py --version 0.6.0
```

### For AI Agents/Automation (Non-Interactive Mode)

```bash
# Create release without prompts, don't push
python scripts/release.py --version 0.5.2 --yes --no-push

# Create release and push automatically
python scripts/release.py --type patch --yes --push

# Test what would happen (dry run)
python scripts/release.py --version 0.5.2 --dry-run
```

## Command-Line Arguments

| Argument | Description |
|----------|-------------|
| `--version X.Y.Z` | Specify exact version to release |
| `--type {major\|minor\|patch}` | Bump version automatically |
| `--yes`, `-y` | Skip all confirmation prompts (non-interactive mode) |
| `--push` | Push to origin without asking (requires `--yes`) |
| `--no-push` | Don't push to origin (useful for testing) |
| `--dry-run` | Show what would be done without making changes |

## What the Script Does

1. **Validates environment**:
   - Checks that you're in a git repository
   - Ensures working directory is clean (no uncommitted changes)
   - Validates version format

2. **Version handling**:
   - Gets current version from `pyproject.toml`
   - Calculates or validates new version
   - Warns if version already exists or is the same as current

3. **Creates release**:
   - Updates version in `pyproject.toml`
   - Creates git commit with message like "patch: Release version 0.5.2"
   - Creates git tag like "v0.5.2"

4. **Optional push**:
   - Pushes commit and tag to origin (triggers GitHub Actions)
   - Can be automatic (`--push`), skipped (`--no-push`), or prompted (default)

## Usage Examples

### Interactive Development Workflow
```bash
# Make your changes
git add .
git commit -m "feat: add new feature"

# Create a patch release interactively
python scripts/release.py --type patch
# → Script will prompt for confirmation
# → Script will ask if you want to push

# The script will:
# 1. Update pyproject.toml (0.5.1 → 0.5.2)
# 2. Create commit "patch: Release version 0.5.2"
# 3. Create tag "v0.5.2"
# 4. Ask if you want to push to trigger publishing
```

### AI Agent Workflow
```bash
# AI agent creates a release without any prompts
python scripts/release.py --version 0.5.2 --yes --no-push

# The script will:
# 1. Update pyproject.toml to version 0.5.2
# 2. Create commit "release: Release version 0.5.2"
# 3. Create tag "v0.5.2"
# 4. NOT push (--no-push specified)
# 5. Print instructions for manual push if needed
```

### Testing/Validation Workflow
```bash
# See what would happen without making changes
python scripts/release.py --version 0.6.0 --dry-run

# Create release locally but don't push (for testing)
python scripts/release.py --version 0.6.0 --yes --no-push
```

## GitHub Actions Integration

When commits and tags are pushed to the repository, GitHub Actions will automatically:
1. Build the package
2. Run tests
3. Publish to PyPI (for tagged releases)
4. Create GitHub release with release notes

Monitor the workflow at: https://github.com/anjor/pltr-cli/actions

## Error Handling

The script handles several common error scenarios:

- **Dirty working directory**: Script will fail if there are uncommitted changes
- **Duplicate versions**: Warns if trying to release the same version as current
- **Existing tags**: Warns if git tag already exists locally or remotely
- **Invalid versions**: Validates semantic version format (X.Y.Z)
- **Missing arguments**: Requires either `--version` or `--type`
- **Invalid combinations**: Prevents conflicting flags like `--push` and `--no-push`

## Troubleshooting

### "EOFError: EOF when reading a line"
This happens when running the script in non-interactive mode without the `--yes` flag. Add `--yes` to skip prompts.

### "Tag already exists"
The script will warn you and ask for confirmation. You can:
- Delete the existing tag: `git tag -d v0.5.2`
- Use a different version number
- Continue anyway (not recommended)

### "Working directory is not clean"
Commit or stash your changes before running the release script:
```bash
git add .
git commit -m "your changes"
# OR
git stash
```

## Best Practices

1. **Always test with `--dry-run` first** when trying new version numbers
2. **Use `--no-push` for testing** to avoid accidental pushes
3. **Follow semantic versioning**: patch for bug fixes, minor for features, major for breaking changes
4. **Keep working directory clean** before creating releases
5. **Monitor GitHub Actions** after pushing to ensure successful publishing
