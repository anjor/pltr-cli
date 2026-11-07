"""Shell completion utilities for pltr CLI."""

from typing import List, Optional
from pathlib import Path
import json

from pltr.config.profiles import ProfileManager
from pltr.config.aliases import AliasManager


def _rid_cache_file() -> Path:
    """The RID cache, ``~/.cache/pltr/recent_rids.json``.

    Raises RuntimeError (KeyError before Python 3.12) without a home directory.
    """
    return Path.home() / ".cache" / "pltr" / "recent_rids.json"


def _read_rid_cache(rid_cache_file: Path) -> Optional[List[str]]:
    """The cached RIDs, or None if the cache is missing or isn't a valid cache."""
    if not rid_cache_file.exists():
        return None
    try:
        with open(rid_cache_file) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    rids = data.get("rids") if isinstance(data, dict) else None
    if not isinstance(rids, list):
        return None
    return [rid for rid in rids if isinstance(rid, str)]


def get_cached_rids() -> List[str]:
    """Get recently used RIDs from cache."""
    try:
        rids = _read_rid_cache(_rid_cache_file())
    except Exception:
        # Best effort, like cache_rid: no home directory or an unreadable cache
        # directory only means there are no recent RIDs to complete.
        rids = None
    if rids is not None:
        return rids

    # Return some example RIDs if no cache
    return [
        "ri.foundry.main.dataset.",
        "ri.foundry.main.folder.",
        "ri.foundry.main.ontology.",
    ]


def cache_rid(rid: str) -> None:
    """Cache a RID for future completions.

    Best effort: commands call this after their API call succeeded and before
    printing the result, so a cache that can't be read or written (a read-only
    or missing home directory, as in some containers and agent sandboxes, or
    a corrupted cache file) must never fail the command. A retry would repeat
    the call, which may be a write.
    """
    try:
        rid_cache_file = _rid_cache_file()
        # A missing or corrupted cache starts over.
        rids = _read_rid_cache(rid_cache_file) or []

        # Add new RID (keep last 50)
        if rid not in rids:
            rids.insert(0, rid)
            rids = rids[:50]

        rid_cache_file.parent.mkdir(parents=True, exist_ok=True)
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
