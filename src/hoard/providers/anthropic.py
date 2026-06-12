"""anthropic.py — Anthropic Claude provider implementation.

Connects to Anthropic's Messages API. Structured output is handled via
the tool_use paradigm (schema wrapped as a single tool definition).

exports: AnthropicProvider
"""

from __future__ import annotations

from typing import Any

from hoard.providers.protocol import (
    ProviderCapabilities,
    InferenceRequest,
    InferenceResponse,
    TokenUsage,
    Modality,
    estimate_cost,
    ProviderError,
    AuthenticationError,
    RateLimitError,
    ContextWindowExceededError,
)


class AnthropicProvider:
    """Provider for Anthropic's Claude models.

    Args:
        model_name: Claude model ID (e.g. 'claude-sonnet-4-20250514').
        api_key: Anthropic API key (sk-ant-...).
        base_url: API base URL (default https://api.anthropic.com/v1).
    """

    provider_name = "anthropic"

    def __init__(
        self,
        model_name: str = "claude-sonnet-4-20250514",
        api_key: str = "",
        base_url: str = "https://api.anthropic.com/v1",
    ) -> None:
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_output=True,  # via tool_use
            supports_vision=True,
            supports_streaming=True,
            supports_thinking=False,
            max_context_window=200000,
            supported_modalities=[Modality.TEXT, Modality.VISION, Modality.STRUCTURED],
            provider_name=self.provider_name,
            model_name=self.model_name,
            api_format="anthropic",
            input_cost_per_1m=3.00,
            output_cost_per_1m=15.00,
        )

    async def is_available(self) -> bool:
        """Check if the API key is valid by listing models."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Send a request to Anthropic's Messages API.

        Handles:
        - Structured output via tool_use with a single mock function
        - Vision via source blocks in content
        - System prompt as a top-level parameter
        """
        import httpx
        import json

        # Separate system prompt from messages
        system_text: str | None = None
        anthropic_messages: list[dict[str, Any]] = []

        for msg in request.messages:
            role = msg.get("role", "user")
            text = msg.get("content", "")

            if role == "system":
                system_text = text
                continue

            if role == "assistant":
                anthropic_messages.append({"role": "assistant", "content": text})
                continue

            # Build user message content — handle vision
            if request.images:
                content_blocks: list[dict[str, Any]] = [
                    {"type": "text", "text": text}
                ]
                for b64_img in request.images:
                    content_blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": b64_img,
                        },
                    })
                anthropic_messages.append({"role": "user", "content": content_blocks})
            else:
                anthropic_messages.append({"role": "user", "content": text})

        # Build the request body
        body: dict[str, Any] = {
            "model": request.model_name or self.model_name,
            "max_tokens": request.max_tokens or 4096,
            "messages": anthropic_messages,
            "temperature": request.temperature,
        }

        if system_text:
            body["system"] = system_text

        # Structured output via tool_use
        if request.response_schema is not None:
            body["tools"] = [
                {
                    "name": "respond_structured",
                    "description": "Respond with structured data matching the provided schema",
                    "input_schema": request.response_schema,
                }
            ]
            body["tool_choice"] = {"type": "tool", "name": "respond_structured"}

        # Merge provider overrides
        body.update(request.provider_kwargs)

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/messages",
                    json=body,
                    headers=headers,
                )
        except httpx.TimeoutException as e:
            raise ProviderError(
                "Anthropic request timed out after 120s", provider=self.provider_name
            ) from e
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot connect to {self.base_url}", provider=self.provider_name
            ) from e

        if resp.status_code == 401:
            raise AuthenticationError(
                "Invalid API key — check hoard keys set anthropic",
                provider=self.provider_name,
            )
        if resp.status_code == 429:
            raise RateLimitError("Rate limited", provider=self.provider_name)
        if resp.status_code == 400:
            body_text = resp.text[:500]
            if "too many tokens" in body_text.lower() or "context" in body_text.lower():
                raise ContextWindowExceededError(
                    f"Context window exceeded: {body_text}", provider=self.provider_name
                )
            raise ProviderError(
                f"Bad request (400): {body_text}", provider=self.provider_name
            )
        if resp.status_code != 200:
            raise ProviderError(
                f"Anthropic returned HTTP {resp.status_code}: {resp.text[:500]}",
                provider=self.provider_name,
                status_code=resp.status_code,
            )

        data = resp.json()

        # Extract content — handle tool_use or direct text
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content = block.get("text", "")
            elif block.get("type") == "tool_use":
                content = json.dumps(block.get("input", {}), indent=2)

        # Extract usage
        usage_data = data.get("usage", {})
        pt = usage_data.get("input_tokens", 0)
        ct = usage_data.get("output_tokens", 0)
        usage = TokenUsage(
            prompt_tokens=pt,
            completion_tokens=ct,
            total_tokens=pt + ct,
            estimated_cost_usd=estimate_cost(self.provider_name, self.model_name, pt, ct),
        )

        return InferenceResponse(
            content=content,
            usage=usage,
            provider_name=self.provider_name,
            model_name=self.model_name,
            raw_response=data,
        )
