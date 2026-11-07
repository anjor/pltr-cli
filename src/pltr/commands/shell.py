"""
Interactive shell (REPL) command for the pltr CLI.

Runs pltr commands typed at a prompt, with tab completion and persistent
history. Each line runs exactly like a separate ``pltr`` invocation, so
output, errors and exit codes behave as on the command line, and one
command's ``--format`` never leaks into the next. When stdin is not a
terminal, commands are read from it line by line without a prompt (for
example ``pltr shell < commands.txt``).

Tab completion uses click's own completion machinery
(``click.shell_completion.ShellComplete``), the same completions the shell
scripts from ``pltr completion`` get, including the generated ``pltr api``
tree.
"""

import os
import re
import shlex
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Iterator, List, Optional

import click
import typer

from ..config.aliases import AliasManager
from ..config.profiles import ProfileManager
from ..contract import stdin_is_interactive
from ..utils.alias_resolver import resolve_command_aliases

shell_app = typer.Typer(
    name="shell",
    help="Start an interactive shell session with tab completion and history",
)

#: Lines that end the session (besides Ctrl-D).
EXIT_WORDS = {"exit", "quit", ":q", ":quit", ":exit"}
#: ``help`` alone shows pltr's help; ``help <command>`` shows that command's.
HELP_WORDS = {"help", "?", ":help", ":h"}
#: On Windows a backslash separates path components (``C:\data\x.csv``), so
#: shell lines are split without backslash escapes there.
WINDOWS = sys.platform == "win32"

#: Lines that pass credentials (``configure configure --token X``, or
#: ``!export FOUNDRY_TOKEN=X``) are never written to the history file.
_SECRET_LINE = re.compile(
    r"(?:^|\s)--(?:token|client-secret|client-id)(?:[=\s]|$)"
    r"|\bFOUNDRY_(?:TOKEN|CLIENT_SECRET)="
)


def holds_credentials(line: str) -> bool:
    """Whether a shell line passes a token, client ID or client secret."""
    return _SECRET_LINE.search(line) is not None


def get_history_file() -> Path:
    """The REPL history file, in pltr's configuration directory.

    That is ``$XDG_CONFIG_HOME/pltr`` or ``~/.config/pltr``, like the rest of
    pltr's configuration. On POSIX the directory is created private (0700)
    and the file is private (0600) too.
    """
    from ..config.settings import Settings

    config_dir = Settings().config_dir
    config_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    history = config_dir / "repl_history"
    descriptor = os.open(history, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.close(descriptor)
    if os.name == "posix" and history.stat().st_mode & 0o077:
        history.chmod(0o600)  # one created by an earlier version (0644)
    return history


def make_history(path: Path) -> Any:
    """A prompt_toolkit FileHistory that doesn't save lines with credentials.

    Such lines can still be recalled with the arrow keys during the session.
    """
    from prompt_toolkit.history import FileHistory

    class PltrHistory(FileHistory):
        def store_string(self, string: str) -> None:
            if not holds_credentials(string):
                super().store_string(string)

    return PltrHistory(str(path))


def get_prompt() -> str:
    """Get the prompt string for the REPL."""
    try:
        profile_manager = ProfileManager()
        current_profile = profile_manager.get_active_profile()
        if current_profile:
            return f"pltr ({current_profile})> "
        else:
            return "pltr> "
    except Exception:
        return "pltr> "


def split_line(text: str, *, windows: Optional[bool] = None) -> List[str]:
    """Split a command line like a shell; an unclosed quote keeps its partial word.

    Quotes group words everywhere. A backslash escapes the next character
    except on Windows (``windows`` defaults to the platform), where it is a
    path separator: ``C:\\data\\x.csv`` stays one unchanged word.
    """
    lexer = shlex.shlex(text, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    if WINDOWS if windows is None else windows:
        lexer.escape = ""
    words: List[str] = []
    try:
        for word in lexer:
            words.append(word)
    except ValueError:  # end of input inside a quote or after an escape
        words.append(lexer.token)
    return words


def root_command() -> click.Command:
    """The click command of the whole pltr CLI."""
    # Imported here: pltr.cli imports this module.
    from ..cli import app as main_app

    return typer.main.get_command(main_app)


def build_completer(root: click.Command) -> Any:
    """A prompt_toolkit completer for shell lines (pltr commands without 'pltr')."""
    from click.shell_completion import ShellComplete
    from prompt_toolkit.completion import Completer, Completion, PathCompleter
    from prompt_toolkit.document import Document

    complete = ShellComplete(root, {}, "pltr", "_PLTR_COMPLETE")
    shell_words = ("exit", "help", "quit")

    class PltrCompleter(Completer):
        def get_completions(self, document: Any, complete_event: Any) -> Iterator[Any]:
            text = document.text_before_cursor
            if text.lstrip().startswith(("!", "#")):
                return
            words = split_line(text)
            incomplete = "" if not text or text[-1].isspace() else words.pop()
            if words and words[0] in HELP_WORDS:
                words = words[1:]  # "help folder <TAB>" completes like "folder"
            try:
                items = complete.get_completions(list(words), incomplete)
            except Exception:  # completion must never break the prompt
                return
            if not words and not incomplete.startswith("-"):
                items = [item for item in items if item.value != "shell"]
                for word in shell_words:
                    if word.startswith(incomplete):
                        yield Completion(word, -len(incomplete), display_meta="shell")
                for name, command in sorted(AliasManager().list_aliases().items()):
                    if name.startswith(incomplete):
                        yield Completion(
                            name, -len(incomplete), display_meta=f"alias: {command}"
                        )
            path_document = Document(incomplete, len(incomplete))
            for item in items:
                if item.type in ("file", "dir"):
                    paths = PathCompleter(
                        only_directories=item.type == "dir", expanduser=True
                    )
                    yield from paths.get_completions(path_document, complete_event)
                else:
                    yield Completion(
                        str(item.value), -len(incomplete), display_meta=item.help or ""
                    )
            # Typer's Path options leave file names to the shell (bash's
            # `complete -o default`); there is no shell to fall back to here.
            if not items and _looks_like_path(incomplete):
                paths = PathCompleter(expanduser=True)
                yield from paths.get_completions(path_document, complete_event)

    return PltrCompleter()


def _looks_like_path(text: str, *, windows: Optional[bool] = None) -> bool:
    if text.startswith(("/", ".", "~")) or "/" in text:
        return True
    if WINDOWS if windows is None else windows:
        # C:\data, data\file.csv, \\server\share
        return "\\" in text or (len(text) >= 2 and text[0].isalpha() and text[1] == ":")
    return False


def run_line(root: click.Command, line: str) -> bool:
    """Run one line of input; return False when the session should end."""
    text = line.strip()
    if not text or text.startswith("#"):
        return True
    if text in EXIT_WORDS:
        return False
    if text.startswith("!"):  # a system command, as in click-repl
        subprocess.run(text[1:], shell=True)
        return True

    args = split_line(text)
    if args[0] in HELP_WORDS:
        args = args[1:] + ["--help"]
    args = resolve_command_aliases(args)
    if args and args[0] == "shell":
        click.echo("Already in the pltr shell; type 'exit' to leave it.", err=True)
        return True
    try:
        root.main(args=args, prog_name="pltr", standalone_mode=True)
    except SystemExit:
        pass  # every command ends this way, successful or not
    except Exception:  # only with PLTR_DEBUG set (the error layer re-raises)
        traceback.print_exc()
    return True


def run_repl(root: click.Command, read_line: Callable[[], str]) -> None:
    """Read and run lines until EOF or an exit word."""
    while True:
        try:
            line = read_line()
        except KeyboardInterrupt:
            continue
        except EOFError:
            return
        if not run_line(root, line):
            return


def _read_stdin_line() -> str:
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    return line


@shell_app.command()
def start(
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use for the session"
    ),
) -> None:
    """
    Start an interactive shell session for pltr CLI.

    Features:
    - Tab completion for all commands
    - Command history (persistent across sessions)
    - Current profile displayed in prompt
    - All pltr commands available without the 'pltr' prefix

    Examples:
        # Start interactive shell
        $ pltr shell

        # In the shell, run commands without 'pltr' prefix:
        pltr> dataset get ri.foundry.main.dataset.123
        pltr> space list --format json
        pltr> help folder

        # Exit the shell:
        pltr> exit
    """
    # Set profile if specified
    if profile:
        os.environ["PLTR_PROFILE"] = profile

    root = root_command()
    interactive = stdin_is_interactive()
    if not interactive:
        run_repl(root, _read_stdin_line)
        return

    from prompt_toolkit import PromptSession

    if profile:
        click.secho(f"Using profile: {profile}", fg="green", err=True)
    click.secho("\nWelcome to pltr interactive shell!", fg="cyan", bold=True, err=True)
    click.echo("Type 'help' for available commands, 'exit' to quit.\n", err=True)

    session: Any = PromptSession(
        message=get_prompt,
        history=make_history(get_history_file()),
        completer=build_completer(root),
        complete_while_typing=True,
        enable_history_search=True,
    )
    run_repl(root, session.prompt)
    click.secho("\nGoodbye!", fg="cyan", err=True)


# Make 'start' the default command when just running 'pltr shell'
@shell_app.callback(invoke_without_command=True)
def shell_callback(
    ctx: typer.Context,
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use for the session"
    ),
) -> None:
    """Interactive shell mode with tab completion and command history."""
    if ctx.invoked_subcommand is None:
        start(profile=profile)


# Alternative command name for convenience
@shell_app.command("interactive", hidden=True)
def interactive_alias(
    profile: Optional[str] = typer.Option(
        None, "--profile", help="Auth profile to use for the session"
    ),
) -> None:
    """Alias for 'start' command."""
    start(profile=profile)
