"""Realistic language-model JSON bodies for stub_foundry_http tests.

``anthropic_response`` and ``embeddings_response`` use the Foundry API's
shapes (``AnthropicMessagesResponse``, ``OpenAiEmbeddingsResponse``), so the
SDK decodes them into its real models; they contain no timestamps, so pltr's
JSON output equals the body.

``language-models enroll`` calls endpoints outside the SDK (a labeled
direct-HTTP exception) whose response shapes aren't documented; its tests use
small literal bodies.
"""

from typing import Any, Dict, List, Sequence

MODEL_API_NAME = "claude-sonnet"
EMBEDDING_MODEL = "text-embedding-3-small"
MODEL_RID = "ri.language-model-service..language-model.anthropic_claude_3_5_sonnet"


def anthropic_response(text: str = "Hello there!", **overrides: Any) -> Dict[str, Any]:
    """An ``AnthropicMessagesResponse`` with one text block."""
    body: Dict[str, Any] = {
        "content": [{"type": "text", "text": text}],
        "id": "msg_01XFDUDYJgAACzvnptvVoYEL",
        "model": MODEL_API_NAME,
        "role": "ASSISTANT",
        "stopReason": "end_turn",
        "usage": {"inputTokens": 12, "outputTokens": 6},
    }
    body.update(overrides)
    return body


def tool_use_response() -> Dict[str, Any]:
    """An ``AnthropicMessagesResponse`` that calls a tool."""
    return anthropic_response(
        content=[
            {"type": "text", "text": "Let me check the weather."},
            {
                "type": "toolUse",
                "id": "toolu_01A09q90qw90lq917835lq9",
                "name": "get_weather",
                "input": {"city": "London"},
            },
        ],
        stopReason="tool_use",
    )


def embeddings_response(
    vectors: Sequence[Sequence[float]] = (
        (0.0123, -0.0456, 0.0789, 0.1011, -0.1213),
        (0.2, 0.1, -0.3, 0.4, 0.5),
    ),
    prompt_tokens: int = 4,
) -> Dict[str, Any]:
    """An ``OpenAiEmbeddingsResponse``: one vector per input."""
    data: List[List[float]] = [list(vector) for vector in vectors]
    return {
        "data": data,
        "model": EMBEDDING_MODEL,
        "usage": {"promptTokens": prompt_tokens},
    }
