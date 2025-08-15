"""Shell completion utilities for pltr CLI."""

import os
from typing import List
from pathlib import Path
import json

from pltr.config.profiles import ProfileManager
from pltr.config.aliases import AliasManager


def get_cached_rids() -> List[str]:
    """Get recently used RIDs from cache."""
    cache_dir = Path.home() / ".cache" / "pltr"
    rid_cache_file = cache_dir / "recent_rids.json"

    if rid_cache_file.exists():
        try:
            with open(rid_cache_file) as f:
                data = json.load(f)
                return data.get("rids", [])
        except Exception:
            pass

    # Return some example RIDs if no cache
    return [
        "ri.foundry.main.dataset.",
        "ri.foundry.main.folder.",
        "ri.foundry.main.ontology.",
    ]


def cache_rid(rid: str):
    """Cache a RID for future completions."""
    cache_dir = Path.home() / ".cache" / "pltr"
    cache_dir.mkdir(parents=True, exist_ok=True)
    rid_cache_file = cache_dir / "recent_rids.json"

    # Load existing cache
    rids = []
    if rid_cache_file.exists():
        try:
            with open(rid_cache_file) as f:
                data = json.load(f)
                rids = data.get("rids", [])
        except Exception:
            pass

    # Add new RID (keep last 50)
    if rid not in rids:
        rids.insert(0, rid)
        rids = rids[:50]

    # Save cache
    try:
        with open(rid_cache_file, "w") as f:
            json.dump({"rids": rids}, f)
    except Exception:
        pass


def complete_rid(incomplete: str):
    """Complete RID arguments."""
    rids = get_cached_rids()
    return [rid for rid in rids if rid.startswith(incomplete)]


def complete_profile(incomplete: str):
    """Complete profile names."""
    try:
        manager = ProfileManager()
        profiles = manager.list_profiles()
        return [profile for profile in profiles if profile.startswith(incomplete)]
    except Exception:
        return []


def complete_output_format(incomplete: str):
    """Complete output format options."""
    formats = ["table", "json", "csv"]
    return [fmt for fmt in formats if fmt.startswith(incomplete)]


def complete_sql_query(incomplete: str):
    """Complete SQL query templates."""
    templates = [
        "SELECT * FROM ",
        "SELECT COUNT(*) FROM ",
        "SELECT DISTINCT ",
        "WHERE ",
        "GROUP BY ",
        "ORDER BY ",
        "LIMIT 10",
        "JOIN ",
        "LEFT JOIN ",
        "INNER JOIN ",
    ]
    return [tmpl for tmpl in templates if tmpl.lower().startswith(incomplete.lower())]


def complete_ontology_action(incomplete: str):
    """Complete ontology action names."""
    # This would ideally fetch from the API but for now return common patterns
    actions = [
        "create",
        "update",
        "delete",
        "createOrUpdate",
        "link",
        "unlink",
    ]
    return [action for action in actions if action.startswith(incomplete)]


def complete_alias_names(incomplete: str):
    """Complete alias names."""
    manager = AliasManager()
    aliases = manager.get_completion_items()
    return [alias for alias in aliases if alias.startswith(incomplete)]


def complete_file_path(incomplete: str):
    """Complete file paths."""
    # This is handled by shell natively, but we can provide hints
    path = Path(incomplete) if incomplete else Path.cwd()

    if incomplete and not path.exists():
        parent = path.parent
        prefix = path.name
    else:
        parent = path if path.is_dir() else path.parent
        prefix = ""

    try:
        items = []
        for item in parent.iterdir():
            if item.name.startswith(prefix):
                # Return path strings - shell will handle directory indicators
                items.append(str(item))
        return items
    except Exception:
        return []


def setup_completion_environment():
    """Set up environment for shell completion support."""
    # This is called when the CLI starts to register completion handlers

    # Check if we're in completion mode
    if os.environ.get("_PLTR_COMPLETE"):
        # We're generating completions
        # Set up any necessary context
        pass


def handle_completion():
    """Handle shell completion requests."""
    # This is the main entry point for completion handling
    # It's called when _PLTR_COMPLETE environment variable is set

    complete_var = os.environ.get("_PLTR_COMPLETE")
    if not complete_var:
        return False

    # Click handles the completion automatically through Typer
    # Our custom completion functions are registered via autocompletion parameter
    return True


# Register custom completion functions for specific parameter types
COMPLETION_FUNCTIONS = {
    "rid": complete_rid,
    "profile": complete_profile,
    "output_format": complete_output_format,
    "sql_query": complete_sql_query,
    "ontology_action": complete_ontology_action,
    "file_path": complete_file_path,
}
