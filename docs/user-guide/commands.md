# Command Reference

Complete reference for all pltr-cli commands. The CLI provides 80+ commands across 10 major command groups for comprehensive Foundry API access.

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

Comprehensive dataset operations using the foundry-platform-sdk with support for branches, files, transactions, and views. **Note**: SDK requires knowing dataset RIDs in advance.

### Basic Dataset Operations

#### `pltr dataset get [OPTIONS] DATASET_RID`
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

#### `pltr dataset create [OPTIONS] NAME`
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

### Branch Operations

#### `pltr dataset branches list [OPTIONS] DATASET_RID`
List all branches for a dataset.

**Arguments:**
- `DATASET_RID` (required): Dataset Resource Identifier

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Examples:**
```bash
# List dataset branches
pltr dataset branches list ri.foundry.main.dataset.abc123

# Export branch list as CSV
pltr dataset branches list ri.foundry.main.dataset.abc123 --format csv --output branches.csv
```

#### `pltr dataset branches create [OPTIONS] DATASET_RID BRANCH_NAME`
Create a new branch for a dataset.

**Arguments:**
- `DATASET_RID` (required): Dataset Resource Identifier
- `BRANCH_NAME` (required): Name for the new branch

**Options:**
- `--parent` TEXT: Parent branch to branch from [default: master]
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]

**Examples:**
```bash
# Create branch from master
pltr dataset branches create ri.foundry.main.dataset.abc123 "feature-branch"

# Create branch from specific parent
pltr dataset branches create ri.foundry.main.dataset.abc123 "hotfix" --parent development
```

### File Operations

#### `pltr dataset files list [OPTIONS] DATASET_RID`
List all files in a dataset.

**Arguments:**
- `DATASET_RID` (required): Dataset Resource Identifier

**Options:**
- `--branch` TEXT: Dataset branch [default: master]
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Examples:**
```bash
# List files in master branch
pltr dataset files list ri.foundry.main.dataset.abc123

# List files in specific branch
pltr dataset files list ri.foundry.main.dataset.abc123 --branch development

# Export file list
pltr dataset files list ri.foundry.main.dataset.abc123 --format json --output files.json
```

#### `pltr dataset files get [OPTIONS] DATASET_RID FILE_PATH OUTPUT_PATH`
Download a file from a dataset.

**Arguments:**
- `DATASET_RID` (required): Dataset Resource Identifier
- `FILE_PATH` (required): Path of file within dataset
- `OUTPUT_PATH` (required): Local path to save the downloaded file

**Options:**
- `--branch` TEXT: Dataset branch [default: master]
- `--profile`, `-p` TEXT: Profile name

**Examples:**
```bash
# Download file from master branch
pltr dataset files get ri.foundry.main.dataset.abc123 "/data/results.csv" "./downloaded_results.csv"

# Download from specific branch
pltr dataset files get ri.foundry.main.dataset.abc123 "/analysis/report.pdf" "./report.pdf" --branch feature-branch
```

### Transaction Operations

#### `pltr dataset transactions list [OPTIONS] DATASET_RID`
List transactions for a dataset branch.

**Arguments:**
- `DATASET_RID` (required): Dataset Resource Identifier

**Options:**
- `--branch` TEXT: Dataset branch [default: master]
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Examples:**
```bash
# List transactions for master branch
pltr dataset transactions list ri.foundry.main.dataset.abc123

# List transactions for specific branch
pltr dataset transactions list ri.foundry.main.dataset.abc123 --branch development
```

**Note:** Transaction operations may not be available in all foundry-platform-python SDK versions. If unavailable, a warning message will be displayed.

### View Operations

#### `pltr dataset views list [OPTIONS] DATASET_RID`
List all views for a dataset.

**Arguments:**
- `DATASET_RID` (required): Dataset Resource Identifier

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Examples:**
```bash
# List dataset views
pltr dataset views list ri.foundry.main.dataset.abc123

# Export views as JSON
pltr dataset views list ri.foundry.main.dataset.abc123 --format json --output views.json
```

#### `pltr dataset views create [OPTIONS] DATASET_RID VIEW_NAME`
Create a new view for a dataset.

**Arguments:**
- `DATASET_RID` (required): Dataset Resource Identifier
- `VIEW_NAME` (required): Name for the new view

**Options:**
- `--description` TEXT: Optional description for the view
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]

**Examples:**
```bash
# Create a simple view
pltr dataset views create ri.foundry.main.dataset.abc123 "analysis-view"

# Create view with description
pltr dataset views create ri.foundry.main.dataset.abc123 "monthly-report" --description "Monthly analysis report view"
```

**Note:** View operations may not be available in all foundry-platform-python SDK versions. If unavailable, a warning message will be displayed.

### Dataset RID Format
Dataset Resource Identifiers follow the pattern: `ri.foundry.main.dataset.{uuid}`

### SDK Compatibility Notes
- Branch and file operations are available in most SDK versions
- Transaction and view operations require newer SDK versions and will gracefully degrade with informative messages if unavailable
- All dataset operations work with the RID-based API and require knowing dataset RIDs in advance
- Find dataset RIDs in the Foundry web interface or via other API calls

---

## 📁 Folder Commands

Folder operations for managing the Foundry filesystem structure using the foundry-platform-sdk.

### `pltr folder create [OPTIONS] NAME`
Create a new folder in Foundry.

**Arguments:**
- `NAME` (required): Folder display name

**Options:**
- `--parent-folder`, `-p` TEXT: Parent folder RID [default: ri.compass.main.folder.0 (root)]
- `--profile` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]

**Examples:**
```bash
# Create folder in root
pltr folder create "My Project"

# Create folder in specific parent
pltr folder create "Sub Folder" --parent-folder ri.compass.main.folder.xyz123

# Create with JSON output
pltr folder create "Analysis" --format json
```

### `pltr folder get [OPTIONS] FOLDER_RID`
Get detailed information about a specific folder.

**Arguments:**
- `FOLDER_RID` (required): Folder Resource Identifier

**Options:**
- `--profile` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Examples:**
```bash
# Get folder info
pltr folder get ri.compass.main.folder.abc123

# Export as JSON
pltr folder get ri.compass.main.folder.abc123 --format json --output folder-info.json
```

### `pltr folder list [OPTIONS] FOLDER_RID`
List all child resources of a folder.

**Arguments:**
- `FOLDER_RID` (required): Folder Resource Identifier (use 'ri.compass.main.folder.0' for root)

**Options:**
- `--profile` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path
- `--page-size` INTEGER: Number of items per page

**Examples:**
```bash
# List root folder contents
pltr folder list ri.compass.main.folder.0

# List with pagination
pltr folder list ri.compass.main.folder.abc123 --page-size 50

# Export children list
pltr folder list ri.compass.main.folder.abc123 --format csv --output children.csv
```

### `pltr folder batch-get [OPTIONS] FOLDER_RIDS...`
Get multiple folders in a single request (max 1000).

**Arguments:**
- `FOLDER_RIDS...` (required): Space-separated list of folder Resource Identifiers

**Options:**
- `--profile` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Examples:**
```bash
# Get multiple folders
pltr folder batch-get ri.compass.main.folder.abc123 ri.compass.main.folder.def456

# Export batch results
pltr folder batch-get ri.compass.main.folder.abc123 ri.compass.main.folder.def456 --format json --output folders.json
```

**Root Folder RID**: `ri.compass.main.folder.0` - Use this as the parent folder RID to create folders in the root directory.

---

## 🏗️ Orchestration Commands

Comprehensive orchestration operations for managing builds, jobs, and schedules in Foundry.

### Build Commands

#### `pltr orchestration builds search [OPTIONS]`
Search for builds.

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path
- `--page-size` INTEGER: Number of results per page

**Example:**
```bash
pltr orchestration builds search --format table
```

#### `pltr orchestration builds get [OPTIONS] BUILD_RID`
Get detailed information about a specific build.

**Arguments:**
- `BUILD_RID` (required): Build Resource Identifier

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Example:**
```bash
pltr orchestration builds get ri.orchestration.main.build.abc123
```

#### `pltr orchestration builds create [OPTIONS] TARGET`
Create a new build.

**Arguments:**
- `TARGET` (required): Build target configuration in JSON format

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--branch` TEXT: Branch name for the build
- `--force`: Force build even if no changes
- `--abort-on-failure`: Abort on failure
- `--notifications/--no-notifications`: Enable notifications [default: enabled]
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]

**Example:**
```bash
pltr orchestration builds create '{"dataset_rid": "ri.foundry.main.dataset.abc"}' --branch main --force
```

#### `pltr orchestration builds cancel [OPTIONS] BUILD_RID`
Cancel a build and all its unfinished jobs.

**Arguments:**
- `BUILD_RID` (required): Build Resource Identifier

**Example:**
```bash
pltr orchestration builds cancel ri.orchestration.main.build.abc123
```

#### `pltr orchestration builds jobs [OPTIONS] BUILD_RID`
List all jobs in a build.

**Arguments:**
- `BUILD_RID` (required): Build Resource Identifier

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--page-size` INTEGER: Number of results per page
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Example:**
```bash
pltr orchestration builds jobs ri.orchestration.main.build.abc123
```

### Job Commands

#### `pltr orchestration jobs get [OPTIONS] JOB_RID`
Get detailed information about a specific job.

**Arguments:**
- `JOB_RID` (required): Job Resource Identifier

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Example:**
```bash
pltr orchestration jobs get ri.orchestration.main.job.def456
```

#### `pltr orchestration jobs get-batch [OPTIONS] JOB_RIDS`
Get multiple jobs in batch (max 500).

**Arguments:**
- `JOB_RIDS` (required): Comma-separated list of Job RIDs

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Example:**
```bash
pltr orchestration jobs get-batch "ri.orchestration.main.job.abc,ri.orchestration.main.job.def"
```

### Schedule Commands

#### `pltr orchestration schedules get [OPTIONS] SCHEDULE_RID`
Get detailed information about a specific schedule.

**Arguments:**
- `SCHEDULE_RID` (required): Schedule Resource Identifier

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--preview`: Enable preview mode
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]
- `--output`, `-o` TEXT: Output file path

**Example:**
```bash
pltr orchestration schedules get ri.orchestration.main.schedule.ghi789 --preview
```

#### `pltr orchestration schedules create [OPTIONS] ACTION`
Create a new schedule.

**Arguments:**
- `ACTION` (required): Schedule action configuration in JSON format

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--name` TEXT: Display name for the schedule
- `--description` TEXT: Schedule description
- `--trigger` TEXT: Trigger configuration in JSON format
- `--preview`: Enable preview mode
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]

**Example:**
```bash
pltr orchestration schedules create '{"type": "BUILD", "target": "ri.foundry.main.dataset.abc"}' \
  --name "Daily Build" \
  --description "Automated daily build" \
  --trigger '{"type": "CRON", "expression": "0 2 * * *"}'
```

#### `pltr orchestration schedules delete [OPTIONS] SCHEDULE_RID`
Delete a schedule.

**Arguments:**
- `SCHEDULE_RID` (required): Schedule Resource Identifier

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--yes`, `-y`: Skip confirmation prompt

**Example:**
```bash
pltr orchestration schedules delete ri.orchestration.main.schedule.ghi789 --yes
```

#### `pltr orchestration schedules pause [OPTIONS] SCHEDULE_RID`
Pause a schedule.

**Arguments:**
- `SCHEDULE_RID` (required): Schedule Resource Identifier

**Example:**
```bash
pltr orchestration schedules pause ri.orchestration.main.schedule.ghi789
```

#### `pltr orchestration schedules unpause [OPTIONS] SCHEDULE_RID`
Unpause a schedule.

**Arguments:**
- `SCHEDULE_RID` (required): Schedule Resource Identifier

**Example:**
```bash
pltr orchestration schedules unpause ri.orchestration.main.schedule.ghi789
```

#### `pltr orchestration schedules run [OPTIONS] SCHEDULE_RID`
Execute a schedule immediately.

**Arguments:**
- `SCHEDULE_RID` (required): Schedule Resource Identifier

**Example:**
```bash
pltr orchestration schedules run ri.orchestration.main.schedule.ghi789
```

#### `pltr orchestration schedules replace [OPTIONS] SCHEDULE_RID ACTION`
Replace an existing schedule.

**Arguments:**
- `SCHEDULE_RID` (required): Schedule Resource Identifier
- `ACTION` (required): Schedule action configuration in JSON format

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--name` TEXT: Display name for the schedule
- `--description` TEXT: Schedule description
- `--trigger` TEXT: Trigger configuration in JSON format
- `--preview`: Enable preview mode
- `--format`, `-f` TEXT: Output format (table, json, csv) [default: table]

**Example:**
```bash
pltr orchestration schedules replace ri.orchestration.main.schedule.ghi789 \
  '{"type": "BUILD", "target": "ri.foundry.main.dataset.new"}' \
  --name "Updated Schedule"
```

**Note**: All orchestration operations require Resource Identifiers (RIDs) which can be found in the Foundry web interface. RIDs follow the pattern:
- Builds: `ri.orchestration.main.build.{uuid}`
- Jobs: `ri.orchestration.main.job.{uuid}`
- Schedules: `ri.orchestration.main.schedule.{uuid}`

---

## 🎬 MediaSets Commands

Manage media sets and media content with support for uploading, downloading, and transaction-based operations.

### Media Item Information

#### `pltr media-sets get [OPTIONS] MEDIA_SET_RID MEDIA_ITEM_RID`
Get detailed information about a specific media item.

**Arguments:**
- `MEDIA_SET_RID`: Media Set Resource Identifier (required)
- `MEDIA_ITEM_RID`: Media Item Resource Identifier (required)

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv)
- `--output`, `-o` TEXT: Output file path
- `--preview`: Enable preview mode

**Example:**
```bash
pltr media-sets get ri.mediasets.main.media-set.abc123 ri.mediasets.main.media-item.def456
```

#### `pltr media-sets get-by-path [OPTIONS] MEDIA_SET_RID MEDIA_ITEM_PATH`
Get media item RID by its path within the media set.

**Arguments:**
- `MEDIA_SET_RID`: Media Set Resource Identifier (required)
- `MEDIA_ITEM_PATH`: Path to media item within the media set (required)

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--branch` TEXT: Branch name
- `--format`, `-f` TEXT: Output format (table, json, csv)
- `--output`, `-o` TEXT: Output file path
- `--preview`: Enable preview mode

**Example:**
```bash
pltr media-sets get-by-path ri.mediasets.main.media-set.abc123 "/images/photo.jpg"
```

#### `pltr media-sets reference [OPTIONS] MEDIA_SET_RID MEDIA_ITEM_RID`
Get a reference to a media item (e.g., for embedding).

**Arguments:**
- `MEDIA_SET_RID`: Media Set Resource Identifier (required)
- `MEDIA_ITEM_RID`: Media Item Resource Identifier (required)

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--format`, `-f` TEXT: Output format (table, json, csv)
- `--output`, `-o` TEXT: Output file path
- `--preview`: Enable preview mode

**Example:**
```bash
pltr media-sets reference ri.mediasets.main.media-set.abc123 ri.mediasets.main.media-item.def456
```

### Transaction Management

#### `pltr media-sets create [OPTIONS] MEDIA_SET_RID`
Create a new transaction for uploading to a media set.

**Arguments:**
- `MEDIA_SET_RID`: Media Set Resource Identifier (required)

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--branch` TEXT: Branch name
- `--preview`: Enable preview mode

**Example:**
```bash
pltr media-sets create ri.mediasets.main.media-set.abc123 --branch main
```

#### `pltr media-sets commit [OPTIONS] MEDIA_SET_RID TRANSACTION_ID`
Commit a transaction, making uploaded items available.

**Arguments:**
- `MEDIA_SET_RID`: Media Set Resource Identifier (required)
- `TRANSACTION_ID`: Transaction ID to commit (required)

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--preview`: Enable preview mode
- `--yes`, `-y`: Skip confirmation prompt

**Example:**
```bash
pltr media-sets commit ri.mediasets.main.media-set.abc123 transaction-id-12345 --yes
```

#### `pltr media-sets abort [OPTIONS] MEDIA_SET_RID TRANSACTION_ID`
Abort a transaction, deleting any uploaded items.

**Arguments:**
- `MEDIA_SET_RID`: Media Set Resource Identifier (required)
- `TRANSACTION_ID`: Transaction ID to abort (required)

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--preview`: Enable preview mode
- `--yes`, `-y`: Skip confirmation prompt

**Example:**
```bash
pltr media-sets abort ri.mediasets.main.media-set.abc123 transaction-id-12345 --yes
```

### Upload and Download Operations

#### `pltr media-sets upload [OPTIONS] MEDIA_SET_RID FILE_PATH MEDIA_ITEM_PATH TRANSACTION_ID`
Upload a media file to a media set within a transaction.

**Arguments:**
- `MEDIA_SET_RID`: Media Set Resource Identifier (required)
- `FILE_PATH`: Local path to the file to upload (required)
- `MEDIA_ITEM_PATH`: Path within media set where file should be stored (required)
- `TRANSACTION_ID`: Transaction ID for the upload (required)

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--preview`: Enable preview mode

**Example:**
```bash
pltr media-sets upload ri.mediasets.main.media-set.abc123 \
  /local/path/image.jpg "/media/images/image.jpg" transaction-id-12345
```

#### `pltr media-sets download [OPTIONS] MEDIA_SET_RID MEDIA_ITEM_RID OUTPUT_PATH`
Download a media item from a media set.

**Arguments:**
- `MEDIA_SET_RID`: Media Set Resource Identifier (required)
- `MEDIA_ITEM_RID`: Media Item Resource Identifier (required)
- `OUTPUT_PATH`: Local path where file should be saved (required)

**Options:**
- `--profile`, `-p` TEXT: Profile name
- `--original`: Download original version instead of processed
- `--preview`: Enable preview mode
- `--overwrite`: Overwrite existing file

**Example:**
```bash
# Download processed version
pltr media-sets download ri.mediasets.main.media-set.abc123 \
  ri.mediasets.main.media-item.def456 /local/download/image.jpg

# Download original version
pltr media-sets download ri.mediasets.main.media-set.abc123 \
  ri.mediasets.main.media-item.def456 /local/download/original.jpg --original
```

### MediaSets Workflow

The typical workflow for working with MediaSets involves transactions:

1. **Create a transaction**: `pltr media-sets create <media-set-rid>`
2. **Upload files**: `pltr media-sets upload <media-set-rid> <local-file> <remote-path> <transaction-id>`
3. **Commit or abort**: `pltr media-sets commit <media-set-rid> <transaction-id>`

**Note**: All MediaSets operations require Resource Identifiers (RIDs) which can be found in the Foundry web interface. RIDs follow the pattern:
- Media Sets: `ri.mediasets.main.media-set.{uuid}`
- Media Items: `ri.mediasets.main.media-item.{uuid}`

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
pltr dataset branches list <rid>           # List dataset branches
pltr dataset files list <rid>              # List dataset files

# Folder Management
pltr folder create "My Folder"             # Create folder
pltr folder list ri.compass.main.folder.0  # List root contents
pltr folder get <folder-rid>               # Get folder info

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
