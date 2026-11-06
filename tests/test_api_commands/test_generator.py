"""The `pltr api` generator: staleness, coverage, and how SDK shapes are mapped."""

import datetime
import importlib.util
import sys
import typing
from pathlib import Path

import pydantic
import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load_script(name: str, filename: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return load_script("pltr_generate_api_commands", "generate_api_commands.py")


@pytest.fixture(scope="module")
def coverage_script():
    return load_script("pltr_api_coverage", "coverage.py")


@pytest.fixture(scope="module")
def rendered(generator):
    return generator.render_files()


def test_generated_specs_are_up_to_date(generator, rendered):
    stale = generator.stale_files(rendered, generator.existing_files())
    assert not stale, (
        "The committed `pltr api` specs don't match foundry-platform-sdk "
        f"{generator.sdk_version()}: {', '.join(stale)}.\n"
        "Run: uv run python scripts/generate_api_commands.py"
    )


def test_generation_is_deterministic(generator, rendered):
    assert generator.render_files() == rendered


def test_generated_files_are_valid_python_outside_the_formatter(rendered):
    for path, content in rendered.items():
        assert content.endswith("\n")
        assert "\r" not in content
        assert "# fmt: off" in content, path
        compile(content, path, "exec")


def test_coverage_of_every_v2_method(coverage_script):
    coverage = coverage_script.compute()
    report = coverage.to_dict()

    assert coverage.missing == []
    assert coverage.unknown == []
    assert coverage.excluded_but_generated == []
    assert report["totalMethods"] == report["generated"] + report["excluded"]
    for row in coverage.methods:
        if row["excludedReason"]:
            assert len(row["excludedReason"]) > 20, row
    assert coverage.ok


def test_coverage_script_exit_status(coverage_script, capsys):
    assert coverage_script.main([]) == 0
    assert "Generated coverage:" in capsys.readouterr().out


def test_curated_coverage_hook_exists(coverage_script):
    assert coverage_script.curated_commands() == {}


def test_destructive_list_matches_seed_names(generator):
    """Every method whose name looks destructive was reviewed (and exists)."""
    methods = generator.all_public_methods(generator.V2)
    for method in methods:
        name = method.rsplit(".", 1)[1]
        if generator.DESTRUCTIVE_NAME_SEED.fullmatch(name):
            assert (
                method in generator.V2.destructive
                or method in generator.V2.not_destructive
            ), method
    assert set(generator.V2.destructive) <= set(methods)
    for reviewed in (
        "streams.Dataset.Stream.reset",
        "streams.Dataset.Stream.Subscriber.reset_offsets",
        "media_sets.MediaSet.clear",
        "third_party_applications.ThirdPartyApplication.Website.undeploy",
        "datasets.Dataset.put_schema",
    ):
        assert reviewed in generator.V2.destructive


def test_unreviewed_destructive_name_fails_generation(generator, monkeypatch):
    config = generator.V2
    trimmed = generator.dataclasses.replace(
        config, destructive=config.destructive - {"admin.User.delete"}
    )
    monkeypatch.setattr(generator, "API_VERSIONS", (trimmed,))
    with pytest.raises(generator.GeneratorError, match="admin.User.delete"):
        generator.build_specs()


def test_stale_config_entries_fail_generation(generator, monkeypatch):
    config = generator.V2
    broken = generator.dataclasses.replace(
        config, destructive=config.destructive | {"admin.User.no_such_method"}
    )
    monkeypatch.setattr(generator, "API_VERSIONS", (broken,))
    with pytest.raises(generator.GeneratorError, match="no_such_method"):
        generator.build_specs()


@pytest.mark.parametrize(
    "name, expected",
    [
        ("CbacBanner", "cbac-banner"),
        ("OpenAiModel", "open-ai-model"),
        ("TimeSeriesPropertyV2", "time-series-property-v2"),
        ("get_by_rid_batch", "get-by-rid-batch"),
        ("third_party_applications", "third-party-applications"),
        ("SQLQuery", "sql-query"),
    ],
)
def test_kebab(generator, name, expected):
    assert generator.kebab(name) == expected


class _Model(pydantic.BaseModel):
    value: int


@pytest.mark.parametrize(
    "annotation, expected",
    [
        (str, {"type": "str"}),
        (typing.Optional[int], {"type": "int"}),
        (typing.Annotated[str, "rid"], {"type": "str"}),
        (bool, {"type": "bool"}),
        (float, {"type": "float"}),
        (datetime.date, {"type": "date"}),
        (pydantic.AwareDatetime, {"type": "datetime"}),
        (typing.Literal["A", "B"], {"type": "choice", "choices": ["A", "B"]}),
        (typing.List[str], {"type": "str", "multiple": True}),
        (
            typing.Optional[typing.List[typing.Literal["X"]]],
            {
                "type": "choice",
                "choices": ["X"],
                "multiple": True,
            },
        ),
        (bytes, {"type": "bytes"}),
        (_Model, {"type": "json"}),
        (typing.List[_Model], {"type": "json"}),
        (typing.Dict[str, typing.Any], {"type": "json"}),
        (typing.Union[_Model, typing.Dict[str, int]], {"type": "json"}),
        (typing.Any, {"type": "json"}),
    ],
)
def test_parameter_type_mapping(generator, annotation, expected):
    assert generator.parameter_type(annotation) == expected


def test_docstring_parsing(generator):
    doc = generator.parse_docstring(
        """
        Lists all Users.

        This is a paged endpoint.

        Required scopes: [api:admin-read]

        :param page_size: The page size
            to use.
        :type page_size: Optional[PageSize]
        :return: Returns the result object.
        :rtype: core.ResourceIterator[admin_models.User]
        """
    )
    assert doc.description == (
        "Lists all Users.\n\nThis is a paged endpoint.\n\n"
        "Required scopes: [api:admin-read]"
    )
    assert doc.params == {"page_size": "The page size to use."}
    assert doc.types == {"page_size": "Optional[PageSize]"}
    assert generator.summarize(doc.description) == "Lists all Users."
    assert generator.summarize("Required scopes: [api:admin-read]") == ""


def test_specs_record_flags(generator, rendered):
    from pltr.commands.api._specs import admin, datasets, streams

    users = {r["name"]: r for r in admin.SPEC["resources"]}["user"]
    methods = {m["name"]: m for m in users["methods"]}
    assert methods["list"]["paged"] == "iterator"
    assert methods["search"]["paged"] == "response"
    assert methods["delete"]["destructive"] is True
    assert methods["profile-picture"]["binary"] is True
    assert "beta" not in methods["get"]
    assert methods["get"]["params"][0] == {
        "name": "user_id",
        "in": "path",
        "api": "userId",
        "type": "str",
        "schema": "UserId",
        "required": True,
    }

    dataset = {r["name"]: r for r in datasets.SPEC["resources"]}["dataset"]
    read_table = {m["name"]: m for m in dataset["methods"]}["read-table"]
    assert read_table["binary"] is True
    renamed = {p["name"]: p for p in read_table["params"]}["format"]
    assert renamed["option"] == "--api-format"

    stream = {r["name"]: r for r in streams.SPEC["resources"]}["dataset"]
    stream = {r["name"]: r for r in stream["resources"]}["stream"]
    assert {m["name"]: m for m in stream["methods"]}["reset"]["destructive"] is True
