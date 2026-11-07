"""SDK call guardrail (#185): every SDK call in pltr must work with the real SDK.

Resolves every foundry-platform-sdk call in src/pltr/services and src/pltr/commands
against a real FoundryClient (no network), binds its arguments to the real signature
and checks the preview rules, then compares the violations with the ratchet allowlist
tests/sdk_call_allowlist.txt. See docs/development/sdk-guardrail.md.

Run the same check by hand with: uv run python scripts/check_sdk_calls.py
"""

from typing import List

import pytest

from scripts.sdk_calls import (
    DEFAULT_ALLOWLIST,
    Finding,
    collect_sdk_calls,
    compare_with_allowlist,
    find_violations,
    load_allowlist,
)

HOW_TO_FIX = """
Fix the call: point it at the real SDK method and arguments, never pass preview to a GA
method, always pass the literal preview=True to a beta one, and pass explicit keywords
instead of **kwargs. If it truly can't be fixed in this change, add its key to
tests/sdk_call_allowlist.txt with a reason
(uv run python scripts/check_sdk_calls.py --write-allowlist keeps existing reasons).
See docs/development/sdk-guardrail.md."""


@pytest.fixture(scope="module")
def findings() -> List[Finding]:
    return find_violations(collect_sdk_calls())


def test_no_new_sdk_call_violations(findings):
    new, _ = compare_with_allowlist(findings, load_allowlist())
    lines = []
    for finding in new:
        call = finding.call
        lines.append(
            f"\n  {call.location}  {call.function}\n"
            f"    {call.sdk_path}: {finding.violation.rule_id}\n"
            f"    {finding.violation.message}\n"
            f"    key: {finding.key}"
        )
    assert not new, (
        f"{len(new)} new SDK call violation(s):\n"
        + "\n".join(lines)
        + "\n"
        + HOW_TO_FIX
    )


def test_allowlist_has_no_stale_entries(findings):
    _, stale = compare_with_allowlist(findings, load_allowlist())
    assert not stale, (
        f"{len(stale)} entries in {DEFAULT_ALLOWLIST.name} no longer occur. The calls were "
        "fixed (or moved/renamed); delete these lines (or re-run "
        "scripts/check_sdk_calls.py --write-allowlist):\n  " + "\n  ".join(stale)
    )


def test_allowlist_entries_have_reasons():
    missing = [key for key, reason in load_allowlist().items() if not reason]
    assert not missing, "Allowlist entries need a reason:\n  " + "\n  ".join(missing)
