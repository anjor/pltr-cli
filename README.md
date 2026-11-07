# pltr-cli

A comprehensive command-line interface for Palantir Foundry APIs, providing 81+ commands for data analysis, dataset management, ontology operations, orchestration, SQL queries, folder management, and administrative tasks.

## Overview

`pltr-cli` provides a powerful and intuitive way to interact with Palantir Foundry from the command line. Built on top of the official `foundry-platform-sdk`, it offers comprehensive access to Foundry's capabilities with a focus on productivity and ease of use.

## ✨ Key Features

- 🔐 **Secure Authentication**: Token and OAuth2 support, with profiles in the system keyring or environment variables for CI and agents (no keyring or setup needed)
- 📊 **Dataset Operations**: Complete dataset management with branches, files, transactions, and views (RID-based API)
- 📁 **Filesystem Management**: Complete filesystem operations including folders, projects, spaces, and resources
- 🏗️ **Project Management**: Create, update, and manage Foundry projects within spaces
- 🌐 **Space Management**: Administer spaces, manage members, and control access
- 🔐 **Resource Permissions**: Grant, revoke, and manage role-based access to resources
- 🔗 **Connectivity & Imports**: Manage external connections and import files/tables from various data sources
- 🎯 **Comprehensive Ontology Access**: 13 commands for objects, actions, and queries
- 🏗️ **Orchestration Management**: Create, manage, and monitor builds, jobs, and schedules
- 🎬 **MediaSets Operations**: Upload, download, and manage media content with transaction support
- 🤖 **Models Management**: Create and inspect ML models and versions in the model registry
- 🌊 **Streams Management**: Manage streaming datasets and publish real-time data
- 💬 **Language Models**: Interact with Claude and OpenAI embeddings for LLM operations
- 📝 **Full SQL Support**: Execute, submit, monitor, and export query results
- 👥 **Admin Operations**: User, group, role, and organization management (16 commands)
- 💻 **Interactive Shell**: REPL mode with tab completion and command history
- ⚡ **Shell Completion**: Auto-completion for bash, zsh, and fish
- 🎨 **Rich Output**: Beautiful terminal formatting with multiple export formats (table, JSON, CSV)
- 👤 **Multi-Profile Support**: Manage multiple Foundry environments seamlessly

## Installation

### Recommended: an isolated install

```bash
uv tool install pltr-cli    # or: pipx install pltr-cli
```

This gives pltr its own environment, with the `foundry-platform-sdk` version
pltr was tested with. pltr accepts a range of SDK versions, but its
[`pltr api`](#every-endpoint-pltr-api) commands are generated from one
version: in a shared environment where another package upgrades the SDK, a
command whose SDK method changed fails with a clear error. Upgrade with
`uv tool upgrade pltr-cli` (or `pipx upgrade pltr-cli`).

### Using pip

```bash
pip install pltr-cli
```

### From source

```bash
# Clone the repository
git clone https://github.com/anjor/pltr-cli.git
cd pltr-cli

# Install with uv
uv sync

# Run the CLI
uv run pltr --help
```

## 🚀 Quick Start

### 1. Configure Authentication

Set up your Foundry credentials:

```bash
pltr configure configure
```

Follow the interactive prompts to enter:
- Foundry hostname (e.g., `foundry.company.com`)
- Authentication method (token or OAuth2)
- Your credentials

Running in CI, a container or an AI agent? Skip `configure` and export
`FOUNDRY_HOST` and `FOUNDRY_TOKEN` instead (see [Authentication](#-authentication)).

### 2. Verify Connection

Test your setup:

```bash
pltr verify
```

`verify` fetches your user from Foundry and shows which credentials it used
(`pltr verify --format json` for scripts).

### 3. Start Exploring

```bash
# Check current user
pltr admin user current

# List available ontologies
pltr ontology list

# Search for builds
pltr orchestration builds search

# Create a new folder
pltr folder create "My Project"

# List root folder contents
pltr folder list ri.compass.main.folder.0

# Manage spaces and projects
pltr space list
pltr project create "My Project" ri.compass.main.space.123
pltr project list --space-rid ri.compass.main.space.123

# Manage resource permissions
pltr resource-role grant ri.compass.main.dataset.123 user123 User viewer
pltr resource-role list ri.compass.main.dataset.123

# Execute a simple SQL query
pltr sql execute "SELECT 1 as test"

# Explore dataset operations (requires dataset RID)
pltr dataset get ri.foundry.main.dataset.abc123
pltr dataset branches list ri.foundry.main.dataset.abc123
pltr dataset files list ri.foundry.main.dataset.abc123

# Dataset transaction management
pltr dataset transactions start ri.foundry.main.dataset.abc123
pltr dataset transactions commit ri.foundry.main.dataset.abc123 <transaction-rid>
pltr dataset files upload myfile.csv ri.foundry.main.dataset.abc123 --transaction-rid <rid>

# Start interactive mode for exploration
pltr shell
```

### 4. Enable Shell Completion

For the best experience:

```bash
pltr completion install
```

📖 **Need more help?** See the **[Quick Start Guide](docs/user-guide/quick-start.md)** for detailed setup instructions.

## Output, errors and exit codes

pltr is built to be scripted, by people and by agents.

- **stdout is data only.** It carries the result and nothing else, in every
  format. Spinners, progress, success and info messages, warnings,
  confirmation prompts and errors go to stderr.
- **Choose the format** with `--format table|json|csv` (`-f`). The default is
  `table`, whether or not stdout is a terminal. Set `PLTR_FORMAT=json` to
  change the default, for example for agents and CI.
- **`--format json` prints exactly one JSON document**: the Foundry SDK's own
  serialization of the result.
  - Field names are the Foundry API's (camelCase, as in Foundry's REST
    docs), null fields are left out, and times are ISO-8601 strings.
  - Lists use the API's paged shape,
    `{"data": [...], "nextPageToken": "..."}`. `nextPageToken` is left out on
    the last page; pass it to `--page-token` to continue. List commands fetch
    one page by default; use `--all` for every page.
  - A command that returns nothing (for example a delete) prints `null`.
- **In JSON mode stderr carries only JSON Lines.** Informational messages are
  suppressed, and warnings look like
  `{"type": "warning", "message": "..."}`. When a command fails, the last
  stderr line is one structured error:

  ```json
  {"type": "not_found", "message": "FolderNotFound: The given Folder could not be found. (folderRid=ri.compass.main.folder.x)", "exitCode": 5, "statusCode": 404, "errorCode": "NOT_FOUND", "errorName": "FolderNotFound", "errorInstanceId": "…", "parameters": {"folderRid": "ri.compass.main.folder.x"}}
  ```

  Keys that don't apply are left out. In table and CSV mode the same error is
  printed as readable text, including the Foundry `errorName`.

| Exit code | Meaning | Error `type` |
|---|---|---|
| 0 | Success | |
| 1 | Unexpected error, or "no" at a confirmation prompt | `unexpected_error`, `aborted` |
| 2 | Usage error: bad or missing arguments, invalid JSON input, or `--yes` required | `usage_error`, `confirmation_required` |
| 3 | Authentication: no usable credentials, or HTTP 401 | `auth_error` |
| 4 | Permission denied (HTTP 403) | `permission_denied` |
| 5 | Not found (HTTP 404) | `not_found`, `api_not_found` |
| 6 | API validation error (HTTP 400, 422) | `validation_error` |
| 7 | Other API or network error: HTTP 409, 413, 429, 5xx, timeouts, connection errors | `conflict`, `request_too_large`, `rate_limited`, `server_error`, `api_error`, `network_error`, `timeout` |

**Destructive commands ask first.** Commands that delete, remove, revoke,
reset, cancel, abort or replace something ask for confirmation, and
`--yes` (`-y`) skips the prompt. pltr never prompts when stdin is not a
terminal: without `--yes` such a command fails with exit code 2 and tells
you to pass `--yes`. The old `--confirm` and `--force` flags still work for
one release as deprecated aliases of `--yes`.

**Beta endpoints** work without extra flags, and their commands are labeled
`[beta]` in `--help`. `--preview` is no longer needed; where it existed it is
accepted and ignored, with a warning, for one release.

Set `PLTR_DEBUG=1` to see a Python traceback for an unexpected error.

> Commands are being moved to this contract module by module (`folder` and
> `space` first). Until a module is converted, some of its status messages
> may still appear on stdout, and its commands may exit with code 1 for every
> error, use their own JSON keys and confirm in their own way.

## Every endpoint: `pltr api`

`pltr api` has a command for every method of the Foundry Platform SDK's V2
client (390 of its 394 methods; the [exceptions](docs/api-commands.md#methods-without-a-command)
are listed with their reasons). The commands are generated from the SDK, so
they mirror it one to one and follow it on every SDK upgrade:

```
pltr api <namespace> <resource> [<sub-resource>...] <method> [ARGUMENTS] [OPTIONS]
```

The curated commands above (`pltr dataset`, `pltr ontology`, ...) stay the
polished path for common tasks, with friendlier arguments and curated tables.
Use `pltr api` for an endpoint they don't cover, or when you want the API's
exact request and response shapes, for example in scripts and agents. Every
`pltr api` command follows the output, error and exit-code rules above.

```bash
pltr api --help                                   # namespaces
pltr api orchestration build --help               # a resource's methods
pltr api admin user get-current --format json
pltr api datasets dataset branch list "$DATASET_RID"
pltr api orchestration build get "$BUILD_RID"
pltr api ontologies linked-object list-linked-objects my-ontology Aircraft N123 flights
```

- **Arguments** are the endpoint's path parameters, mostly RIDs
  (`ri.foundry.main.dataset.<uuid>`); `--help` shows each one's SDK type.
  Everything else is an option named after the SDK parameter (`page_size`
  becomes `--page-size`).
- **JSON inputs**: options that take a model, a union or a dict accept JSON
  in the Foundry API's own shape (camelCase, as in Foundry's API docs),
  inline, as `@file.json` or as `@-` for stdin. The SDK validates it before
  anything is sent:

  ```bash
  pltr api admin user search --where '{"type": "queryString", "value": "jane"}'
  pltr api orchestration build search --where @filter.json --format json
  ```

- **Paging**: list endpoints print one page, in the API's response shape
  with its `nextPageToken`; `--page-token` resumes, and `--max-pages N` or
  `--all` fetch more.
- **Beta** endpoints are labeled `[beta]` and called with `preview=True` for
  you.
- **Destructive** methods (delete, remove, revoke, replace, reset, clear,
  cancel, abort, disable, undeploy, put-schema and a few others) ask for
  confirmation; `--yes` skips it.
- **Binary** responses (file content, Arrow and Parquet results, images) go
  to `--output FILE`, or to stdout when it isn't a terminal.

See **[docs/api-commands.md](docs/api-commands.md)** for the argument
mapping, paging, the destructive list and how the commands are generated.

## 📚 Documentation

pltr-cli provides comprehensive documentation to help you get the most out of the tool:

### 📖 User Guides
- **[Quick Start Guide](docs/user-guide/quick-start.md)** - Get up and running in 5 minutes
- **[Authentication Setup](docs/user-guide/authentication.md)** - Complete guide to token and OAuth2 setup
- **[Command Reference](docs/user-guide/commands.md)** - Complete reference for all 70+ commands
- **[Common Workflows](docs/user-guide/workflows.md)** - Real-world data analysis patterns
- **[Troubleshooting](docs/user-guide/troubleshooting.md)** - Solutions to common issues

### 🔧 Developer Resources
- **[API Wrapper Documentation](docs/api/wrapper.md)** - Architecture and extension guide
- **[Examples Gallery](docs/examples/gallery.md)** - Real-world use cases and automation scripts

### 🎯 Quick Command Overview

**Most Common Commands:**
```bash
# Authentication & Setup
pltr configure configure        # Set up authentication
pltr verify                    # Test connection

# Data Analysis
pltr sql execute "SELECT * FROM table"  # Run SQL queries
pltr ontology list             # List ontologies
pltr dataset get <rid>         # Get dataset info

# Filesystem Management
pltr folder create "My Project"         # Create folders
pltr space create "Team Space" <org-rid> # Create spaces
pltr project create "New Project" <space-rid> # Create projects
pltr resource search "dataset name"     # Search resources
pltr resource-role grant <resource-rid> <user-id> User viewer # Grant permissions

# Orchestration
pltr orchestration builds search       # Search builds
pltr orchestration jobs get <job-rid>  # Get job details
pltr orchestration schedules create   # Create schedule

# MediaSets
pltr media-sets get <set-rid> <item-rid>  # Get media item info
pltr media-sets upload <set-rid> file.jpg "/path/file.jpg" <txn-id>  # Upload media
pltr media-sets download <set-rid> <item-rid> output.jpg  # Download media

# Connectivity & Data Imports
pltr connectivity connection list              # List available connections
pltr connectivity connection get <conn-rid>    # Get connection details
pltr connectivity import file <conn-rid> <source-path> <dataset-rid> --execute  # Import file
pltr connectivity import table <conn-rid> <table-name> <dataset-rid> --execute  # Import table

# Administrative
pltr admin user current        # Current user info
pltr admin user list          # List users
pltr third-party-apps get <rid>  # Get third-party application details

# Interactive & Tools
pltr shell                    # Interactive mode
pltr completion install       # Enable tab completion
```

💡 **Tip**: Use `pltr --help` or `pltr <command> --help` for detailed command help.

For the complete command reference with examples, see **[Command Reference](docs/user-guide/commands.md)**.

### 🏗️ Orchestration Commands

pltr-cli provides comprehensive support for Foundry's Orchestration module:

#### Build Management
```bash
# Search for builds
pltr orchestration builds search

# Get build details
pltr orchestration builds get ri.orchestration.main.build.12345

# Create a new build
pltr orchestration builds create '{"dataset_rid": "ri.foundry.main.dataset.abc"}' --branch main

# Cancel a running build
pltr orchestration builds cancel ri.orchestration.main.build.12345

# List jobs in a build
pltr orchestration builds jobs ri.orchestration.main.build.12345
```

#### Job Management
```bash
# Get job details
pltr orchestration jobs get ri.orchestration.main.job.12345

# Get multiple jobs in batch
pltr orchestration jobs get-batch "rid1,rid2,rid3"
```

#### Schedule Management
```bash
# Get schedule information
pltr orchestration schedules get ri.orchestration.main.schedule.12345

# Create a new schedule
pltr orchestration schedules create '{"type": "BUILD", "target": "dataset-rid"}' \
  --name "Daily Build" --description "Automated daily build"

# Pause/unpause schedules
pltr orchestration schedules pause ri.orchestration.main.schedule.12345
pltr orchestration schedules unpause ri.orchestration.main.schedule.12345

# Execute schedule immediately
pltr orchestration schedules run ri.orchestration.main.schedule.12345

# Delete a schedule
pltr orchestration schedules delete ri.orchestration.main.schedule.12345 --yes
```

**All orchestration commands support:**
- Multiple output formats (table, JSON, CSV)
- File output (`--output filename`)
- Profile selection (`--profile production`)
- Preview mode for schedules (`--preview`)

### 🎬 MediaSets Commands

pltr-cli provides full support for Foundry's MediaSets module for managing media content:

#### Media Item Operations
```bash
# Get media item information
pltr media-sets get ri.mediasets.main.media-set.abc ri.mediasets.main.media-item.123

# Get media item RID by path
pltr media-sets get-by-path ri.mediasets.main.media-set.abc "/images/photo.jpg"

# Get a reference for embedding
pltr media-sets reference ri.mediasets.main.media-set.abc ri.mediasets.main.media-item.123
```

#### Transaction Management
```bash
# Create a new upload transaction
pltr media-sets create ri.mediasets.main.media-set.abc --branch main

# Commit transaction (makes uploads available)
pltr media-sets commit ri.mediasets.main.media-set.abc transaction-id-12345

# Abort transaction (deletes uploads)
pltr media-sets abort ri.mediasets.main.media-set.abc transaction-id-12345 --yes
```

#### Upload and Download
```bash
# Upload a file to media set
pltr media-sets upload ri.mediasets.main.media-set.abc \
  /local/path/image.jpg "/media/images/image.jpg" transaction-id-12345

# Download media item (processed version)
pltr media-sets download ri.mediasets.main.media-set.abc \
  ri.mediasets.main.media-item.123 /local/download/image.jpg

# Download original version
pltr media-sets download ri.mediasets.main.media-set.abc \
  ri.mediasets.main.media-item.123 /local/download/original.jpg --original
```

**All MediaSets commands support:**
- Multiple output formats (table, JSON, CSV)
- File output (`--output filename`)
- Profile selection (`--profile production`)
- Preview mode (`--preview`)
- Transaction-based upload workflow

### 🤖 Models Commands

pltr-cli provides support for managing ML models and versions in the Foundry model registry. This is distinct from the LanguageModels module, which handles LLM chat and embeddings.

**Note**: The SDK does not provide a way to list all models. Use the Foundry web UI or Ontology API to discover models.

#### Model Operations
```bash
# Create a new model
pltr models model create "fraud-detector" --folder ri.compass.main.folder.xxx

# Get model details
pltr models model get ri.foundry.main.model.abc123

# Get model as JSON
pltr models model get ri.foundry.main.model.abc123 --format json
```

#### Model Version Operations
```bash
# List all versions of a model
pltr models version list ri.foundry.main.model.abc123

# List with pagination
pltr models version list ri.foundry.main.model.abc123 --page-size 50

# Get next page
pltr models version list ri.foundry.main.model.abc123 \
  --page-size 50 --page-token <token-from-previous-response>

# Get specific version details
pltr models version get ri.foundry.main.model.abc123 v1.0.0

# Save version details to file
pltr models version get ri.foundry.main.model.abc123 v1.0.0 \
  --format json --output version-details.json
```

**All Models commands support:**
- Multiple output formats (table, JSON, CSV)
- File output (`--output filename`)
- Profile selection (`--profile production`)
- Preview mode (`--preview`)

**Note**: Model version creation requires specialized ML tooling and is not provided via CLI. Use the Python SDK directly for version creation with dill-serialized models.

### 📊 Dataset Transaction Management

pltr-cli provides comprehensive transaction management for datasets, allowing atomic operations with rollback capability:

#### Transaction Lifecycle
```bash
# Start a new transaction
pltr dataset transactions start ri.foundry.main.dataset.abc123 --branch master --type APPEND
# Returns transaction RID for use in subsequent operations

# Check transaction status
pltr dataset transactions status ri.foundry.main.dataset.abc123 ri.foundry.main.transaction.xyz

# List all transactions for a dataset
pltr dataset transactions list ri.foundry.main.dataset.abc123 --branch master

# Commit a transaction (make changes permanent)
pltr dataset transactions commit ri.foundry.main.dataset.abc123 ri.foundry.main.transaction.xyz

# Abort a transaction (discard all changes)
pltr dataset transactions abort ri.foundry.main.dataset.abc123 ri.foundry.main.transaction.xyz --yes
```

#### File Operations with Transactions
```bash
# Upload files within a transaction
pltr dataset files upload data.csv ri.foundry.main.dataset.abc123 \
  --transaction-rid ri.foundry.main.transaction.xyz

# Multiple file uploads in same transaction
pltr dataset files upload file1.csv ri.foundry.main.dataset.abc123 \
  --transaction-rid ri.foundry.main.transaction.xyz
pltr dataset files upload file2.csv ri.foundry.main.dataset.abc123 \
  --transaction-rid ri.foundry.main.transaction.xyz

# Commit when ready
pltr dataset transactions commit ri.foundry.main.dataset.abc123 ri.foundry.main.transaction.xyz
```

#### Transaction Types
- **APPEND**: Add new files to dataset
- **UPDATE**: Add new files and overwrite existing ones
- **SNAPSHOT**: Replace entire dataset with new files
- **DELETE**: Remove files from dataset

#### Example Workflow
```bash
# Start a transaction for bulk data update
TRANSACTION=$(pltr dataset transactions start ri.foundry.main.dataset.abc123 \
  --type UPDATE --format json | jq -r '.transaction_rid')

# Upload multiple files
pltr dataset files upload data1.csv ri.foundry.main.dataset.abc123 --transaction-rid $TRANSACTION
pltr dataset files upload data2.csv ri.foundry.main.dataset.abc123 --transaction-rid $TRANSACTION

# Check status before committing
pltr dataset transactions status ri.foundry.main.dataset.abc123 $TRANSACTION

# Commit if everything looks good
pltr dataset transactions commit ri.foundry.main.dataset.abc123 $TRANSACTION
```

**Benefits:**
- **Data Integrity**: Atomic operations with rollback capability
- **Error Recovery**: Clean rollback from failed operations
- **Collaboration**: Better concurrent modification handling
- **Automation**: Reliable data pipeline operations

## ⚙️ Configuration

pltr-cli stores configuration securely using industry best practices:

- **Profile Configuration**: `~/.config/pltr/profiles.json` (or `$XDG_CONFIG_HOME/pltr/`)
- **Credentials**: Encrypted in system keyring (never stored in plain text)
- **Shell History**: `~/.config/pltr/repl_history` (for interactive mode)

pltr only creates the configuration directory when it saves something (for
example `pltr configure`); reading configuration never needs it.

## 🔐 Authentication

Every command authenticates the same way, including the few that call Foundry
endpoints directly. pltr uses the **first** of these that applies:

1. `--profile NAME` on the command line
2. the `PLTR_PROFILE` environment variable (a profile name)
3. the default profile (the first profile you configure, or `pltr configure set-default NAME`)
4. environment variables, when no profile is selected by 1–3:
   - token: `FOUNDRY_HOST` and `FOUNDRY_TOKEN`
   - OAuth2 client credentials: `FOUNDRY_HOST`, `FOUNDRY_CLIENT_ID` and `FOUNDRY_CLIENT_SECRET`

An exported `FOUNDRY_*` variable never overrides, or fills gaps in, a stored
profile. `PLTR_PROFILE` naming a profile that doesn't exist is an error, not a
fallback. Hosts work with or without `https://`. `pltr verify` reports which
source it used.

### Headless use: CI, containers and AI agents

With environment variables there is nothing to set up: no `pltr configure`, no
configuration directory and no system keyring.

```bash
# Token authentication
export FOUNDRY_HOST="foundry.company.com"
export FOUNDRY_TOKEN="your-api-token"

# Or OAuth2 client credentials (used when FOUNDRY_TOKEN isn't set)
export FOUNDRY_HOST="foundry.company.com"
export FOUNDRY_CLIENT_ID="your-client-id"
export FOUNDRY_CLIENT_SECRET="your-client-secret"

pltr verify --format json   # {"authSource": {...}, "user": {...}}
```

These variables are only used when no profile is selected, so on a machine
that also has a default profile, that profile wins. `FOUNDRY_HOSTNAME` (the
Foundry SDK's name for the host) is accepted when `FOUNDRY_HOST` isn't set.

Stored profiles keep their credentials in the system keyring. If a profile is
needed and the keyring is missing, broken or doesn't answer within 30 seconds
(`PLTR_KEYRING_TIMEOUT`), pltr stops with an error that points to the
environment variables instead of hanging.

See **[Authentication Setup](docs/user-guide/authentication.md)** for complete configuration options.

## 🔧 Development

### Prerequisites

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) for dependency management

### Quick Development Setup

```bash
# Clone the repository
git clone https://github.com/anjor/pltr-cli.git
cd pltr-cli

# Install dependencies and development tools
uv sync

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest

# Run linting and formatting
uv run ruff check src/
uv run ruff format src/
uv run mypy src/
```

### Project Architecture

pltr-cli uses a layered architecture:

- **CLI Layer** (Typer): Command-line interface and argument parsing
- **Command Layer**: Command implementations with validation
- **Service Layer**: Business logic and foundry-platform-sdk integration
- **Auth Layer**: Secure authentication and credential management
- **Utils Layer**: Formatting, progress, and helper functions

See **[API Wrapper Documentation](docs/api/wrapper.md)** for detailed architecture information and extension guides.

## 📊 Current Status

pltr-cli is **production-ready** with comprehensive features:

- ✅ **81+ Commands** across 11 command groups
- ✅ **273 Unit Tests** with 67% code coverage
- ✅ **Published on PyPI** with automated releases
- ✅ **Cross-Platform** support (Windows, macOS, Linux)
- ✅ **Comprehensive Documentation** (Quick start, guides, examples)
- ✅ **Interactive Shell** with tab completion and history
- ✅ **CI/CD Ready** with environment variable support

**Latest Release**: Available on [PyPI](https://pypi.org/project/pltr-cli/)

## 🤝 Contributing

Contributions are welcome! Whether you're fixing bugs, adding features, or improving documentation.

### Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes following the existing patterns
4. Add tests for new functionality
5. Run the test suite and linting
6. Commit using conventional commit format (`feat:`, `fix:`, `docs:`, etc.)
7. Push to your branch and create a Pull Request

### Development Guidelines

- Follow existing code patterns and architecture
- Add tests for new functionality
- Update documentation for user-facing changes
- Use type hints throughout
- Follow the existing error handling patterns

See **[API Wrapper Documentation](docs/api/wrapper.md)** for detailed development guidelines.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

Built on top of the official [Palantir Foundry Platform Python SDK](https://github.com/palantir/foundry-platform-python).
