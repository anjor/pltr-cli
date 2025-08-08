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
- [x] Make initial commit on main branch
- [x] Create feature/project-setup branch
- [x] Initialize uv project structure
- [x] Add core dependencies
- [x] Create basic CLI entry point
- [x] Merge to main

### Phase 2: Authentication Module ✅
- [x] Create feature/authentication branch
- [x] Implement auth base classes (auth/base.py)
- [x] Add token authentication support (auth/token.py)
- [x] Add OAuth2 client authentication (auth/oauth.py)
- [x] Implement secure credential storage with keyring (auth/storage.py)
- [x] Create `pltr configure` command with subcommands:
  - [x] `pltr configure configure` - Set up authentication
  - [x] `pltr configure list-profiles` - List all profiles
  - [x] `pltr configure set-default` - Set default profile
  - [x] `pltr configure delete` - Delete a profile
- [x] Add multi-profile support (config/profiles.py)
- [x] Add configuration settings management (config/settings.py)
- [x] Add environment variable fallback (FOUNDRY_TOKEN, FOUNDRY_HOST, etc.)
- [x] Add `pltr verify` command for authentication testing
- [x] Write comprehensive test suite (88 tests, 65% coverage)
- [x] Merge to main

### Phase 3: Dataset Commands ✅
- [x] Create feature/dataset-commands branch
- [x] Implement dataset service wrapper
- [x] Add `pltr dataset list` command
- [x] Add `pltr dataset get <id>` command
- [x] Add `pltr dataset upload <id> <file>` with progress bar
- [x] Add `pltr dataset download <id>` with progress bar
- [x] Add `pltr dataset create` command
- [x] Add `pltr dataset delete` command
- [x] Implement branch operations
- [x] Add output formatting (table, json, csv)
- [x] Write tests for dataset commands
- [x] Merge to main

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
- [x] Set up pytest configuration
- [x] Add unit tests for all modules (completed in Phase 2)
- [ ] Add integration tests with mocked API
- [x] Set up code coverage reporting
- [x] Configure GitHub Actions CI/CD
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

### Implementation Progress

**Phase 2 - Authentication Module ✅ (COMPLETED & MERGED):**
- Implemented complete authentication system with base classes for extensibility
- Added support for both token and OAuth2 authentication methods
- Integrated keyring for secure credential storage (passwords never stored in plain text)
- Created comprehensive profile management system allowing multiple Foundry instances
- Configuration stored in XDG-compliant directories (~/.config/pltr/)
- Environment variable support for CI/CD workflows (FOUNDRY_TOKEN, FOUNDRY_HOST, etc.)
- Interactive configuration with user-friendly prompts using Rich library
- Added `pltr verify` command that tests authentication against real Foundry instances
- Comprehensive test suite: 88 tests with 65% code coverage
- Tests include mocking for keyring, HTTP requests, and file system operations
- All critical authentication flows validated with edge case handling
- **Merged via PR #1 on 2025-08-08**

**Phase 3 - Dataset Commands ✅ (COMPLETED & MERGED):**
- Implemented comprehensive dataset management system with BaseService foundation
- Added complete dataset CLI command suite with 9 commands covering all major operations
- Created DatasetService wrapper around foundry-platform-sdk for robust API integration
- Built rich output formatting system supporting table, JSON, and CSV formats
- Integrated file progress tracking with Rich progress bars for upload/download operations
- Added comprehensive branch management capabilities for dataset versioning
- All commands support profile-based authentication and environment variable fallbacks
- Error handling with user-friendly messages and proper exit codes
- Comprehensive test suite: 71 new tests with full command and service coverage
- Service layer tests with mocked SDK interactions and edge case handling
- Command tests using Typer's testing framework with real file operations
- **Merged via PR #3 on 2025-08-08**

**Phase 7 - GitHub Actions CI/CD ✅ (COMPLETED):**
- Set up comprehensive CI/CD pipeline with GitHub Actions
- Multi-Python version testing (3.9, 3.10, 3.11, 3.12)
- Cross-platform testing (Ubuntu, macOS, Windows)
- Integrated uv for fast dependency management
- Automated code quality checks (ruff linting, mypy type checking)
- Test execution with coverage reporting
- Codecov integration for coverage tracking
- **Merged via PR #2 on 2025-08-08**
