"""
Tests for ontology services.
"""

import pytest
from unittest.mock import Mock, patch

from pltr.services.ontology import (
    OntologyService,
    ObjectTypeService,
    OntologyObjectService,
    ActionService,
    QueryService,
)


@pytest.fixture
def mock_ontology_service():
    """Create a mocked OntologyService."""
    with patch("pltr.services.base.AuthManager") as mock_auth:
        # Set up client mock
        mock_client = Mock()
        mock_ontologies = Mock()
        mock_ontology_class = Mock()
        mock_ontologies.Ontology = mock_ontology_class
        mock_client.ontologies = mock_ontologies
        mock_auth.return_value.get_client.return_value = mock_client

        # Create service
        service = OntologyService()
        return service, mock_ontology_class


@pytest.fixture
def mock_object_type_service():
    """Create a mocked ObjectTypeService."""
    with patch("pltr.services.base.AuthManager") as mock_auth:
        # Set up client mock
        mock_client = Mock()
        mock_ontologies = Mock()
        mock_ontology_class = Mock()
        mock_object_type_class = Mock()
        # ObjectType is nested under Ontology in the SDK
        mock_ontology_class.ObjectType = mock_object_type_class
        mock_ontologies.Ontology = mock_ontology_class
        mock_client.ontologies = mock_ontologies
        mock_auth.return_value.get_client.return_value = mock_client

        # Create service
        service = ObjectTypeService()
        return service, mock_object_type_class


@pytest.fixture
def mock_ontology_object_service():
    """Create a mocked OntologyObjectService."""
    with patch("pltr.services.base.AuthManager") as mock_auth:
        # Set up client mock
        mock_client = Mock()
        mock_ontologies = Mock()
        mock_ontology_object_class = Mock()
        mock_ontologies.OntologyObject = mock_ontology_object_class
        mock_client.ontologies = mock_ontologies
        mock_auth.return_value.get_client.return_value = mock_client

        # Create service
        service = OntologyObjectService()
        return service, mock_ontology_object_class


@pytest.fixture
def mock_action_service():
    """Create a mocked ActionService."""
    with patch("pltr.services.base.AuthManager") as mock_auth:
        # Set up client mock
        mock_client = Mock()
        mock_ontologies = Mock()
        mock_action_class = Mock()
        mock_ontologies.Action = mock_action_class
        mock_client.ontologies = mock_ontologies
        mock_auth.return_value.get_client.return_value = mock_client

        # Create service
        service = ActionService()
        return service, mock_action_class


@pytest.fixture
def mock_query_service():
    """Create a mocked QueryService."""
    with patch("pltr.services.base.AuthManager") as mock_auth:
        # Set up client mock
        mock_client = Mock()
        mock_ontologies = Mock()
        mock_query_class = Mock()
        mock_ontologies.Query = mock_query_class
        mock_client.ontologies = mock_ontologies
        mock_auth.return_value.get_client.return_value = mock_client

        # Create service
        service = QueryService()
        return service, mock_query_class


@pytest.fixture
def sample_ontology():
    """Create sample ontology object."""
    ontology = Mock()
    ontology.rid = "ri.ontology.main.ontology.test"
    ontology.api_name = "test_ontology"
    ontology.display_name = "Test Ontology"
    ontology.description = "A test ontology"
    return ontology


@pytest.fixture
def sample_object_type():
    """Create sample object type."""
    obj_type = Mock()
    obj_type.api_name = "Employee"
    obj_type.display_name = "Employee"
    obj_type.description = "Employee object type"
    obj_type.primary_key = "employee_id"
    obj_type.properties = {
        "employee_id": {"type": "string"},
        "name": {"type": "string"},
        "department": {"type": "string"},
    }
    return obj_type


@pytest.fixture
def sample_object():
    """Create sample ontology object."""
    obj = Mock(spec=[])  # Add spec to avoid Mock attribute issues
    obj.employee_id = "EMP001"
    obj.name = "John Doe"
    obj.department = "Engineering"
    obj.__dict__ = {
        "employee_id": "EMP001",
        "name": "John Doe",
        "department": "Engineering",
    }
    return obj


@pytest.fixture
def sample_action_result():
    """Create sample action result."""
    result = Mock()
    result.rid = "ri.action.result.123"
    result.status = "SUCCESS"
    result.created_objects = []
    result.modified_objects = ["EMP001"]
    result.deleted_objects = []
    return result


@pytest.fixture
def sample_validation_result():
    """Create sample validation result."""
    result = Mock()
    result.valid = True
    result.errors = []
    result.warnings = []
    return result


@pytest.fixture
def sample_query_result():
    """Create sample query result."""
    result = Mock()
    result.rows = [
        {"employee_id": "EMP001", "name": "John Doe"},
        {"employee_id": "EMP002", "name": "Jane Smith"},
    ]
    result.columns = ["employee_id", "name"]
    return result


# OntologyService Tests
def test_ontology_service_initialization():
    """Test OntologyService initialization."""
    with patch("pltr.services.base.AuthManager"):
        service = OntologyService()
        assert service is not None
        assert service.auth_manager is not None


def test_list_ontologies(mock_ontology_service, sample_ontology):
    """Test listing ontologies."""
    service, mock_ontology_class = mock_ontology_service
    # Mock the response with a 'data' field
    mock_response = Mock()
    mock_response.data = [sample_ontology]
    mock_ontology_class.list.return_value = mock_response

    result = service.list_ontologies()

    assert len(result) == 1
    assert result[0]["rid"] == "ri.ontology.main.ontology.test"
    assert result[0]["api_name"] == "test_ontology"
    mock_ontology_class.list.assert_called_once()


def test_get_ontology(mock_ontology_service, sample_ontology):
    """Test getting a specific ontology."""
    service, mock_ontology_class = mock_ontology_service
    mock_ontology_class.get.return_value = sample_ontology

    result = service.get_ontology("ri.ontology.main.ontology.test")

    assert result["rid"] == "ri.ontology.main.ontology.test"
    assert result["api_name"] == "test_ontology"
    mock_ontology_class.get.assert_called_once_with("ri.ontology.main.ontology.test")


# ObjectTypeService Tests
def test_list_object_types(mock_object_type_service, sample_object_type):
    """Test listing object types."""
    service, mock_object_type_class = mock_object_type_service
    # Mock the response with a 'data' field
    mock_response = Mock()
    mock_response.data = [sample_object_type]
    mock_object_type_class.list.return_value = mock_response

    result = service.list_object_types("ri.ontology.main.ontology.test")

    assert len(result) == 1
    assert result[0]["api_name"] == "Employee"
    assert result[0]["primary_key"] == "employee_id"
    mock_object_type_class.list.assert_called_once_with(
        "ri.ontology.main.ontology.test"
    )


def test_get_object_type(mock_object_type_service, sample_object_type):
    """Test getting a specific object type."""
    service, mock_object_type_class = mock_object_type_service
    mock_object_type_class.get.return_value = sample_object_type

    result = service.get_object_type("ri.ontology.main.ontology.test", "Employee")

    assert result["api_name"] == "Employee"
    assert result["primary_key"] == "employee_id"
    mock_object_type_class.get.assert_called_once_with(
        "ri.ontology.main.ontology.test", "Employee"
    )


# OntologyObjectService Tests
def test_list_objects(mock_ontology_object_service, sample_object):
    """Test listing objects."""
    service, mock_ontology_object_class = mock_ontology_object_service
    mock_ontology_object_class.list.return_value = [sample_object]

    result = service.list_objects("ri.ontology.main.ontology.test", "Employee")

    assert len(result) == 1
    assert result[0]["employee_id"] == "EMP001"
    assert result[0]["name"] == "John Doe"
    mock_ontology_object_class.list.assert_called_once()


def test_get_object():
    """Test getting a specific object."""
    with patch("pltr.services.base.AuthManager") as mock_auth:
        # Set up client mock
        mock_client = Mock()
        mock_ontologies = Mock()
        mock_ontology_object_class = Mock()

        # Create a simple mock object with the required attributes
        mock_obj = type(
            "MockObject",
            (),
            {
                "employee_id": "EMP001",
                "name": "John Doe",
                "department": "Engineering",
                "__dict__": {
                    "employee_id": "EMP001",
                    "name": "John Doe",
                    "department": "Engineering",
                },
            },
        )()

        mock_ontology_object_class.get.return_value = mock_obj
        mock_ontologies.OntologyObject = mock_ontology_object_class
        mock_client.ontologies = mock_ontologies
        mock_auth.return_value.get_client.return_value = mock_client

        # Create service and test
        service = OntologyObjectService()
        result = service.get_object(
            "ri.ontology.main.ontology.test", "Employee", "EMP001"
        )

        assert result["employee_id"] == "EMP001"
        assert result["name"] == "John Doe"
        mock_ontology_object_class.get.assert_called_once()


def test_aggregate_objects(mock_ontology_object_service):
    """Test aggregating objects."""
    service, mock_ontology_object_class = mock_ontology_object_service
    mock_result = {"count": 10, "avg_salary": 75000}
    mock_ontology_object_class.aggregate.return_value = mock_result

    aggregations = [{"type": "count"}, {"type": "avg", "field": "salary"}]
    result = service.aggregate_objects(
        "ri.ontology.main.ontology.test", "Employee", aggregations
    )

    assert result["count"] == 10
    assert result["avg_salary"] == 75000
    mock_ontology_object_class.aggregate.assert_called_once()


def test_list_linked_objects(mock_ontology_object_service, sample_object):
    """Test listing linked objects."""
    service, mock_ontology_object_class = mock_ontology_object_service
    mock_ontology_object_class.list_linked_objects.return_value = [sample_object]

    result = service.list_linked_objects(
        "ri.ontology.main.ontology.test",
        "Employee",
        "EMP001",
        "manages",
    )

    assert len(result) == 1
    assert result[0]["employee_id"] == "EMP001"
    mock_ontology_object_class.list_linked_objects.assert_called_once()


# ActionService Tests
def test_apply_action(mock_action_service, sample_action_result):
    """Test applying an action."""
    service, mock_action_class = mock_action_service
    mock_action_class.apply.return_value = sample_action_result

    params = {"employee_id": "EMP001", "new_department": "Sales"}
    result = service.apply_action(
        "ri.ontology.main.ontology.test", "transfer_employee", params
    )

    assert result["status"] == "SUCCESS"
    assert "EMP001" in result["modified_objects"]
    mock_action_class.apply.assert_called_once()


def test_validate_action(mock_action_service, sample_validation_result):
    """Test validating an action."""
    service, mock_action_class = mock_action_service
    mock_action_class.validate.return_value = sample_validation_result

    params = {"employee_id": "EMP001", "new_department": "Sales"}
    result = service.validate_action(
        "ri.ontology.main.ontology.test", "transfer_employee", params
    )

    assert result["valid"] is True
    assert len(result["errors"]) == 0
    mock_action_class.validate.assert_called_once()


def test_apply_batch_actions(mock_action_service, sample_action_result):
    """Test applying batch actions."""
    service, mock_action_class = mock_action_service
    mock_action_class.apply_batch.return_value = [
        sample_action_result,
        sample_action_result,
    ]

    requests = [
        {"employee_id": "EMP001", "new_department": "Sales"},
        {"employee_id": "EMP002", "new_department": "Marketing"},
    ]
    result = service.apply_batch_actions(
        "ri.ontology.main.ontology.test", "transfer_employee", requests
    )

    assert len(result) == 2
    assert result[0]["status"] == "SUCCESS"
    mock_action_class.apply_batch.assert_called_once()


def test_apply_batch_actions_exceeds_limit(mock_action_service):
    """Test that batch actions fail when exceeding limit."""
    service, _ = mock_action_service

    # Create 21 requests (exceeds limit of 20)
    requests = [{"employee_id": f"EMP{i}"} for i in range(21)]

    with pytest.raises(RuntimeError) as excinfo:
        service.apply_batch_actions(
            "ri.ontology.main.ontology.test", "transfer_employee", requests
        )

    assert "Maximum 20 actions" in str(excinfo.value)


# QueryService Tests
def test_execute_query(mock_query_service, sample_query_result):
    """Test executing a query."""
    service, mock_query_class = mock_query_service
    mock_query_class.execute.return_value = sample_query_result

    params = {"department": "Engineering"}
    result = service.execute_query(
        "ri.ontology.main.ontology.test", "get_employees_by_dept", params
    )

    assert len(result["rows"]) == 2
    assert result["columns"] == ["employee_id", "name"]
    mock_query_class.execute.assert_called_once()


def test_execute_query_with_objects_result(mock_query_service):
    """Test executing a query that returns objects."""
    service, mock_query_class = mock_query_service
    # Create a mock with spec to control attributes
    mock_result = Mock(spec=["objects"])
    mock_result.objects = [{"id": "1", "name": "Test"}]
    mock_query_class.execute.return_value = mock_result

    result = service.execute_query("ri.ontology.main.ontology.test", "get_all_objects")

    assert "objects" in result
    assert len(result["objects"]) == 1
    mock_query_class.execute.assert_called_once()
