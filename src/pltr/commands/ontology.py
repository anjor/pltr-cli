"""
Ontology commands: ontologies, object types, objects, actions and queries.

Ontologies are addressed by API name or RID; object types, link types,
actions and queries by API name; objects by primary key. Search and aggregate
take the Foundry API's typed JSON objects (``--where``, ``--aggregation``,
``--group-by``, ``--order-by``), validated with the SDK's own models before
anything is sent.
"""

import json
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import click
import typer
from typing_extensions import Annotated

from ..contract import (
    AllPagesOption,
    Columns,
    ExitCode,
    FormatOption,
    MaxPagesOption,
    OutputOption,
    PageSizeOption,
    PageTokenOption,
    PltrError,
    ProfileOption,
    collect_pages,
    emit,
    info,
    load_json_input,
    pltr_command,
    resource_option,
    spinner,
    success,
    warn,
)
from ..services.ontology import (
    AGGREGATION_ACCURACIES,
    BATCH_RETURN_EDITS_MODES,
    LINK_TYPE_CREATE_ENDPOINTS,
    LOAD_LEVELS,
    OBJECT_TYPE_CREATE_ENDPOINTS,
    RETURN_EDITS_MODES,
    ActionService,
    ObjectTypeService,
    OntologyObjectService,
    OntologyService,
    QueryService,
)
from ..utils.completion import cache_rid, complete_rid

app = typer.Typer()

# Examples shown in help and usage errors (Foundry API field names).
WHERE_EXAMPLE = '{"type": "eq", "field": "department", "value": "Engineering"}'
AGGREGATION_EXAMPLE = (
    '[{"type": "count", "name": "employees"}, '
    '{"type": "avg", "field": "salary", "name": "avgSalary"}]'
)
GROUP_BY_EXAMPLE = '[{"type": "exact", "field": "department"}]'
ORDER_BY_EXAMPLE = '{"fields": [{"field": "salary", "direction": "desc"}]}'
PARAMETERS_EXAMPLE = '{"employee": "EMP001", "newDepartment": "Sales"}'
BATCH_EXAMPLE = (
    '[{"parameters": {"employee": "EMP001"}}, {"parameters": {"employee": "EMP002"}}]'
)


# ------------------------------------------------------------------ columns


def _property_types(object_type: Any) -> str:
    return ", ".join(
        f"{name} ({prop.data_type.type})"
        for name, prop in object_type.properties.items()
    )


def _datasources(object_type: Any) -> Optional[str]:
    if object_type.datasources is None:  # not requested (--include-datasources)
        return None
    return ", ".join(
        f"{datasource.definition.type} {datasource.rid}"
        for datasource in object_type.datasources
    )


def _edits_summary(edits: Any) -> Optional[str]:
    """One line for ``ObjectEdits``/``BatchActionObjectEdits``/``ObjectTypeEdits``."""
    if edits is None:
        return None
    if edits.type == "largeScaleEdits":
        return "large-scale edits to " + ", ".join(edits.edited_object_types)
    return (
        f"{edits.added_object_count} added, {edits.modified_objects_count} modified, "
        f"{edits.deleted_objects_count} deleted objects; {edits.added_links_count} "
        f"added, {edits.deleted_links_count} deleted links"
    )


def _criteria_summary(validation: Any) -> Optional[str]:
    if validation is None:
        return None
    return "; ".join(
        criterion.result
        + (
            f" ({criterion.configured_failure_message})"
            if criterion.configured_failure_message
            else ""
        )
        for criterion in validation.submission_criteria
    )


def _parameter_results(validation: Any) -> Optional[str]:
    if validation is None:
        return None
    return ", ".join(
        f"{name}={evaluation.result}"
        for name, evaluation in validation.parameters.items()
    )


#: Table/CSV columns for an ``OntologyV2`` model.
ONTOLOGY_COLUMNS: Columns = {
    "API Name": "api_name",
    "Display Name": "display_name",
    "RID": "rid",
    "Description": "description",
}

#: Table/CSV columns for ``object-type-list`` (one row per ``ObjectTypeV2``).
OBJECT_TYPE_LIST_COLUMNS: Columns = {
    "API Name": "api_name",
    "Display Name": "display_name",
    "Status": "status",
    "Primary Key": "primary_key",
    "Properties": lambda object_type: len(object_type.properties),
    "Description": "description",
    "RID": "rid",
}

#: Table/CSV columns for ``object-type-get`` (an ``ObjectTypeV2``).
OBJECT_TYPE_COLUMNS: Columns = {
    "API Name": "api_name",
    "Display Name": "display_name",
    "Plural Display Name": "plural_display_name",
    "RID": "rid",
    "Status": "status",
    "Visibility": "visibility",
    "Description": "description",
    "Primary Key": "primary_key",
    "Title Property": "title_property",
    "Properties": _property_types,
    "Datasources": _datasources,
}

#: Table/CSV columns for ``action-apply`` (a ``SyncApplyActionResponseV2``).
APPLY_COLUMNS: Columns = {
    "Operation ID": "operation_id",
    "Validation": "validation.result",
    "Edits": lambda response: _edits_summary(response.edits),
}

#: Table/CSV columns for ``action-validate`` (a ``SyncApplyActionResponseV2``).
VALIDATION_COLUMNS: Columns = {
    "Result": "validation.result",
    "Submission Criteria": lambda response: _criteria_summary(response.validation),
    "Parameters": lambda response: _parameter_results(response.validation),
}

#: Table/CSV columns for ``action-apply-batch`` (a ``BatchApplyActionResponseV2``).
BATCH_COLUMNS: Columns = {
    "Edits": lambda response: _edits_summary(response.edits),
}

#: Table/CSV columns for ``object-count`` (a ``CountObjectsResponseV2``).
COUNT_COLUMNS: Columns = {"Count": "count"}


def _aggregate_rows(response: Any) -> List[Dict[str, Any]]:
    """One row per group: its group values, then one column per metric."""
    rows = []
    for item in response.data:
        row: Dict[str, Any] = dict(item.group)
        for metric in item.metrics:
            name = (
                metric.name
                if metric.name not in item.group
                else f"{metric.name} (metric)"
            )
            row[name] = metric.value
        rows.append(row)
    return rows


def _query_rows(response: Any) -> List[Any]:
    """A list result becomes one row per item; anything else a single row."""
    value = response.value
    return list(value) if isinstance(value, list) else [value]


# ------------------------------------------------- arguments and options

OntologyArg = Annotated[
    str,
    typer.Argument(
        help=(
            "Ontology API name or RID (ri.ontology.main.ontology.<id>); find it "
            "with 'pltr ontology list'."
        ),
        autocompletion=complete_rid,
        show_default=False,
    ),
]
OntologyRidArg = Annotated[
    str,
    typer.Argument(
        help="Ontology RID (ri.ontology.main.ontology.<id>); find it with 'pltr ontology list'.",
        autocompletion=complete_rid,
        show_default=False,
    ),
]
ObjectTypeArg = Annotated[
    str,
    typer.Argument(
        help="Object type API name; find it with 'pltr ontology object-type-list'.",
        show_default=False,
    ),
]
PrimaryKeyArg = Annotated[
    str, typer.Argument(help="The object's primary key value.", show_default=False)
]
ActionArg = Annotated[
    str,
    typer.Argument(
        help="Action type API name (see Ontology Manager).", show_default=False
    ),
]
PropertiesOption = Annotated[
    Optional[str],
    typer.Option(
        "--properties",
        help="Comma-separated property API names to return (default: every property).",
        show_default=False,
    ),
]
BranchOption = Annotated[
    Optional[str],
    typer.Option(
        "--branch",
        "-b",
        help="Foundry branch (default: the default branch; branches are experimental in Foundry).",
        show_default=False,
    ),
]
DerivedPropertiesOption = Annotated[
    Optional[bool],
    typer.Option(
        "--derived-properties/--no-derived-properties",
        help=(
            "Whether to load ontology-defined derived properties "
            "(loadOntologyDefinedDerivedProperties; experimental in Foundry). "
            "Foundry loads them by default when --properties isn't given."
        ),
        show_default=False,
    ),
]
IncludeDatasourcesOption = Annotated[
    bool,
    typer.Option(
        "--include-datasources",
        help="Include the datasources that back each object type.",
    ),
]
ScenarioOption = Annotated[
    Optional[str],
    typer.Option(
        "--scenario-rid",
        help="RID of an ontology scenario to work in.",
        show_default=False,
    ),
]


# ------------------------------------------------------------- helpers


def _remember(ontology: str) -> None:
    """Cache an ontology RID (not an API name) for shell completion."""
    if ontology.startswith("ri."):
        cache_rid(ontology)


def _split(value: Optional[str]) -> Optional[List[str]]:
    if value is None:
        return None
    names = [name.strip() for name in value.split(",") if name.strip()]
    return names or None


# ------------------------------------------------------- typed JSON input
#
# --where, --aggregation, --group-by, --order-by and the batch requests are
# the Foundry API's own JSON objects (Foundry field names, camelCase). They
# are validated with the SDK's pydantic models, so a mistake is a usage error
# (exit code 2) naming the problem before anything is sent.


def _hint_name(param_hint: str) -> str:
    return param_hint.strip("'")


def _locate(data: Any, loc: Sequence[Any]) -> Tuple[str, Optional[str]]:
    """Turn a pydantic error location into a JSON path and the owner's "type".

    For tagged unions pydantic puts the tag in the location
    (``('and', 'value', 1, 'gt', 'value')``). Tags are dropped from the
    path; the tag of the object that owns the last field is returned
    (``('value[1].value', 'gt')``), or None when the location doesn't end
    in a field of a tagged object.
    """
    path = ""
    node = data
    tag: Optional[str] = None
    owner: Optional[str] = None
    for part in loc:
        if isinstance(part, int):
            path += f"[{part}]"
            node = (
                node[part] if isinstance(node, list) and 0 <= part < len(node) else None
            )
            tag = owner = None
        elif tag is None and isinstance(node, dict) and node.get("type") == part:
            tag = str(part)
        else:
            path = f"{path}.{part}" if path else str(part)
            node = node.get(part) if isinstance(node, dict) else None
            owner, tag = tag, None
    return path, owner


def _describe_error(error: Dict[str, Any], data: Any) -> str:
    kind = error.get("type")
    ctx = error.get("ctx") or {}
    if kind == "union_tag_invalid":
        expected = str(ctx.get("expected_tags", "")).replace("'", "")
        message = f"unknown type {ctx.get('tag')!r} (expected one of: {expected})"
    elif kind == "union_tag_not_found":
        message = 'missing "type"'
    elif kind == "missing":
        message = "required field missing"
    elif kind in ("model_attributes_type", "model_type", "dict_type"):
        message = "expected a JSON object"
    elif kind == "list_type":
        message = "expected a JSON list"
    else:
        message = str(error.get("msg", "invalid value"))
    path, owner = _locate(data, error.get("loc", ()))
    if owner:  # only set for a field of a tagged object, so path isn't empty
        path = f"{path} (type {owner!r})"
    return f"at {path}: {message}" if path else message


def _unknown_fields(value: Any, path: str = "") -> Iterator[Tuple[str, List[str]]]:
    """Yield (path, known field names) for fields the SDK models don't define.

    SDK models accept unknown fields (and send them), so a misspelled field
    would only fail on the server, or be ignored.
    """
    import pydantic

    if isinstance(value, pydantic.BaseModel):
        fields = type(value).model_fields
        known = [field.alias or name for name, field in fields.items()]
        for key in value.model_extra or {}:
            yield (f"{path}.{key}" if path else str(key)), known
        for name, field in fields.items():
            child = field.alias or name
            yield from _unknown_fields(
                getattr(value, name), f"{path}.{child}" if path else child
            )
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            yield from _unknown_fields(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _unknown_fields(item, f"{path}.{key}" if path else str(key))


def _validate(data: Any, sdk_type: Any, *, param_hint: str, example: str) -> Any:
    """Validate JSON input against an SDK type; usage error (exit 2) if invalid."""
    import pydantic

    try:
        result = pydantic.TypeAdapter(sdk_type).validate_python(data)
    except pydantic.ValidationError as exc:
        errors = exc.errors()
        problems = [_describe_error(dict(error), data) for error in errors[:3]]
        if len(errors) > 3:
            problems.append(f"and {len(errors) - 3} more")
        raise typer.BadParameter(
            "; ".join(problems) + f". Example: {example}", param_hint=param_hint
        ) from exc
    for path, known in _unknown_fields(result):
        warn(
            f"{_hint_name(param_hint)}: unknown field '{path}' (expected one of: "
            f"{', '.join(known)}); it is sent to Foundry as is. Field names are "
            "Foundry API names (camelCase)."
        )
    return result


def _parse_where(value: Optional[str], *, param_hint: str = "'--where'") -> Any:
    """--where: one ``SearchJsonQueryV2`` object, or None."""
    if value is None:
        return None
    from foundry_sdk.v2.ontologies.models import SearchJsonQueryV2

    data = load_json_input(value, param_hint=param_hint)
    if isinstance(data, list):
        raise typer.BadParameter(
            'expected one query object, not a list; combine queries with {"type": '
            f'"and", "value": [...]}}. Example: {WHERE_EXAMPLE}',
            param_hint=param_hint,
        )
    return _validate(
        data, SearchJsonQueryV2, param_hint=param_hint, example=WHERE_EXAMPLE
    )


def _parse_aggregation(value: str, *, param_hint: str = "'--aggregation'") -> List[Any]:
    """--aggregation: a list of ``AggregationV2`` objects (one object is a list of one)."""
    from foundry_sdk.v2.ontologies.models import AggregationV2

    data = load_json_input(value, param_hint=param_hint)
    if isinstance(data, dict):
        data = [data]
    result = _validate(
        data, List[AggregationV2], param_hint=param_hint, example=AGGREGATION_EXAMPLE
    )
    if not result:
        raise typer.BadParameter(
            f"give at least one aggregation. Example: {AGGREGATION_EXAMPLE}",
            param_hint=param_hint,
        )
    return list(result)


def _parse_group_by(
    value: Optional[str], *, param_hint: str = "'--group-by'"
) -> List[Any]:
    """--group-by: a list of ``AggregationGroupByV2`` objects, or property names.

    ``dept,title`` is shorthand for exact groupings,
    ``[{"type": "exact", "field": "dept"}, {"type": "exact", "field": "title"}]``.
    """
    if value is None:
        return []
    from foundry_sdk.v2.ontologies.models import AggregationGroupByV2

    text = value.strip()
    data: Any
    if text.startswith(("[", "{", "@")):
        data = load_json_input(text, param_hint=param_hint)
        if isinstance(data, dict):
            data = [data]
    else:
        data = [{"type": "exact", "field": name} for name in _split(text) or []]
    return list(
        _validate(
            data,
            List[AggregationGroupByV2],
            param_hint=param_hint,
            example=GROUP_BY_EXAMPLE,
        )
    )


def _parse_order_by(value: Optional[str], *, param_hint: str = "'--order-by'") -> Any:
    """--order-by: one ``SearchOrderByV2`` object, or None."""
    if value is None:
        return None
    from foundry_sdk.v2.ontologies.models import SearchOrderByV2

    data = load_json_input(value, param_hint=param_hint)
    return _validate(
        data, SearchOrderByV2, param_hint=param_hint, example=ORDER_BY_EXAMPLE
    )


def _parse_parameters(value: str, *, param_hint: str) -> Dict[str, Any]:
    """Action/query parameters: a JSON object keyed by parameter ID."""
    data = load_json_input(value, param_hint=param_hint)
    if not isinstance(data, dict):
        raise typer.BadParameter(
            "expected a JSON object mapping parameter IDs to values. "
            f"Example: {PARAMETERS_EXAMPLE}",
            param_hint=param_hint,
        )
    return data


def _parse_batch_requests(value: str, *, param_hint: str = "REQUESTS") -> List[Any]:
    """Batch requests: a list of ``BatchApplyActionRequestItem`` objects."""
    from foundry_sdk.v2.ontologies.models import BatchApplyActionRequestItem

    data = load_json_input(value, param_hint=param_hint)
    result = _validate(
        data,
        List[BatchApplyActionRequestItem],
        param_hint=param_hint,
        example=BATCH_EXAMPLE,
    )
    if not result:
        raise typer.BadParameter(
            f"give at least one request. Example: {BATCH_EXAMPLE}",
            param_hint=param_hint,
        )
    return list(result)


def _invalid_summary(validation: Any) -> str:
    invalid = [
        name
        for name, evaluation in validation.parameters.items()
        if evaluation.result == "INVALID"
    ]
    criteria = [
        criterion.configured_failure_message or "a submission criterion"
        for criterion in validation.submission_criteria
        if criterion.result == "INVALID"
    ]
    parts = []
    if invalid:
        parts.append("invalid parameters: " + ", ".join(invalid))
    if criteria:
        parts.append("failed submission criteria: " + "; ".join(criteria))
    return "; ".join(parts) or "validation failed"


# --------------------------------------------------------------- ontologies


@app.command("list")
@pltr_command(sdk="ontologies.Ontology.list")
def list_ontologies(
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """List the ontologies you can see.

    JSON output is the API's response: {"data": [...]}.
    """
    with spinner("Listing ontologies..."):
        response = OntologyService(profile=profile).list_ontologies()
    for ontology in response.data[:50]:
        cache_rid(ontology.rid)
    emit(
        response,
        format=format,
        output=output,
        columns=ONTOLOGY_COLUMNS,
        rows=lambda result: result.data,
    )


@app.command("get")
@pltr_command(sdk="ontologies.Ontology.get")
def get_ontology(
    ontology: OntologyArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get an ontology's metadata."""
    with spinner(f"Fetching ontology {ontology}..."):
        result = OntologyService(profile=profile).get_ontology(ontology)
    cache_rid(result.rid)
    emit(
        result, format=format, output=output, columns=ONTOLOGY_COLUMNS, title="Ontology"
    )


# ------------------------------------------------------------- object types


@app.command("object-type-list")
@pltr_command(sdk="ontologies.Ontology.ObjectType.list", paged=True)
def list_object_types(
    ontology: OntologyArg,
    include_datasources: IncludeDatasourcesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List an ontology's object types.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = ObjectTypeService(profile=profile)
    with spinner(f"Listing object types of {ontology}..."):
        page = collect_pages(
            lambda token: service.list_object_types(
                ontology,
                include_datasources=include_datasources or None,
                page_size=page_size,
                page_token=token,
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    _remember(ontology)
    emit(page, format=format, output=output, columns=OBJECT_TYPE_LIST_COLUMNS)


@app.command("object-type-get")
@pltr_command(sdk="ontologies.Ontology.ObjectType.get")
def get_object_type(
    ontology: OntologyArg,
    object_type: ObjectTypeArg,
    include_datasources: IncludeDatasourcesOption = False,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get an object type: its primary key, title property and properties."""
    with spinner(f"Fetching object type {object_type}..."):
        result = ObjectTypeService(profile=profile).get_object_type(
            ontology, object_type, include_datasources=include_datasources or None
        )
    _remember(ontology)
    emit(
        result,
        format=format,
        output=output,
        columns=OBJECT_TYPE_COLUMNS,
        title="Object Type",
    )


@app.command("object-type-create")
@pltr_command(http=tuple(f"POST {path}" for path in OBJECT_TYPE_CREATE_ENDPOINTS))
def create_object_type(
    ontology_rid: OntologyRidArg,
    api_name: Annotated[str, typer.Option("--api-name", help="Object type API name.")],
    display_name: Annotated[
        str, typer.Option("--display-name", help="Object type display name.")
    ],
    primary_key: Annotated[
        str, typer.Option("--primary-key", help="API name of the primary key property.")
    ],
    backing_dataset: Annotated[
        str,
        resource_option(
            "--backing-dataset",
            kind="dataset",
            help="RID of the backing dataset (ri.foundry.main.dataset.<id>).",
            autocompletion=complete_rid,
        ),
    ],
    description: Annotated[
        Optional[str], typer.Option("--description", help="Object type description.")
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create an object type (direct HTTP: the SDK can't create object types).

    The Foundry Platform SDK has no endpoint for creating object types, so
    this POSTs to the schema endpoints pltr knows, in order, until one exists
    on your stack: /v2/ontologies/{ontology}/objectTypes,
    /v1/ontologies/{ontology}/objectTypes and
    /ontology-manager/api/ontologies/{ontology}/objectTypes. JSON output is the
    response body as Foundry returns it (null when empty).
    """
    with spinner(f"Creating object type {api_name}..."):
        result = ObjectTypeService(profile=profile).create_object_type(
            ontology_rid=ontology_rid,
            api_name=api_name,
            display_name=display_name,
            primary_key=primary_key,
            backing_dataset=backing_dataset,
            description=description,
        )
    _remember(ontology_rid)
    success(f"Created object type '{api_name}' in ontology {ontology_rid}")
    emit(result, format=format, output=output, title="Object Type")


@app.command("link-type-create")
@pltr_command(http=tuple(f"POST {path}" for path in LINK_TYPE_CREATE_ENDPOINTS))
def create_link_type(
    ontology_rid: OntologyRidArg,
    api_name: Annotated[str, typer.Option("--api-name", help="Link type API name.")],
    from_object: Annotated[
        str, typer.Option("--from", help="API name of the source object type.")
    ],
    to_object: Annotated[
        str, typer.Option("--to", help="API name of the target object type.")
    ],
    display_name: Annotated[
        Optional[str], typer.Option("--display-name", help="Link type display name.")
    ] = None,
    description: Annotated[
        Optional[str], typer.Option("--description", help="Link type description.")
    ] = None,
    reverse_api_name: Annotated[
        Optional[str],
        typer.Option(
            "--reverse-api-name",
            help="API name of the reverse (target to source) link.",
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Create a link type (direct HTTP: the SDK can't create link types).

    The Foundry Platform SDK has no endpoint for creating link types, so this
    POSTs to the schema endpoints pltr knows, in order, until one exists on
    your stack: /v2/ontologies/{ontology}/linkTypes,
    /v1/ontologies/{ontology}/linkTypes and
    /ontology-manager/api/ontologies/{ontology}/linkTypes. JSON output is the
    response body as Foundry returns it (null when empty).
    """
    with spinner(f"Creating link type {api_name}..."):
        result = ObjectTypeService(profile=profile).create_link_type(
            ontology_rid=ontology_rid,
            api_name=api_name,
            from_object_type=from_object,
            to_object_type=to_object,
            display_name=display_name,
            description=description,
            reverse_api_name=reverse_api_name,
        )
    _remember(ontology_rid)
    success(f"Created link type '{api_name}' in ontology {ontology_rid}")
    emit(result, format=format, output=output, title="Link Type")


# ------------------------------------------------------------------ objects


@app.command("object-list")
@pltr_command(sdk="ontologies.OntologyObject.list", paged=True)
def list_objects(
    ontology: OntologyArg,
    object_type: ObjectTypeArg,
    properties: PropertiesOption = None,
    branch: BranchOption = None,
    derived_properties: DerivedPropertiesOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the objects of an object type.

    Fetches one page by default; use --all for every page, --max-pages N for
    N pages, or --page-token with the nextPageToken of an earlier response to
    continue. To filter, use 'pltr ontology object-search'.
    """
    service = OntologyObjectService(profile=profile)
    with spinner(f"Listing {object_type} objects..."):
        page = collect_pages(
            lambda token: service.list_objects(
                ontology,
                object_type,
                select=_split(properties),
                branch=branch,
                load_ontology_defined_derived_properties=derived_properties,
                page_size=page_size,
                page_token=token,
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    _remember(ontology)
    emit(page, format=format, output=output)


@app.command("object-get")
@pltr_command(sdk="ontologies.OntologyObject.get")
def get_object(
    ontology: OntologyArg,
    object_type: ObjectTypeArg,
    primary_key: PrimaryKeyArg,
    properties: PropertiesOption = None,
    branch: BranchOption = None,
    scenario_rid: Annotated[
        Optional[str],
        typer.Option(
            "--scenario-rid",
            help="RID of an ontology scenario to read the object from.",
            show_default=False,
        ),
    ] = None,
    transaction_id: Annotated[
        Optional[str],
        typer.Option(
            "--transaction-id",
            help="ID of an ontology transaction to read from (experimental in Foundry).",
            show_default=False,
        ),
    ] = None,
    derived_properties: DerivedPropertiesOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Get an object by primary key.

    JSON output is the object as Foundry returns it: its property values keyed
    by property API name, plus __rid, __primaryKey and __apiName.
    """
    with spinner(f"Fetching {object_type} {primary_key}..."):
        result = OntologyObjectService(profile=profile).get_object(
            ontology,
            object_type,
            primary_key,
            select=_split(properties),
            branch=branch,
            scenario_rid=scenario_rid,
            transaction_id=transaction_id,
            load_ontology_defined_derived_properties=derived_properties,
        )
    _remember(ontology)
    emit(result, format=format, output=output, title=f"{object_type} {primary_key}")


@app.command("object-search")
@pltr_command(sdk="ontologies.OntologyObject.search", paged=True)
def search_objects(
    ontology: OntologyArg,
    object_type: ObjectTypeArg,
    where: Annotated[
        Optional[str],
        typer.Option(
            "--where",
            help=(
                "Filter: a Foundry search query (SearchJsonQueryV2) as JSON, inline "
                f"or @file.json, e.g. {WHERE_EXAMPLE}. Default: every object."
            ),
            show_default=False,
        ),
    ] = None,
    order_by: Annotated[
        Optional[str],
        typer.Option(
            "--order-by",
            help=f"Sort order (SearchOrderByV2) as JSON, e.g. {ORDER_BY_EXAMPLE}.",
            show_default=False,
        ),
    ] = None,
    properties: PropertiesOption = None,
    branch: BranchOption = None,
    default_load_level: Annotated[
        Optional[str],
        typer.Option(
            "--default-load-level",
            click_type=click.Choice(LOAD_LEVELS),
            metavar="LEVEL",
            help=(
                "How to load properties that have reducers or struct main values "
                "(defaultLoadLevel): " + ", ".join(LOAD_LEVELS) + "."
            ),
            show_default=False,
        ),
    ] = None,
    derived_properties: DerivedPropertiesOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
    query: Annotated[
        Optional[str],
        typer.Option(
            "--query",
            "-q",
            hidden=True,
            help="Removed: use --where.",
            show_default=False,
        ),
    ] = None,
):
    """Search the objects of an object type with a typed query.

    --where takes the Foundry API's search query (SearchJsonQueryV2) as JSON,
    inline, as @file.json or as @- (stdin), using Foundry API field names.
    Each query has a
    "type", such as eq, gt, gte, lt, lte, in, isNull, contains,
    containsAnyTerm, containsAllTerms, startsWith, regex, and, or and not (an
    unknown type is rejected with the full list). Most queries name a property
    with "field".

    Examples:

    \b
    # Employees in Engineering
    pltr ontology object-search my-ontology Employee \\
        --where '{"type": "eq", "field": "department", "value": "Engineering"}'

    \b
    # Engineers paid at least 100000, highest salary first
    pltr ontology object-search my-ontology Employee \\
        --where '{"type": "and", "value": [
            {"type": "eq", "field": "department", "value": "Engineering"},
            {"type": "gte", "field": "salary", "value": 100000}]}' \\
        --order-by '{"fields": [{"field": "salary", "direction": "desc"}]}'

    Fetches one page by default; use --all for every page. JSON output is the
    API's response: {"data": [...], "nextPageToken": ..., "totalCount": N}.
    """
    if query is not None:
        suggestion = json.dumps(
            {"type": "containsAnyTerm", "field": "<property>", "value": query}
        )
        raise typer.BadParameter(
            "free-text search was removed: the Foundry search API filters on "
            f"properties with a typed query. Use --where, e.g. --where '{suggestion}'",
            param_hint="'--query'",
        )
    where_query = _parse_where(where)
    order = _parse_order_by(order_by)
    select = _split(properties)
    service = OntologyObjectService(profile=profile)
    total_counts: List[int] = []

    def fetch(token: Optional[str]) -> Any:
        response = service.search_objects(
            ontology,
            object_type,
            where=where_query,
            select=select,
            order_by=order,
            branch=branch,
            default_load_level=default_load_level,
            load_ontology_defined_derived_properties=derived_properties,
            page_size=page_size,
            page_token=token,
        )
        total_counts.append(response.total_count)
        return response

    with spinner(f"Searching {object_type} objects..."):
        page = collect_pages(
            fetch, page_token=page_token, max_pages=max_pages, all_pages=all_pages
        )
    _remember(ontology)

    from foundry_sdk.v2.ontologies.models import SearchObjectsResponseV2

    # The pages merged into the API's own response shape (totalCount
    # included). emit prints it whole in JSON, and one row per object (with
    # the next-page hint) in table and CSV.
    result = SearchObjectsResponseV2(
        data=page.data,
        next_page_token=page.next_page_token,
        total_count=total_counts[0],
    )
    emit(result, format=format, output=output)
    if result.data:
        info(f"{len(result.data)} of {result.total_count} matching objects.")


@app.command("object-aggregate")
@pltr_command(sdk="ontologies.OntologyObject.aggregate")
def aggregate_objects(
    ontology: OntologyArg,
    object_type: ObjectTypeArg,
    aggregations: Annotated[
        Optional[str],
        typer.Argument(
            hidden=True,
            metavar="",
            help="Deprecated: use --aggregation.",
            show_default=False,
        ),
    ] = None,
    aggregation: Annotated[
        Optional[str],
        typer.Option(
            "--aggregation",
            help=(
                "Required. The metrics to compute: a JSON list of Foundry "
                f"aggregations (AggregationV2), inline or @file.json, e.g. {AGGREGATION_EXAMPLE}."
            ),
            show_default=False,
        ),
    ] = None,
    group_by: Annotated[
        Optional[str],
        typer.Option(
            "--group-by",
            help=(
                "Groups: a JSON list of Foundry group-bys (AggregationGroupByV2), e.g. "
                f"{GROUP_BY_EXAMPLE}, or comma-separated property API names as "
                "shorthand for exact groupings (department,title)."
            ),
            show_default=False,
        ),
    ] = None,
    where: Annotated[
        Optional[str],
        typer.Option(
            "--where",
            help=(
                "Only aggregate objects matching this Foundry search query "
                f"(SearchJsonQueryV2), as JSON, e.g. {WHERE_EXAMPLE}."
            ),
            show_default=False,
        ),
    ] = None,
    accuracy: Annotated[
        Optional[str],
        typer.Option(
            "--accuracy",
            click_type=click.Choice(AGGREGATION_ACCURACIES),
            help="Whether approximate results are acceptable (default: Foundry's).",
            show_default=False,
        ),
    ] = None,
    branch: BranchOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    filter_alias: Annotated[
        Optional[str],
        typer.Option(
            "--filter",
            hidden=True,
            help="Deprecated alias for --where.",
            show_default=False,
        ),
    ] = None,
):
    """Aggregate objects: counts, sums, averages and more, optionally grouped.

    --aggregation, --group-by and --where take the Foundry API's typed
    objects as JSON, inline, as @file.json or as @- (stdin), using Foundry API
    field names.
    Aggregation types: count, sum, avg, min, max, approximateDistinct,
    exactDistinct, approximatePercentile. Group-by types: exact, fixedWidth,
    ranges, duration.

    Examples:

    \b
    # Head count and average salary per department
    pltr ontology object-aggregate my-ontology Employee \\
        --aggregation '[{"type": "count", "name": "employees"},
                        {"type": "avg", "field": "salary", "name": "avgSalary"}]' \\
        --group-by department

    \b
    # Number of senior employees, grouped in salary bands of 10000
    pltr ontology object-aggregate my-ontology Employee \\
        --aggregation '{"type": "count"}' \\
        --group-by '[{"type": "fixedWidth", "field": "salary", "fixedWidth": 10000}]' \\
        --where '{"type": "gte", "field": "level", "value": 5}'

    The table has one row per group, with a column per group value and per
    metric. JSON output is the API's response: {"data": [{"group": {...},
    "metrics": [...]}], "accuracy": ...}.
    """
    if aggregations is not None:
        if aggregation is not None:
            raise typer.BadParameter(
                "give the aggregations once, with --aggregation",
                param_hint="'--aggregation'",
            )
        warn(
            "Passing the aggregations as an argument is deprecated and will be "
            "removed in a future release; use --aggregation."
        )
        aggregation = aggregations
    if aggregation is None:
        raise click.MissingParameter(
            f"Give the metrics to compute, e.g. --aggregation '{AGGREGATION_EXAMPLE}'.",
            param_hint="'--aggregation'",
            param_type="option",
        )
    if filter_alias is not None:
        if where is not None:
            raise typer.BadParameter(
                "--filter is a deprecated alias of --where; give only --where",
                param_hint="'--filter'",
            )
        warn(
            "--filter is deprecated and will be removed in a future release; use --where."
        )
        where = filter_alias
    metrics = _parse_aggregation(aggregation)
    groups = _parse_group_by(group_by)
    where_query = _parse_where(where)
    with spinner(f"Aggregating {object_type} objects..."):
        result = OntologyObjectService(profile=profile).aggregate_objects(
            ontology,
            object_type,
            aggregation=metrics,
            group_by=groups,
            where=where_query,
            accuracy=accuracy,
            branch=branch,
        )
    _remember(ontology)
    emit(result, format=format, output=output, rows=_aggregate_rows)
    if result.accuracy == "APPROXIMATE":
        info("These results are approximate (accuracy: APPROXIMATE).")
    if result.excluded_items:
        info(f"Foundry excluded {result.excluded_items} items (excludedItems).")


@app.command("object-count")
@pltr_command(sdk="ontologies.OntologyObject.count", beta=True)
def count_objects(
    ontology: OntologyArg,
    object_type: ObjectTypeArg,
    branch: BranchOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Count the objects of an object type.

    JSON output is the API's response: {"count": N}.
    """
    with spinner(f"Counting {object_type} objects..."):
        result = OntologyObjectService(profile=profile).count_objects(
            ontology, object_type, branch=branch
        )
    _remember(ontology)
    emit(result, format=format, output=output, columns=COUNT_COLUMNS, title=object_type)


@app.command("object-linked")
@pltr_command(sdk="ontologies.LinkedObject.list_linked_objects", paged=True)
def list_linked_objects(
    ontology: OntologyArg,
    object_type: ObjectTypeArg,
    primary_key: PrimaryKeyArg,
    link_type: Annotated[
        str,
        typer.Argument(
            help=(
                "Link type API name, as seen from OBJECT_TYPE. List them with 'pltr api "
                "ontologies ontology object-type list-outgoing-link-types ONTOLOGY "
                "OBJECT_TYPE'."
            ),
            show_default=False,
        ),
    ],
    properties: PropertiesOption = None,
    branch: BranchOption = None,
    derived_properties: DerivedPropertiesOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    page_size: PageSizeOption = None,
    page_token: PageTokenOption = None,
    max_pages: MaxPagesOption = 1,
    all_pages: AllPagesOption = False,
):
    """List the objects linked to an object through a link type.

    Fetches one page by default; use --all for every page, or --page-token
    with the nextPageToken of an earlier response to continue.
    """
    service = OntologyObjectService(profile=profile)
    with spinner(f"Listing objects linked to {object_type} {primary_key}..."):
        page = collect_pages(
            lambda token: service.list_linked_objects(
                ontology,
                object_type,
                primary_key,
                link_type,
                select=_split(properties),
                branch=branch,
                load_ontology_defined_derived_properties=derived_properties,
                page_size=page_size,
                page_token=token,
            ),
            page_token=page_token,
            max_pages=max_pages,
            all_pages=all_pages,
        )
    _remember(ontology)
    emit(page, format=format, output=output)


# ------------------------------------------------------------------ actions

ParametersArg = Annotated[
    str,
    typer.Argument(
        help=(
            "Action parameters: a JSON object keyed by parameter ID, inline, "
            f"@file.json or @- (stdin), e.g. {PARAMETERS_EXAMPLE}."
        ),
        show_default=False,
    ),
]


@app.command("action-apply")
@pltr_command(sdk="ontologies.Action.apply")
def apply_action(
    ontology: OntologyArg,
    action: ActionArg,
    parameters: ParametersArg,
    return_edits: Annotated[
        Optional[str],
        typer.Option(
            "--return-edits",
            click_type=click.Choice(RETURN_EDITS_MODES),
            help="Return the edits the action made (Foundry's default: NONE).",
            show_default=False,
        ),
    ] = None,
    attribution: Annotated[
        Optional[str],
        typer.Option(
            "--attribution",
            help="Attribution to record for the request (sent as the attribution header).",
            show_default=False,
        ),
    ] = None,
    scenario_rid: ScenarioOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Apply an action: validate its parameters and make its edits.

    The action is applied as soon as its parameters are valid (no
    confirmation). Check them first with 'pltr ontology action-validate'. If
    Foundry reports the parameters invalid, nothing is applied and the
    command fails with exit code 6.

    Example:

    \b
    pltr ontology action-apply my-ontology transferEmployee \\
        '{"employee": "EMP001", "newDepartment": "Sales"}' --return-edits ALL
    """
    params = _parse_parameters(parameters, param_hint="PARAMETERS")
    with spinner(f"Applying action {action}..."):
        result = ActionService(profile=profile).apply_action(
            ontology,
            action,
            params,
            return_edits=return_edits,
            attribution=attribution,
            scenario_rid=scenario_rid,
        )
    _remember(ontology)
    if result.validation is not None and result.validation.result == "INVALID":
        raise PltrError(
            f"Action {action} was not applied: {_invalid_summary(result.validation)}.",
            error_type="validation_error",
            exit_code=ExitCode.VALIDATION,
            hint="Run 'pltr ontology action-validate' with the same parameters for details.",
        )
    success(f"Applied action {action}")
    emit(
        result,
        format=format,
        output=output,
        columns=APPLY_COLUMNS,
        title="Action Result",
    )


@app.command("action-validate")
@pltr_command(sdk="ontologies.Action.apply")
def validate_action(
    ontology: OntologyArg,
    action: ActionArg,
    parameters: ParametersArg,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Check an action's parameters without applying it.

    Runs the action in VALIDATE_ONLY mode. Exits 0 when Foundry answers, valid
    or not: the result (VALID or INVALID), the submission criteria and the
    per-parameter results are the output.
    """
    params = _parse_parameters(parameters, param_hint="PARAMETERS")
    with spinner(f"Validating action {action}..."):
        result = ActionService(profile=profile).validate_action(
            ontology, action, params
        )
    _remember(ontology)
    validation = result.validation
    if validation is None:
        warn("Foundry returned no validation result.")
    elif validation.result == "VALID":
        success(f"The parameters are valid for action {action}.")
    else:
        warn(
            f"The parameters are INVALID for action {action}: "
            f"{_invalid_summary(validation)}."
        )
    emit(
        result,
        format=format,
        output=output,
        columns=VALIDATION_COLUMNS,
        title="Validation",
    )


@app.command("action-apply-batch")
@pltr_command(sdk="ontologies.Action.apply_batch")
def apply_action_batch(
    ontology: OntologyArg,
    action: ActionArg,
    requests: Annotated[
        str,
        typer.Argument(
            help=(
                'The actions to apply: a JSON list of {"parameters": {...}} objects, '
                f"inline, @file.json or @- (stdin), e.g. {BATCH_EXAMPLE}."
            ),
            show_default=False,
        ),
    ],
    return_edits: Annotated[
        Optional[str],
        typer.Option(
            "--return-edits",
            click_type=click.Choice(BATCH_RETURN_EDITS_MODES),
            help="Return the edits the actions made (Foundry's default: NONE).",
            show_default=False,
        ),
    ] = None,
    scenario_rid: ScenarioOption = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Apply several actions of one action type in a single request.

    Foundry applies up to 20 actions per request (more for actions that only
    edit Object Storage V2 objects and call no Functions). They are applied
    without confirmation; if any is invalid, Foundry rejects the request.

    Example:

    \b
    pltr ontology action-apply-batch my-ontology transferEmployee \\
        '[{"parameters": {"employee": "EMP001", "newDepartment": "Sales"}},
          {"parameters": {"employee": "EMP002", "newDepartment": "Sales"}}]'
    """
    items = _parse_batch_requests(requests)
    with spinner(f"Applying {len(items)} {action} actions..."):
        result = ActionService(profile=profile).apply_batch_actions(
            ontology,
            action,
            items,
            return_edits=return_edits,
            scenario_rid=scenario_rid,
        )
    _remember(ontology)
    success(f"Applied {len(items)} {action} actions")
    emit(
        result,
        format=format,
        output=output,
        columns=BATCH_COLUMNS,
        title="Batch Result",
    )


# ------------------------------------------------------------------ queries


@app.command("query-execute")
@pltr_command(sdk="ontologies.Query.execute")
def execute_query(
    ontology: OntologyArg,
    query_name: Annotated[
        str,
        typer.Argument(
            help="Query API name (see Ontology Manager).", show_default=False
        ),
    ],
    parameters: Annotated[
        Optional[str],
        typer.Option(
            "--parameters",
            help=(
                "Query parameters: a JSON object keyed by parameter ID, inline, "
                "@file.json or @- (stdin)."
            ),
            show_default=False,
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Execute an ontology query function.

    JSON output is the API's response: {"value": <the query's result>}. The
    table shows one row per item when the result is a list.
    """
    params = (
        _parse_parameters(parameters, param_hint="'--parameters'")
        if parameters is not None
        else None
    )
    with spinner(f"Executing query {query_name}..."):
        result = QueryService(profile=profile).execute_query(
            ontology, query_name, parameters=params
        )
    _remember(ontology)
    emit(result, format=format, output=output, rows=_query_rows)


@app.callback()
def main():
    """
    Ontology operations using foundry-platform-sdk.

    Ontologies are addressed by API name or RID (ri.ontology.main.ontology.<id>);
    find them with 'pltr ontology list'. Object types, link types, actions and
    queries are addressed by API name, objects by primary key.

    Examples:

    \b
        # Ontologies and their object types
        pltr ontology list
        pltr ontology object-type-list my-ontology
    \b
        # Objects
        pltr ontology object-get my-ontology Employee EMP001
        pltr ontology object-search my-ontology Employee \\
            --where '{"type": "eq", "field": "department", "value": "Sales"}'
        pltr ontology object-aggregate my-ontology Employee \\
            --aggregation '[{"type": "count"}]' --group-by department
    \b
        # Actions
        pltr ontology action-validate my-ontology transferEmployee '{"employee": "EMP001"}'
        pltr ontology action-apply my-ontology transferEmployee '{"employee": "EMP001"}'
    """
