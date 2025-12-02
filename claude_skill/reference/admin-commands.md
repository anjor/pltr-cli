# Admin Commands

User, group, role, and organization management. **Requires admin permissions**.

## User Commands

### List Users

```bash
pltr admin user list [--page-size N] [--page-token TEXT] [--format FORMAT]

# Example
pltr admin user list --page-size 50 --format csv --output users.csv
```

### Get User Info

```bash
pltr admin user get USER_ID [--format FORMAT]

# Example
pltr admin user get john.doe@company.com
```

### Current User

```bash
pltr admin user current [--format FORMAT]

# Example
pltr admin user current --format json
```

### Search Users

```bash
pltr admin user search QUERY [--page-size N] [--format FORMAT]

# Example
pltr admin user search "john" --page-size 20
```

### Get User Markings/Permissions

```bash
pltr admin user markings USER_ID [--format FORMAT]

# Example
pltr admin user markings john.doe@company.com
```

### Revoke User Tokens

```bash
pltr admin user revoke-tokens USER_ID [--confirm]

# Example
pltr admin user revoke-tokens john.doe@company.com --confirm
```

## Group Commands

### List Groups

```bash
pltr admin group list [--format FORMAT]

# Example
pltr admin group list
```

### Get Group Info

```bash
pltr admin group get GROUP_ID [--format FORMAT]

# Example
pltr admin group get engineering-team
```

### Search Groups

```bash
pltr admin group search QUERY [--format FORMAT]

# Example
pltr admin group search "engineering"
```

### Create Group

```bash
pltr admin group create NAME [--description TEXT] [--org-rid TEXT]

# Example
pltr admin group create "Data Science Team" --description "Team for ML and analytics"
```

### Delete Group

```bash
pltr admin group delete GROUP_ID [--confirm]

# Example
pltr admin group delete old-team --confirm
```

## Role Commands

### Get Role Info

```bash
pltr admin role get ROLE_ID [--format FORMAT]

# Example
pltr admin role get admin-role
```

## Organization Commands

### Get Organization Info

```bash
pltr admin org get ORGANIZATION_ID [--format FORMAT]

# Example
pltr admin org get my-organization
```

## Common Patterns

### Audit users
```bash
# Export all users
pltr admin user list --format csv --output all_users.csv

# Search for admin users
pltr admin user search "admin" --format csv --output admins.csv
```

### User management workflow
```bash
# Get current user info
pltr admin user current

# Check user permissions
pltr admin user markings john.doe@company.com

# Search for specific users
pltr admin user search "data scientist"
```

### Group management
```bash
# List all groups
pltr admin group list --format json --output groups.json

# Create new team group
pltr admin group create "Analytics Team" --description "Business analytics team"

# Get group details
pltr admin group get analytics-team
```

### Security audit script
```bash
#!/bin/bash
# Export users and groups for audit
DATE=$(date +%Y%m%d)

pltr admin user list --format json --output "audit_users_${DATE}.json"
pltr admin group list --format json --output "audit_groups_${DATE}.json"
pltr admin user search "admin" --format csv --output "potential_admins_${DATE}.csv"

echo "Audit files generated for $DATE"
```
