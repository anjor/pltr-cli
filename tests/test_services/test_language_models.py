"""Tests for LanguageModelsService against a real FoundryClient (only HTTP is faked).

``AnthropicModel.messages`` and ``OpenAiModel.embeddings`` are beta: every
request must carry ``preview=true``. The old Mock-based tests passed
``preview`` through from a CLI flag that defaulted to off, so the calls failed
unless users remembered ``--preview``.

``list_available_models``, ``get_model_enrollment_status`` and ``enroll_model``
are labeled direct-HTTP exceptions; their requests go through ``requests``,
which stub_foundry_http also records (with the bearer token of the SDK auth).
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
from pltr.services.language_models import (
    LanguageModelsService,
    ModelListing,
)
from tests import foundry_json as fj
from tests import foundry_json_language_models as lm
from tests.conftest import STUB_HOSTNAME, STUB_TOKEN

pytestmark = pytest.mark.filterwarnings("error::UserWarning")

MESSAGES = f"/api/v2/languageModels/anthropic/{lm.MODEL_API_NAME}/messages"
EMBEDDINGS = f"/api/v2/languageModels/openAi/{lm.EMBEDDING_MODEL}/embeddings"
LIST = "/api/v2/languageModels"
PROXY_MODELS = "/api/v2/llm/proxy/openai/v1/models"


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


# ===== list_available_models (direct HTTP) =====


def test_list_models_from_the_first_endpoint(stub_foundry_http):
    models = [lm.language_model(), lm.language_model(status="PREVIEW")]
    stub_foundry_http.respond(json={"data": models})

    listing = LanguageModelsService().list_available_models()

    assert listing == ModelListing(endpoint=f"GET {LIST}", models=models)
    [request] = stub_foundry_http.requests
    assert_direct_http(request, "GET", LIST)


def test_list_models_falls_back_to_the_openai_proxy(stub_foundry_http):
    respond(
        stub_foundry_http,
        not_found(),
        {"json": lm.proxy_models(lm.proxy_model(), lm.proxy_model("gpt-4.1"))},
    )

    listing = LanguageModelsService().list_available_models()

    assert listing.endpoint == f"GET {PROXY_MODELS}"
    assert [model["id"] for model in listing.models] == ["gpt-4o", "gpt-4.1"]
    first, second = stub_foundry_http.requests
    assert_direct_http(first, "GET", LIST)
    assert_direct_http(second, "GET", PROXY_MODELS)


def test_list_models_keeps_the_next_page_token(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [lm.language_model()], "nextPageToken": "tok-2"}
    )

    listing = LanguageModelsService().list_available_models()

    assert listing.next_page_token == "tok-2"


def test_list_models_reads_data_before_models(stub_foundry_http):
    stub_foundry_http.respond(json={"data": [], "models": [lm.language_model()]})

    assert LanguageModelsService().list_available_models().models == []
    assert len(stub_foundry_http.requests) == 1


def test_list_models_reads_a_models_list_or_a_bare_list(stub_foundry_http):
    stub_foundry_http.respond(json={"models": [lm.language_model()]})
    stub_foundry_http.respond(json=[lm.language_model(), "not a model"])

    service = LanguageModelsService()

    assert service.list_available_models().models == [lm.language_model()]
    assert service.list_available_models().models == [lm.language_model()]


def test_list_models_skips_an_answer_that_is_not_json(stub_foundry_http):
    respond(
        stub_foundry_http,
        {"content": b"<html>Foundry</html>", "headers": {"Content-Type": "text/html"}},
        {"json": lm.proxy_models(lm.proxy_model())},
    )

    listing = LanguageModelsService().list_available_models()

    assert listing.endpoint == f"GET {PROXY_MODELS}"


def test_list_models_reports_the_most_telling_http_error(stub_foundry_http):
    respond(
        stub_foundry_http,
        not_found(),
        {
            "status_code": 403,
            "json": fj.error("PermissionDenied", error_code="PERMISSION_DENIED"),
        },
    )

    with pytest.raises(RuntimeError) as raised:
        LanguageModelsService().list_available_models()

    message = str(raised.value)
    assert f"GET {LIST} -> HTTP 404" in message
    assert f"GET {PROXY_MODELS} -> HTTP 403" in message
    cause = raised.value.__cause__
    assert isinstance(cause, requests.HTTPError)
    assert cause.response.status_code == 403


def test_list_models_prefers_a_non_404_error_over_a_later_404(stub_foundry_http):
    respond(
        stub_foundry_http,
        {
            "status_code": 401,
            "json": fj.error("Unauthorized", error_code="UNAUTHORIZED"),
        },
        not_found(),
    )

    with pytest.raises(RuntimeError) as raised:
        LanguageModelsService().list_available_models()

    assert raised.value.__cause__.response.status_code == 401


def test_list_models_all_not_found(stub_foundry_http):
    stub_foundry_http.respond_always(404, json=fj.error("NotFound"))

    with pytest.raises(RuntimeError) as raised:
        LanguageModelsService().list_available_models()

    assert raised.value.__cause__.response.status_code == 404
    assert len(stub_foundry_http.requests) == 2


def test_list_models_without_any_json_answer_is_an_api_error(stub_foundry_http):
    stub_foundry_http.respond_always(200, content=b"<html></html>")

    with pytest.raises(PltrError) as raised:
        LanguageModelsService().list_available_models()

    assert raised.value.error_type == "api_error"
    assert "response is not JSON" in raised.value.message


def test_list_models_connection_errors_are_not_retried(stub_foundry_http, monkeypatch):
    calls = []

    def refuse(self, request, **kwargs):
        calls.append(request.url)
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", refuse)

    with pytest.raises(requests.ConnectionError):
        LanguageModelsService().list_available_models()
    assert len(calls) == 1


# ===== get_model_enrollment_status (direct HTTP) =====


def test_status_from_the_first_endpoint_unwraps_a_data_envelope(stub_foundry_http):
    stub_foundry_http.respond(json={"data": lm.language_model()})

    answer = LanguageModelsService().get_model_enrollment_status(lm.MODEL_RID)

    assert answer.body == lm.language_model()
    assert answer.endpoint == f"GET {LIST}/{lm.MODEL_RID}"
    assert not answer.via_openai_proxy
    [request] = stub_foundry_http.requests
    assert_direct_http(request, "GET", f"{LIST}/{lm.MODEL_RID}")


def test_status_url_encodes_the_model_id(stub_foundry_http):
    stub_foundry_http.respond(json=lm.language_model())

    LanguageModelsService().get_model_enrollment_status("models/claude 3")

    [request] = stub_foundry_http.requests
    assert request.url.raw_path == b"/api/v2/languageModels/models%2Fclaude%203"


def test_status_from_the_second_endpoint(stub_foundry_http):
    respond(stub_foundry_http, not_found(), {"json": lm.language_model()})

    answer = LanguageModelsService().get_model_enrollment_status(lm.MODEL_RID)

    assert answer.endpoint == f"GET /api/v2/llm/models/{lm.MODEL_RID}"
    assert answer.body["status"] == "ENROLLED"


def test_status_falls_back_to_the_openai_proxy_list(stub_foundry_http):
    respond(
        stub_foundry_http,
        not_found(),
        not_found(),
        {"json": lm.proxy_models(lm.proxy_model("gpt-4.1"), lm.proxy_model())},
    )

    answer = LanguageModelsService().get_model_enrollment_status("gpt-4o")

    assert answer.via_openai_proxy
    assert answer.body == lm.proxy_model()
    assert_direct_http(stub_foundry_http.requests[-1], "GET", PROXY_MODELS)


def test_status_of_a_model_nobody_knows_is_not_found(stub_foundry_http):
    respond(
        stub_foundry_http,
        not_found(),
        not_found(),
        {"json": lm.proxy_models(lm.proxy_model())},
    )

    with pytest.raises(PltrError) as raised:
        LanguageModelsService().get_model_enrollment_status("missing-model")

    assert raised.value.error_type == "not_found"
    assert raised.value.exit_code == 5
    assert "missing-model" in raised.value.message


def test_status_when_every_endpoint_fails(stub_foundry_http):
    respond(
        stub_foundry_http,
        not_found(),
        not_found(),
        {"status_code": 503, "json": fj.error("Unavailable", error_code="INTERNAL")},
    )

    with pytest.raises(RuntimeError) as raised:
        LanguageModelsService().get_model_enrollment_status(lm.MODEL_RID)

    assert f"GET {PROXY_MODELS} -> HTTP 503" in str(raised.value)
    assert raised.value.__cause__.response.status_code == 503


def test_status_skips_an_answer_that_is_not_json(stub_foundry_http):
    respond(
        stub_foundry_http,
        {"content": b"not json"},
        {"json": lm.language_model()},
    )

    answer = LanguageModelsService().get_model_enrollment_status(lm.MODEL_RID)

    assert answer.endpoint == f"GET /api/v2/llm/models/{lm.MODEL_RID}"


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
