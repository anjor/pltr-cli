# Development Plan for pltr-cli

## Project Overview

Building a command-line interface tool for interacting with Palantir Foundry APIs using the official `foundry-platform-sdk`.

## Technology Stack

- **Language**: Python 3.9+
- **Package Manager**: uv
- **CLI Framework**: Typer
- **SDK**: foundry-platform-sdk
- **Authentication**: keyring (secure credential storage)
- **Output**: Rich (terminal formatting)
- **Testing**: pytest
- **Linting**: ruff
- **Type Checking**: mypy

## Git Workflow

- Main branch for stable releases
- Feature branches for development (merge directly to main)
- Commit format: `type(scope): description`
  - feat: New feature
  - fix: Bug fix
  - docs: Documentation
  - test: Testing
  - chore: Maintenance

## Development Phases

### Phase 1: Project Setup ✅
- [x] Initialize git repository
- [x] Create .gitignore for Python/uv
- [x] Create README.md with project overview
- [x] Create DEVELOPMENT_PLAN.md (this file)
- [ ] Make initial commit on main branch
- [ ] Create feature/project-setup branch
- [ ] Initialize uv project structure
- [ ] Add core dependencies
- [ ] Create basic CLI entry point
- [ ] Merge to main

### Phase 2: Authentication Module
- [ ] Create feature/authentication branch
- [ ] Implement auth base classes
- [ ] Add token authentication support
- [ ] Add OAuth2 client authentication
- [ ] Implement secure credential storage with keyring
- [ ] Create `pltr configure` command
- [ ] Add multi-profile support
- [ ] Add environment variable fallback
- [ ] Write tests for auth module
- [ ] Merge to main

### Phase 3: Dataset Commands
- [ ] Create feature/dataset-commands branch
- [ ] Implement dataset service wrapper
- [ ] Add `pltr dataset list` command
- [ ] Add `pltr dataset get <id>` command
- [ ] Add `pltr dataset upload <id> <file>` with progress bar
- [ ] Add `pltr dataset download <id>` with progress bar
- [ ] Add `pltr dataset create` command
- [ ] Add `pltr dataset delete` command
- [ ] Implement branch operations
- [ ] Add output formatting (table, json, csv)
- [ ] Write tests for dataset commands
- [ ] Merge to main

### Phase 4: Ontology Commands
- [ ] Create feature/ontology-commands branch
- [ ] Implement ontology service wrapper
- [ ] Add `pltr ontology object search <query>` command
- [ ] Add `pltr ontology object get <id>` command
- [ ] Add `pltr ontology type list` command
- [ ] Add `pltr ontology action execute <action>` command
- [ ] Add `pltr ontology link operations`
- [ ] Implement filtering and pagination
- [ ] Write tests for ontology commands
- [ ] Merge to main

### Phase 5: SQL Commands
- [ ] Create feature/sql-commands branch
- [ ] Implement SQL service wrapper
- [ ] Add `pltr sql execute <query>` command
- [ ] Add `pltr sql export <query> --output <file>` command
- [ ] Add query result formatting
- [ ] Add support for parameterized queries
- [ ] Implement query history
- [ ] Write tests for SQL commands
- [ ] Merge to main

### Phase 6: Admin Commands
- [ ] Create feature/admin-commands branch
- [ ] Implement admin service wrapper
- [ ] Add `pltr user list` command
- [ ] Add `pltr user get <id>` command
- [ ] Add `pltr group list` command
- [ ] Add `pltr group manage` operations
- [ ] Add permission management commands
- [ ] Write tests for admin commands
- [ ] Merge to main

### Phase 7: Testing & Quality
- [ ] Create feature/testing branch
- [ ] Set up pytest configuration
- [ ] Add unit tests for all modules
- [ ] Add integration tests with mocked API
- [ ] Set up code coverage reporting
- [ ] Configure GitHub Actions CI/CD
- [ ] Add pre-commit hooks
- [ ] Merge to main

### Phase 8: Advanced Features
- [ ] Create feature/advanced branch
- [ ] Add interactive mode (REPL)
- [ ] Implement command aliases
- [ ] Add batch operations support
- [ ] Add caching for improved performance
- [ ] Implement plugin architecture
- [ ] Add command completion
- [ ] Merge to main

### Phase 9: Documentation
- [ ] Create feature/documentation branch
- [ ] Write comprehensive command reference
- [ ] Create quick start guide
- [ ] Add authentication setup tutorial
- [ ] Document common workflows
- [ ] Add troubleshooting guide
- [ ] Create API wrapper documentation
- [ ] Merge to main

### Phase 10: Distribution
- [ ] Create feature/distribution branch
- [ ] Configure package metadata
- [ ] Set up PyPI publishing
- [ ] Create GitHub releases workflow
- [ ] Add Homebrew formula (macOS)
- [ ] Create Docker image
- [ ] Write installation guide
- [ ] Merge to main

## Project Structure

```
pltr-cli/
├── .gitignore
├── .python-version
├── README.md
├── DEVELOPMENT_PLAN.md
├── CLAUDE.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── src/
│   └── pltr/
│       ├── __init__.py
│       ├── cli.py              # Main CLI entry point
│       ├── auth/
│       │   ├── __init__.py
│       │   ├── base.py         # Auth base classes
│       │   ├── token.py        # Token auth
│       │   ├── oauth.py        # OAuth2 auth
│       │   └── storage.py      # Credential storage
│       ├── commands/
│       │   ├── __init__.py
│       │   ├── configure.py    # Configuration commands
│       │   ├── dataset.py      # Dataset commands
│       │   ├── ontology.py     # Ontology commands
│       │   ├── sql.py          # SQL commands
│       │   └── admin.py        # Admin commands
│       ├── services/
│       │   ├── __init__.py
│       │   ├── base.py         # Base service class
│       │   ├── dataset.py      # Dataset service wrapper
│       │   ├── ontology.py     # Ontology service wrapper
│       │   ├── sql.py          # SQL service wrapper
│       │   └── admin.py        # Admin service wrapper
│       ├── config/
│       │   ├── __init__.py
│       │   ├── settings.py     # Configuration management
│       │   └── profiles.py     # Profile management
│       └── utils/
│           ├── __init__.py
│           ├── formatting.py   # Output formatters
│           ├── progress.py     # Progress bars
│           └── exceptions.py   # Custom exceptions
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_auth/
    ├── test_commands/
    ├── test_services/
    └── test_utils/
```

## Command Examples

```bash
# Configuration
pltr configure --profile production
pltr configure --profile development

# Dataset operations
pltr dataset list --limit 10
pltr dataset get dataset-rid-123
pltr dataset upload dataset-rid-123 data.csv --progress
pltr dataset download dataset-rid-123 --output ./downloads/

# Ontology operations
pltr ontology object search "customer name:John"
pltr ontology object get object-rid-456
pltr ontology action execute send-email --params '{"to": "user@example.com"}'

# SQL operations
pltr sql execute "SELECT * FROM dataset LIMIT 10"
pltr sql export "SELECT * FROM dataset" --output results.csv --format csv

# Admin operations
pltr user list --filter "active:true"
pltr group add-member engineering john.doe@company.com
```

## Success Metrics

- [ ] All core Foundry API operations accessible via CLI
- [ ] Secure credential management
- [ ] Comprehensive test coverage (>80%)
- [ ] Clear documentation and examples
- [ ] Fast and responsive command execution
- [ ] Intuitive command structure
- [ ] Cross-platform compatibility (Windows, macOS, Linux)

## Notes

- Use uv for all dependency management
- Follow Python type hints throughout
- Maintain consistent error handling
- Provide helpful error messages
- Keep commands intuitive and discoverable
- Optimize for common use cases
- Support both interactive and scripted usage