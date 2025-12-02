# Filesystem Commands

Manage folders, spaces, projects, resources, and permissions.

## RID Formats
- Folders: `ri.compass.main.folder.{uuid}` (root: `ri.compass.main.folder.0`)
- Spaces: `ri.compass.main.space.{uuid}`
- Projects: `ri.compass.main.project.{uuid}`
- Resources: Various patterns depending on type

## Folder Commands

### Create Folder

```bash
pltr folder create NAME [--parent-folder FOLDER_RID] [--format FORMAT]

# Default parent is root: ri.compass.main.folder.0

# Example
pltr folder create "My Project"
pltr folder create "Sub Folder" --parent-folder ri.compass.main.folder.xyz123
```

### Get Folder Info

```bash
pltr folder get FOLDER_RID [--format FORMAT] [--output FILE]

# Example
pltr folder get ri.compass.main.folder.abc123
```

### List Folder Contents

```bash
pltr folder list FOLDER_RID [--page-size N] [--format FORMAT]

# Example - List root folder
pltr folder list ri.compass.main.folder.0

# List with pagination
pltr folder list ri.compass.main.folder.abc123 --page-size 50
```

### Batch Get Folders

```bash
pltr folder batch-get FOLDER_RIDS...

# Max 1000 RIDs

# Example
pltr folder batch-get ri.compass.main.folder.abc123 ri.compass.main.folder.def456
```

## Space Commands

### Create Space

```bash
pltr space create DISPLAY_NAME ORGANIZATION_RID [OPTIONS]

# Options:
#   --description TEXT       Space description
#   --default-roles TEXT     Comma-separated default roles
#   --role-grants TEXT       Role grants config (JSON)

# Example
pltr space create "Data Science Team" ri.compass.main.organization.abc123 \
  --description "Space for analytics work" \
  --default-roles "viewer,editor"
```

### Get Space

```bash
pltr space get SPACE_RID [--format FORMAT]
```

### List Spaces

```bash
pltr space list [--organization-rid RID] [--page-size N] [--format FORMAT]
```

### Update Space

```bash
pltr space update SPACE_RID [--display-name TEXT] [--description TEXT]
```

### Delete Space

```bash
pltr space delete SPACE_RID [--yes]
```

### Space Member Management

```bash
# List members
pltr space members SPACE_RID

# Add member
pltr space add-member SPACE_RID PRINCIPAL_ID PRINCIPAL_TYPE ROLE_NAME
# PRINCIPAL_TYPE: "User" or "Group"

# Remove member
pltr space remove-member SPACE_RID PRINCIPAL_ID PRINCIPAL_TYPE

# Examples
pltr space add-member ri.compass.main.space.abc123 john.doe User editor
pltr space add-member ri.compass.main.space.abc123 data-team Group viewer
pltr space remove-member ri.compass.main.space.abc123 john.doe User
```

## Project Commands

### Create Project

```bash
pltr project create DISPLAY_NAME SPACE_RID [OPTIONS]

# Options:
#   --description TEXT         Project description
#   --organization-rids TEXT   Comma-separated org RIDs
#   --default-roles TEXT       Comma-separated default roles

# Example
pltr project create "ML Pipeline" ri.compass.main.space.abc123 \
  --description "Machine learning pipeline project"
```

### Other Project Commands

```bash
pltr project get PROJECT_RID
pltr project list [--space-rid RID]
pltr project update PROJECT_RID [--display-name TEXT] [--description TEXT]
pltr project delete PROJECT_RID [--yes]
pltr project batch-get PROJECT_RIDS...
```

## Resource Commands

### Get Resource

```bash
pltr resource get RESOURCE_RID [--format FORMAT]
```

### List Resources

```bash
pltr resource list [--folder-rid RID] [--resource-type TYPE] [--page-size N]

# Example
pltr resource list --folder-rid ri.compass.main.folder.abc123 --resource-type dataset
```

### Search Resources

```bash
pltr resource search QUERY [--resource-type TYPE] [--folder-rid RID]

# Example
pltr resource search "sales data" --resource-type dataset
```

### Batch Get Resources

```bash
pltr resource batch-get RESOURCE_RIDS...
```

### Resource Metadata

```bash
# Get metadata
pltr resource metadata get RESOURCE_RID

# Set metadata (JSON)
pltr resource metadata set RESOURCE_RID '{"owner": "data-team", "env": "production"}'

# Delete metadata keys
pltr resource metadata delete RESOURCE_RID "key1,key2"
```

### Move Resource

```bash
pltr resource move RESOURCE_RID TARGET_FOLDER_RID

# Example
pltr resource move ri.foundry.main.dataset.abc123 ri.compass.main.folder.new456
```

## Resource Role Commands

### Grant Role

```bash
pltr resource-role grant RESOURCE_RID PRINCIPAL_ID PRINCIPAL_TYPE ROLE_NAME

# PRINCIPAL_TYPE: "User" or "Group"

# Examples
pltr resource-role grant ri.foundry.main.dataset.abc123 john.doe User viewer
pltr resource-role grant ri.foundry.main.dataset.abc123 data-team Group editor
```

### Revoke Role

```bash
pltr resource-role revoke RESOURCE_RID PRINCIPAL_ID PRINCIPAL_TYPE ROLE_NAME
```

### List Roles

```bash
pltr resource-role list RESOURCE_RID [--principal-type TYPE]

# Example
pltr resource-role list ri.foundry.main.dataset.abc123 --principal-type User
```

### Get Principal Roles

```bash
pltr resource-role get-principal-roles PRINCIPAL_ID PRINCIPAL_TYPE [--resource-rid RID]

# Example
pltr resource-role get-principal-roles john.doe User
```

### Bulk Grant/Revoke

```bash
# Bulk grant
pltr resource-role bulk-grant RESOURCE_RID '[
  {"principal_id": "john.doe", "principal_type": "User", "role_name": "viewer"},
  {"principal_id": "data-team", "principal_type": "Group", "role_name": "editor"}
]'

# Bulk revoke
pltr resource-role bulk-revoke RESOURCE_RID '[
  {"principal_id": "john.doe", "principal_type": "User", "role_name": "viewer"}
]'
```

### Available Roles

```bash
pltr resource-role available-roles RESOURCE_RID
```

## Common Patterns

### Create workspace structure
```bash
# Create folders
ROOT=$(pltr folder create "Analytics Work" --format json | jq -r '.rid')
pltr folder create "Raw Data" --parent-folder $ROOT
pltr folder create "Processed" --parent-folder $ROOT
pltr folder create "Reports" --parent-folder $ROOT
```

### Set up team permissions
```bash
DATASET="ri.foundry.main.dataset.customer-data"

# Grant team access
pltr resource-role grant $DATASET data-team Group owner
pltr resource-role grant $DATASET analytics-team Group editor

# Grant individual access
pltr resource-role grant $DATASET john.analyst User viewer
```

### Organize resources
```bash
# Search and move datasets
pltr resource search "sales" --resource-type dataset --format json --output sales.json

# Move to organized folder
for rid in $(cat sales.json | jq -r '.[].rid'); do
  pltr resource move "$rid" ri.compass.main.folder.sales-data
done
```
