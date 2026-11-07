"""The CLI-wide output/error contract (#187), checked for every command.

For every command that calls the Foundry API (everything not in a case
module's ``LOCAL``), the test synthesizes the required arguments, adds
``--format json`` (and ``--yes`` when the command has it) and runs it against
``stub_foundry_http`` answering every request with

* a Foundry 404 error body: exit code 5, and
* a Foundry 400 error body: exit code 6,

checking that stdout is empty, that stderr is JSON Lines only and that its
last line is the structured error with the Foundry ``errorName``. Converted
commands must also pass a success-path run from their ``SUCCESS`` case: exit
code 0, stdout exactly one JSON document, no error on stderr.

Commands in a case module's ``NOT_CONVERTED`` set are run too, and the test
fails as soon as one of them passes, so the set can only shrink. See
``tests/test_contract/cases/__init__.py`` and
``docs/development/command-contract.md``.
"""

import inspect
import json
from typing import Any, List

import click
import pytest
import typer
from click.testing import CliRunner
from foundry_sdk import FoundryClient, UserTokenAuth

from pltr.cli import app
from pltr.contract import FORMAT_ENVVAR, FORMATS, iter_commands
from tests.test_contract.cases import CONTRACT_RID, load_cases

ROOT = typer.main.get_command(app)
ENTRIES = {entry.path: entry for entry in iter_commands(ROOT)}
CASES = load_cases()
API_COMMANDS = sorted(path for path in ENTRIES if path not in CASES.local)
CONVERTED = [path for path in API_COMMANDS if path not in CASES.not_converted]


def _success_exempt(path: str) -> bool:
    return any(
        path == prefix or path.startswith(prefix + " ")
        for prefix in CASES.success_exempt
    )


NEEDS_SUCCESS = [
    path for path in CONVERTED if path in CASES.success or not _success_exempt(path)
]

ERROR_INSTANCE_ID = "00000000-0000-4000-8000-00000000c0de"
SCENARIOS = [
    # status, errorCode, errorName, expected type, expected exit code
    (404, "NOT_FOUND", "ContractTestNotFound", "not_found", 5),
    (400, "INVALID_ARGUMENT", "ContractTestInvalidArgument", "validation_error", 6),
]

runner = CliRunner()


# ------------------------------------------------------------------ helpers


def _sample_value(param: click.Parameter, tmp_path) -> str:
    """A plausible value for a required parameter."""
    param_type = param.type
    if isinstance(param_type, click.Choice):
        return str(param_type.choices[0])
    if isinstance(param_type, (click.Path, click.File)):
        path = tmp_path / f"contract-{param.name}.json"
        path.write_text("{}")
        return str(path)
    if isinstance(param_type, click.types.IntParamType):
        return "1"
    if isinstance(param_type, click.types.FloatParamType):
        return "1.0"
    if isinstance(param_type, click.types.BoolParamType):
        return "true"
    if isinstance(param_type, click.DateTime):
        return "2024-01-01"
    if isinstance(param_type, click.types.UUIDParameterType):
        return "00000000-0000-4000-8000-000000000001"
    name = (param.name or "").lower()
    if name.endswith(("rid", "rids")) or "RID" in (getattr(param, "help", "") or ""):
        return CONTRACT_RID
    return "contract-test"


def synthesize_args(path: str, command: click.Command, tmp_path) -> List[str]:
    """Required arguments for a command (or its ``ARGS`` case)."""
    if path in CASES.args:
        return list(CASES.args[path])
    positional: List[str] = []
    options: List[str] = []
    for param in command.params:
        if not param.required:
            continue
        if isinstance(param, click.Argument):
            count = param.nargs if param.nargs > 0 else 1
            positional.extend(_sample_value(param, tmp_path) for _ in range(count))
        elif isinstance(param, click.Option) and not param.is_flag:
            count = param.nargs if param.nargs > 0 else 1
            options.append(param.opts[0])
            options.extend(_sample_value(param, tmp_path) for _ in range(count))
    return positional + options


def option_names(command: click.Command) -> set:
    return {
        opt
        for param in command.params
        if isinstance(param, click.Option)
        for opt in param.opts
    }


def contract_args(path: str, tmp_path) -> List[str]:
    command = ENTRIES[path].command
    args = path.split() + synthesize_args(path, command, tmp_path)
    args += ["--format", "json"]
    if "--yes" in option_names(command):
        args.append("--yes")
    return args


def stderr_json_lines(result) -> List[Any]:
    """Parse stderr as JSON Lines; raises ValueError on a non-JSON line."""
    lines = []
    for line in result.stderr.splitlines():
        if line.strip():
            try:
                lines.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"non-JSON stderr line: {line!r}") from exc
    return lines


def error_problems(result, status, error_name, error_type, exit_code) -> List[str]:
    if result.exit_code != exit_code:
        detail = result.stderr.strip().splitlines()[-1:] or [repr(result.exception)]
        return [f"exit code {result.exit_code}, expected {exit_code}: {detail[0]}"]
    problems = []
    if result.stdout:
        problems.append(f"stdout is not empty: {result.stdout[:200]!r}")
    try:
        lines = stderr_json_lines(result)
    except ValueError as exc:
        return problems + [str(exc)]
    if not lines:
        return problems + ["no structured error on stderr"]
    error = lines[-1]
    expected = {
        "type": error_type,
        "exitCode": exit_code,
        "statusCode": status,
        "errorName": error_name,
        "errorInstanceId": ERROR_INSTANCE_ID,
    }
    for key, value in expected.items():
        if not isinstance(error, dict) or error.get(key) != value:
            got = error.get(key) if isinstance(error, dict) else error
            problems.append(f"error {key} is {got!r}, expected {value!r}")
    return problems


@pytest.fixture
def contract_env(stub_foundry_http, isolated_home, mock_keyring, monkeypatch):
    """No network, no real home directory, no keyring, no real sleeping."""
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    return stub_foundry_http


def run_error_scenarios(path: str, stub, tmp_path) -> List[str]:
    problems = []
    for status, code, name, error_type, exit_code in SCENARIOS:
        stub.requests.clear()
        stub.respond_always(
            status,
            json={
                "errorCode": code,
                "errorName": name,
                "errorInstanceId": ERROR_INSTANCE_ID,
                "parameters": {},
            },
        )
        result = runner.invoke(ROOT, contract_args(path, tmp_path))
        problems += [
            f"[{status}] {problem}"
            for problem in error_problems(result, status, name, error_type, exit_code)
        ]
    return problems


# -------------------------------------------------------------------- tests


@pytest.mark.parametrize("path", API_COMMANDS)
def test_api_errors_are_structured(path, contract_env, tmp_path):
    """404 -> exit 5 and 400 -> exit 6, with the structured error on stderr."""
    problems = run_error_scenarios(path, contract_env, tmp_path)
    if path in CASES.not_converted:
        if not problems:
            pytest.fail(
                f"'{path}' now follows the error contract: delete it from "
                "NOT_CONVERTED in tests/test_contract/cases/ (and add a SUCCESS case)."
            )
        return
    assert not problems, f"'{path}' breaks the error contract:\n" + "\n".join(problems)


@pytest.mark.parametrize("path", NEEDS_SUCCESS)
def test_success_prints_exactly_one_json_document(path, contract_env, tmp_path):
    assert path in CASES.success, (
        f"'{path}' is converted but has no SUCCESS case in tests/test_contract/cases/"
    )
    for response in CASES.success[path]:
        contract_env.respond(**response)

    result = runner.invoke(ROOT, contract_args(path, tmp_path))

    assert result.exit_code == 0, result.stderr or repr(result.exception)
    json.loads(result.stdout)  # exactly one JSON document
    lines = stderr_json_lines(result)
    assert all(line.get("type") == "warning" for line in lines), lines


def test_success_exempt_matches_whole_path_segments(monkeypatch):
    monkeypatch.setitem(CASES.success_exempt, "folder", "test")
    assert _success_exempt("folder") and _success_exempt("folder get")
    assert not _success_exempt("folders get") and not _success_exempt("space get")


def test_case_modules_name_real_commands():
    named = set(CASES.not_converted) | set(CASES.local) | set(CASES.success)
    named |= set(CASES.args)
    stale_prefixes = [
        prefix
        for prefix in CASES.success_exempt
        if not any(p == prefix or p.startswith(prefix + " ") for p in ENTRIES)
    ]
    assert not stale_prefixes, (
        f"SUCCESS_EXEMPT prefixes matching no command: {stale_prefixes}"
    )
    stale = sorted(path for path in named if path not in ENTRIES)
    assert not stale, f"case entries for commands that don't exist: {stale}"
    assert not CASES.duplicates, CASES.duplicates
    assert not set(CASES.local) & CASES.not_converted


def test_converted_commands_declare_metadata_and_shared_options():
    for path in CONVERTED:
        entry = ENTRIES[path]
        assert entry.meta is not None, f"'{path}' has no @pltr_command metadata"
        assert entry.meta.sdk or entry.meta.http, f"'{path}' declares no SDK method"
        format_option = next(
            param
            for param in entry.command.params
            if isinstance(param, click.Option) and "--format" in param.opts
        )
        assert format_option.envvar == FORMAT_ENVVAR, path
        assert tuple(format_option.type.choices) == FORMATS, path  # type: ignore[attr-defined]


def test_no_command_declares_an_option_string_twice():
    """E.g. the shared --profile/-p next to an existing --parent-folder/-p."""
    for path, entry in ENTRIES.items():
        seen: dict = {}
        for param in entry.command.params:
            if not isinstance(param, click.Option):
                continue
            for opt in param.opts + param.secondary_opts:
                assert opt not in seen, (
                    f"'{path}': {opt} is declared by both {seen[opt]} and "
                    f"{param.name}; use a factory with short=False"
                )
                seen[opt] = param.name


def test_destructive_commands_have_yes():
    for path, entry in ENTRIES.items():
        if entry.meta and entry.meta.destructive:
            assert "--yes" in option_names(entry.command), f"'{path}' lacks --yes"


def test_paged_commands_have_paging_options():
    for path, entry in ENTRIES.items():
        if entry.meta and entry.meta.paged:
            missing = {"--page-size", "--page-token"} - option_names(entry.command)
            assert not missing, f"'{path}' lacks {sorted(missing)}"


def test_beta_commands_are_labeled():
    for path, entry in ENTRIES.items():
        if entry.meta and entry.meta.beta:
            assert (entry.command.help or "").startswith("[beta]"), path


def _resolve_sdk_method(client: Any, dotted: str) -> Any:
    target = client
    for part in dotted.split("."):
        target = getattr(target, part)
    return target


def test_sdk_metadata_matches_the_sdk():
    """Every recorded SDK method exists, and beta == has a `preview` parameter."""
    client = FoundryClient(auth=UserTokenAuth(token="x"), hostname="example.com")
    for path, entry in ENTRIES.items():
        if not entry.meta or not entry.meta.sdk:
            continue
        beta_methods = []
        for dotted in entry.meta.sdk:
            try:
                method = _resolve_sdk_method(client, dotted)
            except AttributeError:
                pytest.fail(f"'{path}': FoundryClient has no {dotted}")
            assert callable(method), f"'{path}': {dotted} is not callable"
            if "preview" in inspect.signature(method).parameters:
                beta_methods.append(dotted)
        assert entry.meta.beta == bool(beta_methods), (
            f"'{path}': beta={entry.meta.beta} but beta SDK methods are {beta_methods}"
        )
