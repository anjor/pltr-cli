# Authentication Setup Guide

pltr-cli supports multiple authentication methods for connecting to Palantir Foundry instances. This guide covers setup, configuration, and best practices.

## 🔐 Authentication Methods

pltr-cli supports two authentication methods:

1. **Token Authentication** - Simple API token-based auth (recommended for most users)
2. **OAuth2 Authentication** - Client credentials flow for advanced scenarios

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
- **Foundry hostname**: Enter your Foundry domain (e.g., `foundry.company.com`)
- **Authentication type**: Choose `token`
- **API token**: Paste your token
- **Profile name**: Enter a name (e.g., `production`)

### Step 3: Verify Setup

Test your configuration:

```bash
pltr verify
```

You should see: `✅ Authentication successful!`

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

## 🌍 Environment Variables

For CI/CD pipelines and automated scripts, you can use environment variables instead of stored profiles:

### Token Authentication

```bash
export FOUNDRY_TOKEN="your-api-token"
export FOUNDRY_HOST="foundry.company.com"

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

### Environment Variable Priority

pltr-cli uses this priority order:
1. Command-line `--profile` option
2. Environment variables (if no profile specified)
3. Default profile (if no env vars or profile specified)

## 🔒 Security Best Practices

### Token Security

- **Never commit tokens to version control**
- **Use environment variables in CI/CD**
- **Rotate tokens regularly**
- **Use minimal permissions**
- **Store tokens securely** (pltr-cli uses system keyring)

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

- **Use HTTPS** (pltr-cli enforces this)
- **Verify SSL certificates** (enabled by default)
- **Use VPN** when required by your organization
- **Monitor network traffic** for suspicious activity

## 🛠️ Profile Management

### Listing Profiles

```bash
pltr configure list-profiles
```

Output example:
```
Configured profiles:
  * production (default)
    development
    staging
```

### Setting Default Profile

```bash
pltr configure set-default development
```

### Deleting Profiles

```bash
# Interactive deletion (with confirmation)
pltr configure delete old-profile

# Force deletion (skip confirmation)
pltr configure delete old-profile --force
```

### Profile Storage

Profiles are stored securely:
- **Credentials**: System keyring (encrypted)
- **Configuration**: `~/.config/pltr/profiles.json`
- **No plaintext secrets**: Tokens and secrets are never stored in plain text

## 🔧 Troubleshooting

### Common Authentication Issues

#### "Authentication failed" Error

**Possible causes:**
- Expired or invalid token
- Wrong hostname
- Network connectivity issues
- Insufficient permissions

**Solutions:**
```bash
# Verify token is still valid
pltr verify --profile your-profile

# Reconfigure with new token
pltr configure configure --profile your-profile

# Check hostname format (should not include https://)
# Correct: foundry.company.com
# Incorrect: https://foundry.company.com
```

#### "Profile not found" Error

**Solutions:**
```bash
# List existing profiles
pltr configure list-profiles

# Create the missing profile
pltr configure configure --profile missing-profile
```

#### "Network timeout" Error

**Solutions:**
- Check VPN connection
- Verify Foundry hostname
- Test network connectivity to Foundry instance
- Check firewall settings

### OAuth2 Specific Issues

#### "Invalid client credentials" Error

**Solutions:**
- Verify client ID and secret with administrator
- Ensure OAuth2 client is properly configured in Foundry
- Check that required scopes are assigned

#### "Insufficient scope" Error

**Solutions:**
- Contact Foundry administrator to review OAuth2 scopes
- Ensure client has permissions for intended operations

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

Override default config location:

```bash
export PLTR_CONFIG_HOME="/custom/path"
pltr configure configure
```

### Debugging Authentication

Enable verbose output:

```bash
# Most commands support debug output through error messages
# For authentication debugging, check the verify command output
pltr verify --profile your-profile
```

### Integration with External Tools

#### Docker/Containers

```dockerfile
# In Dockerfile
ENV FOUNDRY_TOKEN="your-token"
ENV FOUNDRY_HOST="foundry.company.com"

# Or use secrets
RUN --mount=type=secret,id=foundry_token \
    FOUNDRY_TOKEN=$(cat /run/secrets/foundry_token) \
    pltr verify
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
