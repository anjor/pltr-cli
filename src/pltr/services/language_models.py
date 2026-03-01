"""
LanguageModels service wrapper for Foundry SDK.
Provides access to Anthropic Claude models and OpenAI embeddings.
"""

from typing import Any, Dict, List, Optional, Union
import json
import requests
from urllib.parse import quote
from .base import BaseService


class LanguageModelsService(BaseService):
    """Service wrapper for Foundry LanguageModels operations."""

    _MODEL_LIST_ENDPOINTS = [
        "/v2/languageModels",
        "/api/v2/llm/proxy/openai/v1/models",
    ]
    _MODEL_STATUS_ENDPOINTS = [
        "/v2/languageModels/{model_id}",
        "/api/v2/llm/models/{model_id}",
    ]
    _MODEL_ENROLL_ENDPOINTS = [
        "/v2/languageModels/{model_id}/enroll",
        "/api/v2/llm/models/{model_id}/enroll",
    ]

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
                    "role": "USER",
                    "content": [{"type": "text", "text": message}],
                }
            ]

            # Build SDK kwargs
            request_kwargs: Dict[str, Any] = {
                "messages": messages,
                "max_tokens": max_tokens,
                "preview": preview,
            }

            # Add optional parameters if provided
            if system is not None:
                request_kwargs["system"] = [{"type": "text", "text": system}]
            if temperature is not None:
                request_kwargs["temperature"] = temperature
            if stop_sequences is not None:
                request_kwargs["stop_sequences"] = stop_sequences
            if top_k is not None:
                request_kwargs["top_k"] = top_k
            if top_p is not None:
                request_kwargs["top_p"] = top_p

            # Call SDK method
            response = self.service.AnthropicModel.messages(
                model_id,
                **request_kwargs,  # type: ignore[arg-type,call-overload]
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
                Format: [{"role": "USER|ASSISTANT", "content": [...]}]
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
            ...     {"role": "USER", "content": [{"type": "text", "text": "Hi"}]},
            ...     {"role": "ASSISTANT", "content": [{"type": "text", "text": "Hello!"}]},
            ...     {"role": "USER", "content": [{"type": "text", "text": "Help me"}]}
            ... ]
            >>> response = service.send_messages_advanced(
            ...     "ri.language-models.main.model.abc123",
            ...     messages=messages,
            ...     max_tokens=500
            ... )
        """
        try:
            normalized_messages: List[Dict[str, Any]] = []
            for msg in messages:
                normalized_msg = dict(msg)
                role = normalized_msg.get("role")
                if isinstance(role, str):
                    normalized_msg["role"] = role.upper()
                normalized_messages.append(normalized_msg)

            # Build SDK kwargs
            request_kwargs: Dict[str, Any] = {
                "messages": normalized_messages,
                "max_tokens": max_tokens,
                "preview": preview,
            }

            # Add optional parameters if provided
            if system is not None:
                request_kwargs["system"] = system
            if temperature is not None:
                request_kwargs["temperature"] = temperature
            if thinking is not None:
                request_kwargs["thinking"] = thinking
            if tools is not None:
                request_kwargs["tools"] = tools
            if tool_choice is not None:
                request_kwargs["tool_choice"] = tool_choice
            if stop_sequences is not None:
                request_kwargs["stop_sequences"] = stop_sequences
            if top_k is not None:
                request_kwargs["top_k"] = top_k
            if top_p is not None:
                request_kwargs["top_p"] = top_p

            # Call SDK method
            response = self.service.AnthropicModel.messages(
                model_id,
                **request_kwargs,  # type: ignore[arg-type,call-overload]
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
            # Build SDK kwargs
            request_kwargs: Dict[str, Any] = {
                "input": input_texts,
                "preview": preview,
            }

            # Add optional parameters if provided
            if dimensions is not None:
                request_kwargs["dimensions"] = dimensions
            if encoding_format is not None:
                # CLI accepts "float"/"base64", while SDK expects uppercase literals.
                request_kwargs["encoding_format"] = encoding_format.upper()

            # Call SDK method
            response = self.service.OpenAiModel.embeddings(
                model_id,
                **request_kwargs,  # type: ignore[arg-type,call-overload]
            )

            return self._serialize_response(response)
        except Exception as e:
            raise RuntimeError(
                f"Failed to generate embeddings with model {model_id}: {e}"
            )

    def list_available_models(self) -> List[Dict[str, Any]]:
        """
        List language models available to the authenticated user.

        Tries the platform language-model listing endpoint first, then falls back
        to the provider-compatible OpenAI models endpoint.
        Note: This currently reads a single response per endpoint and does not
        follow pagination tokens.

        Returns:
            List of model dictionaries with normalized keys:
            - model_rid
            - status
            - type
            - display_name

        Raises:
            RuntimeError: If no listing endpoint succeeds
        """
        last_error: Optional[Exception] = None

        for endpoint in self._MODEL_LIST_ENDPOINTS:
            try:
                response = self._make_request("GET", endpoint)
            except (requests.RequestException, RuntimeError) as e:
                last_error = e
                continue

            payload = response.json() if response.text else {}
            return self._normalize_model_list(
                payload,
                is_openai_source=("openai/v1/models" in endpoint),
            )

        raise RuntimeError(f"Failed to list available language models: {last_error}")

    def _normalize_model_list(
        self, payload: Union[Dict[str, Any], List[Any]], is_openai_source: bool = False
    ) -> List[Dict[str, Any]]:
        """Normalize varied model list payloads into a stable CLI schema."""
        raw_models: List[Any] = []
        if isinstance(payload, dict):
            if "data" in payload:
                data = payload.get("data")
                if isinstance(data, list):
                    raw_models = data
            elif "models" in payload:
                models = payload.get("models")
                if isinstance(models, list):
                    raw_models = models
        elif isinstance(payload, list):
            raw_models = payload

        normalized: List[Dict[str, Any]] = []
        for model in raw_models:
            if not isinstance(model, dict):
                continue

            model_id = (
                model.get("rid")
                or model.get("modelRid")
                or model.get("id")
                or model.get("apiName")
                or model.get("name")
            )
            if not model_id:
                continue

            status = (
                model.get("status")
                or model.get("enrollmentStatus")
                or ("AVAILABLE" if is_openai_source else "UNKNOWN")
            )

            model_type = (
                model.get("type")
                or model.get("provider")
                or model.get("modelType")
                or model.get("family")
                or ("OPENAI" if is_openai_source else "UNKNOWN")
            )

            normalized.append(
                {
                    "model_rid": str(model_id),
                    "status": str(status),
                    "type": str(model_type),
                    "display_name": (
                        model.get("displayName")
                        or model.get("name")
                        or model.get("id")
                        or str(model_id)
                    ),
                }
            )

        normalized.sort(key=lambda item: item["model_rid"])
        return normalized

    def get_model_enrollment_status(self, model_id: str) -> Dict[str, Any]:
        """
        Get enrollment status for a language model.

        Args:
            model_id: Model RID or API name

        Returns:
            Dictionary with normalized keys:
            - model_rid
            - status
            - type
            - display_name
        """
        encoded_model_id = quote(model_id, safe="")
        last_error: Optional[Exception] = None

        for endpoint_template in self._MODEL_STATUS_ENDPOINTS:
            endpoint = endpoint_template.format(model_id=encoded_model_id)
            try:
                response = self._make_request("GET", endpoint)
                payload = response.json() if response.text else {}
                return self._normalize_single_model_status(model_id, payload)
            except (
                requests.RequestException,
                RuntimeError,
                json.JSONDecodeError,
            ) as e:
                last_error = e
                continue

        # Fallback: infer availability from provider-compatible OpenAI models list.
        try:
            response = self._make_request("GET", "/api/v2/llm/proxy/openai/v1/models")
            payload = response.json() if response.text else {}
        except (
            requests.RequestException,
            RuntimeError,
            json.JSONDecodeError,
        ) as fallback_error:
            raise RuntimeError(
                f"Failed to get model enrollment status for {model_id}. "
                f"Primary endpoint error: {last_error}. "
                f"Fallback endpoint error: {fallback_error}"
            )

        for item in payload.get("data", []) if isinstance(payload, dict) else []:
            if isinstance(item, dict) and item.get("id") == model_id:
                return self._normalize_single_model_status(
                    model_id,
                    item,
                    default_status="AVAILABLE_VIA_PROXY",
                    default_type="OPENAI",
                    default_display_name=model_id,
                )

        raise RuntimeError(
            f"Model '{model_id}' not found via any known endpoint. "
            f"Last primary endpoint error: {last_error}"
        )

    def enroll_model(self, model_id: str) -> Dict[str, Any]:
        """
        Enroll or enable a language model for API usage.

        Args:
            model_id: Model RID or API name

        Returns:
            Enrollment result dictionary with normalized keys:
            - model_rid
            - status
            - type
            - display_name
        """
        encoded_model_id = quote(model_id, safe="")
        last_error: Optional[Exception] = None

        for endpoint_template in self._MODEL_ENROLL_ENDPOINTS:
            endpoint = endpoint_template.format(model_id=encoded_model_id)
            try:
                response = self._make_request("POST", endpoint, json_data={})
                payload = response.json() if response.text else {}
                return self._normalize_single_model_status(
                    model_id, payload, default_status="ENROLLED"
                )
            except (
                requests.RequestException,
                RuntimeError,
                json.JSONDecodeError,
            ) as e:
                last_error = e
                continue

        raise RuntimeError(
            f"Failed to enroll model {model_id}. "
            f"Enrollment may require Model Catalog UI access for this model: {last_error}"
        )

    def _normalize_single_model_status(
        self,
        model_id: str,
        payload: Dict[str, Any],
        default_status: str = "UNKNOWN",
        default_type: str = "UNKNOWN",
        default_display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Normalize status payloads from varying endpoints."""
        model_data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(model_data, dict):
            payload = model_data

        if not isinstance(payload, dict):
            payload = {}

        return {
            "model_rid": str(
                payload.get("rid")
                or payload.get("modelRid")
                or payload.get("id")
                or model_id
            ),
            "status": str(
                payload.get("status")
                or payload.get("enrollmentStatus")
                or default_status
            ),
            "type": str(
                payload.get("type")
                or payload.get("provider")
                or payload.get("modelType")
                or default_type
            ),
            "display_name": str(
                payload.get("displayName")
                or payload.get("name")
                or payload.get("id")
                or default_display_name
                or model_id
            ),
        }
