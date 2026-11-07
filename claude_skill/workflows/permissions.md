# Workflow: permissions, users and groups

Look up users and groups, review who has access to a resource, and grant or
revoke roles and markings. Changing access is sensitive: confirm the
resource, the principal and the role with the user before any grant, revoke
or marking change.

## Find users and groups

Users and groups are identified by UUID; the API doesn't accept usernames or
group names where it expects an ID.

```bash
pltr admin user current --format json            # who pltr is authenticated as
pltr admin user search jane --format json         # matches the start of names
pltr admin user get <user-uuid> --format json
pltr admin group search analysts --format json
pltr admin group get <group-uuid> --format json
pltr api admin group group-member list <group-uuid> --transitive --format json
```

## Review access to a resource

```bash
pltr resource get ri.compass.main.folder.<id> --format json
pltr resource-role list ri.compass.main.folder.<id> --include-inherited --format json
pltr resource list-markings ri.compass.main.folder.<id> --format json
pltr resource access-requirements ri.compass.main.folder.<id> --format json
```

## Grant and revoke roles

Role IDs come from the role set of the resource's space; `resource-role
list` shows the role IDs in use on the resource.

```bash
pltr resource-role grant ri.compass.main.folder.<id> --role <role-id> --principal-id <user-or-group-uuid>
pltr resource-role grant ri.compass.main.folder.<id> --role <role-id> --everyone

# Revoking is destructive: it asks first, or needs --yes without a terminal
pltr resource-role revoke ri.compass.main.folder.<id> --role <role-id> --principal-id <user-or-group-uuid> --yes
```

## Markings

```bash
pltr resource add-markings ri.compass.main.folder.<id> --marking <marking-id>
pltr resource remove-markings ri.compass.main.folder.<id> --marking <marking-id> --yes
pltr api admin marking list --format json
```

## Organizations of a project

```bash
pltr project list-orgs ri.compass.main.folder.<id> --format json
pltr project add-orgs ri.compass.main.folder.<id> --org <organization-rid>
pltr project remove-orgs ri.compass.main.folder.<id> --org <organization-rid> --yes
```
