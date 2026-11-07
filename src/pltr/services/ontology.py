"""
Ontology service wrappers for the Foundry SDK (``client.ontologies``).

Methods return SDK models, SDK iterators or SDK ontology objects (plain dicts
of property values) unchanged; the command layer formats them with
``pltr.contract.emit``. SDK exceptions propagate unchanged so the error layer
can classify them.

Every SDK method used here is GA except ``OntologyObject.count``, which is
beta and always called with ``preview=True``.

``ObjectTypeService.create_object_type`` and ``create_link_type`` are a
labeled direct-HTTP exception (#181): the SDK has no endpoints for creating
object types or link types, so they POST to the schema endpoints in
``_OBJECT_TYPE_CREATE_ENDPOINTS`` / ``_LINK_TYPE_CREATE_ENDPOINTS`` (see
``ObjectTypeService._create_schema_entity``).
"""

from typing import Any, Callable, Dict, List, Optional, Sequence, Union
from urllib.parse import quote

import requests

from ..contract import ExitCode, PltrError
from .base import BaseService

#: ``options.returnEdits`` values of ``Action.apply`` (``ReturnEditsMode``).
RETURN_EDITS_MODES = ("ALL", "ALL_V2_WITH_DELETIONS", "NONE")

#: ``options.returnEdits`` values of ``Action.apply_batch`` (``BatchReturnEditsMode``).
BATCH_RETURN_EDITS_MODES = ("ALL", "NONE")

#: ``defaultLoadLevel`` types of ``OntologyObject.search`` (``PropertyLoadLevel``).
LOAD_LEVELS = (
    "applyReducersAndExtractMainValue",
    "applyReducers",
    "extractMainValue",
    "noLoadLevel",
)

#: ``accuracy`` values of ``OntologyObject.aggregate`` (``AggregationAccuracyRequest``).
AGGREGATION_ACCURACIES = ("REQUIRE_ACCURATE", "ALLOW_APPROXIMATE")

#: Schema endpoints ``ontology object-type-create`` tries, in order (labeled
#: direct-HTTP exception; ``{ontology}`` is the URL-encoded ontology RID).
OBJECT_TYPE_CREATE_ENDPOINTS = (
    "/v2/ontologies/{ontology}/objectTypes",
    "/v1/ontologies/{ontology}/objectTypes",
    "/ontology-manager/api/ontologies/{ontology}/objectTypes",
)

#: Schema endpoints ``ontology link-type-create`` tries, in order.
LINK_TYPE_CREATE_ENDPOINTS = (
    "/v2/ontologies/{ontology}/linkTypes",
    "/v1/ontologies/{ontology}/linkTypes",
    "/ontology-manager/api/ontologies/{ontology}/linkTypes",
)


class OntologyService(BaseService):
    """Ontologies (``client.ontologies.Ontology``)."""

    def _get_service(self) -> Any:
        """Get the Foundry ontologies service."""
        return self.client.ontologies

    def list_ontologies(self) -> Any:
        """List the ontologies you can see (``Ontology.list``, GA).

        Returns:
            ``ListOntologiesV2Response``: ``data`` holds ``OntologyV2`` models
            (the endpoint isn't paged).
        """
        return self.service.Ontology.list()

    def get_ontology(self, ontology: str) -> Any:
        """Get an ontology by API name or RID (``Ontology.get``, GA).

        Returns:
            ``OntologyV2``
        """
        return self.service.Ontology.get(ontology)


class ObjectTypeService(BaseService):
    """Object types (``client.ontologies.Ontology.ObjectType``) and the labeled
    direct-HTTP object/link type creation."""

    def _get_service(self) -> Any:
        """Get the Foundry ontologies service."""
        return self.client.ontologies

    def list_object_types(
        self,
        ontology: str,
        *,
        include_datasources: Optional[bool] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of an ontology's object types (``ObjectType.list``, GA).

        Returns:
            The SDK ``ResourceIterator[ObjectTypeV2]``; constructing it fetched
            exactly one page (``.data``, ``.next_page_token``).
        """
        return self.service.Ontology.ObjectType.list(
            ontology,
            include_datasources=include_datasources,
            page_size=page_size,
            page_token=page_token,
        )

    def get_object_type(
        self,
        ontology: str,
        object_type: str,
        *,
        include_datasources: Optional[bool] = None,
    ) -> Any:
        """Get an object type by API name (``ObjectType.get``, GA).

        Returns:
            ``ObjectTypeV2``
        """
        return self.service.Ontology.ObjectType.get(
            ontology, object_type, include_datasources=include_datasources
        )

    def create_object_type(
        self,
        ontology_rid: str,
        api_name: str,
        display_name: str,
        primary_key: str,
        backing_dataset: str,
        description: Optional[str] = None,
    ) -> Any:
        """Create an object type (labeled direct-HTTP exception; no SDK endpoint).

        Args:
            ontology_rid: Ontology RID
            api_name: Object type API name
            display_name: Object type display name
            primary_key: Primary key property API name
            backing_dataset: Backing dataset RID
            description: Optional object type description

        Returns:
            The response body (parsed JSON), or ``None`` when it is empty.
        """
        payload: Dict[str, Any] = {
            "apiName": api_name,
            "displayName": display_name,
            "primaryKey": primary_key,
            "backingDatasetRid": backing_dataset,
        }
        if description is not None:
            payload["description"] = description

        return self._create_schema_entity(
            ontology_rid=ontology_rid,
            endpoints=OBJECT_TYPE_CREATE_ENDPOINTS,
            payload=payload,
            entity_type="object type",
            entity_id=api_name,
        )

    def create_link_type(
        self,
        ontology_rid: str,
        api_name: str,
        from_object_type: str,
        to_object_type: str,
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        reverse_api_name: Optional[str] = None,
    ) -> Any:
        """Create a link type (labeled direct-HTTP exception; no SDK endpoint).

        Args:
            ontology_rid: Ontology RID
            api_name: Link type API name
            from_object_type: Source object type API name
            to_object_type: Target object type API name
            display_name: Optional link type display name
            description: Optional link type description
            reverse_api_name: Optional reverse direction API name

        Returns:
            The response body (parsed JSON), or ``None`` when it is empty.
        """
        modern_payload: Dict[str, Any] = {
            "apiName": api_name,
            "fromObjectTypeApiName": from_object_type,
            "toObjectTypeApiName": to_object_type,
        }
        legacy_payload: Dict[str, Any] = {
            "apiName": api_name,
            "linkTypeApiNameAtoB": api_name,
            "aSideObjectTypeApiName": from_object_type,
            "bSideObjectTypeApiName": to_object_type,
        }

        if display_name is not None:
            modern_payload["displayName"] = display_name
            legacy_payload["displayName"] = display_name
        if description is not None:
            modern_payload["description"] = description
            legacy_payload["description"] = description
        if reverse_api_name is not None:
            modern_payload["reverseApiName"] = reverse_api_name
            legacy_payload["linkTypeApiNameBtoA"] = reverse_api_name

        def payload_for_endpoint(endpoint_template: str) -> Dict[str, Any]:
            if endpoint_template.startswith("/v2/"):
                return modern_payload
            return legacy_payload

        return self._create_schema_entity(
            ontology_rid=ontology_rid,
            endpoints=LINK_TYPE_CREATE_ENDPOINTS,
            payload=payload_for_endpoint,
            entity_type="link type",
            entity_id=api_name,
        )

    def _create_schema_entity(
        self,
        ontology_rid: str,
        endpoints: Sequence[str],
        payload: Union[Dict[str, Any], Callable[[str], Dict[str, Any]]],
        entity_type: str,
        entity_id: str,
    ) -> Any:
        """POST a create request to the first schema endpoint the stack serves.

        Labeled direct-HTTP exception (#181), through
        ``BaseService._make_request``, which takes the host and bearer token
        from the same auth object as the SDK client (token, OAuth and
        environment-variable auth all work).

        The endpoints are tried in order. A 404 or 405 means the stack doesn't
        serve that endpoint, so the next one is tried; any other HTTP error is
        raised at once, keeping the ``requests.HTTPError`` as ``__cause__``
        so the error layer reports its status and Foundry error body.

        Returns:
            The response body (parsed JSON), or ``None`` when it is empty.
        """
        encoded_ontology = quote(ontology_rid, safe="")
        last_error: Optional[requests.HTTPError] = None
        tried: List[str] = []

        for endpoint_template in endpoints:
            endpoint = endpoint_template.format(ontology=encoded_ontology)
            request_payload = (
                payload(endpoint_template) if callable(payload) else payload
            )
            try:
                response = self._make_request(
                    "POST", endpoint, json_data=request_payload
                )
            except requests.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else None
                if status_code in (404, 405):
                    last_error = e
                    tried.append(f"POST {endpoint} ({status_code})")
                    continue
                raise RuntimeError(f"Failed to create {entity_type} {entity_id}") from e

            if not response.content:
                return None
            try:
                return response.json()
            except ValueError as e:
                raise PltrError(
                    f"Failed to create {entity_type} {entity_id}: POST {endpoint} "
                    "returned a response that is not JSON.",
                    error_type="api_error",
                    exit_code=ExitCode.API,
                ) from e

        raise RuntimeError(
            f"Failed to create {entity_type} {entity_id}: this Foundry stack serves "
            f"none of the schema endpoints pltr knows ({'; '.join(tried)})"
        ) from last_error


class OntologyObjectService(BaseService):
    """Ontology objects (``client.ontologies.OntologyObject`` and ``LinkedObject``).

    SDK ontology objects are plain dicts of property values keyed by property
    API name, plus ``__rid``, ``__primaryKey``, ``__apiName`` and similar.
    """

    def _get_service(self) -> Any:
        """Get the Foundry ontologies service."""
        return self.client.ontologies

    def list_objects(
        self,
        ontology: str,
        object_type: str,
        *,
        select: Optional[List[str]] = None,
        branch: Optional[str] = None,
        load_ontology_defined_derived_properties: Optional[bool] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of objects of a type (``OntologyObject.list``, GA).

        Returns:
            The SDK ``ResourceIterator`` of object dicts; constructing it
            fetched exactly one page (``.data``, ``.next_page_token``).
        """
        return self.service.OntologyObject.list(
            ontology,
            object_type,
            branch=branch,
            load_ontology_defined_derived_properties=load_ontology_defined_derived_properties,
            page_size=page_size,
            page_token=page_token,
            select=select,
        )

    def get_object(
        self,
        ontology: str,
        object_type: str,
        primary_key: str,
        *,
        select: Optional[List[str]] = None,
        branch: Optional[str] = None,
        scenario_rid: Optional[str] = None,
        transaction_id: Optional[str] = None,
        load_ontology_defined_derived_properties: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Get an object by primary key (``OntologyObject.get``, GA).

        Returns:
            The object: a dict of property values.
        """
        return self.service.OntologyObject.get(
            ontology,
            object_type,
            primary_key,
            branch=branch,
            load_ontology_defined_derived_properties=load_ontology_defined_derived_properties,
            scenario_rid=scenario_rid,
            select=select,
            transaction_id=transaction_id,
        )

    def search_objects(
        self,
        ontology: str,
        object_type: str,
        *,
        where: Any = None,
        select: Optional[List[str]] = None,
        order_by: Any = None,
        branch: Optional[str] = None,
        default_load_level: Optional[str] = None,
        load_ontology_defined_derived_properties: Optional[bool] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """Search one page of objects (``OntologyObject.search``, GA).

        Args:
            where: a ``SearchJsonQueryV2`` (model or its JSON as a dict), or
                ``None`` to match every object of the type
            select: property API names to return; the API requires the
                field, so an empty list (every property) is sent by default
            order_by: a ``SearchOrderByV2`` (model or dict)
            default_load_level: a ``PropertyLoadLevel`` type, one of
                :data:`LOAD_LEVELS`

        Returns:
            ``SearchObjectsResponseV2`` (``data``, ``next_page_token``,
            ``total_count``).
        """
        return self.service.OntologyObject.search(
            ontology,
            object_type,
            select=list(select or []),
            branch=branch,
            default_load_level=(
                {"type": default_load_level} if default_load_level else None
            ),
            load_ontology_defined_derived_properties=load_ontology_defined_derived_properties,
            order_by=order_by,
            page_size=page_size,
            page_token=page_token,
            where=where,
        )

    def aggregate_objects(
        self,
        ontology: str,
        object_type: str,
        *,
        aggregation: Sequence[Any],
        group_by: Optional[Sequence[Any]] = None,
        where: Any = None,
        accuracy: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Any:
        """Aggregate objects (``OntologyObject.aggregate``, GA).

        Args:
            aggregation: ``AggregationV2`` objects (models or dicts)
            group_by: ``AggregationGroupByV2`` objects; the API requires the
                field, so an empty list (no grouping) is sent by default
            where: a ``SearchJsonQueryV2`` limiting the aggregated objects
            accuracy: one of :data:`AGGREGATION_ACCURACIES`

        Returns:
            ``AggregateObjectsResponseV2``
        """
        return self.service.OntologyObject.aggregate(
            ontology,
            object_type,
            aggregation=list(aggregation),
            group_by=list(group_by or []),
            accuracy=accuracy,
            branch=branch,
            where=where,
        )

    def count_objects(
        self,
        ontology: str,
        object_type: str,
        *,
        branch: Optional[str] = None,
    ) -> Any:
        """Count the objects of a type (``OntologyObject.count``, beta).

        Returns:
            ``CountObjectsResponseV2`` (read ``.count``).
        """
        return self.service.OntologyObject.count(
            ontology, object_type, branch=branch, preview=True
        )

    def list_linked_objects(
        self,
        ontology: str,
        object_type: str,
        primary_key: str,
        link_type: str,
        *,
        select: Optional[List[str]] = None,
        branch: Optional[str] = None,
        load_ontology_defined_derived_properties: Optional[bool] = None,
        page_size: Optional[int] = None,
        page_token: Optional[str] = None,
    ) -> Any:
        """List one page of the objects linked to an object
        (``LinkedObject.list_linked_objects``, GA).

        Returns:
            The SDK ``ResourceIterator`` of object dicts; constructing it
            fetched exactly one page (``.data``, ``.next_page_token``).
        """
        return self.service.LinkedObject.list_linked_objects(
            ontology,
            object_type,
            primary_key,
            link_type,
            branch=branch,
            load_ontology_defined_derived_properties=load_ontology_defined_derived_properties,
            page_size=page_size,
            page_token=page_token,
            select=select,
        )


class ActionService(BaseService):
    """Actions (``client.ontologies.Action``)."""

    def _get_service(self) -> Any:
        """Get the Foundry ontologies service."""
        return self.client.ontologies

    def apply_action(
        self,
        ontology: str,
        action: str,
        parameters: Dict[str, Any],
        *,
        return_edits: Optional[str] = None,
        attribution: Optional[str] = None,
        scenario_rid: Optional[str] = None,
    ) -> Any:
        """Validate and apply an action (``Action.apply``, GA).

        Args:
            parameters: parameter values keyed by parameter ID
            return_edits: ``options.returnEdits``, one of
                :data:`RETURN_EDITS_MODES` (the API's default is ``NONE``)
            attribution: the ``attribution`` header of the request
            scenario_rid: an ontology scenario to apply the action in

        Returns:
            ``SyncApplyActionResponseV2`` (``operation_id``, ``validation``,
            ``edits``).
        """
        # The SDK validates the options dict into ApplyActionRequestOptions.
        return self.service.Action.apply(
            ontology,
            action,
            parameters=parameters,
            attribution=attribution,
            options={"returnEdits": return_edits} if return_edits else None,
            scenario_rid=scenario_rid,
        )

    def validate_action(
        self,
        ontology: str,
        action: str,
        parameters: Dict[str, Any],
    ) -> Any:
        """Validate an action's parameters without applying it.

        The SDK has no separate validate method: this is ``Action.apply``
        (GA) with ``options.mode = VALIDATE_ONLY``.

        Returns:
            ``SyncApplyActionResponseV2``; ``validation`` holds the result.
        """
        return self.service.Action.apply(
            ontology,
            action,
            parameters=parameters,
            options={"mode": "VALIDATE_ONLY"},
        )

    def apply_batch_actions(
        self,
        ontology: str,
        action: str,
        requests: Sequence[Any],
        *,
        return_edits: Optional[str] = None,
        scenario_rid: Optional[str] = None,
    ) -> Any:
        """Apply several actions of one action type (``Action.apply_batch``, GA).

        Foundry accepts up to 20 actions per call (more for actions that only
        edit Object Storage V2 objects and call no Functions); the server
        enforces the limit.

        Args:
            requests: ``BatchApplyActionRequestItem`` objects (models or dicts
                ``{"parameters": {...}}``)
            return_edits: ``options.returnEdits``, one of
                :data:`BATCH_RETURN_EDITS_MODES` (the API's default is ``NONE``)
            scenario_rid: an ontology scenario to apply the actions in

        Returns:
            ``BatchApplyActionResponseV2`` (``edits``).
        """
        return self.service.Action.apply_batch(
            ontology,
            action,
            requests=list(requests),
            options={"returnEdits": return_edits} if return_edits else None,
            scenario_rid=scenario_rid,
        )


class QueryService(BaseService):
    """Ontology queries (``client.ontologies.Query``)."""

    def _get_service(self) -> Any:
        """Get the Foundry ontologies service."""
        return self.client.ontologies

    def execute_query(
        self,
        ontology: str,
        query_api_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Execute a query function (``Query.execute``, GA).

        Returns:
            ``ExecuteQueryResponse``; ``value`` holds the query's result.
        """
        return self.service.Query.execute(
            ontology, query_api_name, parameters=parameters or {}
        )
