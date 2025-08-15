"""Alias configuration management for pltr-cli."""

import json
from typing import Dict, List, Optional

from rich import print as rprint
from rich.table import Table

from pltr.config.settings import Settings


class AliasManager:
    """Manages command aliases for pltr-cli."""

    def __init__(self) -> None:
        """Initialize the alias manager."""
        settings = Settings()
        self.config_dir = settings.config_dir
        self.aliases_file = self.config_dir / "aliases.json"
        self.aliases = self._load_aliases()

    def _load_aliases(self) -> Dict[str, str]:
        """Load aliases from the configuration file.

        Returns:
            Dictionary mapping alias names to commands
        """
        if not self.aliases_file.exists():
            return {}

        try:
            with open(self.aliases_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_aliases(self) -> None:
        """Save aliases to the configuration file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.aliases_file, "w") as f:
            json.dump(self.aliases, f, indent=2, sort_keys=True)

    def add_alias(self, name: str, command: str) -> bool:
        """Add a new alias.

        Args:
            name: Alias name
            command: Command to alias

        Returns:
            True if alias was added, False if it already exists

        Raises:
            ValueError: If the alias would create a circular reference
        """
        if name in self.aliases:
            return False

        # Check for circular references
        if self._would_create_cycle(name, command):
            raise ValueError(f"Alias '{name}' would create a circular reference")

        self.aliases[name] = command
        self._save_aliases()
        return True

    def remove_alias(self, name: str) -> bool:
        """Remove an alias.

        Args:
            name: Alias name to remove

        Returns:
            True if alias was removed, False if it didn't exist
        """
        if name not in self.aliases:
            return False

        del self.aliases[name]
        self._save_aliases()
        return True

    def edit_alias(self, name: str, command: str) -> bool:
        """Edit an existing alias.

        Args:
            name: Alias name to edit
            command: New command for the alias

        Returns:
            True if alias was edited, False if it doesn't exist
        """
        if name not in self.aliases:
            return False

        # Check for circular references
        if self._would_create_cycle(name, command):
            raise ValueError(f"Alias '{name}' would create a circular reference")

        self.aliases[name] = command
        self._save_aliases()
        return True

    def get_alias(self, name: str) -> Optional[str]:
        """Get the command for an alias.

        Args:
            name: Alias name

        Returns:
            The aliased command, or None if alias doesn't exist
        """
        return self.aliases.get(name)

    def list_aliases(self) -> Dict[str, str]:
        """Get all aliases.

        Returns:
            Dictionary of all aliases
        """
        return self.aliases.copy()

    def resolve_alias(self, command: str, max_depth: int = 10) -> str:
        """Resolve an alias to its final command.

        Args:
            command: Command that might be an alias
            max_depth: Maximum recursion depth for nested aliases

        Returns:
            The resolved command
        """
        resolved = command
        depth = 0
        seen = set()

        while resolved in self.aliases and depth < max_depth:
            if resolved in seen:
                # Circular reference detected
                return command

            seen.add(resolved)
            resolved = self.aliases[resolved]
            depth += 1

        return resolved

    def _would_create_cycle(self, name: str, command: str) -> bool:
        """Check if adding/editing an alias would create a cycle.

        Args:
            name: Alias name
            command: Command to check

        Returns:
            True if this would create a cycle
        """
        # Direct self-reference
        if command == name:
            return True

        # Follow the chain starting from command
        # If we ever reach 'name', it would create a cycle
        current = command
        visited = set()

        while current in self.aliases:
            # Check for existing cycles
            if current in visited:
                break
            visited.add(current)

            # Get what this alias points to
            current = self.aliases[current]

            # If we reached the name we're trying to add, it's a cycle
            if current == name:
                return True

        return False

    def display_aliases(self, name: Optional[str] = None) -> None:
        """Display aliases in a formatted table.

        Args:
            name: Optional specific alias to display
        """
        if name:
            command = self.get_alias(name)
            if command:
                rprint(f"[green]{name}[/green] → {command}")
            else:
                rprint(f"[red]Alias '{name}' not found[/red]")
            return

        if not self.aliases:
            rprint("[yellow]No aliases configured[/yellow]")
            return

        table = Table(title="Command Aliases", show_header=True)
        table.add_column("Alias", style="cyan")
        table.add_column("Command", style="green")

        for alias_name, command in sorted(self.aliases.items()):
            table.add_row(alias_name, command)

        rprint(table)

    def get_completion_items(self) -> List[str]:
        """Get alias names for shell completion.

        Returns:
            List of alias names
        """
        return list(self.aliases.keys())

    def clear_all(self) -> int:
        """Clear all aliases.

        Returns:
            Number of aliases cleared
        """
        count = len(self.aliases)
        self.aliases = {}
        self._save_aliases()
        return count

    def import_aliases(self, data: Dict[str, str]) -> int:
        """Import aliases from a dictionary.

        Args:
            data: Dictionary of aliases to import

        Returns:
            Number of aliases imported
        """
        count = 0
        for name, command in data.items():
            if not self._would_create_cycle(name, command):
                self.aliases[name] = command
                count += 1

        if count > 0:
            self._save_aliases()

        return count

    def export_aliases(self) -> Dict[str, str]:
        """Export all aliases.

        Returns:
            Dictionary of all aliases
        """
        return self.aliases.copy()
