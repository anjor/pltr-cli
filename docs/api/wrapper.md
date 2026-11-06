# API Wrapper Documentation

Developer guide for understanding and extending pltr-cli. Learn about the architecture, service layer, and how to add new functionality.

## 🏗️ Architecture Overview

pltr-cli is built with a layered architecture that separates concerns and enables extensibility:

```
CLI Layer (Typer)
    ↓
Command Layer (commands/)
    ↓
Service Layer (services/)
    ↓
foundry-platform-sdk
    ↓
Foundry APIs
```

### Key Components

- **CLI Layer**: Typer-based command-line interface
- **Command Layer**: Command implementations with argument parsing
- **Service Layer**: Business logic and SDK integration
- **Authentication**: Secure credential management with keyring
- **Configuration**: Profile and settings management
- **Utilities**: Formatting, progress, and helper functions

## 📦 Project Structure

```
src/pltr/
├── cli.py                  # Main CLI entry point
├── __init__.py            # Package initialization
├── __main__.py            # Console script entry point
├── auth/                  # Authentication system
│   ├── base.py           # Auth base classes and interfaces
│   ├── manager.py        # Authentication manager
│   ├── oauth.py          # OAuth2 implementation
│   ├── storage.py        # Credential storage with keyring
│   └── token.py          # Token-based authentication
├── commands/             # CLI command implementations
│   ├── admin.py         # Admin commands (user, group, role, org)
│   ├── completion.py    # Shell completion management
│   ├── configure.py     # Profile configuration commands
│   ├── dataset.py       # Dataset operations
│   ├── ontology.py      # Ontology operations
│   ├── shell.py         # Interactive shell mode
│   ├── sql.py           # SQL query commands
│   └── verify.py        # Authentication verification
├── config/              # Configuration management
│   ├── profiles.py      # Profile management
│   └── settings.py      # Settings and preferences
├── services/            # Service layer (business logic)
│   ├── admin.py         # Admin service wrapper
│   ├── base.py          # Base service class
│   ├── dataset.py       # Dataset service wrapper
│   ├── ontology.py      # Ontology service wrapper
│   └── sql.py           # SQL service wrapper
└── utils/               # Utility functions
    ├── completion.py    # Tab completion helpers
    ├── formatting.py    # Output formatting (table, JSON, CSV)
    └── progress.py      # Progress indicators
```

## 🔧 Service Layer API

The service layer provides a clean, pythonic interface to Foundry APIs.

### Base Service

All services inherit from `BaseService`:

```python
from pltr.services.base import BaseService
from pltr.auth.manager import AuthManager

class BaseService:
    """Base class for all Foundry API services."""

    def __init__(self, auth_manager: AuthManager):
        self.auth_manager = auth_manager
        self.client = auth_manager.get_client()

    def _handle_api_error(self, error: Exception) -> None:
        """Handle and format API errors consistently."""
        # Error handling implementation
```

### Using Services Programmatically

```python
from pltr.auth.manager import AuthManager
from pltr.services.sql import SqlService
from pltr.services.ontology import OntologyService

# Initialize authentication
auth_manager = AuthManager(profile="production")

# Create service instances
sql_service = SqlService(auth_manager)
ontology_service = OntologyService(auth_manager)

# Execute operations
result = sql_service.execute_query("SELECT COUNT(*) FROM my_table")
ontologies = ontology_service.list_ontologies()
```

### SQL Service API

```python
class SqlService(BaseService):
    """Service for SQL query operations."""

    def execute_query(self, query: str, timeout: int = 300,
                     fallback_branches: Optional[List[str]] = None) -> List[Dict]:
        """Execute a SQL query and return results."""

    def submit_query(self, query: str,
                    fallback_branches: Optional[List[str]] = None) -> str:
        """Submit a query asynchronously and return query ID."""

    def get_query_status(self, query_id: str) -> Dict:
        """Get the status of a submitted query."""

    def get_query_results(self, query_id: str) -> List[Dict]:
        """Get results of a completed query."""

    def cancel_query(self, query_id: str) -> bool:
        """Cancel a running query."""

    def wait_for_query(self, query_id: str, timeout: int = 300) -> List[Dict]:
        """Wait for query completion and return results."""
```

### Ontology Service API

```python
class OntologyService(BaseService):
    """Service for ontology operations."""

    def list_ontologies(self, page_size: Optional[int] = None) -> List[Dict]:
        """List all available ontologies."""

    def get_ontology(self, ontology_rid: str) -> Dict:
        """Get details of a specific ontology."""

class ObjectTypeService(BaseService):
    """Service for object type operations."""

    def list_object_types(self, ontology_rid: str,
                         page_size: Optional[int] = None) -> List[Dict]:
        """List object types in an ontology."""

    def get_object_type(self, ontology_rid: str, object_type: str) -> Dict:
        """Get details of a specific object type."""

class OntologyObjectService(BaseService):
    """Service for ontology object operations."""

    def list_objects(self, ontology_rid: str, object_type: str,
                    properties: Optional[List[str]] = None,
                    page_size: Optional[int] = None) -> List[Dict]:
        """List objects of a specific type."""

    def get_object(self, ontology_rid: str, object_type: str,
                  primary_key: str,
                  properties: Optional[List[str]] = None) -> Dict:
        """Get a specific object by primary key."""
```

### Dataset Service API

```python
class DatasetService(BaseService):
    """Service for dataset operations."""

    def get_dataset(self, dataset_rid: str) -> Dict:
        """Get dataset information by RID."""

    def create_dataset(self, name: str,
                      parent_folder_rid: Optional[str] = None) -> Dict:
        """Create a new dataset."""
```

### Admin Service API

```python
class AdminService(BaseService):
    """Service for administrative operations."""

    def list_users(self, page_size: Optional[int] = None) -> List[Dict]:
        """List all users in the organization."""

    def get_user(self, user_id: str) -> Dict:
        """Get information about a specific user."""

    def get_current_user(self) -> Dict:
        """Get information about the current user."""

    def search_users(self, query: str,
                    page_size: Optional[int] = None) -> List[Dict]:
        """Search for users by query string."""

    def list_groups(self, page_size: Optional[int] = None) -> List[Dict]:
        """List all groups in the organization."""

    def create_group(self, name: str, description: Optional[str] = None,
                    org_rid: Optional[str] = None) -> Dict:
        """Create a new group."""
```

## 🔐 Authentication System

### Authentication Manager

The `AuthManager` handles authentication and client creation:

```python
from pltr.auth.manager import AuthManager

# Initialize with profile
auth_manager = AuthManager(profile="production")

# Get authenticated client
client = auth_manager.get_client()

# Get current profile info
profile_info = auth_manager.get_current_profile()
```

### Custom Authentication

For advanced use cases, you can create custom authentication:

```python
from pltr.auth.base import BaseAuth
from foundry_sdk import FoundryClient

class CustomAuth(BaseAuth):
    """Custom authentication implementation."""

    def get_client(self, hostname: str) -> FoundryClient:
        """Create and return authenticated client."""
        # Your custom authentication logic
        return FoundryClient(auth=your_auth, hostname=hostname)

# Use custom authentication
auth_manager = AuthManager()
auth_manager.set_auth(CustomAuth())
```

## 🎯 Adding New Commands

### Step 1: Create Service Method

Add business logic to the appropriate service:

```python
# services/ontology.py
class OntologyService(BaseService):
    def new_operation(self, ontology_rid: str, param: str) -> Dict:
        """New ontology operation."""
        try:
            # Use foundry-platform-sdk
            result = self.client.ontology.some_new_method(
                ontology_rid=ontology_rid,
                parameter=param
            )
            return result
        except Exception as e:
            self._handle_api_error(e)
```

### Step 2: Add CLI Command

Create the command interface:

```python
# commands/ontology.py
@app.command()
def new_command(
    ontology_rid: str = typer.Argument(..., help="Ontology RID"),
    param: str = typer.Option(..., help="Required parameter"),
    profile: Optional[str] = typer.Option(None, help="Profile name"),
    format: OutputFormat = typer.Option(OutputFormat.TABLE, help="Output format"),
    output: Optional[Path] = typer.Option(None, help="Output file"),
):
    """New ontology command with description."""
    try:
        auth_manager = AuthManager(profile=profile)
        service = OntologyService(auth_manager)

        result = service.new_operation(ontology_rid, param)

        formatter = OutputFormatter(format=format, output=output)
        formatter.format_and_output(result)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
```

### Step 3: Add Tests

Create comprehensive tests. Test services with the `stub_foundry_http` fixture
(`tests/conftest.py`), not a `Mock()` client: it runs the real `FoundryClient` with only HTTP
faked, so a method or argument the SDK doesn't have fails the test. CI also checks every SDK
call statically; see the [SDK call guardrail](../development/sdk-guardrail.md).

```python
# tests/test_services/test_ontology.py
import pytest

@pytest.mark.filterwarnings("error::UserWarning")  # fails if a GA call gets preview=
def test_new_operation(stub_foundry_http):
    """Test new ontology operation against the real SDK client."""
    stub_foundry_http.respond(json={...})  # a realistic Foundry API response (camelCase)

    result = OntologyService().new_operation(ONTOLOGY_RID, "test-param")

    [request] = stub_foundry_http.requests
    assert request.method == "GET"
    assert request.url.path == f"/api/v2/ontologies/{ONTOLOGY_RID}/..."
    assert result[...] == ...  # read from the decoded SDK model

# tests/test_commands/test_ontology.py
def test_new_command(runner, mock_auth_manager):
    """Test new ontology CLI command."""
    result = runner.invoke(app, [
        "new-command",
        "test-rid",
        "--param", "test-value"
    ])

    assert result.exit_code == 0
    assert "expected output" in result.stdout
```

## 🎨 Output Formatting

### Using OutputFormatter

```python
from pltr.utils.formatting import OutputFormatter, OutputFormat

# Create formatter
formatter = OutputFormatter(
    format=OutputFormat.TABLE,  # or JSON, CSV
    output=Path("results.csv")  # optional file output
)

# Format single object
formatter.format_single(data_dict)

# Format list of objects
formatter.format_list(data_list)

# Format with custom columns
formatter.format_table(data_list, ["col1", "col2", "col3"])
```

### Custom Formatting

```python
def custom_format_function(data: List[Dict]) -> str:
    """Custom formatting function."""
    # Your custom formatting logic
    return formatted_string

# Use in command
formatted_output = custom_format_function(result)
console.print(formatted_output)
```

## 🧪 Testing

### Test Structure

```python
# Service tests: a real FoundryClient with only HTTP faked (fixture in tests/conftest.py).
# Assert on the outgoing request; for beta endpoints, assert preview=true in the query.
@pytest.mark.filterwarnings("error::UserWarning")
def test_service_method(stub_foundry_http):
    """Test service layer."""
    stub_foundry_http.respond(json={...})  # realistic Foundry API JSON
    result = YourService().your_method("ri.foundry.main.dataset.abc")
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", "/api/v2/...")

# Command tests
def test_command(runner):
    """Test CLI command."""
    result = runner.invoke(app, ["command", "args"])
    assert result.exit_code == 0
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_services/test_sql.py

# Run with coverage
pytest --cov=pltr --cov-report=html

# Run only unit tests (exclude integration)
pytest tests/ -k "not integration"
```

## 🔌 Extension Points

### Custom Services

Create your own service for custom functionality:

```python
from pltr.services.base import BaseService

class CustomService(BaseService):
    """Custom service for specialized operations."""

    def custom_operation(self, param: str) -> Dict:
        """Custom operation implementation."""
        # Use self.client to access foundry-platform-sdk
        result = self.client.custom_api.method(param)
        return result
```

### Custom Commands

Add commands to existing apps or create new command groups:

```python
from pltr.cli import app

# Add to existing command group
from pltr.commands.ontology import app as ontology_app

@ontology_app.command()
def custom_ontology_command():
    """Custom ontology command."""
    pass

# Or create new command group
custom_app = typer.Typer()

@custom_app.command()
def custom_command():
    """Custom command."""
    pass

# Add to main CLI
app.add_typer(custom_app, name="custom", help="Custom commands")
```

### Configuration Extensions

Extend configuration system:

```python
from pltr.config.settings import Settings

class CustomSettings(Settings):
    """Extended settings with custom options."""

    custom_option: str = "default_value"

    @classmethod
    def load_custom(cls) -> "CustomSettings":
        """Load settings with custom defaults."""
        # Custom loading logic
        return cls()
```

## 📚 Best Practices

### Error Handling

```python
from pltr.utils.exceptions import PltrError

class CustomServiceError(PltrError):
    """Custom service error."""
    pass

def service_method(self):
    try:
        result = self.client.api_call()
        return result
    except SdkError as e:
        raise CustomServiceError(f"Operation failed: {e}")
    except Exception as e:
        self._handle_api_error(e)
```

### Logging

```python
import logging

logger = logging.getLogger(__name__)

def service_method(self):
    logger.debug("Starting operation")
    try:
        result = self.client.api_call()
        logger.info("Operation completed successfully")
        return result
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        raise
```

### Type Hints

```python
from typing import List, Dict, Optional
from pathlib import Path

def service_method(
    self,
    param: str,
    optional_param: Optional[int] = None
) -> Dict[str, Any]:
    """Service method with proper type hints."""
    pass
```

### Documentation

```python
def service_method(self, param: str) -> Dict:
    """
    Service method description.

    Args:
        param: Description of parameter

    Returns:
        Dictionary containing operation results

    Raises:
        CustomServiceError: When operation fails

    Example:
        >>> service = CustomService(auth_manager)
        >>> result = service.service_method("value")
        >>> print(result["key"])
    """
    pass
```

## 🚀 Development Workflow

### Setting Up Development Environment

```bash
# Clone repository
git clone https://github.com/anjor/pltr-cli.git
cd pltr-cli

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Install development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Development Commands

```bash
# Run tests
pytest

# Run linting
ruff check src/

# Run type checking
mypy src/

# Format code
ruff format src/

# Run all pre-commit hooks
pre-commit run --all-files
```

### Release Process

```bash
# Update version and create release
python scripts/release.py --type minor

# Push to trigger automated publishing
git push origin main --tags
```

---

💡 **Pro Tips for Developers:**
- Always inherit from `BaseService` for new services
- Use `OutputFormatter` for consistent output formatting
- Add comprehensive tests for both service and command layers
- Follow existing patterns for error handling and type hints
- Use the existing authentication system rather than creating custom auth
- Check existing services for patterns before implementing new functionality
