import json
import os
import shutil
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

from ..auth.storage import CredentialStorage
from ..config.profiles import ProfileManager
from ..utils.completion import complete_profile

app = typer.Typer(help="Manage Palantir MCP server integration")
console = Console(stderr=True)

PLTR_MCP_KEY = "palantir-mcp"


def _resolve_pltr_path() -> str:
    pltr_path = shutil.which("pltr")
    if pltr_path:
        return pltr_path
    return "pltr"


def _build_opencode_mcp_entry(profile: str) -> dict:
    return {
        "type": "local",
        "command": [_resolve_pltr_path(), "mcp", "serve", "--profile", profile],
        "environment": {},
    }


def _build_claude_code_mcp_entry(profile: str) -> dict:
    return {
        "command": _resolve_pltr_path(),
        "args": ["mcp", "serve", "--profile", profile],
    }


def _read_json_file(path: Path) -> dict:
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {}


def _write_json_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _validate_profile(profile: str) -> None:
    profile_manager = ProfileManager()
    if not profile_manager.profile_exists(profile):
        available = profile_manager.list_profiles()
        console.print(f"[red]Error:[/red] Profile '{profile}' not found.")
        if available:
            console.print(f"Available profiles: {', '.join(available)}")
        else:
            console.print("Run 'pltr configure configure' to create a profile first.")
        raise typer.Exit(1)


def _update_opencode_config(directory: Path, profile: str) -> Path:
    config_path = directory / "opencode.json"
    config = _read_json_file(config_path)
    if "mcp" not in config:
        config["mcp"] = {}
    config["mcp"][PLTR_MCP_KEY] = _build_opencode_mcp_entry(profile)
    _write_json_file(config_path, config)
    return config_path


def _update_claude_code_config(directory: Path, profile: str) -> Path:
    config_path = directory / ".mcp.json"
    config = _read_json_file(config_path)
    config[PLTR_MCP_KEY] = _build_claude_code_mcp_entry(profile)
    _write_json_file(config_path, config)
    return config_path


def _get_current_mcp_profile(directory: Path) -> Optional[str]:
    for filename, extract in [
        (
            "opencode.json",
            lambda c: c.get("mcp", {}).get(PLTR_MCP_KEY, {}).get("command", []),
        ),
        (
            ".mcp.json",
            lambda c: [c.get(PLTR_MCP_KEY, {}).get("command", "")]
            + c.get(PLTR_MCP_KEY, {}).get("args", []),
        ),
    ]:
        config_path = directory / filename
        if config_path.exists():
            config = _read_json_file(config_path)
            parts = extract(config)
            for i, part in enumerate(parts):
                if part == "--profile" and i + 1 < len(parts):
                    return parts[i + 1]
    return None


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def serve(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(
        None, "--profile", "-p", help="Profile name", autocompletion=complete_profile
    ),
    command: str = typer.Option("npx", help="Base command to run (default: npx)"),
    package: str = typer.Option("palantir-mcp", help="MCP package to run"),
):
    """Run the Palantir MCP server using credentials from a pltr profile."""
    profile_manager = ProfileManager()
    storage = CredentialStorage()

    active_profile = (
        profile
        or os.environ.get("PLTR_PROFILE")
        or profile_manager.get_active_profile()
    )
    if not active_profile:
        console.print("[red]Error:[/red] No profile configured.")
        console.print("Run 'pltr configure configure' to set up your first profile.")
        raise typer.Exit(1)

    try:
        credentials = storage.get_profile(active_profile)
    except Exception as e:
        console.print(
            f"[red]Error:[/red] Failed to load credentials for profile '{active_profile}': {e}"
        )
        raise typer.Exit(1)

    host = credentials.get("host")
    auth_type = credentials.get("auth_type", "token")

    if auth_type != "token":
        console.print(
            f"[yellow]Warning:[/yellow] Profile '{active_profile}' uses {auth_type} auth. "
            "MCP server wrapper works best with 'token' auth. It may fail to connect."
        )

    token = credentials.get("token")

    if not host or not token:
        console.print(
            f"[red]Error:[/red] Profile '{active_profile}' is missing host or token."
        )
        raise typer.Exit(1)

    env = os.environ.copy()
    env["FOUNDRY_URL"] = host
    env["FOUNDRY_TOKEN"] = token

    cmd_args = [command, "-y", package, "--foundry-api-url", host] + ctx.args

    console.print(
        f"[green]Starting MCP server[/green] using profile: [bold]{active_profile}[/bold] ({host})"
    )

    executable = shutil.which(command)
    if not executable:
        console.print(f"[red]Error:[/red] Command '{command}' not found in PATH.")
        raise typer.Exit(1)

    try:
        os.execvpe(executable, cmd_args, env)
    except OSError as e:
        console.print(f"[red]Error:[/red] Failed to start MCP server: {e}")
        raise typer.Exit(1)


@app.command()
def init(
    profile: str = typer.Argument(..., help="Profile name to wire into MCP configs"),
    directory: Optional[str] = typer.Option(
        None, "--dir", "-d", help="Target directory (defaults to current directory)"
    ),
):
    """Initialize project-local MCP configs for OpenCode and Claude Code."""
    _validate_profile(profile)

    target = Path(directory) if directory else Path.cwd()
    if not target.is_dir():
        console.print(f"[red]Error:[/red] Directory '{target}' does not exist.")
        raise typer.Exit(1)

    opencode_path = _update_opencode_config(target, profile)
    claude_path = _update_claude_code_config(target, profile)

    storage = CredentialStorage()
    credentials = storage.get_profile(profile)
    host = credentials.get("host", "Unknown")

    from rich.table import Table

    table = Table(title=f"MCP configs initialized for profile: {profile}")
    table.add_column("Client", style="cyan")
    table.add_column("Config File", style="magenta")
    table.add_column("Foundry URL", style="green")

    table.add_row("OpenCode", str(opencode_path), host)
    table.add_row("Claude Code", str(claude_path), host)

    console.print(table)
    console.print(
        f"\nOpen [bold]OpenCode[/bold] or [bold]Claude Code[/bold] in [cyan]{target}[/cyan] "
        "and the Palantir MCP will connect automatically."
    )


@app.command()
def switch(
    profile: str = typer.Argument(..., help="Profile name to switch to"),
    directory: Optional[str] = typer.Option(
        None, "--dir", "-d", help="Target directory (defaults to current directory)"
    ),
):
    """Switch project-local MCP configs to a different profile."""
    _validate_profile(profile)

    target = Path(directory) if directory else Path.cwd()

    opencode_exists = (target / "opencode.json").exists()
    claude_exists = (target / ".mcp.json").exists()

    if not opencode_exists and not claude_exists:
        console.print(
            f"[red]Error:[/red] No MCP configs found in '{target}'.\n"
            f"Run 'pltr mcp init {profile}' first to create them."
        )
        raise typer.Exit(1)

    old_profile = _get_current_mcp_profile(target)

    updated = []
    if opencode_exists:
        _update_opencode_config(target, profile)
        updated.append("opencode.json")
    if claude_exists:
        _update_claude_code_config(target, profile)
        updated.append(".mcp.json")

    storage = CredentialStorage()
    credentials = storage.get_profile(profile)
    host = credentials.get("host", "Unknown")

    switch_msg = f"'{old_profile}' -> '{profile}'" if old_profile else f"-> '{profile}'"
    console.print(f"[green]Switched MCP profile[/green]: {switch_msg}")
    console.print(f"Foundry URL: [bold]{host}[/bold]")
    console.print(f"Updated: {', '.join(updated)}")
    console.print(
        "\n[yellow]Restart your OpenCode/Claude Code session to pick up the new profile.[/yellow]"
    )


@app.command()
def status(
    directory: Optional[str] = typer.Option(
        None, "--dir", "-d", help="Target directory (defaults to current directory)"
    ),
):
    """Show which Foundry profile is configured for MCP in this directory."""
    target = Path(directory) if directory else Path.cwd()

    current_profile = _get_current_mcp_profile(target)
    if not current_profile:
        console.print(f"No MCP configs found in '{target}'.")
        console.print("Run 'pltr mcp init <profile>' to set one up.")
        return

    storage = CredentialStorage()
    try:
        credentials = storage.get_profile(current_profile)
        host = credentials.get("host", "Unknown")
    except Exception:
        host = "Error loading credentials"

    from rich.table import Table

    table = Table(title=f"MCP Status: {target}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Active Profile", current_profile)
    table.add_row("Foundry URL", host)

    configs_found = []
    if (target / "opencode.json").exists():
        configs_found.append("opencode.json")
    if (target / ".mcp.json").exists():
        configs_found.append(".mcp.json")
    table.add_row("Config Files", ", ".join(configs_found))

    console.print(table)
