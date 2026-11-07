"""What `pltr` imports at startup (`pltr --help`, every shell completion).

Importing foundry-platform-sdk's model packages takes about half a second,
so command and service modules import SDK models in the functions that use
them, never at module level. A command that calls the SDK imports it when it
runs.
"""

import subprocess
import sys

CHECK = """
import sys

from typer.testing import CliRunner

import pltr.cli

after_import = sorted(m for m in sys.modules if m.split(".")[0] == "foundry_sdk")
for args in (["--help"], ["dataset", "--help"], ["sql", "--help"]):
    result = CliRunner().invoke(pltr.cli.app, args)
    assert result.exit_code == 0, result.output
after_help = sorted(m for m in sys.modules if m.split(".")[0] == "foundry_sdk")
print(after_import, after_help)
"""


def test_startup_and_help_do_not_import_the_sdk():
    result = subprocess.run(
        [sys.executable, "-c", CHECK], capture_output=True, text=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[] []", (
        "A command or service module imports foundry_sdk at module level; "
        "import SDK models inside the functions that use them."
    )
