"""Shell completion utilities for pltr CLI."""

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


def complete_alias_names(incomplete: str):
    """Complete alias names."""
    manager = AliasManager()
    aliases = manager.get_completion_items()
    return [alias for alias in aliases if alias.startswith(incomplete)]
