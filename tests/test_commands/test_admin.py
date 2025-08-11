"""
Tests for Admin commands.
"""

import pytest
from unittest.mock import Mock, patch
from typer.testing import CliRunner

from pltr.commands.admin import app
from pltr.services.admin import AdminService


class TestAdminCommands:
    """Test Admin CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock Admin service."""
        return Mock(spec=AdminService)

    # User Commands Tests
    def test_user_list_command_success(self, runner, mock_service):
        """Test successful user list command."""
        # Setup
        user_result = {
            "users": [
                {"id": "user1", "username": "john.doe", "email": "john@example.com"},
                {"id": "user2", "username": "jane.doe", "email": "jane@example.com"},
            ],
            "nextPageToken": None,
        }
        mock_service.list_users.return_value = user_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["user", "list", "--format", "json"])

        # Assert
        assert result.exit_code == 0
        mock_service.list_users.assert_called_once_with(page_size=None, page_token=None)

    def test_user_list_with_pagination(self, runner, mock_service):
        """Test user list command with pagination."""
        # Setup
        user_result = {"users": [], "nextPageToken": "next123"}
        mock_service.list_users.return_value = user_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                app, ["user", "list", "--page-size", "10", "--page-token", "prev123"]
            )

        # Assert
        assert result.exit_code == 0
        mock_service.list_users.assert_called_once_with(
            page_size=10, page_token="prev123"
        )

    def test_user_get_command_success(self, runner, mock_service):
        """Test successful user get command."""
        # Setup
        user_id = "user123"
        user_result = {
            "id": user_id,
            "username": "john.doe",
            "email": "john@example.com",
            "displayName": "John Doe",
        }
        mock_service.get_user.return_value = user_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["user", "get", user_id])

        # Assert
        assert result.exit_code == 0
        mock_service.get_user.assert_called_once_with(user_id)

    def test_user_current_command_success(self, runner, mock_service):
        """Test successful user current command."""
        # Setup
        user_result = {
            "id": "current_user",
            "username": "current.user",
            "email": "current@example.com",
        }
        mock_service.get_current_user.return_value = user_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["user", "current", "--format", "table"])

        # Assert
        assert result.exit_code == 0
        mock_service.get_current_user.assert_called_once()

    def test_user_search_command_success(self, runner, mock_service):
        """Test successful user search command."""
        # Setup
        query = "john"
        search_result = {
            "users": [{"id": "user1", "username": "john.doe"}],
            "nextPageToken": None,
        }
        mock_service.search_users.return_value = search_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["user", "search", query])

        # Assert
        assert result.exit_code == 0
        mock_service.search_users.assert_called_once_with(
            query=query, page_size=None, page_token=None
        )

    def test_user_markings_command_success(self, runner, mock_service):
        """Test successful user markings command."""
        # Setup
        user_id = "user123"
        markings_result = {
            "markings": ["public", "internal"],
            "permissions": ["read", "write"],
        }
        mock_service.get_user_markings.return_value = markings_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["user", "markings", user_id])

        # Assert
        assert result.exit_code == 0
        mock_service.get_user_markings.assert_called_once_with(user_id)

    def test_user_revoke_tokens_command_with_confirm(self, runner, mock_service):
        """Test user revoke tokens command with confirmation."""
        # Setup
        user_id = "user123"
        revoke_result = {
            "success": True,
            "message": f"All tokens revoked for user {user_id}",
        }
        mock_service.revoke_user_tokens.return_value = revoke_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["user", "revoke-tokens", user_id, "--confirm"])

        # Assert
        assert result.exit_code == 0
        mock_service.revoke_user_tokens.assert_called_once_with(user_id)

    # Group Commands Tests
    def test_group_list_command_success(self, runner, mock_service):
        """Test successful group list command."""
        # Setup
        group_result = {
            "groups": [
                {"id": "group1", "name": "Engineering", "description": "Dev team"},
                {"id": "group2", "name": "Product", "description": "Product team"},
            ],
            "nextPageToken": None,
        }
        mock_service.list_groups.return_value = group_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["group", "list"])

        # Assert
        assert result.exit_code == 0
        mock_service.list_groups.assert_called_once_with(
            page_size=None, page_token=None
        )

    def test_group_get_command_success(self, runner, mock_service):
        """Test successful group get command."""
        # Setup
        group_id = "group123"
        group_result = {
            "id": group_id,
            "name": "Engineering",
            "description": "Engineering team",
        }
        mock_service.get_group.return_value = group_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["group", "get", group_id])

        # Assert
        assert result.exit_code == 0
        mock_service.get_group.assert_called_once_with(group_id)

    def test_group_search_command_success(self, runner, mock_service):
        """Test successful group search command."""
        # Setup
        query = "engineering"
        search_result = {
            "groups": [{"id": "group1", "name": "Engineering"}],
            "nextPageToken": None,
        }
        mock_service.search_groups.return_value = search_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["group", "search", query, "--page-size", "5"])

        # Assert
        assert result.exit_code == 0
        mock_service.search_groups.assert_called_once_with(
            query=query, page_size=5, page_token=None
        )

    def test_group_create_command_success(self, runner, mock_service):
        """Test successful group create command."""
        # Setup
        group_name = "New Team"
        description = "A new team"
        org_rid = "org123"
        create_result = {
            "id": "new_group_id",
            "name": group_name,
            "description": description,
        }
        mock_service.create_group.return_value = create_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                app,
                [
                    "group",
                    "create",
                    group_name,
                    "--description",
                    description,
                    "--org-rid",
                    org_rid,
                ],
            )

        # Assert
        assert result.exit_code == 0
        mock_service.create_group.assert_called_once_with(
            name=group_name, description=description, organization_rid=org_rid
        )

    def test_group_create_command_minimal(self, runner, mock_service):
        """Test group create command with minimal parameters."""
        # Setup
        group_name = "Simple Group"
        create_result = {"id": "simple_group_id", "name": group_name}
        mock_service.create_group.return_value = create_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["group", "create", group_name])

        # Assert
        assert result.exit_code == 0
        mock_service.create_group.assert_called_once_with(
            name=group_name, description=None, organization_rid=None
        )

    def test_group_delete_command_with_confirm(self, runner, mock_service):
        """Test group delete command with confirmation."""
        # Setup
        group_id = "group123"
        delete_result = {
            "success": True,
            "message": f"Group {group_id} deleted successfully",
        }
        mock_service.delete_group.return_value = delete_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["group", "delete", group_id, "--confirm"])

        # Assert
        assert result.exit_code == 0
        mock_service.delete_group.assert_called_once_with(group_id)

    # Role Commands Tests
    def test_role_get_command_success(self, runner, mock_service):
        """Test successful role get command."""
        # Setup
        role_id = "role123"
        role_result = {
            "id": role_id,
            "name": "Admin",
            "description": "Administrator role",
        }
        mock_service.get_role.return_value = role_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["role", "get", role_id])

        # Assert
        assert result.exit_code == 0
        mock_service.get_role.assert_called_once_with(role_id)

    # Organization Commands Tests
    def test_org_get_command_success(self, runner, mock_service):
        """Test successful organization get command."""
        # Setup
        org_id = "org123"
        org_result = {
            "id": org_id,
            "name": "Acme Corp",
            "description": "Example organization",
        }
        mock_service.get_organization.return_value = org_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["org", "get", org_id])

        # Assert
        assert result.exit_code == 0
        mock_service.get_organization.assert_called_once_with(org_id)

    # Error Handling Tests
    def test_user_list_command_error(self, runner, mock_service):
        """Test user list command error handling."""
        # Setup
        mock_service.list_users.side_effect = RuntimeError("API Error")

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["user", "list"])

        # Assert
        assert result.exit_code == 1
        assert "Error:" in result.stdout

    def test_user_get_command_error(self, runner, mock_service):
        """Test user get command error handling."""
        # Setup
        user_id = "user123"
        mock_service.get_user.side_effect = RuntimeError("User not found")

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["user", "get", user_id])

        # Assert
        assert result.exit_code == 1
        assert "Error:" in result.stdout

    def test_group_create_command_error(self, runner, mock_service):
        """Test group create command error handling."""
        # Setup
        group_name = "Bad Group"
        mock_service.create_group.side_effect = RuntimeError("Validation error")

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["group", "create", group_name])

        # Assert
        assert result.exit_code == 1
        assert "Error:" in result.stdout

    # Profile Parameter Tests
    def test_user_list_with_profile(self, runner, mock_service):
        """Test user list command with profile parameter."""
        # Setup
        profile_name = "prod"
        user_result = {"users": [], "nextPageToken": None}
        mock_service.list_users.return_value = user_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(app, ["user", "list", "--profile", profile_name])

        # Assert
        assert result.exit_code == 0
        mock_service_class.assert_called_once_with(profile=profile_name)

    def test_group_get_with_profile(self, runner, mock_service):
        """Test group get command with profile parameter."""
        # Setup
        profile_name = "dev"
        group_id = "group123"
        group_result = {"id": group_id, "name": "Test Group"}
        mock_service.get_group.return_value = group_result

        with patch("pltr.commands.admin.AdminService") as mock_service_class:
            mock_service_class.return_value = mock_service

            result = runner.invoke(
                app, ["group", "get", group_id, "--profile", profile_name]
            )

        # Assert
        assert result.exit_code == 0
        mock_service_class.assert_called_once_with(profile=profile_name)

    # Output Format Tests
    def test_user_list_json_format(self, runner, mock_service):
        """Test user list command with JSON format."""
        # Setup
        user_result = {"users": [{"id": "user1", "username": "john"}]}
        mock_service.list_users.return_value = user_result

        with (
            patch("pltr.commands.admin.AdminService") as mock_service_class,
            patch("pltr.commands.admin.OutputFormatter") as mock_formatter,
        ):
            mock_service_class.return_value = mock_service
            mock_formatter_instance = Mock()
            mock_formatter.return_value = mock_formatter_instance

            result = runner.invoke(app, ["user", "list", "--format", "json"])

        # Assert
        assert result.exit_code == 0
        mock_formatter_instance.display.assert_called_once_with(user_result, "json")

    def test_group_create_csv_format(self, runner, mock_service):
        """Test group create command with CSV format."""
        # Setup
        group_name = "CSV Group"
        create_result = {"id": "csv_group", "name": group_name}
        mock_service.create_group.return_value = create_result

        with (
            patch("pltr.commands.admin.AdminService") as mock_service_class,
            patch("pltr.commands.admin.OutputFormatter") as mock_formatter,
        ):
            mock_service_class.return_value = mock_service
            mock_formatter_instance = Mock()
            mock_formatter.return_value = mock_formatter_instance

            result = runner.invoke(
                app, ["group", "create", group_name, "--format", "csv"]
            )

        # Assert
        assert result.exit_code == 0
        mock_formatter_instance.display.assert_called_once_with(create_result, "csv")
