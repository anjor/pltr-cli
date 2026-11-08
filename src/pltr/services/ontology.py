"""
Ontology service wrappers for the Foundry SDK (``client.ontologies``).

Methods return SDK models, SDK iterators or SDK ontology objects (plain dicts
of property values) unchanged; the command layer formats them with
``pltr.contract.emit``. SDK exceptions propagate unchanged so the error layer
can classify them.

Every SDK method used here is GA except ``OntologyObject.count``, which is
beta and always called with ``preview=True``.

The Foundry Platform API has no endpoints for creating object types or link
types, so pltr can't create them. Use Ontology Manager in the Foundry UI, or
an Ontology as Code repository with ``@osdk/maker``.
"""

from typing import Any, Dict, List, Optional, Sequence

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

    def get_full_metadata(self, ontology: str) -> Any:
        """Everything in an ontology (``Ontology.get_full_metadata``, beta)."""
        return self.service.Ontology.get_full_metadata(ontology, preview=True)

    def get_ontology(self, ontology: str) -> Any:
        """Get an ontology by API name or RID (``Ontology.get``, GA).

        Returns:
            ``OntologyV2``
        """
        return self.service.Ontology.get(ontology)


class ObjectTypeService(BaseService):
    """Object types (``client.ontologies.Ontology.ObjectType``)."""

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
