# Command Reference

Complete reference for all pltr-cli commands. The CLI provides 65+ commands across 8 major command groups for comprehensive Foundry API access.

## Global Options

All commands support these global options:
- `--help`: Show help message and exit
- `--version`: Show version and exit

## Common Patterns

### Authentication
Most commands support profile selection:
```bash
pltr <command> --profile production
```

### Output Formats
Most commands support multiple output formats:
```bash
pltr <command> --format table    # Default: Rich table format
pltr <command> --format json     # JSON output
pltr <command> --format csv      # CSV format
pltr <command> --output file.csv # Save to file
```

---

## 🔧 Configuration Commands

### `pltr configure`

Manage authentication profiles for different Foundry instances.

#### `pltr configure configure [OPTIONS]`
Configure authentication for Palantir Foundry.

**Options:**
- `--profile`, `-p` TEXT: Profile name (default: "default")
- `--auth-type` TEXT: Authentication type (token or oauth)
- `--host` TEXT: Foundry host URL
- `--token` TEXT: Bearer token (for token auth)
- `--client-id` TEXT: OAuth client ID
- `--client-secret` TEXT: OAuth client secret

**Examples:**
```bash
# Interactive setup
pltr configure configure

# Token authentication
pltr configure configure --profile prod --auth-type token --host foundry.company.com --token "your-token"

# OAuth authentication
pltr configure configure --profile dev --auth-type oauth --host dev.foundry.com --client-id "id" --client-secret "secret"
```

#### `pltr configure list-profiles`
List all configured profiles.

**Example:**
```bash
pltr configure list-profiles
```

#### `pltr configure set-default PROFILE`
Set a profile as the default.

**Example:**
```bash
pltr configure set-default production
```

#### `pltr configure delete [OPTIONS] PROFILE`
Delete a profile.

**Options:**
- `--force`, `-f`: Skip confirmation

**Example:**
```bash
pltr configure delete old-profile --force
```

---

## ✅ Verification Commands

### `pltr verify [OPTIONS]`
Verify authentication by connecting to Palantir Foundry.

**Options:**
- `--profile`, `-p` TEXT: Profile to verify

**Examples:**
```bash
pltr verify                    # Verify default profile
pltr verify --profile staging  # Verify specific profile
```

---

## 📊 Dataset Commands

Dataset operations using the foundry-platform-sdk. **Note**: SDK requires knowing dataset RIDs in advance.

### `pltr dataset get [OPTIONS] DATASET_RID`
Get detailed information about a specific dataset.

**Arguments:**
- `DATASET_RID` (required): Dataset Resource Identifier

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Examples:**
```bash
# Get dataset info
pltr dataset get ri.foundry.main.dataset.abc123

# Export as JSON
pltr dataset get ri.foundry.main.dataset.abc123 --format json --output dataset-info.json
```

### `pltr dataset create [OPTIONS] NAME`
Create a new dataset.

**Arguments:**
- `NAME` (required): Dataset name

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--parent-folder` TEXT: Parent folder RID
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]

**Examples:**
```bash
# Create dataset
pltr dataset create "My New Dataset"

# Create in specific folder
pltr dataset create "Analysis Results" --parent-folder ri.foundry.main.folder.xyz789
```

---

## 🎯 Ontology Commands

Comprehensive ontology operations for interacting with Foundry ontologies.

### `pltr ontology list [OPTIONS]`
List all available ontologies.

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path
- `--page-size` INTEGER: Number of results per page

**Example:**
```bash
pltr ontology list --format table
```

### `pltr ontology get [OPTIONS] ONTOLOGY_RID`
Get details of a specific ontology.

**Arguments:**
- `ONTOLOGY_RID` (required): Ontology Resource Identifier

**Example:**
```bash
pltr ontology get ri.ontology.main.ontology.abc123
```

### Object Type Operations

#### `pltr ontology object-type-list [OPTIONS] ONTOLOGY_RID`
List object types in an ontology.

**Example:**
```bash
pltr ontology object-type-list ri.ontology.main.ontology.abc123
```

#### `pltr ontology object-type-get [OPTIONS] ONTOLOGY_RID OBJECT_TYPE`
Get details of a specific object type.

**Arguments:**
- `ONTOLOGY_RID` (required): Ontology Resource Identifier
- `OBJECT_TYPE` (required): Object type API name

**Example:**
```bash
pltr ontology object-type-get ri.ontology.main.ontology.abc123 Employee
```

### Object Operations

#### `pltr ontology object-list [OPTIONS] ONTOLOGY_RID OBJECT_TYPE`
List objects of a specific type.

**Options:**
- `--page-size` INTEGER: Number of results per page
- `--properties` TEXT: Comma-separated list of properties to include

**Example:**
```bash
pltr ontology object-list ri.ontology.main.ontology.abc123 Employee --properties "name,department,email"
```

#### `pltr ontology object-get [OPTIONS] ONTOLOGY_RID OBJECT_TYPE PRIMARY_KEY`
Get a specific object by primary key.

**Arguments:**
- `PRIMARY_KEY` (required): Object primary key

**Example:**
```bash
pltr ontology object-get ri.ontology.main.ontology.abc123 Employee "john.doe"
```

#### `pltr ontology object-aggregate [OPTIONS] ONTOLOGY_RID OBJECT_TYPE AGGREGATIONS`
Aggregate objects with specified functions.

**Arguments:**
- `AGGREGATIONS` (required): JSON string of aggregation specs

**Options:**
- `--group-by` TEXT: Comma-separated list of fields to group by
- `--filter` TEXT: JSON string of filter criteria

**Example:**
```bash
pltr ontology object-aggregate ri.ontology.main.ontology.abc123 Employee '{"count": "count"}' --group-by department
```

#### `pltr ontology object-linked [OPTIONS] ONTOLOGY_RID OBJECT_TYPE PRIMARY_KEY LINK_TYPE`
List objects linked to a specific object.

**Arguments:**
- `LINK_TYPE` (required): Link type API name

**Example:**
```bash
pltr ontology object-linked ri.ontology.main.ontology.abc123 Employee "john.doe" worksIn
```

### Action Operations

#### `pltr ontology action-apply [OPTIONS] ONTOLOGY_RID ACTION_TYPE PARAMETERS`
Apply an action with given parameters.

**Arguments:**
- `ACTION_TYPE` (required): Action type API name
- `PARAMETERS` (required): JSON string of action parameters

**Example:**
```bash
pltr ontology action-apply ri.ontology.main.ontology.abc123 promoteEmployee '{"employeeId": "john.doe", "newLevel": "senior"}'
```

#### `pltr ontology action-validate [OPTIONS] ONTOLOGY_RID ACTION_TYPE PARAMETERS`
Validate action parameters without executing.

**Example:**
```bash
pltr ontology action-validate ri.ontology.main.ontology.abc123 promoteEmployee '{"employeeId": "john.doe", "newLevel": "senior"}'
```

### Query Operations

#### `pltr ontology query-execute [OPTIONS] ONTOLOGY_RID QUERY_NAME`
Execute a predefined query.

**Arguments:**
- `QUERY_NAME` (required): Query API name

**Options:**
- `--parameters` TEXT: JSON string of query parameters

**Example:**
```bash
pltr ontology query-execute ri.ontology.main.ontology.abc123 getEmployeesByDepartment --parameters '{"department": "Engineering"}'
```

---

## 🔍 SQL Commands

Execute SQL queries against Foundry datasets with comprehensive query lifecycle management.

### `pltr sql execute [OPTIONS] QUERY`
Execute a SQL query and display results.

**Arguments:**
- `QUERY` (required): SQL query to execute

**Options:**
- `--timeout` INTEGER: Query timeout in seconds [default: 300]
- `--fallback-branches` TEXT: Comma-separated list of fallback branch IDs

**Examples:**
```bash
# Simple query
pltr sql execute "SELECT COUNT(*) FROM my_dataset"

# Complex query with timeout
pltr sql execute "SELECT * FROM large_dataset WHERE category = 'important'" --timeout 600

# Export results
pltr sql execute "SELECT * FROM dataset" --format csv --output results.csv
```

### `pltr sql submit [OPTIONS] QUERY`
Submit a SQL query without waiting for completion.

**Example:**
```bash
pltr sql submit "SELECT * FROM huge_dataset"
# Returns: Query submitted with ID: abc-123-def
```

### `pltr sql status [OPTIONS] QUERY_ID`
Get the status of a submitted query.

**Example:**
```bash
pltr sql status abc-123-def
```

### `pltr sql results [OPTIONS] QUERY_ID`
Get the results of a completed query.

**Example:**
```bash
pltr sql results abc-123-def --format json --output results.json
```

### `pltr sql cancel [OPTIONS] QUERY_ID`
Cancel a running query.

**Example:**
```bash
pltr sql cancel abc-123-def
```

### `pltr sql export [OPTIONS] QUERY OUTPUT_FILE`
Execute a SQL query and export results to a file.

**Arguments:**
- `OUTPUT_FILE` (required): Output file path

**Example:**
```bash
pltr sql export "SELECT * FROM dataset WHERE date > '2025-01-01'" analysis_results.csv
```

### `pltr sql wait [OPTIONS] QUERY_ID`
Wait for a query to complete and optionally display results.

**Options:**
- `--timeout` INTEGER: Maximum wait time in seconds [default: 300]

**Example:**
```bash
pltr sql wait abc-123-def --format table
```

---

## 👥 Admin Commands

Administrative operations for user, group, role, and organization management. **Note**: Requires admin permissions.

### User Management

#### `pltr admin user list [OPTIONS]`
List all users in the organization.

**Options:**
- `--page-size` INTEGER: Number of users per page
- `--page-token` TEXT: Pagination token from previous response

**Example:**
```bash
pltr admin user list --page-size 50
```

#### `pltr admin user get [OPTIONS] USER_ID`
Get information about a specific user.

**Example:**
```bash
pltr admin user get john.doe@company.com
```

#### `pltr admin user current [OPTIONS]`
Get information about the current authenticated user.

**Example:**
```bash
pltr admin user current --format json
```

#### `pltr admin user search [OPTIONS] QUERY`
Search for users by query string.

**Example:**
```bash
pltr admin user search "john" --page-size 20
```

#### `pltr admin user markings [OPTIONS] USER_ID`
Get markings/permissions for a specific user.

**Example:**
```bash
pltr admin user markings john.doe@company.com
```

#### `pltr admin user revoke-tokens [OPTIONS] USER_ID`
Revoke all tokens for a specific user.

**Options:**
- `--confirm`: Skip confirmation prompt

**Example:**
```bash
pltr admin user revoke-tokens john.doe@company.com --confirm
```

### Group Management

#### `pltr admin group list [OPTIONS]`
List all groups in the organization.

**Example:**
```bash
pltr admin group list
```

#### `pltr admin group get [OPTIONS] GROUP_ID`
Get information about a specific group.

**Example:**
```bash
pltr admin group get engineering-team
```

#### `pltr admin group search [OPTIONS] QUERY`
Search for groups by query string.

**Example:**
```bash
pltr admin group search "engineering"
```

#### `pltr admin group create [OPTIONS] NAME`
Create a new group.

**Options:**
- `--description` TEXT: Group description
- `--org-rid` TEXT: Organization RID

**Example:**
```bash
pltr admin group create "Data Science Team" --description "Team for ML and analytics"
```

#### `pltr admin group delete [OPTIONS] GROUP_ID`
Delete a specific group.

**Options:**
- `--confirm`: Skip confirmation prompt

**Example:**
```bash
pltr admin group delete old-team --confirm
```

### Role Management

#### `pltr admin role get [OPTIONS] ROLE_ID`
Get information about a specific role.

**Example:**
```bash
pltr admin role get admin-role
```

### Organization Management

#### `pltr admin org get [OPTIONS] ORGANIZATION_ID`
Get information about a specific organization.

**Example:**
```bash
pltr admin org get my-organization
```

---

## 💻 Interactive Shell

### `pltr shell [OPTIONS]`
Start an interactive shell session with enhanced features.

**Options:**
- `--profile` TEXT: Auth profile to use for the session

**Features:**
- Tab completion for all commands
- Persistent command history across sessions
- Current profile displayed in prompt
- All pltr commands available without the 'pltr' prefix
- Multi-line editing support
- History search with Ctrl+R

**Example:**
```bash
pltr shell --profile production

# In shell mode:
pltr (production)> admin user current
pltr (production)> sql execute "SELECT COUNT(*) FROM my_table"
pltr (production)> exit
```

---

## ⚡ Shell Completion

### `pltr completion install [OPTIONS]`
Install shell completions for enhanced command-line experience.

**Options:**
- `--shell`, `-s` TEXT: Shell type (bash, zsh, fish). Auto-detected if not specified
- `--path`, `-p` PATH: Custom path to install completion file

**Examples:**
```bash
# Auto-detect shell and install
pltr completion install

# Install for specific shell
pltr completion install --shell zsh

# Install to custom path
pltr completion install --shell bash --path ~/.bash_completions/_pltr
```

### `pltr completion show [OPTIONS]`
Show the completion script for manual installation.

**Example:**
```bash
pltr completion show --shell bash
```

### `pltr completion uninstall [OPTIONS]`
Remove shell completions.

**Example:**
```bash
pltr completion uninstall --shell zsh
```

---

## 🔍 Quick Reference

### Most Common Commands
```bash
# Setup
pltr configure configure                    # Configure authentication
pltr verify                                # Test connection

# Data Analysis
pltr sql execute "SELECT * FROM table"     # Run SQL query
pltr ontology list                         # List ontologies
pltr dataset get <rid>                     # Get dataset info

# Admin
pltr admin user current                    # Current user info
pltr admin user list                       # List users

# Interactive
pltr shell                                 # Start interactive mode
pltr completion install                    # Enable tab completion
```

### Output and Format Options
```bash
--format table      # Rich table (default)
--format json       # JSON output
--format csv        # CSV format
--output file.ext   # Save to file
--profile name      # Use specific profile
```

### Help and Documentation
```bash
pltr --help                    # Main help
pltr <command> --help          # Command help
pltr <command> <sub> --help    # Subcommand help
```

---

**💡 Tip**: Use `pltr shell` for interactive exploration and `pltr completion install` for the best command-line experience with tab completion and history.
