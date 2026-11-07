"""
LanguageModels service wrapper.

Through foundry-platform-sdk: ``AnthropicModel.messages`` and
``OpenAiModel.embeddings`` are beta endpoints, always called with a literal
``preview=True``. Both take the model's API name (``LanguageModelApiName``),
return the SDK response models unchanged and let SDK exceptions propagate.

Labeled direct-HTTP exception (see docs/development/sdk-guardrail.md): the
SDK has no endpoint to enroll a model. ``enroll_model`` calls Foundry with
``BaseService._make_request`` (the SDK client's host and auth), trying the
endpoints below in order and returning the first answer as the endpoint sent
it. These endpoints aren't in the SDK and haven't been verified against a live
stack.

``language-models list`` and ``status`` were removed in 0.17.0: the endpoints
they tried (``GET /api/v2/languageModels``, ``GET /api/v2/llm/models/{id}``
and the OpenAI-compatible proxy's ``GET /api/v2/llm/proxy/openai/v1/models``)
returned 404 on a live stack, and the SDK has no equivalent.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, NoReturn, Optional, Tuple
from urllib.parse import quote

import requests

from ..contract import ExitCode, PltrError
from .base import BaseService

#: ``language-models enroll``: POST endpoints tried in order.
MODEL_ENROLL_ENDPOINTS: Tuple[str, ...] = (
    "/api/v2/languageModels/{model_id}/enroll",
    "/api/v2/llm/models/{model_id}/enroll",
)


@dataclass
class EndpointAnswer:
    """The JSON body of the endpoint that answered (``None``: no body)."""

    endpoint: str
    body: Any


class _NotJson:
    """Marker for a 2xx response whose body isn't JSON."""


_NOT_JSON = _NotJson()


def _json_body(response: requests.Response) -> Any:
    """The response's JSON body, ``None`` when empty, or ``_NOT_JSON``."""
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:  # requests' JSONDecodeError is a ValueError
        return _NOT_JSON


def _unwrap_data(body: Any) -> Any:
    """A single model object, unwrapped from a ``{"data": {...}}`` envelope."""
    if isinstance(body, dict) and isinstance(body.get("data"), dict):
        return body["data"]
    return body


def _normalize_roles(messages: Any) -> Any:
    """Upper-case each message's ``role`` ("user" -> "USER"), as the API expects."""
    if not isinstance(messages, list):
        return messages
    normalized = []
    for message in messages:
        if isinstance(message, dict) and isinstance(message.get("role"), str):
            message = {**message, "role": message["role"].upper()}
        normalized.append(message)
    return normalized


class _Attempts:
    """The endpoints a direct-HTTP lookup tried, and why each didn't answer."""

    def __init__(self) -> None:
        self.failures: List[str] = []
        self.errors: List[requests.HTTPError] = []

    def http_error(self, endpoint: str, error: requests.HTTPError) -> None:
        status = error.response.status_code if error.response is not None else "?"
        self.failures.append(f"{endpoint} -> HTTP {status}")
        self.errors.append(error)

    def not_json(self, endpoint: str) -> None:
        self.failures.append(f"{endpoint} -> response is not JSON")

    def summary(self) -> str:
        return "; ".join(self.failures)

    def most_telling_error(self) -> Optional[requests.HTTPError]:
        """The last error that isn't a 404, else the last error.

        A 404 only says that an endpoint doesn't exist on this stack; any
        other status (401, 403, 400, 5xx) says why the request failed.
        """
        for error in reversed(self.errors):
            if error.response is not None and error.response.status_code != 404:
                return error
        return self.errors[-1] if self.errors else None


def _raise_no_answer(message: str, attempts: _Attempts) -> NoReturn:
    """Fail after every endpoint was tried.

    The most telling HTTP error is kept as ``__cause__``, so the error layer
    reports its status, Foundry error name and exit code.
    """
    summary = f"{message} ({attempts.summary()})"
    cause = attempts.most_telling_error()
    if cause is None:
        raise PltrError(summary, error_type="api_error", exit_code=ExitCode.API)
    raise RuntimeError(summary) from cause


class LanguageModelsService(BaseService):
    """Service wrapper for Foundry language models (``client.language_models``)."""

    # The direct-HTTP endpoints, also as the class attribute they used to be.
    _MODEL_ENROLL_ENDPOINTS = MODEL_ENROLL_ENDPOINTS

    def _get_service(self) -> Any:
        """Get the Foundry LanguageModels service."""
        return self.client.language_models

    # ===== Anthropic models (SDK, beta) =====

    def send_message(
        self,
        model_id: str,
        message: str,
        *,
        max_tokens: int = 1024,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        stop_sequences: Optional[List[str]] = None,
        top_k: Optional[int] = None,
        top_p: Optional[float] = None,
    ) -> Any:
        """Send one user message (``AnthropicModel.messages``, beta).

        Args:
            model_id: The model's API name (``LanguageModelApiName``)
            message: User message text
            max_tokens: Maximum number of tokens to generate
            system: System prompt
            temperature: Sampling temperature (0.0-1.0)
            stop_sequences: Sequences that stop generation
            top_k: Sample from the top K tokens
            top_p: Nucleus sampling threshold (0.0-1.0)

        Returns:
            The ``AnthropicMessagesResponse`` model
        """
        return self.service.AnthropicModel.messages(
            model_id,
            max_tokens=max_tokens,
            messages=[{"role": "USER", "content": [{"type": "text", "text": message}]}],
            stop_sequences=stop_sequences,
            system=[{"type": "text", "text": system}] if system is not None else None,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            preview=True,
        )

    def send_messages_advanced(
        self,
        model_id: str,
        *,
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
        output_config: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Send a full messages request (``AnthropicModel.messages``, beta).

        Arguments are the fields of the API's ``AnthropicMessagesRequest``,
        as JSON with the API's field names inside (``{"type": "text", ...}``).
        Message roles are upper-cased (``user`` -> ``USER``).

        Returns:
            The ``AnthropicMessagesResponse`` model
        """
        return self.service.AnthropicModel.messages(
            model_id,
            max_tokens=max_tokens,
            messages=_normalize_roles(messages),
            output_config=output_config,
            stop_sequences=stop_sequences,
            system=system,
            temperature=temperature,
            thinking=thinking,
            tool_choice=tool_choice,
            tools=tools,
            top_k=top_k,
            top_p=top_p,
            preview=True,
        )

    # ===== OpenAI models (SDK, beta) =====

    def generate_embeddings(
        self,
        model_id: str,
        input_texts: List[str],
        *,
        dimensions: Optional[int] = None,
        encoding_format: Optional[str] = None,
    ) -> Any:
        """Embed texts (``OpenAiModel.embeddings``, beta).

        Args:
            model_id: The model's API name (``LanguageModelApiName``)
            input_texts: Texts to embed
            dimensions: Number of dimensions of the embeddings
            encoding_format: ``float`` (any case). The API also takes
                ``base64``, but the SDK's response model (``data`` is a list
                of float lists) can't decode a base64 answer.

        Returns:
            The ``OpenAiEmbeddingsResponse`` model: one vector per input in ``data``
        """
        return self.service.OpenAiModel.embeddings(
            model_id,
            input=input_texts,
            dimensions=dimensions,
            encoding_format=encoding_format.upper() if encoding_format else None,
            preview=True,
        )

    # ===== Labeled direct-HTTP exceptions =====

    def enroll_model(self, model_id: str) -> EndpointAnswer:
        """Enroll (enable) a language model for API use (direct HTTP).

        POSTs ``{}`` to ``MODEL_ENROLL_ENDPOINTS`` in order; the first one
        that answers (2xx, with a JSON or empty body) wins.

        Args:
            model_id: Model RID or API name

        Raises:
            RuntimeError: no endpoint answered (``__cause__``: the most telling
                ``requests.HTTPError``)
        """
        encoded_model_id = quote(model_id, safe="")
        attempts = _Attempts()
        for template in MODEL_ENROLL_ENDPOINTS:
            path = template.format(model_id=encoded_model_id)
            endpoint = f"POST {path}"
            try:
                response = self._make_request("POST", path, json_data={})
            except requests.HTTPError as error:
                attempts.http_error(endpoint, error)
                continue
            body = _json_body(response)
            if body is _NOT_JSON:
                attempts.not_json(endpoint)
                continue
            return EndpointAnswer(endpoint=endpoint, body=_unwrap_data(body))
        _raise_no_answer(
            f"Couldn't enroll model {model_id}; enrolling it may need the Model "
            "Catalog in the Foundry UI",
            attempts,
        )
