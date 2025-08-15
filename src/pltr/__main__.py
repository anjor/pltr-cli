"""Main entry point for pltr CLI."""

import os
import sys

# Handle shell completion before importing the main app
if "_PLTR_COMPLETE" in os.environ:
    # Import Click's completion handling
    from click.shell_completion import shell_complete
    import typer
    from pltr.cli import app

    # Convert Typer app to Click command
    click_app = typer.main.get_command(app)

    # Get the completion instruction from environment
    complete_var = "_PLTR_COMPLETE"
    instruction = os.environ.get(complete_var, "")

    # Run Click's completion
    exit_code = shell_complete(click_app, {}, "pltr", complete_var, instruction)
    sys.exit(exit_code)

# Normal CLI execution
from pltr.cli import app
from pltr.utils.alias_resolver import inject_alias_resolution

if __name__ == "__main__":
    # Resolve aliases before running the app
    inject_alias_resolution()
    app()
