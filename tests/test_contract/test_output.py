"""Tests for pltr.contract.emit and the column spec."""

import csv
import datetime
import io
import json

import pytest
from foundry_sdk.v2.filesystem.models import Folder, Space

from pltr.contract import ColumnError, Page, column_value, emit, format_cell
from tests import foundry_json as fj

FOLDER = Folder.model_validate(fj.folder())
SPACE = Space.model_validate(fj.space(organizations=[fj.ORG_A, fj.ORG_B]))


@pytest.fixture(autouse=True)
def wide_console(monkeypatch):
    monkeypatch.setenv("COLUMNS", "200")


# ------------------------------------------------------------------ columns


def test_column_paths_accept_python_and_api_names():
    assert column_value(FOLDER, "display_name") == "Test Folder"
    assert column_value(FOLDER, "displayName") == "Test Folder"
    assert column_value(FOLDER, "created_by") == fj.USER_ID


def test_column_access_on_models_is_strict():
    with pytest.raises(ColumnError, match="Folder has no field 'created'"):
        column_value(FOLDER, "created")
    with pytest.raises(ColumnError):
        column_value(FOLDER, "modified")


def test_existing_none_field_renders_empty():
    folder = Folder.model_validate({**fj.folder(), "description": None})
    assert column_value(folder, "description") is None
    assert format_cell(column_value(folder, "description")) == ""


def test_dotted_paths_and_none_short_circuit():
    nested = {"reference": {"mediaSetViewItem": {"mediaSetRid": "ri.x"}}}
    assert column_value(nested, "reference.mediaSetViewItem.mediaSetRid") == "ri.x"
    assert column_value({"reference": None}, "reference.mediaSetViewItem") is None


def test_plain_dict_missing_key_is_empty():
    assert column_value({"a": 1}, "b") is None


def test_callable_columns():
    assert column_value(SPACE, lambda s: ", ".join(s.organizations)) == (
        f"{fj.ORG_A}, {fj.ORG_B}"
    )


def test_strict_attribute_access_on_other_objects():
    class Plain:
        rid = "ri.x"

    assert column_value(Plain(), "rid") == "ri.x"
    with pytest.raises(ColumnError):
        column_value(Plain(), "missing")


def test_format_cell():
    assert format_cell(None) == ""
    assert format_cell(True) == "true"
    assert format_cell(3) == "3"
    assert format_cell(["a", "b"]) == '["a","b"]'
    assert format_cell({"k": None}) == '{"k":null}'
    aware = datetime.datetime(
        2024, 1, 1, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=1))
    )
    assert format_cell(aware) == "2024-01-01T00:00:00+00:00"
    assert format_cell(FOLDER.created_time) == "2024-01-01T00:00:00+00:00"


# --------------------------------------------------------------------- emit

COLUMNS = {"RID": "rid", "Name": "display_name", "Created": "created_time"}


def test_emit_json_single_object(capsys):
    emit(FOLDER, format="json", columns=COLUMNS)
    out, err = capsys.readouterr()
    assert json.loads(out) == fj.sdk_json(fj.folder())
    assert err == ""


def test_emit_json_list_and_page(capsys):
    emit([FOLDER], format="json")
    assert json.loads(capsys.readouterr().out) == {"data": [fj.sdk_json(fj.folder())]}
    emit(Page([FOLDER], "next"), format="json")
    assert json.loads(capsys.readouterr().out)["nextPageToken"] == "next"


def test_emit_json_none_is_null(capsys):
    emit(None, format="json")
    assert json.loads(capsys.readouterr().out) is None


def test_emit_table_single_object_is_vertical(capsys):
    emit(FOLDER, format="table", columns=COLUMNS, title="Folder")
    out = capsys.readouterr().out
    assert "Property" in out and "Value" in out
    assert fj.FOLDER_RID in out and "2024-01-01T00:00:00+00:00" in out


def test_emit_table_list_is_horizontal_and_hints_next_page(capsys):
    emit(Page([FOLDER], "tok"), format="table", columns=COLUMNS)
    out, err = capsys.readouterr()
    header = [cell.strip() for cell in out.splitlines()[1].split("┃")[1:4]]
    assert header == ["RID", "Name", "Created"]
    assert "--page-token tok" in err


def test_emit_table_escapes_markup(capsys):
    emit({"name": "[bold]not markup[/bold]"}, format="table")
    assert "[bold]not markup[/bold]" in capsys.readouterr().out


def test_emit_empty_list(capsys):
    emit([], format="table", columns=COLUMNS)
    out, err = capsys.readouterr()
    assert out == "" and "No results." in err
    emit([], format="csv", columns=COLUMNS)
    assert capsys.readouterr().out == "RID,Name,Created\n"


def test_emit_csv(capsys):
    emit([FOLDER], format="csv", columns=COLUMNS)
    rows = list(csv.reader(io.StringIO(capsys.readouterr().out)))
    assert rows == [
        ["RID", "Name", "Created"],
        [fj.FOLDER_RID, "Test Folder", "2024-01-01T00:00:00+00:00"],
    ]


def test_emit_rows_override_for_table_and_csv(capsys):
    batch = {"data": {"a": {"rid": "ri.a"}, "b": {"rid": "ri.b"}}}
    emit(batch, format="csv", columns={"RID": "rid"}, rows=lambda r: r["data"].values())
    assert capsys.readouterr().out == "RID\nri.a\nri.b\n"
    emit(batch, format="json", rows=lambda r: r["data"].values())
    assert json.loads(capsys.readouterr().out) == batch


def test_emit_auto_columns_for_models_and_dicts(capsys):
    emit([FOLDER], format="csv")
    header = capsys.readouterr().out.splitlines()[0].split(",")
    assert header[:3] == ["rid", "displayName", "description"]
    emit([{"a": 1}, {"b": 2}], format="csv")
    assert capsys.readouterr().out == "a,b\n1,\n,2\n"


def test_emit_strict_columns_fail_loudly():
    with pytest.raises(ColumnError):
        emit(FOLDER, format="table", columns={"Created": "created"})


@pytest.mark.parametrize("fmt", ["json", "csv", "table"])
def test_emit_to_output_file(fmt, tmp_path, capsys):
    path = tmp_path / f"out.{fmt}"
    emit([FOLDER], format=fmt, output=str(path), columns=COLUMNS)
    out, err = capsys.readouterr()
    assert out == ""
    assert fj.FOLDER_RID in path.read_text(encoding="utf-8")
    assert str(path) in err  # text mode: tell the user where it went
