"""
Tests for ontology commands.
"""

import json
import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from pltr.commands.ontology import app

runner = CliRunner()


@pytest.fixture
def mock_services():
    """Mock all ontology services."""
    with (
        patch("pltr.commands.ontology.OntologyService") as mock_ont_svc,
        patch("pltr.commands.ontology.ObjectTypeService") as mock_obj_type_svc,
        patch("pltr.commands.ontology.OntologyObjectService") as mock_obj_svc,
        patch("pltr.commands.ontology.ActionService") as mock_action_svc,
        patch("pltr.commands.ontology.QueryService") as mock_query_svc,
    ):
        yield {
            "ontology": mock_ont_svc,
            "object_type": mock_obj_type_svc,
            "object": mock_obj_svc,
            "action": mock_action_svc,
            "query": mock_query_svc,
        }


# Ontology management command tests
def test_list_ontologies_command(mock_services):
    """Test list ontologies command."""
    mock_instance = Mock()
    mock_instance.list_ontologies.return_value = [
        {
            "rid": "ri.ontology.main.ontology.test",
            "api_name": "test_ontology",
            "display_name": "Test Ontology",
            "description": "A test ontology",
        }
    ]
    mock_services["ontology"].return_value = mock_instance

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 0
    mock_instance.list_ontologies.assert_called_once()


def test_get_ontology_command(mock_services):
    """Test get ontology command."""
    mock_instance = Mock()
    mock_instance.get_ontology.return_value = {
        "rid": "ri.ontology.main.ontology.test",
        "api_name": "test_ontology",
        "display_name": "Test Ontology",
        "description": "A test ontology",
    }
    mock_services["ontology"].return_value = mock_instance

    result = runner.invoke(app, ["get", "ri.ontology.main.ontology.test"])

    assert result.exit_code == 0
    mock_instance.get_ontology.assert_called_once_with("ri.ontology.main.ontology.test")


# Object Type command tests
def test_list_object_types_command(mock_services):
    """Test list object types command."""
    mock_instance = Mock()
    mock_instance.list_object_types.return_value = [
        {
            "api_name": "Employee",
            "display_name": "Employee",
            "description": "Employee object type",
            "primary_key": "employee_id",
        }
    ]
    mock_services["object_type"].return_value = mock_instance

    result = runner.invoke(app, ["object-type-list", "ri.ontology.main.ontology.test"])

    assert result.exit_code == 0
    mock_instance.list_object_types.assert_called_once()


def test_get_object_type_command(mock_services):
    """Test get object type command."""
    mock_instance = Mock()
    mock_instance.get_object_type.return_value = {
        "api_name": "Employee",
        "display_name": "Employee",
        "description": "Employee object type",
        "primary_key": "employee_id",
        "properties": {},
    }
    mock_services["object_type"].return_value = mock_instance

    result = runner.invoke(
        app, ["object-type-get", "ri.ontology.main.ontology.test", "Employee"]
    )

    assert result.exit_code == 0
    mock_instance.get_object_type.assert_called_once_with(
        "ri.ontology.main.ontology.test", "Employee"
    )


# Object operation command tests
def test_list_objects_command(mock_services):
    """Test list objects command."""
    mock_instance = Mock()
    mock_instance.list_objects.return_value = [
        {
            "employee_id": "EMP001",
            "name": "John Doe",
            "department": "Engineering",
        }
    ]
    mock_services["object"].return_value = mock_instance

    result = runner.invoke(
        app, ["object-list", "ri.ontology.main.ontology.test", "Employee"]
    )

    assert result.exit_code == 0
    mock_instance.list_objects.assert_called_once()


def test_list_objects_with_properties(mock_services):
    """Test list objects with specific properties."""
    mock_instance = Mock()
    mock_instance.list_objects.return_value = [
        {"employee_id": "EMP001", "name": "John Doe"}
    ]
    mock_services["object"].return_value = mock_instance

    result = runner.invoke(
        app,
        [
            "object-list",
            "ri.ontology.main.ontology.test",
            "Employee",
            "--properties",
            "employee_id,name",
        ],
    )

    assert result.exit_code == 0
    mock_instance.list_objects.assert_called_once()
    call_args = mock_instance.list_objects.call_args
    assert call_args[1]["properties"] == ["employee_id", "name"]


def test_get_object_command(mock_services):
    """Test get object command."""
    mock_instance = Mock()
    mock_instance.get_object.return_value = {
        "employee_id": "EMP001",
        "name": "John Doe",
        "department": "Engineering",
    }
    mock_services["object"].return_value = mock_instance

    result = runner.invoke(
        app, ["object-get", "ri.ontology.main.ontology.test", "Employee", "EMP001"]
    )

    assert result.exit_code == 0
    mock_instance.get_object.assert_called_once_with(
        "ri.ontology.main.ontology.test", "Employee", "EMP001", properties=None
    )


def test_aggregate_objects_command(mock_services):
    """Test aggregate objects command."""
    mock_instance = Mock()
    mock_instance.aggregate_objects.return_value = {"count": 10, "avg_salary": 75000}
    mock_services["object"].return_value = mock_instance

    aggregations = json.dumps([{"type": "count"}])
    result = runner.invoke(
        app,
        [
            "object-aggregate",
            "ri.ontology.main.ontology.test",
            "Employee",
            aggregations,
        ],
    )

    assert result.exit_code == 0
    mock_instance.aggregate_objects.assert_called_once()


def test_list_linked_objects_command(mock_services):
    """Test list linked objects command."""
    mock_instance = Mock()
    mock_instance.list_linked_objects.return_value = [
        {"employee_id": "EMP002", "name": "Jane Smith"}
    ]
    mock_services["object"].return_value = mock_instance

    result = runner.invoke(
        app,
        [
            "object-linked",
            "ri.ontology.main.ontology.test",
            "Employee",
            "EMP001",
            "manages",
        ],
    )

    assert result.exit_code == 0
    mock_instance.list_linked_objects.assert_called_once()


# Action command tests
def test_apply_action_command(mock_services):
    """Test apply action command."""
    mock_instance = Mock()
    mock_instance.apply_action.return_value = {
        "rid": "ri.action.result.123",
        "status": "SUCCESS",
        "created_objects": [],
        "modified_objects": ["EMP001"],
        "deleted_objects": [],
    }
    mock_services["action"].return_value = mock_instance

    params = json.dumps({"employee_id": "EMP001", "new_department": "Sales"})
    result = runner.invoke(
        app,
        ["action-apply", "ri.ontology.main.ontology.test", "transfer_employee", params],
    )

    assert result.exit_code == 0
    mock_instance.apply_action.assert_called_once()


def test_validate_action_command(mock_services):
    """Test validate action command."""
    mock_instance = Mock()
    mock_instance.validate_action.return_value = {
        "valid": True,
        "errors": [],
        "warnings": [],
    }
    mock_services["action"].return_value = mock_instance

    params = json.dumps({"employee_id": "EMP001", "new_department": "Sales"})
    result = runner.invoke(
        app,
        [
            "action-validate",
            "ri.ontology.main.ontology.test",
            "transfer_employee",
            params,
        ],
    )

    assert result.exit_code == 0
    assert "Action parameters are valid" in result.output
    mock_instance.validate_action.assert_called_once()


def test_validate_action_invalid(mock_services):
    """Test validate action with invalid parameters."""
    mock_instance = Mock()
    mock_instance.validate_action.return_value = {
        "valid": False,
        "errors": ["Missing required field: employee_id"],
        "warnings": [],
    }
    mock_services["action"].return_value = mock_instance

    params = json.dumps({"new_department": "Sales"})
    result = runner.invoke(
        app,
        [
            "action-validate",
            "ri.ontology.main.ontology.test",
            "transfer_employee",
            params,
        ],
    )

    assert result.exit_code == 0
    assert "Action parameters are invalid" in result.output
    mock_instance.validate_action.assert_called_once()


# Query command tests
def test_execute_query_command(mock_services):
    """Test execute query command."""
    mock_instance = Mock()
    mock_instance.execute_query.return_value = {
        "rows": [
            {"employee_id": "EMP001", "name": "John Doe"},
            {"employee_id": "EMP002", "name": "Jane Smith"},
        ],
        "columns": ["employee_id", "name"],
    }
    mock_services["query"].return_value = mock_instance

    result = runner.invoke(
        app, ["query-execute", "ri.ontology.main.ontology.test", "get_all_employees"]
    )

    assert result.exit_code == 0
    mock_instance.execute_query.assert_called_once()


def test_execute_query_with_parameters(mock_services):
    """Test execute query with parameters."""
    mock_instance = Mock()
    mock_instance.execute_query.return_value = {
        "rows": [{"employee_id": "EMP001", "name": "John Doe"}],
        "columns": ["employee_id", "name"],
    }
    mock_services["query"].return_value = mock_instance

    params = json.dumps({"department": "Engineering"})
    result = runner.invoke(
        app,
        [
            "query-execute",
            "ri.ontology.main.ontology.test",
            "get_employees_by_dept",
            "--parameters",
            params,
        ],
    )

    assert result.exit_code == 0
    mock_instance.execute_query.assert_called_once()
    call_args = mock_instance.execute_query.call_args
    assert call_args[1]["parameters"] == {"department": "Engineering"}


# Error handling tests
def test_authentication_error(mock_services):
    """Test handling of authentication errors."""
    from pltr.auth.base import ProfileNotFoundError

    mock_instance = Mock()
    mock_instance.list_ontologies.side_effect = ProfileNotFoundError(
        "Profile not found"
    )
    mock_services["ontology"].return_value = mock_instance

    result = runner.invoke(app, ["list"])

    assert result.exit_code == 1
    assert "Authentication error" in result.output


def test_invalid_json_parameters(mock_services):
    """Test handling of invalid JSON parameters."""
    result = runner.invoke(
        app,
        [
            "action-apply",
            "ri.ontology.main.ontology.test",
            "transfer_employee",
            "invalid json",
        ],
    )

    assert result.exit_code == 1
    assert "Invalid JSON" in result.output


def test_output_formats(mock_services):
    """Test different output formats."""
    mock_instance = Mock()
    mock_instance.list_ontologies.return_value = [
        {
            "rid": "ri.ontology.main.ontology.test",
            "api_name": "test_ontology",
            "display_name": "Test Ontology",
            "description": "A test ontology",
        }
    ]
    mock_services["ontology"].return_value = mock_instance

    # Test JSON format
    result = runner.invoke(app, ["list", "--format", "json"])
    assert result.exit_code == 0

    # Test CSV format
    result = runner.invoke(app, ["list", "--format", "csv"])
    assert result.exit_code == 0

    # Test output to file
    with patch("builtins.open", create=True):
        result = runner.invoke(app, ["list", "--output", "output.json"])
        assert result.exit_code == 0
        assert "Ontologies saved to output.json" in result.output
