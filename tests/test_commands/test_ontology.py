"""Tests for `pltr ontology` against a real FoundryClient (only HTTP is faked)."""

import csv
import io
import json

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_ontology as fo

# Every endpoint except OntologyObject.count is GA: a stray preview= would
# raise a UserWarning.
pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()

API = "/api/v2/ontologies"
OBJECTS = f"{API}/{fo.ONTOLOGY}/objects/Employee"
ACTIONS = f"{API}/{fo.ONTOLOGY}/actions/transferEmployee"


def invoke(*args: str, input=None):
    return runner.invoke(app, ["ontology", *args], input=input)


def json_error(result) -> dict:
    """The structured error: the last stderr line, parsed."""
    return json.loads(result.stderr.strip().splitlines()[-1])


def stderr_json_lines(result) -> list:
    return [json.loads(line) for line in result.stderr.splitlines() if line.strip()]


def body(request) -> dict:
    return json.loads(request.content)


def csv_rows(result) -> list:
    return list(csv.DictReader(io.StringIO(result.stdout)))


# --------------------------------------------------------------- ontologies


def test_list_ontologies_table(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.ontology()]})

    result = invoke("list")

    assert result.exit_code == 0, result.output
    for expected in (fo.ONTOLOGY, "HR Ontology", fo.ONTOLOGY_RID, "People and"):
        assert expected in result.stdout
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", API)


def test_list_ontologies_json_is_the_api_response(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [fo.ontology()]})

    result = invoke("list", "--format", "json")

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"data": [fo.ontology()]}
    assert result.stderr == ""


def test_list_ontologies_csv(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [fo.ontology(), fo.ontology("ri.ontology.main.ontology.b", "b")]}
    )

    result = invoke("list", "--format", "csv")

    rows = csv_rows(result)
    assert [row["API Name"] for row in rows] == [fo.ONTOLOGY, "b"]
    assert rows[0]["RID"] == fo.ONTOLOGY_RID
    assert rows[0]["Display Name"] == "HR Ontology"


def test_list_ontologies_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403, json=fj.error("PermissionDenied", error_code="PERMISSION_DENIED")
    )

    result = invoke("list", "-f", "json")

    assert result.exit_code == 4
    assert result.stdout == ""
    assert json_error(result)["type"] == "permission_denied"


def test_get_ontology_by_api_name(stub_foundry_http):
    stub_foundry_http.respond(json=fo.ontology())

    result = invoke("get", fo.ONTOLOGY)

    assert result.exit_code == 0, result.output
    assert fo.ONTOLOGY_RID in result.stdout
    assert "HR Ontology" in result.stdout
    assert stub_foundry_http.requests[0].url.path == f"{API}/{fo.ONTOLOGY}"


def test_get_ontology_json(stub_foundry_http):
    stub_foundry_http.respond(json=fo.ontology())

    result = invoke("get", fo.ONTOLOGY_RID, "--format", "json")

    assert json.loads(result.stdout) == fo.ontology()


def test_get_ontology_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404,
        json=fj.error("OntologyNotFound", parameters={"ontologyRid": fo.ONTOLOGY_RID}),
    )

    result = invoke("get", fo.ONTOLOGY_RID, "--format", "json")

    assert result.exit_code == 5
    assert result.stdout == ""
    error = json_error(result)
    assert error["type"] == "not_found"
    assert error["errorName"] == "OntologyNotFound"
    assert error["parameters"] == {"ontologyRid": fo.ONTOLOGY_RID}


def test_get_ontology_not_found_text(stub_foundry_http):
    stub_foundry_http.respond(404, json=fj.error("OntologyNotFound"))

    result = invoke("get", fo.ONTOLOGY)

    assert result.exit_code == 5
    assert "Error: OntologyNotFound" in result.stderr
    assert "Hint:" in result.stderr


# ------------------------------------------------------------- object types


def test_object_type_list_table(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([fo.object_type()]))

    result = invoke("object-type-list", fo.ONTOLOGY)

    assert result.exit_code == 0, result.output
    for expected in ("Employee", "ACTIVE", "employeeId", fo.OBJECT_TYPE_RID):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/{fo.ONTOLOGY}/objectTypes"
    assert dict(request.url.params) == {}


def test_object_type_list_csv_reads_real_fields(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([fo.object_type()]))

    result = invoke("object-type-list", fo.ONTOLOGY, "--format", "csv")

    [row] = csv_rows(result)
    assert row == {
        "API Name": "Employee",
        "Display Name": "Employee",
        "Status": "ACTIVE",
        "Primary Key": "employeeId",
        "Properties": "3",
        "Description": "A employee of the company",
        "RID": fo.OBJECT_TYPE_RID,
    }


def test_object_type_list_json_is_the_paged_shape(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([fo.object_type()], "tok-2"))

    result = invoke("object-type-list", fo.ONTOLOGY, "-f", "json")

    assert json.loads(result.stdout) == {
        "data": [fo.object_type()],
        "nextPageToken": "tok-2",
    }


def test_object_type_list_all_pages_with_datasources(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([fo.object_type()], "tok-2"))
    stub_foundry_http.respond(json=fo.page([fo.object_type("Department")]))

    result = invoke(
        "object-type-list", fo.ONTOLOGY, "--include-datasources", "--all", "-f", "json"
    )

    document = json.loads(result.stdout)
    assert [ot["apiName"] for ot in document["data"]] == ["Employee", "Department"]
    assert "nextPageToken" not in document
    first, second = stub_foundry_http.requests
    assert dict(first.url.params) == {"includeDatasources": "true"}
    assert dict(second.url.params) == {
        "includeDatasources": "true",
        "pageToken": "tok-2",
    }


def test_object_type_list_hints_at_the_next_page(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([fo.object_type()], "tok-2"))

    result = invoke("object-type-list", fo.ONTOLOGY)

    assert "--page-token tok-2" in result.stderr


def test_object_type_get_table(stub_foundry_http):
    stub_foundry_http.respond(json=fo.object_type(datasources=True))

    result = invoke("object-type-get", fo.ONTOLOGY, "Employee", "--include-datasources")

    assert result.exit_code == 0, result.output
    for expected in (
        "Employees",  # plural display name
        "fullName",  # title property
        "employeeId (string), fullName (string), salary (double)",
        f"dataset {fo.DATASOURCE_RID}",
    ):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{API}/{fo.ONTOLOGY}/objectTypes/Employee"
    assert dict(request.url.params) == {"includeDatasources": "true"}


def test_object_type_get_csv_without_datasources(stub_foundry_http):
    stub_foundry_http.respond(json=fo.object_type())

    result = invoke("object-type-get", fo.ONTOLOGY, "Employee", "-f", "csv")

    [row] = csv_rows(result)
    assert row["Primary Key"] == "employeeId"
    assert row["Title Property"] == "fullName"
    assert row["Visibility"] == "NORMAL"
    assert row["Datasources"] == ""  # not requested


def test_object_type_get_json(stub_foundry_http):
    stub_foundry_http.respond(json=fo.object_type(datasources=True))

    result = invoke("object-type-get", fo.ONTOLOGY, "Employee", "-f", "json")

    assert json.loads(result.stdout) == fo.object_type(datasources=True)


def test_object_type_get_not_found(stub_foundry_http):
    stub_foundry_http.respond(404, json=fj.error("ObjectTypeNotFound"))

    result = invoke("object-type-get", fo.ONTOLOGY, "Nope", "-f", "json")

    assert result.exit_code == 5
    assert json_error(result)["errorName"] == "ObjectTypeNotFound"


# ----------------------------------------- object/link type create (removed)


@pytest.mark.parametrize("command", ["object-type-create", "link-type-create"])
def test_schema_create_commands_are_removed(command):
    """The Platform API can't create object or link types (#216)."""
    from pltr.manifest import build_manifest

    result = invoke(command, "--help")

    assert result.exit_code == 2
    assert "No such command" in result.output
    paths = {entry["path"] for entry in build_manifest()["commands"]}
    assert f"pltr ontology {command}" not in paths


# ------------------------------------------------------------------ objects

EMP1 = fo.employee()
EMP2 = fo.employee("EMP002", "John Roe", "Sales", 98000)


def test_object_list_table_shows_the_object_properties(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([EMP1, EMP2], totalCount="2"))

    result = invoke("object-list", fo.ONTOLOGY, "Employee")

    assert result.exit_code == 0, result.output
    for expected in ("fullName", "Jane Doe", "John Roe", "EMP002", "98000"):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("GET", OBJECTS)
    # one page of the API's default size
    assert dict(request.url.params) == {}


def test_object_list_json_is_the_paged_shape(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([EMP1], "tok-2", totalCount="2"))

    result = invoke("object-list", fo.ONTOLOGY, "Employee", "-f", "json")

    assert json.loads(result.stdout) == {"data": [EMP1], "nextPageToken": "tok-2"}


def test_object_list_csv_has_a_column_per_property(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([EMP1, EMP2], totalCount="2"))

    result = invoke("object-list", fo.ONTOLOGY, "Employee", "-f", "csv")

    rows = csv_rows(result)
    assert [row["fullName"] for row in rows] == ["Jane Doe", "John Roe"]
    assert rows[1]["__primaryKey"] == "EMP002"


def test_object_list_options(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([EMP2], totalCount="2"))

    result = invoke(
        "object-list",
        fo.ONTOLOGY,
        "Employee",
        "--properties",
        "fullName, salary",
        "--branch",
        "feature",
        "--no-derived-properties",
        "--page-size",
        "5",
        "--page-token",
        "tok-2",
    )

    assert result.exit_code == 0, result.output
    [request] = stub_foundry_http.requests
    assert list(request.url.params.multi_items()) == [
        ("branch", "feature"),
        ("loadOntologyDefinedDerivedProperties", "false"),
        ("pageSize", "5"),
        ("pageToken", "tok-2"),
        ("select", "fullName"),
        ("select", "salary"),
    ]


def test_object_list_ignores_the_page_size_setting(stub_foundry_http, isolated_home):
    # Like every paged command: --page-size, else the API's default page size.
    settings = isolated_home / ".config" / "pltr" / "settings.json"
    settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"page_size": 50}))
    stub_foundry_http.respond(json=fo.page([EMP1], totalCount="1"))

    result = invoke("object-list", fo.ONTOLOGY, "Employee")

    assert result.exit_code == 0, result.output
    assert "pageSize" not in stub_foundry_http.requests[0].url.params


def test_object_list_all_pages(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([EMP1], "tok-2", totalCount="2"))
    stub_foundry_http.respond(json=fo.page([EMP2], totalCount="2"))

    result = invoke("object-list", fo.ONTOLOGY, "Employee", "--all", "-f", "json")

    assert json.loads(result.stdout) == {"data": [EMP1, EMP2]}
    assert stub_foundry_http.requests[1].url.params["pageToken"] == "tok-2"


def test_object_list_empty(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([], totalCount="0"))

    result = invoke("object-list", fo.ONTOLOGY, "Employee")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "No results." in result.stderr


def test_object_get_table(stub_foundry_http):
    stub_foundry_http.respond(json=EMP1)

    result = invoke("object-get", fo.ONTOLOGY, "Employee", "EMP001")

    assert result.exit_code == 0, result.output
    for expected in ("fullName", "Jane Doe", "__primaryKey", "120000"):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{OBJECTS}/EMP001"
    assert dict(request.url.params) == {}


def test_object_get_json_and_options(stub_foundry_http):
    stub_foundry_http.respond(json=EMP1)

    result = invoke(
        "object-get",
        fo.ONTOLOGY,
        "Employee",
        "EMP001",
        "--properties",
        "fullName",
        "--scenario-rid",
        fo.SCENARIO_RID,
        "--transaction-id",
        "txn-1",
        "--derived-properties",
        "-b",
        "feature",
        "-f",
        "json",
    )

    assert json.loads(result.stdout) == EMP1
    assert list(stub_foundry_http.requests[0].url.params.multi_items()) == [
        ("branch", "feature"),
        ("loadOntologyDefinedDerivedProperties", "true"),
        ("scenarioRid", fo.SCENARIO_RID),
        ("select", "fullName"),
        ("transactionId", "txn-1"),
    ]


def test_object_get_not_found(stub_foundry_http):
    stub_foundry_http.respond(
        404, json=fj.error("ObjectNotFound", parameters={"primaryKey": {"id": "X"}})
    )

    result = invoke("object-get", fo.ONTOLOGY, "Employee", "X", "-f", "json")

    assert result.exit_code == 5
    error = json_error(result)
    assert error["errorName"] == "ObjectNotFound"
    assert error["parameters"] == {"primaryKey": {"id": "X"}}


# ------------------------------------------------------------ object-search

WHERE = {"type": "eq", "field": "department", "value": "Engineering"}


def test_search_sends_the_where_query(stub_foundry_http):
    stub_foundry_http.respond(json=fo.search_response([EMP1], total_count=1))

    result = invoke(
        "object-search", fo.ONTOLOGY, "Employee", "--where", json.dumps(WHERE)
    )

    assert result.exit_code == 0, result.output
    assert "Jane Doe" in result.stdout
    assert "1 of 1 matching objects." in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{OBJECTS}/search")
    assert body(request) == {"where": WHERE, "select": []}  # API's page size


def test_search_json_is_the_api_response_shape(stub_foundry_http):
    stub_foundry_http.respond(
        json=fo.search_response([EMP1], token="tok-2", total_count=7)
    )

    result = invoke("object-search", fo.ONTOLOGY, "Employee", "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [EMP1],
        "nextPageToken": "tok-2",
        "totalCount": "7",  # a Foundry Long: a string in JSON
    }
    assert result.stderr == ""


def test_search_without_where_matches_everything(stub_foundry_http):
    stub_foundry_http.respond(json=fo.search_response([]))

    result = invoke("object-search", fo.ONTOLOGY, "Employee")

    assert result.exit_code == 0
    assert body(stub_foundry_http.requests[0]) == {"select": []}
    assert "No results." in result.stderr


def test_search_all_pages_keep_the_total_count(stub_foundry_http):
    stub_foundry_http.respond(json=fo.search_response([EMP1], "tok-2", total_count=2))
    stub_foundry_http.respond(json=fo.search_response([EMP2], total_count=2))

    result = invoke(
        "object-search",
        fo.ONTOLOGY,
        "Employee",
        "--where",
        json.dumps(WHERE),
        "--all",
        "-f",
        "json",
    )

    assert json.loads(result.stdout) == {"data": [EMP1, EMP2], "totalCount": "2"}
    second = body(stub_foundry_http.requests[1])
    assert second["pageToken"] == "tok-2"  # search pages through the request body
    assert second["where"] == WHERE


def test_search_table_hints_at_the_next_page(stub_foundry_http):
    stub_foundry_http.respond(json=fo.search_response([EMP1], "tok-2", total_count=9))

    result = invoke("object-search", fo.ONTOLOGY, "Employee")

    assert "1 of 9 matching objects." in result.stderr
    assert "--page-token tok-2" in result.stderr
    assert "tok-2" not in result.stdout


def test_search_csv_has_a_row_per_object(stub_foundry_http):
    stub_foundry_http.respond(json=fo.search_response([EMP1, EMP2], "tok-2", 5))

    result = invoke("object-search", fo.ONTOLOGY, "Employee", "-f", "csv")

    assert result.exit_code == 0, result.output
    rows = csv_rows(result)
    assert [row["fullName"] for row in rows] == ["Jane Doe", "John Roe"]
    assert "totalCount" not in rows[0]
    assert "--page-token tok-2" in result.stderr


def test_search_where_from_stdin(stub_foundry_http):
    stub_foundry_http.respond(json=fo.search_response([EMP1]))

    result = invoke(
        "object-search",
        fo.ONTOLOGY,
        "Employee",
        "--where",
        "@-",
        input=json.dumps(WHERE),
    )

    assert result.exit_code == 0, result.output
    assert body(stub_foundry_http.requests[0])["where"] == WHERE


def test_search_options(stub_foundry_http, tmp_path):
    where_file = tmp_path / "where.json"
    where_file.write_text(json.dumps(WHERE))
    stub_foundry_http.respond(json=fo.search_response([EMP1]))

    result = invoke(
        "object-search",
        fo.ONTOLOGY,
        "Employee",
        "--where",
        f"@{where_file}",
        "--order-by",
        '{"fields": [{"field": "salary", "direction": "desc"}]}',
        "--properties",
        "fullName,salary",
        "--default-load-level",
        "applyReducers",
        "--no-derived-properties",
        "--branch",
        "feature",
        "--page-size",
        "3",
    )

    assert result.exit_code == 0, result.output
    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {"branch": "feature"}
    assert body(request) == {
        "where": WHERE,
        "orderBy": {"fields": [{"field": "salary", "direction": "desc"}]},
        "pageSize": 3,
        "select": ["fullName", "salary"],
        "defaultLoadLevel": {"type": "applyReducers"},
        "loadOntologyDefinedDerivedProperties": False,
    }


def test_search_snake_case_fields_are_sent_as_api_names(stub_foundry_http):
    stub_foundry_http.respond(json=fo.search_response([]))
    where = {
        "type": "eq",
        "property_identifier": {"type": "property", "apiName": "department"},
        "value": "Sales",
    }

    result = invoke(
        "object-search", fo.ONTOLOGY, "Employee", "--where", json.dumps(where)
    )

    assert result.exit_code == 0, result.output
    assert body(stub_foundry_http.requests[0])["where"] == {
        "type": "eq",
        "propertyIdentifier": {"type": "property", "apiName": "department"},
        "value": "Sales",
    }


@pytest.mark.parametrize(
    "where, expected",
    [
        ("{nope", "invalid JSON"),
        ('{"type": "eqq", "field": "a", "value": 1}', "unknown type 'eqq'"),
        ('{"type": "eqq", "field": "a", "value": 1}', "containsAnyTerm"),
        ('{"field": "a", "value": 1}', 'missing "type"'),
        (
            '{"type": "eq", "field": "a"}',
            "at value (type 'eq'): required field missing",
        ),
        (
            '{"type": "and", "value": [{"type": "eq", "field": "a", "value": 1},'
            ' {"type": "gt", "field": "b"}]}',
            "at value[1].value (type 'gt'): required field missing",
        ),
        (
            '{"type": "or", "value": [{"type": "nope"}]}',
            "at value[0]: unknown type 'nope'",
        ),
        ('[{"type": "eq", "field": "a", "value": 1}]', '{"type": "and"'),
        ('"department = Sales"', "expected a JSON object"),
    ],
)
def test_search_invalid_where_is_a_usage_error(stub_foundry_http, where, expected):
    result = invoke(
        "object-search", fo.ONTOLOGY, "Employee", "--where", where, "-f", "json"
    )

    assert result.exit_code == 2
    assert result.stdout == ""
    error = json_error(result)
    assert error["type"] == "usage_error"
    assert "'--where'" in error["message"]
    assert expected in error["message"]
    assert stub_foundry_http.requests == []


def test_search_invalid_where_text_mode(stub_foundry_http):
    result = invoke(
        "object-search", fo.ONTOLOGY, "Employee", "--where", '{"type": "eqq"}'
    )

    assert result.exit_code == 2
    assert "Invalid value for '--where'" in result.stderr
    assert "unknown type 'eqq'" in result.stderr
    assert "Example:" in result.stderr


def test_search_unknown_field_is_sent_with_a_warning(stub_foundry_http):
    stub_foundry_http.respond(json=fo.search_response([]))
    where = {"type": "eq", "feild": "department", "value": "Sales"}

    result = invoke(
        "object-search",
        fo.ONTOLOGY,
        "Employee",
        "--where",
        json.dumps(where),
        "-f",
        "json",
    )

    assert result.exit_code == 0
    [warning] = stderr_json_lines(result)
    assert warning["type"] == "warning"
    assert "unknown field 'feild'" in warning["message"]
    assert "propertyIdentifier" in warning["message"]
    assert body(stub_foundry_http.requests[0])["where"] == where


def test_search_invalid_order_by(stub_foundry_http):
    result = invoke(
        "object-search",
        fo.ONTOLOGY,
        "Employee",
        "--order-by",
        '{"orderType": "sideways", "fields": []}',
        "-f",
        "json",
    )

    assert result.exit_code == 2
    message = json_error(result)["message"]
    assert "'--order-by'" in message
    assert "at orderType" in message


def test_search_removed_query_option_explains_where(stub_foundry_http):
    result = invoke(
        "object-search", fo.ONTOLOGY, "Employee", "--query", "Jane", "-f", "json"
    )

    assert result.exit_code == 2
    message = json_error(result)["message"]
    assert "--where" in message
    assert '"value": "Jane"' in message
    assert stub_foundry_http.requests == []


def test_search_api_validation_error(stub_foundry_http):
    stub_foundry_http.respond(
        400,
        json=fj.error(
            "PropertiesNotFound", "INVALID_ARGUMENT", {"properties": ["nope"]}
        ),
    )

    result = invoke("object-search", fo.ONTOLOGY, "Employee", "--properties", "nope")

    assert result.exit_code == 6
    assert "PropertiesNotFound" in result.stderr


# --------------------------------------------------------- object-aggregate

AGGREGATION = [
    {"type": "count", "name": "employees"},
    {"type": "avg", "field": "salary", "name": "avgSalary"},
]


def aggregate(*extra: str):
    return invoke(
        "object-aggregate",
        fo.ONTOLOGY,
        "Employee",
        "--aggregation",
        json.dumps(AGGREGATION),
        *extra,
    )


def test_aggregate_table_has_a_row_per_group(stub_foundry_http):
    stub_foundry_http.respond(json=fo.aggregate_response())

    result = aggregate("--group-by", "department")

    assert result.exit_code == 0, result.output
    for expected in ("department", "employees", "avgSalary", "Engineering", "125000.5"):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{OBJECTS}/aggregate")
    assert body(request) == {
        "aggregation": AGGREGATION,
        "groupBy": [{"type": "exact", "field": "department"}],
    }


def test_aggregate_csv(stub_foundry_http):
    stub_foundry_http.respond(json=fo.aggregate_response())

    result = aggregate("--group-by", "department", "-f", "csv")

    assert csv_rows(result) == [
        {"department": "Engineering", "employees": "12", "avgSalary": "125000.5"},
        {"department": "Sales", "employees": "7", "avgSalary": "98000.0"},
    ]


def test_aggregate_json_is_the_api_response(stub_foundry_http):
    stub_foundry_http.respond(json=fo.aggregate_response())

    result = aggregate("-f", "json")

    assert json.loads(result.stdout) == fo.aggregate_response()
    assert result.stderr == ""


def test_aggregate_typed_options(stub_foundry_http):
    stub_foundry_http.respond(json=fo.aggregate_response(accuracy="APPROXIMATE"))
    group_by = [{"type": "fixedWidth", "field": "salary", "fixedWidth": 10000}]

    result = aggregate(
        "--group-by",
        json.dumps(group_by),
        "--where",
        json.dumps(WHERE),
        "--accuracy",
        "ALLOW_APPROXIMATE",
        "--branch",
        "feature",
    )

    assert result.exit_code == 0, result.output
    assert "approximate" in result.stderr
    [request] = stub_foundry_http.requests
    assert dict(request.url.params) == {"branch": "feature"}
    assert body(request) == {
        "aggregation": AGGREGATION,
        "where": WHERE,
        "groupBy": group_by,
        "accuracy": "ALLOW_APPROXIMATE",
    }


def test_aggregate_single_objects_and_group_by_shorthand(stub_foundry_http):
    stub_foundry_http.respond(json=fo.aggregate_response([]))

    result = invoke(
        "object-aggregate",
        fo.ONTOLOGY,
        "Employee",
        "--aggregation",
        '{"type": "count"}',
        "--group-by",
        "department, title",
    )

    assert result.exit_code == 0, result.output
    assert body(stub_foundry_http.requests[0]) == {
        "aggregation": [{"type": "count"}],
        "groupBy": [
            {"type": "exact", "field": "department"},
            {"type": "exact", "field": "title"},
        ],
    }


def test_aggregate_without_groups_is_one_row(stub_foundry_http):
    stub_foundry_http.respond(
        json=fo.aggregate_response(
            [{"group": {}, "metrics": [{"name": "count", "value": 19}]}]
        )
    )

    result = invoke(
        "object-aggregate",
        fo.ONTOLOGY,
        "Employee",
        "--aggregation",
        '{"type": "count"}',
    )

    assert result.exit_code == 0, result.output
    assert "19" in result.stdout
    assert body(stub_foundry_http.requests[0])["groupBy"] == []


def test_aggregate_requires_aggregation(stub_foundry_http):
    result = invoke("object-aggregate", fo.ONTOLOGY, "Employee", "-f", "json")

    assert result.exit_code == 2
    message = json_error(result)["message"]
    assert "Missing option '--aggregation'" in message
    assert '"type": "count"' in message
    assert stub_foundry_http.requests == []


@pytest.mark.parametrize(
    "aggregation, expected",
    [
        ('[{"type": "median", "field": "x"}]', "at [0]: unknown type 'median'"),
        ('[{"type": "median", "field": "x"}]', "approximatePercentile"),
        (
            '[{"type": "count"}, {"type": "approximatePercentile", "field": "x"}]',
            "at [1].approximatePercentile (type 'approximatePercentile'): "
            "required field missing",
        ),
        ('{"count": "count"}', 'at [0]: missing "type"'),
        ("[]", "give at least one aggregation"),
        ('"count"', "expected a JSON list"),
    ],
)
def test_aggregate_invalid_aggregation(stub_foundry_http, aggregation, expected):
    result = invoke(
        "object-aggregate",
        fo.ONTOLOGY,
        "Employee",
        "--aggregation",
        aggregation,
        "-f",
        "json",
    )

    assert result.exit_code == 2
    error = json_error(result)
    assert error["type"] == "usage_error"
    assert "'--aggregation'" in error["message"]
    assert expected in error["message"]
    assert stub_foundry_http.requests == []


def test_aggregate_invalid_group_by(stub_foundry_http):
    result = aggregate(
        "--group-by", '[{"type": "fixedWidth", "field": "age"}]', "-f", "json"
    )

    assert result.exit_code == 2
    message = json_error(result)["message"]
    assert "'--group-by'" in message
    assert "at [0].fixedWidth (type 'fixedWidth'): required field missing" in message


def test_aggregate_deprecated_positional_aggregations(stub_foundry_http):
    stub_foundry_http.respond(json=fo.aggregate_response([]))

    result = invoke(
        "object-aggregate",
        fo.ONTOLOGY,
        "Employee",
        json.dumps(AGGREGATION),
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    [warning] = stderr_json_lines(result)
    assert "deprecated" in warning["message"] and "--aggregation" in warning["message"]
    assert body(stub_foundry_http.requests[0])["aggregation"] == AGGREGATION


def test_aggregate_positional_and_option_together_is_a_usage_error(stub_foundry_http):
    result = aggregate(json.dumps(AGGREGATION))

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_aggregate_deprecated_filter_alias(stub_foundry_http):
    stub_foundry_http.respond(json=fo.aggregate_response([]))

    result = aggregate("--filter", json.dumps(WHERE))

    assert result.exit_code == 0, result.output
    assert "--filter is deprecated" in result.stderr
    assert body(stub_foundry_http.requests[0])["where"] == WHERE


def test_aggregate_filter_and_where_together_is_a_usage_error(stub_foundry_http):
    result = aggregate("--filter", json.dumps(WHERE), "--where", json.dumps(WHERE))

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_aggregate_help_hides_the_deprecated_inputs():
    result = invoke("object-aggregate", "--help")

    assert result.exit_code == 0
    assert "AGGREGATIONS" not in result.stdout
    assert "--filter" not in result.stdout
    assert '"type": "fixedWidth"' in result.stdout  # an example


# ------------------------------------------------------------- object-count


def test_count_calls_the_beta_endpoint_with_preview(stub_foundry_http):
    stub_foundry_http.respond(json=fo.count_response(42))

    result = invoke("object-count", fo.ONTOLOGY, "Employee", "--branch", "feature")

    assert result.exit_code == 0, result.output
    assert "42" in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{OBJECTS}/count")
    assert dict(request.url.params) == {"branch": "feature", "preview": "true"}


def test_count_json_and_csv(stub_foundry_http):
    stub_foundry_http.respond(json=fo.count_response(42))
    stub_foundry_http.respond(json=fo.count_response(42))

    as_json = invoke("object-count", fo.ONTOLOGY, "Employee", "-f", "json")
    as_csv = invoke("object-count", fo.ONTOLOGY, "Employee", "-f", "csv")

    assert json.loads(as_json.stdout) == {"count": 42}
    assert csv_rows(as_csv) == [{"Count": "42"}]


def test_count_is_labeled_beta():
    result = invoke("object-count", "--help")

    assert "[beta]" in result.stdout


# ------------------------------------------------------------ object-linked


def test_linked_objects(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([EMP2], "tok-2"))

    result = invoke("object-linked", fo.ONTOLOGY, "Employee", "EMP001", "manages")

    assert result.exit_code == 0, result.output
    assert "John Roe" in result.stdout
    assert "--page-token tok-2" in result.stderr
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{OBJECTS}/EMP001/links/manages"
    assert dict(request.url.params) == {}


def test_linked_objects_json_all_pages(stub_foundry_http):
    stub_foundry_http.respond(json=fo.page([EMP1], "tok-2"))
    stub_foundry_http.respond(json=fo.page([EMP2]))

    result = invoke(
        "object-linked",
        fo.ONTOLOGY,
        "Employee",
        "EMP001",
        "manages",
        "--properties",
        "fullName",
        "--all",
        "-f",
        "json",
    )

    assert json.loads(result.stdout) == {"data": [EMP1, EMP2]}
    second = stub_foundry_http.requests[1]
    assert list(second.url.params.multi_items()) == [
        ("pageToken", "tok-2"),
        ("select", "fullName"),
    ]


def test_linked_objects_link_type_not_found(stub_foundry_http):
    stub_foundry_http.respond(404, json=fj.error("LinkTypeNotFound"))

    result = invoke(
        "object-linked", fo.ONTOLOGY, "Employee", "EMP001", "nope", "-f", "json"
    )

    assert result.exit_code == 5
    assert json_error(result)["errorName"] == "LinkTypeNotFound"


# ------------------------------------------------------------------ actions

PARAMETERS = {"employee": "EMP001", "newDepartment": "Sales"}


def test_action_apply(stub_foundry_http):
    stub_foundry_http.respond(json=fo.apply_response())

    result = invoke(
        "action-apply", fo.ONTOLOGY, "transferEmployee", json.dumps(PARAMETERS)
    )

    assert result.exit_code == 0, result.output
    assert fo.OPERATION_ID in result.stdout
    assert "VALID" in result.stdout
    assert "Applied action transferEmployee" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{ACTIONS}/apply")
    assert body(request) == {"parameters": PARAMETERS}


def test_action_apply_returns_edits(stub_foundry_http, tmp_path):
    parameters_file = tmp_path / "params.json"
    parameters_file.write_text(json.dumps(PARAMETERS))
    stub_foundry_http.respond(json=fo.apply_response(edits=fo.object_edits(1)))

    result = invoke(
        "action-apply",
        fo.ONTOLOGY,
        "transferEmployee",
        f"@{parameters_file}",
        "--return-edits",
        "ALL",
        "--attribution",
        "pltr-tests",
        "--scenario-rid",
        fo.SCENARIO_RID,
        "-f",
        "csv",
    )

    assert result.exit_code == 0, result.output
    [row] = csv_rows(result)
    assert row == {
        "Operation ID": fo.OPERATION_ID,
        "Validation": "VALID",
        "Edits": "0 added, 1 modified, 0 deleted objects; 0 added, 0 deleted links",
    }
    [request] = stub_foundry_http.requests
    assert body(request) == {
        "parameters": PARAMETERS,
        "options": {"returnEdits": "ALL"},
    }
    assert dict(request.url.params) == {"scenarioRid": fo.SCENARIO_RID}
    assert request.headers["attribution"] == "pltr-tests"


def test_action_apply_json_is_the_api_response(stub_foundry_http):
    response = fo.apply_response(edits=fo.object_edits(2))
    stub_foundry_http.respond(json=response)

    result = invoke(
        "action-apply",
        fo.ONTOLOGY,
        "transferEmployee",
        json.dumps(PARAMETERS),
        "-f",
        "json",
    )

    assert json.loads(result.stdout) == response
    assert result.stderr == ""


def test_action_apply_large_scale_edits(stub_foundry_http):
    stub_foundry_http.respond(
        json=fo.apply_response(
            edits={"type": "largeScaleEdits", "editedObjectTypes": ["Employee"]}
        )
    )

    result = invoke(
        "action-apply",
        fo.ONTOLOGY,
        "transferEmployee",
        json.dumps(PARAMETERS),
        "-f",
        "csv",
    )

    assert csv_rows(result)[0]["Edits"] == "large-scale edits to Employee"


@pytest.mark.parametrize(
    "parameters, expected",
    [
        ("not json", "invalid JSON"),
        ('["EMP001"]', "expected a JSON object mapping parameter IDs to values"),
    ],
)
def test_action_apply_invalid_parameters(stub_foundry_http, parameters, expected):
    result = invoke(
        "action-apply", fo.ONTOLOGY, "transferEmployee", parameters, "-f", "json"
    )

    assert result.exit_code == 2
    error = json_error(result)
    assert error["type"] == "usage_error"
    assert expected in error["message"]
    assert stub_foundry_http.requests == []


def test_action_apply_rejected_by_foundry(stub_foundry_http):
    stub_foundry_http.respond(
        400,
        json=fj.error(
            "ActionValidationFailed", "INVALID_ARGUMENT", {"actionType": "x"}
        ),
    )

    result = invoke(
        "action-apply",
        fo.ONTOLOGY,
        "transferEmployee",
        json.dumps(PARAMETERS),
        "-f",
        "json",
    )

    assert result.exit_code == 6
    assert result.stdout == ""
    assert json_error(result)["errorName"] == "ActionValidationFailed"


def test_action_apply_invalid_validation_result_fails(stub_foundry_http):
    # "a 200 HTTP status code only indicates that the request was received":
    # an INVALID validation result means nothing was applied.
    stub_foundry_http.respond(
        json={
            "operationId": fo.OPERATION_ID,
            "validation": fo.validation("INVALID", invalid_parameter="employee"),
        }
    )

    result = invoke(
        "action-apply",
        fo.ONTOLOGY,
        "transferEmployee",
        json.dumps(PARAMETERS),
        "-f",
        "json",
    )

    assert result.exit_code == 6
    assert result.stdout == ""
    error = json_error(result)
    assert error["type"] == "validation_error"
    assert "was not applied" in error["message"]
    assert "invalid parameters: employee" in error["message"]


def test_action_validate_valid(stub_foundry_http):
    stub_foundry_http.respond(json=fo.validate_response("VALID"))

    result = invoke(
        "action-validate", fo.ONTOLOGY, "transferEmployee", json.dumps(PARAMETERS)
    )

    assert result.exit_code == 0, result.output
    assert "VALID" in result.stdout
    assert "employee=VALID" in result.stdout
    assert "The parameters are valid" in result.stderr
    [request] = stub_foundry_http.requests
    assert request.url.path == f"{ACTIONS}/apply"
    assert body(request) == {
        "parameters": PARAMETERS,
        "options": {"mode": "VALIDATE_ONLY"},
    }


def test_action_validate_invalid_is_reported_not_failed(stub_foundry_http):
    response = fo.validate_response("INVALID")  # a submission criterion failed
    stub_foundry_http.respond(json=response)

    result = invoke(
        "action-validate",
        fo.ONTOLOGY,
        "transferEmployee",
        json.dumps(PARAMETERS),
        "-f",
        "json",
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == response
    [warning] = stderr_json_lines(result)
    assert warning["type"] == "warning"
    assert "INVALID" in warning["message"]
    assert "Only managers may do this" in warning["message"]


def test_action_validate_csv(stub_foundry_http):
    stub_foundry_http.respond(
        json=fo.validate_response("INVALID", invalid_parameter="employee")
    )

    result = invoke(
        "action-validate",
        fo.ONTOLOGY,
        "transferEmployee",
        json.dumps(PARAMETERS),
        "-f",
        "csv",
    )

    [row] = csv_rows(result)
    assert row == {
        "Result": "INVALID",
        "Submission Criteria": "VALID",
        "Parameters": "employee=INVALID, newDepartment=VALID",
    }


BATCH = [
    {"parameters": {"employee": "EMP001", "newDepartment": "Sales"}},
    {"parameters": {"employee": "EMP002", "newDepartment": "Sales"}},
]


def test_action_apply_batch(stub_foundry_http):
    stub_foundry_http.respond(json=fo.batch_response(fo.object_edits(2)))

    result = invoke(
        "action-apply-batch",
        fo.ONTOLOGY,
        "transferEmployee",
        json.dumps(BATCH),
        "--return-edits",
        "ALL",
        "--scenario-rid",
        fo.SCENARIO_RID,
    )

    assert result.exit_code == 0, result.output
    assert "2 modified" in result.stdout
    assert "Applied 2 transferEmployee actions" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", f"{ACTIONS}/applyBatch")
    assert dict(request.url.params) == {"scenarioRid": fo.SCENARIO_RID}
    assert body(request) == {"requests": BATCH, "options": {"returnEdits": "ALL"}}


def test_action_apply_batch_json(stub_foundry_http):
    stub_foundry_http.respond(json=fo.batch_response())

    result = invoke(
        "action-apply-batch",
        fo.ONTOLOGY,
        "transferEmployee",
        json.dumps(BATCH),
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {}


@pytest.mark.parametrize(
    "requests, expected",
    [
        ('[{"employee": "EMP001"}]', "at [0].parameters: required field missing"),
        ('{"parameters": {}}', "expected a JSON list"),
        ("[]", "give at least one request"),
    ],
)
def test_action_apply_batch_invalid_requests(stub_foundry_http, requests, expected):
    result = invoke(
        "action-apply-batch", fo.ONTOLOGY, "transferEmployee", requests, "-f", "json"
    )

    assert result.exit_code == 2
    message = json_error(result)["message"]
    assert "REQUESTS" in message
    assert expected in message
    assert stub_foundry_http.requests == []


# ------------------------------------------------------------------ queries


def test_query_execute_list_result_is_one_row_per_item(stub_foundry_http):
    value = [
        {"employeeId": "EMP001", "hours": 45},
        {"employeeId": "EMP002", "hours": 50},
    ]
    stub_foundry_http.respond(json=fo.query_response(value))

    result = invoke(
        "query-execute",
        fo.ONTOLOGY,
        "overallocatedEmployees",
        "--parameters",
        '{"threshold": 40}',
        "-f",
        "csv",
    )

    assert result.exit_code == 0, result.output
    assert csv_rows(result) == [
        {"employeeId": "EMP001", "hours": "45"},
        {"employeeId": "EMP002", "hours": "50"},
    ]
    [request] = stub_foundry_http.requests
    assert (
        request.url.path
        == f"{API}/{fo.ONTOLOGY}/queries/overallocatedEmployees/execute"
    )
    assert body(request) == {"parameters": {"threshold": 40}}


def test_query_execute_json_is_the_api_response(stub_foundry_http):
    stub_foundry_http.respond(json=fo.query_response({"total": 3}))

    result = invoke("query-execute", fo.ONTOLOGY, "headCount", "-f", "json")

    assert json.loads(result.stdout) == {"value": {"total": 3}}
    assert body(stub_foundry_http.requests[0]) == {"parameters": {}}


def test_query_execute_scalar_result(stub_foundry_http):
    stub_foundry_http.respond(json=fo.query_response(19))

    result = invoke("query-execute", fo.ONTOLOGY, "headCount")

    assert result.exit_code == 0, result.output
    assert "Value" in result.stdout
    assert "19" in result.stdout


def test_query_execute_invalid_parameters(stub_foundry_http):
    result = invoke("query-execute", fo.ONTOLOGY, "headCount", "--parameters", "[1]")

    assert result.exit_code == 2
    assert "Invalid value for '--parameters'" in result.stderr
    assert stub_foundry_http.requests == []


def test_query_not_found(stub_foundry_http):
    stub_foundry_http.respond(404, json=fj.error("QueryNotFound"))

    result = invoke("query-execute", fo.ONTOLOGY, "nope", "-f", "json")

    assert result.exit_code == 5
    assert json_error(result)["errorName"] == "QueryNotFound"
