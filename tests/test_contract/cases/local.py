"""Commands that make no Foundry API call (see __init__.py).

They are excluded from the contract test's API-error and success checks.
Commands in configure.py, alias.py, completion.py, shell.py and cli.py.
"""

LOCAL = {
    "hello": "prints a greeting; no API call (cli.py)",
    "configure configure": "writes a local profile and keyring entry",
    "configure list-profiles": "reads local profiles",
    "configure set-default": "writes the local default profile",
    "configure delete": "deletes a local profile",
    "shell": "starts an interactive REPL",
    "shell start": "starts an interactive REPL",
    "shell interactive": "starts an interactive REPL",
    "completion install": "writes shell completion files",
    "completion show": "prints a shell completion script",
    "completion uninstall": "removes shell completion files",
    "alias add": "edits the local alias file",
    "alias remove": "edits the local alias file",
    "alias edit": "edits the local alias file",
    "alias list": "reads the local alias file",
    "alias show": "reads the local alias file",
    "alias clear": "edits the local alias file",
    "alias export": "prints the local aliases as JSON (stdout or --output)",
    "alias import": "reads aliases from a file",
    "alias resolve": "resolves an alias locally",
}
