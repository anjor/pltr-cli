"""Rendering SDK calls as Python code (pltr.contract.codegen, #192)."""

import datetime

import pytest
from foundry_sdk.v2.ontologies import models as ontologies_models

from pltr.contract.codegen import Call, PathValue, RawExpr, render_snippet, render_value


def test_primitives_and_containers() -> None:
    imports: set = set()
    assert render_value("a'b", imports) == '"a\'b"'
    assert render_value(None, imports) == "None"
    assert render_value(True, imports) == "True"
    assert render_value(3, imports) == "3"
    assert render_value([1, "x"], imports) == '[1, "x"]'
    assert render_value({"k": [1]}, imports) == '{"k": [1]}'
    assert imports == set()


def test_datetimes_import_datetime() -> None:
    imports: set = set()
    value = datetime.datetime(2026, 1, 31, 12, 0, tzinfo=datetime.timezone.utc)
    assert render_value(value, imports) == (
        'datetime.datetime.fromisoformat("2026-01-31T12:00:00+00:00")'
    )
    assert render_value(datetime.date(2026, 1, 31), imports) == (
        'datetime.date.fromisoformat("2026-01-31")'
    )
    assert imports == {"import datetime"}


def test_models_render_as_constructors_with_their_module() -> None:
    imports: set = set()
    query = ontologies_models.EqualsQueryV2(field="name", value="x")
    assert render_value(query, imports) == (
        'ontologies_models.EqualsQueryV2(field="name", value="x")'
    )
    assert imports == {
        "from foundry_sdk.v2.ontologies import models as ontologies_models"
    }


def test_raw_expressions_are_verbatim() -> None:
    assert render_value(RawExpr('open("a", "rb").read()'), set()) == (
        'open("a", "rb").read()'
    )


def _run(code: str) -> None:
    compile(code, "<emitted>", "exec")


def test_a_plain_call() -> None:
    code = render_snippet(
        Call(
            "datasets.Dataset.get",
            {"dataset_rid": "ri.foundry.main.dataset.d1"},
        )
    )
    _run(code)
    assert 'auth=UserTokenAuth(token=os.environ["FOUNDRY_TOKEN"])' in code
    assert 'hostname=os.environ["FOUNDRY_HOST"]' in code
    assert (
        "result = client.datasets.Dataset.get(\n"
        '    dataset_rid="ri.foundry.main.dataset.d1",\n'
        ")\nprint(result)\n"
    ) in code


def test_paths_are_looked_up_first() -> None:
    code = render_snippet(
        Call("datasets.Dataset.get", {"dataset_rid": PathValue("/S/P/d")})
    )
    _run(code)
    assert (
        "dataset_rid = client.filesystem.Resource.get_by_path(\n"
        '    path="/S/P/d",\n'
        ").rid\n"
    ) in code
    assert "    dataset_rid=dataset_rid,\n" in code


def test_the_same_path_is_looked_up_once() -> None:
    code = render_snippet(
        Call(
            "filesystem.Resource.get_batch",
            {"body": [PathValue("/S/P/d"), PathValue("/S/P/d")]},
        )
    )
    assert code.count("get_by_path(") == 1


def test_an_iterator_is_looped() -> None:
    code = render_snippet(Call("admin.User.list", {"page_size": 10}, paged="iterator"))
    _run(code)
    assert (
        "for item in client.admin.User.list(\n    page_size=10,\n):\n    print(item)\n"
        in code
    )


def test_a_paged_response_is_looped_by_token() -> None:
    code = render_snippet(Call("admin.User.search", {"where": {}}, paged="response"))
    _run(code)
    assert "page_token=page_token" in code
    assert "page_token = page.next_page_token" in code


def test_binary_content_goes_to_a_file_or_stdout() -> None:
    to_file = render_snippet(
        Call(
            "datasets.Dataset.File.content",
            {"dataset_rid": "r"},
            binary=True,
            output="out.csv",
        )
    )
    _run(to_file)
    assert 'with open("out.csv", "wb") as file:\n    file.write(content)\n' in to_file
    to_stdout = render_snippet(
        Call("datasets.Dataset.File.content", {"dataset_rid": "r"}, binary=True)
    )
    _run(to_stdout)
    assert "sys.stdout.buffer.write(content)" in to_stdout


@pytest.mark.parametrize("secret", ["test-token", "Bearer"])
def test_snippets_hold_no_credentials(secret) -> None:
    code = render_snippet(Call("admin.User.get_current", {}))
    assert secret not in code
