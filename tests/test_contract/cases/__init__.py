"""Per-module cases for the CLI-wide contract test (test_cli_contract.py).

There is one module here per ``src/pltr/commands/<module>.py``, so agents
converting different command modules never edit the same file. A case
module may define any of:

``NOT_CONVERTED``: set of command paths (e.g. ``"dataset get"``) that don't
    follow the output/error contract yet. The contract test still runs them,
    and fails as soon as one passes: delete a command's entry when you
    convert it. This set only shrinks.

``LOCAL``: dict of command path -> reason, for commands that make no
    Foundry API call (configure, alias, completion, ...). They are not run.

``SUCCESS``: dict of command path -> list of responses, each a dict of
    keyword arguments for ``stub_foundry_http.respond`` (``{"json": {...}}``,
    ``{"status_code": 204}``), queued in order for the success-path check.
    Every converted command needs one.

``ARGS``: dict of command path -> argument list that replaces the
    synthesized required arguments, for commands whose required arguments
    need specific values (JSON input, several options, ...).

``SUCCESS_EXEMPT``: dict of command-path prefix -> reason. Commands under a
    prefix (e.g. ``"api"``, the generated tree whose generator tests the
    success path) don't need a ``SUCCESS`` case; the 404/400 error checks
    still run. Use sparingly; a ``SUCCESS`` case, when present, still runs.

Use ``CONTRACT_RID`` (below) wherever a case needs the RID the contract test
passes for RID-like arguments.
"""

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

#: The value the contract test passes for arguments whose name ends in "rid".
CONTRACT_RID = "ri.compass.main.folder.contract-test"


@dataclass
class Cases:
    not_converted: Set[str] = field(default_factory=set)
    local: Dict[str, str] = field(default_factory=dict)
    success: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    args: Dict[str, List[str]] = field(default_factory=dict)
    success_exempt: Dict[str, str] = field(default_factory=dict)
    duplicates: List[str] = field(default_factory=list)


def load_cases() -> Cases:
    """Merge the case modules of this package."""
    cases = Cases()
    for module_info in sorted(pkgutil.iter_modules(__path__), key=lambda m: m.name):
        module = importlib.import_module(f"{__name__}.{module_info.name}")
        for attr, target in (
            ("NOT_CONVERTED", cases.not_converted),
            ("LOCAL", cases.local),
            ("SUCCESS", cases.success),
            ("ARGS", cases.args),
            ("SUCCESS_EXEMPT", cases.success_exempt),
        ):
            values = getattr(module, attr, None) or {}
            for key in values:
                if key in target:
                    cases.duplicates.append(f"{attr} {key!r} ({module_info.name})")
            target.update(values)
    return cases
