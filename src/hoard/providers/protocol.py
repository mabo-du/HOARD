"""protocol.py — Core data models and abstract interface for model providers.

Defines the ModelProvider protocol that all local and cloud providers
implement, plus the request/response data models shared across all phases.

exports: ModelProvider, ProviderCapabilities, InferenceRequest,
         InferenceResponse, TokenUsage, Modality
used_by: hoard.providers.ollama, .openai, .anthropic, .google, .router
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


# ── Enums ────────────────────────────────────────────────────────────────────


class Modality(str, Enum):
    """Inference modalities supported by HOARD phases."""

    TEXT = "text"  # Plain text chat (Phase 3, Phase 4)
    VISION = "vision"  # Image + text input (Phase 2)
    STRUCTURED = "structured"  # JSON schema output (Phase 1, Phase 4)


class PrivacyTier(str, Enum):
    """Data privacy classification for cloud requests."""

    STRICT_LOCAL = "strict_local"  # Air-gapped — never send data to network
    SANITIZED_CLOUD = "sanitized_cloud"  # Send text only; scrub coordinates, no images
    FULL_HYBRID = "full_hybrid"  # Full data flow (institutional DPAs only)


# ── Data Models ──────────────────────────────────────────────────────────────


@dataclass
class TokenUsage:
    """Token and cost tracking for a single inference request."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def add(self, other: TokenUsage) -> TokenUsage:
        """Combine two usage records (for chunk-and-merge aggregation)."""
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            estimated_cost_usd=self.estimated_cost_usd + other.estimated_cost_usd,
        )


@dataclass
class ProviderCapabilities:
    """Describes what a provider can do — used by the router for selection."""

    supports_structured_output: bool = False
    supports_vision: bool = False
    supports_streaming: bool = False
    supports_thinking: bool = False
    max_context_window: int = 4096
    supported_modalities: list[Modality] = field(default_factory=lambda: [Modality.TEXT])

    # Provider identity
    provider_name: str = ""
    model_name: str = ""
    api_format: str = ""  # "ollama", "openai", "anthropic", "google"

    # Pricing per 1M tokens (USD) — used for cost estimation
    input_cost_per_1m: float = 0.0
    output_cost_per_1m: float = 0.0


@dataclass
class InferenceRequest:
    """Normalised request that every ModelProvider implementation can handle."""

    messages: list[dict[str, Any]]
    model_name: str = ""
    temperature: float = 0.0
    max_tokens: int | None = None

    # Structured output (Phase 1, Phase 4)
    response_schema: dict[str, Any] | None = None  # JSON Schema dict
    template_format: str | None = None  # NuExtract empty-JSON template string

    # Vision (Phase 2)
    images: list[str] | None = None  # Base64-encoded PNGs

    # Provider-specific overrides
    provider_kwargs: dict[str, Any] = field(default_factory=dict)

    # Context window management
    estimated_input_tokens: int | None = None  # Set by caller for size estimates


@dataclass
class InferenceResponse:
    """Normalised response returned by every ModelProvider implementation."""

    content: str
    usage: TokenUsage = field(default_factory=TokenUsage)
    provider_name: str = ""
    model_name: str = ""
    raw_response: Any = None


# ── Provider Pricing Manifest ────────────────────────────────────────────────
# Used for cost estimation when usage stats are not returned by the provider.

PRICING: dict[str, dict[str, tuple[float, float]]] = {
    # provider -> model -> (input_cost_per_1m, output_cost_per_1m)
    "ollama": {"*": (0.0, 0.0)},  # Local inference is "free" (hardware amortised separately)
    "openai": {
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4o": (2.50, 10.00),
    },
    "openrouter": {"*": (0.0, 0.0)},  # Dynamic pricing — use OpenRouter's API response
    "anthropic": {
        "claude-3-5-haiku-20241022": (0.80, 4.00),
        "claude-3-5-sonnet-20241022": (3.00, 15.00),
        "claude-sonnet-4-20250514": (3.00, 15.00),
    },
    "google": {
        "gemini-2.5-flash": (0.30, 2.50),
        "gemini-2.5-flash-lite": (0.10, 0.40),
        "gemini-2.5-pro": (1.25, 10.00),
    },
}


def estimate_cost(provider: str, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost for a request based on the pricing manifest.

    Falls back to $0 for unknown provider/model combinations.
    """
    provider_pricing = PRICING.get(provider, {})
    # Try exact model match first, then wildcard
    costs = provider_pricing.get(model) or provider_pricing.get("*")
    if costs is None:
        return 0.0
    input_rate, output_rate = costs
    return (prompt_tokens / 1_000_000 * input_rate) + (
        completion_tokens / 1_000_000 * output_rate
    )


# ── Protocol ─────────────────────────────────────────────────────────────────


@runtime_checkable
class ModelProvider(Protocol):
    """Interface that every provider backend must implement.

    Implementations are stateless configuration objects — they hold connection
    details (base URL, API key reference) but no runtime state.
    """

    provider_name: str
    model_name: str

    async def generate(self, request: InferenceRequest) -> InferenceResponse:
        """Execute a normalised inference request against this provider.

        Args:
            request: Normalised inference parameters.

        Returns:
            Normalised inference response with content and usage stats.

        Raises:
            ConnectionError: If the provider endpoint is unreachable.
            AuthenticationError: If credentials are invalid/expired.
            RateLimitError: If the provider rate-limits the request.
            ProviderError: For other provider-specific failures.
        """
        ...

    async def is_available(self) -> bool:
        """Lightweight health check — returns True if the provider is reachable."""
        ...

    def capabilities(self) -> ProviderCapabilities:
        """Return this provider's capabilities for router selection."""
        ...


# ── Custom Exceptions ────────────────────────────────────────────────────────


class ProviderError(Exception):
    """Base exception for all provider errors."""

    def __init__(self, message: str, provider: str = "", status_code: int | None = None) -> None:
        self.provider = provider
        self.status_code = status_code
        super().__init__(message)


class AuthenticationError(ProviderError):
    """Invalid or expired credentials."""


class RateLimitError(ProviderError):
    """Provider rate-limited the request."""


class ContextWindowExceededError(ProviderError):
    """Input exceeds the provider's context window."""
