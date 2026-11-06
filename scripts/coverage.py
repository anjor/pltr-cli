"""Report which public foundry-platform-sdk (V2) methods pltr commands reach.

    uv run python scripts/coverage.py           # summary per namespace
    uv run python scripts/coverage.py --list    # one line per SDK method
    uv run python scripts/coverage.py --json    # machine-readable report

Every public V2 SDK method must be reachable from a generated `pltr api` command,
except the methods in the generator's explicit exclusion list (each with a
reason). The script walks the real CLI tree, so a spec that doesn't turn into a
command doesn't count. It exits with status 1 when a method is missing, when a
command calls a method the installed SDK doesn't have, or when an excluded method
is also generated.

Curated commands (pltr dataset ..., pltr ontology ...) are counted through
`curated_commands()`, which returns nothing until curated commands record the SDK
methods they call (#187/#188).
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPTS_DIR = Path(__file__).resolve().parent


def load_generator() -> Any:
    """Import scripts/generate_api_commands.py without touching sys.path."""
    name = "pltr_generate_api_commands"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, SCRIPTS_DIR / "generate_api_commands.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def generated_commands() -> Dict[str, str]:
    """{SDK method ("admin.User.list"): "pltr api admin user list"} from the CLI."""
    import click
    import typer

    from pltr.cli import app
    from pltr.commands.api._runtime import ApiCommand

    root = typer.main.get_command(app)
    found: Dict[str, str] = {}

    def walk(command: click.Command, path: List[str], parent: click.Context) -> None:
        ctx = click.Context(command, info_name=path[-1], parent=parent)
        if isinstance(command, ApiCommand):
            found[command.sdk_method] = " ".join(path)
            return
        if isinstance(command, click.Group):
            for name in command.list_commands(ctx):
                child = command.get_command(ctx, name)
                if child is not None:
                    walk(child, path + [name], ctx)

    root_ctx = click.Context(root, info_name="pltr")
    api = root.get_command(root_ctx, "api")  # type: ignore[attr-defined]
    if api is not None:
        walk(api, ["pltr", "api"], root_ctx)
    return found


def curated_commands() -> Dict[str, List[str]]:
    """Hook for curated-command coverage: {SDK method: ["pltr dataset get", ...]}.

    Curated commands don't record the SDK methods they call yet. Once they carry
    that metadata (see #187/#188), collect it here and the report counts it.
    """
    return {}


@dataclasses.dataclass
class Coverage:
    sdk_version: str
    methods: List[Dict[str, Any]]  # one row per public SDK method
    missing: List[str]  # neither generated nor excluded
    unknown: List[str]  # generated commands for methods the SDK doesn't have
    excluded_but_generated: List[str]

    @property
    def ok(self) -> bool:
        return not (self.missing or self.unknown or self.excluded_but_generated)

    def to_dict(self) -> Dict[str, Any]:
        generated = sum(1 for row in self.methods if row["generated"])
        return {
            "sdkVersion": self.sdk_version,
            "totalMethods": len(self.methods),
            "generated": generated,
            "curated": sum(1 for row in self.methods if row["curated"]),
            "excluded": sum(1 for row in self.methods if row["excludedReason"]),
            "missing": self.missing,
            "unknown": self.unknown,
            "excludedButGenerated": self.excluded_but_generated,
            "methods": self.methods,
        }


def compute(config: Optional[Any] = None) -> Coverage:
    generator = load_generator()
    config = config or generator.V2
    methods = generator.all_public_methods(config)
    generated = generated_commands()
    curated = curated_commands()
    rows = []
    for method in methods:
        rows.append(
            {
                "method": method,
                "generated": generated.get(method),
                "curated": curated.get(method, []),
                "excludedReason": config.excluded.get(method),
            }
        )
    known = set(methods)
    return Coverage(
        sdk_version=generator.sdk_version(),
        methods=rows,
        missing=[
            row["method"]
            for row in rows
            if not row["generated"] and not row["excludedReason"]
        ],
        unknown=sorted(set(generated) - known),
        excluded_but_generated=sorted(set(config.excluded) & set(generated)),
    )


def print_summary(coverage: Coverage, list_methods: bool) -> None:
    report = coverage.to_dict()
    by_namespace: Dict[str, List[int]] = {}
    for row in coverage.methods:
        counts = by_namespace.setdefault(row["method"].split(".")[0], [0, 0, 0, 0])
        counts[0] += 1
        counts[1] += 1 if row["generated"] else 0
        counts[2] += 1 if row["curated"] else 0
        counts[3] += 1 if row["excludedReason"] else 0
    print(f"foundry-platform-sdk {report['sdkVersion']} (V2)")
    print(
        f"{'namespace':<26}{'methods':>8}{'generated':>11}{'curated':>9}{'excluded':>10}"
    )
    for namespace, (total, gen, cur, exc) in sorted(by_namespace.items()):
        print(f"{namespace:<26}{total:>8}{gen:>11}{cur:>9}{exc:>10}")
    total = report["totalMethods"]
    print(
        f"{'total':<26}{total:>8}{report['generated']:>11}{report['curated']:>9}"
        f"{report['excluded']:>10}"
    )
    covered = report["generated"] + report["excluded"]
    print(
        f"\nGenerated coverage: {report['generated']}/{total - report['excluded']} "
        f"callable methods ({covered}/{total} including {report['excluded']} "
        "justified exclusions)."
    )
    for row in coverage.methods:
        if row["excludedReason"]:
            print(f"  excluded {row['method']}: {row['excludedReason']}")
    if list_methods:
        print()
        for row in coverage.methods:
            target = row["generated"] or f"(excluded: {row['excludedReason']})"
            print(f"{row['method']:<80} {target}")
    for label, items in (
        ("Missing (no command, not excluded)", coverage.missing),
        ("Commands for methods the installed SDK doesn't have", coverage.unknown),
        ("Excluded methods that are also generated", coverage.excluded_but_generated),
    ):
        if items:
            print(f"\n{label}:")
            for item in items:
                print(f"  {item}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--json", action="store_true", help="Print a JSON report.")
    parser.add_argument("--list", action="store_true", help="List every method.")
    args = parser.parse_args(argv)
    coverage = compute()
    if args.json:
        print(json.dumps(coverage.to_dict(), indent=2))
    else:
        print_summary(coverage, args.list)
    if not coverage.ok:
        if not args.json:
            print(
                "\nCoverage check failed. Regenerate the specs "
                "(uv run python scripts/generate_api_commands.py) or add a justified "
                "exclusion to the generator config.",
                file=sys.stderr,
            )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
