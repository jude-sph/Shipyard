"""Unified LLM client supporting Anthropic, OpenRouter, and local providers."""
import json
import logging
import re
import time
from typing import Any

from src.core import config

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]


def _provider_for_model(model_id: str) -> str:
    """Infer the correct provider for a model ID from the catalogue."""
    for entry in config.MODEL_CATALOGUE:
        if entry["id"] == model_id:
            return entry["provider"]
    # Fallback heuristics: IDs with '/' are typically openrouter
    if "/" in model_id:
        return "openrouter"
    return "anthropic"


def _create_client(provider: str | None = None):
    """Create the appropriate API client based on provider."""
    if provider is None:
        provider = config.PROVIDER
    if provider == "openrouter":
        if not config.OPENROUTER_API_KEY:
            raise RuntimeError(
                "OpenRouter API key not set. Set OPENROUTER_API_KEY in your .env"
            )
        import openai
        return openai.OpenAI(
            api_key=config.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            timeout=120.0,
        )
    elif provider == "local":
        import openai
        return openai.OpenAI(
            api_key="not-needed",
            base_url=config.LOCAL_LLM_URL,
            timeout=120.0,
        )
    else:
        # Default: anthropic
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "Anthropic API key not set. Set ANTHROPIC_API_KEY in your .env"
            )
        import anthropic
        return anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=120.0)


def _get_retry_exceptions(provider: str):
    """Get the retryable exception types for the given provider."""
    if provider in ("openrouter", "local"):
        import openai
        return (openai.APIError, openai.APIConnectionError, openai.RateLimitError, TimeoutError)
    else:
        import anthropic
        return (anthropic.APIError, anthropic.APIConnectionError, anthropic.RateLimitError, TimeoutError)


def _make_request(client, model: str, provider: str, prompt: str, max_tokens: int = 4096) -> tuple[str, int, int, float | None]:
    """Make an API request and return (text, input_tokens, output_tokens, actual_cost_or_none)."""
    if provider in ("openrouter", "local"):
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content or ""
        input_tokens = resp.usage.prompt_tokens if resp.usage else 0
        output_tokens = resp.usage.completion_tokens if resp.usage else 0
        actual_cost = None
        if hasattr(resp.usage, "total_cost"):
            actual_cost = resp.usage.total_cost
        elif hasattr(resp, "_raw_response"):
            try:
                headers = resp._raw_response.headers
                if "x-openrouter-cost" in headers:
                    actual_cost = float(headers["x-openrouter-cost"])
            except Exception:
                pass
    else:
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text
        input_tokens = resp.usage.input_tokens
        output_tokens = resp.usage.output_tokens
        actual_cost = None  # Anthropic direct doesn't return cost
    return text, input_tokens, output_tokens, actual_cost


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response, handling markdown code blocks."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    text = text.strip()
    # Fix common LLM JSON issues: control characters, trailing commas
    # Remove control characters except \n \r \t
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def call_llm(
    prompt: str,
    cost_tracker: Any,
    call_type: str,
    stage: str = "",
    max_tokens: int = 4096,
    client=None,
    level: int = 0,
    model: str | None = None,
) -> dict:
    """Make an LLM API call with retry logic. Returns parsed JSON dict.

    Args:
        prompt: The prompt text to send
        cost_tracker: Object with a record() method for recording usage
        call_type: Type of call for cost tracking (e.g. "analyze", "generate")
        stage: Pipeline stage name for cost tracking (defaults to "")
        max_tokens: Maximum tokens in response
        client: Optional pre-created client (reuse across calls for efficiency)
        level: Decomposition level for cost tracking (used by reqdecomp pipeline)
        model: Model ID to use (defaults to config.MODEL)
    """
    model = model or config.MODEL
    provider = _provider_for_model(model)

    if client is None:
        client = _create_client(provider)

    retry_exceptions = _get_retry_exceptions(provider)
    text = ""

    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(f"API call: {call_type} [{stage}] model={model} provider={provider} (attempt {attempt + 1})")
            logger.debug(f"Prompt length: {len(prompt)} chars")

            text, input_tokens, output_tokens, actual_cost = _make_request(client, model, provider, prompt, max_tokens)

            if not text:
                raise ValueError("LLM returned empty response")

            logger.debug(f"Response length: {len(text)} chars")
            cost_tracker.record(
                call_type=call_type,
                stage=stage,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                actual_cost=actual_cost,
            )

            json_text = _extract_json(text)
            if not json_text:
                logger.error(f"No JSON found in response. Raw text: {text[:500]}")
                raise ValueError(f"LLM response contained no JSON. Raw response starts with: {text[:200]}")
            return json.loads(json_text)

        except retry_exceptions as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                logger.warning(f"API error (attempt {attempt + 1}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"API call failed after {MAX_RETRIES} attempts: {e}")
                raise
        except (json.JSONDecodeError, ValueError) as e:
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAYS[attempt]
                logger.warning(f"Bad response (attempt {attempt + 1}): {e}. Retrying in {delay}s...")
                logger.debug(f"Raw response: {text}")
                time.sleep(delay)
            else:
                logger.error(f"Failed to get valid JSON after {MAX_RETRIES} attempts: {e}")
                logger.debug(f"Raw response: {text}")
                raise


def call_llm_with_tools(
    messages: list[dict],
    tools: list[dict],
    cost_tracker: Any,
    call_type: str,
    stage: str = "",
    max_tokens: int = 4096,
    client=None,
    model: str | None = None,
):
    """Make an LLM API call with tool/function calling support. Returns raw response.

    Used by the chat agent. Requires an OpenAI-compatible client (OpenRouter or local).
    Returns the raw completion response so the caller can inspect tool_calls and content.

    Args:
        messages: Chat message history (list of role/content dicts)
        tools: List of tool definitions in OpenAI function-calling format
        cost_tracker: Object with a record() method for recording usage
        call_type: Type of call for cost tracking
        stage: Pipeline stage name for cost tracking (defaults to "")
        max_tokens: Maximum tokens in response
        client: Optional pre-created client
        model: Model ID to use (defaults to config.MODEL)
    """
    model = model or config.MODEL
    provider = _provider_for_model(model)

    if provider == "anthropic":
        # Anthropic SDK doesn't support OpenAI-style tool calling;
        # route through OpenRouter if an OpenRouter key is available
        if config.OPENROUTER_API_KEY:
            provider = "openrouter"
            # Map direct Anthropic model IDs to OpenRouter format
            if "/" not in model:
                model = f"anthropic/{model}"
        else:
            raise RuntimeError(
                f"Chat agent requires an OpenAI-compatible API. Model '{model}' uses the "
                "Anthropic provider which doesn't support tool calling in this format. "
                "Set an OPENROUTER_API_KEY or select an OpenRouter model."
            )

    if client is None:
        client = _create_client(provider)

    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        tools=tools,
    )

    input_tokens = resp.usage.prompt_tokens if resp.usage else 0
    output_tokens = resp.usage.completion_tokens if resp.usage else 0
    actual_cost = None
    if hasattr(resp.usage, "total_cost"):
        actual_cost = resp.usage.total_cost

    cost_tracker.record(
        call_type=call_type,
        stage=stage,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        actual_cost=actual_cost,
    )

    return resp


def create_client(model: str | None = None):
    """Public factory for creating a reusable client.

    If model is provided, the client is created for the correct provider.
    """
    if model:
        return _create_client(_provider_for_model(model))
    return _create_client()
