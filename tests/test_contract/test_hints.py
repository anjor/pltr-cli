"""Recovery hints on errors (#197), triggered through real commands."""

import json
from typing import Any, Dict

import pytest
from typer.testing import CliRunner

from pltr.auth.manager import AuthSource
from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_dataset as dj

pytestmark = pytest.mark.usefixtures("isolated_home")

runner = CliRunner()

DS = dj.DATASET_RID
TXN = dj.TRANSACTION_RID


def error_of(*args: str) -> Dict[str, Any]:
    result = runner.invoke(app, [*args, "--format", "json"])
    assert result.exit_code != 0, result.stdout
    assert result.stdout == ""
    return json.loads(result.stderr.strip().splitlines()[-1])


def text_error_of(*args: str) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code != 0
    return result.stderr


# ------------------------------------------------------- open transaction


def open_transaction_conflict(stub) -> None:
    stub.respond(
        409,
        json=fj.error(
            "OpenTransactionAlreadyExists",
            "CONFLICT",
            parameters={"datasetRid": DS, "branchName": "master"},
        ),
    )


def test_an_open_transaction_is_named_with_the_command_to_abort_it(
    stub_foundry_http,
) -> None:
    open_transaction_conflict(stub_foundry_http)
    stub_foundry_http.respond(json=dj.branch("master", TXN))
    stub_foundry_http.respond(json=dj.transaction(TXN, status="OPEN"))

    error = error_of("dataset", "transactions", "start", DS, "--branch", "master")

    assert error["type"] == "conflict"
    assert error["hint"] == (
        f"Branch master of {DS} already has an open transaction, {TXN}: "
        "commit it or abort it first."
    )
    assert error["suggestedCommand"] == f"pltr dataset transactions abort {DS} {TXN}"
    lookups = [r.url.path for r in stub_foundry_http.requests[1:]]
    assert lookups == [
        f"/api/v2/datasets/{DS}/branches/master",
        f"/api/v2/datasets/{DS}/transactions/{TXN}",
    ]


def test_an_open_transaction_that_cant_be_found_suggests_listing(
    stub_foundry_http,
) -> None:
    open_transaction_conflict(stub_foundry_http)
    stub_foundry_http.respond(404, json=fj.error("BranchNotFound"))

    error = error_of("dataset", "transactions", "start", DS, "--branch", "master")

    assert error["hint"] == (
        f"Branch master of {DS} already has an open transaction: "
        "commit it or abort it first."
    )
    assert error["suggestedCommand"] == (
        f"pltr dataset transactions list {DS} --branch master"
    )


def test_hints_show_in_text_mode(stub_foundry_http) -> None:
    open_transaction_conflict(stub_foundry_http)
    stub_foundry_http.respond(json=dj.branch("master", TXN))
    stub_foundry_http.respond(json=dj.transaction(TXN, status="OPEN"))

    stderr = text_error_of("dataset", "transactions", "start", DS, "--branch", "master")

    assert f"Hint: Branch master of {DS} already has an open transaction" in stderr
    assert f"Try: pltr dataset transactions abort {DS} {TXN}" in stderr


# ----------------------------------------------------------- missing scope


def test_a_missing_scope_named_by_the_api_is_in_the_hint(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "ApiUsageDenied",
            "PERMISSION_DENIED",
            parameters={"missingScope": "api:datasets-read"},
        ),
    )

    error = error_of("dataset", "get", DS)

    assert error["type"] == "permission_denied"
    assert error["hint"] == (
        "The token or OAuth client lacks the scope api:datasets-read. Grant it "
        "to the OAuth client in Developer Console, or use a token that has it."
    )
    assert "suggestedCommand" not in error


def test_without_a_named_scope_the_commands_scopes_are_listed(
    stub_foundry_http,
) -> None:
    stub_foundry_http.respond(403, json=fj.error("ApiUsageDenied", "PERMISSION_DENIED"))

    error = error_of("dataset", "get", DS)

    assert error["hint"] == (
        "This command needs the scope api:datasets-read, which the token or OAuth "
        "client may lack. Grant it to the OAuth client in Developer Console, or "
        "use a token that has it."
    )


def test_generated_commands_list_their_scopes_too(stub_foundry_http) -> None:
    stub_foundry_http.respond(403, json=fj.error("ApiUsageDenied", "PERMISSION_DENIED"))

    error = error_of("api", "datasets", "dataset", "get", DS)

    assert "api:datasets-read" in error["hint"]


# ------------------------------------------------------- permission denied


def test_permission_denied_names_the_operation_and_the_resource(
    stub_foundry_http,
) -> None:
    stub_foundry_http.respond(
        403,
        json=fj.error(
            "AbortTransactionPermissionDenied",
            "PERMISSION_DENIED",
            parameters={"datasetRid": DS, "transactionRid": TXN},
        ),
    )

    error = error_of("dataset", "transactions", "abort", DS, TXN, "--yes")

    assert error["hint"] == (
        f"Your account isn't allowed to abort transaction on {DS}. Ask someone "
        "who manages it for a role that allows this."
    )
    assert error["suggestedCommand"] == f"pltr resource-role list {DS}"


def test_permission_denied_without_a_rid_has_no_specific_hint(
    stub_foundry_http,
) -> None:
    stub_foundry_http.respond(
        403, json=fj.error("SomethingPermissionDenied", "PERMISSION_DENIED")
    )

    error = error_of("dataset", "get", DS)

    assert "hint" not in error
    assert "suggestedCommand" not in error


# ---------------------------------------------------------- rejected token


def unauthorized(stub) -> None:
    stub.respond(401, json=fj.error("MissingCredentials", "UNAUTHORIZED"))


def test_a_rejected_environment_token(stub_foundry_http) -> None:
    unauthorized(stub_foundry_http)

    error = error_of("dataset", "get", DS)

    assert error["type"] == "auth_error"
    assert error["hint"] == (
        "Foundry rejected FOUNDRY_TOKEN: it has expired or been revoked. "
        "Set a new token."
    )
    assert error["suggestedCommand"] == "export FOUNDRY_TOKEN=<new-token>"


def test_a_rejected_profile_token(stub_foundry_http) -> None:
    from pltr.services import base

    context = base.AuthManager.return_value.get_auth_context.return_value
    context.source = AuthSource(
        kind="profile",
        profile="work",
        selected_by="--profile",
        auth_type="token",
        host="example.palantirfoundry.com",
    )
    unauthorized(stub_foundry_http)

    error = error_of("dataset", "get", DS, "--profile", "work")

    assert error["hint"] == (
        "Foundry rejected the token of profile work: it has expired or been "
        "revoked. Store a new one."
    )
    assert error["suggestedCommand"] == (
        "pltr configure configure --profile work --auth-type token "
        "--host example.palantirfoundry.com --token <new-token>"
    )
    base.AuthManager.return_value.get_auth_context.assert_called_with("work")


def test_a_rejected_oauth_token_keeps_the_generic_hint(stub_foundry_http) -> None:
    from pltr.services import base

    context = base.AuthManager.return_value.get_auth_context.return_value
    context.source = AuthSource(kind="profile", profile="ci", auth_type="oauth")
    unauthorized(stub_foundry_http)

    error = error_of("dataset", "get", DS)

    assert "hint" not in error


# -------------------------------------------------------- best effort


def test_a_failing_provider_leaves_the_error_unchanged(
    stub_foundry_http, monkeypatch
) -> None:
    from pltr.services import base

    base.AuthManager.return_value.get_auth_context.side_effect = RuntimeError("boom")
    unauthorized(stub_foundry_http)

    error = error_of("dataset", "get", DS)

    assert error["type"] == "auth_error"
    assert "hint" not in error
