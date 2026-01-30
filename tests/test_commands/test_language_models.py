"""Tests for LanguageModels commands."""

import pytest
import json
from unittest.mock import Mock, patch
from typer.testing import CliRunner
from pltr.cli import app


class TestLanguageModelsCommands:
    """Test LanguageModels CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_service(self):
        """Create mock LanguageModelsService."""
        with patch(
            "pltr.services.language_models.LanguageModelsService"
        ) as MockService:
            mock_svc = Mock()
            MockService.return_value = mock_svc
            yield mock_svc

    # ===== Anthropic Messages Tests =====

    def test_anthropic_messages_success(self, runner, mock_service):
        """Test successful anthropic messages command."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        response = {
            "content": [{"type": "text", "text": "Hello!"}],
            "role": "assistant",
            "usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
        }
        mock_service.send_message.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "anthropic",
                "messages",
                model_id,
                "--message",
                "Hello",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.send_message.assert_called_once_with(
            model_id=model_id,
            message="Hello",
            max_tokens=1024,
            system=None,
            temperature=None,
            stop_sequences=None,
            top_k=None,
            top_p=None,
            preview=False,
        )

    def test_anthropic_messages_with_system(self, runner, mock_service):
        """Test anthropic messages with system prompt."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        response = {
            "content": [{"type": "text", "text": "A haiku"}],
            "role": "assistant",
            "usage": {"inputTokens": 15, "outputTokens": 10, "totalTokens": 25},
        }
        mock_service.send_message.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "anthropic",
                "messages",
                model_id,
                "--message",
                "Write a haiku",
                "--system",
                "You are a poet",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_args = mock_service.send_message.call_args
        assert call_args[1]["system"] == "You are a poet"

    def test_anthropic_messages_with_all_parameters(self, runner, mock_service):
        """Test anthropic messages with all parameters."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        response = {
            "content": [{"type": "text", "text": "Response"}],
            "role": "assistant",
            "usage": {"inputTokens": 20, "outputTokens": 10, "totalTokens": 30},
        }
        mock_service.send_message.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "anthropic",
                "messages",
                model_id,
                "--message",
                "Test",
                "--max-tokens",
                "500",
                "--system",
                "System prompt",
                "--temperature",
                "0.7",
                "--stop",
                "STOP",
                "--stop",
                "END",
                "--top-k",
                "50",
                "--top-p",
                "0.9",
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_args = mock_service.send_message.call_args
        assert call_args[1]["max_tokens"] == 500
        assert call_args[1]["temperature"] == 0.7
        assert call_args[1]["stop_sequences"] == ["STOP", "END"]
        assert call_args[1]["top_k"] == 50
        assert call_args[1]["top_p"] == 0.9
        assert call_args[1]["preview"] is True

    def test_anthropic_messages_with_profile(self, runner, mock_service):
        """Test anthropic messages with profile option."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        response = {"content": [], "role": "assistant", "usage": {}}
        mock_service.send_message.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "anthropic",
                "messages",
                model_id,
                "--message",
                "Test",
                "--profile",
                "custom-profile",
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.send_message.assert_called_once()

    def test_anthropic_messages_auth_error(self, runner, mock_service):
        """Test anthropic messages with authentication error."""
        # Setup
        from pltr.auth.base import ProfileNotFoundError

        model_id = "ri.language-models.main.model.abc123"
        mock_service.send_message.side_effect = ProfileNotFoundError(
            "Profile not found"
        )

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "anthropic",
                "messages",
                model_id,
                "--message",
                "Test",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Authentication error" in result.output

    def test_anthropic_messages_runtime_error(self, runner, mock_service):
        """Test anthropic messages with runtime error."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        mock_service.send_message.side_effect = RuntimeError("API error")

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "anthropic",
                "messages",
                model_id,
                "--message",
                "Test",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Operation failed" in result.output

    # ===== Anthropic Messages Advanced Tests =====

    def test_anthropic_messages_advanced_inline_json(self, runner, mock_service):
        """Test anthropic messages-advanced with inline JSON."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        request_data = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}],
            "maxTokens": 100,
        }
        response = {
            "content": [{"type": "text", "text": "Hello!"}],
            "role": "assistant",
            "usage": {"inputTokens": 5, "outputTokens": 3, "totalTokens": 8},
        }
        mock_service.send_messages_advanced.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "anthropic",
                "messages-advanced",
                model_id,
                "--request",
                json.dumps(request_data),
            ],
        )

        # Assert
        assert result.exit_code == 0
        mock_service.send_messages_advanced.assert_called_once()

    def test_anthropic_messages_advanced_from_file(self, runner, mock_service):
        """Test anthropic messages-advanced with file input."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        request_data = {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
                {"role": "assistant", "content": [{"type": "text", "text": "Hello!"}]},
                {"role": "user", "content": [{"type": "text", "text": "Help"}]},
            ],
            "maxTokens": 500,
        }
        response = {"content": [], "role": "assistant", "usage": {}}
        mock_service.send_messages_advanced.return_value = response

        # Execute with file reference
        with runner.isolated_filesystem():
            # Write request to file
            with open("request.json", "w") as f:
                json.dump(request_data, f)

            result = runner.invoke(
                app,
                [
                    "language-models",
                    "anthropic",
                    "messages-advanced",
                    model_id,
                    "--request",
                    "@request.json",
                ],
            )

        # Assert
        assert result.exit_code == 0

    def test_anthropic_messages_advanced_missing_messages(self, runner, mock_service):
        """Test anthropic messages-advanced with missing messages field."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        request_data = {"maxTokens": 100}  # Missing messages

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "anthropic",
                "messages-advanced",
                model_id,
                "--request",
                json.dumps(request_data),
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Invalid input" in result.output

    def test_anthropic_messages_advanced_missing_max_tokens(self, runner, mock_service):
        """Test anthropic messages-advanced with missing maxTokens field."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        request_data = {
            "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}]
        }  # Missing maxTokens

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "anthropic",
                "messages-advanced",
                model_id,
                "--request",
                json.dumps(request_data),
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Invalid input" in result.output

    def test_anthropic_messages_advanced_invalid_json(self, runner, mock_service):
        """Test anthropic messages-advanced with invalid JSON."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "anthropic",
                "messages-advanced",
                model_id,
                "--request",
                "{invalid json}",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Invalid input" in result.output

    # ===== OpenAI Embeddings Tests =====

    def test_openai_embeddings_single_text(self, runner, mock_service):
        """Test openai embeddings with single text."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        response = {
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}],
            "model": "text-embedding-3-small",
            "usage": {"promptTokens": 2, "totalTokens": 2},
        }
        mock_service.generate_embeddings.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "openai",
                "embeddings",
                model_id,
                "--input",
                "Sample text",
                "--format",
                "json",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_args = mock_service.generate_embeddings.call_args
        assert call_args[1]["input_texts"] == ["Sample text"]

    def test_openai_embeddings_multiple_texts_inline(self, runner, mock_service):
        """Test openai embeddings with multiple texts (inline JSON)."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        input_texts = ["Text 1", "Text 2", "Text 3"]
        response = {
            "data": [
                {"embedding": [0.1, 0.2], "index": 0},
                {"embedding": [0.3, 0.4], "index": 1},
                {"embedding": [0.5, 0.6], "index": 2},
            ],
            "model": "text-embedding-3-small",
            "usage": {"promptTokens": 6, "totalTokens": 6},
        }
        mock_service.generate_embeddings.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "openai",
                "embeddings",
                model_id,
                "--input",
                json.dumps(input_texts),
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_args = mock_service.generate_embeddings.call_args
        assert call_args[1]["input_texts"] == input_texts

    def test_openai_embeddings_from_file(self, runner, mock_service):
        """Test openai embeddings with file input."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        input_texts = ["Document 1", "Document 2"]
        response = {
            "data": [
                {"embedding": [0.1], "index": 0},
                {"embedding": [0.2], "index": 1},
            ],
            "model": "text-embedding-3-small",
            "usage": {"promptTokens": 4, "totalTokens": 4},
        }
        mock_service.generate_embeddings.return_value = response

        # Execute with file reference
        with runner.isolated_filesystem():
            # Write input to file
            with open("texts.json", "w") as f:
                json.dump(input_texts, f)

            result = runner.invoke(
                app,
                [
                    "language-models",
                    "openai",
                    "embeddings",
                    model_id,
                    "--input",
                    "@texts.json",
                ],
            )

        # Assert
        assert result.exit_code == 0

    def test_openai_embeddings_with_dimensions(self, runner, mock_service):
        """Test openai embeddings with custom dimensions."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        response = {
            "data": [{"embedding": [0.1] * 1024, "index": 0}],
            "model": "text-embedding-3-large",
            "usage": {"promptTokens": 2, "totalTokens": 2},
        }
        mock_service.generate_embeddings.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "openai",
                "embeddings",
                model_id,
                "--input",
                "Test",
                "--dimensions",
                "1024",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_args = mock_service.generate_embeddings.call_args
        assert call_args[1]["dimensions"] == 1024

    def test_openai_embeddings_with_encoding(self, runner, mock_service):
        """Test openai embeddings with base64 encoding."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        response = {
            "data": [{"embedding": "YmFzZTY0ZGF0YQ==", "index": 0}],
            "model": "text-embedding-3-small",
            "usage": {"promptTokens": 2, "totalTokens": 2},
        }
        mock_service.generate_embeddings.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "openai",
                "embeddings",
                model_id,
                "--input",
                "Test",
                "--encoding",
                "base64",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_args = mock_service.generate_embeddings.call_args
        assert call_args[1]["encoding_format"] == "base64"

    def test_openai_embeddings_invalid_encoding(self, runner, mock_service):
        """Test openai embeddings with invalid encoding format."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "openai",
                "embeddings",
                model_id,
                "--input",
                "Test",
                "--encoding",
                "invalid",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Invalid input" in result.output

    def test_openai_embeddings_with_all_parameters(self, runner, mock_service):
        """Test openai embeddings with all parameters."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        response = {
            "data": [{"embedding": [0.1] * 512, "index": 0}],
            "model": "text-embedding-3-large",
            "usage": {"promptTokens": 2, "totalTokens": 2},
        }
        mock_service.generate_embeddings.return_value = response

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "openai",
                "embeddings",
                model_id,
                "--input",
                "Test text",
                "--dimensions",
                "512",
                "--encoding",
                "float",
                "--preview",
            ],
        )

        # Assert
        assert result.exit_code == 0
        call_args = mock_service.generate_embeddings.call_args
        assert call_args[1]["dimensions"] == 512
        assert call_args[1]["encoding_format"] == "float"
        assert call_args[1]["preview"] is True

    def test_openai_embeddings_auth_error(self, runner, mock_service):
        """Test openai embeddings with authentication error."""
        # Setup
        from pltr.auth.base import MissingCredentialsError

        model_id = "ri.language-models.main.model.xyz789"
        mock_service.generate_embeddings.side_effect = MissingCredentialsError(
            "Missing credentials"
        )

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "openai",
                "embeddings",
                model_id,
                "--input",
                "Test",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Authentication error" in result.output

    def test_openai_embeddings_runtime_error(self, runner, mock_service):
        """Test openai embeddings with runtime error."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        mock_service.generate_embeddings.side_effect = RuntimeError("API error")

        # Execute
        result = runner.invoke(
            app,
            [
                "language-models",
                "openai",
                "embeddings",
                model_id,
                "--input",
                "Test",
            ],
        )

        # Assert
        assert result.exit_code == 1
        assert "Operation failed" in result.output
