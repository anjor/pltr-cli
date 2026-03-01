"""
Ontology service wrappers for Foundry SDK.
"""

from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import quote
import requests

from ..config.settings import Settings
from ..utils.pagination import PaginationConfig, PaginationResult
from .base import BaseService


class OntologyService(BaseService):
    """Service wrapper for Foundry ontology operations."""

    def _get_service(self) -> Any:
        """Get the Foundry ontologies service."""
        return self.client.ontologies

    def list_ontologies(self) -> List[Dict[str, Any]]:
        """
        List all ontologies visible to the current user.

        Returns:
            List of ontology information dictionaries
        """
        try:
            result = self.service.Ontology.list()
            ontologies = []
            # The response has a 'data' field containing the list of ontologies
            for ontology in result.data:
                ontologies.append(self._format_ontology_info(ontology))
            return ontologies
        except Exception as e:
            raise RuntimeError(f"Failed to list ontologies: {e}")

    def get_ontology(self, ontology_rid: str) -> Dict[str, Any]:
        """
        Get a specific ontology by RID.

        Args:
            ontology_rid: Ontology Resource Identifier

        Returns:
            Ontology information dictionary
        """
        try:
            ontology = self.service.Ontology.get(ontology_rid)
            return self._format_ontology_info(ontology)
        except Exception as e:
            raise RuntimeError(f"Failed to get ontology {ontology_rid}: {e}")

    def _format_ontology_info(self, ontology: Any) -> Dict[str, Any]:
        """Format ontology information for consistent output."""
        return {
            "rid": ontology.rid,
            "api_name": getattr(ontology, "api_name", None),
            "display_name": getattr(ontology, "display_name", None),
            "description": getattr(ontology, "description", None),
        }


class ObjectTypeService(BaseService):
    """Service wrapper for object type operations."""

    _OBJECT_TYPE_CREATE_ENDPOINTS = [
        "/v2/ontologies/{ontology}/objectTypes",
        "/v1/ontologies/{ontology}/objectTypes",
        "/ontology-manager/api/ontologies/{ontology}/objectTypes",
    ]
    _LINK_TYPE_CREATE_ENDPOINTS = [
        "/v2/ontologies/{ontology}/linkTypes",
        "/v1/ontologies/{ontology}/linkTypes",
        "/ontology-manager/api/ontologies/{ontology}/linkTypes",
    ]

    def _get_service(self) -> Any:
        """Get the Foundry ontologies service."""
        return self.client.ontologies

    def list_object_types(self, ontology_rid: str) -> List[Dict[str, Any]]:
        """
        List object types in an ontology.

        Args:
            ontology_rid: Ontology Resource Identifier

        Returns:
            List of object type information dictionaries
        """
        try:
            # ObjectType is nested under Ontology in the SDK
            result = self.service.Ontology.ObjectType.list(ontology_rid)
            object_types = []
            # The response has a 'data' field containing the list of object types
            for obj_type in result.data:
                object_types.append(self._format_object_type_info(obj_type))
            return object_types
        except Exception as e:
            raise RuntimeError(f"Failed to list object types: {e}")

    def get_object_type(self, ontology_rid: str, object_type: str) -> Dict[str, Any]:
        """
        Get a specific object type.

        Args:
            ontology_rid: Ontology Resource Identifier
            object_type: Object type API name

        Returns:
            Object type information dictionary
        """
        try:
            # ObjectType is nested under Ontology in the SDK
            obj_type = self.service.Ontology.ObjectType.get(ontology_rid, object_type)
            return self._format_object_type_info(obj_type)
        except Exception as e:
            raise RuntimeError(f"Failed to get object type {object_type}: {e}")

    def create_object_type(
        self,
        ontology_rid: str,
        api_name: str,
        display_name: str,
        primary_key: str,
        backing_dataset: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an ontology object type via direct API calls.

        Args:
            ontology_rid: Ontology Resource Identifier
            api_name: Object type API name
            display_name: Object type display name
            primary_key: Primary key property API name
            backing_dataset: Backing dataset RID
            description: Optional object type description

        Returns:
            API response dictionary
        """
        payload = {
            "apiName": api_name,
            "displayName": display_name,
            "primaryKey": primary_key,
            "backingDatasetRid": backing_dataset,
        }
        if description is not None:
            payload["description"] = description

        return self._create_schema_entity(
            ontology_rid=ontology_rid,
            endpoints=self._OBJECT_TYPE_CREATE_ENDPOINTS,
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
    ) -> Dict[str, Any]:
        """
        Create an ontology link type via direct API calls.

        Args:
            ontology_rid: Ontology Resource Identifier
            api_name: Link type API name
            from_object_type: Source object type API name
            to_object_type: Target object type API name
            display_name: Optional link type display name
            description: Optional link type description
            reverse_api_name: Optional reverse direction API name

        Returns:
            API response dictionary
        """
        modern_payload = {
            "apiName": api_name,
            "fromObjectTypeApiName": from_object_type,
            "toObjectTypeApiName": to_object_type,
        }
        legacy_payload = {
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
            endpoints=self._LINK_TYPE_CREATE_ENDPOINTS,
            payload=payload_for_endpoint,
            entity_type="link type",
            entity_id=api_name,
        )

    def list_outgoing_link_types(
        self, ontology_rid: str, object_type: str
    ) -> List[Dict[str, Any]]:
        """
        List outgoing link types for an object type.

        Args:
            ontology_rid: Ontology Resource Identifier
            object_type: Object type API name

        Returns:
            List of link type information dictionaries
        """
        try:
            # ObjectType is nested under Ontology in the SDK
            result = self.service.Ontology.ObjectType.list_outgoing_link_types(
                ontology_rid, object_type
            )
            link_types = []
            # The response has a 'data' field containing the list of link types
            for link_type in result.data:
                link_types.append(self._format_link_type_info(link_type))
            return link_types
        except Exception as e:
            raise RuntimeError(f"Failed to list link types: {e}")

    def _format_object_type_info(self, obj_type: Any) -> Dict[str, Any]:
        """Format object type information for consistent output."""
        return {
            "api_name": obj_type.api_name,
            "display_name": getattr(obj_type, "display_name", None),
            "description": getattr(obj_type, "description", None),
            "primary_key": getattr(obj_type, "primary_key", None),
            "properties": getattr(obj_type, "properties", {}),
        }

    def _format_link_type_info(self, link_type: Any) -> Dict[str, Any]:
        """Format link type information for consistent output."""
        return {
            "api_name": link_type.api_name,
            "display_name": getattr(link_type, "display_name", None),
            "object_type": getattr(link_type, "object_type", None),
            "linked_object_type": getattr(link_type, "linked_object_type", None),
        }

    def _create_schema_entity(
        self,
        ontology_rid: str,
        endpoints: List[str],
        payload: Union[Dict[str, Any], Callable[[str], Dict[str, Any]]],
        entity_type: str,
        entity_id: str,
    ) -> Dict[str, Any]:
        """Post create requests across known schema management endpoints."""
        encoded_ontology = quote(ontology_rid, safe="")
        last_error: Optional[Exception] = None

        for endpoint_template in endpoints:
            endpoint = endpoint_template.format(ontology=encoded_ontology)
            request_payload = (
                payload(endpoint_template) if callable(payload) else payload
            )
            try:
                response = self._make_request(
                    "POST", endpoint, json_data=request_payload
                )
                result = response.json() if response.text else {}
                if isinstance(result, dict):
                    result.setdefault("apiName", entity_id)
                    result.setdefault("ontologyRid", ontology_rid)
                    return result
                return {
                    "apiName": entity_id,
                    "ontologyRid": ontology_rid,
                    "response": result,
                }
            except requests.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else None
                if status_code not in (404, 405):
                    raise RuntimeError(
                        f"Failed to create {entity_type} {entity_id}: {e}"
                    ) from e
                last_error = e
            except RuntimeError as e:
                if "404" in str(e) or "405" in str(e):
                    last_error = e
                    continue
                raise RuntimeError(f"Failed to create {entity_type} {entity_id}: {e}")
            except requests.RequestException as e:
                raise RuntimeError(f"Failed to create {entity_type} {entity_id}: {e}")
            except ValueError as e:
                raise RuntimeError(
                    f"Failed to parse create {entity_type} response for {entity_id}: {e}"
                ) from e
            except Exception as e:
                raise RuntimeError(
                    f"Failed to create {entity_type} {entity_id}: {e}"
                ) from e

        raise RuntimeError(f"Failed to create {entity_type} {entity_id}: {last_error}")


class OntologyObjectService(BaseService):
    """Service wrapper for ontology object operations."""

    def _get_service(self) -> Any:
        """Get the Foundry ontologies service."""
        return self.client.ontologies

    def list_objects(
        self,
        ontology_rid: str,
        object_type: str,
        page_size: Optional[int] = None,
        properties: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        List objects of a specific type.

        DEPRECATED: Use list_objects_paginated() instead for better pagination support.

        Args:
            ontology_rid: Ontology Resource Identifier
            object_type: Object type API name
            page_size: Number of results per page
            properties: List of properties to include

        Returns:
            List of object dictionaries
        """
        try:
            result = self.service.OntologyObject.list(
                ontology_rid,
                object_type,
                page_size=page_size,
                select=properties,
            )
            objects = []
            for obj in result:
                objects.append(self._format_object(obj))
            return objects
        except Exception as e:
            raise RuntimeError(f"Failed to list objects: {e}")

    def list_objects_paginated(
        self,
        ontology_rid: str,
        object_type: str,
        config: PaginationConfig,
        properties: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> PaginationResult:
        """
        List objects with full pagination control.

        Args:
            ontology_rid: Ontology Resource Identifier
            object_type: Object type API name
            config: Pagination configuration
            properties: List of properties to include
            progress_callback: Optional progress callback

        Returns:
            PaginationResult with objects and metadata
        """
        try:
            settings = Settings()

            # Get iterator from SDK - ResourceIterator with next_page_token support
            iterator = self.service.OntologyObject.list(
                ontology_rid,
                object_type,
                page_size=config.page_size or settings.get("page_size", 20),
                select=properties,
            )

            # Use iterator pagination handler
            result = self._paginate_iterator(iterator, config, progress_callback)

            # Format objects
            result.data = [self._format_object(obj) for obj in result.data]

            return result
        except Exception as e:
            raise RuntimeError(f"Failed to list objects: {e}")

    def get_object(
        self,
        ontology_rid: str,
        object_type: str,
        primary_key: str,
        properties: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get a specific object by primary key.

        Args:
            ontology_rid: Ontology Resource Identifier
            object_type: Object type API name
            primary_key: Object primary key
            properties: List of properties to include

        Returns:
            Object dictionary
        """
        try:
            obj = self.service.OntologyObject.get(
                ontology_rid, object_type, primary_key, select=properties
            )
            return self._format_object(obj)
        except Exception as e:
            raise RuntimeError(f"Failed to get object {primary_key}: {e}")

    def aggregate_objects(
        self,
        ontology_rid: str,
        object_type: str,
        aggregations: List[Dict[str, Any]],
        group_by: Optional[List[str]] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Aggregate objects with specified functions.

        Args:
            ontology_rid: Ontology Resource Identifier
            object_type: Object type API name
            aggregations: List of aggregation specifications
            group_by: Fields to group by
            filter: Filter criteria

        Returns:
            Aggregation results
        """
        try:
            result = self.service.OntologyObject.aggregate(
                ontology_rid,
                object_type,
                aggregations=aggregations,
                group_by=group_by,
                filter=filter,
            )
            return result
        except Exception as e:
            raise RuntimeError(f"Failed to aggregate objects: {e}")

    def list_linked_objects(
        self,
        ontology_rid: str,
        object_type: str,
        primary_key: str,
        link_type: str,
        page_size: Optional[int] = None,
        properties: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        List objects linked to a specific object.

        Args:
            ontology_rid: Ontology Resource Identifier
            object_type: Object type API name
            primary_key: Object primary key
            link_type: Link type API name
            page_size: Number of results per page
            properties: List of properties to include

        Returns:
            List of linked object dictionaries
        """
        try:
            result = self.service.OntologyObject.list_linked_objects(
                ontology_rid,
                object_type,
                primary_key,
                link_type,
                page_size=page_size,
                select=properties,
            )
            objects = []
            for obj in result:
                objects.append(self._format_object(obj))
            return objects
        except Exception as e:
            raise RuntimeError(f"Failed to list linked objects: {e}")

    def count_objects(
        self,
        ontology_rid: str,
        object_type: str,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Count objects of a specific type.

        Args:
            ontology_rid: Ontology Resource Identifier
            object_type: Object type API name
            branch: Branch name (optional)

        Returns:
            Dictionary containing count information
        """
        try:
            count = self.service.OntologyObject.count(
                ontology_rid,
                object_type,
                branch=branch,
            )
            return {
                "ontology_rid": ontology_rid,
                "object_type": object_type,
                "count": count,
                "branch": branch,
            }
        except Exception as e:
            raise RuntimeError(f"Failed to count objects: {e}")

    def search_objects(
        self,
        ontology_rid: str,
        object_type: str,
        query: str,
        page_size: Optional[int] = None,
        properties: Optional[List[str]] = None,
        branch: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search objects by query.

        Args:
            ontology_rid: Ontology Resource Identifier
            object_type: Object type API name
            query: Search query string
            page_size: Number of results per page
            properties: List of properties to include
            branch: Branch name (optional)

        Returns:
            List of matching object dictionaries
        """
        try:
            result = self.service.OntologyObject.search(
                ontology_rid,
                object_type,
                query=query,
                page_size=page_size,
                select=properties,
                branch=branch,
            )
            objects = []
            for obj in result:
                objects.append(self._format_object(obj))
            return objects
        except Exception as e:
            raise RuntimeError(f"Failed to search objects: {e}")

    def _format_object(self, obj: Any) -> Dict[str, Any]:
        """Format object for consistent output."""
        # Objects may have various properties - extract them dynamically
        result = {}
        if hasattr(obj, "__dict__"):
            for key, value in obj.__dict__.items():
                if not key.startswith("_"):
                    result[key] = value
        return result


class ActionService(BaseService):
    """Service wrapper for action operations."""

    def _get_service(self) -> Any:
        """Get the Foundry ontologies service."""
        return self.client.ontologies

    def apply_action(
        self,
        ontology_rid: str,
        action_type: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Apply an action with given parameters.

        Args:
            ontology_rid: Ontology Resource Identifier
            action_type: Action type API name
            parameters: Action parameters

        Returns:
            Action result
        """
        try:
            result = self.service.Action.apply(ontology_rid, action_type, parameters)
            return self._format_action_result(result)
        except Exception as e:
            raise RuntimeError(f"Failed to apply action {action_type}: {e}")

    def validate_action(
        self,
        ontology_rid: str,
        action_type: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Validate action parameters without executing.

        Args:
            ontology_rid: Ontology Resource Identifier
            action_type: Action type API name
            parameters: Action parameters to validate

        Returns:
            Validation result
        """
        try:
            result = self.service.Action.validate(ontology_rid, action_type, parameters)
            return self._format_validation_result(result)
        except Exception as e:
            raise RuntimeError(f"Failed to validate action {action_type}: {e}")

    def apply_batch_actions(
        self,
        ontology_rid: str,
        action_type: str,
        requests: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Apply multiple actions of the same type.

        Args:
            ontology_rid: Ontology Resource Identifier
            action_type: Action type API name
            requests: List of action requests (max 20)

        Returns:
            List of action results
        """
        try:
            if len(requests) > 20:
                raise ValueError("Maximum 20 actions can be applied in a batch")

            result = self.service.Action.apply_batch(
                ontology_rid, action_type, requests
            )
            return [self._format_action_result(r) for r in result]
        except Exception as e:
            raise RuntimeError(f"Failed to apply batch actions: {e}")

    def _format_action_result(self, result: Any) -> Dict[str, Any]:
        """Format action result for consistent output."""
        return {
            "rid": getattr(result, "rid", None),
            "status": getattr(result, "status", None),
            "created_objects": getattr(result, "created_objects", []),
            "modified_objects": getattr(result, "modified_objects", []),
            "deleted_objects": getattr(result, "deleted_objects", []),
        }

    def _format_validation_result(self, result: Any) -> Dict[str, Any]:
        """Format validation result for consistent output."""
        return {
            "valid": getattr(result, "valid", False),
            "errors": getattr(result, "errors", []),
            "warnings": getattr(result, "warnings", []),
        }


class QueryService(BaseService):
    """Service wrapper for query operations."""

    def _get_service(self) -> Any:
        """Get the Foundry ontologies service."""
        return self.client.ontologies

    def execute_query(
        self,
        ontology_rid: str,
        query_api_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a predefined query.

        Args:
            ontology_rid: Ontology Resource Identifier
            query_api_name: Query API name
            parameters: Query parameters

        Returns:
            Query results
        """
        try:
            result = self.service.Query.execute(
                ontology_rid, query_api_name, parameters=parameters or {}
            )
            return self._format_query_result(result)
        except Exception as e:
            raise RuntimeError(f"Failed to execute query {query_api_name}: {e}")

    def _format_query_result(self, result: Any) -> Dict[str, Any]:
        """Format query result for consistent output."""
        # Query results can vary widely - extract what we can
        if hasattr(result, "rows"):
            return {"rows": result.rows, "columns": getattr(result, "columns", [])}
        elif hasattr(result, "objects"):
            return {"objects": result.objects}
        else:
            # Return as dict if possible
            return result if isinstance(result, dict) else {"result": str(result)}
