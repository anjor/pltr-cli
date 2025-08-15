"""Alias resolution utilities for CLI commands."""

import shlex
import sys
from typing import List, Optional

from pltr.config.aliases import AliasManager


def resolve_command_aliases(args: Optional[List[str]] = None) -> List[str]:
    """Resolve command aliases in the argument list.

    Args:
        args: Command arguments (defaults to sys.argv[1:])

    Returns:
        Resolved command arguments
    """
    if args is None:
        args = sys.argv[1:]

    if not args:
        return args

    # Don't resolve aliases for certain commands
    if args[0] in ["alias", "--help", "-h", "--version", "completion"]:
        return args

    # Check if the first argument is an alias
    manager = AliasManager()
    first_arg = args[0]

    # Try to resolve as an alias
    resolved = manager.resolve_alias(first_arg)

    if resolved != first_arg:
        # It's an alias - parse the resolved command
        try:
            resolved_parts = shlex.split(resolved)
            # Replace the first argument with the resolved command parts
            # and append any additional arguments
            return resolved_parts + args[1:]
        except ValueError:
            # If parsing fails, return original args
            return args

    return args


def inject_alias_resolution() -> None:
    """Inject alias resolution into sys.argv before CLI parsing."""
    # Get resolved arguments
    resolved_args = resolve_command_aliases()

    # Replace sys.argv with resolved arguments
    sys.argv = [sys.argv[0]] + resolved_args
