"""Recovery hints on errors (#197), triggered through real commands."""

import json
from typing import Any, Dict

import pytest
from typer.testing import CliRunner

from pltr.auth.manager import AuthSource
from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_dataset as dj
from tests import foundry_json_ontology as oj

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
    assert error["suggestedCommand"] == (
        f"pltr resource-role list {DS} --include-inherited"
    )


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
        "Foundry at test.palantirfoundry.com rejected FOUNDRY_TOKEN (invalid, "
        "expired or revoked). Set a new token."
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
        "Foundry at example.palantirfoundry.com rejected the token of profile "
        "work (invalid, expired or revoked). Store a new one."
    )
    assert error["suggestedCommand"] == (
        "pltr configure configure --profile work --auth-type token "
        "--host example.palantirfoundry.com"
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


# ------------------------------------------------ ontology names not found


ONT = oj.ONTOLOGY


def action_type(api_name: str) -> Dict[str, Any]:
    return {
        "apiName": api_name,
        "status": "ACTIVE",
        "parameters": {},
        "rid": f"ri.actions.main.action-type.{api_name.lower()}",
        "operations": [],
    }


def link_type(api_name: str) -> Dict[str, Any]:
    return {
        "apiName": api_name,
        "displayName": api_name.title(),
        "status": "ACTIVE",
        "objectTypeApiName": "Employee",
        "cardinality": "ONE",
        "linkTypeRid": f"ri.ontology.main.relation.{api_name.lower()}",
    }


def test_an_unknown_object_type_lists_the_closest_names(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        404, json=fj.error("ObjectTypeNotFound", parameters={"objectType": "Employe"})
    )
    stub_foundry_http.respond(
        json=oj.page(
            [
                oj.object_type("Employee"),
                oj.object_type("EmployeeReview"),
                oj.object_type("Department"),
            ]
        )
    )

    error = error_of("ontology", "object-type-get", ONT, "Employe")

    assert error["hint"] == (
        "Closest object type API names to 'Employe': Employee, EmployeeReview."
    )
    assert error["suggestedCommand"] == f"pltr ontology object-type-list {ONT}"
    assert stub_foundry_http.requests[1].url.path == (
        f"/api/v2/ontologies/{ONT}/objectTypes"
    )


def test_an_object_type_with_no_close_name(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        404, json=fj.error("ObjectTypeNotFound", parameters={"objectType": "Zebra"})
    )
    stub_foundry_http.respond(json=oj.page([oj.object_type("Employee")]))

    error = error_of("ontology", "object-type-get", ONT, "Zebra")

    assert error["hint"] == (
        f"No object type in {ONT} has an API name close to 'Zebra'."
    )
    assert error["suggestedCommand"] == f"pltr ontology object-type-list {ONT}"


def test_unknown_properties_list_the_closest_names(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        400,
        json=fj.error(
            "PropertiesNotFound",
            "INVALID_ARGUMENT",
            parameters={"objectType": "Employee", "properties": ["fulName", "xyz"]},
        ),
    )
    stub_foundry_http.respond(json=oj.object_type("Employee"))

    error = error_of("ontology", "object-get", ONT, "Employee", "e-1")

    assert error["hint"] == (
        "Closest property API names: 'fulName' -> fullName; 'xyz' -> none."
    )
    assert error["suggestedCommand"] == (
        f"pltr ontology object-type-get {ONT} Employee"
    )


def test_an_unknown_action_type_lists_the_closest_names(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "ActionTypeNotFound", parameters={"actionType": "promote-employe"}
        ),
    )
    stub_foundry_http.respond(
        json=oj.page([action_type("promote-employee"), action_type("fire-employee")])
    )

    error = error_of("ontology", "action-apply", ONT, "promote-employe", "{}", "--yes")

    assert error["hint"] == (
        "Closest action type API names to 'promote-employe': promote-employee, "
        "fire-employee."
    )
    assert error["suggestedCommand"] == (
        f"pltr api ontologies ontology action-type list {ONT}"
    )


def test_an_unknown_link_type_lists_the_closest_names(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        404,
        json=fj.error(
            "LinkTypeNotFound",
            parameters={"objectType": "Employee", "linkType": "Manger"},
        ),
    )
    stub_foundry_http.respond(
        json=oj.page([link_type("manager"), link_type("reports")])
    )

    error = error_of("ontology", "object-linked", ONT, "Employee", "e-1", "Manger")

    assert error["hint"] == "Closest link type API names to 'Manger': manager."
    assert error["suggestedCommand"] == (
        "pltr api ontologies ontology object-type list-outgoing-link-types "
        f"{ONT} Employee"
    )


# ------------------------------------------------------ review fixes (#197)


def test_suggestions_keep_the_profile(stub_foundry_http) -> None:
    open_transaction_conflict(stub_foundry_http)
    stub_foundry_http.respond(json=dj.branch("master", TXN))
    stub_foundry_http.respond(json=dj.transaction(TXN, status="OPEN"))

    error = error_of(
        "dataset", "transactions", "start", DS, "--branch", "master", "-p", "staging"
    )

    assert error["suggestedCommand"] == (
        f"pltr dataset transactions abort {DS} {TXN} --profile staging"
    )


def test_a_failed_path_lookup_names_the_filesystem_scope(stub_foundry_http) -> None:
    stub_foundry_http.respond(403, json=fj.error("ApiUsageDenied", "PERMISSION_DENIED"))

    error = error_of("dataset", "get", "/Space/Project/ds")

    assert "api:filesystem-read" in error["hint"]
    assert "api:datasets-read" not in error["hint"]


@pytest.mark.parametrize(
    "name", ["Default:PermissionDenied", "Compass:PermissionDenied"]
)
def test_namespaced_permission_errors_get_no_operation_hint(
    stub_foundry_http, name
) -> None:
    stub_foundry_http.respond(
        403, json=fj.error(name, "PERMISSION_DENIED", parameters={"rid": DS})
    )

    error = error_of("dataset", "get", DS)

    assert "hint" not in error


def test_hint_lookups_print_no_warnings(stub_foundry_http) -> None:
    open_transaction_conflict(stub_foundry_http)
    stub_foundry_http.respond(404, json=fj.error("BranchNotFound"))  # undecodable

    result = runner.invoke(
        app, ["dataset", "transactions", "start", DS, "--branch", "master"]
    )

    assert "Warning" not in result.stderr
    assert result.stderr.startswith("Error:")


def test_hint_lookups_have_a_timeout(stub_foundry_http) -> None:
    open_transaction_conflict(stub_foundry_http)
    stub_foundry_http.respond(json=dj.branch("master", TXN))
    stub_foundry_http.respond(json=dj.transaction(TXN, status="OPEN"))

    error_of("dataset", "transactions", "start", DS, "--branch", "master")

    for lookup in stub_foundry_http.requests[1:]:
        assert lookup.extensions["timeout"]["read"] == 10


def test_an_existing_name_in_another_case_gets_no_name_hint(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        404, json=fj.error("ObjectTypeNotFound", parameters={"objectType": "employee"})
    )
    stub_foundry_http.respond(
        json=oj.page([oj.object_type("Employee"), oj.object_type("Employees")])
    )

    error = error_of("ontology", "object-type-get", ONT, "employee")

    assert "hint" not in error


# ------------------------------------------- build targets up to date (#218)

UP_TO_DATE_HINT = (
    "Nothing to build: every target is already up to date, so no build was "
    "started. Add --force to rebuild anyway."
)


def build_targets_up_to_date(stub) -> None:
    stub.respond(400, json=fj.error("BuildTargetsUpToDate", "INVALID_ARGUMENT"))


def test_an_up_to_date_build_suggests_the_same_command_with_force(
    stub_foundry_http,
) -> None:
    stub_foundry_http.respond(
        json=fj.resource(DS, "sales", "FOUNDRY_DATASET")  # /Space/Project/sales
    )
    build_targets_up_to_date(stub_foundry_http)

    error = error_of(
        "orchestration",
        "builds",
        "create",
        "--dataset",
        "/Space/Project/sales",
        "--branch",
        "master",
        "--wait",
    )

    assert (error["type"], error["exitCode"]) == ("validation_error", 6)
    assert error["errorName"] == "BuildTargetsUpToDate"
    assert error["hint"] == UP_TO_DATE_HINT
    assert error["suggestedCommand"] == (
        "pltr orchestration builds create --dataset /Space/Project/sales "
        "--branch master --wait --format json --force"
    )


def test_the_suggestion_keeps_target_options_and_profile(stub_foundry_http) -> None:
    build_targets_up_to_date(stub_foundry_http)
    target = json.dumps({"type": "manual", "targetRids": [DS]})

    error = error_of(
        "orchestration",
        "builds",
        "create",
        target,
        "--fallback-branch",
        "develop",
        "--fallback-branch",
        "main",
        "--no-notifications",
        "--retry-count",
        "2",
        "--wait",
        "--timeout",
        "90",
        "--profile",
        "dev",
    )

    assert error["hint"] == UP_TO_DATE_HINT
    assert error["suggestedCommand"] == (
        f"pltr orchestration builds create '{target}' --fallback-branch develop "
        "--fallback-branch main --no-notifications --retry-count 2 --wait "
        "--timeout 90.0 --format json --force --profile dev"
    )


def test_the_up_to_date_hint_in_text_mode(stub_foundry_http) -> None:
    build_targets_up_to_date(stub_foundry_http)

    stderr = text_error_of("orchestration", "builds", "create", "--dataset", DS)

    assert "Add --force to rebuild anyway" in stderr
    assert f"pltr orchestration builds create --dataset {DS} --force" in stderr


def test_the_generated_command_names_its_own_flag(stub_foundry_http) -> None:
    build_targets_up_to_date(stub_foundry_http)
    target = json.dumps({"type": "manual", "targetRids": [DS]})

    error = error_of("api", "orchestration", "build", "create", "--target", target)

    assert error["hint"] == UP_TO_DATE_HINT.replace("--force", "--force-build")
    assert error["suggestedCommand"].endswith("--force-build")
    assert error["suggestedCommand"].startswith("pltr api orchestration build create")
