# Authentication Setup Guide

pltr-cli supports multiple authentication methods for connecting to Palantir Foundry instances. This guide covers setup, configuration, and best practices.

## 🔐 Authentication Methods

pltr-cli supports two authentication methods:

1. **Token Authentication** - Simple API token-based auth (recommended for most users)
2. **OAuth2 Authentication** - Client credentials flow for service users and automation

You can provide either one in two ways:

- **Profiles**, created with `pltr configure configure`. The host is stored in
  `~/.config/pltr/profiles.json`; the token or client secret is stored in the
  system keyring.
- **Environment variables** (`FOUNDRY_HOST` plus `FOUNDRY_TOKEN`, or
  `FOUNDRY_CLIENT_ID` and `FOUNDRY_CLIENT_SECRET`). Nothing to set up and no
  keyring needed, which suits CI, containers and AI agents. See
  [Headless use](#-headless-use-ci-containers-and-ai-agents).

## 🧭 How pltr Chooses Credentials

Every command authenticates the same way, including `pltr verify` and the few
commands that call Foundry endpoints directly. pltr uses the **first** of these
that applies:

1. `--profile NAME` on the command line
2. the `PLTR_PROFILE` environment variable (a profile name)
3. the default profile (the first profile you configure, or
   `pltr configure set-default NAME`)
4. environment variables, only when no profile is selected by 1–3:
   - token: `FOUNDRY_HOST` and `FOUNDRY_TOKEN`
   - OAuth2: `FOUNDRY_HOST`, `FOUNDRY_CLIENT_ID` and `FOUNDRY_CLIENT_SECRET`
     (used when `FOUNDRY_TOKEN` isn't set)

Rules worth knowing:

- An exported `FOUNDRY_*` variable never overrides a stored profile, and never
  fills in a value missing from one.
- `PLTR_PROFILE` naming a profile that doesn't exist is an error. pltr does not
  fall back to the default profile, so a typo can't send a command to the wrong
  stack.
- Hosts work with or without `https://` and a trailing slash, in profiles and
  environment variables alike. pltr always connects over HTTPS.
- `FOUNDRY_HOSTNAME` (the name the Foundry SDK uses) is accepted when
  `FOUNDRY_HOST` isn't set.

`pltr verify` reports which source it used:

```bash
$ pltr verify --format json
{
  "authSource": {
    "kind": "profile",
    "profile": "production",
    "selectedBy": "default",
    "authType": "token",
    "host": "foundry.company.com"
  },
  "user": {
    "id": "...",
    "username": "jane.doe@company.com",
    ...
  }
}
```

`authSource.kind` is `profile` or `environment`. For a profile, `selectedBy` is
`--profile`, `PLTR_PROFILE` or `default`. For environment variables,
`variables` lists the ones used. `user` is the Foundry user object, with the
API's field names.

## 📋 Prerequisites

Before setting up authentication, you'll need:

- Access to a Palantir Foundry instance
- Appropriate permissions for the operations you want to perform
- Network access to your Foundry instance (VPN may be required)

## 🚀 Quick Setup (Token Authentication)

### Step 1: Get Your API Token

1. Log in to your Foundry instance via web browser
2. Navigate to your user settings or profile
3. Find the "API Tokens" or "Personal Access Tokens" section
4. Generate a new token with appropriate permissions
5. **Copy the token immediately** - you won't be able to see it again

### Step 2: Configure pltr-cli

Run the interactive configuration:

```bash
pltr configure configure
```

You'll be prompted for:
- **Authentication type**: Choose `token`
- **Foundry hostname**: Enter your Foundry domain (e.g., `foundry.company.com`)
- **API token**: Paste your token

The profile is called `default` unless you pass `--profile NAME`. The first
profile you configure becomes the default profile.

### Step 3: Verify Setup

Test your configuration:

```bash
pltr verify
```

`verify` fetches your user from Foundry (`admin.User.get_current`) through the
same client every other command uses, prints your user details, and ends with
`✓ Authentication successful` on stderr. It exits with a non-zero code when
authentication fails (see [Troubleshooting](#-troubleshooting)).

## 🔧 Advanced Setup

### Multiple Profiles

You can configure multiple profiles for different Foundry instances or environments:

```bash
# Production environment
pltr configure configure --profile production
# Follow prompts for production settings

# Development environment
pltr configure configure --profile development
# Follow prompts for development settings

# Staging environment
pltr configure configure --profile staging
# Follow prompts for staging settings
```

### Using Specific Profiles

```bash
# List all configured profiles
pltr configure list-profiles

# Set default profile
pltr configure set-default production

# Use specific profile for a command
pltr verify --profile development
pltr sql execute "SELECT 1" --profile staging

# Use a profile for every command in this shell
export PLTR_PROFILE=staging
```

### Command-Line Configuration

For automation or scripting, you can configure profiles non-interactively:

```bash
# Token authentication
pltr configure configure \
  --profile production \
  --auth-type token \
  --host foundry.company.com \
  --token "your-api-token-here"

# OAuth2 authentication
pltr configure configure \
  --profile oauth-prod \
  --auth-type oauth \
  --host foundry.company.com \
  --client-id "your-client-id" \
  --client-secret "your-client-secret"
```

Without a terminal, `pltr configure configure` never prompts: a missing value
is a usage error (exit code 2) that names the option to pass, and replacing an
existing profile needs `--yes`. `--auth-type` is `token` or `oauth`, and is
inferred from `--token` or the client credentials when you leave it out.

Profiles need a working system keyring. In CI and other headless environments,
use environment variables instead of `pltr configure`.

## 🔑 OAuth2 Authentication

### When to Use OAuth2

Use OAuth2 authentication when:
- Your organization requires client credentials flow
- You're building automated systems or services
- Token authentication is not available or suitable
- You need more granular permission control

### Prerequisites for OAuth2

You'll need:
- OAuth2 client ID and secret from your Foundry administrator
- Appropriate OAuth2 scopes configured for your client
- Understanding of your organization's OAuth2 setup

pltr requests a token with all the scopes granted to the client. `pltr verify`
reads the current user, which needs the `api:admin-read` scope; without it,
verify reports "Permission denied (HTTP 403)" even though the credentials work.

### Setup Process

1. **Get OAuth2 Credentials**
   - Contact your Foundry administrator
   - Request OAuth2 client credentials
   - Ensure proper scopes are assigned

2. **Configure pltr-cli**
   ```bash
   pltr configure configure --profile oauth-profile --auth-type oauth
   ```

   Provide:
   - Foundry hostname
   - OAuth2 client ID
   - OAuth2 client secret

3. **Test Authentication**
   ```bash
   pltr verify --profile oauth-profile
   ```

pltr requests the access token itself and refreshes it as needed, for SDK
commands and direct-HTTP commands alike.

## 🤖 Headless Use: CI, Containers and AI Agents

Environment variables are enough to run every command. pltr then never touches
the system keyring and doesn't need (or create) a configuration directory, so it
works with a read-only or missing home directory.

### Token Authentication

```bash
export FOUNDRY_HOST="foundry.company.com"
export FOUNDRY_TOKEN="your-api-token"

# Now pltr commands will use these credentials
pltr verify
pltr sql execute "SELECT 1"
```

### OAuth2 Authentication

```bash
export FOUNDRY_HOST="foundry.company.com"
export FOUNDRY_CLIENT_ID="your-client-id"
export FOUNDRY_CLIENT_SECRET="your-client-secret"

pltr verify
```

If both `FOUNDRY_TOKEN` and the client credentials are set, the token is used.
If only some of the variables are set (for example `FOUNDRY_TOKEN` without
`FOUNDRY_HOST`), pltr says which one is missing.

### Machines That Also Have Profiles

Environment variables are only used when no profile is selected. If the machine
has a default profile (from an earlier `pltr configure`), that profile wins over
`FOUNDRY_*` variables. `pltr verify` shows which one was used, and its errors
name the file that sets the default profile.

### Agents

For an AI agent, set the variables in the agent's environment and have it run
`pltr verify --format json` first: stdout is a single JSON document, and on
failure stderr carries one JSON error object and the exit code tells the
failure apart (3 authentication, 4 permission denied, 7 network or API error).

## 🔒 Security Best Practices

### Token Security

- **Never commit tokens to version control**
- **Use your CI system's secret store** for `FOUNDRY_TOKEN` and `FOUNDRY_CLIENT_SECRET`
- **Rotate tokens regularly**
- **Use minimal permissions**
- **Store tokens securely** (profiles keep them in the system keyring)

### Profile Management

```bash
# Remove old or compromised profiles
pltr configure delete old-profile

# Use dedicated profiles for different purposes
pltr configure configure --profile readonly-prod    # Read-only operations
pltr configure configure --profile admin-prod       # Admin operations
pltr configure configure --profile development      # Development work
```

### Network Security

- **Use HTTPS** (pltr-cli always connects over HTTPS)
- **Verify SSL certificates** (enabled by default)
- **Use VPN** when required by your organization
- **Monitor network traffic** for suspicious activity

## 🛠️ Profile Management

### Listing Profiles

```bash
pltr configure list-profiles
```

It prints a table of profile names with a `Default` column (`true` for the
default profile); `--format json` prints
`{"data": [{"name": "production", "default": true}, ...]}`.

### Setting Default Profile

```bash
pltr configure set-default development
```

### Deleting Profiles

```bash
# Interactive deletion (with confirmation)
pltr configure delete old-profile

# Skip the confirmation (required when stdin is not a terminal)
pltr configure delete old-profile --yes
```

### Profile Storage

Profiles are stored securely:
- **Credentials**: System keyring (encrypted)
- **Configuration**: `~/.config/pltr/profiles.json` (or `$XDG_CONFIG_HOME/pltr/profiles.json`)
- **No plaintext secrets**: Tokens and secrets are never stored in plain text

## 🔧 Troubleshooting

`pltr verify` exits with `0` on success, `3` when authentication fails (no
usable credentials, rejected token or client credentials, unusable keyring),
`4` when the credentials work but may not read the current user, and `7` for
network and other API errors.

### Common Authentication Issues

#### "Authentication failed (HTTP 401)" Error

**Possible causes:**
- Expired or invalid token
- Wrong hostname
- Credentials from a different source than you expected

**Solutions:**
```bash
# See which credentials were used
pltr verify --format json

# Verify token is still valid
pltr verify --profile your-profile

# Reconfigure with new token
pltr configure configure --profile your-profile
```

#### "No profile specified and no default profile configured" Error

Nothing is configured: no `--profile`, no `PLTR_PROFILE`, no default profile and
no `FOUNDRY_*` variables. Run `pltr configure configure`, or export
`FOUNDRY_HOST` and `FOUNDRY_TOKEN`.

#### "Profile not found" Error

**Solutions:**
```bash
# List existing profiles
pltr configure list-profiles

# Check PLTR_PROFILE: it must name an existing profile
echo "$PLTR_PROFILE"

# Create the missing profile
pltr configure configure --profile missing-profile
```

#### "The system keyring could not read the credentials" Error

A stored profile was needed, but the system keyring is missing (common in
containers and CI), failed, or didn't answer in time (for example the macOS
Keychain over SSH, where it can't show its unlock prompt).

**Solutions:**
- Use environment variables instead (`FOUNDRY_HOST` with `FOUNDRY_TOKEN`, or
  with `FOUNDRY_CLIENT_ID` and `FOUNDRY_CLIENT_SECRET`). They are only used when
  no profile is selected, so drop `--profile`, unset `PLTR_PROFILE`, and make
  sure no default profile is set (the error names the file that sets it).
- If the keyring just needs longer (for example while you type a keychain
  password), raise the time limit: `export PLTR_KEYRING_TIMEOUT=120`. The
  default is 30 seconds; `0` waits indefinitely.
- On Linux without a desktop keyring, install a keyring backend (see the
  [keyring documentation](https://pypi.org/project/keyring/)).

#### "Network timeout" or "Could not reach" Error

**Solutions:**
- Check VPN connection
- Verify Foundry hostname
- Test network connectivity to Foundry instance
- Check firewall settings

### OAuth2 Specific Issues

#### "The OAuth token request ... failed" Error

**Solutions:**
- Verify client ID and secret with administrator
- Ensure OAuth2 client is properly configured in Foundry
- Check that required scopes are assigned

#### "Permission denied (HTTP 403)" from `pltr verify`

The credentials work, but the client may not read the current user. Ask your
administrator to grant the `api:admin-read` scope, or check the client with a
command that uses the scopes it has.

### Token Specific Issues

#### "Token expired" Error

**Solutions:**
```bash
# Generate new token in Foundry web interface
# Reconfigure profile with new token
pltr configure configure --profile your-profile --token "new-token"
```

#### "Insufficient permissions" Error

**Solutions:**
- Check token permissions in Foundry
- Generate new token with required permissions
- Contact administrator for access to restricted resources

## 📚 Advanced Configuration

### Custom Configuration Directory

pltr follows the XDG convention: profiles and settings live in
`$XDG_CONFIG_HOME/pltr` when `XDG_CONFIG_HOME` is set, otherwise in
`~/.config/pltr`. The directory is only created when pltr saves something.

```bash
export XDG_CONFIG_HOME="/custom/path"
pltr configure configure   # writes /custom/path/pltr/profiles.json
```

### Environment Variable Reference

| Variable | Purpose |
|---|---|
| `PLTR_PROFILE` | Profile to use when `--profile` isn't given |
| `FOUNDRY_HOST` | Foundry host for environment-variable auth (`FOUNDRY_HOSTNAME` also works) |
| `FOUNDRY_TOKEN` | Token for environment-variable auth |
| `FOUNDRY_CLIENT_ID`, `FOUNDRY_CLIENT_SECRET` | OAuth2 client credentials for environment-variable auth |
| `PLTR_KEYRING_TIMEOUT` | Seconds to wait for the system keyring (default 30; `0` waits indefinitely) |
| `XDG_CONFIG_HOME` | Parent of pltr's configuration directory |

### Debugging Authentication

```bash
# Which credentials were used, and who you are
pltr verify --format json

# Check a specific profile
pltr verify --profile your-profile
```

### Integration with External Tools

#### Docker/Containers

Pass credentials at run time; don't bake tokens into images:

```bash
docker run --rm \
  -e FOUNDRY_HOST=foundry.company.com \
  -e FOUNDRY_TOKEN \
  my-image pltr verify
```

#### CI/CD Examples

**GitHub Actions:**
```yaml
- name: Run pltr commands
  env:
    FOUNDRY_TOKEN: ${{ secrets.FOUNDRY_TOKEN }}
    FOUNDRY_HOST: foundry.company.com
  run: |
    pltr verify
    pltr sql execute "SELECT COUNT(*) FROM important_table"
```

**Jenkins:**
```groovy
withCredentials([string(credentialsId: 'foundry-token', variable: 'FOUNDRY_TOKEN')]) {
    sh '''
        export FOUNDRY_HOST="foundry.company.com"
        pltr verify
        pltr sql execute "SELECT * FROM dataset" --output results.csv
    '''
}
```

## 🔍 Next Steps

Once authentication is working:

1. **Explore Commands**: Check the [Command Reference](commands.md)
2. **Learn Workflows**: See [Common Workflows](workflows.md)
3. **Interactive Mode**: Try `pltr shell` for exploration
4. **Shell Completion**: Run `pltr completion install` for better experience

## 🆘 Getting Help

- **Verify setup**: `pltr verify`
- **List profiles**: `pltr configure list-profiles`
- **Command help**: `pltr configure --help`
- **Troubleshooting**: See [Troubleshooting Guide](troubleshooting.md)

---

💡 **Pro Tip**: Use `pltr shell --profile production` to start an interactive session with a specific profile, perfect for exploratory data analysis!
