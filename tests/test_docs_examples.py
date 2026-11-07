"""Check every `pltr ...` example in the documentation against the real CLI.

The test reads README.md, docs/**/*.md and claude_skill/**/*.md, finds the
`pltr` commands in shell code blocks (bash, sh, console, unlabeled, ...) and
in inline code, and resolves each one against the command tree that
`pltr.contract.iter_commands` walks (curated commands and the generated
`pltr api` tree). An example fails when it names a command that doesn't
exist, uses an option the command doesn't have, or passes more positional
arguments than the command takes. Hidden commands and options count as
missing: they are deprecated aliases kept for one release, and the docs
should show their replacement.

What the checker skips:
- placeholders in place of a command or argument (`<rid>`, `{rid}`,
  `[OPTIONS]`, `...`), shell variables and `$(...)` substitutions (the
  substitution itself is checked as its own example);
- environment assignments before `pltr` (`PLTR_FORMAT=json pltr ...`),
  pipes, `&&`, `;`, redirections and `# comments`;
- aliases defined in the same file with `pltr alias add NAME "COMMAND"`,
  which are expanded.

Examples that are wrong on purpose (a removed command in a migration note,
for instance) go in IGNORED with a reason. Each entry must still match a
failing example, so the list can't go stale.
"""

import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple

import click
import pytest
import typer

from pltr.cli import app
from pltr.contract import iter_commands

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATTERNS = ("README.md", "docs/**/*.md", "claude_skill/**/*.md")

#: {(file, start of the example): reason} for examples that are wrong on
#: purpose. The start is matched against the normalized example the failure
#: message prints (`pltr` plus its words, joined by single spaces).
IGNORED: Dict[Tuple[str, str], str] = {
    ("docs/api-commands.md", "pltr api v3"): (
        "describes where a future V3 tree would go (maintainer notes)"
    ),
    ("docs/user-guide/aliases.md", "pltr a"): "the circular-alias error example",
    ("docs/user-guide/aliases.md", "pltr b"): "the circular-alias error example",
}

#: Code block languages that hold shell commands ("" is an unlabeled block).
SHELL_LANGUAGES = {"", "bash", "sh", "shell", "console", "zsh", "fish", "text"}

#: Words that can come before `pltr` in a simple command.
WRAPPERS = {
    "!",
    "{",
    "command",
    "do",
    "elif",
    "else",
    "env",
    "exec",
    "if",
    "nohup",
    "python",
    "python3",
    "run",
    "sudo",
    "then",
    "time",
    "until",
    "uv",
    "watch",
    "while",
    "xargs",
}

_FENCE = re.compile(r"^\s*(`{3,}|~{3,})\s*([\w+-]*)")
#: The `pltr shell` prompt, `pltr> ` or `pltr (profile)> `, and its own words.
_SHELL_PROMPT = re.compile(r"^pltr(?: \([^)]*\))?>(.*)$")
_SHELL_WORDS = {"exit", "quit", "help"}
_INLINE_CODE = re.compile(r"(`+)(.+?)\1")
_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
#: `<placeholder>` (also inside a word, as in `ri.foundry.main.dataset.<id>`):
#: quoted before lexing so the shell lexer doesn't read it as a redirection.
_ANGLE_PLACEHOLDER = re.compile(r"<[A-Za-z][^<>\n]*?>")
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_PUNCTUATION = set("|&;<>()")


@dataclass(frozen=True)
class Example:
    """One `pltr` invocation found in a Markdown file."""

    file: str
    line: int
    words: Tuple[str, ...]  # the words after `pltr`

    @property
    def text(self) -> str:
        return " ".join(("pltr",) + self.words)


# --------------------------------------------------------------- extraction


def _strip_comment(line: str) -> str:
    """Drop a shell `# comment`: a `#` outside quotes that starts a word."""
    quote = ""
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1].isspace()):
            return line[:index].rstrip()
    return line


def snippets(text: str) -> Iterator[Tuple[int, str, bool]]:
    """(line number, code, from a code block) for every shell code block line
    (continuation lines joined) and every inline code span."""
    fence = ""
    language = ""
    pending = ""
    pending_line = 0
    for number, line in enumerate(text.splitlines(), 1):
        match = _FENCE.match(line)
        if fence:
            if match and match.group(1).startswith(fence) and not match.group(2):
                fence = ""
                pending = ""
                continue
            if language not in SHELL_LANGUAGES:
                continue
            code = _strip_comment(line.strip())
            if code.startswith("$ "):
                code = code[2:]
            prompt = _SHELL_PROMPT.match(code)
            if prompt and not pending:
                # A line typed in `pltr shell`: a pltr command without `pltr`,
                # or one of the shell's own words.
                typed = prompt.group(1).strip()
                if not typed or typed.split()[0] in _SHELL_WORDS or typed[0] == "!":
                    continue
                code = "pltr " + typed
            if not code and not pending:
                continue
            if not pending:
                pending_line = number
            if code.endswith("\\"):
                pending += code[:-1] + " "
                continue
            yield pending_line, pending + code, True
            pending = ""
        elif match:
            fence = match.group(1)
            language = match.group(2).lower()
        else:
            for span in _INLINE_CODE.finditer(line):
                yield number, span.group(2).strip(), False


def _substitutions(code: str) -> Tuple[str, List[str]]:
    """Replace each `$(...)` in `code` with a placeholder word and return the
    substituted commands, so that they are checked on their own."""
    inner: List[str] = []
    out = []
    index = 0
    while index < len(code):
        if code.startswith("$(", index):
            depth = 0
            end = index + 1
            while end < len(code):
                if code[end] == "(":
                    depth += 1
                elif code[end] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                end += 1
            inner.append(code[index + 2 : end])
            out.append("SUBSTITUTION")
            index = end + 1
        else:
            out.append(code[index])
            index += 1
    return "".join(out), inner


def _quote_placeholders(code: str) -> str:
    """Quote `<placeholder>`s outside quotes, so that the shell lexer doesn't
    read their `<` and `>` as redirections (inside quotes they are text)."""
    out = []
    quote = ""
    index = 0
    while index < len(code):
        char = code[index]
        if quote:
            if char == quote:
                quote = ""
        elif char in "'\"":
            quote = char
        else:
            match = _ANGLE_PLACEHOLDER.match(code, index)
            if match:
                out.append(shlex.quote(match.group(0)))
                index = match.end()
                continue
        out.append(char)
        index += 1
    return "".join(out)


def _lex(code: str) -> Optional[List[str]]:
    code = _quote_placeholders(code)
    lexer = shlex.shlex(code, posix=True, punctuation_chars="|&;<>()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:  # an unbalanced quote: not a complete command
        return None


def _simple_commands(tokens: Sequence[str]) -> Iterator[List[str]]:
    """Split a token list at pipes, `&&`, `;`, parentheses, and drop
    redirections with their targets."""
    current: List[str] = []
    skip_target = False
    for token in tokens:
        if skip_target:
            skip_target = False
            continue
        if token and set(token) <= _PUNCTUATION:
            if "<" in token or ">" in token:
                # `2>&1`: the `2` belongs to the redirection.
                if current and current[-1].isdigit():
                    current.pop()
                skip_target = True
                continue
            if current:
                yield current
            current = []
            continue
        current.append(token)
    if current:
        yield current


def _invocation(words: Sequence[str]) -> Optional[Tuple[str, ...]]:
    """The words after `pltr` if this simple command runs pltr."""
    for index, word in enumerate(words):
        if word == "pltr":
            return tuple(words[index + 1 :])
        if not (
            word in WRAPPERS
            or _ENV_ASSIGNMENT.match(word)
            or word.startswith("-")
            or word.isdigit()
            or word == "SUBSTITUTION"
        ):
            return None
    return None


def find_examples(file: str, text: str) -> List[Example]:
    """Every `pltr` invocation in a Markdown text."""
    examples = []
    for line, code, in_block in snippets(text):
        if "pltr" not in code:
            continue
        pending = [code]
        while pending:
            outer, inner = _substitutions(pending.pop())
            pending.extend(inner)
            tokens = _lex(outer)
            if tokens is None:
                continue
            for words in _simple_commands(tokens):
                found = _invocation(words)
                if found is not None:
                    examples.append(Example(file, line, found))
    return examples


# --------------------------------------------------------------- resolution


class CommandTree:
    """The CLI's commands and groups, from `iter_commands`."""

    def __init__(self, root: click.Command) -> None:
        self.root = root
        self.commands: Dict[Tuple[str, ...], click.Command] = {
            tuple(entry.path.split()): entry.command for entry in iter_commands(root)
        }
        self.groups: Set[Tuple[str, ...]] = {()}
        for path in self.commands:
            for end in range(1, len(path)):
                self.groups.add(path[:end])
        self.root_flags = _flags(root)


def _flags(command: click.Command) -> Dict[str, click.Option]:
    flags: Dict[str, click.Option] = {}
    for param in command.params:
        if isinstance(param, click.Option):
            for flag in param.opts + param.secondary_opts:
                flags[flag] = param
    return flags


def _is_placeholder(word: str) -> bool:
    """`<rid>`, `{name}`, `[OPTIONS]`, `$VAR`, `COMMAND`, `...`, and words
    with a placeholder inside, such as `da<TAB>`."""
    return bool(
        word in ("...", "…", "SUBSTITUTION")
        or word.startswith(("<", "{", "[", "$"))
        or _ANGLE_PLACEHOLDER.search(word)
        or re.fullmatch(r"[A-Z][A-Z0-9_]*", word)
    )


def _is_optional_placeholder(word: str) -> bool:
    """`[OPTIONS]`, `[ARGUMENTS]`, `[<sub>...]`, `...`: not an argument.

    JSON arrays (`'[{"type": "count"}]'`) are arguments, not placeholders.
    """
    return word in ("...", "…") or bool(
        re.fullmatch(r"\[[A-Za-z<][^\]\"'{}]*\](\.\.\.|…)?", word)
    )


def check(
    tree: CommandTree, example: Example, aliases: Dict[str, Tuple[str, ...]]
) -> List[str]:
    """Problems with one example (an empty list when it is fine)."""
    words = list(example.words)
    path: Tuple[str, ...] = ()
    expansions = 0
    while words:
        word = words[0]
        if word.startswith("-"):
            break
        child = path + (word,)
        if child in tree.commands or child in tree.groups:
            path = child
            words.pop(0)
            if path in tree.commands and path not in tree.groups:
                break
            continue
        if path in tree.commands:
            break  # a group that runs on its own, such as `pltr shell`
        if not path and word in aliases and expansions < 10:
            words[:1] = list(aliases[word])
            expansions += 1
            continue
        if _is_placeholder(word):
            return []  # `pltr <group> --help`: nothing more to check
        return [f"`{' '.join(('pltr',) + child)}` is not a command"]

    shown = " ".join(("pltr",) + path)
    if path not in tree.commands:
        flags = tree.root_flags if not path else {}
        for word in words:
            name = word.split("=", 1)[0]
            if word.startswith("-") and name != "--help" and name not in flags:
                return [f"`{shown}` is a group and has no option {name}"]
        return []

    command = tree.commands[path]
    if command.hidden:
        return [f"`{shown}` is hidden (a deprecated alias): show its replacement"]
    return _check_parameters(command, shown, words)


def _check_parameters(
    command: click.Command, shown: str, words: List[str]
) -> List[str]:
    flags = _flags(command)
    problems = []
    positionals = 0
    index = 0
    while index < len(words):
        word = words[index]
        index += 1
        bracketed = word.startswith("[-")
        if bracketed:
            word = word.strip("[]")
        if word == "--":
            positionals += len(words) - index
            break
        if word.startswith("-") and word != "-" and not _NUMBER.match(word):
            name, has_value, _ = word.partition("=")
            if not word.startswith("--") and len(word) > 2:
                name = word[:2]  # `-fjson`
                has_value = "attached"
            if name == "--help":
                continue
            option = flags.get(name)
            if option is None:
                if not _is_placeholder(name.lstrip("-")):
                    problems.append(f"`{shown}` has no option {name}")
                # Assume it takes the next word as its value, so that the
                # value isn't also reported as an extra argument.
                if (
                    not has_value
                    and index < len(words)
                    and not words[index].startswith("-")
                ):
                    index += 1
                continue
            if option.hidden:
                problems.append(
                    f"`{shown}` option {name} is hidden (a deprecated alias): "
                    "show its replacement"
                )
            if not (option.is_flag or option.count or has_value):
                index += max(option.nargs, 1)
            continue
        if not _is_optional_placeholder(word):
            positionals += 1

    arguments = [p for p in command.params if isinstance(p, click.Argument)]
    if any(argument.nargs == -1 for argument in arguments):
        return problems
    limit = sum(max(argument.nargs, 1) for argument in arguments)
    if positionals > limit:
        problems.append(
            f"`{shown}` takes {limit} argument{'s' if limit != 1 else ''}, "
            f"this example passes {positionals}"
        )
    return problems


def _alias_definitions(examples: Sequence[Example]) -> Dict[str, Example]:
    """Aliases defined in a file with `pltr alias add NAME "COMMAND"`, as
    {name: the aliased command as an example}."""
    aliases: Dict[str, Example] = {}
    for example in examples:
        words = example.words
        if words[:2] == ("alias", "add") and len(words) >= 4:
            tokens = _lex(words[3])
            if tokens:
                aliases[words[2]] = Example(example.file, example.line, tuple(tokens))
    return aliases


def _aliases(examples: Sequence[Example]) -> Dict[str, Tuple[str, ...]]:
    return {name: e.words for name, e in _alias_definitions(examples).items()}


# --------------------------------------------------------------------- test


def doc_files() -> List[Path]:
    files: Set[Path] = set()
    for pattern in DOC_PATTERNS:
        files.update(REPO_ROOT.glob(pattern))
    return sorted(files)


def find_problems(tree: CommandTree) -> List[Tuple[Example, str]]:
    problems = []
    for path in doc_files():
        file = path.relative_to(REPO_ROOT).as_posix()
        examples = find_examples(file, path.read_text(encoding="utf-8"))
        definitions = _alias_definitions(examples)
        aliases = {name: e.words for name, e in definitions.items()}
        for example in examples:
            for problem in check(tree, example, aliases):
                problems.append((example, problem))
        for name, target in definitions.items():
            # An alias's command may name another alias (aliases of aliases).
            for problem in check(tree, target, aliases):
                problems.append((target, f"alias {name!r}: {problem}"))
    return problems


def _ignored(example: Example) -> Optional[Tuple[str, str]]:
    """The IGNORED entry that covers this example, if any."""
    for file, start in IGNORED:
        if example.file == file and example.text.startswith(start):
            return (file, start)
    return None


@pytest.fixture(scope="module")
def tree() -> CommandTree:
    return CommandTree(typer.main.get_command(app))


def test_doc_examples_use_real_commands_and_options(tree: CommandTree) -> None:
    used: Set[Tuple[str, str]] = set()
    failures = []
    for example, problem in find_problems(tree):
        key = _ignored(example)
        if key is not None:
            used.add(key)
        else:
            failures.append(
                f"{example.file}:{example.line}: {problem}\n    {example.text}"
            )
    stale = sorted(set(IGNORED) - used)
    message = []
    if failures:
        message.append(
            f"{len(failures)} documentation example(s) don't match the CLI "
            "(fix the example, or add it to IGNORED with a reason if it is "
            "wrong on purpose):\n" + "\n".join(failures)
        )
    if stale:
        message.append(
            "Entries in IGNORED that match no failing example (remove them):\n"
            + "\n".join(f"    {key}" for key in stale)
        )
    assert not message, "\n\n".join(message)


# ------------------------------------------------------- checker self-tests


@pytest.mark.parametrize(
    "markdown, expected",
    [
        (
            "```bash\npltr folder list ri.x  # comment\n```",
            [("folder", "list", "ri.x")],
        ),
        (
            "```bash\npltr sql execute \\\n  'SELECT 1' --format json\n```",
            [("sql", "execute", "SELECT 1", "--format", "json")],
        ),
        (
            "```bash\nRID=$(pltr dataset create x --parent-folder ri.f --format json | jq -r .rid)\n```",
            [("dataset", "create", "x", "--parent-folder", "ri.f", "--format", "json")],
        ),
        (
            "```bash\nPLTR_FORMAT=json pltr verify 2>&1 >/dev/null && echo ok\n```",
            [("verify",)],
        ),
        ("Run `pltr dataset get <rid>` first.", [("dataset", "get", "<rid>")]),
        ("```python\nsubprocess.run('pltr x')\n```", []),
        ("```bash\necho pltr is great; pip install pltr-cli\n```", []),
        (
            "```bash\nfor r in $(cat r.txt); do pltr dataset get $r; done\n```",
            [("dataset", "get", "$r")],
        ),
        (
            "```\npltr> dataset get ri.x\npltr (prod)> exit\npltr> help folder\n```",
            [("dataset", "get", "ri.x")],
        ),
        (
            "```bash\npltr sql execute 'SELECT * FROM `<rid>` LIMIT 1' > <out.csv>\n```",
            [("sql", "execute", "SELECT * FROM `<rid>` LIMIT 1")],
        ),
        (
            "```bash\npltr dataset get ri.foundry.main.dataset.<id> <extra arg>\n```",
            [("dataset", "get", "ri.foundry.main.dataset.<id>", "<extra arg>")],
        ),
    ],
)
def test_find_examples(markdown: str, expected: List[Tuple[str, ...]]) -> None:
    assert [e.words for e in find_examples("x.md", markdown)] == expected


@pytest.mark.parametrize(
    "example, problem",
    [
        ("pltr folder list ri.x --page-size 5 --format json", None),
        ("pltr folder list ri.x -f json -o out.json", None),
        ("pltr dataset files get <rid> data.csv -", None),
        ("pltr <group> --help", None),
        ("pltr da<TAB>", None),
        ("pltr dataset", None),
        ("pltr --version", None),
        ("pltr api datasets dataset get <rid>", None),
        ("pltr folder nope", "`pltr folder nope` is not a command"),
        ("pltr folder list ri.x --nope", "has no option --nope"),
        ("pltr space delete ri.x --confirm", "option --confirm is hidden"),
        ("pltr folder get a b", "takes 1 argument, this example passes 2"),
        ("pltr dataset get [OPTIONS] DATASET_RID", None),
        ("pltr folder list ri.x [--format json]", None),
    ],
)
def test_check(tree: CommandTree, example: str, problem: Optional[str]) -> None:
    words = tuple(shlex.split(example))[1:]
    problems = check(tree, Example("x.md", 1, words), {})
    if problem is None:
        assert problems == []
    else:
        assert len(problems) == 1 and problem in problems[0], problems


def test_aliases_are_expanded(tree: CommandTree) -> None:
    text = '```bash\npltr alias add ds "dataset get"\npltr ds ri.x --format json\n```'
    examples = find_examples("x.md", text)
    aliases = _aliases(examples)
    assert aliases == {"ds": ("dataset", "get")}
    assert [check(tree, e, aliases) for e in examples] == [[], []]
