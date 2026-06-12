"""openai.py — OpenAI / OpenRouter provider implementation.

Supports OpenAI-compatible APIs including:
- OpenAI (api.openai.com)
- OpenRouter (openrouter.ai/api/v1) — adds HTTP-Referer and X-Title headers
- Any custom OpenAI-compatible endpoint (vLLM, TGI, etc.)

exports: OpenAIProvider
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


class OpenAIProvider:
    """Provider for OpenAI-compatible chat completion APIs.

    Args:
        model_name: Model identifier (e.g. 'gpt-4o-mini', 'openai/gpt-4o-mini').
        api_key: OpenAI API key.
        base_url: API base URL (default https://api.openai.com/v1).
        is_openrouter: If True, adds OpenRouter-specific headers.
    """

    provider_name = "openai"

    def __init__(
        self,
        model_name: str = "gpt-4o-mini",
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        is_openrouter: bool = False,
    ) -> None:
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.is_openrouter = is_openrouter

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_output=True,
            supports_vision=True,
            supports_streaming=True,
            supports_thinking=False,
            max_context_window=128000,
            supported_modalities=[Modality.TEXT, Modality.VISION, Modality.STRUCTURED],
            provider_name=self.provider_name,
            model_name=self.model_name,
            api_format="openai",
        )

    async def is_available(self) -> bool:
        """Check if the API endpoint is reachable and the key is valid."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Send a chat completion request to the OpenAI-compatible API.

        Handles:
        - Structured output via response_format (json_schema or json_object)
        - Vision via content array with image_url parts
        - OpenRouter-specific headers when configured
        """
        import httpx

        # Build message content — handle vision parts
        messages: list[dict[str, Any]] = []
        for msg in request.messages:
            role = msg.get("role", "user")
            text = msg.get("content", "")

            if request.images and role == "user":
                # Build content array with text + image parts
                content: list[dict[str, Any]] = [{"type": "text", "text": text}]
                for b64_img in request.images:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64_img}"},
                    })
                messages.append({"role": role, "content": content})
            else:
                messages.append({"role": role, "content": text})

        # Build the request body
        body: dict[str, Any] = {
            "model": request.model_name or self.model_name,
            "messages": messages,
            "temperature": request.temperature,
        }

        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens

        # Structured output
        if request.response_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_response",
                    "schema": request.response_schema,
                    "strict": True,
                },
            }

        # Merge provider-level overrides (e.g. OpenRouter-specific params)
        body.update(request.provider_kwargs)

        # Build headers
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.is_openrouter:
            headers["HTTP-Referer"] = "https://github.com/mabo-du/hoard"
            headers["X-Title"] = "HOARD"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=body,
                    headers=headers,
                )
        except httpx.TimeoutException as e:
            raise ProviderError(
                "OpenAI request timed out after 120s", provider=self.provider_name
            ) from e
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot connect to {self.base_url}", provider=self.provider_name
            ) from e

        if resp.status_code == 401:
            raise AuthenticationError(
                "Invalid API key — check hoard keys set openai",
                provider=self.provider_name,
            )
        if resp.status_code == 429:
            raise RateLimitError("Rate limited", provider=self.provider_name)
        if resp.status_code == 400:
            body_text = resp.text[:500]
            if "context_length" in body_text.lower() or "maximum context" in body_text.lower():
                raise ContextWindowExceededError(
                    f"Context window exceeded: {body_text}", provider=self.provider_name
                )
            raise ProviderError(
                f"Bad request (400): {body_text}", provider=self.provider_name
            )
        if resp.status_code != 200:
            raise ProviderError(
                f"API returned HTTP {resp.status_code}: {resp.text[:500]}",
                provider=self.provider_name,
                status_code=resp.status_code,
            )

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")

        # Extract usage
        usage_data = data.get("usage", {})
        pt = usage_data.get("prompt_tokens", 0)
        ct = usage_data.get("completion_tokens", 0)
        usage = TokenUsage(
            prompt_tokens=pt,
            completion_tokens=ct,
            total_tokens=usage_data.get("total_tokens", pt + ct),
            estimated_cost_usd=estimate_cost(self.provider_name, self.model_name, pt, ct),
        )

        return InferenceResponse(
            content=content,
            usage=usage,
            provider_name=self.provider_name,
            model_name=self.model_name,
            raw_response=data,
        )
