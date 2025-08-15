# Troubleshooting Guide

Common issues and solutions when using pltr-cli. This guide helps you diagnose and fix problems quickly.

## 🚨 Quick Diagnostics

Before diving into specific issues, run these quick checks:

```bash
# 1. Verify pltr-cli is installed and working
pltr --version

# 2. Check authentication
pltr verify

# 3. List configured profiles
pltr configure list-profiles

# 4. Test with a simple command
pltr hello
```

## 🔐 Authentication Issues

### Error: "Authentication failed"

**Symptoms:**
- `pltr verify` returns authentication failure
- Commands return 401 or 403 errors
- "Invalid credentials" messages

**Possible Causes & Solutions:**

#### 1. Expired or Invalid Token
```bash
# Check if token is expired (common cause)
pltr verify --profile your-profile

# Solution: Generate new token and reconfigure
pltr configure configure --profile your-profile
# Follow prompts to enter new token
```

#### 2. Incorrect Hostname
```bash
# Check your profile configuration
pltr configure list-profiles

# Common mistakes:
# ❌ Wrong: https://foundry.company.com
# ❌ Wrong: foundry.company.com/
# ✅ Correct: foundry.company.com

# Reconfigure with correct hostname
pltr configure configure --profile your-profile --host foundry.company.com
```

#### 3. Network/VPN Issues
```bash
# Test network connectivity
ping foundry.company.com

# If on corporate network, ensure VPN is connected
# Check if you can access Foundry web interface
```

#### 4. Profile Not Found
```bash
# Error: Profile 'xyz' not found
# List available profiles
pltr configure list-profiles

# Create missing profile
pltr configure configure --profile xyz
```

### Error: "SSL Certificate verification failed"

**Solutions:**
```bash
# This usually indicates network/proxy issues
# Check corporate proxy settings
# Ensure VPN is properly connected

# For development only (NOT recommended for production):
# Contact your IT team instead of disabling SSL verification
```

## 🔧 Installation Issues

### Error: "Command not found: pltr"

**Causes & Solutions:**

#### 1. Not in PATH
```bash
# Check if Python scripts directory is in PATH
echo $PATH

# Find where pip installed pltr
pip show pltr-cli

# Add to PATH (example for bash/zsh)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

#### 2. Wrong Python Environment
```bash
# Check which Python/pip you're using
which python
which pip

# Ensure you're in the correct virtual environment
# Or install globally if that's your setup
pip install --user pltr-cli
```

#### 3. Installation Failed
```bash
# Reinstall with verbose output
pip install --upgrade --force-reinstall pltr-cli -v

# Check for dependency conflicts
pip check
```

### Error: "Permission denied" during installation

```bash
# Solution 1: Use --user flag
pip install --user pltr-cli

# Solution 2: Use virtual environment (recommended)
python -m venv pltr-env
source pltr-env/bin/activate  # On Windows: pltr-env\Scripts\activate
pip install pltr-cli

# Solution 3: Use pipx (isolated installation)
pipx install pltr-cli
```

## 💾 Data Access Issues

### Error: "Dataset not found" or "Invalid RID"

**Symptoms:**
- `pltr dataset get` returns not found errors
- RID appears correct but command fails

**Solutions:**
```bash
# 1. Verify RID format
# Correct format: ri.foundry.main.dataset.xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# 2. Check permissions
pltr admin user current
# Ensure you have read access to the dataset

# 3. Verify dataset exists and you have access via web interface

# 4. Try listing available ontologies to find valid RIDs
pltr ontology list
```

### Error: "SQL execution failed"

**Common SQL Issues:**

#### 1. Syntax Errors
```bash
# Error: Invalid SQL syntax
# Check your query carefully
pltr sql execute "SELECT * FROM my_table LIMIT 10"

# Use quotes properly for complex queries
pltr sql execute "
  SELECT column1, COUNT(*)
  FROM my_table
  WHERE date > '2025-01-01'
  GROUP BY column1
"
```

#### 2. Table/Column Not Found
```bash
# Check available datasets
pltr ontology list

# Verify table name and column names
pltr sql execute "DESCRIBE my_table"

# Use correct table references
```

#### 3. Query Timeout
```bash
# For long-running queries, increase timeout
pltr sql execute "SELECT * FROM huge_table" --timeout 3600

# Or use async pattern
QUERY_ID=$(pltr sql submit "SELECT * FROM huge_table")
pltr sql wait $QUERY_ID --timeout 3600
```

#### 4. Permission Denied
```bash
# Check if you have access to query the specific tables
# Contact admin if you need additional permissions
pltr admin user current
```

## 🏢 Admin Command Issues

### Error: "Insufficient permissions"

**Symptoms:**
- Admin commands return permission errors
- Can't list users or groups

**Solutions:**
```bash
# 1. Verify you have admin permissions
pltr admin user current

# 2. Check if you're in admin groups
# (Output should show admin roles/groups)

# 3. Contact your Foundry administrator for access
```

### Error: "User/Group not found"

```bash
# 1. Search instead of direct access
pltr admin user search "partial-name"
pltr admin group search "partial-name"

# 2. Use exact identifiers from search results
pltr admin user get "exact-user-id-from-search"
```

## 🖥️ Command Line Issues

### Error: "JSON decode error"

**Symptoms:**
- Commands with JSON parameters fail
- Malformed JSON errors

**Solutions:**
```bash
# 1. Validate JSON syntax
# Use online JSON validator or jq
echo '{"key": "value"}' | jq .

# 2. Proper quoting for shell
# Single quotes preserve literal strings
pltr ontology action-apply ri.ontology.main.ontology.abc123 myAction '{"param": "value"}'

# 3. For complex JSON, use files
echo '{"complex": {"nested": "structure"}}' > params.json
pltr ontology action-apply ri.ontology.main.ontology.abc123 myAction "$(cat params.json)"
```

### Error: "Output format not supported"

```bash
# Check supported formats
pltr <command> --help

# Supported formats are usually: table, json, csv
pltr sql execute "SELECT 1" --format table
pltr sql execute "SELECT 1" --format json
pltr sql execute "SELECT 1" --format csv
```

### Error: "File not found" for output

```bash
# Ensure output directory exists
mkdir -p /path/to/output/
pltr sql execute "SELECT 1" --output /path/to/output/results.csv

# Check permissions on output directory
ls -la /path/to/output/
```

## 🌐 Network Issues

### Error: "Connection timeout"

**Solutions:**
```bash
# 1. Check network connectivity
ping foundry.company.com

# 2. Verify VPN connection if required

# 3. Check for corporate firewall/proxy
# Contact IT team for proxy configuration

# 4. Increase timeout for slow networks
pltr verify --profile your-profile
# (Built-in timeouts usually handle this)
```

### Error: "Connection refused"

**Solutions:**
```bash
# 1. Verify hostname is correct
# Should not include protocol (https://)
pltr configure configure --host foundry.company.com

# 2. Check if Foundry instance is accessible
# Try accessing web interface

# 3. Verify port accessibility (usually 443 for HTTPS)
telnet foundry.company.com 443
```

## 🔄 Interactive Shell Issues

### Error: "Shell command not working"

**Symptoms:**
- `pltr shell` starts but commands fail
- Tab completion not working
- History not saving

**Solutions:**
```bash
# 1. Ensure click-repl is installed
pip install --upgrade pltr-cli

# 2. Check shell configuration
pltr shell --help

# 3. Try with specific profile
pltr shell --profile your-profile

# 4. For tab completion issues
pltr completion install
```

### History File Issues

```bash
# History file location: ~/.config/pltr/repl_history
# If history not working:

# 1. Check directory permissions
ls -la ~/.config/pltr/

# 2. Create directory if missing
mkdir -p ~/.config/pltr/

# 3. Check disk space
df -h ~/.config/
```

## 🛠️ Shell Completion Issues

### Tab Completion Not Working

**Solutions:**
```bash
# 1. Install completions
pltr completion install

# 2. Restart your shell
exec $SHELL

# 3. For manual installation
pltr completion show --shell bash >> ~/.bashrc
source ~/.bashrc

# 4. Check shell type
echo $SHELL
pltr completion install --shell zsh  # if using zsh
```

## 📊 Performance Issues

### Slow Query Execution

**Symptoms:**
- Queries take longer than expected
- Frequent timeouts

**Solutions:**
```bash
# 1. Use async pattern for long queries
QUERY_ID=$(pltr sql submit "SELECT * FROM huge_table")
pltr sql status $QUERY_ID
pltr sql wait $QUERY_ID --timeout 3600

# 2. Optimize your SQL
# Add WHERE clauses to reduce data
# Use LIMIT for testing

# 3. Check query execution plan
pltr sql execute "EXPLAIN SELECT * FROM huge_table"

# 4. Contact Foundry admin about resource limits
```

### High Memory Usage

```bash
# 1. Use streaming for large results
pltr sql execute "SELECT * FROM large_table" --output results.csv

# 2. Limit result size
pltr sql execute "SELECT * FROM large_table LIMIT 10000"

# 3. Use pagination for ontology operations
pltr ontology object-list ri.ontology.main.ontology.abc123 MyType --page-size 100
```

## 🔍 Debugging Tips

### Enable Verbose Output

```bash
# Most commands show detailed error messages
# For debugging, check the full error output

# Use verify command to test connectivity
pltr verify --profile your-profile
```

### Check Configuration Files

```bash
# Profile configuration location
ls -la ~/.config/pltr/

# View profile configuration (credentials are in keyring)
cat ~/.config/pltr/profiles.json

# Check for file permission issues
ls -la ~/.config/pltr/profiles.json
```

### Environment Variable Debugging

```bash
# Check current environment
env | grep FOUNDRY

# Test with environment variables
export FOUNDRY_TOKEN="your-token"
export FOUNDRY_HOST="foundry.company.com"
pltr verify
```

## 🆘 Getting Additional Help

### Built-in Help

```bash
# General help
pltr --help

# Command-specific help
pltr configure --help
pltr sql --help
pltr sql execute --help

# List all available commands
pltr --help | grep Commands -A 20
```

### Information Gathering

When reporting issues, gather this information:

```bash
# 1. Version information
pltr --version
python --version
pip show pltr-cli

# 2. Configuration status
pltr configure list-profiles
pltr verify

# 3. Environment
echo $SHELL
env | grep FOUNDRY
```

### Common Solutions Summary

| Issue | Quick Fix |
|-------|-----------|
| Authentication failed | `pltr configure configure` |
| Command not found | Check PATH, reinstall with `--user` |
| Permission denied | Contact admin, check user permissions |
| Query timeout | Use `--timeout` or async pattern |
| JSON error | Check JSON syntax, use proper quotes |
| Network issues | Check VPN, verify hostname |
| Tab completion | `pltr completion install && exec $SHELL` |

---

💡 **Pro Tips:**
- Always run `pltr verify` first when troubleshooting
- Use `pltr configure list-profiles` to check your setup
- For complex issues, try the same operation via Foundry web interface
- Keep your token up to date - they may expire
- Use `pltr shell` for interactive debugging and exploration
