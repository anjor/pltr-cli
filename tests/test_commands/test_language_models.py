"""Tests for `pltr language-models` against a real FoundryClient (only HTTP is faked).

These replace Mock-based tests that patched the service: they asserted that
``--preview`` was passed through to the beta SDK methods (so the commands
failed without it), and that JSON output had pltr's own keys.
"""

import csv
import io
import json
from unittest.mock import Mock

import pytest
from foundry_sdk.v2.language_models.models import AnthropicMessagesRequest
from typer.testing import CliRunner

from pltr.auth.base import ProfileNotFoundError
from pltr.cli import app
from pltr.commands.language_models import MESSAGES_REQUEST_FIELDS
from tests import foundry_json as fj
from tests import foundry_json_language_models as lm
from tests.conftest import STUB_TOKEN

pytestmark = [
    pytest.mark.filterwarnings("error::UserWarning"),
    pytest.mark.usefixtures("isolated_home"),
]

runner = CliRunner()

MESSAGES = f"/api/v2/languageModels/anthropic/{lm.MODEL_API_NAME}/messages"
EMBEDDINGS = f"/api/v2/languageModels/openAi/{lm.EMBEDDING_MODEL}/embeddings"
PROXY_MODELS = "/api/v2/llm/proxy/openai/v1/models"
SIMPLE_REQUEST = {
    "messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}],
    "maxTokens": 100,
}


def invoke(*args: str, **kwargs):
    return runner.invoke(app, list(args), **kwargs)


def json_lines(stderr: str) -> list:
    return [json.loads(line) for line in stderr.splitlines() if line.strip()]


def json_error(result) -> dict:
    return json_lines(result.stderr)[-1]


def not_found():
    return {"status_code": 404, "json": fj.error("NotFound")}


def test_sdk_commands_are_labeled_beta_and_direct_http_ones_are_not():
    anthropic = invoke("language-models", "anthropic", "--help").stdout
    openai = invoke("language-models", "openai", "--help").stdout
    top = invoke("language-models", "--help").stdout

    for line in anthropic.splitlines() + openai.splitlines():
        if " messages " in line or " embeddings " in line:
            assert "[beta]" in line, line
    for command in ("list", "status", "enroll"):
        line = next(line for line in top.splitlines() if f" {command} " in line)
        assert "[beta]" not in line, line


def test_messages_request_fields_match_the_sdk():
    fields = AnthropicMessagesRequest.model_fields
    assert set(MESSAGES_REQUEST_FIELDS) == {
        info.alias or name for name, info in fields.items()
    }


# ======================================================= anthropic messages


def test_messages_table_shows_the_reply_and_token_usage(stub_foundry_http):
    stub_foundry_http.respond(json=lm.anthropic_response("Quantum bits are qubits."))

    result = invoke(
        "language-models",
        "anthropic",
        "messages",
        lm.MODEL_API_NAME,
        "--message",
        "Explain quantum computing",
    )

    assert result.exit_code == 0, result.output
    for expected in ("Quantum bits are qubits.", "end_turn", "ASSISTANT", "12", "6"):
        assert expected in result.stdout
    assert result.stderr == ""
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", MESSAGES)
    assert request.url.params["preview"] == "true"
    assert json.loads(request.content) == {
        "messages": [
            {
                "role": "USER",
                "content": [{"type": "text", "text": "Explain quantum computing"}],
            }
        ],
        "maxTokens": 1024,
    }


def test_messages_json_is_the_sdk_serialization(stub_foundry_http):
    stub_foundry_http.respond(json=lm.anthropic_response())

    result = invoke(
        "language-models",
        "anthropic",
        "messages",
        lm.MODEL_API_NAME,
        "-m",
        "Hello",
        "--format",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == lm.anthropic_response()
    assert result.stderr == ""


def test_messages_csv(stub_foundry_http):
    stub_foundry_http.respond(json=lm.tool_use_response())

    result = invoke(
        "language-models",
        "anthropic",
        "messages",
        lm.MODEL_API_NAME,
        "-m",
        "Weather?",
        "-f",
        "csv",
    )

    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row["Text"] == "Let me check the weather."
    assert row["Stop Reason"] == "tool_use"
    assert json.loads(row["Tool Use"]) == [
        {
            "id": "toolu_01A09q90qw90lq917835lq9",
            "name": "get_weather",
            "input": {"city": "London"},
        }
    ]
    assert (row["Input Tokens"], row["Output Tokens"]) == ("12", "6")


def test_messages_options(stub_foundry_http):
    stub_foundry_http.respond(json=lm.anthropic_response())

    result = invoke(
        "language-models",
        "anthropic",
        "messages",
        lm.MODEL_API_NAME,
        "-m",
        "Write a haiku",
        "--system",
        "You are a poet",
        "--temperature",
        "0.8",
        "--max-tokens",
        "100",
        "--stop",
        ".",
        "--stop",
        "END",
        "--top-k",
        "40",
        "--top-p",
        "0.9",
        "--profile",
        "dev",
    )

    assert result.exit_code == 0, result.output
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body["system"] == [{"type": "text", "text": "You are a poet"}]
    assert body["temperature"] == 0.8
    assert body["maxTokens"] == 100
    assert body["stopSequences"] == [".", "END"]
    assert (body["topK"], body["topP"]) == (40, 0.9)


def test_messages_preview_flag_is_a_deprecated_no_op(stub_foundry_http):
    stub_foundry_http.respond(json=lm.anthropic_response())

    result = invoke(
        "language-models",
        "anthropic",
        "messages",
        lm.MODEL_API_NAME,
        "-m",
        "Hi",
        "--preview",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    [warning] = json_lines(result.stderr)
    assert warning["type"] == "warning"
    assert "--preview is deprecated" in warning["message"]
    assert stub_foundry_http.requests[0].url.params["preview"] == "true"


def test_messages_temperature_out_of_range(stub_foundry_http):
    result = invoke(
        "language-models",
        "anthropic",
        "messages",
        lm.MODEL_API_NAME,
        "-m",
        "Hi",
        "-t",
        "1.5",
    )

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_messages_permission_denied(stub_foundry_http):
    stub_foundry_http.respond(
        403, json=fj.error("PermissionDenied", error_code="PERMISSION_DENIED")
    )

    result = invoke(
        "language-models",
        "anthropic",
        "messages",
        lm.MODEL_API_NAME,
        "-m",
        "Hi",
        "-f",
        "json",
    )

    assert result.exit_code == 4
    assert result.stdout == ""
    assert json_error(result)["type"] == "permission_denied"


def test_messages_preview_usage_rejected_by_the_server(stub_foundry_http):
    stub_foundry_http.respond(
        400,
        json=fj.error("ApiFeaturePreviewUsageOnly", error_code="INVALID_ARGUMENT"),
    )

    result = invoke(
        "language-models", "anthropic", "messages", lm.MODEL_API_NAME, "-m", "Hi"
    )

    assert result.exit_code == 6
    assert "ApiFeaturePreviewUsageOnly" in result.stderr


# ============================================== anthropic messages-advanced


def test_messages_advanced_inline_request(stub_foundry_http):
    stub_foundry_http.respond(json=lm.anthropic_response())

    result = invoke(
        "language-models",
        "anthropic",
        "messages-advanced",
        lm.MODEL_API_NAME,
        "--request",
        json.dumps(SIMPLE_REQUEST),
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == lm.anthropic_response()
    [request] = stub_foundry_http.requests
    assert request.url.params["preview"] == "true"
    assert json.loads(request.content) == {
        "messages": [{"role": "USER", "content": [{"type": "text", "text": "Hi"}]}],
        "maxTokens": 100,
    }


def test_messages_advanced_request_from_file(stub_foundry_http, tmp_path):
    request_file = tmp_path / "conversation.json"
    request_file.write_text(
        json.dumps(
            {
                "messages": [
                    {"role": "USER", "content": [{"type": "text", "text": "Hi"}]},
                    {
                        "role": "ASSISTANT",
                        "content": [{"type": "text", "text": "Hello!"}],
                    },
                    {"role": "USER", "content": [{"type": "text", "text": "Help"}]},
                ],
                "maxTokens": 2000,
                "system": [{"type": "text", "text": "Be concise"}],
                "thinking": {"type": "enabled", "budgetTokens": 1500},
                "stopSequences": ["END"],
                "topK": 5,
                "topP": 0.5,
                "temperature": 0.2,
                "toolChoice": {"type": "none"},
                "tools": [
                    {
                        "type": "custom",
                        "name": "noop",
                        "inputSchema": {"type": "object"},
                    }
                ],
                "outputConfig": {"effort": "HIGH"},
            }
        )
    )
    stub_foundry_http.respond(json=lm.anthropic_response())

    result = invoke(
        "language-models",
        "anthropic",
        "messages-advanced",
        lm.MODEL_API_NAME,
        "-r",
        f"@{request_file}",
    )

    assert result.exit_code == 0, result.output
    body = json.loads(stub_foundry_http.requests[0].content)
    assert len(body["messages"]) == 3
    assert body["thinking"] == {"type": "enabled", "budgetTokens": 1500}
    assert body["outputConfig"] == {"effort": "HIGH"}
    assert body["toolChoice"] == {"type": "none"}
    assert (body["topK"], body["topP"], body["temperature"]) == (5, 0.5, 0.2)


@pytest.mark.parametrize(
    "request_json, message",
    [
        ({"maxTokens": 10}, "must include messages"),
        ({"messages": []}, "must include maxTokens"),
        ({**SIMPLE_REQUEST, "max_tokens": 5}, "unknown field(s) max_tokens"),
        ([SIMPLE_REQUEST], "must be a JSON object"),
    ],
)
def test_messages_advanced_checks_the_request(stub_foundry_http, request_json, message):
    result = invoke(
        "language-models",
        "anthropic",
        "messages-advanced",
        lm.MODEL_API_NAME,
        "--request",
        json.dumps(request_json),
        "-f",
        "json",
    )

    assert result.exit_code == 2
    error = json_error(result)
    assert error["type"] == "usage_error"
    assert message in error["message"]
    assert stub_foundry_http.requests == []


def test_messages_advanced_invalid_json(stub_foundry_http):
    result = invoke(
        "language-models",
        "anthropic",
        "messages-advanced",
        lm.MODEL_API_NAME,
        "-r",
        "{oops",
    )

    assert result.exit_code == 2
    assert "invalid JSON" in result.stderr
    assert stub_foundry_http.requests == []


def test_messages_advanced_bad_thinking_config_is_a_usage_error(stub_foundry_http):
    """The old help's example used "budget"; the API field is budgetTokens."""
    request_json = {**SIMPLE_REQUEST, "thinking": {"type": "enabled", "budget": 10000}}

    result = invoke(
        "language-models",
        "anthropic",
        "messages-advanced",
        lm.MODEL_API_NAME,
        "-r",
        json.dumps(request_json),
        "-f",
        "json",
    )

    assert result.exit_code == 2
    error = json_error(result)
    assert error["type"] == "usage_error"
    assert "thinking.enabled.budgetTokens: Field required" in error["message"]
    assert stub_foundry_http.requests == []


# ========================================================= openai embeddings


def test_embeddings_table_previews_each_vector(stub_foundry_http):
    stub_foundry_http.respond(json=lm.embeddings_response())

    result = invoke(
        "language-models",
        "openai",
        "embeddings",
        lm.EMBEDDING_MODEL,
        "-i",
        "Machine learning",
    )

    assert result.exit_code == 0, result.output
    assert "[0.0123, -0.0456, 0.0789, 0.1011, ...]" in result.stdout
    assert "text-embedding-3-small (4 prompt tokens)" in result.stdout
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == ("POST", EMBEDDINGS)
    assert request.url.params["preview"] == "true"
    assert json.loads(request.content) == {"input": ["Machine learning"]}


def test_embeddings_csv_has_the_whole_vector(stub_foundry_http):
    stub_foundry_http.respond(json=lm.embeddings_response())

    result = invoke(
        "language-models",
        "openai",
        "embeddings",
        lm.EMBEDDING_MODEL,
        "--input",
        '["Doc 1", "Doc 2"]',
        "-f",
        "csv",
    )

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    assert [row["Input"] for row in rows] == ["0", "1"]
    assert rows[0]["Dimensions"] == "5"
    assert json.loads(rows[0]["Embedding"]) == [
        0.0123,
        -0.0456,
        0.0789,
        0.1011,
        -0.1213,
    ]
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body == {"input": ["Doc 1", "Doc 2"]}


def test_embeddings_json_is_the_sdk_serialization(stub_foundry_http, tmp_path):
    texts = tmp_path / "texts.json"
    texts.write_text('["Text 1", "Text 2"]')
    stub_foundry_http.respond(json=lm.embeddings_response())

    result = invoke(
        "language-models",
        "openai",
        "embeddings",
        lm.EMBEDDING_MODEL,
        "-i",
        f"@{texts}",
        "--dimensions",
        "5",
        "--encoding",
        "FLOAT",
        "-f",
        "json",
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == lm.embeddings_response()
    body = json.loads(stub_foundry_http.requests[0].content)
    assert body == {
        "input": ["Text 1", "Text 2"],
        "dimensions": 5,
        "encodingFormat": "FLOAT",
    }


@pytest.mark.parametrize("value", ["[1, 2]", "[]", "@missing.json", "[oops"])
def test_embeddings_rejects_bad_input(stub_foundry_http, value):
    result = invoke(
        "language-models", "openai", "embeddings", lm.EMBEDDING_MODEL, "-i", value
    )

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_embeddings_rejects_an_unknown_encoding(stub_foundry_http):
    result = invoke(
        "language-models",
        "openai",
        "embeddings",
        lm.EMBEDDING_MODEL,
        "-i",
        "x",
        "-e",
        "int8",
    )

    assert result.exit_code == 2
    assert stub_foundry_http.requests == []


def test_embeddings_preview_flag_is_a_deprecated_no_op(stub_foundry_http):
    stub_foundry_http.respond(json=lm.embeddings_response())

    result = invoke(
        "language-models",
        "openai",
        "embeddings",
        lm.EMBEDDING_MODEL,
        "-i",
        "x",
        "--preview",
    )

    assert result.exit_code == 0, result.output
    assert "--preview is deprecated" in result.stderr


# ============================================== list (labeled direct HTTP)


def test_list_table(stub_foundry_http):
    stub_foundry_http.respond(
        json={
            "data": [
                lm.language_model(),
                lm.language_model("ri.x..y.z", "Other", "PREVIEW"),
            ]
        }
    )

    result = invoke("language-models", "list")

    assert result.exit_code == 0, result.output
    for expected in (
        lm.MODEL_RID,
        "Claude 3.5 Sonnet",
        "ENROLLED",
        "ANTHROPIC",
        "PREVIEW",
    ):
        assert expected in result.stdout
    assert "Models from GET /api/v2/languageModels" in result.stderr
    [request] = stub_foundry_http.requests
    assert request.url.path == "/api/v2/languageModels"
    assert request.headers["Authorization"] == f"Bearer {STUB_TOKEN}"


def test_list_json_keeps_the_endpoints_model_objects(stub_foundry_http):
    stub_foundry_http.respond(
        json={"data": [lm.language_model()], "nextPageToken": "t"}
    )

    result = invoke("language-models", "list", "--format", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "data": [lm.language_model()],
        "nextPageToken": "t",
    }
    assert result.stderr == ""


def test_list_from_the_openai_proxy(stub_foundry_http):
    stub_foundry_http.respond(**not_found())
    stub_foundry_http.respond(json=lm.proxy_models(lm.proxy_model()))

    result = invoke("language-models", "list", "-f", "csv")

    assert result.exit_code == 0, result.output
    [row] = list(csv.DictReader(io.StringIO(result.stdout)))
    assert row == {
        "Model": "gpt-4o",
        "Display Name": "",
        "Status": "",
        "Type": "openai",
    }
    assert "OpenAI-compatible proxy" in result.stderr
    assert stub_foundry_http.requests[-1].url.path == PROXY_MODELS


def test_list_empty(stub_foundry_http):
    stub_foundry_http.respond(json={"data": []})

    result = invoke("language-models", "list")

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "No results." in result.stderr


@pytest.mark.parametrize(
    "status, code, error_type, exit_code",
    [
        (404, "NOT_FOUND", "not_found", 5),
        (403, "PERMISSION_DENIED", "permission_denied", 4),
        (401, "UNAUTHORIZED", "auth_error", 3),
        (500, "INTERNAL", "server_error", 7),
    ],
)
def test_list_errors_are_structured(
    stub_foundry_http, status, code, error_type, exit_code
):
    stub_foundry_http.respond_always(status, json=fj.error("SomeError", code))

    result = invoke("language-models", "list", "-f", "json")

    assert result.exit_code == exit_code
    assert result.stdout == ""
    error = json_error(result)
    assert (error["type"], error["statusCode"], error["errorName"]) == (
        error_type,
        status,
        "SomeError",
    )
    assert error["errorInstanceId"] == fj.ERROR_INSTANCE_ID
    assert "GET /api/v2/languageModels -> HTTP" in error["message"]


def test_list_missing_credentials_is_an_auth_error(monkeypatch):
    # Same seam stub_foundry_http uses: the AuthManager services construct.
    auth_manager = Mock()
    auth_manager.return_value.get_auth_context.side_effect = ProfileNotFoundError(
        "No profile configured"
    )
    monkeypatch.setattr("pltr.services.base.AuthManager", auth_manager)

    result = invoke("language-models", "list", "-f", "json")

    assert result.exit_code == 3
    error = json_error(result)
    assert (error["type"], error["message"]) == ("auth_error", "No profile configured")


# ============================================ status (labeled direct HTTP)


def test_status_table(stub_foundry_http):
    stub_foundry_http.respond(json=lm.language_model())

    result = invoke("language-models", "status", lm.MODEL_RID)

    assert result.exit_code == 0, result.output
    for expected in (lm.MODEL_RID, "Claude 3.5 Sonnet", "ENROLLED", "ANTHROPIC"):
        assert expected in result.stdout
    [request] = stub_foundry_http.requests
    assert request.url.path == f"/api/v2/languageModels/{lm.MODEL_RID}"


def test_status_json(stub_foundry_http):
    stub_foundry_http.respond(json=lm.language_model())

    result = invoke("language-models", "status", lm.MODEL_RID, "-f", "json")

    assert json.loads(result.stdout) == lm.language_model()
    assert result.stderr == ""


def test_status_via_the_openai_proxy(stub_foundry_http):
    stub_foundry_http.respond(**not_found())
    stub_foundry_http.respond(**not_found())
    stub_foundry_http.respond(json=lm.proxy_models(lm.proxy_model()))

    result = invoke("language-models", "status", "gpt-4o")

    assert result.exit_code == 0, result.output
    assert "gpt-4o" in result.stdout
    assert "reports no enrollment status" in result.stderr


def test_status_unknown_model_is_not_found(stub_foundry_http):
    stub_foundry_http.respond(**not_found())
    stub_foundry_http.respond(**not_found())
    stub_foundry_http.respond(json=lm.proxy_models(lm.proxy_model()))

    result = invoke("language-models", "status", "missing-model", "-f", "json")

    assert result.exit_code == 5
    error = json_error(result)
    assert error["type"] == "not_found"
    assert "missing-model" in error["message"]


# ============================================ enroll (labeled direct HTTP)


def test_enroll(stub_foundry_http):
    stub_foundry_http.respond(json={"rid": lm.MODEL_RID, "status": "ENROLLED"})

    result = invoke("language-models", "enroll", lm.MODEL_RID)

    assert result.exit_code == 0, result.output
    assert "ENROLLED" in result.stdout
    assert f"Enrolled model {lm.MODEL_RID}" in result.stderr
    [request] = stub_foundry_http.requests
    assert (request.method, request.url.path) == (
        "POST",
        f"/api/v2/languageModels/{lm.MODEL_RID}/enroll",
    )
    assert request.headers["Authorization"] == f"Bearer {STUB_TOKEN}"


def test_enroll_without_a_response_body_prints_null(stub_foundry_http):
    stub_foundry_http.respond(**not_found())
    stub_foundry_http.respond(204)

    result = invoke("language-models", "enroll", lm.MODEL_RID, "-f", "json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) is None
    assert result.stderr == ""


def test_enroll_failure_mentions_the_model_catalog(stub_foundry_http):
    stub_foundry_http.respond_always(
        403, json=fj.error("PermissionDenied", "PERMISSION_DENIED")
    )

    result = invoke("language-models", "enroll", lm.MODEL_RID)

    assert result.exit_code == 4
    assert "Model Catalog" in result.stderr
    assert result.stdout == ""
