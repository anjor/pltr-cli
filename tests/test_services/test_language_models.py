"""Tests for LanguageModelsService against a real FoundryClient (only HTTP is faked).

``AnthropicModel.messages`` and ``OpenAiModel.embeddings`` are beta: every
request must carry ``preview=true``. The old Mock-based tests passed
``preview`` through from a CLI flag that defaulted to off, so the calls failed
unless users remembered ``--preview``.

``enroll_model`` is a labeled direct-HTTP exception; its requests go through
``requests``, which stub_foundry_http also records (with the bearer token of
the SDK auth).
"""

import json

import pytest
import requests
from foundry_sdk import PermissionDeniedError
from foundry_sdk.v2.language_models.models import (
    AnthropicMessagesResponse,
    OpenAiEmbeddingsResponse,
)

from pltr.contract import PltrError
from pltr.services.language_models import LanguageModelsService
from tests import foundry_json as fj
from tests import foundry_json_language_models as lm
from tests.conftest import STUB_HOSTNAME, STUB_TOKEN

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

MESSAGES = f"/api/v2/languageModels/anthropic/{lm.MODEL_API_NAME}/messages"
EMBEDDINGS = f"/api/v2/languageModels/openAi/{lm.EMBEDDING_MODEL}/embeddings"
LIST = "/api/v2/languageModels"


def not_found():
    return {"status_code": 404, "json": fj.error("NotFound")}


def respond(stub, *responses):
    for response in responses:
        stub.respond(**response)


def assert_direct_http(request, method, path):
    assert request.method == method
    assert request.url.host == STUB_HOSTNAME
    assert request.url.path == path
    assert request.headers["Authorization"] == f"Bearer {STUB_TOKEN}"


# ===== AnthropicModel.messages (beta) =====


def test_send_message_calls_the_beta_endpoint_with_preview(stub_foundry_http):
    stub_foundry_http.respond(json=lm.anthropic_response())

    response = LanguageModelsService().send_message(lm.MODEL_API_NAME, "Hello")

    assert isinstance(response, AnthropicMessagesResponse)
    assert response.content[0].text == "Hello there!"
    assert response.usage.output_tokens == 6
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", MESSAGES)
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {
        "messages": [{"role": "USER", "content": [{"type": "text", "text": "Hello"}]}],
        "maxTokens": 1024,
    }


def test_send_message_optional_fields(stub_foundry_http):
    stub_foundry_http.respond(json=lm.anthropic_response())

    LanguageModelsService().send_message(
        lm.MODEL_API_NAME,
        "Write a haiku",
        max_tokens=100,
        system="You are a poet",
        temperature=0.8,
        stop_sequences=["END"],
        top_k=40,
        top_p=0.9,
    )

    body = json.loads(stub_foundry_http.requests[0].content)
    assert body == {
        "messages": [
            {"role": "USER", "content": [{"type": "text", "text": "Write a haiku"}]}
        ],
        "maxTokens": 100,
        "system": [{"type": "text", "text": "You are a poet"}],
        "temperature": 0.8,
        "stopSequences": ["END"],
        "topK": 40,
        "topP": 0.9,
    }


def test_send_messages_advanced_sends_every_field_and_normalizes_roles(
    stub_foundry_http,
):
    stub_foundry_http.respond(json=lm.tool_use_response())
    tool = {
        "type": "custom",
        "name": "get_weather",
        "inputSchema": {"type": "object", "properties": {"city": {"type": "string"}}},
    }

    response = LanguageModelsService().send_messages_advanced(
        lm.MODEL_API_NAME,
        messages=[
            {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
            {"role": "assistant", "content": [{"type": "text", "text": "Hello!"}]},
            {"role": "user", "content": [{"type": "text", "text": "Weather?"}]},
        ],
        max_tokens=2000,
        system=[{"type": "text", "text": "Be brief"}],
        thinking={"type": "enabled", "budgetTokens": 1500},
        tools=[tool],
        tool_choice={"type": "auto"},
        output_config={"effort": "LOW"},
    )

    assert response.content[1].type == "toolUse"
    [request] = stub_foundry_http.requests
    assert request.url.params["preview"] == "true"
    body = json.loads(request.content)
    assert [message["role"] for message in body["messages"]] == [
        "USER",
        "ASSISTANT",
        "USER",
    ]
    assert body["maxTokens"] == 2000
    assert body["thinking"] == {"type": "enabled", "budgetTokens": 1500}
    assert body["tools"] == [tool]
    assert body["toolChoice"] == {"type": "auto"}
    assert body["outputConfig"] == {"effort": "LOW"}
    assert body["system"] == [{"type": "text", "text": "Be brief"}]


def test_send_message_sdk_errors_propagate(stub_foundry_http):
    stub_foundry_http.respond(
        403, json=fj.error("PermissionDenied", error_code="PERMISSION_DENIED")
    )

    with pytest.raises(PermissionDeniedError):
        LanguageModelsService().send_message(lm.MODEL_API_NAME, "Hello")


# ===== OpenAiModel.embeddings (beta) =====


def test_generate_embeddings_calls_the_beta_endpoint_with_preview(stub_foundry_http):
    stub_foundry_http.respond(json=lm.embeddings_response())

    response = LanguageModelsService().generate_embeddings(
        lm.EMBEDDING_MODEL, ["Doc 1", "Doc 2"]
    )

    assert isinstance(response, OpenAiEmbeddingsResponse)
    assert len(response.data) == 2
    assert response.usage.prompt_tokens == 4
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", EMBEDDINGS)
    assert dict(request.url.params) == {"preview": "true"}
    assert json.loads(request.content) == {"input": ["Doc 1", "Doc 2"]}


def test_generate_embeddings_dimensions_and_encoding(stub_foundry_http):
    stub_foundry_http.respond(json=lm.embeddings_response())

    LanguageModelsService().generate_embeddings(
        lm.EMBEDDING_MODEL, ["Doc"], dimensions=256, encoding_format="float"
    )

    body = json.loads(stub_foundry_http.requests[0].content)
    assert body == {"input": ["Doc"], "dimensions": 256, "encodingFormat": "FLOAT"}


# ===== enroll_model (direct HTTP) =====


def test_enroll_posts_an_empty_object_to_the_first_endpoint(stub_foundry_http):
    stub_foundry_http.respond(json={"status": "ENROLLED"})

    answer = LanguageModelsService().enroll_model(lm.MODEL_RID)

    assert answer.body == {"status": "ENROLLED"}
    assert answer.endpoint == f"POST {LIST}/{lm.MODEL_RID}/enroll"
    [request] = stub_foundry_http.requests
    assert_direct_http(request, "POST", f"{LIST}/{lm.MODEL_RID}/enroll")
    assert json.loads(request.content) == {}


def test_enroll_falls_back_to_the_second_endpoint(stub_foundry_http):
    respond(stub_foundry_http, not_found(), {"status_code": 204})

    answer = LanguageModelsService().enroll_model(lm.MODEL_RID)

    assert answer.body is None
    assert answer.endpoint == f"POST /api/v2/llm/models/{lm.MODEL_RID}/enroll"
    assert_direct_http(
        stub_foundry_http.requests[-1],
        "POST",
        f"/api/v2/llm/models/{lm.MODEL_RID}/enroll",
    )


def test_enroll_failure_points_to_the_model_catalog(stub_foundry_http):
    respond(
        stub_foundry_http,
        not_found(),
        {"status_code": 400, "json": fj.error("InvalidModel", "INVALID_ARGUMENT")},
    )

    with pytest.raises(RuntimeError) as raised:
        LanguageModelsService().enroll_model(lm.MODEL_RID)

    assert "Model Catalog" in str(raised.value)
    assert raised.value.__cause__.response.status_code == 400


def test_enroll_skips_an_answer_that_is_not_json(stub_foundry_http):
    respond(
        stub_foundry_http,
        {"content": b"<html>Foundry</html>", "headers": {"Content-Type": "text/html"}},
        {"json": {"status": "ENROLLED"}},
    )

    answer = LanguageModelsService().enroll_model(lm.MODEL_RID)

    assert answer.endpoint == f"POST /api/v2/llm/models/{lm.MODEL_RID}/enroll"


def test_enroll_prefers_a_non_404_error_over_a_later_404(stub_foundry_http):
    respond(
        stub_foundry_http,
        {
            "status_code": 401,
            "json": fj.error("Unauthorized", error_code="UNAUTHORIZED"),
        },
        not_found(),
    )

    with pytest.raises(RuntimeError) as raised:
        LanguageModelsService().enroll_model(lm.MODEL_RID)

    message = str(raised.value)
    assert f"POST {LIST}/{lm.MODEL_RID}/enroll -> HTTP 401" in message
    assert f"POST /api/v2/llm/models/{lm.MODEL_RID}/enroll -> HTTP 404" in message
    assert raised.value.__cause__.response.status_code == 401


def test_enroll_without_any_json_answer_is_an_api_error(stub_foundry_http):
    stub_foundry_http.respond_always(200, content=b"<html></html>")

    with pytest.raises(PltrError) as raised:
        LanguageModelsService().enroll_model(lm.MODEL_RID)

    assert raised.value.error_type == "api_error"
    assert "response is not JSON" in raised.value.message


def test_enroll_connection_errors_are_not_retried(stub_foundry_http, monkeypatch):
    calls = []

    def refuse(self, request, **kwargs):
        calls.append(request.url)
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", refuse)

    with pytest.raises(requests.ConnectionError):
        LanguageModelsService().enroll_model(lm.MODEL_RID)
    assert len(calls) == 1
