# pltr-cli Documentation

pltr is a command-line interface for the Palantir Foundry Platform API, built
on the official `foundry-platform-sdk`. Start with the
[project README](../README.md) for installation and an overview.

## User Guide

- **[Quick Start Guide](user-guide/quick-start.md)**: install, authenticate and run your first commands
- **[Authentication Setup](user-guide/authentication.md)**: profiles, token and OAuth2, environment variables and their precedence
- **[Command Reference](user-guide/commands.md)**: every curated command, by group, with examples
- **[`pltr api` commands](api-commands.md)**: a generated command for every Foundry Platform SDK method
- **[Pagination](pagination.md)**: paging options and the paged JSON shape
- **[Common Workflows](user-guide/workflows.md)**: multi-step tasks and scripts
- **[Command Aliases](user-guide/aliases.md)**: shortcuts for commands you type often
- **[Claude Code Skill](user-guide/claude-skill.md)**: using pltr from Claude Code
- **[Troubleshooting](user-guide/troubleshooting.md)**: common problems and their fixes

## Examples

- **[Examples Gallery](examples/gallery.md)**: scripts for common tasks
- **[CSV Upload](examples/csv-upload.md)**: uploading CSV files to datasets
- **[Dataset Transactions](features/dataset-transactions.md)**: grouping file changes in transactions

## Upgrading

- **[CHANGELOG](../CHANGELOG.md)**: every release, with its breaking changes
- **[Pagination migration](migration/v2-pagination.md)**: how list commands changed

## Development

- **[The command contract](development/command-contract.md)**: how a command handles output, errors, exit codes, confirmation and beta endpoints, and how to convert or add one
- **[SDK call check](development/sdk-guardrail.md)**: the CI check that every SDK call exists and binds, and how service tests use the real SDK client
- **[Service layer](api/wrapper.md)**: the architecture and how to add a command
- **[Release process](../RELEASE.md)**: releasing, the changelog, and the checklist for bumping `foundry-platform-sdk`
