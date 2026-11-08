"""`pltr assert`: checks that pass or fail by exit code (#195)."""

import datetime
import json
from typing import Any, Dict

import pytest
from typer.testing import CliRunner

from pltr.cli import app
from tests import foundry_json_dataset as dj
from tests import foundry_json_orchestration as oj
from tests import foundry_json_ontology as ontj

pytestmark = pytest.mark.usefixtures("isolated_home")

runner = CliRunner()

DS = dj.DATASET_RID


def run(*args: str) -> Any:
    return runner.invoke(app, ["assert", *args, "--format", "json"])


def result_of(result: Any) -> Dict[str, Any]:
    return json.loads(result.stdout)


def recent(minutes: int) -> str:
    when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        minutes=minutes
    )
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------- dataset


def test_min_rows_reads_at_most_that_many_rows(stub_foundry_http) -> None:
    stub_foundry_http.respond(content=dj.arrow_stream({"id": [1, 2, 3]}))

    result = run("dataset", DS, "--min-rows", "3")

    assert result.exit_code == 0, result.stderr
    assert result_of(result) == {
        "passed": True,
        "target": DS,
        "checks": [{"check": "min-rows", "passed": True, "expected": 3, "actual": 3}],
    }
    (request,) = stub_foundry_http.requests
    assert request.url.params["rowLimit"] == "3"


def test_too_few_rows_fails_with_exit_8(stub_foundry_http) -> None:
    stub_foundry_http.respond(content=dj.arrow_stream({"id": [1]}))

    result = run("dataset", DS, "--min-rows", "5")

    assert result.exit_code == 8
    assert result_of(result)["passed"] is False
    error = json.loads(result.stderr.strip().splitlines()[-1])
    assert error["type"] == "assertion_failed"
    assert "min-rows" in error["message"]


def test_schema_matches_an_expected_file(stub_foundry_http, tmp_path) -> None:
    expected = tmp_path / "schema.json"
    expected.write_text(json.dumps(dj.schema_response()))
    stub_foundry_http.respond(json=dj.schema_response())

    result = run("dataset", DS, "--schema", str(expected))

    assert result.exit_code == 0, result.stderr
    assert result_of(result)["checks"][0]["check"] == "schema"


def test_schema_differences_are_listed(stub_foundry_http, tmp_path) -> None:
    expected = tmp_path / "schema.json"
    expected.write_text(
        json.dumps(
            {
                "fieldSchemaList": [
                    {"name": "id", "type": "STRING"},
                    {"name": "missing", "type": "LONG"},
                ]
            }
        )
    )
    stub_foundry_http.respond(
        json=dj.schema_response([dj.field("id", "LONG"), dj.field("extra", "DOUBLE")])
    )

    result = run("dataset", DS, "--schema", str(expected))

    assert result.exit_code == 8
    (check,) = result_of(result)["checks"]
    assert check["missing"] == ["missing"]
    assert check["unexpected"] == ["extra"]
    assert check["typeMismatches"] == [
        {"column": "id", "expected": "STRING", "actual": "LONG"}
    ]


def test_updated_within_checks_the_latest_committed_transaction(
    stub_foundry_http,
) -> None:
    stub_foundry_http.respond(
        json=dj.page(
            [
                dj.transaction("ri.foundry.main.transaction.open", status="OPEN"),
                dj.transaction(status="COMMITTED", closed_time=recent(10)),
            ]
        )
    )

    result = run("dataset", DS, "--updated-within", "1h", "--branch", "master")

    assert result.exit_code == 0, result.stderr
    (check,) = result_of(result)["checks"]
    assert check["check"] == "updated-within"
    assert check["transactionRid"] == dj.TRANSACTION_RID


def test_a_stale_dataset_fails(stub_foundry_http) -> None:
    stub_foundry_http.respond(
        json=dj.page([dj.transaction(status="COMMITTED", closed_time=recent(120))])
    )

    result = run("dataset", DS, "--updated-within", "30m")

    assert result.exit_code == 8


def test_a_dataset_check_is_required(stub_foundry_http) -> None:
    result = run("dataset", DS)

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_several_checks_run_together(stub_foundry_http, tmp_path) -> None:
    expected = tmp_path / "schema.json"
    expected.write_text(json.dumps(dj.schema_response()))
    stub_foundry_http.respond(content=dj.arrow_stream({"id": [1, 2]}))
    stub_foundry_http.respond(json=dj.schema_response())

    result = run("dataset", DS, "--min-rows", "1", "--schema", str(expected))

    assert result.exit_code == 0, result.stderr
    assert [c["check"] for c in result_of(result)["checks"]] == ["min-rows", "schema"]


# ------------------------------------------------------------- build, objects


def test_assert_build_succeeded(stub_foundry_http) -> None:
    stub_foundry_http.respond(json=oj.build(status="SUCCEEDED"))
    passed = run("build", oj.BUILD_RID, "--succeeded")
    stub_foundry_http.respond(json=oj.build(status="FAILED"))
    failed = run("build", oj.BUILD_RID, "--succeeded")

    assert passed.exit_code == 0, passed.stderr
    assert failed.exit_code == 8
    assert result_of(failed)["checks"][0]["actual"] == "FAILED"


def test_assert_objects_min_count(stub_foundry_http) -> None:
    stub_foundry_http.respond(json={"count": 42})

    result = run("objects", ontj.ONTOLOGY, "Employee", "--min-count", "40")

    assert result.exit_code == 0, result.stderr
    assert result_of(result)["checks"] == [
        {"check": "min-count", "passed": True, "expected": 40, "actual": 42}
    ]


# ------------------------------------------------------ review fixes (#195)


def test_nested_and_decimal_types_are_compared(stub_foundry_http, tmp_path) -> None:
    expected = tmp_path / "schema.json"
    expected.write_text(
        json.dumps(
            {
                "fieldSchemaList": [
                    {
                        "name": "tags",
                        "type": "ARRAY",
                        "arraySubtype": {"type": "STRING"},
                    },
                    {"name": "price", "type": "DECIMAL", "precision": 38, "scale": 0},
                ]
            }
        )
    )
    stub_foundry_http.respond(
        json=dj.schema_response(
            [
                {
                    "name": "tags",
                    "type": "ARRAY",
                    "nullable": True,
                    "arraySubtype": {"type": "LONG", "nullable": True},
                },
                {
                    "name": "price",
                    "type": "DECIMAL",
                    "nullable": True,
                    "precision": 10,
                    "scale": 2,
                },
            ]
        )
    )

    result = run("dataset", DS, "--schema", str(expected))

    assert result.exit_code == 8
    (check,) = result_of(result)["checks"]
    assert check["typeMismatches"] == [
        {"column": "price", "expected": "DECIMAL(38,0)", "actual": "DECIMAL(10,2)"},
        {"column": "tags", "expected": "ARRAY<STRING>", "actual": "ARRAY<LONG>"},
    ]
    error = json.loads(result.stderr.strip().splitlines()[-1])
    assert "price" in error["message"]


@pytest.mark.parametrize("flag", ["--schema", "--updated-within"])
def test_empty_check_values_are_usage_errors(stub_foundry_http, flag) -> None:
    result = run("dataset", DS, flag, "")

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


@pytest.mark.parametrize("content", ["{}", "[]", '{"schema": null}'])
def test_a_schema_file_without_fields_is_a_usage_error(
    stub_foundry_http, tmp_path, content
) -> None:
    expected = tmp_path / "schema.json"
    expected.write_text(content)

    result = run("dataset", DS, "--schema", str(expected))

    assert result.exit_code == 2
