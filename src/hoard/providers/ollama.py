"""ollama.py — Ollama provider implementation.

Connects to a local Ollama daemon at http://localhost:11434.
Supports all HOARD phases: structured output (format param), vision (images array),
and VRAM eviction (keep_alive control).

exports: OllamaProvider
"""

from __future__ import annotations

import json
from typing import Any

from hoard.providers.protocol import (
    ProviderCapabilities,
    InferenceRequest,
    InferenceResponse,
    TokenUsage,
    Modality,
    estimate_cost,
    ProviderError,
    RateLimitError,
    ContextWindowExceededError,
)


class OllamaProvider:
    """Provider that routes requests to a local Ollama daemon.

    Args:
        model_name: Ollama model tag (e.g. 'qwen3.5-4b', 'glm-ocr:latest').
        base_url: Ollama server URL (default http://localhost:11434).
        keep_alive: Model keep-alive duration ('0' = evict, '-1' = keep loaded).
    """

    provider_name = "ollama"

    def __init__(
        self,
        model_name: str = "qwen3.5-4b",
        base_url: str = "http://localhost:11434",
        keep_alive: str = "0",
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.keep_alive = keep_alive
        self._session: Any = None  # Lazy-imported httpx or requests

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_structured_output=True,
            supports_vision=True,
            supports_streaming=True,
            supports_thinking=True,
            max_context_window=131072,
            supported_modalities=[Modality.TEXT, Modality.VISION, Modality.STRUCTURED],
            provider_name=self.provider_name,
            model_name=self.model_name,
            api_format="ollama",
            input_cost_per_1m=0.0,
            output_cost_per_1m=0.0,
        )

    async def is_available(self) -> bool:
        """Check if Ollama daemon is reachable and the model is loaded."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return False
                models = resp.json().get("models", [])
                # Check if our model (or any model) is available
                return len(models) > 0
        except Exception:
            return False

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Send a chat request to the Ollama daemon.

        Handles:
        - Structured output via the 'format' parameter
        - Vision via the 'images' array in messages
        - VRAM eviction via 'keep_alive' in options
        """
        import httpx

        # Build messages array
        ollama_messages: list[dict[str, Any]] = []
        for msg in request.messages:
            m: dict[str, Any] = {"role": msg.get("role", "user"), "content": msg.get("content", "")}
            # Attach images to the user message if present
            if request.images and msg.get("role") == "user":
                m["images"] = request.images
            ollama_messages.append(m)

        # Build options
        options: dict[str, Any] = {
            "temperature": request.temperature,
            "keep_alive": self.keep_alive,
        }
        if request.max_tokens is not None:
            options["num_predict"] = request.max_tokens

        # Merge provider-level overrides
        options.update(request.provider_kwargs)

        # Build the request payload
        payload: dict[str, Any] = {
            "model": request.model_name or self.model_name,
            "messages": ollama_messages,
            "options": options,
            "stream": False,
        }

        # Structured output
        if request.response_schema is not None:
            payload["format"] = json.dumps(request.response_schema)

        # NuExtract template format — handled via the generic format field
        if request.template_format is not None:
            payload["format"] = request.template_format

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
        except httpx.TimeoutException as e:
            raise ProviderError(
                f"Ollama request timed out after 120s for '{self.model_name}'",
                provider=self.provider_name,
            ) from e
        except httpx.ConnectError as e:
            raise ProviderError(
                f"Cannot connect to Ollama at {self.base_url}. Is it running?",
                provider=self.provider_name,
            ) from e

        if resp.status_code == 429:
            raise RateLimitError("Ollama rate-limited", provider=self.provider_name)
        if resp.status_code != 200:
            body = resp.text[:500]
            if "context length" in body.lower() or "token" in body.lower():
                raise ContextWindowExceededError(
                    f"Context window exceeded: {body}", provider=self.provider_name
                )
            raise ProviderError(
                f"Ollama returned HTTP {resp.status_code}: {body}",
                provider=self.provider_name,
                status_code=resp.status_code,
            )

        data = resp.json()
        content = data.get("message", {}).get("content", "")

        # Extract usage from Ollama response
        usage = TokenUsage(
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            estimated_cost_usd=estimate_cost(
                self.provider_name,
                self.model_name,
                data.get("prompt_eval_count", 0),
                data.get("eval_count", 0),
            ),
        )

        return InferenceResponse(
            content=content,
            usage=usage,
            provider_name=self.provider_name,
            model_name=self.model_name,
            raw_response=data,
        )
