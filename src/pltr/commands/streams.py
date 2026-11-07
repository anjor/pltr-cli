"""
Streams commands (Foundry streams API): streaming datasets, streams and
publishing records.
"""

from typing import Any, Dict, List, Optional

import click
import typer
from typing_extensions import Annotated

from ..contract import (
    Columns,
    ConfirmAliasOption,
    FormatOption,
    OutputOption,
    PreviewNoopOption,
    ProfileOption,
    YesOption,
    confirm_destructive,
    emit,
    format_option,
    load_json_input,
    pltr_command,
    spinner,
    success,
)
from ..services.streams import StreamsService
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer(help="Manage streaming datasets and streams")
dataset_app = typer.Typer(help="Manage streaming datasets")
stream_app = typer.Typer(help="Manage streams and publish records")

app.add_typer(dataset_app, name="dataset")
app.add_typer(stream_app, name="stream")

#: Table/CSV columns for a ``streams.models.Dataset``.
DATASET_COLUMNS: Columns = {
    "RID": "rid",
    "Name": "name",
    "Parent Folder": "parent_folder_rid",
}

#: Table/CSV columns for a ``Stream``.
STREAM_COLUMNS: Columns = {
    "Branch": "branch_name",
    "View RID": "view_rid",
    "Stream Type": "stream_type",
    "Partitions": "partitions_count",
    "Compressed": "compressed",
    "Fields": lambda stream: ", ".join(
        f"{field.name} ({field.schema_.data_type.type})"
        for field in stream.schema_.fields
    ),
    "Key Fields": lambda stream: ", ".join(stream.schema_.key_field_names or []),
}

_SCHEMA_EXAMPLE = (
    '{"fields": [{"name": "id", "schema": {"nullable": false, '
    '"dataType": {"type": "long"}}}], "keyFieldNames": ["id"]}'
)

DatasetRid = Annotated[
    str,
    typer.Argument(
        help="RID of the streaming dataset (ri.foundry.main.dataset.<id>).",
        autocompletion=complete_rid,
        show_default=False,
    ),
]
BranchOption = Annotated[
    str,
    typer.Option("--branch", "-b", help="Branch of the stream.", show_default=False),
]
SchemaHelp = (
    'Foundry stream schema as JSON or @file.json: a "fields" list of '
    '{"name", "schema": {"nullable", "dataType": {"type"}}} objects and optional '
    '"keyFieldNames", e.g. ' + _SCHEMA_EXAMPLE + ". Types include string, "
    "integer, long, double, float, boolean, date, timestamp and decimal."
)
CompressedOption = Annotated[
    Optional[bool],
    typer.Option(
        "--compressed/--no-compressed",
        help="Compress the stream (default: off for a new stream).",
        show_default=False,
    ),
]
PartitionsOption = Annotated[
    Optional[int],
    typer.Option(
        "--partitions",
        min=1,
        help=(
            "Number of partitions (default: 1). Each handles about 5 MB/s; it "
            "can't be changed later except by a reset."
        ),
        show_default=False,
    ),
]
StreamTypeOption = Annotated[
    Optional[str],
    typer.Option(
        "--type",
        click_type=click.Choice(
            ["LOW_LATENCY", "HIGH_THROUGHPUT"], case_sensitive=False
        ),
        help="Stream type (default: LOW_LATENCY).",
        show_default=False,
    ),
]
ViewRidOption = Annotated[
    Optional[str],
    typer.Option(
        "--view",
        help=(
            "Write only to the stream view with this RID (advanced; default: the "
            "branch's latest stream)."
        ),
        autocompletion=complete_rid,
    ),
]


def _load_schema(value: str) -> Dict[str, Any]:
    """Parse --schema (inline JSON or @file.json) into a stream schema dict."""
    schema = load_json_input(value, param_hint="'--schema'")
    if not isinstance(schema, dict) or "fields" not in schema:
        raise typer.BadParameter(
            'expected a stream schema object with a "fields" list, e.g. '
            + _SCHEMA_EXAMPLE,
            param_hint="'--schema'",
        )
    return schema


def _stream_type(value: Optional[str]) -> Optional[str]:
    return value.upper() if value else None


@dataset_app.command("create")
@pltr_command(sdk="streams.Dataset.create", beta=True)
def create_dataset(
    name: Annotated[
        str,
        typer.Argument(help="Name of the new streaming dataset.", show_default=False),
    ],
    parent_folder_rid: Annotated[
        str,
        typer.Option(
            "--folder",
            "-f",
            help=(
                "RID of the folder or project to create the dataset in "
                "(ri.compass.main.folder.<id>; not a user folder)."
            ),
            autocompletion=complete_rid,
            show_default=False,
        ),
    ],
    schema: Annotated[
        str, typer.Option("--schema", "-s", help=SchemaHelp, show_default=False)
    ],
    branch: Annotated[
        Optional[str],
        typer.Option(
            "--branch",
            "-b",
            help="Branch of the initial stream (default: the default branch, usually master).",
        ),
    ] = None,
    compressed: CompressedOption = None,
    partitions: PartitionsOption = None,
    stream_type: StreamTypeOption = None,
    profile: ProfileOption = None,
    # -f is --folder here, so --format has no short flag.
    format: Annotated[str, format_option(short=False)] = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Create a streaming dataset with a stream on one branch.

    Examples:

        pltr streams dataset create sensor-data \\
            --folder ri.compass.main.folder.<id> \\
            --schema '{"fields": [{"name": "value", "schema": {"nullable": true, "dataType": {"type": "string"}}}]}'

        pltr streams dataset create sensor-data --folder ri.compass.main.folder.<id> \\
            --schema @schema.json --partitions 5 --type HIGH_THROUGHPUT
    """
    schema_dict = _load_schema(schema)
    with spinner(f"Creating streaming dataset '{name}'..."):
        dataset = StreamsService(profile=profile).create_dataset(
            name=name,
            parent_folder_rid=parent_folder_rid,
            schema=schema_dict,
            branch_name=branch,
            compressed=compressed,
            partitions_count=partitions,
            stream_type=_stream_type(stream_type),
        )
    cache_rid(dataset.rid)
    success(f"Created streaming dataset '{dataset.name}' ({dataset.rid})")
    emit(
        dataset,
        format=format,
        output=output,
        columns=DATASET_COLUMNS,
        title="Streaming Dataset",
    )


@stream_app.command("create")
@pltr_command(sdk="streams.Dataset.Stream.create", beta=True)
def create_stream(
    dataset_rid: DatasetRid,
    branch: Annotated[
        str,
        typer.Option(
            "--branch",
            "-b",
            help="Name of the new branch to create the stream on.",
            show_default=False,
        ),
    ],
    schema: Annotated[
        str, typer.Option("--schema", "-s", help=SchemaHelp, show_default=False)
    ],
    compressed: CompressedOption = None,
    partitions: PartitionsOption = None,
    stream_type: StreamTypeOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Create a branch of a streaming dataset with a new stream on it.

    Example:

        pltr streams stream create ri.foundry.main.dataset.<id> \\
            --branch feature --schema @schema.json --partitions 3
    """
    schema_dict = _load_schema(schema)
    with spinner(f"Creating stream on branch '{branch}'..."):
        stream = StreamsService(profile=profile).create_stream(
            dataset_rid,
            branch_name=branch,
            schema=schema_dict,
            compressed=compressed,
            partitions_count=partitions,
            stream_type=_stream_type(stream_type),
        )
    cache_rid(dataset_rid)
    success(f"Created stream on branch '{stream.branch_name}' ({stream.view_rid})")
    emit(stream, format=format, output=output, columns=STREAM_COLUMNS, title="Stream")


@stream_app.command("get")
@pltr_command(sdk="streams.Dataset.Stream.get")
def get_stream(
    dataset_rid: DatasetRid,
    branch: BranchOption,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Get the stream on a branch: its schema, view RID and settings."""
    with spinner(f"Fetching stream on branch '{branch}'..."):
        stream = StreamsService(profile=profile).get_stream(dataset_rid, branch)
    cache_rid(dataset_rid)
    emit(stream, format=format, output=output, columns=STREAM_COLUMNS, title="Stream")


@stream_app.command("publish")
@pltr_command(sdk="streams.Dataset.Stream.publish_record")
def publish_record(
    dataset_rid: DatasetRid,
    branch: BranchOption,
    record: Annotated[
        str,
        typer.Option(
            "--record",
            "-r",
            help=(
                "Record as a JSON object or @file.json. It must match the stream's "
                "schema; timestamps used as keys are epoch milliseconds."
            ),
            show_default=False,
        ),
    ],
    view_rid: ViewRidOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    preview: PreviewNoopOption = False,
):
    """Publish one record to a stream.

    Example:

        pltr streams stream publish ri.foundry.main.dataset.<id> --branch master \\
            --record '{"id": 123, "value": "hello"}'
    """
    record_value = load_json_input(record, param_hint="'--record'")
    if not isinstance(record_value, dict):
        raise typer.BadParameter("expected a JSON object", param_hint="'--record'")
    with spinner("Publishing record..."):
        StreamsService(profile=profile).publish_record(
            dataset_rid, branch, record_value, view_rid=view_rid
        )
    success(f"Published 1 record to the stream on branch '{branch}'")
    emit(None, format=format)


@stream_app.command("publish-batch")
@pltr_command(sdk="streams.Dataset.Stream.publish_records")
def publish_records(
    dataset_rid: DatasetRid,
    branch: BranchOption,
    records: Annotated[
        str,
        typer.Option(
            "--records",
            "-r",
            help=(
                "Records as a JSON array of objects or @file.json. The batch is "
                "rejected if any record doesn't match the stream's schema."
            ),
            show_default=False,
        ),
    ],
    view_rid: ViewRidOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    preview: PreviewNoopOption = False,
):
    """Publish a batch of records to a stream in one request.

    Example:

        pltr streams stream publish-batch ri.foundry.main.dataset.<id> --branch master \\
            --records '[{"id": 1, "value": "a"}, {"id": 2, "value": "b"}]'
    """
    records_value = load_json_input(records, param_hint="'--records'")
    if (
        not isinstance(records_value, list)
        or not records_value
        or not all(isinstance(item, dict) for item in records_value)
    ):
        raise typer.BadParameter(
            "expected a non-empty JSON array of objects", param_hint="'--records'"
        )
    record_list: List[Dict[str, Any]] = records_value
    with spinner(f"Publishing {len(record_list)} records..."):
        StreamsService(profile=profile).publish_records(
            dataset_rid, branch, record_list, view_rid=view_rid
        )
    success(f"Published {len(record_list)} records to the stream on branch '{branch}'")
    emit(None, format=format)


@stream_app.command("reset")
@pltr_command(sdk="streams.Dataset.Stream.reset", beta=True, destructive=True)
def reset_stream(
    dataset_rid: DatasetRid,
    branch: BranchOption,
    schema: Annotated[
        Optional[str],
        typer.Option(
            "--schema",
            "-s",
            help=(
                "New stream schema as JSON or @file.json, in the format of "
                "'pltr streams dataset create --schema' (default: keep the "
                "current schema)."
            ),
        ),
    ] = None,
    compressed: Annotated[
        Optional[bool],
        typer.Option(
            "--compressed/--no-compressed",
            help="Turn compression on or off (default: keep the current setting).",
            show_default=False,
        ),
    ] = None,
    partitions: Annotated[
        Optional[int],
        typer.Option(
            "--partitions",
            min=1,
            help="New number of partitions (default: keep the current one).",
            show_default=False,
        ),
    ] = None,
    stream_type: Annotated[
        Optional[str],
        typer.Option(
            "--type",
            click_type=click.Choice(
                ["LOW_LATENCY", "HIGH_THROUGHPUT"], case_sensitive=False
            ),
            help="New stream type (default: keep the current one).",
            show_default=False,
        ),
    ] = None,
    yes: YesOption = False,
    confirm: ConfirmAliasOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Reset the stream on a branch: delete all of its records.

    Optionally applies a new schema, partition count, stream type or
    compression; settings you don't pass keep their current values. The
    branch gets a new stream view (a new view RID). Asks for confirmation;
    --yes skips it.
    """
    schema_dict = _load_schema(schema) if schema is not None else None
    confirm_destructive(
        f"Reset the stream on branch '{branch}' of {dataset_rid}? This deletes "
        "all of its records.",
        yes=yes,
    )
    with spinner(f"Resetting stream on branch '{branch}'..."):
        stream = StreamsService(profile=profile).reset_stream(
            dataset_rid,
            branch,
            schema=schema_dict,
            compressed=compressed,
            partitions_count=partitions,
            stream_type=_stream_type(stream_type),
        )
    success(f"Reset the stream on branch '{branch}' (new view {stream.view_rid})")
    emit(stream, format=format, output=output, columns=STREAM_COLUMNS, title="Stream")
