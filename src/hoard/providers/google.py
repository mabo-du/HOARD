"""google.py — Google Gemini provider implementation.

Connects to the Gemini API via generateContent endpoint.
Structured output is handled via response_mime_type + response_schema.

exports: GoogleProvider
"""

from __future__ import annotations

from typing import Any

from hoard.providers.protocol import (
    ModelProvider,
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


class GoogleProvider:
    """Provider for Google's Gemini models.

    Args:
        model_name: Gemini model ID (e.g. 'gemini-2.5-flash-lite').
        api_key: Google AI Studio API key.
        base_url: API base URL (default https://generativelanguage.googleapis.com/v1beta).
    """

    provider_name = "google"

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash-lite",
        api_key: str = "",
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
    ) -> None:
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_output=True,
            supports_vision=True,
            supports_streaming=True,
            supports_thinking=False,
            max_context_window=1_000_000,
            supported_modalities=[Modality.TEXT, Modality.VISION, Modality.STRUCTURED],
            provider_name=self.provider_name,
            model_name=self.model_name,
            api_format="google",
            input_cost_per_1m=0.10,
            output_cost_per_1m=0.40,
        )

    async def is_available(self) -> bool:
        """Check if the API key is valid."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/models?key={self.api_key}",
                )
                return resp.status_code == 200
        except Exception:
            return False

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Send a request to the Gemini generateContent endpoint.

        Handles:
        - Structured output via generationConfig.response_mime_type + response_schema
        - Vision via inline_data parts
        - System instruction as a top-level parameter
        """
        import httpx
        import json

        # Separate system instruction
        system_text: str | None = None
        contents: list[dict[str, Any]] = []
        current_role: str | None = None
        current_parts: list[dict[str, Any]] = []

        def _flush() -> None:
            """Flush current role's parts into contents."""
            nonlocal current_role, current_parts
            if current_role and current_parts:
                contents.append({"role": current_role, "parts": current_parts})
            current_parts = []

        for msg in request.messages:
            role = msg.get("role", "user")
            text = msg.get("content", "")

            if role == "system":
                system_text = text
                continue

            # Map roles: Gemini uses "user" and "model" (not "assistant")
            gemini_role = "model" if role == "assistant" else "user"

            if gemini_role != current_role:
                _flush()
                current_role = gemini_role

            # Text part
            current_parts.append({"text": text})

            # Image parts
            if request.images and role == "user":
                for b64_img in request.images:
                    current_parts.append({
                        "inline_data": {
                            "mime_type": "image/png",
                            "data": b64_img,
                        },
                    })

        _flush()

        # Build the request body
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens or 8192,
            },
        }

        if system_text:
            body["system_instruction"] = {"parts": [{"text": system_text}]}

        # Structured output
        if request.response_schema is not None:
            body["generationConfig"]["response_mime_type"] = "application/json"
            body["generationConfig"]["response_schema"] = request.response_schema

        # Merge provider overrides
        body.update(request.provider_kwargs)

        url = (
            f"{self.base_url}/models/{request.model_name or self.model_name}"
            f":generateContent?key={self.api_key}"
        )

        try:
            import httpx
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=body)
        except httpx.TimeoutException as e:
            raise ProviderError(
                f"Google request timed out after 120s", provider=self.provider_name
            ) from e
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot connect to Google API", provider=self.provider_name
            ) from e

        if resp.status_code == 403:
            raise AuthenticationError(
                "Invalid API key — check hoard keys set google",
                provider=self.provider_name,
            )
        if resp.status_code == 429:
            raise RateLimitError("Rate limited", provider=self.provider_name)
        if resp.status_code == 400:
            body_text = resp.text[:500]
            if "maximum context" in body_text.lower():
                raise ContextWindowExceededError(
                    f"Context window exceeded: {body_text}", provider=self.provider_name
                )
            raise ProviderError(
                f"Bad request (400): {body_text}", provider=self.provider_name
            )
        if resp.status_code != 200:
            raise ProviderError(
                f"Google returned HTTP {resp.status_code}: {resp.text[:500]}",
                provider=self.provider_name,
                status_code=resp.status_code,
            )

        data = resp.json()

        # Extract content from response
        content = ""
        try:
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                content = "".join(p.get("text", "") for p in parts)
        except (IndexError, KeyError):
            content = ""

        # Extract token usage from Gemini's usageMetadata
        usage_meta = data.get("usageMetadata", {})
        prompt_tokens = usage_meta.get("promptTokenCount", 0)
        completion_tokens = usage_meta.get("candidatesTokenCount", 0)
        total_tokens = usage_meta.get("totalTokenCount", prompt_tokens + completion_tokens)
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimate_cost(
                self.provider_name, self.model_name,
                prompt_tokens, completion_tokens,
            ),
        )

        return InferenceResponse(
            content=content,
            usage=usage,
            provider_name=self.provider_name,
            model_name=self.model_name,
            raw_response=data,
        )
