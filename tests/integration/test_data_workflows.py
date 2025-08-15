"""
Integration tests for data workflows.

These tests verify complete data operation workflows including dataset operations,
SQL queries, and ontology object manipulations.
"""

import json
from unittest.mock import Mock, patch
from click.testing import CliRunner
import pytest

from pltr.cli import app
from pltr.config.profiles import ProfileManager


class TestDataWorkflows:
    """Test complete data operation workflows."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def authenticated_profile(self, temp_config_dir):
        """Create an authenticated profile for testing."""
        with patch.object(
            ProfileManager, "_get_config_dir", return_value=temp_config_dir
        ):
            profile_manager = ProfileManager()
            profile_manager.create_profile(
                "test",
                {
                    "auth_type": "token",
                    "host": "https://test.palantirfoundry.com",
                    "token": "test_token",
                },
            )
            profile_manager.set_default_profile("test")
            yield profile_manager

    def test_dataset_creation_and_retrieval_workflow(
        self, runner, authenticated_profile
    ):
        """Test creating a dataset and then retrieving it."""
        with patch("pltr.commands.dataset.AuthManager") as mock_auth_manager:
            with patch("pltr.services.dataset.DatasetService") as mock_dataset_service:
                mock_auth = Mock()
                mock_auth_manager.from_profile.return_value = mock_auth

                mock_service = Mock()

                # Mock dataset creation
                created_dataset = {
                    "rid": "ri.foundry.main.dataset.new-123",
                    "name": "New Test Dataset",
                    "created": {"time": "2024-01-01T00:00:00Z", "userId": "user-123"},
                    "parentFolderRid": "ri.foundry.main.folder.parent-456",
                }
                mock_service.create.return_value = created_dataset

                # Mock dataset retrieval
                mock_service.get.return_value = created_dataset

                mock_dataset_service.return_value = mock_service

                # Create dataset
                result = runner.invoke(
                    app,
                    [
                        "dataset",
                        "create",
                        "New Test Dataset",
                        "--parent-folder-rid",
                        "ri.foundry.main.folder.parent-456",
                    ],
                )
                assert result.exit_code == 0
                assert "New Test Dataset" in result.output
                assert "ri.foundry.main.dataset.new-123" in result.output

                # Retrieve the created dataset
                result = runner.invoke(
                    app, ["dataset", "get", "ri.foundry.main.dataset.new-123"]
                )
                assert result.exit_code == 0
                assert "New Test Dataset" in result.output

                # Verify service calls
                mock_service.create.assert_called_once_with(
                    name="New Test Dataset",
                    parent_folder_rid="ri.foundry.main.folder.parent-456",
                )
                mock_service.get.assert_called_once_with(
                    "ri.foundry.main.dataset.new-123"
                )

    def test_sql_query_workflow(self, runner, authenticated_profile):
        """Test SQL query submission, status checking, and results retrieval."""
        with patch("pltr.commands.sql.AuthManager") as mock_auth_manager:
            with patch("pltr.services.sql.SqlService") as mock_sql_service:
                mock_auth = Mock()
                mock_auth_manager.from_profile.return_value = mock_auth

                mock_service = Mock()
                query_id = "query-789"

                # Mock query submission
                mock_service.submit.return_value = query_id

                # Mock status checking (running -> succeeded)
                mock_service.get_status.side_effect = [
                    {"status": "running", "queryId": query_id},
                    {"status": "running", "queryId": query_id},
                    {"status": "succeeded", "queryId": query_id},
                ]

                # Mock results retrieval
                mock_service.get_results.return_value = {
                    "columns": [
                        {"name": "id", "type": "INTEGER"},
                        {"name": "value", "type": "DOUBLE"},
                    ],
                    "rows": [[1, 100.5], [2, 200.75], [3, 300.25]],
                }

                mock_sql_service.return_value = mock_service

                # Submit query
                result = runner.invoke(
                    app, ["sql", "submit", "SELECT id, value FROM metrics"]
                )
                assert result.exit_code == 0
                assert query_id in result.output

                # Check status
                result = runner.invoke(app, ["sql", "status", query_id])
                assert result.exit_code == 0

                # Wait for completion
                mock_service.wait.return_value = {
                    "status": "succeeded",
                    "queryId": query_id,
                }
                result = runner.invoke(
                    app, ["sql", "wait", query_id, "--timeout", "30"]
                )
                assert result.exit_code == 0
                assert "succeeded" in result.output.lower()

                # Get results
                result = runner.invoke(app, ["sql", "results", query_id])
                assert result.exit_code == 0
                assert "100.5" in result.output
                assert "200.75" in result.output
                assert "300.25" in result.output

    def test_sql_export_workflow(self, runner, authenticated_profile, tmp_path):
        """Test SQL query export to different formats."""
        with patch("pltr.commands.sql.AuthManager") as mock_auth_manager:
            with patch("pltr.services.sql.SqlService") as mock_sql_service:
                mock_auth = Mock()
                mock_auth_manager.from_profile.return_value = mock_auth

                mock_service = Mock()
                mock_service.execute.return_value = {
                    "columns": [
                        {"name": "name", "type": "STRING"},
                        {"name": "count", "type": "INTEGER"},
                    ],
                    "rows": [
                        ["Alice", 10],
                        ["Bob", 20],
                        ["Charlie", 15],
                    ],
                }
                mock_sql_service.return_value = mock_service

                # Export to CSV
                csv_file = tmp_path / "results.csv"
                result = runner.invoke(
                    app,
                    [
                        "sql",
                        "export",
                        "SELECT name, count FROM users",
                        "--output",
                        str(csv_file),
                        "--format",
                        "csv",
                    ],
                )
                assert result.exit_code == 0
                assert csv_file.exists()

                # Export to JSON
                json_file = tmp_path / "results.json"
                result = runner.invoke(
                    app,
                    [
                        "sql",
                        "export",
                        "SELECT name, count FROM users",
                        "--output",
                        str(json_file),
                        "--format",
                        "json",
                    ],
                )
                assert result.exit_code == 0
                assert json_file.exists()

    def test_ontology_object_operations_workflow(self, runner, authenticated_profile):
        """Test ontology object listing, retrieval, and linked object navigation."""
        with patch("pltr.commands.ontology.AuthManager") as mock_auth_manager:
            with patch(
                "pltr.services.ontology.OntologyService"
            ) as mock_ontology_service:
                with patch(
                    "pltr.services.ontology.OntologyObjectService"
                ) as mock_object_service:
                    mock_auth = Mock()
                    mock_auth_manager.from_profile.return_value = mock_auth

                    # Mock ontology service
                    mock_ont_service = Mock()
                    mock_ont_service.list.return_value = [
                        {
                            "rid": "ri.ontology.main.ontology.test-123",
                            "apiName": "test-ontology",
                            "displayName": "Test Ontology",
                        }
                    ]
                    mock_ontology_service.return_value = mock_ont_service

                    # Mock object service
                    mock_obj_service = Mock()

                    # Mock object listing with pagination
                    mock_obj_service.list.side_effect = [
                        {
                            "data": [
                                {
                                    "primaryKey": "obj-1",
                                    "properties": {"name": "Object 1"},
                                },
                                {
                                    "primaryKey": "obj-2",
                                    "properties": {"name": "Object 2"},
                                },
                            ],
                            "nextPageToken": "token-123",
                        },
                        {
                            "data": [
                                {
                                    "primaryKey": "obj-3",
                                    "properties": {"name": "Object 3"},
                                },
                            ],
                            "nextPageToken": None,
                        },
                    ]

                    # Mock single object retrieval
                    mock_obj_service.get.return_value = {
                        "primaryKey": "obj-1",
                        "properties": {
                            "name": "Object 1",
                            "type": "TypeA",
                            "value": 100,
                        },
                    }

                    # Mock linked objects
                    mock_obj_service.get_linked.return_value = {
                        "data": [
                            {
                                "primaryKey": "linked-1",
                                "properties": {"name": "Linked 1"},
                            },
                            {
                                "primaryKey": "linked-2",
                                "properties": {"name": "Linked 2"},
                            },
                        ]
                    }

                    mock_object_service.return_value = mock_obj_service

                    # List ontologies
                    result = runner.invoke(app, ["ontology", "list"])
                    assert result.exit_code == 0
                    assert "Test Ontology" in result.output

                    # List objects
                    result = runner.invoke(
                        app,
                        [
                            "ontology",
                            "object-list",
                            "ri.ontology.main.ontology.test-123",
                            "Person",
                        ],
                    )
                    assert result.exit_code == 0

                    # Get specific object
                    result = runner.invoke(
                        app,
                        [
                            "ontology",
                            "object-get",
                            "ri.ontology.main.ontology.test-123",
                            "Person",
                            "obj-1",
                        ],
                    )
                    assert result.exit_code == 0
                    assert "Object 1" in result.output

                    # Get linked objects
                    result = runner.invoke(
                        app,
                        [
                            "ontology",
                            "object-linked",
                            "ri.ontology.main.ontology.test-123",
                            "Person",
                            "obj-1",
                            "relatedTo",
                        ],
                    )
                    assert result.exit_code == 0
                    assert "Linked 1" in result.output
                    assert "Linked 2" in result.output

    def test_ontology_action_workflow(self, runner, authenticated_profile):
        """Test ontology action validation and application."""
        with patch("pltr.commands.ontology.AuthManager") as mock_auth_manager:
            with patch("pltr.services.ontology.ActionService") as mock_action_service:
                mock_auth = Mock()
                mock_auth_manager.from_profile.return_value = mock_auth

                mock_service = Mock()

                # Mock action validation
                mock_service.validate.return_value = {
                    "valid": True,
                    "parameters": {
                        "input1": "value1",
                        "input2": 123,
                    },
                }

                # Mock action application
                mock_service.apply.return_value = {
                    "success": True,
                    "results": {
                        "output1": "result1",
                        "output2": 456,
                    },
                }

                mock_action_service.return_value = mock_service

                # Validate action
                params = json.dumps({"input1": "value1", "input2": 123})
                result = runner.invoke(
                    app,
                    [
                        "ontology",
                        "action-validate",
                        "ri.ontology.main.ontology.test-123",
                        "updateEntity",
                        "--parameters",
                        params,
                    ],
                )
                assert result.exit_code == 0
                assert "valid" in result.output.lower()

                # Apply action
                result = runner.invoke(
                    app,
                    [
                        "ontology",
                        "action-apply",
                        "ri.ontology.main.ontology.test-123",
                        "updateEntity",
                        "--parameters",
                        params,
                    ],
                )
                assert result.exit_code == 0
                assert "success" in result.output.lower()

    def test_batch_operations_workflow(self, runner, authenticated_profile):
        """Test batch operations across multiple datasets."""
        with patch("pltr.commands.dataset.AuthManager") as mock_auth_manager:
            with patch("pltr.services.dataset.DatasetService") as mock_dataset_service:
                mock_auth = Mock()
                mock_auth_manager.from_profile.return_value = mock_auth

                mock_service = Mock()

                # Mock multiple dataset retrievals
                datasets = [
                    {
                        "rid": f"ri.foundry.main.dataset.batch-{i}",
                        "name": f"Batch Dataset {i}",
                        "created": {
                            "time": "2024-01-01T00:00:00Z",
                            "userId": "user-123",
                        },
                    }
                    for i in range(1, 4)
                ]
                mock_service.get.side_effect = datasets

                mock_dataset_service.return_value = mock_service

                # Retrieve multiple datasets
                for i in range(1, 4):
                    result = runner.invoke(
                        app,
                        ["dataset", "get", f"ri.foundry.main.dataset.batch-{i}"],
                    )
                    assert result.exit_code == 0
                    assert f"Batch Dataset {i}" in result.output

                # Verify all calls were made
                assert mock_service.get.call_count == 3

    def test_error_recovery_workflow(self, runner, authenticated_profile):
        """Test error handling and recovery in workflows."""
        with patch("pltr.commands.sql.AuthManager") as mock_auth_manager:
            with patch("pltr.services.sql.SqlService") as mock_sql_service:
                mock_auth = Mock()
                mock_auth_manager.from_profile.return_value = mock_auth

                mock_service = Mock()

                # Mock query failure
                query_id = "failed-query-123"
                mock_service.submit.return_value = query_id
                mock_service.get_status.return_value = {
                    "status": "failed",
                    "queryId": query_id,
                    "error": "Syntax error in SQL query",
                }

                mock_sql_service.return_value = mock_service

                # Submit bad query
                result = runner.invoke(app, ["sql", "submit", "SELECT * FROM"])
                assert result.exit_code == 0
                assert query_id in result.output

                # Check failed status
                result = runner.invoke(app, ["sql", "status", query_id])
                assert result.exit_code == 0
                assert "failed" in result.output.lower()
                assert "Syntax error" in result.output

                # Attempt to get results (should fail gracefully)
                mock_service.get_results.side_effect = Exception(
                    "Query failed, no results available"
                )
                result = runner.invoke(app, ["sql", "results", query_id])
                assert result.exit_code == 1
                assert "Error" in result.output or "error" in result.output.lower()

    def test_pagination_workflow(self, runner, authenticated_profile):
        """Test pagination handling in list operations."""
        with patch("pltr.commands.ontology.AuthManager") as mock_auth_manager:
            with patch(
                "pltr.services.ontology.OntologyObjectService"
            ) as mock_object_service:
                mock_auth = Mock()
                mock_auth_manager.from_profile.return_value = mock_auth

                mock_service = Mock()

                # Mock paginated responses
                pages = [
                    {
                        "data": [
                            {
                                "primaryKey": f"obj-{i}",
                                "properties": {"name": f"Object {i}"},
                            }
                            for i in range(1, 11)
                        ],
                        "nextPageToken": "page-2",
                    },
                    {
                        "data": [
                            {
                                "primaryKey": f"obj-{i}",
                                "properties": {"name": f"Object {i}"},
                            }
                            for i in range(11, 21)
                        ],
                        "nextPageToken": "page-3",
                    },
                    {
                        "data": [
                            {
                                "primaryKey": f"obj-{i}",
                                "properties": {"name": f"Object {i}"},
                            }
                            for i in range(21, 26)
                        ],
                        "nextPageToken": None,
                    },
                ]
                mock_service.list.side_effect = pages

                mock_object_service.return_value = mock_service

                # List with limit
                result = runner.invoke(
                    app,
                    [
                        "ontology",
                        "object-list",
                        "ri.ontology.main.ontology.test-123",
                        "Person",
                        "--limit",
                        "25",
                    ],
                )
                assert result.exit_code == 0
                # Should have fetched multiple pages
                assert mock_service.list.call_count >= 2
