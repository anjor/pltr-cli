"""Tests for LanguageModels service."""

import pytest
import requests
from unittest.mock import Mock, patch
from pltr.services.language_models import LanguageModelsService


class TestLanguageModelsService:
    """Test LanguageModels service functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Foundry client."""
        client = Mock()
        client.language_models = Mock()
        client.language_models.AnthropicModel = Mock()
        client.language_models.OpenAiModel = Mock()
        return client

    @pytest.fixture
    def service(self, mock_client):
        """Create LanguageModelsService with mocked client."""
        with patch("pltr.services.base.AuthManager") as mock_auth:
            mock_auth.return_value.get_client.return_value = mock_client
            service = LanguageModelsService()
            return service

    # ===== Anthropic Messages Tests =====

    def test_send_message(self, service, mock_client):
        """Test sending a simple message."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        message = "Hello, Claude!"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "content": [{"type": "text", "text": "Hello!"}],
            "role": "assistant",
            "model": "claude-3-sonnet",
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": 10,
                "outputTokens": 5,
                "totalTokens": 15,
            },
        }
        mock_client.language_models.AnthropicModel.messages.return_value = mock_response

        # Execute
        result = service.send_message(model_id, message)

        # Assert
        mock_client.language_models.AnthropicModel.messages.assert_called_once()
        call_args = mock_client.language_models.AnthropicModel.messages.call_args
        assert call_args[0][0] == model_id
        assert call_args[1]["preview"] is False

        # Check SDK kwargs structure
        assert "request" not in call_args[1]
        assert call_args[1]["max_tokens"] == 1024
        assert len(call_args[1]["messages"]) == 1
        assert call_args[1]["messages"][0]["role"] == "USER"
        assert call_args[1]["messages"][0]["content"][0]["text"] == message

        # Check result
        assert result["role"] == "assistant"
        assert result["usage"]["totalTokens"] == 15

    def test_send_message_with_system_prompt(self, service, mock_client):
        """Test sending message with system prompt."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        message = "Write a haiku"
        system = "You are a poetic assistant"
        mock_response = Mock()
        mock_response.dict.return_value = {"content": [], "role": "assistant"}
        mock_client.language_models.AnthropicModel.messages.return_value = mock_response

        # Execute
        service.send_message(model_id, message, system=system)

        # Assert
        call_args = mock_client.language_models.AnthropicModel.messages.call_args
        assert "system" in call_args[1]
        assert call_args[1]["system"][0]["type"] == "text"
        assert call_args[1]["system"][0]["text"] == system

    def test_send_message_with_all_parameters(self, service, mock_client):
        """Test sending message with all optional parameters."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        message = "Test message"
        mock_response = Mock()
        mock_response.dict.return_value = {"content": [], "role": "assistant"}
        mock_client.language_models.AnthropicModel.messages.return_value = mock_response

        # Execute
        service.send_message(
            model_id,
            message,
            max_tokens=500,
            system="System prompt",
            temperature=0.7,
            stop_sequences=["STOP", "END"],
            top_k=50,
            top_p=0.9,
            preview=True,
        )

        # Assert
        call_args = mock_client.language_models.AnthropicModel.messages.call_args
        assert "request" not in call_args[1]
        assert call_args[1]["max_tokens"] == 500
        assert call_args[1]["temperature"] == 0.7
        assert call_args[1]["stop_sequences"] == ["STOP", "END"]
        assert call_args[1]["top_k"] == 50
        assert call_args[1]["top_p"] == 0.9
        assert call_args[1]["preview"] is True

    def test_send_message_error(self, service, mock_client):
        """Test error handling in send_message."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        message = "Test"
        mock_client.language_models.AnthropicModel.messages.side_effect = Exception(
            "Model not found"
        )

        # Execute & Assert
        with pytest.raises(RuntimeError) as exc_info:
            service.send_message(model_id, message)
        assert "Failed to send message" in str(exc_info.value)
        assert model_id in str(exc_info.value)

    def test_send_messages_advanced(self, service, mock_client):
        """Test sending multi-turn messages."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        messages = [
            {"role": "USER", "content": [{"type": "text", "text": "Hi"}]},
            {"role": "ASSISTANT", "content": [{"type": "text", "text": "Hello!"}]},
            {"role": "USER", "content": [{"type": "text", "text": "Help"}]},
        ]
        max_tokens = 500
        mock_response = Mock()
        mock_response.dict.return_value = {
            "content": [{"type": "text", "text": "I'm here to help!"}],
            "role": "assistant",
        }
        mock_client.language_models.AnthropicModel.messages.return_value = mock_response

        # Execute
        result = service.send_messages_advanced(model_id, messages, max_tokens)

        # Assert
        call_args = mock_client.language_models.AnthropicModel.messages.call_args
        assert "request" not in call_args[1]
        assert call_args[1]["messages"] == messages
        assert call_args[1]["max_tokens"] == max_tokens
        assert call_args[1]["preview"] is False
        assert result["role"] == "assistant"

    def test_send_messages_advanced_normalizes_roles(self, service, mock_client):
        """Test advanced messages role normalization to SDK enum casing."""
        model_id = "ri.language-models.main.model.abc123"
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Hello!"}]},
        ]
        mock_response = Mock()
        mock_response.dict.return_value = {"content": [], "role": "assistant"}
        mock_client.language_models.AnthropicModel.messages.return_value = mock_response

        service.send_messages_advanced(model_id, messages, max_tokens=50)

        call_args = mock_client.language_models.AnthropicModel.messages.call_args
        assert call_args[1]["messages"][0]["role"] == "USER"
        assert call_args[1]["messages"][1]["role"] == "ASSISTANT"

    def test_send_messages_advanced_with_thinking(self, service, mock_client):
        """Test sending messages with extended thinking."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        messages = [{"role": "USER", "content": [{"type": "text", "text": "Solve"}]}]
        thinking = {"type": "enabled", "budget": 10000}
        mock_response = Mock()
        mock_response.dict.return_value = {"content": [], "role": "assistant"}
        mock_client.language_models.AnthropicModel.messages.return_value = mock_response

        # Execute
        service.send_messages_advanced(
            model_id, messages, max_tokens=2000, thinking=thinking
        )

        # Assert
        call_args = mock_client.language_models.AnthropicModel.messages.call_args
        assert call_args[1]["thinking"] == thinking

    def test_send_messages_advanced_with_tools(self, service, mock_client):
        """Test sending messages with tool calling."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        messages = [
            {"role": "USER", "content": [{"type": "text", "text": "Calculate"}]}
        ]
        tools = [
            {
                "name": "calculator",
                "description": "Performs calculations",
                "inputSchema": {"type": "object"},
            }
        ]
        tool_choice = {"type": "auto"}
        mock_response = Mock()
        mock_response.dict.return_value = {"content": [], "role": "assistant"}
        mock_client.language_models.AnthropicModel.messages.return_value = mock_response

        # Execute
        service.send_messages_advanced(
            model_id,
            messages,
            max_tokens=1000,
            tools=tools,
            tool_choice=tool_choice,
        )

        # Assert
        call_args = mock_client.language_models.AnthropicModel.messages.call_args
        assert call_args[1]["tools"] == tools
        assert call_args[1]["tool_choice"] == tool_choice

    def test_send_messages_advanced_error(self, service, mock_client):
        """Test error handling in send_messages_advanced."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        messages = [{"role": "USER", "content": [{"type": "text", "text": "Hi"}]}]
        mock_client.language_models.AnthropicModel.messages.side_effect = Exception(
            "API error"
        )

        # Execute & Assert
        with pytest.raises(RuntimeError) as exc_info:
            service.send_messages_advanced(model_id, messages, max_tokens=100)
        assert "Failed to send messages" in str(exc_info.value)

    # ===== Language Model Discovery Tests =====

    def test_list_available_models_v2_endpoint(self, service):
        """Test listing models from native language models endpoint."""
        mock_response = Mock()
        mock_response.text = "ok"
        mock_response.json.return_value = {
            "data": [
                {
                    "rid": "ri.language-model-service..language-model.anthropic_claude_3_5_sonnet_v2",
                    "status": "ENROLLED",
                    "provider": "ANTHROPIC",
                    "displayName": "Claude 3.5 Sonnet",
                }
            ]
        }

        with patch.object(
            service, "_make_request", return_value=mock_response
        ) as mock_req:
            result = service.list_available_models()

        assert len(result) == 1
        assert (
            result[0]["model_rid"]
            == "ri.language-model-service..language-model.anthropic_claude_3_5_sonnet_v2"
        )
        assert result[0]["status"] == "ENROLLED"
        assert result[0]["type"] == "ANTHROPIC"
        mock_req.assert_called_once_with("GET", "/v2/languageModels")

    def test_list_available_models_openai_proxy_fallback(self, service):
        """Test fallback to provider-compatible OpenAI models endpoint."""
        fallback_response = Mock()
        fallback_response.text = "ok"
        fallback_response.json.return_value = {
            "data": [
                {
                    "id": "gpt-4o",
                    "object": "model",
                }
            ]
        }

        with patch.object(
            service,
            "_make_request",
            side_effect=[RuntimeError("404"), fallback_response],
        ) as mock_req:
            result = service.list_available_models()

        assert len(result) == 1
        assert result[0]["model_rid"] == "gpt-4o"
        assert result[0]["status"] == "AVAILABLE"
        assert result[0]["type"] == "OPENAI"
        assert mock_req.call_count == 2
        assert mock_req.call_args_list[0].args == ("GET", "/v2/languageModels")
        assert mock_req.call_args_list[1].args == (
            "GET",
            "/api/v2/llm/proxy/openai/v1/models",
        )

    def test_list_available_models_connection_error_fallback(self, service):
        """Test fallback when the first endpoint fails with network error."""
        fallback_response = Mock()
        fallback_response.text = "ok"
        fallback_response.json.return_value = {"data": [{"id": "gpt-4.1"}]}

        with patch.object(
            service,
            "_make_request",
            side_effect=[requests.ConnectionError("network down"), fallback_response],
        ) as mock_req:
            result = service.list_available_models()

        assert len(result) == 1
        assert result[0]["model_rid"] == "gpt-4.1"
        assert mock_req.call_args_list[-1].args == (
            "GET",
            "/api/v2/llm/proxy/openai/v1/models",
        )

    def test_list_available_models_prefers_explicit_empty_data(self, service):
        """Test that an explicit empty `data` list does not fall back to `models`."""
        mock_response = Mock()
        mock_response.text = "ok"
        mock_response.json.return_value = {
            "data": [],
            "models": [{"id": "should-not-be-used"}],
        }

        with patch.object(
            service, "_make_request", return_value=mock_response
        ) as mock_req:
            result = service.list_available_models()

        assert result == []
        mock_req.assert_called_once_with("GET", "/v2/languageModels")

    def test_list_available_models_json_error_not_swallowed(self, service):
        """Test that JSON parsing errors are surfaced and do not trigger fallback."""
        bad_response = Mock()
        bad_response.text = "not-json"
        bad_response.json.side_effect = ValueError("invalid json")

        with patch.object(
            service, "_make_request", return_value=bad_response
        ) as mock_req:
            with pytest.raises(ValueError, match="invalid json"):
                service.list_available_models()

        mock_req.assert_called_once_with("GET", "/v2/languageModels")

    def test_list_available_models_error(self, service):
        """Test error handling when all model listing endpoints fail."""
        with patch.object(
            service, "_make_request", side_effect=RuntimeError("unavailable")
        ):
            with pytest.raises(RuntimeError) as exc_info:
                service.list_available_models()

        assert "Failed to list available language models" in str(exc_info.value)

    # ===== Enrollment/Status Tests =====

    def test_get_model_enrollment_status(self, service):
        """Test getting model enrollment status."""
        model_id = (
            "ri.language-model-service..language-model.anthropic_claude_3_5_sonnet_v2"
        )
        mock_response = Mock()
        mock_response.text = "ok"
        mock_response.json.return_value = {
            "rid": model_id,
            "status": "ENROLLED",
            "provider": "ANTHROPIC",
            "displayName": "Claude 3.5 Sonnet",
        }

        with patch.object(
            service, "_make_request", return_value=mock_response
        ) as mock_req:
            result = service.get_model_enrollment_status(model_id)

        assert result["model_rid"] == model_id
        assert result["status"] == "ENROLLED"
        assert result["type"] == "ANTHROPIC"
        mock_req.assert_called_once_with(
            "GET",
            "/v2/languageModels/ri.language-model-service..language-model.anthropic_claude_3_5_sonnet_v2",
        )

    def test_get_model_enrollment_status_openai_proxy_fallback(self, service):
        """Test status fallback to OpenAI-compatible models listing."""
        model_id = "gpt-4o"
        fallback_response = Mock()
        fallback_response.text = "ok"
        fallback_response.json.return_value = {
            "data": [{"id": "gpt-4o"}, {"id": "gpt-4.1"}]
        }

        with patch.object(
            service,
            "_make_request",
            side_effect=[
                RuntimeError("not found"),
                RuntimeError("not found"),
                fallback_response,
            ],
        ) as mock_req:
            result = service.get_model_enrollment_status(model_id)

        assert result["model_rid"] == "gpt-4o"
        assert result["status"] == "AVAILABLE"
        assert result["type"] == "OPENAI"
        assert mock_req.call_args_list[-1].args == (
            "GET",
            "/api/v2/llm/proxy/openai/v1/models",
        )

    def test_get_model_enrollment_status_not_found_after_fallback(self, service):
        """Test error when model is not found in fallback list either."""
        model_id = "missing-model"
        fallback_response = Mock()
        fallback_response.text = "ok"
        fallback_response.json.return_value = {"data": [{"id": "gpt-4o"}]}

        with patch.object(
            service,
            "_make_request",
            side_effect=[
                RuntimeError("not found"),
                RuntimeError("not found"),
                fallback_response,
            ],
        ):
            with pytest.raises(RuntimeError) as exc_info:
                service.get_model_enrollment_status(model_id)

        assert "not found via any known endpoint" in str(exc_info.value)

    def test_get_model_enrollment_status_fallback_request_failure(self, service):
        """Test error details when fallback endpoint request fails."""
        model_id = "missing-model"

        with patch.object(
            service,
            "_make_request",
            side_effect=[
                RuntimeError("primary endpoint down"),
                RuntimeError("primary endpoint down"),
                RuntimeError("fallback endpoint down"),
            ],
        ):
            with pytest.raises(RuntimeError) as exc_info:
                service.get_model_enrollment_status(model_id)

        error_text = str(exc_info.value)
        assert "Primary endpoint error" in error_text
        assert "Fallback endpoint error" in error_text

    def test_get_model_enrollment_status_json_error_falls_back(self, service):
        """Test JSON decode errors trigger fallback instead of opaque command errors."""
        model_id = "gpt-4o"
        bad_primary_response = Mock()
        bad_primary_response.text = "not-json"
        bad_primary_response.json.side_effect = ValueError("invalid json")

        fallback_response = Mock()
        fallback_response.text = "ok"
        fallback_response.json.return_value = {"data": [{"id": "gpt-4o"}]}

        with patch.object(
            service,
            "_make_request",
            side_effect=[
                bad_primary_response,
                RuntimeError("not found"),
                fallback_response,
            ],
        ):
            result = service.get_model_enrollment_status(model_id)

        assert result["model_rid"] == "gpt-4o"
        assert result["status"] == "AVAILABLE"

    def test_enroll_model_success(self, service):
        """Test enrolling a language model."""
        model_id = (
            "ri.language-model-service..language-model.anthropic_claude_3_5_sonnet_v2"
        )
        mock_response = Mock()
        mock_response.text = "ok"
        mock_response.json.return_value = {
            "status": "ENROLLED",
            "provider": "ANTHROPIC",
        }

        with patch.object(
            service, "_make_request", return_value=mock_response
        ) as mock_req:
            result = service.enroll_model(model_id)

        assert result["model_rid"] == model_id
        assert result["status"] == "ENROLLED"
        assert result["type"] == "ANTHROPIC"
        assert result["display_name"] == model_id
        assert "response" not in result
        mock_req.assert_called_once_with(
            "POST",
            "/v2/languageModels/ri.language-model-service..language-model.anthropic_claude_3_5_sonnet_v2/enroll",
            json_data={},
        )

    def test_enroll_model_fallback_endpoint(self, service):
        """Test enrollment fallback when the first endpoint fails."""
        model_id = "ri.language-model-service..language-model.gpt_4o"
        fallback_response = Mock()
        fallback_response.text = "ok"
        fallback_response.json.return_value = {"status": "ENROLLED"}

        with patch.object(
            service,
            "_make_request",
            side_effect=[RuntimeError("missing endpoint"), fallback_response],
        ) as mock_req:
            result = service.enroll_model(model_id)

        assert result["model_rid"] == model_id
        assert result["status"] == "ENROLLED"
        assert mock_req.call_args_list[-1].args == (
            "POST",
            "/api/v2/llm/models/ri.language-model-service..language-model.gpt_4o/enroll",
        )
        assert mock_req.call_args_list[-1].kwargs == {"json_data": {}}

    def test_enroll_model_error(self, service):
        """Test enrollment error handling when all endpoints fail."""
        with patch.object(
            service, "_make_request", side_effect=RuntimeError("unavailable")
        ):
            with pytest.raises(RuntimeError) as exc_info:
                service.enroll_model(
                    "ri.language-model-service..language-model.some_model"
                )

        assert "Failed to enroll model" in str(exc_info.value)
        assert "Model Catalog UI access for this model" in str(exc_info.value)

    # ===== OpenAI Embeddings Tests =====

    def test_generate_embeddings_single_text(self, service, mock_client):
        """Test generating embeddings for single text."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        input_texts = ["Sample text"]
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [
                {
                    "embedding": [0.1, 0.2, 0.3],
                    "index": 0,
                    "object": "embedding",
                }
            ],
            "model": "text-embedding-3-small",
            "usage": {
                "promptTokens": 2,
                "totalTokens": 2,
            },
        }
        mock_client.language_models.OpenAiModel.embeddings.return_value = mock_response

        # Execute
        result = service.generate_embeddings(model_id, input_texts)

        # Assert
        mock_client.language_models.OpenAiModel.embeddings.assert_called_once()
        call_args = mock_client.language_models.OpenAiModel.embeddings.call_args
        assert call_args[0][0] == model_id
        assert "request" not in call_args[1]
        assert call_args[1]["input"] == input_texts
        assert call_args[1]["preview"] is False
        assert len(result["data"]) == 1
        assert result["usage"]["totalTokens"] == 2

    def test_generate_embeddings_multiple_texts(self, service, mock_client):
        """Test generating embeddings for multiple texts."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        input_texts = ["Text 1", "Text 2", "Text 3"]
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [
                {"embedding": [0.1, 0.2], "index": 0},
                {"embedding": [0.3, 0.4], "index": 1},
                {"embedding": [0.5, 0.6], "index": 2},
            ],
            "model": "text-embedding-3-small",
            "usage": {"promptTokens": 6, "totalTokens": 6},
        }
        mock_client.language_models.OpenAiModel.embeddings.return_value = mock_response

        # Execute
        result = service.generate_embeddings(model_id, input_texts)

        # Assert
        call_args = mock_client.language_models.OpenAiModel.embeddings.call_args
        assert "request" not in call_args[1]
        assert call_args[1]["input"] == input_texts
        assert len(result["data"]) == 3

    def test_generate_embeddings_with_dimensions(self, service, mock_client):
        """Test generating embeddings with custom dimensions."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        input_texts = ["Test"]
        dimensions = 1024
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [{"embedding": [0.1] * 1024, "index": 0}],
            "model": "text-embedding-3-large",
            "usage": {"promptTokens": 1, "totalTokens": 1},
        }
        mock_client.language_models.OpenAiModel.embeddings.return_value = mock_response

        # Execute
        service.generate_embeddings(model_id, input_texts, dimensions=dimensions)

        # Assert
        call_args = mock_client.language_models.OpenAiModel.embeddings.call_args
        assert call_args[1]["dimensions"] == dimensions

    def test_generate_embeddings_with_encoding_format(self, service, mock_client):
        """Test generating embeddings with base64 encoding."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        input_texts = ["Test"]
        encoding_format = "base64"
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [{"embedding": "YmFzZTY0ZGF0YQ==", "index": 0}],
            "model": "text-embedding-3-small",
            "usage": {"promptTokens": 1, "totalTokens": 1},
        }
        mock_client.language_models.OpenAiModel.embeddings.return_value = mock_response

        # Execute
        service.generate_embeddings(
            model_id, input_texts, encoding_format=encoding_format
        )

        # Assert
        call_args = mock_client.language_models.OpenAiModel.embeddings.call_args
        assert call_args[1]["encoding_format"] == "BASE64"

    def test_generate_embeddings_with_all_parameters(self, service, mock_client):
        """Test generating embeddings with all optional parameters."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        input_texts = ["Text 1", "Text 2"]
        mock_response = Mock()
        mock_response.dict.return_value = {
            "data": [{"embedding": [0.1], "index": 0}],
            "model": "text-embedding-3-large",
            "usage": {"promptTokens": 4, "totalTokens": 4},
        }
        mock_client.language_models.OpenAiModel.embeddings.return_value = mock_response

        # Execute
        service.generate_embeddings(
            model_id,
            input_texts,
            dimensions=512,
            encoding_format="float",
            preview=True,
        )

        # Assert
        call_args = mock_client.language_models.OpenAiModel.embeddings.call_args
        assert call_args[1]["input"] == input_texts
        assert call_args[1]["dimensions"] == 512
        assert call_args[1]["encoding_format"] == "FLOAT"
        assert call_args[1]["preview"] is True

    def test_generate_embeddings_error(self, service, mock_client):
        """Test error handling in generate_embeddings."""
        # Setup
        model_id = "ri.language-models.main.model.xyz789"
        input_texts = ["Test"]
        mock_client.language_models.OpenAiModel.embeddings.side_effect = Exception(
            "Model not found"
        )

        # Execute & Assert
        with pytest.raises(RuntimeError) as exc_info:
            service.generate_embeddings(model_id, input_texts)
        assert "Failed to generate embeddings" in str(exc_info.value)
        assert model_id in str(exc_info.value)
