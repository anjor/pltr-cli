# Quick Start Guide

Get up and running with pltr-cli in under 5 minutes! This guide will take you from installation to your first successful Foundry query.

## 📦 Installation

### Option 1: Install from PyPI (Recommended)
```bash
pip install pltr-cli
```

### Option 2: Install with pipx (Isolated)
```bash
pipx install pltr-cli
```

### Option 3: Install from source
```bash
git clone https://github.com/anjor/pltr-cli.git
cd pltr-cli
pip install .
```

## ✅ Verify Installation

Check that pltr-cli is installed correctly:

```bash
pltr --version
```

You should see the version number. If you get a "command not found" error, ensure your Python scripts directory is in your PATH.

## 🔐 Setup Authentication

pltr-cli needs to authenticate with your Foundry instance. You have two options:

### Quick Setup (Token)
If you have a Foundry API token:

```bash
pltr configure configure
```

Follow the prompts to enter:
- **Foundry hostname** (e.g., `foundry.company.com`)
- **API token** (from your Foundry settings)
- **Profile name** (e.g., `production`)

### Environment Variables (CI/CD)
For scripts or CI/CD, use environment variables:

```bash
export FOUNDRY_TOKEN="your-token-here"
export FOUNDRY_HOST="foundry.company.com"
```

## 🧪 Test Your Connection

Verify authentication is working:

```bash
pltr verify
```

You should see: `✅ Authentication successful!`

## 🚀 Your First Query

Now let's run your first Foundry operation! Try these examples:

### 1. Check Current User
```bash
pltr admin user current
```

### 2. List Available Ontologies
```bash
pltr ontology list
```

### 3. Search for Builds (Orchestration)
```bash
pltr orchestration builds search
```

### 4. Execute a Simple SQL Query
```bash
pltr sql execute "SELECT 1 as test"
```

### 5. Get Dataset Information (if you have a dataset RID)
```bash
pltr dataset get ri.foundry.main.dataset.your-dataset-rid
```

## 🎯 Interactive Mode

For exploratory work, try the interactive shell:

```bash
pltr shell
```

In shell mode, you can run commands without the `pltr` prefix:
```
pltr> admin user current
pltr> sql execute "SELECT COUNT(*) FROM my_table"
pltr> exit
```

## 📊 Output Formats

pltr-cli supports multiple output formats:

```bash
# Table format (default)
pltr admin user list

# JSON format
pltr admin user list --format json

# CSV format
pltr admin user list --format csv

# Save to file
pltr sql execute "SELECT * FROM dataset" --output results.csv
```

## 🔧 Shell Completion

Enable tab completion for your shell:

```bash
# Install completions
pltr completion install

# For specific shells
pltr completion install --shell bash
pltr completion install --shell zsh
pltr completion install --shell fish
```

## ✨ What's Next?

Now that you're set up, explore these key areas:

### Data Analysis
- **[SQL Commands](commands.md#sql-commands)**: Execute queries and export results
- **[Dataset Operations](commands.md#dataset-commands)**: Work with Foundry datasets
- **[Common Workflows](workflows.md)**: Real-world analysis patterns

### Advanced Features
- **[Multi-Profile Setup](authentication.md#multiple-profiles)**: Work with multiple Foundry instances
- **[Orchestration Operations](commands.md#orchestration-commands)**: Manage builds, jobs, and schedules
- **[Ontology Operations](commands.md#ontology-commands)**: Work with Foundry ontologies
- **[Admin Tasks](commands.md#admin-commands)**: User and group management

### Get Help
- Run `pltr --help` to see all available commands
- Run `pltr <command> --help` for specific command help
- Check the [Command Reference](commands.md) for complete documentation
- See [Troubleshooting](troubleshooting.md) for common issues

## 🆘 Common Issues

### Authentication Errors
- **Token expired**: Run `pltr configure` to update your token
- **Wrong hostname**: Ensure hostname doesn't include `https://`
- **Network issues**: Check VPN/proxy settings

### Command Not Found
- **Path issues**: Ensure Python scripts directory is in PATH
- **Virtual environment**: Make sure you're in the correct environment

### Permission Denied
- **Admin commands**: Some commands require Foundry admin permissions
- **Dataset access**: Ensure you have read permissions for datasets

---

🎉 **Congratulations!** You're now ready to use pltr-cli. For complete documentation, see the [Command Reference](commands.md) and [Common Workflows](workflows.md).

*Need help? Check the [Troubleshooting Guide](troubleshooting.md) or run `pltr --help`*
