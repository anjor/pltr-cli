"""
LanguageModels commands for Foundry.
Provides commands for Anthropic Claude models and OpenAI embeddings.
"""

import typer
import json
from typing import Optional, List, Any
from pathlib import Path
from rich.console import Console

from ..services.language_models import LanguageModelsService
from ..utils.formatting import OutputFormatter
from ..utils.progress import SpinnerProgressTracker
from ..auth.base import ProfileNotFoundError, MissingCredentialsError
from ..utils.completion import (
    complete_profile,
    complete_output_format,
)

# Create main app and sub-apps
app = typer.Typer(help="Interact with language models")
anthropic_app = typer.Typer(help="Anthropic Claude models")
openai_app = typer.Typer(help="OpenAI models")

# Add sub-apps
app.add_typer(anthropic_app, name="anthropic")
app.add_typer(openai_app, name="openai")

console = Console()
formatter = OutputFormatter(console)


def parse_json_input(input_str: str) -> Any:
    """
    Parse JSON input from string or file.

    Supports:
    - Inline JSON: '{"key": "value"}' or '["item1", "item2"]'
    - File reference: @input.json

    Args:
        input_str: Input string or file reference

    Returns:
        Parsed JSON data

    Raises:
        FileNotFoundError: If file reference doesn't exist
        json.JSONDecodeError: If JSON is invalid
    """
    if not input_str:
        return None

    # Handle file reference
    if input_str.startswith("@"):
        file_path = Path(input_str[1:])
        if not file_path.exists():
            raise FileNotFoundError(f"Input file not found: {file_path}")

        with open(file_path, "r") as f:
            return json.load(f)

    # Handle inline JSON
    return json.loads(input_str)


def display_anthropic_response(response: dict, format: str, output: Optional[str]):
    """
    Display Anthropic model response with token usage.

    Args:
        response: Response dictionary from service
        format: Output format
        output: Optional output file path
    """
    # Display token usage prominently if available
    if "usage" in response:
        usage = response["usage"]
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        total_tokens = usage.get("totalTokens", input_tokens + output_tokens)

        formatter.print_info(
            f"Token usage - Input: {input_tokens}, Output: {output_tokens}, Total: {total_tokens}"
        )

    # Display full response
    if output:
        formatter.save_to_file(response, output, format)
        formatter.print_success(f"Response saved to {output}")
    else:
        formatter.display(response, format)


def display_openai_response(response: dict, format: str, output: Optional[str]):
    """
    Display OpenAI model response with token usage.

    Args:
        response: Response dictionary from service
        format: Output format
        output: Optional output file path
    """
    # Display token usage prominently if available
    if "usage" in response:
        usage = response["usage"]
        prompt_tokens = usage.get("promptTokens", 0)
        total_tokens = usage.get("totalTokens", prompt_tokens)

        formatter.print_info(
            f"Token usage - Prompt: {prompt_tokens}, Total: {total_tokens}"
        )

    # Display full response
    if output:
        formatter.save_to_file(response, output, format)
        formatter.print_success(f"Response saved to {output}")
    else:
        formatter.display(response, format)


# ===== Anthropic Commands =====


@anthropic_app.command("messages")
def anthropic_messages(
    model_id: str = typer.Argument(
        ...,
        help="Model Resource Identifier (ri.language-models.main.model.<id>)",
    ),
    message: str = typer.Option(
        ...,
        "--message",
        "-m",
        help="User message text",
    ),
    max_tokens: int = typer.Option(
        1024,
        "--max-tokens",
        help="Maximum tokens to generate",
    ),
    system: Optional[str] = typer.Option(
        None,
        "--system",
        "-s",
        help="System prompt to guide model behavior",
    ),
    temperature: Optional[float] = typer.Option(
        None,
        "--temperature",
        "-t",
        help="Sampling temperature (0.0-1.0). Lower is more deterministic.",
        min=0.0,
        max=1.0,
    ),
    stop: Optional[List[str]] = typer.Option(
        None,
        "--stop",
        help="Stop sequences (can be specified multiple times)",
    ),
    top_k: Optional[int] = typer.Option(
        None,
        "--top-k",
        help="Sample from top K tokens (Anthropic models only)",
        min=1,
    ),
    top_p: Optional[float] = typer.Option(
        None,
        "--top-p",
        help="Nucleus sampling threshold (0.0-1.0)",
        min=0.0,
        max=1.0,
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Send a single message to an Anthropic Claude model.

    Simple interface for single-turn Q&A with Claude models. For multi-turn
    conversations, tool calling, or advanced features, use messages-advanced.

    Examples:

        # Basic message
        pltr language-models anthropic messages ri.language-models.main.model.abc123 \\
            --message "Explain quantum computing"

        # With system prompt and custom parameters
        pltr language-models anthropic messages ri.language-models.main.model.abc123 \\
            --message "Write a haiku" \\
            --system "You are a poetic assistant" \\
            --temperature 0.8 \\
            --max-tokens 100

        # With stop sequences
        pltr language-models anthropic messages ri.language-models.main.model.abc123 \\
            --message "List three items" \\
            --stop "." --stop "\\n\\n"

        # Save response to file
        pltr language-models anthropic messages ri.language-models.main.model.abc123 \\
            --message "Summarize AI trends" \\
            --output response.json
    """
    try:
        service = LanguageModelsService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Sending message..."):
            response = service.send_message(
                model_id=model_id,
                message=message,
                max_tokens=max_tokens,
                system=system,
                temperature=temperature,
                stop_sequences=stop if stop else None,
                top_k=top_k,
                top_p=top_p,
                preview=preview,
            )

        display_anthropic_response(response, format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        formatter.print_error(f"Invalid input: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Operation failed: {e}")
        raise typer.Exit(1)


@anthropic_app.command("messages-advanced")
def anthropic_messages_advanced(
    model_id: str = typer.Argument(
        ...,
        help="Model Resource Identifier (ri.language-models.main.model.<id>)",
    ),
    request: str = typer.Option(
        ...,
        "--request",
        "-r",
        help="Request JSON (inline or @file.json). Must include 'messages' and 'maxTokens'.",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Send messages to Anthropic Claude model with advanced features.

    Accepts full SDK request structure, enabling:
    - Multi-turn conversations
    - Tool/function calling
    - Extended thinking mode
    - Document and image processing
    - Citations

    The request must be a JSON object containing:
    - messages: List of message objects with role and content
    - maxTokens: Maximum tokens to generate

    Optional fields:
    - system: System prompt blocks
    - temperature: Sampling temperature (0.0-1.0)
    - thinking: Extended thinking configuration
    - tools: Tool definitions for function calling
    - toolChoice: Tool selection strategy
    - stopSequences: Sequences that stop generation
    - topK: Sample from top K tokens
    - topP: Nucleus sampling threshold

    Examples:

        # Multi-turn conversation from file
        # conversation.json:
        # {
        #   "messages": [
        #     {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
        #     {"role": "assistant", "content": [{"type": "text", "text": "Hello!"}]},
        #     {"role": "user", "content": [{"type": "text", "text": "Help me"}]}
        #   ],
        #   "maxTokens": 500
        # }
        pltr language-models anthropic messages-advanced ri.language-models.main.model.abc123 \\
            --request @conversation.json

        # Inline JSON with system prompt
        pltr language-models anthropic messages-advanced ri.language-models.main.model.abc123 \\
            --request '{"messages": [{"role": "user", "content": [{"type": "text", "text": "Hi"}]}], "maxTokens": 100, "system": [{"type": "text", "text": "Be concise"}]}'

        # With extended thinking
        pltr language-models anthropic messages-advanced ri.language-models.main.model.abc123 \\
            --request '{"messages": [{"role": "user", "content": [{"type": "text", "text": "Solve this problem"}]}], "maxTokens": 2000, "thinking": {"type": "enabled", "budget": 10000}}'
    """
    try:
        # Parse request JSON
        request_data = parse_json_input(request)

        # Validate required fields
        if not isinstance(request_data, dict):
            raise ValueError("Request must be a JSON object")
        if "messages" not in request_data:
            raise ValueError("Request must include 'messages' field")
        if "maxTokens" not in request_data:
            raise ValueError("Request must include 'maxTokens' field")

        service = LanguageModelsService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Sending messages..."):
            response = service.send_messages_advanced(
                model_id=model_id,
                messages=request_data["messages"],
                max_tokens=request_data["maxTokens"],
                system=request_data.get("system"),
                temperature=request_data.get("temperature"),
                thinking=request_data.get("thinking"),
                tools=request_data.get("tools"),
                tool_choice=request_data.get("toolChoice"),
                stop_sequences=request_data.get("stopSequences"),
                top_k=request_data.get("topK"),
                top_p=request_data.get("topP"),
                preview=preview,
            )

        display_anthropic_response(response, format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        formatter.print_error(f"Invalid input: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Operation failed: {e}")
        raise typer.Exit(1)


# ===== OpenAI Commands =====


@openai_app.command("embeddings")
def openai_embeddings(
    model_id: str = typer.Argument(
        ...,
        help="Model Resource Identifier (ri.language-models.main.model.<id>)",
    ),
    input: str = typer.Option(
        ...,
        "--input",
        "-i",
        help='Input text(s). Single string, JSON array \'["text1", "text2"]\', or @file.json',
    ),
    dimensions: Optional[int] = typer.Option(
        None,
        "--dimensions",
        "-d",
        help="Custom embedding dimensions (not all models support this)",
        min=1,
    ),
    encoding: Optional[str] = typer.Option(
        None,
        "--encoding",
        "-e",
        help="Output encoding format: 'float' or 'base64'",
    ),
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Profile name",
        autocompletion=complete_profile,
    ),
    format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format (table, json, csv)",
        autocompletion=complete_output_format,
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    preview: bool = typer.Option(
        False,
        "--preview",
        help="Enable preview mode",
    ),
):
    """
    Generate embeddings for text using an OpenAI model.

    Accepts single text strings or multiple texts for batch processing.
    Returns embedding vectors that can be used for semantic search,
    clustering, or similarity comparisons.

    Examples:

        # Single text
        pltr language-models openai embeddings ri.language-models.main.model.xyz789 \\
            --input "Machine learning is fascinating"

        # Multiple texts (inline JSON array)
        pltr language-models openai embeddings ri.language-models.main.model.xyz789 \\
            --input '["Document 1", "Document 2", "Document 3"]'

        # Multiple texts from file
        # texts.json: ["Text 1", "Text 2", "Text 3"]
        pltr language-models openai embeddings ri.language-models.main.model.xyz789 \\
            --input @texts.json

        # Custom dimensions and encoding
        pltr language-models openai embeddings ri.language-models.main.model.xyz789 \\
            --input "Sample text" \\
            --dimensions 1024 \\
            --encoding base64

        # Save embeddings to file
        pltr language-models openai embeddings ri.language-models.main.model.xyz789 \\
            --input '["Text 1", "Text 2"]' \\
            --output embeddings.json
    """
    try:
        # Parse input - handle string or array
        input_data = (
            parse_json_input(input)
            if input.startswith("@") or input.startswith("[")
            else input
        )

        # Convert to list if single string
        if isinstance(input_data, str):
            input_texts = [input_data]
        elif isinstance(input_data, list):
            input_texts = input_data
        else:
            raise ValueError("Input must be a string or array of strings")

        # Validate encoding format if provided
        if encoding and encoding not in ["float", "base64"]:
            raise ValueError("Encoding format must be 'float' or 'base64'")

        service = LanguageModelsService(profile=profile)

        with SpinnerProgressTracker().track_spinner("Generating embeddings..."):
            response = service.generate_embeddings(
                model_id=model_id,
                input_texts=input_texts,
                dimensions=dimensions,
                encoding_format=encoding,
                preview=preview,
            )

        display_openai_response(response, format, output)

    except (ProfileNotFoundError, MissingCredentialsError) as e:
        formatter.print_error(f"Authentication error: {e}")
        raise typer.Exit(1)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        formatter.print_error(f"Invalid input: {e}")
        raise typer.Exit(1)
    except Exception as e:
        formatter.print_error(f"Operation failed: {e}")
        raise typer.Exit(1)
