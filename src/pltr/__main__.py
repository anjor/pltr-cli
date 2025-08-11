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
    
    # Run Click's completion
    shell_complete(click_app, {}, sys.argv[1] if len(sys.argv) > 1 else "pltr")
    sys.exit(0)

# Normal CLI execution
from pltr.cli import app

if __name__ == "__main__":
    app()