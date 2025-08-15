# pltr-cli

A comprehensive command-line interface for Palantir Foundry APIs, providing 65+ commands for data analysis, ontology operations, SQL queries, and administrative tasks.

## Overview

`pltr-cli` provides a powerful and intuitive way to interact with Palantir Foundry from the command line. Built on top of the official `foundry-platform-sdk`, it offers comprehensive access to Foundry's capabilities with a focus on productivity and ease of use.

## ✨ Key Features

- 🔐 **Secure Authentication**: Token and OAuth2 support with encrypted credential storage
- 📊 **Dataset Operations**: Get dataset information and create new datasets (RID-based API)
- 🎯 **Comprehensive Ontology Access**: 13 commands for objects, actions, and queries
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

# Execute a simple SQL query
pltr sql execute "SELECT 1 as test"

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
- **[Command Reference](docs/user-guide/commands.md)** - Complete reference for all 65+ commands
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

# Administrative
pltr admin user current        # Current user info
pltr admin user list          # List users

# Interactive & Tools
pltr shell                    # Interactive mode
pltr completion install       # Enable tab completion
```

💡 **Tip**: Use `pltr --help` or `pltr <command> --help` for detailed command help.

For the complete command reference with examples, see **[Command Reference](docs/user-guide/commands.md)**.

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

- ✅ **65+ Commands** across 8 command groups
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
