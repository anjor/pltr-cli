# Claude Code Skill

This repository includes a Claude Code skill that helps you work effectively with Palantir Foundry using the pltr-cli.

## What is This?

The `claude_skill` directory contains a Claude Code skill that provides Claude with knowledge about the pltr-cli commands, workflows, and best practices. When you use Claude Code in this repository or install the skill, Claude will automatically recognize Foundry-related tasks and provide accurate guidance.

## Installation

### Option 1: Use Within This Repository

The skill is automatically available when you clone this repository and use Claude Code within it.

### Option 2: Install Globally

To make the skill available across all your projects:

```bash
# Copy to your personal skills directory
cp -r claude_skill ~/.claude/skills/pltr
```

## Prerequisites

Before using the skill, ensure you have:

1. **Claude Code installed** - [Installation instructions](https://docs.anthropic.com/claude-code)
2. **pltr-cli installed**:
   ```bash
   pip install pltr-cli
   # or
   pipx install pltr-cli
   ```
3. **Authentication configured**:
   ```bash
   pltr configure configure
   pltr verify
   ```

## Usage

Simply ask Claude Code questions about Foundry tasks. The skill will automatically activate based on your request.

### Example Prompts

**Getting Started:**
- "How do I configure authentication for pltr?"
- "Help me verify my Foundry connection"

**Data Operations:**
- "How do I query a dataset?"
- "Download files from dataset ri.foundry.main.dataset.abc123"
- "Execute SQL query to count rows in my table"

**Orchestration:**
- "Help me set up a daily build schedule"
- "Show me how to monitor build jobs"
- "Create a schedule that runs at 2 AM"

**Permissions:**
- "Grant viewer access to john.doe on my dataset"
- "Set up team permissions for a new project"
- "Audit who has access to this resource"

**Workflows:**
- "Help me create an ETL pipeline script"
- "How do I do cohort analysis with SQL?"
- "Set up data quality monitoring"

## Skill Structure

```
claude_skill/
├── SKILL.md                    # Main skill file
├── reference/                  # Command references
│   ├── quick-start.md         # Setup and authentication
│   ├── dataset-commands.md    # Dataset operations
│   ├── sql-commands.md        # SQL queries
│   ├── orchestration-commands.md  # Builds, jobs, schedules
│   ├── ontology-commands.md   # Ontology operations
│   ├── admin-commands.md      # User/group management
│   ├── filesystem-commands.md # Folders, spaces, projects
│   ├── connectivity-commands.md   # Connections, imports
│   └── mediasets-commands.md  # Media operations
└── workflows/                  # Common patterns
    ├── data-analysis.md       # Analysis workflows
    ├── data-pipeline.md       # ETL and pipelines
    └── permission-management.md   # Access control
```

## How It Works

Claude Code skills use on-demand loading. When you ask a question:

1. Claude reads the main `SKILL.md` file to understand the CLI
2. Based on your task, Claude loads relevant reference files
3. Claude provides accurate, contextual guidance

This approach minimizes token usage while providing comprehensive knowledge.

## Customization

You can extend the skill by:

1. **Adding reference files**: Create new `.md` files in `reference/` for additional topics
2. **Adding workflows**: Create new `.md` files in `workflows/` for common patterns
3. **Modifying SKILL.md**: Update the main skill file to reference new content

## Troubleshooting

### Skill Not Activating

If Claude doesn't seem to use the skill:

1. Verify the skill directory exists at the correct path
2. Check that `SKILL.md` has valid YAML frontmatter
3. Use trigger keywords like "Foundry", "pltr", "dataset", "SQL query"

### Incorrect Commands

If Claude suggests incorrect commands:

1. The CLI may have been updated - check `pltr --help`
2. Update the relevant reference file in `claude_skill/reference/`

## Contributing

To improve the skill:

1. Test commands and verify they work
2. Update reference files with correct syntax
3. Add common patterns to workflow files
4. Submit a PR with your improvements

## Related Documentation

- [Quick Start Guide](quick-start.md)
- [Command Reference](commands.md)
- [Common Workflows](workflows.md)
- [Authentication Guide](authentication.md)
