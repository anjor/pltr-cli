"""
LanguageModels service wrapper for Foundry SDK.
Provides access to Anthropic Claude models and OpenAI embeddings.
"""

from typing import Any, Dict, List, Optional
from .base import BaseService


class LanguageModelsService(BaseService):
    """Service wrapper for Foundry LanguageModels operations."""

    def _get_service(self) -> Any:
        """Get the Foundry LanguageModels service."""
        return self.client.language_models

    # ===== Anthropic Model Operations =====

    def send_message(
        self,
        model_id: str,
        message: str,
        max_tokens: int = 1024,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Send a single message to an Anthropic model (simplified interface).

        Args:
            model_id: Model Resource Identifier
                Format: ri.language-models.main.model.<id>
            message: User message text
            max_tokens: Maximum tokens to generate (default: 1024)
            system: Optional system prompt to guide model behavior
            temperature: Sampling temperature (0.0-1.0)
                Lower values are more deterministic
            stop_sequences: Optional list of sequences that stop generation
            top_k: Sample from top K tokens (Anthropic models only)
            top_p: Nucleus sampling threshold (0.0-1.0)
            preview: Enable preview mode (default: False)

        Returns:
            Response dictionary containing:
            - content: List of content blocks (text, tool use, etc.)
            - role: Message role (typically "assistant")
            - model: Model identifier
            - stopReason: Reason generation stopped
            - usage: Token usage statistics
                - inputTokens: Input tokens consumed
                - outputTokens: Output tokens generated
                - totalTokens: Total tokens (input + output)

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = LanguageModelsService()
            >>> response = service.send_message(
            ...     "ri.language-models.main.model.abc123",
            ...     "Explain quantum computing",
            ...     max_tokens=200
            ... )
            >>> print(response['content'][0]['text'])
        """
        try:
            # Transform simple message to SDK message format
            messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": message}],
                }
            ]

            # Build request parameters
            request_params: Dict[str, Any] = {
                "messages": messages,
                "maxTokens": max_tokens,
            }

            # Add optional parameters if provided
            if system is not None:
                request_params["system"] = [{"type": "text", "text": system}]
            if temperature is not None:
                request_params["temperature"] = temperature
            if stop_sequences is not None:
                request_params["stopSequences"] = stop_sequences
            if top_k is not None:
                request_params["topK"] = top_k
            if top_p is not None:
                request_params["topP"] = top_p

            # Call SDK method
            response = self.service.AnthropicModel.messages(
                model_id,
                request=request_params,
                preview=preview,  # type: ignore
            )

            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to send message to model {model_id}: {e}")

    def send_messages_advanced(
        self,
        model_id: str,
        messages: List[Dict[str, Any]],
        max_tokens: int,
        system: Optional[List[Dict[str, Any]]] = None,
        temperature: Optional[float] = None,
        thinking: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Dict[str, Any]] = None,
        stop_sequences: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Send messages to an Anthropic model with advanced features.

        This method accepts the full SDK request structure, enabling:
        - Multi-turn conversations
        - Tool/function calling
        - Extended thinking mode
        - Document and image processing
        - Citations

        Args:
            model_id: Model Resource Identifier
                Format: ri.language-models.main.model.<id>
            messages: List of message objects with role and content
                Format: [{"role": "user|assistant", "content": [...]}]
            max_tokens: Maximum tokens to generate
            system: Optional system prompt blocks
                Format: [{"type": "text", "text": "..."}]
            temperature: Sampling temperature (0.0-1.0)
            thinking: Extended thinking configuration
                Format: {"type": "enabled", "budget": 10000}
            tools: Tool definitions for function calling
            tool_choice: Tool selection strategy
            stop_sequences: Sequences that stop generation
            top_k: Sample from top K tokens
            top_p: Nucleus sampling threshold (0.0-1.0)
            preview: Enable preview mode (default: False)

        Returns:
            Response dictionary containing:
            - content: List of content blocks (text, tool use, thinking, etc.)
            - role: Message role (typically "assistant")
            - model: Model identifier
            - stopReason: Reason generation stopped
            - usage: Token usage statistics

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = LanguageModelsService()
            >>> messages = [
            ...     {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
            ...     {"role": "assistant", "content": [{"type": "text", "text": "Hello!"}]},
            ...     {"role": "user", "content": [{"type": "text", "text": "Help me"}]}
            ... ]
            >>> response = service.send_messages_advanced(
            ...     "ri.language-models.main.model.abc123",
            ...     messages=messages,
            ...     max_tokens=500
            ... )
        """
        try:
            # Build request parameters
            request_params: Dict[str, Any] = {
                "messages": messages,
                "maxTokens": max_tokens,
            }

            # Add optional parameters if provided
            if system is not None:
                request_params["system"] = system
            if temperature is not None:
                request_params["temperature"] = temperature
            if thinking is not None:
                request_params["thinking"] = thinking
            if tools is not None:
                request_params["tools"] = tools
            if tool_choice is not None:
                request_params["toolChoice"] = tool_choice
            if stop_sequences is not None:
                request_params["stopSequences"] = stop_sequences
            if top_k is not None:
                request_params["topK"] = top_k
            if top_p is not None:
                request_params["topP"] = top_p

            # Call SDK method
            response = self.service.AnthropicModel.messages(
                model_id,
                request=request_params,
                preview=preview,  # type: ignore
            )

            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(f"Failed to send messages to model {model_id}: {e}")

    # ===== OpenAI Model Operations =====

    def generate_embeddings(
        self,
        model_id: str,
        input_texts: List[str],
        dimensions: Optional[int] = None,
        encoding_format: Optional[str] = None,
        preview: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate embeddings for text using an OpenAI model.

        Args:
            model_id: Model Resource Identifier
                Format: ri.language-models.main.model.<id>
            input_texts: List of text strings to embed
                Can be a single string or multiple strings
            dimensions: Optional custom embedding dimensions
                Not all models support this parameter
            encoding_format: Output encoding format
                Options: "float" (default) or "base64"
            preview: Enable preview mode (default: False)

        Returns:
            Response dictionary containing:
            - data: List of embedding objects
                Each object has:
                - embedding: Vector (list of floats or base64 string)
                - index: Position in input array
                - object: Type identifier ("embedding")
            - model: Model identifier
            - usage: Token usage statistics
                - promptTokens: Input tokens consumed
                - totalTokens: Total tokens

        Raises:
            RuntimeError: If the operation fails

        Example:
            >>> service = LanguageModelsService()
            >>> response = service.generate_embeddings(
            ...     "ri.language-models.main.model.xyz789",
            ...     input_texts=["Machine learning", "Deep learning"]
            ... )
            >>> embeddings = [item['embedding'] for item in response['data']]
        """
        try:
            # Build request parameters
            request_params: Dict[str, Any] = {
                "input": input_texts,
            }

            # Add optional parameters if provided
            if dimensions is not None:
                request_params["dimensions"] = dimensions
            if encoding_format is not None:
                request_params["encodingFormat"] = encoding_format

            # Call SDK method
            response = self.service.OpenAiModel.embeddings(
                model_id,
                request=request_params,
                preview=preview,  # type: ignore
            )

            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(
                f"Failed to generate embeddings with model {model_id}: {e}"
            )
