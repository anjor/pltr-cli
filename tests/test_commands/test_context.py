"""`pltr context`: compact summaries of a dataset, folder or ontology (#194)."""

import json
from typing import Any, Dict, List

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json as fj
from tests import foundry_json_dataset as dj
from tests import foundry_json_orchestration as orj
from tests import foundry_json_ontology as oj

pytestmark = pytest.mark.usefixtures("isolated_home")

runner = CliRunner()

DS = dj.DATASET_RID
SCHEDULE = orj.SCHEDULE_RID
JOB = orj.JOB_RID

#: Documented cap of a default dataset context (README / skill).
MAX_DATASET_CONTEXT_BYTES = 16_000


def dataset_responses(
    stub, fields: List[Dict[str, Any]], rows: Dict[str, list]
) -> None:
    stub.respond(
        json={
            **fj.resource(DS, "sales", "FOUNDRY_DATASET"),
            "path": "/Space/Project/sales",
        }
    )
    stub.respond(json=dj.schema_response(fields))
    stub.respond(content=dj.arrow_stream(rows))
    stub.respond(json={"data": [SCHEDULE]})
    stub.respond(json={"data": [{"jobRid": JOB}]})
    stub.respond(json=orj.job(JOB, jobStatus="SUCCEEDED"))


FIELDS = [dj.field("id", "LONG", nullable=False), dj.field("name", "STRING")]
ROWS = {"id": [1, 2], "name": ["Ada", "Grace"]}


def test_dataset_context_as_markdown(stub_foundry_http) -> None:
    dataset_responses(stub_foundry_http, FIELDS, ROWS)

    result = runner.invoke(app, ["context", "dataset", DS])

    assert result.exit_code == 0, result.stderr
    text = result.stdout
    assert text.startswith("# Dataset sales\n")
    assert f"- RID: {DS}" in text
    assert "- Path: /Space/Project/sales" in text
    assert "| id | LONG | no |" in text
    assert "| name | STRING | yes |" in text
    assert "| 1 | Ada |" in text
    assert SCHEDULE in text
    assert f"{JOB}: SUCCEEDED" in text


def test_dataset_context_as_json(stub_foundry_http) -> None:
    dataset_responses(stub_foundry_http, FIELDS, ROWS)

    result = runner.invoke(app, ["context", "dataset", DS, "--format", "json"])

    assert result.exit_code == 0, result.stderr
    document = json.loads(result.stdout)
    assert document["rid"] == DS
    assert document["path"] == "/Space/Project/sales"
    assert document["columns"] == [
        {"name": "id", "type": "LONG", "nullable": False},
        {"name": "name", "type": "STRING", "nullable": True},
    ]
    assert document["sampleRows"] == [
        {"id": 1, "name": "Ada"},
        {"id": 2, "name": "Grace"},
    ]
    assert document["schedules"] == [SCHEDULE]
    assert document["latestJob"] == {"rid": JOB, "status": "SUCCEEDED"}


def test_a_wide_dataset_stays_under_the_documented_size(stub_foundry_http) -> None:
    fields = [dj.field(f"column_{i:03d}", "STRING") for i in range(200)]
    rows = {f"column_{i:03d}": ["x" * 80] * 5 for i in range(200)}
    dataset_responses(stub_foundry_http, fields, rows)

    result = runner.invoke(app, ["context", "dataset", DS])

    assert result.exit_code == 0, result.stderr
    assert len(result.stdout.encode()) < MAX_DATASET_CONTEXT_BYTES
    assert "| column_199 | STRING | yes |" in result.stdout  # every column is listed
    assert "--columns" in result.stdout  # the sample says how to see more


def test_unavailable_sections_are_noted_not_fatal(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=fj.resource(DS, "sales", "FOUNDRY_DATASET"))
    stub_foundry_http.respond(json=dj.schema_response(FIELDS))
    stub_foundry_http.respond(content=dj.arrow_stream(ROWS))
    stub_foundry_http.respond(
        403, json=fj.error("GetSchedulesPermissionDenied", "PERMISSION_DENIED")
    )
    stub_foundry_http.respond(
        403, json=fj.error("JobsPermissionDenied", "PERMISSION_DENIED")
    )

    result = runner.invoke(app, ["context", "dataset", DS, "--format", "json"])

    assert result.exit_code == 0, result.stderr
    notes = json.loads(result.stdout)["notes"]
    assert any("schedules" in note for note in notes)
    assert any("jobs" in note for note in notes)


def test_dataset_fixtures_load_with_pandas(stub_foundry_http, tmp_path) -> None:
    import pandas

    dataset_responses(stub_foundry_http, FIELDS, ROWS)

    result = runner.invoke(
        app, ["context", "dataset", DS, "--fixture-dir", str(tmp_path / "fx")]
    )

    assert result.exit_code == 0, result.stderr
    frame = pandas.read_parquet(tmp_path / "fx" / "sales.parquet")
    assert list(frame.columns) == ["id", "name"]
    assert len(frame) == 2
    schema = json.loads((tmp_path / "fx" / "sales.schema.json").read_text())
    assert [f["name"] for f in schema["fieldSchemaList"]] == ["id", "name"]
    assert "real Foundry data" in result.stderr
    assert "gitignore" in result.stderr


# ------------------------------------------------------------------ folder


def test_folder_context_lists_resources_to_a_depth(stub_foundry_http) -> None:
    sub = "ri.compass.main.folder.sub"
    stub_foundry_http.respond(
        json={
            "data": [
                {**fj.resource(sub, "raw"), "path": "/Space/Project/raw"},
                {
                    **fj.resource(DS, "sales", "FOUNDRY_DATASET"),
                    "path": "/Space/Project/sales",
                },
            ]
        }
    )
    stub_foundry_http.respond(
        json={
            "data": [
                {
                    **fj.resource(
                        "ri.foundry.main.dataset.r1", "events", "FOUNDRY_DATASET"
                    ),
                    "path": "/Space/Project/raw/events",
                }
            ]
        }
    )

    markdown = runner.invoke(app, ["context", "folder", fj.PROJECT_RID, "--depth", "2"])

    assert markdown.exit_code == 0, markdown.stderr
    assert (
        "| FOUNDRY_DATASET | /Space/Project/raw/events | ri.foundry.main.dataset.r1 |"
        in markdown.stdout
    )
    assert len(stub_foundry_http.requests) == 2


def test_folder_context_as_json(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json={
            "data": [
                {**fj.resource(DS, "sales", "FOUNDRY_DATASET"), "path": "/S/P/sales"}
            ]
        }
    )

    result = runner.invoke(
        app, ["context", "folder", fj.PROJECT_RID, "--format", "json"]
    )

    assert result.exit_code == 0, result.stderr
    assert json.loads(result.stdout)["resources"] == [
        {"type": "FOUNDRY_DATASET", "name": "sales", "path": "/S/P/sales", "rid": DS}
    ]


# ---------------------------------------------------------------- ontology

LINK = {
    "apiName": "manager",
    "displayName": "Manager",
    "status": "ACTIVE",
    "objectTypeApiName": "Employee",
    "cardinality": "ONE",
    "linkTypeRid": "ri.ontology.main.relation.manager",
}
ACTION = {
    "apiName": "promote-employee",
    "status": "ACTIVE",
    "parameters": {
        "employee": {
            "dataType": {
                "type": "object",
                "objectApiName": "Employee",
                "objectTypeApiName": "Employee",
            },
            "required": True,
            "displayName": "Employee",
        },
        "level": {
            "dataType": {"type": "integer"},
            "required": False,
            "displayName": "Level",
        },
    },
    "rid": "ri.actions.main.action-type.promote",
    "operations": [{"type": "modifyObject", "objectTypeApiName": "Employee"}],
}
OTHER_ACTION = {
    "apiName": "close-ticket",
    "status": "ACTIVE",
    "parameters": {},
    "rid": "ri.actions.main.action-type.close",
    "operations": [{"type": "modifyObject", "objectTypeApiName": "Ticket"}],
}


def full_metadata() -> Dict[str, Any]:
    def entry(api_name: str, links: list) -> Dict[str, Any]:
        return {
            "objectType": oj.object_type(api_name),
            "linkTypes": links,
            "implementsInterfaces": [],
            "implementsInterfaces2": {},
            "sharedPropertyTypeMapping": {},
        }

    return {
        "ontology": oj.ontology(),
        "objectTypes": {
            "Employee": entry("Employee", [LINK]),
            "Ticket": entry("Ticket", []),
        },
        "actionTypes": {"promote-employee": ACTION, "close-ticket": OTHER_ACTION},
        "actionTypesFullMetadata": {},
        "queryTypes": {},
        "interfaceTypes": {},
        "sharedPropertyTypes": {},
        "valueTypes": {},
    }


def test_ontology_context_for_some_types(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=full_metadata())

    result = runner.invoke(
        app, ["context", "ontology", oj.ONTOLOGY, "--types", "Employee"]
    )

    assert result.exit_code == 0, result.stderr
    text = result.stdout
    assert "## Employee" in text
    assert "- Primary key: employeeId" in text
    assert "| salary | double |" in text
    assert "- manager -> Employee (ONE)" in text
    assert "### promote-employee" in text
    assert "close-ticket" not in text  # it doesn't involve Employee
    assert "## Ticket" not in text


def test_ontology_context_as_json(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=full_metadata())

    result = runner.invoke(
        app,
        ["context", "ontology", oj.ONTOLOGY, "--types", "Employee", "--format", "json"],
    )

    document = json.loads(result.stdout)
    (employee,) = document["objectTypes"]
    assert employee["apiName"] == "Employee"
    assert employee["primaryKey"] == "employeeId"
    assert employee["linkTypes"] == [
        {"apiName": "manager", "objectType": "Employee", "cardinality": "ONE"}
    ]
    assert [a["apiName"] for a in document["actionTypes"]] == ["promote-employee"]
    assert document["actionTypes"][0]["parameters"] == [
        {"name": "employee", "type": "object<Employee>", "required": True},
        {"name": "level", "type": "integer", "required": False},
    ]


def test_ontology_context_without_types_is_a_summary(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=full_metadata())

    result = runner.invoke(app, ["context", "ontology", oj.ONTOLOGY])

    assert result.exit_code == 0, result.stderr
    assert "| Employee | employeeId | 3 | 1 |" in result.stdout
    assert "--types" in result.stdout


def test_ontology_fixtures_are_sample_objects(stub_foundry_http, tmp_path) -> None:
    stub_foundry_http.respond(json=full_metadata())
    stub_foundry_http.respond(json=oj.page([oj.employee()], totalCount="1"))

    result = runner.invoke(
        app,
        [
            "context",
            "ontology",
            oj.ONTOLOGY,
            "--types",
            "Employee",
            "--fixture-dir",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.stderr
    objects = json.loads((tmp_path / "Employee.json").read_text())
    assert len(objects) == 1
    assert "real Foundry data" in result.stderr


def test_long_paths_and_rids_are_never_cut(stub_foundry_http) -> None:
    long_rid = "ri.foundry.main.dataset.0f5c1a9e-5555-4000-8000-000000000001"
    long_path = "/A space with a long name/A project with a long name/sales"
    stub_foundry_http.respond(
        json={
            "data": [
                {**fj.resource(long_rid, "sales", "FOUNDRY_DATASET"), "path": long_path}
            ]
        }
    )

    result = runner.invoke(app, ["context", "folder", fj.PROJECT_RID])

    assert f"| FOUNDRY_DATASET | {long_path} | {long_rid} |" in result.stdout
