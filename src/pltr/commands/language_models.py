"""
Language model commands: Anthropic Claude messages, OpenAI embeddings, and
enrolling models.
"""

from typing import Any, Callable, Dict, List, Optional

import click
import typer
from typing_extensions import Annotated

from ..contract import (
    Columns,
    FormatOption,
    OutputOption,
    PreviewNoopOption,
    ProfileOption,
    emit,
    load_json_input,
    pltr_command,
    spinner,
    success,
)
from ..services.language_models import (
    MODEL_ENROLL_ENDPOINTS,
    LanguageModelsService,
)

app = typer.Typer(help="Interact with language models")
anthropic_app = typer.Typer(help="Anthropic Claude models")
openai_app = typer.Typer(help="OpenAI models")

app.add_typer(anthropic_app, name="anthropic")
app.add_typer(openai_app, name="openai")

#: Top-level fields of the API's ``AnthropicMessagesRequest`` (its JSON names),
#: accepted by ``messages-advanced --request``.
MESSAGES_REQUEST_FIELDS = (
    "messages",
    "maxTokens",
    "stopSequences",
    "system",
    "temperature",
    "thinking",
    "toolChoice",
    "tools",
    "topK",
    "topP",
    "outputConfig",
)

ModelApiName = Annotated[
    str,
    typer.Argument(
        help="The model's API name (LanguageModelApiName in the Foundry API).",
        show_default=False,
    ),
]

ModelIdentifier = Annotated[
    str,
    typer.Argument(
        help=(
            "Model RID (ri.language-model-service..language-model.<name>) or API name."
        ),
        show_default=False,
    ),
]


# ------------------------------------------------------------------ columns


def _response_text(response: Any) -> str:
    """The text blocks of an ``AnthropicMessagesResponse``, joined."""
    return "\n".join(block.text for block in response.content if block.type == "text")


def _tool_uses(response: Any) -> Optional[List[Dict[str, Any]]]:
    """The tool calls of an ``AnthropicMessagesResponse``, if any."""
    calls = [
        {"id": block.id, "name": block.name, "input": block.input}
        for block in response.content
        if block.type == "toolUse"
    ]
    return calls or None


#: Table/CSV columns for an ``AnthropicMessagesResponse``.
MESSAGE_COLUMNS: Columns = {
    "ID": "id",
    "Model": "model",
    "Role": "role",
    "Stop Reason": "stop_reason",
    "Stop Sequence": "stop_sequence",
    "Text": _response_text,
    "Tool Use": _tool_uses,
    "Input Tokens": "usage.input_tokens",
    "Output Tokens": "usage.output_tokens",
}


def _embedding_rows(response: Any) -> List[Dict[str, Any]]:
    """One table/CSV row per vector of an ``OpenAiEmbeddingsResponse``."""
    return [
        {"index": index, "embedding": vector}
        for index, vector in enumerate(response.data)
    ]


def _embedding_preview(row: Dict[str, Any]) -> str:
    vector = row["embedding"]
    head = ", ".join(f"{value:.6g}" for value in vector[:4])
    return f"[{head}, ...]" if len(vector) > 4 else f"[{head}]"


#: Table columns for ``openai embeddings`` (the vector is shortened).
EMBEDDING_TABLE_COLUMNS: Columns = {
    "Input": "index",
    "Dimensions": lambda row: len(row["embedding"]),
    "Embedding": _embedding_preview,
}

#: CSV columns for ``openai embeddings`` (the whole vector, as a JSON array).
EMBEDDING_CSV_COLUMNS: Columns = {
    "Input": "index",
    "Dimensions": lambda row: len(row["embedding"]),
    "Embedding": "embedding",
}


def _first(*keys: str) -> Callable[[Dict[str, Any]], Any]:
    """Column reading the first of ``keys`` the model object has.

    The direct-HTTP enroll endpoints return plain JSON whose field names may
    differ by endpoint; a missing field renders empty.
    """

    def get(item: Dict[str, Any]) -> Any:
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return value
        return None

    return get


#: Table/CSV columns for the model object ``enroll`` returns.
MODEL_COLUMNS: Columns = {
    "Model": _first("rid", "modelRid", "id", "apiName", "name"),
    "Display Name": _first("displayName", "name"),
    "Status": _first("status", "enrollmentStatus"),
    "Type": _first("type", "provider", "modelType", "family", "owned_by"),
}


# ------------------------------------------------------------------ helpers


def _parse_messages_request(value: str) -> Dict[str, Any]:
    """Parse and check ``--request`` (inline JSON or @file.json)."""
    request = load_json_input(value, param_hint="'--request'")
    if not isinstance(request, dict):
        raise typer.BadParameter(
            "the request must be a JSON object", param_hint="'--request'"
        )
    unknown = sorted(set(request) - set(MESSAGES_REQUEST_FIELDS))
    if unknown:
        raise typer.BadParameter(
            f"unknown field(s) {', '.join(unknown)}; the request takes "
            f"{', '.join(MESSAGES_REQUEST_FIELDS)} (the API's JSON names)",
            param_hint="'--request'",
        )
    missing = [field for field in ("messages", "maxTokens") if field not in request]
    if missing:
        raise typer.BadParameter(
            f"the request must include {' and '.join(missing)}",
            param_hint="'--request'",
        )
    return request


def _parse_input_texts(value: str) -> List[str]:
    """Parse ``--input``: a string, a JSON array of strings, or @file.json."""
    data: Any = value
    if value.startswith(("@", "[")):
        data = load_json_input(value, param_hint="'--input'")
    if isinstance(data, str):
        return [data]
    if isinstance(data, list) and data and all(isinstance(t, str) for t in data):
        return data
    raise typer.BadParameter(
        "expected a string or a non-empty JSON array of strings",
        param_hint="'--input'",
    )


# ===== Models (labeled direct-HTTP exceptions) =====


@app.command("enroll")
@pltr_command(http=tuple(f"POST {path}" for path in MODEL_ENROLL_ENDPOINTS))
def enroll_model(
    model_id: ModelIdentifier,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
):
    """Enroll (enable) a language model for API use.

    The Foundry Platform SDK has no endpoint for this, so pltr calls Foundry
    directly: POST /api/v2/languageModels/MODEL_ID/enroll, then
    POST /api/v2/llm/models/MODEL_ID/enroll. As these endpoints aren't in the
    SDK, not every Foundry stack may have them; if both fail, enroll the
    model in the Model Catalog in the Foundry UI.

    JSON output is the endpoint's response body (null when it has none).
    """
    with spinner("Enrolling model..."):
        answer = LanguageModelsService(profile=profile).enroll_model(model_id)
    success(f"Enrolled model {model_id} ({answer.endpoint})")
    emit(
        answer.body,
        format=format,
        output=output,
        columns=MODEL_COLUMNS,
        title="Language model",
    )


# ===== Anthropic =====


@anthropic_app.command("messages")
@pltr_command(sdk="language_models.AnthropicModel.messages", beta=True)
def anthropic_messages(
    model_id: ModelApiName,
    message: Annotated[
        str,
        typer.Option("--message", "-m", help="User message text.", show_default=False),
    ],
    max_tokens: Annotated[
        int, typer.Option("--max-tokens", help="Maximum number of tokens to generate.")
    ] = 1024,
    system: Annotated[
        Optional[str],
        typer.Option(
            "--system",
            "-s",
            help="System prompt to guide the model.",
            show_default=False,
        ),
    ] = None,
    temperature: Annotated[
        Optional[float],
        typer.Option(
            "--temperature",
            "-t",
            min=0.0,
            max=1.0,
            help="Sampling temperature (0.0-1.0). Lower is more deterministic.",
            show_default=False,
        ),
    ] = None,
    stop: Annotated[
        Optional[List[str]],
        typer.Option(
            "--stop", help="Stop sequence (repeat for several).", show_default=False
        ),
    ] = None,
    top_k: Annotated[
        Optional[int],
        typer.Option(
            "--top-k",
            min=1,
            help="Sample from the top K tokens.",
            show_default=False,
        ),
    ] = None,
    top_p: Annotated[
        Optional[float],
        typer.Option(
            "--top-p",
            min=0.0,
            max=1.0,
            help="Nucleus sampling threshold (0.0-1.0).",
            show_default=False,
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Send one message to an Anthropic Claude model.

    For multi-turn conversations, tools or extended thinking, use
    messages-advanced. The table shows the reply's text and token usage;
    --format json prints the API's whole response.

    Examples:

    \b
    pltr language-models anthropic messages <MODEL_API_NAME> -m "Explain RIDs"
    pltr language-models anthropic messages <MODEL_API_NAME> -m "Write a haiku" \\
        --system "You are a poet" --temperature 0.8 --max-tokens 100
    """
    with spinner("Sending message..."):
        response = LanguageModelsService(profile=profile).send_message(
            model_id,
            message,
            max_tokens=max_tokens,
            system=system,
            temperature=temperature,
            stop_sequences=list(stop) if stop else None,
            top_k=top_k,
            top_p=top_p,
        )
    emit(response, format=format, output=output, columns=MESSAGE_COLUMNS)


@anthropic_app.command("messages-advanced")
@pltr_command(sdk="language_models.AnthropicModel.messages", beta=True)
def anthropic_messages_advanced(
    model_id: ModelApiName,
    request: Annotated[
        str,
        typer.Option(
            "--request",
            "-r",
            help=(
                "The API's messages request as JSON, inline or @file.json. "
                "messages and maxTokens are required."
            ),
            show_default=False,
        ),
    ],
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Send a full messages request to an Anthropic Claude model.

    For multi-turn conversations, tool use, extended thinking, documents and
    images. --request is the API's AnthropicMessagesRequest with its JSON
    field names: messages and maxTokens (required), system, temperature,
    thinking, tools, toolChoice, stopSequences, topK, topP and outputConfig.
    Message roles are USER or ASSISTANT (lower case is accepted).

    Examples:

    \b
    pltr language-models anthropic messages-advanced <MODEL_API_NAME> \\
        --request @conversation.json
    pltr language-models anthropic messages-advanced <MODEL_API_NAME> --request \\
        '{"messages": [{"role": "USER", "content": [{"type": "text", "text": "Hi"}]}],
          "maxTokens": 2000, "thinking": {"type": "enabled", "budgetTokens": 1500}}'
    """
    body = _parse_messages_request(request)
    with spinner("Sending messages..."):
        response = LanguageModelsService(profile=profile).send_messages_advanced(
            model_id,
            messages=body["messages"],
            max_tokens=body["maxTokens"],
            system=body.get("system"),
            temperature=body.get("temperature"),
            thinking=body.get("thinking"),
            tools=body.get("tools"),
            tool_choice=body.get("toolChoice"),
            stop_sequences=body.get("stopSequences"),
            top_k=body.get("topK"),
            top_p=body.get("topP"),
            output_config=body.get("outputConfig"),
        )
    emit(response, format=format, output=output, columns=MESSAGE_COLUMNS)


# ===== OpenAI =====


class _EncodingChoice(click.Choice):
    """``--encoding``: only ``float``; ``base64`` fails with the reason.

    The API accepts ``BASE64``, but the SDK's response model holds lists of
    floats (``OpenAiEmbeddingsResponse.data: List[List[float]]``), so a
    base64 answer can't be decoded and the command would fail after the
    call (exit 7).
    """

    def convert(self, value: Any, param: Any, ctx: Any) -> Any:
        if isinstance(value, str) and value.lower() == "base64":
            self.fail(
                "base64 isn't supported: foundry-platform-sdk reads embeddings "
                "only as lists of floats, so a base64 response can't be decoded. "
                "Leave out --encoding (float).",
                param,
                ctx,
            )
        return super().convert(value, param, ctx)


@openai_app.command("embeddings")
@pltr_command(sdk="language_models.OpenAiModel.embeddings", beta=True)
def openai_embeddings(
    model_id: ModelApiName,
    input: Annotated[
        str,
        typer.Option(
            "--input",
            "-i",
            help=(
                'Text to embed: a string, a JSON array of strings (\'["a", "b"]\') '
                "or @file.json."
            ),
            show_default=False,
        ),
    ],
    dimensions: Annotated[
        Optional[int],
        typer.Option(
            "--dimensions",
            "-d",
            min=1,
            help="Number of dimensions of the embeddings (not every model supports it).",
            show_default=False,
        ),
    ] = None,
    encoding: Annotated[
        Optional[str],
        typer.Option(
            "--encoding",
            "-e",
            click_type=_EncodingChoice(["float"], case_sensitive=False),
            help=(
                "Encoding of the embeddings: float (the default). base64 isn't "
                "supported: the SDK can't decode it."
            ),
            show_default=False,
        ),
    ] = None,
    profile: ProfileOption = None,
    format: FormatOption = "table",
    output: OutputOption = None,
    preview: PreviewNoopOption = False,
):
    """Embed texts with an OpenAI embedding model.

    The table shows one row per input with a preview of its vector; CSV has
    the whole vector as a JSON array, and --format json prints the API's
    response ({"data": [[...], ...], "model": ..., "usage": ...}).

    Examples:

    \b
    pltr language-models openai embeddings <MODEL_API_NAME> -i "Machine learning"
    pltr language-models openai embeddings <MODEL_API_NAME> -i '["Doc 1", "Doc 2"]' \\
        --format json --output embeddings.json
    """
    texts = _parse_input_texts(input)
    with spinner("Generating embeddings..."):
        response = LanguageModelsService(profile=profile).generate_embeddings(
            model_id, texts, dimensions=dimensions, encoding_format=encoding
        )
    emit(
        response,
        format=format,
        output=output,
        columns=EMBEDDING_CSV_COLUMNS
        if format.lower() == "csv"
        else EMBEDDING_TABLE_COLUMNS,
        rows=_embedding_rows,
        title=f"{response.model} ({response.usage.prompt_tokens} prompt tokens)",
    )
