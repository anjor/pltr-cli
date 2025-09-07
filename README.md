# pltr-cli

A comprehensive command-line interface for Palantir Foundry APIs, providing 80+ commands for data analysis, dataset management, ontology operations, orchestration, SQL queries, folder management, and administrative tasks.

## Overview

`pltr-cli` provides a powerful and intuitive way to interact with Palantir Foundry from the command line. Built on top of the official `foundry-platform-sdk`, it offers comprehensive access to Foundry's capabilities with a focus on productivity and ease of use.

## ✨ Key Features

- 🔐 **Secure Authentication**: Token and OAuth2 support with encrypted credential storage
- 📊 **Dataset Operations**: Complete dataset management with branches, files, transactions, and views (RID-based API)
- 📁 **Filesystem Management**: Complete filesystem operations including folders, projects, spaces, and resources
- 🏗️ **Project Management**: Create, update, and manage Foundry projects within spaces
- 🌐 **Space Management**: Administer spaces, manage members, and control access
- 🔐 **Resource Permissions**: Grant, revoke, and manage role-based access to resources
- 🔗 **Connectivity & Imports**: Manage external connections and import files/tables from various data sources
- 🎯 **Comprehensive Ontology Access**: 13 commands for objects, actions, and queries
- 🏗️ **Orchestration Management**: Create, manage, and monitor builds, jobs, and schedules
- 🎬 **MediaSets Operations**: Upload, download, and manage media content with transaction support
- 📝 **Full SQL Support**: Execute, submit, monitor, and export query results
- 👥 **Admin Operations**: User, group, role, and organization management (16 commands)
- 💻 **Interactive Shell**: REPL mode with tab completion and command history
- ⚡ **Shell Completion**: Auto-completion for bash, zsh, and fish
- 🎨 **Rich Output**: Beautiful terminal formatting with multiple export formats (table, JSON, CSV)
- 👤 **Multi-Profile Support**: Manage multiple Foundry environments seamlessly

## Installation

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

### 2. Verify Connection

Test your setup:

```bash
pltr verify
```

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

- **Profile Configuration**: `~/.config/pltr/profiles.json`
- **Credentials**: Encrypted in system keyring (never stored in plain text)
- **Shell History**: `~/.config/pltr/repl_history` (for interactive mode)

### Environment Variables

For CI/CD and automation, use environment variables:

```bash
# Token authentication
export FOUNDRY_TOKEN="your-api-token"
export FOUNDRY_HOST="foundry.company.com"

# OAuth2 authentication
export FOUNDRY_CLIENT_ID="your-client-id"
export FOUNDRY_CLIENT_SECRET="your-client-secret"
export FOUNDRY_HOST="foundry.company.com"
```

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

- ✅ **80+ Commands** across 10 command groups
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
