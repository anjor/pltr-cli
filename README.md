# pltr-cli

A command-line interface tool for interacting with Palantir Foundry APIs.

## Overview

`pltr-cli` provides a streamlined way to interact with Palantir Foundry services from the command line. Built on top of the official `foundry-platform-sdk`, it offers intuitive commands for dataset management, ontology operations, SQL queries, and more.

## Features

- 🔐 **Secure Authentication**: Support for both token and OAuth2 authentication with secure credential storage
- 📊 **Dataset Management**: List, create, upload, and download datasets with progress indicators
- 🔍 **Ontology Operations**: Search and interact with ontology objects and actions
- 📝 **SQL Queries**: Execute SQL queries directly from the command line
- 🎨 **Rich Output**: Beautiful terminal output with table formatting and color support
- 👤 **Multi-Profile Support**: Manage multiple Foundry environments with profile configurations

## Installation

### Using pip

```bash
pip install pltr
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

## Quick Start

### Configure Authentication

Set up your Foundry credentials:

```bash
pltr configure --profile production
```

This will prompt you for:
- Foundry host URL
- Authentication method (token or OAuth2)
- Credentials

### Basic Usage

```bash
# List datasets
pltr dataset list

# Upload a file to a dataset
pltr dataset upload <dataset-id> path/to/file.csv

# Execute a SQL query
pltr sql execute "SELECT * FROM dataset LIMIT 10"

# Search ontology objects
pltr ontology object search "customer name:John"
```

## Command Reference

### Dataset Commands

- `pltr dataset list` - List all accessible datasets
- `pltr dataset get <id>` - Get dataset details
- `pltr dataset upload <id> <file>` - Upload file to dataset
- `pltr dataset download <id>` - Download dataset files

### Ontology Commands

- `pltr ontology object search <query>` - Search for objects
- `pltr ontology object get <id>` - Get specific object
- `pltr ontology action execute <action>` - Execute ontology action

### SQL Commands

- `pltr sql execute <query>` - Execute SQL query
- `pltr sql export <query> --output <file>` - Export query results

### Configuration Commands

- `pltr configure` - Set up authentication
- `pltr configure --profile <name>` - Configure named profile

## Configuration

Configuration files are stored in `~/.pltr/`:
- `~/.pltr/config` - Profile configurations
- Credentials are stored securely in your system keyring

### Environment Variables

You can also configure authentication via environment variables:

```bash
export FOUNDRY_HOST=https://your-foundry.palantir.com
export FOUNDRY_TOKEN=your-token-here
```

## Development

### Prerequisites

- Python 3.9+
- [uv](https://github.com/astral-sh/uv) for dependency management

### Setup

```bash
# Clone the repository
git clone https://github.com/anjor/pltr-cli.git
cd pltr-cli

# Install dependencies
uv sync

# Run tests
uv run pytest

# Format code
uv run ruff format
uv run ruff check --fix
```

### Project Structure

```
pltr-cli/
├── src/
│   └── pltr/
│       ├── cli.py           # Main CLI entry point
│       ├── auth/            # Authentication handling
│       ├── commands/        # CLI command implementations
│       ├── services/        # Foundry service wrappers
│       ├── config/          # Configuration management
│       └── utils/           # Utilities and helpers
└── tests/                   # Test suite
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

Built on top of the official [Palantir Foundry Platform Python SDK](https://github.com/palantir/foundry-platform-python).