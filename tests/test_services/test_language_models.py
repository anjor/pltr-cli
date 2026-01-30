"""Tests for LanguageModels service."""

import pytest
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

        # Check request structure
        request = call_args[1]["request"]
        assert request["maxTokens"] == 1024
        assert len(request["messages"]) == 1
        assert request["messages"][0]["role"] == "user"
        assert request["messages"][0]["content"][0]["text"] == message

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
        request = call_args[1]["request"]
        assert "system" in request
        assert request["system"][0]["type"] == "text"
        assert request["system"][0]["text"] == system

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
        request = call_args[1]["request"]
        assert request["maxTokens"] == 500
        assert request["temperature"] == 0.7
        assert request["stopSequences"] == ["STOP", "END"]
        assert request["topK"] == 50
        assert request["topP"] == 0.9
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
            {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Hello!"}]},
            {"role": "user", "content": [{"type": "text", "text": "Help"}]},
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
        request = call_args[1]["request"]
        assert request["messages"] == messages
        assert request["maxTokens"] == max_tokens
        assert result["role"] == "assistant"

    def test_send_messages_advanced_with_thinking(self, service, mock_client):
        """Test sending messages with extended thinking."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        messages = [{"role": "user", "content": [{"type": "text", "text": "Solve"}]}]
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
        request = call_args[1]["request"]
        assert request["thinking"] == thinking

    def test_send_messages_advanced_with_tools(self, service, mock_client):
        """Test sending messages with tool calling."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        messages = [
            {"role": "user", "content": [{"type": "text", "text": "Calculate"}]}
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
        request = call_args[1]["request"]
        assert request["tools"] == tools
        assert request["toolChoice"] == tool_choice

    def test_send_messages_advanced_error(self, service, mock_client):
        """Test error handling in send_messages_advanced."""
        # Setup
        model_id = "ri.language-models.main.model.abc123"
        messages = [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}]
        mock_client.language_models.AnthropicModel.messages.side_effect = Exception(
            "API error"
        )

        # Execute & Assert
        with pytest.raises(RuntimeError) as exc_info:
            service.send_messages_advanced(model_id, messages, max_tokens=100)
        assert "Failed to send messages" in str(exc_info.value)

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
        assert call_args[1]["request"]["input"] == input_texts
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
        assert call_args[1]["request"]["input"] == input_texts
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
        request = call_args[1]["request"]
        assert request["dimensions"] == dimensions

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
        request = call_args[1]["request"]
        assert request["encodingFormat"] == encoding_format

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
        request = call_args[1]["request"]
        assert request["input"] == input_texts
        assert request["dimensions"] == 512
        assert request["encodingFormat"] == "float"
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
