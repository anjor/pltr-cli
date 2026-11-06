#!/usr/bin/env python3
"""Check every foundry-platform-sdk call in pltr against the installed SDK.

Usage (from the repository root):

    uv run python scripts/check_sdk_calls.py                    # report; exit 1 on new/stale
    uv run python scripts/check_sdk_calls.py --all              # also list allowlisted ones
    uv run python scripts/check_sdk_calls.py --write-allowlist  # rewrite the allowlist
    uv run python scripts/check_sdk_calls.py --json             # every call as JSON records

The same check runs in CI as tests/test_sdk_call_guardrail.py. See
docs/development/sdk-guardrail.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.sdk_calls import (  # noqa: E402
    DEFAULT_ALLOWLIST,
    Finding,
    collect_sdk_calls,
    compare_with_allowlist,
    find_violations,
    load_allowlist,
    render_allowlist,
    unused_labeled_exceptions,
)


def _print_grouped(findings: Sequence[Finding], allowlisted: Dict[str, str]) -> None:
    by_file: Dict[str, Dict[str, List[Finding]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for finding in findings:
        by_file[finding.call.file][finding.violation.rule].append(finding)
    for file in sorted(by_file):
        print(f"\nsrc/pltr/{file}")
        for rule in sorted(by_file[file]):
            group = by_file[file][rule]
            print(f"  {rule} ({len(group)})")
            for finding in sorted(group, key=lambda f: f.call.line):
                call = finding.call
                marker = "" if finding.key in allowlisted else "  [NEW]"
                print(f"    {call.line:>4}  {call.function}  {call.sdk_path}{marker}")
                print(f"          {finding.violation.message}")


def main(argv: Sequence[str] = ()) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=DEFAULT_ALLOWLIST,
        help="allowlist file (default: %(default)s)",
    )
    parser.add_argument(
        "--write-allowlist",
        action="store_true",
        help="rewrite the allowlist with the current violations, keeping existing reasons",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="list allowlisted violations too (default: only new ones)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print one JSON record per SDK/HTTP call and exit",
    )
    args = parser.parse_args(list(argv))

    started = time.perf_counter()
    calls = collect_sdk_calls()
    findings = find_violations(calls)
    elapsed = time.perf_counter() - started

    if args.json:
        json.dump([call.to_dict() for call in calls], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    allowlist = load_allowlist(args.allowlist)
    if args.write_allowlist:
        args.allowlist.write_text(
            render_allowlist(findings, allowlist), encoding="utf-8"
        )
        print(f"Wrote {len(findings)} entries to {args.allowlist}")
        return 0

    new, stale = compare_with_allowlist(findings, allowlist)
    shown = findings if args.all else new
    if shown:
        _print_grouped(shown, allowlist)

    if stale:
        print("\nAllowlist entries that no longer occur (delete these lines):")
        for key in stale:
            print(f"  {key}")
    for key in unused_labeled_exceptions(calls):
        print(
            f"\nNote: labeled HTTP exception {key} no longer makes a direct HTTP call."
        )

    sdk_calls = sum(1 for call in calls if call.kind == "sdk")
    http_calls = len(calls) - sdk_calls
    print(
        f"\n{sdk_calls} SDK calls and {http_calls} direct HTTP calls checked in "
        f"{elapsed:.1f}s: {len(findings)} violations "
        f"({len(findings) - len(new)} allowlisted), {len(new)} new, "
        f"{len(stale)} stale allowlist entries."
    )
    if new or stale:
        print("See docs/development/sdk-guardrail.md for how to fix or allowlist them.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
