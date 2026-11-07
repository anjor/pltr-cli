"""Contract-test cases for src/pltr/commands/language_models.py (see __init__.py)."""

import json

from tests import foundry_json_language_models as lm

SUCCESS = {
    "language-models anthropic messages": [{"json": lm.anthropic_response()}],
    "language-models anthropic messages-advanced": [{"json": lm.anthropic_response()}],
    "language-models openai embeddings": [{"json": lm.embeddings_response()}],
    # enroll is a labeled direct-HTTP command (requests, not httpx)
    "language-models enroll": [{"json": {"status": "ENROLLED"}}],
}

ARGS = {
    # --request must be a messages request object
    "language-models anthropic messages-advanced": [
        lm.MODEL_API_NAME,
        "--request",
        json.dumps(
            {
                "messages": [
                    {"role": "USER", "content": [{"type": "text", "text": "Hi"}]}
                ],
                "maxTokens": 16,
            }
        ),
    ],
}
